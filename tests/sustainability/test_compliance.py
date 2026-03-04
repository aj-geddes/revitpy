"""
Unit tests for ComplianceChecker functionality.
"""

from __future__ import annotations

import pytest

from revitpy.sustainability.compliance import ComplianceChecker
from revitpy.sustainability.exceptions import ComplianceError
from revitpy.sustainability.types import (
    ComplianceResult,
    ComplianceStandard,
    EnergyEnvelopeData,
)


@pytest.fixture
def checker() -> ComplianceChecker:
    """Fixture providing a ComplianceChecker instance."""
    return ComplianceChecker()


class TestComplianceChecker:
    """Tests for ComplianceChecker."""

    # --- LL97 Tests ---

    def test_ll97_pass(self, checker):
        """Test LL97 compliance with passing emissions."""
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 500.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data)

        assert isinstance(result, ComplianceResult)
        assert result.standard == ComplianceStandard.LL97
        # 500 / 100000 = 0.005 < 0.00846
        assert result.passed is True

    def test_ll97_fail(self, checker):
        """Test LL97 compliance with failing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 1000.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data)

        # 1000 / 50000 = 0.02 > 0.00846
        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_ll97_residential_limit(self, checker):
        """Test LL97 with residential occupancy type."""
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 600.0,
            "occupancy_type": "residential",
        }
        result = checker.check_ll97(data)

        # 600 / 100000 = 0.006 < 0.00675
        assert result.passed is True

    def test_ll97_zero_area_raises(self, checker):
        """Test LL97 raises error for zero building area."""
        data = {
            "area_sqft": 0.0,
            "annual_emissions_tco2e": 100.0,
        }
        with pytest.raises(ComplianceError):
            checker.check_ll97(data)

    def test_ll97_includes_details(self, checker):
        """Test LL97 result includes occupancy and period details."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 300.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data)

        assert "occupancy_type" in result.details
        assert "limit_period" in result.details

    def test_ll97_default_occupancy(self, checker):
        """Test LL97 uses default occupancy when not specified."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 300.0,
        }
        result = checker.check_ll97(data)

        assert result.details["occupancy_type"] == "default"

    # --- BERDO Tests ---

    def test_berdo_pass(self, checker):
        """Test BERDO compliance with passing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 200000.0,
            "building_type": "office",
        }
        result = checker.check_berdo(data)

        assert result.standard == ComplianceStandard.BERDO
        # 200000 / 50000 = 4.0 < 5.4
        assert result.passed is True

    def test_berdo_fail(self, checker):
        """Test BERDO compliance with failing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 500000.0,
            "building_type": "office",
        }
        result = checker.check_berdo(data)

        # 500000 / 50000 = 10.0 > 5.4
        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_berdo_zero_area_raises(self, checker):
        """Test BERDO raises error for zero building area."""
        data = {
            "area_sqft": 0.0,
            "annual_emissions_kgco2e": 100000.0,
        }
        with pytest.raises(ComplianceError):
            checker.check_berdo(data)

    def test_berdo_residential_limit(self, checker):
        """Test BERDO with residential building type."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 150000.0,
            "building_type": "residential",
        }
        result = checker.check_berdo(data)

        # 150000 / 50000 = 3.0 < 3.6
        assert result.passed is True

    # --- EPBD Tests ---

    def test_epbd_pass(self, checker):
        """Test EPBD compliance with passing energy performance."""
        data = {
            "area_m2": 5000.0,
            "primary_energy_kwh": 400000.0,
            "building_type": "office",
        }
        result = checker.check_epbd(data)

        assert result.standard == ComplianceStandard.EPBD
        # 400000 / 5000 = 80 < 120
        assert result.passed is True

    def test_epbd_fail(self, checker):
        """Test EPBD compliance with failing energy performance."""
        data = {
            "area_m2": 5000.0,
            "primary_energy_kwh": 1000000.0,
            "building_type": "office",
        }
        result = checker.check_epbd(data)

        # 1000000 / 5000 = 200 > 120
        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_epbd_zero_area_raises(self, checker):
        """Test EPBD raises error for zero building area."""
        data = {
            "area_m2": 0.0,
            "primary_energy_kwh": 100000.0,
        }
        with pytest.raises(ComplianceError):
            checker.check_epbd(data)

    def test_epbd_residential_limit(self, checker):
        """Test EPBD with residential building type."""
        data = {
            "area_m2": 1000.0,
            "primary_energy_kwh": 90000.0,
            "building_type": "residential",
        }
        result = checker.check_epbd(data)

        # 90000 / 1000 = 90 < 100
        assert result.passed is True

    # --- ASHRAE 90.1 Tests ---

    def test_ashrae_pass(self, checker):
        """Test ASHRAE 90.1 compliance with passing envelope."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope)

        assert result.standard == ComplianceStandard.ASHRAE_90_1
        assert result.passed is True
        assert result.actual_value == pytest.approx(1.0)

    def test_ashrae_fail_wall_r_value(self, checker):
        """Test ASHRAE fails with low wall R-value."""
        envelope = EnergyEnvelopeData(
            wall_r_value=10.0,  # Below 13.0 minimum
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope)

        assert result.passed is False
        assert any("Wall" in r for r in result.recommendations)

    def test_ashrae_fail_window_u_value(self, checker):
        """Test ASHRAE fails with high window U-value."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.50,  # Above 0.38 maximum
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope)

        assert result.passed is False
        assert any("Window" in r for r in result.recommendations)

    def test_ashrae_fail_multiple_criteria(self, checker):
        """Test ASHRAE with multiple failing criteria."""
        envelope = EnergyEnvelopeData(
            wall_r_value=10.0,
            roof_r_value=20.0,
            window_u_value=0.50,
            glazing_ratio=0.50,
        )
        result = checker.check_ashrae(envelope)

        assert result.passed is False
        # 0 of 4 criteria pass -> score = 0
        assert result.actual_value == pytest.approx(0.0)

    def test_ashrae_includes_details(self, checker):
        """Test ASHRAE result includes envelope performance details."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope)

        assert "wall_r_value" in result.details
        assert "roof_r_value" in result.details
        assert "window_u_value" in result.details
        assert "glazing_ratio" in result.details

    # --- Dispatch Tests ---

    def test_check_dispatches_ll97(self, checker, sample_building_data):
        """Test that check() dispatches to LL97."""
        result = checker.check(ComplianceStandard.LL97, sample_building_data)

        assert result.standard == ComplianceStandard.LL97

    def test_check_dispatches_berdo(self, checker, sample_building_data):
        """Test that check() dispatches to BERDO."""
        result = checker.check(ComplianceStandard.BERDO, sample_building_data)

        assert result.standard == ComplianceStandard.BERDO

    def test_check_dispatches_epbd(self, checker, sample_building_data):
        """Test that check() dispatches to EPBD."""
        result = checker.check(ComplianceStandard.EPBD, sample_building_data)

        assert result.standard == ComplianceStandard.EPBD

    def test_check_dispatches_ashrae(self, checker, sample_building_data):
        """Test that check() dispatches to ASHRAE 90.1."""
        result = checker.check(ComplianceStandard.ASHRAE_90_1, sample_building_data)

        assert result.standard == ComplianceStandard.ASHRAE_90_1

    # --- Recommendations Tests ---

    def test_get_recommendations_for_passing_result(self, checker):
        """Test recommendations for a passing result."""
        result = ComplianceResult(
            standard=ComplianceStandard.LL97,
            passed=True,
            threshold=0.00846,
            actual_value=0.005,
            unit="tCO2e/sqft/year",
        )
        recs = checker.get_recommendations(result)

        assert len(recs) >= 1
        assert "achieved" in recs[0].lower() or "exceed" in recs[0].lower()

    def test_get_recommendations_for_failing_result(self, checker):
        """Test recommendations for a failing result."""
        result = ComplianceResult(
            standard=ComplianceStandard.LL97,
            passed=False,
            threshold=0.00846,
            actual_value=0.02,
            unit="tCO2e/sqft/year",
            recommendations=["Reduce emissions"],
        )
        recs = checker.get_recommendations(result)

        assert len(recs) > 1

    def test_get_recommendations_no_duplicates(self, checker):
        """Test that recommendations have no duplicates."""
        result = ComplianceResult(
            standard=ComplianceStandard.BERDO,
            passed=False,
            threshold=5.4,
            actual_value=10.0,
            unit="kgCO2e/sqft/year",
            recommendations=["Improve insulation"],
        )
        recs = checker.get_recommendations(result)

        assert len(recs) == len(set(recs))
