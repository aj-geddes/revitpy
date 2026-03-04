"""
Type definitions and enums for the RevitPy extraction layer.

This module provides all type definitions, enums, and dataclasses used
throughout the extraction system for quantity takeoffs, cost estimation,
schedule building, and data export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class QuantityType(Enum):
    """Types of quantities that can be extracted from elements."""

    AREA = "area"
    VOLUME = "volume"
    LENGTH = "length"
    COUNT = "count"
    WEIGHT = "weight"


class AggregationLevel(Enum):
    """Levels at which extracted data can be aggregated."""

    ELEMENT = "element"
    CATEGORY = "category"
    LEVEL = "level"
    SYSTEM = "system"
    BUILDING = "building"


class ExportFormat(Enum):
    """Supported data export formats."""

    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PARQUET = "parquet"
    DICT = "dict"


class CostSource(Enum):
    """Sources for cost data."""

    CSV_FILE = "csv_file"
    JSON_FILE = "json_file"
    YAML_FILE = "yaml_file"
    MANUAL = "manual"


@dataclass
class QuantityItem:
    """A single extracted quantity from an element."""

    element_id: Any
    element_name: str
    category: str
    quantity_type: QuantityType
    value: float
    unit: str
    level: str = ""
    system: str = ""


@dataclass
class MaterialQuantity:
    """Material quantity data extracted from elements."""

    material_name: str
    category: str
    volume: float = 0.0
    area: float = 0.0
    mass: float = 0.0
    classification_code: str = ""
    classification_system: str = ""


@dataclass
class CostItem:
    """A single cost line item."""

    description: str
    quantity: float
    unit: str
    unit_cost: float
    total_cost: float
    source: CostSource = CostSource.MANUAL
    category: str = ""
    system: str = ""


@dataclass
class CostSummary:
    """Summary of cost estimation results."""

    items: list[CostItem] = field(default_factory=list)
    total_cost: float = 0.0
    by_category: dict[str, float] = field(default_factory=dict)
    by_system: dict[str, float] = field(default_factory=dict)
    by_level: dict[str, float] = field(default_factory=dict)
    currency: str = "USD"


@dataclass
class ScheduleConfig:
    """Configuration for building a schedule view."""

    columns: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    sort_by: list[str] = field(default_factory=list)
    group_by: str = ""
    include_totals: bool = False
    title: str = ""


@dataclass
class ExportConfig:
    """Configuration for data export."""

    format: ExportFormat = ExportFormat.CSV
    output_path: Path | None = None
    include_headers: bool = True
    decimal_places: int = 2
    sheet_name: str = "Sheet1"
