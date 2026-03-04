"""
Unit tests for CarbonCalculator functionality.
"""

from __future__ import annotations

import pytest

from revitpy.sustainability.carbon import CarbonCalculator
from revitpy.sustainability.epd import EpdDatabase
from revitpy.sustainability.exceptions import CarbonCalculationError
from revitpy.sustainability.types import (
    BuildingCarbonSummary,
    CarbonBenchmark,
    CarbonResult,
    LifecycleStage,
    MaterialData,
)


@pytest.fixture
def calculator() -> CarbonCalculator:
    """Fixture providing a CarbonCalculator with default EPD database."""
    return CarbonCalculator()


class TestCarbonCalculator:
    """Tests for CarbonCalculator."""

    def test_calculate_returns_results(self, calculator, sample_materials):
        """Test that calculation returns a list of CarbonResult."""
        results = calculator.calculate(sample_materials)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, CarbonResult) for r in results)

    def test_calculate_mass_based(self, calculator):
        """Test mass-based carbon calculation accuracy."""
        materials = [
            MaterialData(
                name="Concrete",
                category="Structure",
                mass_kg=1000.0,
            ),
        ]
        results = calculator.calculate(materials)

        assert len(results) == 1
        # 1000 kg * 0.13 kgCO2e/kg = 130 kgCO2e
        assert results[0].embodied_carbon_kgco2e == pytest.approx(130.0, rel=0.01)
        assert results[0].calculation_method == "mass_based"

    def test_calculate_volume_based(self, calculator):
        """Test volume-based carbon calculation when mass is zero."""
        materials = [
            MaterialData(
                name="Concrete",
                category="Structure",
                volume_m3=1.0,
                mass_kg=0.0,
            ),
        ]
        results = calculator.calculate(materials)

        assert len(results) == 1
        # 1 m3 * 312.0 kgCO2e/m3 = 312 kgCO2e
        assert results[0].embodied_carbon_kgco2e == pytest.approx(312.0, rel=0.01)
        assert results[0].calculation_method == "volume_based"

    def test_calculate_skips_unknown_materials(self, calculator):
        """Test that unknown materials are skipped gracefully."""
        materials = [
            MaterialData(
                name="Unobtanium",
                category="SciFi",
                mass_kg=1000.0,
            ),
        ]
        results = calculator.calculate(materials)

        assert len(results) == 0

    def test_calculate_with_custom_stages(self, calculator):
        """Test calculation with custom lifecycle stages."""
        stages = [LifecycleStage.A1_RAW_MATERIALS]
        materials = [
            MaterialData(
                name="Steel",
                category="Metals",
                mass_kg=100.0,
            ),
        ]
        results = calculator.calculate(materials, lifecycle_stages=stages)

        assert len(results) == 1
        assert results[0].lifecycle_stages == stages

    def test_calculate_default_stages_are_a1_a3(self, calculator):
        """Test that default stages are A1-A3."""
        materials = [
            MaterialData(
                name="Concrete",
                category="Structure",
                mass_kg=100.0,
            ),
        ]
        results = calculator.calculate(materials)

        assert len(results[0].lifecycle_stages) == 3
        assert LifecycleStage.A1_RAW_MATERIALS in results[0].lifecycle_stages
        assert LifecycleStage.A2_TRANSPORT in results[0].lifecycle_stages
        assert LifecycleStage.A3_MANUFACTURING in results[0].lifecycle_stages

    def test_calculate_steel_accuracy(self, calculator):
        """Test steel carbon calculation accuracy."""
        materials = [
            MaterialData(
                name="Steel",
                category="Metals",
                mass_kg=1000.0,
            ),
        ]
        results = calculator.calculate(materials)

        # 1000 kg * 1.55 kgCO2e/kg = 1550 kgCO2e
        assert results[0].embodied_carbon_kgco2e == pytest.approx(1550.0, rel=0.01)

    def test_calculate_timber_accuracy(self, calculator):
        """Test timber carbon calculation accuracy."""
        materials = [
            MaterialData(
                name="Timber",
                category="Wood",
                mass_kg=500.0,
            ),
        ]
        results = calculator.calculate(materials)

        # 500 kg * 0.45 kgCO2e/kg = 225 kgCO2e
        assert results[0].embodied_carbon_kgco2e == pytest.approx(225.0, rel=0.01)

    def test_summarize_total_carbon(self, calculator, sample_carbon_results):
        """Test that summarize computes correct total."""
        summary = calculator.summarize(sample_carbon_results)

        expected_total = sum(r.embodied_carbon_kgco2e for r in sample_carbon_results)
        assert summary.total_embodied_carbon_kgco2e == pytest.approx(
            expected_total, rel=0.01
        )

    def test_summarize_by_material(self, calculator, sample_carbon_results):
        """Test that summarize breaks down by material."""
        summary = calculator.summarize(sample_carbon_results)

        assert "Concrete" in summary.by_material
        assert "Steel" in summary.by_material
        assert "Timber" in summary.by_material

    def test_summarize_by_system(self, calculator, sample_carbon_results):
        """Test that summarize breaks down by system."""
        summary = calculator.summarize(sample_carbon_results)

        assert "Structure" in summary.by_system
        assert "Framing" in summary.by_system

    def test_summarize_by_level(self, calculator, sample_carbon_results):
        """Test that summarize breaks down by level."""
        summary = calculator.summarize(sample_carbon_results)

        assert "Level 1" in summary.by_level
        assert "Level 2" in summary.by_level

    def test_summarize_material_count(self, calculator, sample_carbon_results):
        """Test that summarize reports correct material count."""
        summary = calculator.summarize(sample_carbon_results)

        assert summary.material_count == 3

    def test_summarize_has_calculation_date(self, calculator, sample_carbon_results):
        """Test that summarize includes calculation date."""
        summary = calculator.summarize(sample_carbon_results)

        assert summary.calculation_date != ""

    def test_summarize_empty_results(self, calculator):
        """Test summarize with empty results."""
        summary = calculator.summarize([])

        assert summary.total_embodied_carbon_kgco2e == 0.0
        assert summary.material_count == 0

    def test_benchmark_good_rating(self, calculator):
        """Test benchmark with good carbon intensity."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=200000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        benchmark = calculator.benchmark(
            summary,
            building_area_m2=1000.0,
            building_type="residential",
        )

        # 200000 / 1000 = 200 kgCO2e/m2, target 300 -> ratio 0.667 -> Good
        assert isinstance(benchmark, CarbonBenchmark)
        assert benchmark.actual_kgco2e_per_m2 == pytest.approx(200.0)
        assert benchmark.target_kgco2e_per_m2 == pytest.approx(300.0)
        assert benchmark.rating == "Good"

    def test_benchmark_acceptable_rating(self, calculator):
        """Test benchmark with acceptable carbon intensity."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=250000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        benchmark = calculator.benchmark(
            summary,
            building_area_m2=1000.0,
            building_type="residential",
        )

        # 250000 / 1000 = 250 kgCO2e/m2, target 300 -> ratio 0.833 -> Acceptable
        assert isinstance(benchmark, CarbonBenchmark)
        assert benchmark.actual_kgco2e_per_m2 == pytest.approx(250.0)
        assert benchmark.target_kgco2e_per_m2 == pytest.approx(300.0)
        assert benchmark.rating == "Acceptable"

    def test_benchmark_excellent_rating(self, calculator):
        """Test benchmark with excellent carbon intensity."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=100000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        benchmark = calculator.benchmark(
            summary,
            building_area_m2=1000.0,
            building_type="residential",
        )

        # 100 kgCO2e/m2 vs 300 target -> Excellent
        assert benchmark.rating == "Excellent"
        assert benchmark.percentile == 95.0

    def test_benchmark_poor_rating(self, calculator):
        """Test benchmark with poor carbon intensity."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=500000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        benchmark = calculator.benchmark(
            summary,
            building_area_m2=1000.0,
            building_type="residential",
        )

        # 500 kgCO2e/m2 vs 300 target -> Poor
        assert benchmark.rating == "Poor"

    def test_benchmark_zero_area_raises(self, calculator):
        """Test that zero area raises an error."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=100000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        with pytest.raises(CarbonCalculationError):
            calculator.benchmark(summary, building_area_m2=0.0)

    def test_benchmark_source(self, calculator):
        """Test benchmark source attribution."""
        summary = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=300000.0,
            material_count=5,
            calculation_date="2025-01-01",
        )
        benchmark = calculator.benchmark(summary, building_area_m2=1000.0)

        assert "RIBA" in benchmark.benchmark_source

    @pytest.mark.asyncio
    async def test_calculate_async(self, calculator, sample_materials):
        """Test async carbon calculation."""
        results = await calculator.calculate_async(sample_materials)

        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_calculate_async_with_progress(self, calculator, sample_materials):
        """Test async calculation with progress callback."""
        progress_calls = []

        def on_progress(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        await calculator.calculate_async(sample_materials, progress=on_progress)

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == len(sample_materials)

    def test_calculator_with_custom_epd_database(self):
        """Test calculator with custom EPD database."""
        db = EpdDatabase()
        calc = CarbonCalculator(epd_database=db)

        materials = [
            MaterialData(
                name="Concrete",
                category="Structure",
                mass_kg=1000.0,
            ),
        ]
        results = calc.calculate(materials)

        assert len(results) == 1
