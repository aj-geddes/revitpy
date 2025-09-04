"""
Integration helpers for PyRevit + RevitPy workflows.
Demonstrates how the two systems can work together effectively.
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# Mock imports for demonstration (would be actual RevitPy bridge in production)
try:
    from .revitpy_mock import RevitElement, get_elements, get_project_info
except ImportError:
    from revitpy_mock import RevitElement, get_elements, get_project_info


class DataExchangeFormat(Enum):
    """Supported data exchange formats between PyRevit and RevitPy."""
    JSON = "json"
    CSV = "csv"
    PICKLE = "pickle"
    PARQUET = "parquet"


@dataclass
class WorkflowRequest:
    """Request structure for PyRevit -> RevitPy workflows."""
    request_id: str
    workflow_type: str
    parameters: Dict[str, Any]
    element_ids: List[str]
    timestamp: datetime
    priority: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowRequest':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class WorkflowResponse:
    """Response structure for RevitPy -> PyRevit workflows."""
    request_id: str
    status: str  # 'success', 'error', 'processing'
    results: Dict[str, Any]
    execution_time: float
    timestamp: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class PyRevitBridge:
    """Bridge interface for PyRevit integration."""
    
    def __init__(self, exchange_directory: Path = None):
        """Initialize bridge with shared exchange directory."""
        self.exchange_dir = exchange_directory or Path.cwd() / "pyrevit_exchange"
        self.exchange_dir.mkdir(exist_ok=True)
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def export_for_pyrevit(self, data: Any, filename: str, 
                          format_type: DataExchangeFormat = DataExchangeFormat.JSON) -> Path:
        """Export data in format consumable by PyRevit."""
        filepath = self.exchange_dir / f"{filename}.{format_type.value}"
        
        if format_type == DataExchangeFormat.JSON:
            # Handle datetime serialization
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object {obj} is not JSON serializable")
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=json_serializer)
        
        elif format_type == DataExchangeFormat.CSV:
            import pandas as pd
            if isinstance(data, pd.DataFrame):
                data.to_csv(filepath, index=False)
            else:
                # Convert dict/list to DataFrame
                df = pd.DataFrame(data)
                df.to_csv(filepath, index=False)
        
        elif format_type == DataExchangeFormat.PARQUET:
            import pandas as pd
            if isinstance(data, pd.DataFrame):
                data.to_parquet(filepath)
            else:
                df = pd.DataFrame(data)
                df.to_parquet(filepath)
        
        self.logger.info(f"Exported data to {filepath}")
        return filepath
    
    def import_from_pyrevit(self, filename: str, 
                           format_type: DataExchangeFormat = DataExchangeFormat.JSON) -> Any:
        """Import data from PyRevit."""
        filepath = self.exchange_dir / f"{filename}.{format_type.value}"
        
        if not filepath.exists():
            raise FileNotFoundError(f"Exchange file not found: {filepath}")
        
        if format_type == DataExchangeFormat.JSON:
            with open(filepath, 'r') as f:
                return json.load(f)
        
        elif format_type == DataExchangeFormat.CSV:
            import pandas as pd
            return pd.read_csv(filepath)
        
        elif format_type == DataExchangeFormat.PARQUET:
            import pandas as pd
            return pd.read_parquet(filepath)
        
        self.logger.info(f"Imported data from {filepath}")
    
    def create_element_summary(self, elements: List[RevitElement]) -> Dict[str, Any]:
        """Create PyRevit-friendly element summary."""
        summary = {
            'total_elements': len(elements),
            'categories': {},
            'elements': []
        }
        
        # Categorize elements
        for element in elements:
            category = element.category.value
            if category not in summary['categories']:
                summary['categories'][category] = 0
            summary['categories'][category] += 1
            
            # Create simplified element data for PyRevit
            element_data = {
                'id': element.id,
                'name': element.name,
                'category': category,
                'area': round(element.area, 2) if element.area else 0,
                'volume': round(element.volume, 2) if element.volume else 0,
                'parameters': {
                    name: param.value 
                    for name, param in element.parameters.items()
                    if isinstance(param.value, (str, int, float, bool))
                }
            }
            summary['elements'].append(element_data)
        
        return summary
    
    async def process_workflow_request(self, request: WorkflowRequest) -> WorkflowResponse:
        """Process workflow request from PyRevit."""
        start_time = datetime.now()
        
        try:
            # Route to appropriate processor based on workflow type
            if request.workflow_type == 'energy_analysis':
                results = await self._process_energy_analysis(request)
            elif request.workflow_type == 'space_optimization':
                results = await self._process_space_optimization(request)
            elif request.workflow_type == 'structural_analysis':
                results = await self._process_structural_analysis(request)
            elif request.workflow_type == 'iot_integration':
                results = await self._process_iot_integration(request)
            elif request.workflow_type == 'computer_vision':
                results = await self._process_computer_vision(request)
            else:
                raise ValueError(f"Unknown workflow type: {request.workflow_type}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return WorkflowResponse(
                request_id=request.request_id,
                status='success',
                results=results,
                execution_time=execution_time,
                timestamp=datetime.now()
            )
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Workflow processing failed: {str(e)}")
            
            return WorkflowResponse(
                request_id=request.request_id,
                status='error',
                results={},
                execution_time=execution_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _process_energy_analysis(self, request: WorkflowRequest) -> Dict[str, Any]:
        """Process energy analysis workflow."""
        # Simulate advanced energy analysis
        await asyncio.sleep(0.1)  # Simulate computation time
        
        elements = [e for e in get_elements() if e.id in request.element_ids]
        
        results = {
            'analysis_type': 'energy_performance',
            'total_annual_consumption': sum(
                e.get_parameter('AnnualEnergyUse') or 0 for e in elements
            ),
            'efficiency_score': 0.85,  # Calculated efficiency
            'recommendations': [
                'Upgrade HVAC systems in zones with low efficiency',
                'Implement smart lighting controls',
                'Add insulation to exterior walls'
            ],
            'cost_savings_potential': 125000,  # Annual savings in $
            'payback_period_years': 3.2
        }
        
        return results
    
    async def _process_space_optimization(self, request: WorkflowRequest) -> Dict[str, Any]:
        """Process space optimization workflow."""
        await asyncio.sleep(0.2)  # Simulate ML computation
        
        return {
            'optimization_type': 'ml_space_planning',
            'efficiency_improvement': 0.34,  # 34% improvement
            'space_utilization_before': 0.68,
            'space_utilization_after': 0.91,
            'recommended_changes': [
                'Convert 3 private offices to collaboration spaces',
                'Relocate storage areas to optimize flow',
                'Create flexible meeting spaces'
            ],
            'estimated_capacity_increase': 45,  # Additional people
            'implementation_cost': 85000
        }
    
    async def _process_structural_analysis(self, request: WorkflowRequest) -> Dict[str, Any]:
        """Process structural analysis workflow."""
        await asyncio.sleep(0.15)  # Simulate complex calculations
        
        return {
            'analysis_type': 'structural_optimization',
            'safety_factor': 2.1,
            'max_stress_ratio': 0.78,
            'deflection_limits_met': True,
            'weight_optimization': {
                'original_weight_tons': 1250,
                'optimized_weight_tons': 1180,
                'weight_reduction_percent': 5.6,
                'material_cost_savings': 42000
            },
            'critical_elements': [
                {'id': 'beam_345', 'stress_ratio': 0.95, 'status': 'monitor'},
                {'id': 'column_187', 'stress_ratio': 0.88, 'status': 'acceptable'}
            ]
        }
    
    async def _process_iot_integration(self, request: WorkflowRequest) -> Dict[str, Any]:
        """Process IoT integration workflow."""
        await asyncio.sleep(0.05)  # Simulate async API calls
        
        return {
            'integration_type': 'iot_sensor_sync',
            'sensors_connected': 127,
            'data_points_processed': 15420,
            'anomalies_detected': [
                {'sensor_id': 'HVAC_Zone_3_Temp', 'anomaly': 'temperature_spike', 'severity': 'medium'},
                {'sensor_id': 'Lighting_Floor_8', 'anomaly': 'power_consumption_high', 'severity': 'low'}
            ],
            'energy_optimization': {
                'current_efficiency': 0.87,
                'potential_efficiency': 0.93,
                'estimated_savings_monthly': 8500
            },
            'predictive_maintenance': {
                'equipment_needing_attention': 3,
                'estimated_cost_avoidance': 25000
            }
        }
    
    async def _process_computer_vision(self, request: WorkflowRequest) -> Dict[str, Any]:
        """Process computer vision workflow."""
        await asyncio.sleep(0.3)  # Simulate image processing
        
        return {
            'analysis_type': 'construction_progress',
            'images_processed': len(request.parameters.get('image_paths', [])),
            'overall_progress': 0.73,  # 73% complete
            'phase_progress': {
                'foundation': 1.0,
                'structure': 0.95,
                'envelope': 0.68,
                'mep_rough': 0.42,
                'interior': 0.15
            },
            'quality_issues': [
                {'location': 'Floor 8, Zone C', 'issue': 'alignment_deviation', 'severity': 'low'},
                {'location': 'Floor 3, Zone A', 'issue': 'material_defect', 'severity': 'medium'}
            ],
            'completion_forecast': '2024-09-15',
            'schedule_variance_days': -3  # 3 days ahead of schedule
        }


def create_pyrevit_script_template(workflow_type: str) -> str:
    """Generate PyRevit script template for RevitPy integration."""
    
    template = f'''"""
