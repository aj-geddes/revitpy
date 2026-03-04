"""
Pytest configuration and fixtures for sustainability tests.
"""

from __future__ import annotations

import pytest

from revitpy.sustainability.types import (
    BuildingCarbonSummary,
    CarbonResult,
    EpdRecord,
    LifecycleStage,
    MaterialData,
)


@pytest.fixture
def sample_materials() -> list[MaterialData]:
    """Fixture providing sample material data for testing."""
    return [
        MaterialData(
            name="Concrete",
            category="Structure",
            volume_m3=500.0,
            area_m2=1200.0,
            mass_kg=1200000.0,
            density_kg_m3=2400.0,
            element_id="E001",
            level="Level 1",
            system="Structure",
        ),
        MaterialData(
            name="Steel",
            category="Structure",
            volume_m3=20.0,
            area_m2=300.0,
            mass_kg=157000.0,
            density_kg_m3=7850.0,
            element_id="E002",
            level="Level 1",
            system="Structure",
        ),
        MaterialData(
            name="Timber",
            category="Framing",
            volume_m3=80.0,
            area_m2=400.0,
            mass_kg=40000.0,
            density_kg_m3=500.0,
            element_id="E003",
            level="Level 2",
            system="Framing",
        ),
        MaterialData(
            name="Glass",
            category="Glazing",
            volume_m3=5.0,
            area_m2=200.0,
            mass_kg=12500.0,
            density_kg_m3=2500.0,
            element_id="E004",
            level="Level 1",
            system="Envelope",
        ),
        MaterialData(
            name="Brick",
            category="Masonry",
            volume_m3=100.0,
            area_m2=600.0,
            mass_kg=180000.0,
            density_kg_m3=1800.0,
            element_id="E005",
            level="Level 1",
            system="Envelope",
        ),
    ]


@pytest.fixture
def sample_epd_records() -> list[EpdRecord]:
    """Fixture providing sample EPD records for testing."""
    return [
        EpdRecord(
            material_name="Concrete",
            category="Concrete",
            gwp_per_kg=0.13,
            gwp_per_m3=312.0,
            source="generic-ice",
            lifecycle_stages=[
                LifecycleStage.A1_RAW_MATERIALS,
                LifecycleStage.A2_TRANSPORT,
                LifecycleStage.A3_MANUFACTURING,
            ],
        ),
        EpdRecord(
            material_name="Steel",
            category="Metals",
            gwp_per_kg=1.55,
            gwp_per_m3=12167.5,
            source="generic-ice",
            lifecycle_stages=[
                LifecycleStage.A1_RAW_MATERIALS,
                LifecycleStage.A2_TRANSPORT,
                LifecycleStage.A3_MANUFACTURING,
            ],
        ),
        EpdRecord(
            material_name="Timber",
            category="Wood",
            gwp_per_kg=0.45,
            gwp_per_m3=225.0,
            source="generic-ice",
            lifecycle_stages=[
                LifecycleStage.A1_RAW_MATERIALS,
                LifecycleStage.A2_TRANSPORT,
                LifecycleStage.A3_MANUFACTURING,
            ],
        ),
    ]


@pytest.fixture
def sample_carbon_results(
    sample_materials,
    sample_epd_records,
) -> list[CarbonResult]:
    """Fixture providing sample carbon results for testing."""
    stages = [
        LifecycleStage.A1_RAW_MATERIALS,
        LifecycleStage.A2_TRANSPORT,
        LifecycleStage.A3_MANUFACTURING,
    ]
    return [
        CarbonResult(
            material=sample_materials[0],
            epd=sample_epd_records[0],
            embodied_carbon_kgco2e=156000.0,
            lifecycle_stages=stages,
            calculation_method="mass_based",
        ),
        CarbonResult(
            material=sample_materials[1],
            epd=sample_epd_records[1],
            embodied_carbon_kgco2e=243350.0,
            lifecycle_stages=stages,
            calculation_method="mass_based",
        ),
        CarbonResult(
            material=sample_materials[2],
            epd=sample_epd_records[2],
            embodied_carbon_kgco2e=18000.0,
            lifecycle_stages=stages,
            calculation_method="mass_based",
        ),
    ]


@pytest.fixture
def sample_building_summary(
    sample_carbon_results,
) -> BuildingCarbonSummary:
    """Fixture providing a sample building carbon summary."""
    return BuildingCarbonSummary(
        total_embodied_carbon_kgco2e=417350.0,
        by_material={
            "Concrete": 156000.0,
            "Steel": 243350.0,
            "Timber": 18000.0,
        },
        by_system={
            "Structure": 399350.0,
            "Framing": 18000.0,
        },
        by_level={
            "Level 1": 399350.0,
            "Level 2": 18000.0,
        },
        by_lifecycle_stage={
            "A1": 139116.67,
            "A2": 139116.67,
            "A3": 139116.67,
        },
        material_count=3,
        calculation_date="2025-01-15T00:00:00+00:00",
    )


@pytest.fixture
def sample_building_data() -> dict:
    """Fixture providing sample building data for compliance checks."""
    return {
        "area_sqft": 50000.0,
        "area_m2": 4645.0,
        "annual_emissions_tco2e": 300.0,
        "annual_emissions_kgco2e": 200000.0,
        "primary_energy_kwh": 500000.0,
        "occupancy_type": "office",
        "building_type": "office",
        "wall_r_value": 15.0,
        "roof_r_value": 30.0,
        "window_u_value": 0.30,
        "glazing_ratio": 0.35,
    }
