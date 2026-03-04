"""
Embodied carbon calculation engine.

This module provides the core carbon calculation logic, including
per-material calculation, building-level summarization, and
benchmarking against industry targets.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime

from loguru import logger

from .epd import EpdDatabase
from .exceptions import CarbonCalculationError
from .types import (
    BuildingCarbonSummary,
    CarbonBenchmark,
    CarbonResult,
    EpdRecord,
    LifecycleStage,
    MaterialData,
)

# Default lifecycle stages for A1-A3 (product stage).
_DEFAULT_STAGES: list[LifecycleStage] = [
    LifecycleStage.A1_RAW_MATERIALS,
    LifecycleStage.A2_TRANSPORT,
    LifecycleStage.A3_MANUFACTURING,
]

# RIBA 2030 Climate Challenge benchmarks (kgCO2e/m2).
_RIBA_TARGETS: dict[str, float] = {
    "residential": 300.0,
    "office": 350.0,
    "school": 300.0,
    "retail": 350.0,
    "industrial": 400.0,
    "default": 350.0,
}


class CarbonCalculator:
    """Calculates embodied carbon for building materials.

    Uses an EPD database to resolve GWP factors and computes embodied
    carbon on a mass or volume basis.
    """

    def __init__(
        self,
        epd_database: EpdDatabase | None = None,
    ) -> None:
        self._epd_db = epd_database or EpdDatabase()
        logger.debug("CarbonCalculator initialized")

    def calculate(
        self,
        materials: list[MaterialData],
        lifecycle_stages: list[LifecycleStage] | None = None,
    ) -> list[CarbonResult]:
        """Calculate embodied carbon for a list of materials.

        For each material the calculator looks up an EPD record and
        computes embodied carbon as mass * gwp_per_kg (preferred) or
        volume * gwp_per_m3 when mass is unavailable.

        Args:
            materials: List of MaterialData to calculate for.
            lifecycle_stages: Lifecycle stages to include. Defaults to
                A1-A3 (product stage).

        Returns:
            List of CarbonResult instances.

        Raises:
            CarbonCalculationError: When calculation fails for a material.
        """
        stages = lifecycle_stages or _DEFAULT_STAGES
        results: list[CarbonResult] = []

        for mat in materials:
            epd = self._epd_db.lookup(mat.name, mat.category)
            if epd is None:
                logger.warning(
                    "No EPD found for '{}', skipping",
                    mat.name,
                )
                continue

            try:
                carbon, method = self._compute_carbon(mat, epd)
            except Exception as exc:
                raise CarbonCalculationError(
                    f"Calculation failed for '{mat.name}': {exc}",
                    material_name=mat.name,
                    cause=exc,
                ) from exc

            result = CarbonResult(
                material=mat,
                epd=epd,
                embodied_carbon_kgco2e=carbon,
                lifecycle_stages=stages,
                calculation_method=method,
            )
            results.append(result)
            logger.trace(
                "Carbon for '{}': {:.2f} kgCO2e ({})",
                mat.name,
                carbon,
                method,
            )

        logger.info(
            "Calculated carbon for {} of {} materials",
            len(results),
            len(materials),
        )
        return results

    def summarize(
        self,
        results: list[CarbonResult],
    ) -> BuildingCarbonSummary:
        """Aggregate carbon results into a building-level summary.

        Args:
            results: List of CarbonResult to aggregate.

        Returns:
            BuildingCarbonSummary with totals by material, system,
            level, and lifecycle stage.
        """
        total = 0.0
        by_material: dict[str, float] = defaultdict(float)
        by_system: dict[str, float] = defaultdict(float)
        by_level: dict[str, float] = defaultdict(float)
        by_stage: dict[str, float] = defaultdict(float)

        for r in results:
            carbon = r.embodied_carbon_kgco2e
            total += carbon
            by_material[r.material.name] += carbon

            system_key = r.material.system or "Unassigned"
            by_system[system_key] += carbon

            level_key = r.material.level or "Unassigned"
            by_level[level_key] += carbon

            for stage in r.lifecycle_stages:
                by_stage[stage.value] += carbon / len(r.lifecycle_stages)

        now = datetime.now(tz=UTC).isoformat()

        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=round(total, 2),
            by_material=dict(by_material),
            by_system=dict(by_system),
            by_level=dict(by_level),
            by_lifecycle_stage=dict(by_stage),
            material_count=len(results),
            calculation_date=now,
        )

        logger.info(
            "Building carbon summary: {:.2f} kgCO2e total, {} materials",
            total,
            len(results),
        )
        return summary

    def benchmark(
        self,
        summary: BuildingCarbonSummary,
        building_area_m2: float,
        building_type: str = "default",
    ) -> CarbonBenchmark:
        """Benchmark building carbon against RIBA 2030 targets.

        Args:
            summary: Building carbon summary to benchmark.
            building_area_m2: Gross floor area in square meters.
            building_type: Building type for target selection (e.g.
                "residential", "office").

        Returns:
            CarbonBenchmark with actual vs target comparison.
        """
        if building_area_m2 <= 0:
            raise CarbonCalculationError(
                "Building area must be positive",
                material_name=None,
            )

        actual = summary.total_embodied_carbon_kgco2e / building_area_m2
        target = _RIBA_TARGETS.get(building_type.lower(), _RIBA_TARGETS["default"])

        ratio = actual / target if target > 0 else float("inf")

        if ratio <= 0.5:
            rating = "Excellent"
            percentile = 95.0
        elif ratio <= 0.75:
            rating = "Good"
            percentile = 75.0
        elif ratio <= 1.0:
            rating = "Acceptable"
            percentile = 50.0
        elif ratio <= 1.25:
            rating = "Below Average"
            percentile = 25.0
        else:
            rating = "Poor"
            percentile = 10.0

        benchmark = CarbonBenchmark(
            actual_kgco2e_per_m2=round(actual, 2),
            target_kgco2e_per_m2=target,
            benchmark_source="RIBA 2030 Climate Challenge",
            rating=rating,
            percentile=percentile,
        )

        logger.info(
            "Benchmark: {:.1f} kgCO2e/m2 vs {:.1f} target -> {}",
            actual,
            target,
            rating,
        )
        return benchmark

    async def calculate_async(
        self,
        materials: list[MaterialData],
        lifecycle_stages: list[LifecycleStage] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> list[CarbonResult]:
        """Asynchronously calculate embodied carbon for materials.

        Runs the calculation in a thread executor and reports progress
        through an optional callback.

        Args:
            materials: List of MaterialData to calculate for.
            lifecycle_stages: Lifecycle stages to include.
            progress: Optional callback ``(completed, total)`` for progress
                reporting.

        Returns:
            List of CarbonResult instances.
        """
        stages = lifecycle_stages or _DEFAULT_STAGES
        results: list[CarbonResult] = []
        total = len(materials)

        for idx, mat in enumerate(materials):
            epd = self._epd_db.lookup(mat.name, mat.category)
            if epd is None:
                if progress:
                    progress(idx + 1, total)
                continue

            try:
                carbon, method = self._compute_carbon(mat, epd)
            except Exception as exc:
                raise CarbonCalculationError(
                    f"Async calculation failed for '{mat.name}': {exc}",
                    material_name=mat.name,
                    cause=exc,
                ) from exc

            result = CarbonResult(
                material=mat,
                epd=epd,
                embodied_carbon_kgco2e=carbon,
                lifecycle_stages=stages,
                calculation_method=method,
            )
            results.append(result)

            if progress:
                progress(idx + 1, total)

            # Yield control to the event loop periodically.
            if (idx + 1) % 50 == 0:
                await asyncio.sleep(0)

        return results

    @staticmethod
    def _compute_carbon(
        material: MaterialData,
        epd: EpdRecord,
    ) -> tuple[float, str]:
        """Compute embodied carbon for a single material/EPD pair.

        Prefers mass-based calculation. Falls back to volume-based when
        mass is zero but volume and gwp_per_m3 are available.

        Returns:
            Tuple of (carbon_kgco2e, calculation_method).
        """
        if material.mass_kg > 0 and epd.gwp_per_kg > 0:
            carbon = material.mass_kg * epd.gwp_per_kg
            return round(carbon, 4), "mass_based"

        if material.volume_m3 > 0 and epd.gwp_per_m3 is not None and epd.gwp_per_m3 > 0:
            carbon = material.volume_m3 * epd.gwp_per_m3
            return round(carbon, 4), "volume_based"

        return 0.0, "no_data"
