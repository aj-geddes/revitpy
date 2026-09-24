"""
Pythonic Element wrapper with modern Python conventions.
"""

from __future__ import annotations

import weakref
from collections.abc import Iterator
from dataclasses import dataclass
from typing import (
    Any,
    ClassVar,
    Generic,
    Protocol,
    TypeVar,
)

from loguru import logger
from pydantic import BaseModel, model_validator

from .exceptions import (
    ElementNotFoundError,
    PermissionError,
    RevitAPIError,
    ValidationError,
)

T = TypeVar("T", bound="Element")
P = TypeVar("P")


class IRevitElement(Protocol):
    """Protocol for Revit element interface."""

    @property
    def Id(self) -> Any: ...

    @property
    def Name(self) -> str: ...

    def GetParameterValue(self, parameter_name: str) -> Any: ...

    def SetParameterValue(self, parameter_name: str, value: Any) -> None: ...


def element_id_value(revit_id: Any) -> int:
    """Return the integer value of a Revit ``ElementId``-like object.

    Revit 2024+ exposes ``ElementId.Value`` (Int64); ``IntegerValue`` is
    deprecated there and removed in later versions. Plain ints pass through.
    """
    if isinstance(revit_id, int):
        return revit_id
    value = getattr(revit_id, "Value", None)
    if value is None:
        value = revit_id.IntegerValue
    return int(value)


