"""
Pythonic Element wrapper with modern Python conventions.
"""

from __future__ import annotations

import weakref
from typing import (
    Any, Dict, List, Optional, Type, TypeVar, Generic, Union, 
    Iterator, overload, cast, Protocol
)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator
from loguru import logger

from .exceptions import ValidationError, ElementNotFoundError, PermissionError


T = TypeVar('T', bound='Element')
P = TypeVar('P')


class IRevitElement(Protocol):
    """Protocol for Revit element interface."""
    
    @property
    def Id(self) -> Any: ...
    
    @property 
    def Name(self) -> str: ...
    
    def GetParameterValue(self, parameter_name: str) -> Any: ...
    
    def SetParameterValue(self, parameter_name: str, value: Any) -> None: ...


@dataclass(frozen=True)
class ElementId:
    """Immutable element ID wrapper."""
    
    value: int
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __int__(self) -> int:
        return self.value


class ParameterValue(BaseModel):
    """Type-safe parameter value container."""
    
    name: str
    value: Any
    type_name: str
    is_read_only: bool = False
    storage_type: str = "String"
    
    @validator('value')
    def validate_value(cls, v: Any, values: Dict[str, Any]) -> Any:
        """Validate parameter value based on storage type."""
        storage_type = values.get('storage_type', 'String')
        
        if storage_type == 'Double' and not isinstance(v, (int, float)):
            try:
                return float(v)
            except (ValueError, TypeError):
                raise ValidationError(f"Cannot convert {v} to double")
        
        if storage_type == 'Integer' and not isinstance(v, int):
            try:
                return int(v)
            except (ValueError, TypeError):
                raise ValidationError(f"Cannot convert {v} to integer")
        
        return v


class ElementMetaclass(type):
    """Metaclass for Element that handles property registration."""
    
    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> Type:
        # Register property accessors
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Add dynamic property access
        if hasattr(cls, '_property_mappings'):
            for prop_name, revit_param in cls._property_mappings.items():
                setattr(cls, prop_name, ElementProperty(revit_param))
        
        return cls


class ElementProperty:
    """Descriptor for element properties with automatic type conversion."""
    
    def __init__(self, parameter_name: str, read_only: bool = False) -> None:
        self.parameter_name = parameter_name
        self.read_only = read_only
    
    def __get__(self, obj: Optional['Element'], objtype: Optional[Type] = None) -> Any:
        if obj is None:
            return self
        
        try:
            return obj.get_parameter_value(self.parameter_name)
        except Exception as e:
            logger.warning(
                f"Failed to get parameter {self.parameter_name} from element {obj.id}: {e}"
            )
            return None
    
    def __set__(self, obj: 'Element', value: Any) -> None:
        if self.read_only:
            raise PermissionError(f"Parameter {self.parameter_name} is read-only")
        
        try:
            obj.set_parameter_value(self.parameter_name, value)
        except Exception as e:
            logger.error(
                f"Failed to set parameter {self.parameter_name} on element {obj.id}: {e}"
            )
            raise


