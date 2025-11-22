"""
Event filters for selective event handling.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .types import ElementEventData, EventData, EventType, ParameterEventData


class EventFilter(ABC):
    """Abstract base class for event filters."""

    @abstractmethod
    def matches(self, event_data: EventData) -> bool:
        """
        Check if the event matches this filter.

        Args:
            event_data: Event data to check

        Returns:
            True if the event matches the filter
        """
        pass

    def __and__(self, other: EventFilter) -> EventFilter:
        """Combine filters with AND logic."""
        return AndFilter(self, other)

    def __or__(self, other: EventFilter) -> EventFilter:
        """Combine filters with OR logic."""
        return OrFilter(self, other)

    def __invert__(self) -> EventFilter:
        """Invert filter with NOT logic."""
        return NotFilter(self)


class EventTypeFilter(EventFilter):
    """Filter events by event type."""

    def __init__(self, *event_types: EventType) -> None:
        self.event_types = set(event_types)

    def matches(self, event_data: EventData) -> bool:
        return event_data.event_type in self.event_types


class ElementTypeFilter(EventFilter):
    """Filter element events by element type."""

    def __init__(self, *element_types: str) -> None:
        self.element_types = set(element_types)

    def matches(self, event_data: EventData) -> bool:
        if not isinstance(event_data, ElementEventData):
            return False

        return event_data.element_type in self.element_types


class CategoryFilter(EventFilter):
    """Filter element events by category."""

    def __init__(self, *categories: str) -> None:
        self.categories = set(categories)

    def matches(self, event_data: EventData) -> bool:
        if not isinstance(event_data, ElementEventData):
            return False

        return event_data.category in self.categories


class ParameterChangeFilter(EventFilter):
    """Filter parameter change events by parameter name."""

    def __init__(self, *parameter_names: str, use_regex: bool = False) -> None:
        if use_regex:
            self.patterns = [re.compile(name) for name in parameter_names]
            self.use_regex = True
        else:
            self.parameter_names = set(parameter_names)
            self.use_regex = False

    def matches(self, event_data: EventData) -> bool:
        if isinstance(event_data, ParameterEventData):
            if self.use_regex:
                return any(
                    pattern.search(event_data.parameter_name)
                    for pattern in self.patterns
                )
            else:
                return event_data.parameter_name in self.parameter_names

        elif isinstance(event_data, ElementEventData):
            if self.use_regex:
                return any(
                    pattern.search(param_name)
                    for param_name in event_data.parameters_changed
                    for pattern in self.patterns
                )
            else:
                return bool(set(event_data.parameters_changed) & self.parameter_names)

        return False


class ElementIdFilter(EventFilter):
    """Filter events by specific element IDs."""

    def __init__(self, *element_ids: Any) -> None:
        self.element_ids = set(element_ids)

    def matches(self, event_data: EventData) -> bool:
        if isinstance(event_data, ElementEventData):
            return event_data.element_id in self.element_ids
        elif isinstance(event_data, ParameterEventData):
            return event_data.element_id in self.element_ids

        return False


class SourceFilter(EventFilter):
    """Filter events by source object."""

    def __init__(self, source: Any) -> None:
        self.source = source

    def matches(self, event_data: EventData) -> bool:
        return event_data.source == self.source


class DataFilter(EventFilter):
    """Filter events by data content."""

    def __init__(
        self,
        key: str,
        value: Any = None,
        predicate: Callable[[Any], bool] | None = None,
    ) -> None:
        self.key = key
        self.value = value
        self.predicate = predicate

    def matches(self, event_data: EventData) -> bool:
        if self.key not in event_data.data:
            return False

        data_value = event_data.data[self.key]

        if self.predicate:
            return self.predicate(data_value)
        else:
            return data_value == self.value


class TimeRangeFilter(EventFilter):
    """Filter events by timestamp range."""

    def __init__(
        self, start_time: Any | None = None, end_time: Any | None = None
    ) -> None:
        self.start_time = start_time
        self.end_time = end_time

    def matches(self, event_data: EventData) -> bool:
        timestamp = event_data.timestamp

        if self.start_time and timestamp < self.start_time:
            return False

        if self.end_time and timestamp > self.end_time:
            return False

        return True


class CancellableFilter(EventFilter):
    """Filter events by whether they are cancellable."""

    def __init__(self, cancellable: bool = True) -> None:
        self.cancellable = cancellable

    def matches(self, event_data: EventData) -> bool:
        return event_data.cancellable == self.cancellable


class CustomFilter(EventFilter):
    """Custom filter using a predicate function."""

    def __init__(self, predicate: Callable[[EventData], bool]) -> None:
        self.predicate = predicate

    def matches(self, event_data: EventData) -> bool:
        return self.predicate(event_data)


class AndFilter(EventFilter):
    """Combines multiple filters with AND logic."""

    def __init__(self, *filters: EventFilter) -> None:
        self.filters = filters

    def matches(self, event_data: EventData) -> bool:
        return all(f.matches(event_data) for f in self.filters)


class OrFilter(EventFilter):
    """Combines multiple filters with OR logic."""

    def __init__(self, *filters: EventFilter) -> None:
        self.filters = filters

    def matches(self, event_data: EventData) -> bool:
        return any(f.matches(event_data) for f in self.filters)


class NotFilter(EventFilter):
    """Inverts another filter."""

    def __init__(self, filter_to_invert: EventFilter) -> None:
        self.filter_to_invert = filter_to_invert

    def matches(self, event_data: EventData) -> bool:
        return not self.filter_to_invert.matches(event_data)


# Convenience factory functions


def element_type(*types: str) -> ElementTypeFilter:
    """Create an element type filter."""
    return ElementTypeFilter(*types)


def category(*categories: str) -> CategoryFilter:
    """Create a category filter."""
    return CategoryFilter(*categories)


def parameter_changed(
    *param_names: str, use_regex: bool = False
) -> ParameterChangeFilter:
    """Create a parameter change filter."""
    return ParameterChangeFilter(*param_names, use_regex=use_regex)


def element_id(*ids: Any) -> ElementIdFilter:
    """Create an element ID filter."""
    return ElementIdFilter(*ids)


def event_type(*types: EventType) -> EventTypeFilter:
    """Create an event type filter."""
    return EventTypeFilter(*types)


def source_is(source: Any) -> SourceFilter:
    """Create a source filter."""
    return SourceFilter(source)


def data_equals(key: str, value: Any) -> DataFilter:
    """Create a data filter for equality."""
    return DataFilter(key, value)


def data_matches(key: str, predicate: Callable[[Any], bool]) -> DataFilter:
    """Create a data filter with custom predicate."""
    return DataFilter(key, predicate=predicate)


def time_range(
    start_time: Any | None = None, end_time: Any | None = None
) -> TimeRangeFilter:
    """Create a time range filter."""
    return TimeRangeFilter(start_time, end_time)


def cancellable(is_cancellable: bool = True) -> CancellableFilter:
    """Create a cancellable filter."""
    return CancellableFilter(is_cancellable)


def custom(predicate: Callable[[EventData], bool]) -> CustomFilter:
    """Create a custom filter."""
    return CustomFilter(predicate)


# Common filter combinations


def walls_created() -> EventFilter:
    """Filter for wall creation events."""
    return event_type(EventType.ELEMENT_CREATED) & element_type("Wall")


def doors_and_windows() -> EventFilter:
    """Filter for door and window events."""
    return category("Doors", "Windows")


def parameter_change_events() -> EventFilter:
    """Filter for any parameter change events."""
    return event_type(
        EventType.PARAMETER_CHANGED,
        EventType.PARAMETER_ADDED,
        EventType.PARAMETER_REMOVED,
    )


def structural_elements() -> EventFilter:
    """Filter for structural element events."""
    return category("Structural Columns", "Structural Beams", "Structural Foundations")


def document_events() -> EventFilter:
    """Filter for document-related events."""
    return event_type(
        EventType.DOCUMENT_OPENED,
        EventType.DOCUMENT_CLOSED,
        EventType.DOCUMENT_SAVED,
        EventType.DOCUMENT_SYNCHRONIZED,
    )
