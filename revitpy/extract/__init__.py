"""
RevitPy Extract Layer - Quantity takeoffs, cost estimation, and data export.

This module provides a comprehensive extraction layer for Revit projects,
offering quantity extraction, material takeoffs, cost estimation,
schedule building, and multi-format data export.

Key Features:
- Quantity extraction (area, volume, length, count, weight)
- Material takeoff with classification (UniFormat, MasterFormat)
- Cost estimation with pluggable cost databases
- Schedule building with filtering, sorting, grouping, and totals
- Export to CSV, JSON, Excel, and Parquet

Usage:
    from revitpy.extract import extract_quantities, material_takeoff

    quantities = extract_quantities(elements)
    materials = material_takeoff(elements)
"""

from .costs import CostEstimator
from .exceptions import (
    CostEstimationError,
    ExportError,
    ExtractionError,
    QuantityError,
    ScheduleError,
)
from .exporters import DataExporter
from .materials import MaterialTakeoff
from .quantities import QuantityExtractor
from .schedules import ScheduleBuilder
from .types import (
    AggregationLevel,
    CostItem,
    CostSource,
    CostSummary,
    ExportConfig,
    ExportFormat,
    MaterialQuantity,
    QuantityItem,
    QuantityType,
    ScheduleConfig,
)

__all__ = [
    # Core classes
    "QuantityExtractor",
    "MaterialTakeoff",
    "CostEstimator",
    "ScheduleBuilder",
    "DataExporter",
    # Types and enums
    "QuantityType",
    "AggregationLevel",
    "ExportFormat",
    "CostSource",
    # Dataclasses
    "QuantityItem",
    "MaterialQuantity",
    "CostItem",
    "CostSummary",
    "ScheduleConfig",
    "ExportConfig",
    # Exceptions
    "ExtractionError",
    "QuantityError",
    "CostEstimationError",
    "ExportError",
    "ScheduleError",
]


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def extract_quantities(
    elements: list,
    quantity_types: list[QuantityType] | None = None,
    context=None,
) -> list[QuantityItem]:
    """Extract quantities from a list of elements.

    Convenience wrapper around ``QuantityExtractor.extract``.

    Args:
        elements: List of duck-typed element objects.
        quantity_types: Optional list of quantity types to extract.
        context: Optional RevitContext.

    Returns:
        List of extracted QuantityItem instances.
    """
    extractor = QuantityExtractor(context=context)
    return extractor.extract(elements, quantity_types=quantity_types)


def material_takeoff(
    elements: list,
    aggregate: bool = True,
    classify: bool = False,
    classification_system: str = "UniFormat",
    context=None,
) -> list[MaterialQuantity]:
    """Extract material quantities from elements.

    Convenience wrapper around ``MaterialTakeoff``.

    Args:
        elements: List of duck-typed element objects.
        aggregate: Whether to aggregate by material name.
        classify: Whether to classify materials.
        classification_system: Classification system to use.
        context: Optional RevitContext.

    Returns:
        List of MaterialQuantity instances.
    """
    takeoff = MaterialTakeoff(context=context)
    materials = takeoff.extract(elements)

    if aggregate:
        materials = takeoff.aggregate(materials)

    if classify:
        materials = takeoff.classify(materials, system=classification_system)

    return materials


def estimate_costs(
    quantities: list[QuantityItem],
    cost_database: dict[str, float] | None = None,
    aggregation: AggregationLevel = AggregationLevel.CATEGORY,
) -> CostSummary:
    """Estimate costs from extracted quantities.

    Convenience wrapper around ``CostEstimator.estimate``.

    Args:
        quantities: List of QuantityItem instances.
        cost_database: Dict mapping category names to unit costs.
        aggregation: Aggregation level for cost summary.

    Returns:
        CostSummary with itemized costs and totals.
    """
    estimator = CostEstimator(cost_database=cost_database)
    return estimator.estimate(quantities, aggregation=aggregation)


def export_data(
    data: list[dict],
    config: ExportConfig | None = None,
    **kwargs,
) -> ...:
    """Export data to the configured format.

    Convenience wrapper around ``DataExporter.export``.

    Args:
        data: List of row dicts.
        config: Export configuration. If None, returns dicts.
        **kwargs: Passed to ExportConfig if config is None.

    Returns:
        Path for file exports, or list[dict] for DICT format.
    """
    if config is None:
        config = (
            ExportConfig(**kwargs) if kwargs else ExportConfig(format=ExportFormat.DICT)
        )
    exporter = DataExporter()
    return exporter.export(data, config)
