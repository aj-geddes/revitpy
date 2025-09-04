"""
Mock RevitPy API for demonstration purposes.
Provides realistic data structures and behaviors for POC development.
"""

import uuid
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from enum import Enum


class ElementCategory(Enum):
    SPACES = "Spaces"
    WALLS = "Walls" 
    STRUCTURAL_FRAMING = "StructuralFraming"
    MECHANICAL_EQUIPMENT = "MechanicalEquipment"
    DOORS = "Doors"
    WINDOWS = "Windows"
    COLUMNS = "StructuralColumns"
    BEAMS = "StructuralFraming"


@dataclass
class Point3D:
    x: float
    y: float
    z: float
    
    def distance_to(self, other: 'Point3D') -> float:
        return math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2 + 
            (self.z - other.z)**2
        )


@dataclass
class BoundingBox:
    min_point: Point3D
    max_point: Point3D
    
    @property
    def width(self) -> float:
        return self.max_point.x - self.min_point.x
    
    @property
    def height(self) -> float:
        return self.max_point.z - self.min_point.z
    
    @property
    def depth(self) -> float:
        return self.max_point.y - self.min_point.y
    
    @property
    def volume(self) -> float:
        return self.width * self.height * self.depth


@dataclass
class Parameter:
    name: str
    value: Any
    data_type: str
    is_read_only: bool = False
    
    def __str__(self) -> str:
        return f"{self.name}: {self.value} ({self.data_type})"


@dataclass
class RevitElement:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: ElementCategory = ElementCategory.SPACES
    name: str = ""
    parameters: Dict[str, Parameter] = field(default_factory=dict)
    geometry: Optional[BoundingBox] = None
    location: Optional[Point3D] = None
    
    def get_parameter(self, name: str) -> Any:
        """Get parameter value by name."""
        if name in self.parameters:
            return self.parameters[name].value
        return None
    
    def set_parameter(self, name: str, value: Any, data_type: str = "String"):
        """Set parameter value."""
        self.parameters[name] = Parameter(name, value, data_type)
    
    @property
    def area(self) -> float:
        """Calculate area based on geometry."""
        if self.geometry:
            return self.geometry.width * self.geometry.depth
        return 0.0
    
    @property 
    def volume(self) -> float:
        """Calculate volume based on geometry."""
        if self.geometry:
            return self.geometry.volume
        return 0.0


