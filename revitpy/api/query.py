"""
LINQ-style querying system for Revit elements.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from loguru import logger

from .element import Element, ElementSet

T = TypeVar("T", bound=Element)


class FilterOperator(Enum):
    """Filter operators for queries."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    REGEX = "regex"


class SortDirection(Enum):
    """Sort direction for queries."""

    ASCENDING = "asc"
    DESCENDING = "desc"


@dataclass
class FilterCriteria:
    """Represents a filter criteria for querying."""

    property_name: str
    operator: FilterOperator
    value: Any = None
    case_sensitive: bool = True

    def apply(self, element: Element) -> bool:
        """Apply this filter criteria to an element."""
        try:
            element_value = element.get_parameter_value(self.property_name)

            if self.operator == FilterOperator.EQUALS:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x == y
                )
            elif self.operator == FilterOperator.NOT_EQUALS:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x != y
                )
            elif self.operator == FilterOperator.GREATER_THAN:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x > y
                )
            elif self.operator == FilterOperator.LESS_THAN:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x < y
                )
            elif self.operator == FilterOperator.GREATER_EQUAL:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x >= y
                )
            elif self.operator == FilterOperator.LESS_EQUAL:
                return self._compare_values(
                    element_value, self.value, lambda x, y: x <= y
                )
            elif self.operator == FilterOperator.CONTAINS:
                return self._string_compare(
                    element_value, self.value, lambda x, y: y in x
                )
            elif self.operator == FilterOperator.STARTS_WITH:
                return self._string_compare(
                    element_value, self.value, lambda x, y: x.startswith(y)
                )
            elif self.operator == FilterOperator.ENDS_WITH:
                return self._string_compare(
                    element_value, self.value, lambda x, y: x.endswith(y)
                )
            elif self.operator == FilterOperator.IN:
                return element_value in self.value if self.value else False
            elif self.operator == FilterOperator.NOT_IN:
                return element_value not in self.value if self.value else True
            elif self.operator == FilterOperator.IS_NULL:
                return element_value is None
            elif self.operator == FilterOperator.IS_NOT_NULL:
                return element_value is not None
            elif self.operator == FilterOperator.REGEX:
                import re

                pattern = self.value if self.case_sensitive else f"(?i){self.value}"
                return bool(re.search(pattern, str(element_value)))

            return False

        except Exception as e:
            logger.warning(f"Error applying filter {self.property_name}: {e}")
            return False

    def _compare_values(
        self, a: Any, b: Any, comparator: Callable[[Any, Any], bool]
    ) -> bool:
        """Compare two values with type conversion."""
        if a is None or b is None:
            return a is None and b is None

        # Try to convert to same type
        try:
            if isinstance(a, str) and not isinstance(b, str):
                b = str(b)
            elif isinstance(b, str) and not isinstance(a, str):
                a = str(a)
            elif isinstance(a, int | float) and isinstance(b, int | float):
                pass  # Numeric comparison is fine

            return comparator(a, b)
        except (ValueError, TypeError):
            # Fall back to string comparison
            return comparator(str(a), str(b))

    def _string_compare(
        self, a: Any, b: Any, comparator: Callable[[str, str], bool]
    ) -> bool:
        """Compare values as strings."""
        str_a = str(a) if a is not None else ""
        str_b = str(b) if b is not None else ""

        if not self.case_sensitive:
            str_a = str_a.lower()
            str_b = str_b.lower()

        return comparator(str_a, str_b)


@dataclass
class SortCriteria:
    """Represents a sort criteria for querying."""

    property_name: str
    direction: SortDirection = SortDirection.ASCENDING

    def get_sort_key(self, element: Element) -> Any:
        """Get the sort key for an element."""
        try:
            value = element.get_parameter_value(self.property_name)
            return value if value is not None else ""
        except Exception:
            return ""


@runtime_checkable
class IElementProvider(Protocol):
    """Protocol for element providers."""

    def get_all_elements(self) -> list[Element]:
        """Get all elements from the provider."""
        ...

    def get_elements_of_type(self, element_type: type[Element]) -> list[Element]:
        """Get elements of specific type."""
        ...


