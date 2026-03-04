"""
Type definitions, enums, and dataclasses for the RevitPy sustainability layer.

This module provides all type definitions used throughout the sustainability
system for carbon calculation, EPD management, compliance checking, and
sustainability reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LifecycleStage(Enum):
    """EN 15978 lifecycle stages for whole-life carbon assessment."""

    A1_RAW_MATERIALS = "A1"
    A2_TRANSPORT = "A2"
    A3_MANUFACTURING = "A3"
    A4_TRANSPORT_SITE = "A4"
    A5_CONSTRUCTION = "A5"
    B1_USE = "B1"
    B2_MAINTENANCE = "B2"
    B3_REPAIR = "B3"
    B4_REPLACEMENT = "B4"
    B5_REFURBISHMENT = "B5"
    B6_ENERGY = "B6"
    B7_WATER = "B7"
    C1_DEMOLITION = "C1"
    C2_TRANSPORT = "C2"
    C3_WASTE = "C3"
    C4_DISPOSAL = "C4"
    D_REUSE = "D"


class CertificationSystem(Enum):
    """Green building certification systems."""

    LEED = "LEED"
    BREEAM = "BREEAM"
    WELL = "WELL"
    GREENSTAR = "Green Star"
    DGNB = "DGNB"


class ComplianceStandard(Enum):
    """Building emissions compliance standards."""

    LL97 = "LL97"
    BERDO = "BERDO"
    EPBD = "EPBD"
    ASHRAE_90_1 = "ASHRAE 90.1"


class ReportFormat(Enum):
    """Supported sustainability report output formats."""

    JSON = "json"
    CSV = "csv"
    HTML = "html"


@dataclass
class MaterialData:
    """Material quantity data extracted from building elements."""

    name: str
    category: str
    volume_m3: float = 0.0
    area_m2: float = 0.0
    mass_kg: float = 0.0
    density_kg_m3: float | None = None
    element_id: str | None = None
    level: str | None = None
    system: str | None = None


@dataclass
class EpdRecord:
    """Environmental Product Declaration record for a material."""

    material_name: str
    category: str
    gwp_per_kg: float
    gwp_per_m3: float | None = None
    source: str = "generic"
    lifecycle_stages: list[LifecycleStage] = field(default_factory=list)
    valid_until: str | None = None
    manufacturer: str | None = None


@dataclass
class CarbonResult:
    """Result of embodied carbon calculation for a single material."""

    material: MaterialData
    epd: EpdRecord
    embodied_carbon_kgco2e: float
    lifecycle_stages: list[LifecycleStage] = field(default_factory=list)
    calculation_method: str = "mass_based"


@dataclass
class BuildingCarbonSummary:
    """Aggregated embodied carbon summary for an entire building."""

    total_embodied_carbon_kgco2e: float
    by_material: dict[str, float] = field(default_factory=dict)
    by_system: dict[str, float] = field(default_factory=dict)
    by_level: dict[str, float] = field(default_factory=dict)
    by_lifecycle_stage: dict[str, float] = field(default_factory=dict)
    material_count: int = 0
    calculation_date: str = ""


@dataclass
class ComplianceResult:
    """Result of a compliance check against a building standard."""

    standard: ComplianceStandard
    passed: bool
    threshold: float
    actual_value: float
    unit: str
    recommendations: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnergyEnvelopeData:
    """Building envelope thermal performance data."""

    wall_r_value: float
    roof_r_value: float
    window_u_value: float
    glazing_ratio: float
    air_tightness: float | None = None


@dataclass
class CarbonBenchmark:
    """Benchmark comparison of building embodied carbon performance."""

    actual_kgco2e_per_m2: float
    target_kgco2e_per_m2: float
    benchmark_source: str
    rating: str
    percentile: float | None = None
