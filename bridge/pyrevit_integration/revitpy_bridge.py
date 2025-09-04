"""
Main PyRevit integration library for RevitPy bridge communication.

This module provides a simple interface for PyRevit scripts to communicate
with RevitPy for advanced analysis and processing.
"""

import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union
from pathlib import Path
import tempfile

# PyRevit imports (these would be available in PyRevit environment)
try:
    from pyrevit import revit
    from pyrevit.framework import List as PyRevitList
    from Autodesk.Revit.DB import Element, FilteredElementCollector
    PYREVIT_AVAILABLE = True
except ImportError:
    # For development/testing outside PyRevit
    PYREVIT_AVAILABLE = False

from ..core.config import BridgeConfig
from ..core.exceptions import BridgeException, BridgeTimeoutError, BridgeConnectionError
from ..serialization.element_serializer import RevitElementSerializer
from ..communication.websocket_server import WebSocketBridgeClient
from ..communication.file_exchange import FileExchangeHandler


class RevitPyBridge:
    """
    Main bridge interface for PyRevit scripts to communicate with RevitPy.
    
    This class provides a simple, synchronous interface that PyRevit scripts
    can use to send elements to RevitPy for advanced analysis.
    
    Example Usage:
        # Basic usage
        bridge = RevitPyBridge()
        walls = get_selected_walls()
        results = bridge.execute_analysis(walls, "energy_performance")
        
        # Advanced usage with custom parameters
        bridge = RevitPyBridge(websocket_port=9000)
        analysis_params = {"include_thermal": True, "precision": "high"}
        results = bridge.execute_analysis(walls, "thermal_analysis", analysis_params)
    """
    
    def __init__(self, config: Optional[BridgeConfig] = None,
                 websocket_host: str = "localhost",
                 websocket_port: int = 8765,
                 websocket_path: str = "/bridge",
                 timeout: int = 300):
        """
        Initialize the PyRevit bridge.
        
        Args:
            config: Bridge configuration (optional)
            websocket_host: WebSocket server host
            websocket_port: WebSocket server port
            websocket_path: WebSocket server path
            timeout: Default timeout for analysis requests
        """
        self.config = config or BridgeConfig()
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.websocket_path = websocket_path
        self.default_timeout = timeout
        
        # Initialize serializer
        self.serializer = RevitElementSerializer(self.config.serialization)
        
        # Initialize file handler for large datasets
        self.file_handler = FileExchangeHandler(self.config.communication)
        
        # Connection management
        self._client: Optional[WebSocketBridgeClient] = None
        self._is_connected = False
        
        # Statistics
        self.stats = {
            'requests_sent': 0,
            'requests_successful': 0,
            'requests_failed': 0,
            'total_elements_processed': 0,
            'avg_response_time': 0.0
        }
    
    def connect(self, timeout: int = 10) -> bool:
        """
        Connect to the RevitPy bridge server.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create WebSocket client
            self._client = WebSocketBridgeClient(
                host=self.websocket_host,
                port=self.websocket_port,
                path=self.websocket_path
            )
            
            # Connect using asyncio
            loop = self._get_or_create_event_loop()
            connected = loop.run_until_complete(
                asyncio.wait_for(self._client.connect(), timeout=timeout)
            )
            
            self._is_connected = connected
            return connected
            
        except Exception as e:
            print(f"Failed to connect to RevitPy bridge: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the RevitPy bridge server."""
        if self._client and self._is_connected:
            try:
                loop = self._get_or_create_event_loop()
                loop.run_until_complete(self._client.disconnect())
                self._is_connected = False
            except Exception as e:
                print(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to the RevitPy bridge server."""
        return self._is_connected and self._client is not None
    
    def execute_analysis(self, elements: Union[List, Any], 
                        analysis_type: str,
                        parameters: Optional[Dict[str, Any]] = None,
                        timeout: Optional[int] = None,
                        use_file_exchange: bool = False) -> Dict[str, Any]:
        """
        Execute analysis on elements using RevitPy.
        
        Args:
            elements: List of Revit elements or single element
            analysis_type: Type of analysis to perform
            parameters: Additional parameters for analysis
            timeout: Request timeout (uses default if None)
            use_file_exchange: Use file exchange for large datasets
            
        Returns:
            Analysis results dictionary
        """
        start_time = time.time()
        
        try:
            # Ensure connection
            if not self.is_connected():
                if not self.connect():
                    raise BridgeConnectionError("websocket", "Failed to connect to RevitPy bridge")
            
            # Convert single element to list
            if not isinstance(elements, list):
                elements = [elements]
            
            # Determine if file exchange should be used
            element_count = len(elements)
            if element_count > self.config.serialization.streaming_threshold:
                use_file_exchange = True
            
            # Execute based on exchange method
            if use_file_exchange:
                result = self._execute_analysis_file_exchange(
                    elements, analysis_type, parameters, timeout
                )
            else:
                result = self._execute_analysis_websocket(
                    elements, analysis_type, parameters, timeout
                )
            
            # Update statistics
            execution_time = time.time() - start_time
            self._update_stats(element_count, execution_time, True)
            
            return result
            
        except Exception as e:
            # Update error statistics
            execution_time = time.time() - start_time
            self._update_stats(len(elements) if isinstance(elements, list) else 1, 
                             execution_time, False)
            
            # Re-raise with context
            if isinstance(e, BridgeException):
                raise
            else:
                raise BridgeException(f"Analysis execution failed: {e}")
    
    def _execute_analysis_websocket(self, elements: List[Any],
                                   analysis_type: str,
                                   parameters: Optional[Dict[str, Any]],
                                   timeout: Optional[int]) -> Dict[str, Any]:
        """Execute analysis using WebSocket communication."""
        try:
            # Create analysis request
            request = self.serializer.create_analysis_request(
                elements, analysis_type, parameters or {}
            )
            
            # Send request via WebSocket
            loop = self._get_or_create_event_loop()
            response = loop.run_until_complete(
                self._client.send_message(
                    {
                        'type': 'analysis_request',
                        'data': request
                    },
                    expect_response=True,
                    timeout=timeout or self.default_timeout
                )
            )
            
            # Process response
            if response.get('type') == 'analysis_result':
                result_data = response.get('data', {})
                if result_data.get('success', False):
                    return result_data.get('data', {})
                else:
                    error = result_data.get('error', 'Unknown error')
                    raise BridgeException(f"Analysis failed: {error}")
            else:
                raise BridgeException(f"Unexpected response type: {response.get('type')}")
                
        except asyncio.TimeoutError:
            raise BridgeTimeoutError("analysis", timeout or self.default_timeout)
    
    def _execute_analysis_file_exchange(self, elements: List[Any],
                                       analysis_type: str,
                                       parameters: Optional[Dict[str, Any]],
                                       timeout: Optional[int]) -> Dict[str, Any]:
        """Execute analysis using file exchange for large datasets."""
        try:
            # Serialize elements to file
            temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            serialized_data = self.serializer.serialize_elements(elements, temp_path)
            
            # Create file exchange request
            request_data = {
                'analysis_type': analysis_type,
                'parameters': parameters or {},
                'elements_file': temp_path,
                'element_count': len(elements)
            }
            
            loop = self._get_or_create_event_loop()
            
            # Create request file
            request_id = loop.run_until_complete(
                self.file_handler.create_request_file(request_data)
            )
            
            # Wait for response file
            response_timeout = timeout or self.default_timeout
            start_time = time.time()
            
            while time.time() - start_time < response_timeout:
                # Look for response file
                response_files = loop.run_until_complete(
                    self.file_handler.list_files(file_type='response', status='completed')
                )
                
                for response_file in response_files:
                    if (response_file.metadata and 
                        response_file.metadata.get('request_id') == request_id):
                        
                        # Read response
                        response_data = loop.run_until_complete(
                            self.file_handler.read_file(response_file.file_path.stem)
                        )
                        
                        # Cleanup temporary files
                        Path(temp_path).unlink(missing_ok=True)
                        loop.run_until_complete(
                            self.file_handler.archive_file(request_id)
                        )
                        loop.run_until_complete(
                            self.file_handler.archive_file(response_file.file_path.stem)
                        )
                        
                        return response_data.get('data', {})
                
                # Brief pause before checking again
                time.sleep(1)
            
            # Cleanup on timeout
            Path(temp_path).unlink(missing_ok=True)
            raise BridgeTimeoutError("file_exchange_analysis", response_timeout)
            
        except Exception as e:
            # Cleanup temporary file
            if 'temp_path' in locals():
                Path(temp_path).unlink(missing_ok=True)
            raise
    
    def create_analysis_request(self, elements: Union[List, Any],
                               analysis_type: str,
                               parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create an analysis request without executing it.
        
        This is useful for batch processing or when you want to inspect
        the request before sending it.
        
        Args:
            elements: List of Revit elements or single element
            analysis_type: Type of analysis to perform
            parameters: Additional parameters for analysis
            
        Returns:
            Analysis request dictionary
        """
        if not isinstance(elements, list):
            elements = [elements]
        
        return self.serializer.create_analysis_request(
            elements, analysis_type, parameters or {}
        )
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to RevitPy bridge server.
        
        Returns:
            Connection test results
        """
        try:
            if not self.is_connected():
                if not self.connect():
                    return {
                        'success': False,
                        'error': 'Failed to establish connection',
                        'details': 'Could not connect to RevitPy bridge server'
                    }
            
            # Send ping message
            loop = self._get_or_create_event_loop()
            start_time = time.time()
            
            response = loop.run_until_complete(
                self._client.send_message(
                    {'type': 'ping'},
                    expect_response=True,
                    timeout=10
                )
            )
            
            response_time = time.time() - start_time
            
            if response.get('type') == 'pong':
                return {
                    'success': True,
                    'response_time_ms': round(response_time * 1000, 2),
                    'server_time': response.get('data', {}).get('timestamp'),
                    'connection_id': response.get('data', {}).get('connection_id')
                }
            else:
                return {
                    'success': False,
                    'error': 'Unexpected response',
                    'details': f"Expected 'pong', got '{response.get('type')}'"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'details': 'Connection test failed'
            }
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get RevitPy bridge server status.
        
        Returns:
            Server status information
        """
        try:
            if not self.is_connected():
                return {'error': 'Not connected to server'}
            
            loop = self._get_or_create_event_loop()
            response = loop.run_until_complete(
                self._client.send_message(
                    {'type': 'get_status'},
                    expect_response=True,
                    timeout=10
                )
            )
            
            if response.get('type') == 'status':
                return response.get('data', {})
            else:
                return {'error': f"Unexpected response: {response.get('type')}"}
                
        except Exception as e:
            return {'error': str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge usage statistics."""
        return {
            'bridge_stats': self.stats.copy(),
            'connection_info': {
                'host': self.websocket_host,
                'port': self.websocket_port,
                'path': self.websocket_path,
                'connected': self.is_connected()
            },
            'serializer_stats': self.serializer.get_statistics()
        }
    
    def _update_stats(self, element_count: int, execution_time: float, success: bool):
        """Update bridge statistics."""
        self.stats['requests_sent'] += 1
        self.stats['total_elements_processed'] += element_count
        
        if success:
            self.stats['requests_successful'] += 1
        else:
            self.stats['requests_failed'] += 1
        
        # Update average response time
        current_avg = self.stats['avg_response_time']
        total_requests = self.stats['requests_sent']
        
        if total_requests == 1:
            self.stats['avg_response_time'] = execution_time
        else:
            self.stats['avg_response_time'] = (
                (current_avg * (total_requests - 1) + execution_time) / total_requests
            )
    
    def _get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for async operations."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            return loop
        except RuntimeError:
            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Convenience functions for PyRevit scripts
def execute_analysis(elements: Union[List, Any], 
                    analysis_type: str,
                    parameters: Optional[Dict[str, Any]] = None,
                    **kwargs) -> Dict[str, Any]:
    """
    Convenience function to execute analysis with default bridge settings.
    
    Args:
        elements: List of Revit elements or single element
        analysis_type: Type of analysis to perform
        parameters: Additional parameters for analysis
        **kwargs: Additional arguments for bridge configuration
        
    Returns:
        Analysis results dictionary
    """
    with RevitPyBridge(**kwargs) as bridge:
        return bridge.execute_analysis(elements, analysis_type, parameters)


def test_revitpy_connection(**kwargs) -> Dict[str, Any]:
    """
    Convenience function to test RevitPy bridge connection.
    
    Args:
        **kwargs: Arguments for bridge configuration
        
    Returns:
        Connection test results
    """
    with RevitPyBridge(**kwargs) as bridge:
        return bridge.test_connection()


def get_revitpy_server_status(**kwargs) -> Dict[str, Any]:
    """
    Convenience function to get RevitPy server status.
    
    Args:
        **kwargs: Arguments for bridge configuration
        
    Returns:
        Server status information
    """
    with RevitPyBridge(**kwargs) as bridge:
        return bridge.get_server_status()


# Example analysis types for reference
ANALYSIS_TYPES = {
    'energy_performance': {
        'description': 'Analyze energy performance of building elements',
        'parameters': ['include_thermal', 'precision', 'weather_data'],
        'returns': ['efficiency_rating', 'energy_usage', 'recommendations']
    },
    'space_optimization': {
        'description': 'Optimize space layout using ML algorithms',
        'parameters': ['optimization_goal', 'constraints', 'algorithm'],
        'returns': ['optimized_layout', 'efficiency_gain', 'cost_impact']
    },
    'structural_analysis': {
        'description': 'Perform structural analysis on building elements',
        'parameters': ['load_cases', 'material_properties', 'safety_factor'],
        'returns': ['stress_analysis', 'deflection', 'safety_margin']
    },
    'clash_detection': {
        'description': 'Detect clashes between building elements',
        'parameters': ['tolerance', 'clash_types', 'ignore_rules'],
        'returns': ['clash_reports', 'severity_levels', 'resolution_suggestions']
    },
    'cost_analysis': {
        'description': 'Analyze costs of building elements',
        'parameters': ['cost_database', 'region', 'currency'],
        'returns': ['total_cost', 'cost_breakdown', 'cost_optimization']
    }
}