class QueryBuilder(Generic[T]):
    """
    LINQ-style query builder for Revit elements.
    """

    def __init__(
        self, provider: IElementProvider, element_type: type[T] | None = None
    ) -> None:
        self._provider = provider
        self._element_type = element_type or Element
        self._filters: list[FilterCriteria] = []
        self._sorts: list[SortCriteria] = []
        self._skip_count = 0
        self._take_count: int | None = None
        self._distinct_property: str | None = None

    def where(
        self,
        property_name: str,
        operator: FilterOperator,
        value: Any = None,
        case_sensitive: bool = True,
    ) -> QueryBuilder[T]:
        """Add a filter criteria."""
        criteria = FilterCriteria(property_name, operator, value, case_sensitive)
        self._filters.append(criteria)
        return self

    def equals(
        self, property_name: str, value: Any, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by equality."""
        return self.where(property_name, FilterOperator.EQUALS, value, case_sensitive)

    def not_equals(
        self, property_name: str, value: Any, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by inequality."""
        return self.where(
            property_name, FilterOperator.NOT_EQUALS, value, case_sensitive
        )

    def contains(
        self, property_name: str, value: str, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by string contains."""
        return self.where(property_name, FilterOperator.CONTAINS, value, case_sensitive)

    def starts_with(
        self, property_name: str, value: str, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by string starts with."""
        return self.where(
            property_name, FilterOperator.STARTS_WITH, value, case_sensitive
        )

    def ends_with(
        self, property_name: str, value: str, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by string ends with."""
        return self.where(
            property_name, FilterOperator.ENDS_WITH, value, case_sensitive
        )

    def in_values(self, property_name: str, values: list[Any]) -> QueryBuilder[T]:
        """Filter by value in list."""
        return self.where(property_name, FilterOperator.IN, values)

    def is_null(self, property_name: str) -> QueryBuilder[T]:
        """Filter by null value."""
        return self.where(property_name, FilterOperator.IS_NULL)

    def is_not_null(self, property_name: str) -> QueryBuilder[T]:
        """Filter by non-null value."""
        return self.where(property_name, FilterOperator.IS_NOT_NULL)

    def regex(
        self, property_name: str, pattern: str, case_sensitive: bool = True
    ) -> QueryBuilder[T]:
        """Filter by regular expression."""
        return self.where(property_name, FilterOperator.REGEX, pattern, case_sensitive)

    def order_by(
        self, property_name: str, direction: SortDirection = SortDirection.ASCENDING
    ) -> QueryBuilder[T]:
        """Add sort criteria."""
        criteria = SortCriteria(property_name, direction)
        self._sorts.append(criteria)
        return self

    def order_by_ascending(self, property_name: str) -> QueryBuilder[T]:
        """Sort by property ascending."""
        return self.order_by(property_name, SortDirection.ASCENDING)

    def order_by_descending(self, property_name: str) -> QueryBuilder[T]:
        """Sort by property descending."""
        return self.order_by(property_name, SortDirection.DESCENDING)

    def skip(self, count: int) -> QueryBuilder[T]:
        """Skip number of elements."""
        self._skip_count = count
        return self

    def take(self, count: int) -> QueryBuilder[T]:
        """Take number of elements."""
        self._take_count = count
        return self

    def distinct(self, property_name: str | None = None) -> QueryBuilder[T]:
        """Get distinct elements by property."""
        self._distinct_property = property_name
        return self

    def execute(self) -> ElementSet[T]:
        """Execute the query and return results."""
        # Get base elements
        if self._element_type and self._element_type != Element:
            elements = self._provider.get_elements_of_type(self._element_type)
        else:
            elements = self._provider.get_all_elements()

        # Apply filters
        filtered_elements = elements
        for criteria in self._filters:
            filtered_elements = [
                element for element in filtered_elements if criteria.apply(element)
            ]

        # Apply sorting
        if self._sorts:

            def sort_key(element: Element) -> tuple:
                keys = []
                for sort_criteria in self._sorts:
                    key = sort_criteria.get_sort_key(element)
                    if sort_criteria.direction == SortDirection.DESCENDING:
                        # For descending, we need to reverse the comparison
                        if isinstance(key, str):
                            key = key[::-1] if key else ""
                        elif isinstance(key, int | float):
                            key = -key
                    keys.append(key)
                return tuple(keys)

            filtered_elements = sorted(filtered_elements, key=sort_key)

        # Apply distinct
        if self._distinct_property:
            seen_values = set()
            distinct_elements = []

            for element in filtered_elements:
                try:
                    value = element.get_parameter_value(self._distinct_property)
                    if value not in seen_values:
                        seen_values.add(value)
                        distinct_elements.append(element)
                except Exception:
                    # Include elements where property can't be read
                    distinct_elements.append(element)

            filtered_elements = distinct_elements

        # Apply skip and take
        start_index = self._skip_count
        end_index = start_index + self._take_count if self._take_count else None

        final_elements = filtered_elements[start_index:end_index]

        logger.debug(
            f"Query executed: {len(elements)} -> {len(filtered_elements)} -> {len(final_elements)} elements"
        )

        return ElementSet(final_elements)

    def count(self) -> int:
        """Get count of elements matching query."""
        result = self.execute()
        return result.count

    def any(self) -> bool:
        """Check if any elements match query."""
        # Optimize by taking only 1 element
        temp_take = self._take_count
        self._take_count = 1

        result = self.execute()
        has_any = result.count > 0

        # Restore original take count
        self._take_count = temp_take

        return has_any

    def first(self) -> T:
        """Get first element matching query."""
        result = self.take(1).execute()
        return result.first()

    def first_or_default(self, default: T | None = None) -> T | None:
        """Get first element matching query or default."""
        result = self.take(1).execute()
        return result.first_or_default(default=default)

    def single(self) -> T:
        """Get single element matching query."""
        result = self.take(2).execute()  # Take 2 to detect multiple
        return result.single()

    def to_list(self) -> list[T]:
        """Convert query to list."""
        return self.execute().to_list()


class Query:
    """
    Static factory class for creating queries.
    """

    @staticmethod
    def from_provider(provider: IElementProvider) -> QueryBuilder[Element]:
        """Create a query from element provider."""
        return QueryBuilder(provider)

    @staticmethod
    def from_elements(elements: list[Element]) -> QueryBuilder[Element]:
        """Create a query from element list."""

        class ListProvider:
            def __init__(self, elements: list[Element]) -> None:
                self.elements = elements

            def get_all_elements(self) -> list[Element]:
                return self.elements

            def get_elements_of_type(
                self, element_type: type[Element]
            ) -> list[Element]:
                return [e for e in self.elements if isinstance(e, element_type)]

        return QueryBuilder(ListProvider(elements))

    @staticmethod
    def of_type(provider: IElementProvider, element_type: type[T]) -> QueryBuilder[T]:
        """Create a typed query."""
        return QueryBuilder(provider, element_type)
