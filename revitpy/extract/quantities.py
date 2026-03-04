"""
Quantity extraction for RevitPy.

This module provides the QuantityExtractor class for extracting
measured quantities (area, volume, length, count, weight) from
Revit elements using duck-typed attribute access.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from loguru import logger

from .exceptions import QuantityError
from .types import AggregationLevel, QuantityItem, QuantityType

# Mapping from QuantityType to (attribute_name, default_unit)
_QUANTITY_ATTR_MAP: dict[QuantityType, tuple[str, str]] = {
    QuantityType.AREA: ("area", "m2"),
    QuantityType.VOLUME: ("volume", "m3"),
    QuantityType.LENGTH: ("length", "m"),
    QuantityType.COUNT: ("count", "ea"),
    QuantityType.WEIGHT: ("weight", "kg"),
}


class QuantityExtractor:
    """Extract measured quantities from Revit elements.

    Elements are duck-typed objects with optional area, volume, length,
    count, weight, name, category, level, and system attributes.
    """

    def __init__(self, context: Any | None = None) -> None:
        self._context = context

    def extract(
        self,
        elements: list[Any],
        quantity_types: list[QuantityType] | None = None,
    ) -> list[QuantityItem]:
        """Extract quantities from elements.

        Args:
            elements: List of duck-typed element objects.
            quantity_types: Types to extract. Defaults to all types.

        Returns:
            List of extracted QuantityItem instances.

        Raises:
            QuantityError: If extraction fails for an element.
        """
        if quantity_types is None:
            quantity_types = list(QuantityType)

        items: list[QuantityItem] = []

        for element in elements:
            try:
                items.extend(self._extract_element(element, quantity_types))
            except Exception as exc:
                element_id = getattr(element, "id", None)
                logger.warning(
                    "Failed to extract quantities from element {}: {}",
                    element_id,
                    exc,
                )
                raise QuantityError(
                    f"Failed to extract quantities from element {element_id}",
                    element_id=element_id,
                    cause=exc,
                ) from exc

        logger.debug(
            "Extracted {} quantity items from {} elements",
            len(items),
            len(elements),
        )
        return items

    def _extract_element(
        self,
        element: Any,
        quantity_types: list[QuantityType],
    ) -> list[QuantityItem]:
        """Extract quantities from a single element."""
        items: list[QuantityItem] = []
        element_id = getattr(element, "id", None)
        element_name = getattr(element, "name", str(element_id) or "Unknown")
        category = getattr(element, "category", "Uncategorized")
        level = getattr(element, "level", "")
        system = getattr(element, "system", "")

        for qty_type in quantity_types:
            attr_name, default_unit = _QUANTITY_ATTR_MAP[qty_type]
            value = getattr(element, attr_name, None)

            if value is not None:
                try:
                    float_value = float(value)
                except (TypeError, ValueError):
                    continue

                if float_value > 0:
                    unit = getattr(element, f"{attr_name}_unit", default_unit)
                    items.append(
                        QuantityItem(
                            element_id=element_id,
                            element_name=str(element_name),
                            category=str(category),
                            quantity_type=qty_type,
                            value=float_value,
                            unit=str(unit),
                            level=str(level),
                            system=str(system),
                        )
                    )

        # COUNT is special: if requested and element exists, always count 1
        if QuantityType.COUNT in quantity_types:
            count_val = getattr(element, "count", None)
            if count_val is None:
                items.append(
                    QuantityItem(
                        element_id=element_id,
                        element_name=str(element_name),
                        category=str(category),
                        quantity_type=QuantityType.COUNT,
                        value=1.0,
                        unit="ea",
                        level=str(level),
                        system=str(system),
                    )
                )

        return items

    def extract_grouped(
        self,
        elements: list[Any],
        group_by: AggregationLevel = AggregationLevel.CATEGORY,
        quantity_types: list[QuantityType] | None = None,
    ) -> dict[str, list[QuantityItem]]:
        """Extract and group quantities by aggregation level.

        Args:
            elements: List of duck-typed element objects.
            group_by: Aggregation level to group by.
            quantity_types: Types to extract. Defaults to all types.

        Returns:
            Dict mapping group keys to lists of QuantityItem.
        """
        items = self.extract(elements, quantity_types)
        grouped: dict[str, list[QuantityItem]] = defaultdict(list)

        key_fn = self._get_group_key_fn(group_by)
        for item in items:
            key = key_fn(item)
            grouped[key].append(item)

        logger.debug(
            "Grouped {} items into {} groups by {}",
            len(items),
            len(grouped),
            group_by.value,
        )
        return dict(grouped)

    def summarize(self, items: list[QuantityItem]) -> dict[str, float]:
        """Summarize quantities by type, summing values.

        Args:
            items: List of QuantityItem instances.

        Returns:
            Dict mapping quantity type names to summed values.
        """
        summary: dict[str, float] = defaultdict(float)
        for item in items:
            summary[item.quantity_type.value] += item.value
        return dict(summary)

    async def extract_async(
        self,
        elements: list[Any],
        quantity_types: list[QuantityType] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> list[QuantityItem]:
        """Async version of extract with optional progress reporting.

        Args:
            elements: List of duck-typed element objects.
            quantity_types: Types to extract. Defaults to all types.
            progress: Optional callback(current, total) for progress.

        Returns:
            List of extracted QuantityItem instances.
        """
        if quantity_types is None:
            quantity_types = list(QuantityType)

        items: list[QuantityItem] = []
        total = len(elements)

        for idx, element in enumerate(elements):
            extracted = self._extract_element(element, quantity_types)
            items.extend(extracted)

            if progress is not None:
                progress(idx + 1, total)

            # Yield control to the event loop periodically
            if (idx + 1) % 100 == 0:
                await asyncio.sleep(0)

        logger.debug(
            "Async extracted {} quantity items from {} elements",
            len(items),
            len(elements),
        )
        return items

    @staticmethod
    def _get_group_key_fn(
        group_by: AggregationLevel,
    ) -> Callable[[QuantityItem], str]:
        """Return a function that extracts the grouping key from a QuantityItem."""
        if group_by == AggregationLevel.CATEGORY:
            return lambda item: item.category
        if group_by == AggregationLevel.LEVEL:
            return lambda item: item.level or "No Level"
        if group_by == AggregationLevel.SYSTEM:
            return lambda item: item.system or "No System"
        if group_by == AggregationLevel.ELEMENT:
            return lambda item: str(item.element_id)
        if group_by == AggregationLevel.BUILDING:
            return lambda _item: "Building"
        return lambda item: item.category