PyRevit script for {workflow_type} using RevitPy integration.
This script demonstrates how PyRevit can leverage RevitPy's advanced capabilities.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# PyRevit imports
from pyrevit import revit, DB, UI
from pyrevit.framework import List
from pyrevit import forms

def collect_elements():
    """Collect elements from Revit for analysis."""
    # Use PyRevit's element collection capabilities
    collector = DB.FilteredElementCollector(revit.doc)
    
    # Example: collect spaces for analysis
    spaces = collector.OfCategory(DB.BuiltInCategory.OST_MEPSpaces).ToElements()
    
    # Convert to simple data structure
    element_data = []
    for space in spaces:
        element_data.append({{
            'id': str(space.Id),
            'name': space.Name,
            'area': space.Area,
            'level': space.Level.Name if space.Level else 'Unknown'
        }})
    
    return element_data

def create_revitpy_request(element_ids, parameters):
    """Create request for RevitPy processing."""
    request = {{
        'request_id': str(uuid.uuid4()),
        'workflow_type': '{workflow_type}',
        'parameters': parameters,
        'element_ids': element_ids,
        'timestamp': datetime.now().isoformat(),
        'priority': 1
    }}
    
    # Write request to exchange directory
    exchange_dir = Path.cwd() / "pyrevit_exchange"
    exchange_dir.mkdir(exist_ok=True)
    
    request_file = exchange_dir / f"request_{{request['request_id']}}.json"
    with open(request_file, 'w') as f:
        json.dump(request, f, indent=2)
    
    return request['request_id']