class Element(metaclass=ElementMetaclass):
    """
    Pythonic wrapper for Revit elements with automatic type conversion,
    lazy loading, and change tracking.
    """
    
    # Property mappings for common parameters
    _property_mappings: Dict[str, str] = {
        'name': 'Name',
        'family_name': 'Family',
        'type_name': 'Type',
        'level': 'Level',
        'comments': 'Comments',
        'mark': 'Mark',
    }
    
    def __init__(self, revit_element: IRevitElement) -> None:
        self._revit_element = revit_element
        self._parameter_cache: Dict[str, ParameterValue] = {}
        self._change_tracker: Dict[str, Any] = {}
        self._is_dirty = False
        
        # Create weak reference to avoid circular references
        self._weak_ref = weakref.ref(self)
    
    @property
    def id(self) -> ElementId:
        """Get the element ID."""
        return ElementId(self._revit_element.Id.IntegerValue)
    
    @property
    def name(self) -> str:
        """Get the element name."""
        return self._revit_element.Name or ""
    
    @name.setter
    def name(self, value: str) -> None:
        """Set the element name."""
        self.set_parameter_value('Name', value)
    
    @property
    def is_dirty(self) -> bool:
        """Check if element has unsaved changes."""
        return self._is_dirty
    
    @property
    def changes(self) -> Dict[str, Any]:
        """Get tracked changes."""
        return self._change_tracker.copy()
    
    def get_parameter_value(
        self, 
        parameter_name: str, 
        use_cache: bool = True
    ) -> Any:
        """
        Get parameter value with caching and type conversion.
        
        Args:
            parameter_name: Name of the parameter
            use_cache: Whether to use cached values
            
        Returns:
            Parameter value with appropriate Python type
            
        Raises:
            ElementNotFoundError: If parameter doesn't exist
        """
        if use_cache and parameter_name in self._parameter_cache:
            return self._parameter_cache[parameter_name].value
        
        try:
            raw_value = self._revit_element.GetParameterValue(parameter_name)
            
            # Convert Revit value to Python type
            converted_value = self._convert_from_revit(raw_value)
            
            # Cache the result
            param_value = ParameterValue(
                name=parameter_name,
                value=converted_value,
                type_name=type(converted_value).__name__,
                storage_type=self._get_storage_type(raw_value)
            )
            
            if use_cache:
                self._parameter_cache[parameter_name] = param_value
            
            return converted_value
            
        except Exception as e:
            raise ElementNotFoundError(
                element_id=self.id,
                element_type=parameter_name,
                cause=e
            )
    
    def set_parameter_value(
        self, 
        parameter_name: str, 
        value: Any,
        track_changes: bool = True
    ) -> None:
        """
        Set parameter value with type conversion and change tracking.
        
        Args:
            parameter_name: Name of the parameter
            value: New value
            track_changes: Whether to track this change
            
        Raises:
            ValidationError: If value is invalid
            PermissionError: If parameter is read-only
        """
        try:
            # Convert Python value to Revit type
            revit_value = self._convert_to_revit(value)
            
            # Set the value
            self._revit_element.SetParameterValue(parameter_name, revit_value)
            
            # Track changes
            if track_changes:
                old_value = self._parameter_cache.get(parameter_name, {}).get('value')
                if old_value != value:
                    self._change_tracker[parameter_name] = {
                        'old': old_value,
                        'new': value
                    }
                    self._is_dirty = True
            
            # Update cache
            param_value = ParameterValue(
                name=parameter_name,
                value=value,
                type_name=type(value).__name__,
                storage_type=self._get_storage_type(revit_value)
            )
            self._parameter_cache[parameter_name] = param_value
            
            logger.debug(f"Set parameter {parameter_name} = {value} on element {self.id}")
            
        except Exception as e:
            logger.error(f"Failed to set parameter {parameter_name} on element {self.id}: {e}")
            raise ValidationError(
                f"Failed to set parameter {parameter_name}",
                field=parameter_name,
                value=value,
                cause=e
            )
    
    def get_all_parameters(self, refresh_cache: bool = False) -> Dict[str, ParameterValue]:
        """
        Get all parameters for this element.
        
        Args:
            refresh_cache: Whether to refresh the parameter cache
            
        Returns:
            Dictionary of parameter names to values
        """
        if refresh_cache:
            self._parameter_cache.clear()
        
        # Implementation would iterate through all Revit parameters
        # This is a simplified version
        parameters = {}
        
        for param_name in self._get_all_parameter_names():
            try:
                value = self.get_parameter_value(param_name, use_cache=not refresh_cache)
                parameters[param_name] = self._parameter_cache[param_name]
            except ElementNotFoundError:
                continue
        
        return parameters
    
    def save_changes(self) -> None:
        """Save all tracked changes to Revit."""
        if not self._is_dirty:
            return
        
        # In a real implementation, this would batch the changes
        # and apply them in a transaction
        logger.info(f"Saving {len(self._change_tracker)} changes to element {self.id}")
        
        # Clear change tracking
        self._change_tracker.clear()
        self._is_dirty = False
    
    def discard_changes(self) -> None:
        """Discard all tracked changes."""
        if not self._is_dirty:
            return
        
        # Revert changes by reloading from Revit
        for param_name in self._change_tracker:
            if param_name in self._parameter_cache:
                del self._parameter_cache[param_name]
        
        self._change_tracker.clear()
        self._is_dirty = False
        
        logger.info(f"Discarded changes for element {self.id}")
    
    def refresh(self) -> None:
        """Refresh element data from Revit."""
        self._parameter_cache.clear()
        self._change_tracker.clear()
        self._is_dirty = False
        
        logger.debug(f"Refreshed element {self.id}")
    
    def _convert_from_revit(self, value: Any) -> Any:
        """Convert Revit value to appropriate Python type."""
        if value is None:
            return None
        
        # Handle common Revit types
        if hasattr(value, 'AsString'):
            return value.AsString()
        elif hasattr(value, 'AsDouble'):
            return value.AsDouble()
        elif hasattr(value, 'AsInteger'):
            return value.AsInteger()
        elif hasattr(value, 'AsValueString'):
            return value.AsValueString()
        
        return str(value)
    
    def _convert_to_revit(self, value: Any) -> Any:
        """Convert Python value to Revit type."""
        # This would contain logic to convert Python types
        # to appropriate Revit parameter values
        return value
    
    def _get_storage_type(self, value: Any) -> str:
        """Determine storage type from Revit value."""
        if hasattr(value, 'StorageType'):
            return str(value.StorageType)
        return 'String'
    
    def _get_all_parameter_names(self) -> List[str]:
        """Get all parameter names for this element."""
        # This would query the actual Revit element for its parameters
        return list(self._property_mappings.values())
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.id}): {self.name}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} name='{self.name}'>"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Element):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id.value)