def category_name(revit_element: Any) -> str | None:
    """Return a category name for a Revit element, or ``None``.

    Accepts a plain string ``Category`` (mocks, adapters) or a Revit
    ``Category`` object, in which case its ``Name`` is used.
    """
    category = getattr(revit_element, "Category", None)
    if category is None or isinstance(category, str):
        return category
    return getattr(category, "Name", None)


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

    @model_validator(mode="after")
    def _coerce_value(self) -> ParameterValue:
        """Coerce ``value`` to match ``storage_type``.

        Runs after all fields are populated so ``storage_type`` is always
        available regardless of field declaration order.
        """
        v = self.value
        if v is None:
            return self

        if self.storage_type == "Double" and not isinstance(v, int | float):
            try:
                self.value = float(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Cannot convert {v!r} to double") from e

        elif self.storage_type == "Integer" and not isinstance(v, int):
            try:
                self.value = int(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Cannot convert {v!r} to integer") from e

        return self


class ElementMetaclass(type):
    """Metaclass for Element that handles property registration."""

    # Maps a category name (e.g. "OST_Walls" or "Walls") to the most
    # specific Element subclass registered for it.
    category_registry: ClassVar[dict[str, type]] = {}

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        # Register property accessors
        cls = super().__new__(mcs, name, bases, namespace)

        # Add dynamic property access
        if hasattr(cls, "_property_mappings"):
            for prop_name, revit_param in cls._property_mappings.items():
                setattr(cls, prop_name, ElementProperty(revit_param))

        for category in namespace.get("revit_categories", ()):
            mcs.category_registry[category] = cls

        return cls


class ElementProperty:
    """Descriptor for element properties with automatic type conversion."""

    def __init__(self, parameter_name: str, read_only: bool = False) -> None:
        self.parameter_name = parameter_name
        self.read_only = read_only

    def __get__(self, obj: Element | None, objtype: type | None = None) -> Any:
        if obj is None:
            return self

        try:
            return obj.get_parameter_value(self.parameter_name)
        except Exception as e:
            # Callers handle the raised error; many elements simply lack a
            # given parameter, so this is not worth a warning.
            logger.debug(
                f"Failed to get parameter {self.parameter_name} from element {obj.id}: {e}"
            )
            raise RevitAPIError(
                f"Failed to get parameter {self.parameter_name} from element {obj.id}",
                cause=e,
            ) from e

    def __set__(self, obj: Element, value: Any) -> None:
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

    Subclasses may declare ``revit_categories`` (built-in category names such
    as ``"OST_Walls"`` and/or display names such as ``"Walls"``). Elements are
    then wrapped in the matching subclass, which makes typed queries such as
    ``api.query(Wall)`` work.
    """

    revit_categories: ClassVar[tuple[str, ...]] = ()

    # Property mappings for common parameters
    _property_mappings: dict[str, str] = {
        "name": "Name",
        "family_name": "Family",
        "type_name": "Type",
        "level": "Level",
        "comments": "Comments",
        "mark": "Mark",
    }

    def __init__(self, revit_element: IRevitElement) -> None:
        self._revit_element = revit_element
        self._parameter_cache: dict[str, ParameterValue] = {}
        self._change_tracker: dict[str, Any] = {}
        self._is_dirty = False

        # Create weak reference to avoid circular references
        self._weak_ref = weakref.ref(self)

    @classmethod
    def wrap(cls, revit_element: IRevitElement) -> Element:
        """Wrap a Revit element in the most specific registered subclass.

        Falls back to ``cls`` when the element's category is unknown.
        """
        category = category_name(revit_element)
        subclass = ElementMetaclass.category_registry.get(category or "")
        if subclass is not None and issubclass(subclass, cls):
            return subclass(revit_element)
        return cls(revit_element)

    @property
    def id(self) -> ElementId:
        """Get the element ID."""
        return ElementId(element_id_value(self._revit_element.Id))

    @property
    def category(self) -> str | None:
        """Get the element's category name, if available."""
        return category_name(self._revit_element)

    @property
    def name(self) -> str:
        """Get the element name."""
        return self._revit_element.Name or ""

    @name.setter
    def name(self, value: str) -> None:
        """Set the element name."""
        self.set_parameter_value("Name", value)

    @property
    def is_dirty(self) -> bool:
        """Check if element has unsaved changes."""
        return self._is_dirty

    @property
    def changes(self) -> dict[str, Any]:
        """Get tracked changes."""
        return self._change_tracker.copy()

    def get_parameter_value(self, parameter_name: str, use_cache: bool = True) -> Any:
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
                storage_type=self._get_storage_type(raw_value),
            )

            if use_cache:
                self._parameter_cache[parameter_name] = param_value

            return converted_value

        except Exception as e:
            raise ElementNotFoundError(
                element_id=self.id, element_type=parameter_name, cause=e
            )

    def set_parameter_value(
        self, parameter_name: str, value: Any, track_changes: bool = True
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

            # Capture the pre-change value so discard_changes() can restore it.
            # Repeated writes keep the original value from the first write.
            old_value: Any = None
            if track_changes:
                previous = self._change_tracker.get(parameter_name)
                if previous is not None:
                    old_value = previous["old"]
                elif parameter_name in self._parameter_cache:
                    old_value = self._parameter_cache[parameter_name].value
                else:
                    try:
                        old_value = self.get_parameter_value(
                            parameter_name, use_cache=False
                        )
                    except ElementNotFoundError:
                        old_value = None  # parameter is being created

            # Set the value
            self._revit_element.SetParameterValue(parameter_name, revit_value)

            # Track changes
            if track_changes:
                if old_value != value:
                    self._change_tracker[parameter_name] = {
                        "old": old_value,
                        "new": value,
                    }
                    self._is_dirty = True
                else:
                    self._change_tracker.pop(parameter_name, None)
                    self._is_dirty = bool(self._change_tracker)

            # Update cache
            param_value = ParameterValue(
                name=parameter_name,
                value=value,
                type_name=type(value).__name__,
                storage_type=self._get_storage_type(revit_value),
            )
            self._parameter_cache[parameter_name] = param_value

            logger.debug(
                f"Set parameter {parameter_name} = {value} on element {self.id}"
            )

        except PermissionError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set parameter {parameter_name} on element {self.id}: {e}"
            )
            raise ValidationError(
                f"Failed to set parameter {parameter_name}",
                field=parameter_name,
                value=value,
                cause=e,
            )

    def get_all_parameters(
        self, refresh_cache: bool = False
    ) -> dict[str, ParameterValue]:
        """
        Get all parameters for this element.

        Args:
            refresh_cache: Whether to refresh the parameter cache

        Returns:
            Dictionary of parameter names to values
        """
        if refresh_cache:
            self._parameter_cache.clear()

        parameters = {}

        for param_name in self._get_all_parameter_names():
            try:
                self.get_parameter_value(param_name, use_cache=not refresh_cache)
                parameters[param_name] = self._parameter_cache[param_name]
            except ElementNotFoundError:
                continue

        return parameters

    def save_changes(self) -> None:
        """Accept tracked changes.

        Parameter writes are applied to the Revit element immediately, so they
        become permanent when the enclosing transaction commits (and are
        reverted by Revit if it rolls back). This method only clears the
        local change log.
        """
        if not self._is_dirty:
            return

        logger.debug(
            f"Accepting {len(self._change_tracker)} changes on element {self.id}"
        )

        # Clear change tracking
        self._change_tracker.clear()
        self._is_dirty = False

    def discard_changes(self) -> None:
        """Revert tracked changes by writing the previous values back.

        Must be called while a transaction is open, like any other write.
        """
        if not self._is_dirty:
            return

        for param_name, change in self._change_tracker.items():
            self._parameter_cache.pop(param_name, None)
            if change.get("old") is not None:
                self._revit_element.SetParameterValue(param_name, change["old"])

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

        # Adapters (e.g. revitpy.revit) already return plain Python values.
        if isinstance(value, str | int | float | bool):
            return value

        # A Revit Parameter exposes every As* accessor; pick by storage type.
        storage_type = getattr(value, "StorageType", None)
        if storage_type is not None:
            kind = str(storage_type).split(".")[-1]
            if kind == "String":
                return value.AsString()
            if kind == "Double":
                return value.AsDouble()
            if kind == "Integer":
                return value.AsInteger()
            if kind == "ElementId":
                return element_id_value(value.AsElementId())
            return value.AsValueString()

        # Handle common Revit types
        if hasattr(value, "AsString"):
            return value.AsString()
        elif hasattr(value, "AsDouble"):
            return value.AsDouble()
        elif hasattr(value, "AsInteger"):
            return value.AsInteger()
        elif hasattr(value, "AsValueString"):
            return value.AsValueString()

        return str(value)

    def _convert_to_revit(self, value: Any) -> Any:
        """Convert a Python value for ``IRevitElement.SetParameterValue``.

        RevitPy wrapper types are unwrapped to plain values; storage-type
        specific conversion (e.g. to ``DB.ElementId``) is the responsibility
        of the element adapter, which knows the target parameter.
        """
        if isinstance(value, ElementId):
            return value.value
        if isinstance(value, Element):
            return value.id.value
        return value

    def _get_storage_type(self, value: Any) -> str:
        """Determine storage type from Revit value."""
        if hasattr(value, "StorageType"):
            return str(value.StorageType).split(".")[-1]
        if isinstance(value, bool):
            return "Integer"
        if isinstance(value, float):
            return "Double"
        if isinstance(value, int):
            return "Integer"
        return "String"

    def _get_all_parameter_names(self) -> list[str]:
        """Get all parameter names for this element.

        Uses ``GetAllParameters()`` on the underlying element when available,
        otherwise falls back to the mapped common parameters.
        """
        get_all = getattr(self._revit_element, "GetAllParameters", None)
        if callable(get_all):
            try:
                return list(get_all())
            except Exception as e:
                logger.debug(f"GetAllParameters failed on element {self.id}: {e}")
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


class Wall(Element):
    """Wall element."""

    revit_categories = ("OST_Walls", "Walls")


class Floor(Element):
    """Floor element."""

    revit_categories = ("OST_Floors", "Floors")


class Door(Element):
    """Door element."""

    revit_categories = ("OST_Doors", "Doors")


class Window(Element):
    """Window element."""

    revit_categories = ("OST_Windows", "Windows")


class Room(Element):
    """Room element."""

    revit_categories = ("OST_Rooms", "Rooms")


class Level(Element):
    """Level element."""

    revit_categories = ("OST_Levels", "Levels")


class ElementSet(Generic[T]):
    """
    Collection of elements with LINQ-style operations and lazy evaluation.
    """

    def __init__(self, elements: list[T] | None = None) -> None:
        self._elements: list[T] = elements or []
        self._is_evaluated = bool(elements)
        self._query_operations: list[Any] = []

    @property
    def count(self) -> int:
        """Get the number of elements in the collection.

        This is a property because ElementSet holds an already-materialized
        (or lazily-evaluated) collection. For filtered counts, chain with
        ``where``::

            element_set.where(predicate).count

        Note: ``QueryBuilder.count()`` is a method because it is a terminal
        operation that triggers query execution.
        """
        self._ensure_evaluated()
        return len(self._elements)

    def where(self, predicate: callable) -> ElementSet[T]:
        """Filter elements using a predicate."""
        new_set = ElementSet[T]()
        new_set._query_operations = self._query_operations + [("where", predicate)]
        new_set._is_evaluated = False
        return new_set

    def select(self, selector: callable) -> ElementSet:
        """Transform elements using a selector."""
        new_set = ElementSet()
        new_set._query_operations = self._query_operations + [("select", selector)]
        new_set._is_evaluated = False
        return new_set

    def first(self, predicate: callable | None = None) -> T:
        """Get the first element matching the predicate."""
        if predicate:
            filtered = self.where(predicate)
            return filtered.first()

        self._ensure_evaluated()
        if not self._elements:
            raise ElementNotFoundError("No elements in set")

        return self._elements[0]

    def first_or_default(
        self, predicate: callable | None = None, default: T | None = None
    ) -> T | None:
        """Get the first element matching the predicate or default."""
        try:
            return self.first(predicate)
        except ElementNotFoundError:
            return default

    def single(self, predicate: callable | None = None) -> T:
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

    def to_list(self) -> list[T]:
        """Convert to list."""
        self._ensure_evaluated()
        return self._elements.copy()

    def any(self, predicate: callable | None = None) -> bool:
        """Check if any elements match the predicate."""
        if predicate:
            return self.where(predicate).any()

        self._ensure_evaluated()
        return len(self._elements) > 0

    def all(self, predicate: callable) -> bool:
        """Check if all elements match the predicate."""
        self._ensure_evaluated()
        return all(predicate(element) for element in self._elements)

    def order_by(self, key_selector: callable) -> ElementSet[T]:
        """Order elements by key selector."""
        new_set = ElementSet[T]()
        new_set._query_operations = self._query_operations + [
            ("order_by", key_selector)
        ]
        new_set._is_evaluated = False
        return new_set

    def group_by(self, key_selector: callable) -> dict[Any, list[T]]:
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
            if operation == "where":
                result = [x for x in result if func(x)]
            elif operation == "select":
                result = [func(x) for x in result]
            elif operation == "order_by":
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