class MockRevitAPI:
    """Mock RevitPy API for demonstration purposes."""
    
    def __init__(self):
        self.elements = self._generate_mock_elements()
        self.project_info = {
            'name': 'Sample Office Building',
            'number': 'PRJ-2024-001',
            'location': 'San Francisco, CA',
            'building_type': 'Office',
            'gross_area': 150000,  # sq ft
            'floors': 12,
            'year_built': 2020
        }
    
    def _generate_mock_elements(self) -> List[RevitElement]:
        """Generate realistic mock building elements."""
        elements = []
        
        # Generate spaces (offices, meeting rooms, etc.)
        space_types = [
            'Private Office', 'Open Office', 'Meeting Room', 'Conference Room',
            'Break Room', 'Restroom', 'Storage', 'Corridor', 'Lobby', 'Server Room'
        ]
        
        for floor in range(1, 13):  # 12 floors
            for i in range(random.randint(15, 25)):  # 15-25 spaces per floor
                space_type = random.choice(space_types)
                
                # Generate realistic dimensions based on space type
                if space_type == 'Private Office':
                    width, depth = random.uniform(10, 15), random.uniform(12, 18)
                elif space_type == 'Open Office':
                    width, depth = random.uniform(30, 80), random.uniform(40, 100)
                elif space_type == 'Meeting Room':
                    width, depth = random.uniform(12, 20), random.uniform(15, 25)
                else:
                    width, depth = random.uniform(8, 25), random.uniform(10, 30)
                
                height = 9.0  # Standard ceiling height
                
                element = RevitElement(
                    category=ElementCategory.SPACES,
                    name=f"{space_type} {floor}-{i+1:02d}",
                    geometry=BoundingBox(
                        Point3D(i*20, 0, (floor-1)*12),
                        Point3D(i*20 + width, depth, floor*12)
                    ),
                    location=Point3D(i*20 + width/2, depth/2, (floor-1)*12 + height/2)
                )
                
                # Add realistic parameters
                element.set_parameter('Occupancy', random.randint(1, 8), 'Integer')
                element.set_parameter('LightingLoad', round(random.uniform(0.8, 2.5), 2), 'Double')
                element.set_parameter('EquipmentLoad', round(random.uniform(0.5, 3.0), 2), 'Double')
                element.set_parameter('Zone', f'HVAC-Zone-{floor}-{(i//5)+1}', 'String')
                element.set_parameter('SpaceType', space_type, 'String')
                element.set_parameter('Floor', floor, 'Integer')
                element.set_parameter('Department', random.choice(['Engineering', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations']), 'String')
                
                # Energy-related parameters
                element.set_parameter('AnnualEnergyUse', round(random.uniform(2000, 8000), 2), 'Double')  # kWh
                element.set_parameter('CoolingLoad', round(random.uniform(5, 25), 2), 'Double')  # BTU/hr/sf
                element.set_parameter('HeatingLoad', round(random.uniform(15, 35), 2), 'Double')  # BTU/hr/sf
                
                elements.append(element)
        
        # Generate walls
        for i in range(500):  # 500 walls
            wall_type = random.choice(['Exterior', 'Interior', 'Partition', 'Curtain Wall'])
            element = RevitElement(
                category=ElementCategory.WALLS,
                name=f"{wall_type} Wall {i+1:03d}",
                geometry=BoundingBox(
                    Point3D(random.uniform(0, 200), random.uniform(0, 100), 0),
                    Point3D(random.uniform(200, 400), random.uniform(100, 200), 12)
                )
            )
            
            element.set_parameter('WallType', wall_type, 'String')
            element.set_parameter('Thickness', random.uniform(4, 12), 'Double')  # inches
            element.set_parameter('U-Value', round(random.uniform(0.05, 0.35), 3), 'Double')  # BTU/(hr·ft²·°F)
            element.set_parameter('R-Value', round(1/element.get_parameter('U-Value'), 2), 'Double')
            
            elements.append(element)
        
        # Generate mechanical equipment
        equipment_types = ['Air Handler', 'Chiller', 'Boiler', 'Heat Pump', 'VAV Box', 'Fan Coil Unit']
        for i in range(50):
            equipment_type = random.choice(equipment_types)
            element = RevitElement(
                category=ElementCategory.MECHANICAL_EQUIPMENT,
                name=f"{equipment_type} {i+1:02d}",
                location=Point3D(
                    random.uniform(0, 400),
                    random.uniform(0, 200), 
                    random.uniform(0, 144)
                )
            )
            
            element.set_parameter('EquipmentType', equipment_type, 'String')
            element.set_parameter('Capacity', random.uniform(50000, 500000), 'Double')  # BTU/hr
            element.set_parameter('Efficiency', round(random.uniform(0.75, 0.95), 3), 'Double')
            element.set_parameter('PowerConsumption', round(random.uniform(5, 150), 2), 'Double')  # kW
            element.set_parameter('MaintenanceDate', 
                                datetime.now() - timedelta(days=random.randint(0, 365)), 
                                'DateTime')
            element.set_parameter('ServiceLife', random.randint(15, 25), 'Integer')  # years
            
            elements.append(element)
        
        # Generate structural elements
        for i in range(200):  # 200 structural elements
            element_type = random.choice(['Beam', 'Column'])
            element = RevitElement(
                category=ElementCategory.STRUCTURAL_FRAMING,
                name=f"W{random.choice(['12x26', '14x30', '16x36', '18x40', '21x44'])} {element_type} {i+1:03d}"
            )
            
            element.set_parameter('StructuralType', element_type, 'String')
            element.set_parameter('Material', random.choice(['Steel', 'Concrete', 'Wood']), 'String')
            element.set_parameter('LoadCapacity', random.uniform(50000, 200000), 'Double')  # lbs
            element.set_parameter('DeadLoad', random.uniform(1000, 5000), 'Double')  # lbs
            element.set_parameter('LiveLoad', random.uniform(2000, 8000), 'Double')  # lbs
            
            elements.append(element)
        
        return elements
    
    def get_elements(self, category: Union[str, ElementCategory] = None, element_type: str = None) -> List[RevitElement]:
        """Get elements by category and/or type."""
        if isinstance(category, str):
            category = ElementCategory(category)
        
        filtered = self.elements
        
        if category:
            filtered = [e for e in filtered if e.category == category]
        
        if element_type:
            filtered = [e for e in filtered if element_type.lower() in e.name.lower()]
        
        return filtered
    
    def get_elements_in_view(self, view_direction: str = None, location: Point3D = None) -> List[RevitElement]:
        """Get elements visible in a view (for computer vision POC)."""
        # Simplified implementation for demo
        return self.elements[:50]  # Return subset for visualization
    
    async def batch_update_parameters_async(self, updates: Dict[str, Any]):
        """Async parameter updates (for IoT POC)."""
        # Simulate async operation
        import asyncio
        await asyncio.sleep(0.1)
        
        # Update elements with new parameter values
        for element in self.elements[:10]:  # Update first 10 elements as example
            for param_name, value in updates.items():
                element.set_parameter(param_name, value, 'Double')


# Global mock API instance
revitpy = MockRevitAPI()


# Convenience functions that mimic RevitPy API
def get_elements(category: str = None, element_type: str = None) -> List[RevitElement]:
    """Get elements from the active Revit model."""
    return revitpy.get_elements(category, element_type)


def get_project_info() -> Dict[str, Any]:
    """Get project information."""
    return revitpy.project_info


def get_elements_in_view(view_direction: str = None, location: Point3D = None) -> List[RevitElement]:
    """Get elements visible in current view."""
    return revitpy.get_elements_in_view(view_direction, location)


async def batch_update_parameters_async(updates: Dict[str, Any]):
    """Batch update element parameters asynchronously."""
    await revitpy.batch_update_parameters_async(updates)