class ElementSet(Generic[T]):
    """
    Collection of elements with LINQ-style operations and lazy evaluation.
    """
    
    def __init__(self, elements: Optional[List[T]] = None) -> None:
        self._elements: List[T] = elements or []
        self._is_evaluated = bool(elements)
        self._query_operations: List[Any] = []
    
    @property
    def count(self) -> int:
        """Get the count of elements."""
        self._ensure_evaluated()
        return len(self._elements)
    
    def where(self, predicate: callable) -> 'ElementSet[T]':
        """Filter elements using a predicate."""
        new_set = ElementSet[T]()
        new_set._query_operations = self._query_operations + [('where', predicate)]
        new_set._is_evaluated = False
        return new_set
    
    def select(self, selector: callable) -> 'ElementSet':
        """Transform elements using a selector."""
        new_set = ElementSet()
        new_set._query_operations = self._query_operations + [('select', selector)]
        new_set._is_evaluated = False
        return new_set
    
    def first(self, predicate: Optional[callable] = None) -> T:
        """Get the first element matching the predicate."""
        if predicate:
            filtered = self.where(predicate)
            return filtered.first()
        
        self._ensure_evaluated()
        if not self._elements:
            raise ElementNotFoundError("No elements in set")
        
        return self._elements[0]
    
    def first_or_default(self, predicate: Optional[callable] = None, default: Optional[T] = None) -> Optional[T]:
        """Get the first element matching the predicate or default."""
        try:
            return self.first(predicate)
        except ElementNotFoundError:
            return default
    
    def single(self, predicate: Optional[callable] = None) -> T:
        """Get the single element matching the predicate."""
        if predicate:
            filtered = self.where(predicate)
            return filtered.single()
        
        self._ensure_evaluated()
        if len(self._elements) == 0:
            raise ElementNotFoundError("No elements in set")
        elif len(self._elements) > 1:
            raise ValidationError("More than one element in set")
        
        return self._elements[0]
    
    def to_list(self) -> List[T]:
        """Convert to list."""
        self._ensure_evaluated()
        return self._elements.copy()
    
    def any(self, predicate: Optional[callable] = None) -> bool:
        """Check if any elements match the predicate."""
        if predicate:
            return self.where(predicate).any()
        
        self._ensure_evaluated()
        return len(self._elements) > 0
    
    def all(self, predicate: callable) -> bool:
        """Check if all elements match the predicate."""
        self._ensure_evaluated()
        return all(predicate(element) for element in self._elements)
    
    def order_by(self, key_selector: callable) -> 'ElementSet[T]':
        """Order elements by key selector."""
        new_set = ElementSet[T]()
        new_set._query_operations = self._query_operations + [('order_by', key_selector)]
        new_set._is_evaluated = False
        return new_set
    
    def group_by(self, key_selector: callable) -> Dict[Any, List[T]]:
        """Group elements by key selector."""
        self._ensure_evaluated()
        groups = {}
        
        for element in self._elements:
            key = key_selector(element)
            if key not in groups:
                groups[key] = []
            groups[key].append(element)
        
        return groups
    
    def _ensure_evaluated(self) -> None:
        """Ensure the query is evaluated."""
        if self._is_evaluated:
            return
        
        # Apply query operations
        result = self._elements
        
        for operation, func in self._query_operations:
            if operation == 'where':
                result = [x for x in result if func(x)]
            elif operation == 'select':
                result = [func(x) for x in result]
            elif operation == 'order_by':
                result = sorted(result, key=func)
        
        self._elements = result
        self._is_evaluated = True
    
    def __iter__(self) -> Iterator[T]:
        self._ensure_evaluated()
        return iter(self._elements)
    
    def __len__(self) -> int:
        return self.count
    
    def __getitem__(self, index: int) -> T:
        self._ensure_evaluated()
        return self._elements[index]
    
    def __contains__(self, item: T) -> bool:
        self._ensure_evaluated()
        return item in self._elements