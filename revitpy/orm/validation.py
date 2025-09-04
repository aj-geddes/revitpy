"""
Type safety and validation system for RevitPy ORM using Pydantic.

This module provides comprehensive validation for Revit elements using Pydantic models,
ensuring type safety, data integrity, and constraint validation throughout the ORM layer.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Generic, Union, 
    Callable, get_type_hints, get_origin, get_args
)
from datetime import datetime
from enum import Enum
from pydantic import (
    BaseModel, Field, validator, root_validator, ValidationError,
    ConfigDict, field_validator, model_validator
)
from pydantic.fields import FieldInfo
from loguru import logger

from .types import ElementState, PropertyValue, ElementId
from .exceptions import ValidationError as ORMValidationError


T = TypeVar('T', bound=BaseModel)
E = TypeVar('E', bound='BaseElement')


class ValidationLevel(Enum):
    """Levels of validation strictness."""
    
    NONE = "none"           # No validation
    BASIC = "basic"         # Basic type checking only
    STANDARD = "standard"   # Standard validation rules
    STRICT = "strict"       # Strict validation with all constraints
    CUSTOM = "custom"       # Custom validation rules


class ConstraintType(Enum):
    """Types of validation constraints."""
    
    REQUIRED = "required"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    PATTERN = "pattern"
    CUSTOM = "custom"


class BaseElement(BaseModel):
    """
    Base Pydantic model for all Revit elements with comprehensive validation.
    
    Provides common properties and validation logic for all Revit element types.
    """
    
    model_config = ConfigDict(
        # Allow extra attributes for dynamic properties
        extra='allow',
        # Validate default values
        validate_default=True,
        # Use enum values instead of names
        use_enum_values=True,
        # Validate assignments after model creation
        validate_assignment=True,
        # Allow population by field name and alias
        populate_by_name=True,
        # Strict type validation
        strict=False,
        # Arbitrary types allowed (for Revit-specific types)
        arbitrary_types_allowed=True
    )
    
    # Common Revit element properties
    id: ElementId = Field(..., description="Unique element identifier")
    name: Optional[str] = Field(None, description="Element name", max_length=1000)
    category: Optional[str] = Field(None, description="Element category", max_length=255)
    level_id: Optional[ElementId] = Field(None, description="Level ID reference")
    family_name: Optional[str] = Field(None, description="Family name", max_length=255)
    type_name: Optional[str] = Field(None, description="Type name", max_length=255)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=datetime.utcnow, description="Last modification timestamp")
    version: int = Field(default=1, ge=1, description="Version number")
    is_valid: bool = Field(default=True, description="Validity flag")
    
    # ORM-specific properties
    state: ElementState = Field(default=ElementState.UNCHANGED, description="Entity state")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate element name."""
        if v is not None and v.strip() == "":
            return None
        return v.strip() if v else None
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Validate category name."""
        if v is not None and v.strip() == "":
            return None
        return v.strip() if v else None
    
    @model_validator(mode='after')
    def validate_element(self) -> 'BaseElement':
        """Root validator for element-wide validation."""
        # Update modification timestamp when model changes
        if hasattr(self, '__dict__'):
            object.__setattr__(self, 'modified_at', datetime.utcnow())
        
        return self
    
    def is_dirty(self) -> bool:
        """Check if element has unsaved changes."""
        return self.state in (ElementState.ADDED, ElementState.MODIFIED)
    
    def mark_dirty(self) -> None:
        """Mark element as modified."""
        if self.state == ElementState.UNCHANGED:
            self.state = ElementState.MODIFIED
        self.modified_at = datetime.utcnow()
        self.version += 1
    
    def mark_clean(self) -> None:
        """Mark element as clean (saved)."""
        self.state = ElementState.UNCHANGED


class WallElement(BaseElement):
    """Pydantic model for Revit Wall elements with specific validation."""
    
    height: float = Field(..., gt=0, description="Wall height in feet")
    length: float = Field(..., gt=0, description="Wall length in feet")
    width: float = Field(..., gt=0, description="Wall width/thickness in feet")
    area: Optional[float] = Field(None, ge=0, description="Wall area in square feet")
    volume: Optional[float] = Field(None, ge=0, description="Wall volume in cubic feet")
    
    # Wall-specific properties
    base_constraint: Optional[str] = Field(None, description="Base constraint level")
    top_constraint: Optional[str] = Field(None, description="Top constraint level") 
    base_offset: float = Field(default=0.0, description="Base offset from level")
    top_offset: float = Field(default=0.0, description="Top offset from level")
    
    # Material and finish
    structural_material: Optional[str] = Field(None, description="Structural material")
    finish_material_interior: Optional[str] = Field(None, description="Interior finish material")
    finish_material_exterior: Optional[str] = Field(None, description="Exterior finish material")
    
    # Analytical properties
    structural: bool = Field(default=False, description="Is structural element")
    fire_rating: Optional[int] = Field(None, ge=0, le=4, description="Fire rating (0-4 hours)")
    
    @field_validator('height')
    @classmethod
    def validate_height(cls, v: float) -> float:
        """Validate wall height."""
        if v <= 0:
            raise ValueError("Wall height must be positive")
        if v > 100:  # Reasonable upper limit in feet
            logger.warning(f"Wall height {v} ft seems unusually large")
        return v
    
    @field_validator('width')
    @classmethod
    def validate_width(cls, v: float) -> float:
        """Validate wall thickness."""
        if v <= 0:
            raise ValueError("Wall width must be positive")
        if v > 5:  # Reasonable upper limit for wall thickness
            logger.warning(f"Wall thickness {v} ft seems unusually large")
        return v
    
    @model_validator(mode='after')
    def calculate_derived_properties(self) -> 'WallElement':
        """Calculate area and volume if not provided."""
        # Calculate area if not provided
        if self.area is None:
            self.area = self.height * self.length
        
        # Calculate volume if not provided
        if self.volume is None:
            self.volume = self.height * self.length * self.width
        
        return self


class RoomElement(BaseElement):
    """Pydantic model for Revit Room elements with space validation."""
    
    number: str = Field(..., min_length=1, max_length=50, description="Room number")
    area: float = Field(..., ge=0, description="Room area in square feet")
    perimeter: float = Field(..., ge=0, description="Room perimeter in feet")
    volume: float = Field(..., ge=0, description="Room volume in cubic feet")
    
    # Room-specific properties
    department: Optional[str] = Field(None, max_length=255, description="Department")
    occupancy: Optional[int] = Field(None, ge=0, description="Occupancy count")
    ceiling_height: Optional[float] = Field(None, gt=0, description="Ceiling height")
    
    # Environmental properties
    temperature: Optional[float] = Field(None, ge=-50, le=150, description="Temperature in Fahrenheit")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Humidity percentage")
    air_flow_required: Optional[float] = Field(None, ge=0, description="Required air flow in CFM")
    
    @field_validator('number')
    @classmethod
    def validate_room_number(cls, v: str) -> str:
        """Validate room number format."""
        v = v.strip()
        if not v:
            raise ValueError("Room number cannot be empty")
        # Allow alphanumeric and basic punctuation
        if not all(c.isalnum() or c in '.-_' for c in v):
            raise ValueError("Room number contains invalid characters")
        return v
    
    @field_validator('area')
    @classmethod
    def validate_area(cls, v: float) -> float:
        """Validate room area."""
        if v < 0:
            raise ValueError("Room area cannot be negative")
        if v > 10000:  # Reasonable upper limit in square feet
            logger.warning(f"Room area {v} sq ft seems unusually large")
        return v


class DoorElement(BaseElement):
    """Pydantic model for Revit Door elements."""
    
    width: float = Field(..., gt=0, description="Door width in feet")
    height: float = Field(..., gt=0, description="Door height in feet")
    
    # Door-specific properties
    material: Optional[str] = Field(None, description="Door material")
    fire_rating: Optional[float] = Field(None, ge=0, le=4, description="Fire rating in hours")
    hardware_set: Optional[str] = Field(None, description="Hardware set specification")
    
    # Operational properties
    hand: Optional[str] = Field(None, regex=r'^(Left|Right)$', description="Door hand (Left/Right)")
    operation_type: Optional[str] = Field(None, description="Operation type (Swing, Sliding, etc.)")
    
    @field_validator('width', 'height')
    @classmethod
    def validate_dimensions(cls, v: float) -> float:
        """Validate door dimensions."""
        if v <= 0:
            raise ValueError("Door dimensions must be positive")
        if v > 20:  # Reasonable upper limit
            logger.warning(f"Door dimension {v} ft seems unusually large")
        return v


class WindowElement(BaseElement):
    """Pydantic model for Revit Window elements."""
    
    width: float = Field(..., gt=0, description="Window width in feet")
    height: float = Field(..., gt=0, description="Window height in feet")
    
    # Window-specific properties
    glass_type: Optional[str] = Field(None, description="Glass type specification")
    frame_material: Optional[str] = Field(None, description="Frame material")
    u_factor: Optional[float] = Field(None, gt=0, description="U-Factor for energy analysis")
    solar_heat_gain: Optional[float] = Field(None, ge=0, le=1, description="Solar Heat Gain Coefficient")
    
    # Performance properties
    sound_transmission_class: Optional[int] = Field(None, ge=0, le=100, description="STC rating")
    energy_star_rated: bool = Field(default=False, description="Energy Star certification")


class ValidationRule(BaseModel):
    """Represents a validation rule for element properties."""
    
    property_name: str = Field(..., description="Property name to validate")
    constraint_type: ConstraintType = Field(..., description="Type of constraint")
    constraint_value: Any = Field(..., description="Constraint value")
    error_message: str = Field(..., description="Error message for validation failure")
    is_active: bool = Field(default=True, description="Whether rule is active")
    
    def validate_value(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a value against this rule.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.is_active:
            return True, None
        
        try:
            if self.constraint_type == ConstraintType.REQUIRED:
                if value is None or (isinstance(value, str) and not value.strip()):
                    return False, self.error_message
                    
            elif self.constraint_type == ConstraintType.MIN_VALUE:
                if value is not None and value < self.constraint_value:
                    return False, self.error_message
                    
            elif self.constraint_type == ConstraintType.MAX_VALUE:
                if value is not None and value > self.constraint_value:
                    return False, self.error_message
                    
            elif self.constraint_type == ConstraintType.MIN_LENGTH:
                if value is not None and len(str(value)) < self.constraint_value:
                    return False, self.error_message
                    
            elif self.constraint_type == ConstraintType.MAX_LENGTH:
                if value is not None and len(str(value)) > self.constraint_value:
                    return False, self.error_message
                    
            elif self.constraint_type == ConstraintType.PATTERN:
                import re
                if value is not None and not re.match(self.constraint_value, str(value)):
                    return False, self.error_message
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {e}"


class ElementValidator:
    """
    Comprehensive validator for Revit elements with support for
    custom rules, async validation, and performance optimization.
    """
    
    def __init__(
        self, 
        validation_level: ValidationLevel = ValidationLevel.STANDARD,
        custom_rules: Optional[List[ValidationRule]] = None
    ) -> None:
        self.validation_level = validation_level
        self.custom_rules = custom_rules or []
        self.element_types: Dict[str, Type[BaseElement]] = {
            'Wall': WallElement,
            'Room': RoomElement,
            'Door': DoorElement,
            'Window': WindowElement,
            'BaseElement': BaseElement
        }
        self._validation_cache: Dict[str, Any] = {}
    
    def register_element_type(self, name: str, element_type: Type[BaseElement]) -> None:
        """Register a custom element type."""
        self.element_types[name] = element_type
        logger.debug(f"Registered element type: {name}")
    
    def validate_element(self, element: BaseElement, strict: bool = None) -> Dict[str, List[str]]:
        """
        Validate an element instance.
        
        Args:
            element: Element to validate
            strict: Override validation level for this validation
            
        Returns:
            Dictionary of validation errors (empty if valid)
        """
        if self.validation_level == ValidationLevel.NONE:
            return {}
        
        errors = {}
        
        try:
            # Pydantic model validation
            if strict or self.validation_level == ValidationLevel.STRICT:
                element.model_validate(element.model_dump(), strict=True)
            else:
                element.model_validate(element.model_dump())
                
        except ValidationError as e:
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                if field not in errors:
                    errors[field] = []
                errors[field].append(error['msg'])
        
        # Apply custom validation rules
        for rule in self.custom_rules:
            if hasattr(element, rule.property_name):
                value = getattr(element, rule.property_name)
                is_valid, error_msg = rule.validate_value(value)
                if not is_valid:
                    if rule.property_name not in errors:
                        errors[rule.property_name] = []
                    errors[rule.property_name].append(error_msg)
        
        # Element-specific validation
        element_errors = self._validate_element_specific(element)
        for field, field_errors in element_errors.items():
            if field not in errors:
                errors[field] = []
            errors[field].extend(field_errors)
        
        return errors
    
    def validate_element_dict(self, element_data: Dict[str, Any], element_type: str) -> Dict[str, List[str]]:
        """
        Validate element data as dictionary.
        
        Args:
            element_data: Element data dictionary
            element_type: Type of element to validate as
            
        Returns:
            Dictionary of validation errors
        """
        if self.validation_level == ValidationLevel.NONE:
            return {}
        
        if element_type not in self.element_types:
            return {'element_type': [f'Unknown element type: {element_type}']}
        
        try:
            element_class = self.element_types[element_type]
            element = element_class.model_validate(element_data)
            return self.validate_element(element)
            
        except ValidationError as e:
            errors = {}
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                if field not in errors:
                    errors[field] = []
                errors[field].append(error['msg'])
            return errors
    
    async def validate_element_async(self, element: BaseElement) -> Dict[str, List[str]]:
        """Validate element asynchronously."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.validate_element, element
        )
    
    def validate_batch(self, elements: List[BaseElement]) -> List[Dict[str, List[str]]]:
        """
        Validate multiple elements.
        
        Args:
            elements: List of elements to validate
            
        Returns:
            List of validation error dictionaries
        """
        return [self.validate_element(element) for element in elements]
    
    async def validate_batch_async(self, elements: List[BaseElement]) -> List[Dict[str, List[str]]]:
        """Validate multiple elements asynchronously."""
        tasks = [self.validate_element_async(element) for element in elements]
        return await asyncio.gather(*tasks)
    
    def is_valid(self, element: BaseElement) -> bool:
        """Check if element is valid without returning detailed errors."""
        errors = self.validate_element(element)
        return len(errors) == 0
    
    def assert_valid(self, element: BaseElement) -> None:
        """Assert that element is valid, raise exception if not."""
        errors = self.validate_element(element)
        if errors:
            raise ORMValidationError(
                "Element validation failed",
                validation_errors=errors,
                entity=element
            )
    
    def get_element_schema(self, element_type: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for element type."""
        if element_type in self.element_types:
            return self.element_types[element_type].model_json_schema()
        return None
    
    def _validate_element_specific(self, element: BaseElement) -> Dict[str, List[str]]:
        """Perform element-specific validation."""
        errors = {}
        
        # Cross-property validation for walls
        if isinstance(element, WallElement):
            # Check area consistency
            if element.area and element.height and element.length:
                calculated_area = element.height * element.length
                if abs(element.area - calculated_area) > 0.1:
                    errors['area'] = [f'Area {element.area} does not match calculated area {calculated_area:.2f}']
            
            # Check volume consistency
            if element.volume and element.height and element.length and element.width:
                calculated_volume = element.height * element.length * element.width
                if abs(element.volume - calculated_volume) > 0.1:
                    errors['volume'] = [f'Volume {element.volume} does not match calculated volume {calculated_volume:.2f}']
        
        # Room validation
        elif isinstance(element, RoomElement):
            # Check occupancy vs area
            if element.occupancy and element.area:
                area_per_person = element.area / element.occupancy
                if area_per_person < 50:  # Minimum area per person
                    errors['occupancy'] = ['Occupancy too high for room area (min 50 sq ft per person)']
        
        return errors
    
    def add_custom_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self.custom_rules.append(rule)
        logger.debug(f"Added custom validation rule for {rule.property_name}")
    
    def remove_custom_rule(self, property_name: str, constraint_type: ConstraintType) -> bool:
        """Remove a custom validation rule."""
        initial_count = len(self.custom_rules)
        self.custom_rules = [
            rule for rule in self.custom_rules
            if not (rule.property_name == property_name and rule.constraint_type == constraint_type)
        ]
        removed = len(self.custom_rules) < initial_count
        if removed:
            logger.debug(f"Removed custom validation rule for {property_name}")
        return removed


class TypeSafetyMixin:
    """
    Mixin class that adds type safety checking to ORM operations.
    
    Automatically validates types during ORM operations and provides
    compile-time type checking hints.
    """
    
    def __init__(self, validator: ElementValidator):
        self._validator = validator
        self._type_cache: Dict[Type, bool] = {}
    
    def ensure_type_safety(self, obj: Any, expected_type: Type[T]) -> T:
        """
        Ensure object matches expected type with validation.
        
        Args:
            obj: Object to validate
            expected_type: Expected type
            
        Returns:
            Typed object
            
        Raises:
            ORMValidationError: If validation fails
        """
        if not isinstance(obj, expected_type):
            # Try to convert if it's a dictionary
            if isinstance(obj, dict) and issubclass(expected_type, BaseElement):
                try:
                    obj = expected_type.model_validate(obj)
                except ValidationError as e:
                    raise ORMValidationError(
                        f"Cannot convert dict to {expected_type.__name__}",
                        validation_errors={'conversion': [str(e)]},
                        entity=obj
                    )
            else:
                raise ORMValidationError(
                    f"Expected {expected_type.__name__}, got {type(obj).__name__}",
                    entity=obj
                )
        
        # Validate the object
        if isinstance(obj, BaseElement):
            self._validator.assert_valid(obj)
        
        return obj
    
    def validate_collection(self, objects: List[Any], expected_type: Type[T]) -> List[T]:
        """Validate and ensure type safety for collections."""
        return [self.ensure_type_safety(obj, expected_type) for obj in objects]


# Factory functions for creating type-safe elements

def create_wall(
    id: ElementId,
    height: float,
    length: float,
    width: float,
    **kwargs
) -> WallElement:
    """Create a validated Wall element."""
    data = {
        'id': id,
        'height': height,
        'length': length,
        'width': width,
        **kwargs
    }
    return WallElement.model_validate(data)


def create_room(
    id: ElementId,
    number: str,
    area: float,
    **kwargs
) -> RoomElement:
    """Create a validated Room element."""
    data = {
        'id': id,
        'number': number,
        'area': area,
        'perimeter': kwargs.get('perimeter', 0.0),
        'volume': kwargs.get('volume', 0.0),
        **kwargs
    }
    return RoomElement.model_validate(data)


def create_door(
    id: ElementId,
    width: float,
    height: float,
    **kwargs
) -> DoorElement:
    """Create a validated Door element."""
    data = {
        'id': id,
        'width': width,
        'height': height,
        **kwargs
    }
    return DoorElement.model_validate(data)


def create_window(
    id: ElementId,
    width: float,
    height: float,
    **kwargs
) -> WindowElement:
    """Create a validated Window element."""
    data = {
        'id': id,
        'width': width,
        'height': height,
        **kwargs
    }
    return WindowElement.model_validate(data)


# Global validator instance
_default_validator = ElementValidator(ValidationLevel.STANDARD)

def get_validator() -> ElementValidator:
    """Get the default validator instance."""
    return _default_validator

def set_validation_level(level: ValidationLevel) -> None:
    """Set global validation level."""
    global _default_validator
    _default_validator.validation_level = level
    logger.info(f"Set validation level to {level.value}")