def wait_for_revitpy_response(request_id, timeout_seconds=30):
    """Wait for RevitPy to process request and return response."""
    import time
    
    exchange_dir = Path.cwd() / "pyrevit_exchange"
    response_file = exchange_dir / f"response_{{request_id}}.json"
    
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if response_file.exists():
            with open(response_file, 'r') as f:
                response = json.load(f)
            
            # Clean up files
            response_file.unlink()
            return response
        
        time.sleep(1)
    
    raise TimeoutError(f"RevitPy response timeout after {{timeout_seconds}} seconds")

def main():
    """Main execution function."""
    try:
        # Step 1: Collect elements using PyRevit
        forms.alert("Collecting elements...", title="{workflow_type}")
        elements = collect_elements()
        
        if not elements:
            forms.alert("No elements found for analysis.")
            return
        
        element_ids = [elem['id'] for elem in elements]
        
        # Step 2: Configure analysis parameters
        parameters = {{
            'analysis_detail': 'high',
            'include_recommendations': True,
            'optimization_target': 'efficiency'
        }}
        
        # Step 3: Send request to RevitPy
        forms.alert("Sending analysis request to RevitPy...", title="Processing")
        request_id = create_revitpy_request(element_ids, parameters)
        
        # Step 4: Wait for response
        response = wait_for_revitpy_response(request_id)
        
        # Step 5: Process results in PyRevit
        if response['status'] == 'success':
            results = response['results']
            
            # Display results using PyRevit UI
            output = []
            output.append(f"Analysis Type: {{results.get('analysis_type', 'Unknown')}}")
            output.append(f"Execution Time: {{response['execution_time']:.2f}} seconds")
            output.append("")
            
            # Add specific results based on workflow type
            if '{workflow_type}' == 'energy_analysis':
                output.append(f"Total Annual Consumption: {{results.get('total_annual_consumption', 0):,.0f}} kWh")
                output.append(f"Efficiency Score: {{results.get('efficiency_score', 0):.2f}}")
                output.append(f"Cost Savings Potential: ${{results.get('cost_savings_potential', 0):,}}")
            
            # Show results
            forms.alert("\\n".join(output), title="{workflow_type} Results")
            
        else:
            forms.alert(f"Analysis failed: {{response.get('error_message', 'Unknown error')}}")
    
    except Exception as e:
        forms.alert(f"Error: {{str(e)}}")

# Execute main function
if __name__ == "__main__":
    main()
'''
    
    return template


# Example usage patterns for PyRevit integration
INTEGRATION_EXAMPLES = {
    'element_export': {
        'description': 'Export Revit elements to RevitPy for advanced analysis',
        'pyrevit_script': 'export_elements_for_analysis.py',
        'revitpy_processor': 'process_element_analysis.py',
        'data_flow': 'PyRevit → JSON → RevitPy → Analysis → JSON → PyRevit'
    },
    
    'real_time_monitoring': {
        'description': 'Real-time building performance monitoring',
        'pyrevit_script': 'setup_monitoring_dashboard.py',
        'revitpy_processor': 'iot_sensor_integration.py',
        'data_flow': 'IoT Sensors → RevitPy → Analysis → WebSocket → PyRevit UI'
    },
    
    'ml_optimization': {
        'description': 'Machine learning-based design optimization',
        'pyrevit_script': 'optimize_design_layout.py',
        'revitpy_processor': 'ml_space_optimizer.py',
        'data_flow': 'PyRevit Elements → ML Analysis → Optimization → Design Updates'
    }
}