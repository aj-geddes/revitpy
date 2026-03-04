"""
Sustainability and carbon assessment for RevitPy.

This module provides whole-life carbon calculation, EPD management,
building emissions compliance checking, and sustainability reporting
for green building certification workflows.

Key Features:
- Embodied carbon calculation with EPD database integration
- Material extraction and classification (UniFormat, MasterFormat)
- Compliance checking (LL97, BERDO, EPBD, ASHRAE 90.1)
- Report generation (JSON, CSV, HTML)
- Certification documentation helpers (LEED, BREEAM, DGNB, Green Star)

Usage:
    from revitpy.sustainability import (
        CarbonCalculator,
        EpdDatabase,
        calculate_carbon,
    )

    # Quick carbon calculation
    results = calculate_carbon(materials)

    # Full workflow
    epd_db = EpdDatabase()
    calculator = CarbonCalculator(epd_database=epd_db)
    results = calculator.calculate(materials)
    summary = calculator.summarize(results)
"""

from .carbon import CarbonCalculator
from .compliance import ComplianceChecker
from .epd import EpdDatabase
from .exceptions import (
    CarbonCalculationError,
    ComplianceError,
    EpdLookupError,
    ReportGenerationError,
    SustainabilityError,
)
from .materials import MaterialExtractor
from .reports import SustainabilityReporter
from .types import (
    BuildingCarbonSummary,
    CarbonBenchmark,
    CarbonResult,
    CertificationSystem,
    ComplianceResult,
    ComplianceStandard,
    EnergyEnvelopeData,
    EpdRecord,
    LifecycleStage,
    MaterialData,
    ReportFormat,
)


def calculate_carbon(
    materials: list[MaterialData],
    lifecycle_stages: list[LifecycleStage] | None = None,
    epd_database: EpdDatabase | None = None,
) -> list[CarbonResult]:
    """Convenience function to calculate embodied carbon for materials.

    Args:
        materials: List of MaterialData to calculate for.
        lifecycle_stages: Lifecycle stages to include. Defaults to A1-A3.
        epd_database: Optional EPD database instance.

    Returns:
        List of CarbonResult instances.
    """
    calculator = CarbonCalculator(epd_database=epd_database)
    return calculator.calculate(materials, lifecycle_stages)


def check_compliance(
    standard: ComplianceStandard,
    building_data: dict,
) -> ComplianceResult:
    """Convenience function to check building compliance.

    Args:
        standard: The compliance standard to check against.
        building_data: Dictionary containing building performance data.

    Returns:
        ComplianceResult with pass/fail and recommendations.
    """
    checker = ComplianceChecker()
    return checker.check(standard, building_data)


def generate_report(
    summary: BuildingCarbonSummary,
    format: ReportFormat = ReportFormat.JSON,
    output_path: str | None = None,
) -> str:
    """Convenience function to generate a sustainability report.

    Args:
        summary: Building carbon summary data.
        format: Output format (JSON, CSV, or HTML).
        output_path: Optional file path to write to.

    Returns:
        Report content as a string or Path.
    """
    reporter = SustainabilityReporter()
    return reporter.generate(summary, format=format, output_path=output_path)


__all__ = [
    # Core calculators
    "CarbonCalculator",
    "EpdDatabase",
    "MaterialExtractor",
    "ComplianceChecker",
    "SustainabilityReporter",
    # Types and enums
    "LifecycleStage",
    "CertificationSystem",
    "ComplianceStandard",
    "ReportFormat",
    # Dataclasses
    "MaterialData",
    "EpdRecord",
    "CarbonResult",
    "BuildingCarbonSummary",
    "ComplianceResult",
    "EnergyEnvelopeData",
    "CarbonBenchmark",
    # Exceptions
    "SustainabilityError",
    "CarbonCalculationError",
    "EpdLookupError",
    "ComplianceError",
    "ReportGenerationError",
    # Convenience functions
    "calculate_carbon",
    "check_compliance",
    "generate_report",
]
