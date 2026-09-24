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
    # Limits: NYC Admin. Code §28-320.3.1 (2024-2029) / §28-320.3.2 (2030-2034);
    # ESPM factors: 1 RCNY §103-14(c)(3).

    def test_ll97_pass(self, checker):
        """Office (group B) at 0.005 tCO2e/sf passes the 2024-2029 limit."""
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 500.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data, year=2025)

        assert isinstance(result, ComplianceResult)
        assert result.standard == ComplianceStandard.LL97
        assert result.threshold == pytest.approx(0.00846)
        assert result.passed is True

    def test_ll97_fail(self, checker):
        """Test LL97 compliance with failing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 1000.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data, year=2025)

        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_ll97_residential_limit(self, checker):
        """'residential' maps to group R-2 (0.00675 for 2024-2029)."""
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 600.0,
            "occupancy_type": "residential",
        }
        result = checker.check_ll97(data, year=2025)

        assert result.details["occupancy_type"] == "R-2"
        assert result.threshold == pytest.approx(0.00675)
        assert result.passed is True
        assert any("interpreted as occupancy group R-2" in n for n in result.notes)

    def test_ll97_zero_area_raises(self, checker):
        """Test LL97 raises error for zero building area."""
        data = {
            "area_sqft": 0.0,
            "annual_emissions_tco2e": 100.0,
            "occupancy_type": "B",
        }
        with pytest.raises(ComplianceError):
            checker.check_ll97(data)

    def test_ll97_includes_details(self, checker):
        """Test LL97 result includes occupancy, period and source."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 300.0,
            "occupancy_type": "office",
        }
        result = checker.check_ll97(data, year=2025)

        assert result.details["occupancy_type"] == "B"
        assert result.details["limit_period"] == "2024-2029"
        assert result.details["compliance_year"] == 2025
        assert "28-320.3.1" in result.source
        assert any("not a compliance determination" in n for n in result.notes)

    def test_ll97_missing_occupancy_raises(self, checker):
        """No silent default occupancy: classification is required."""
        data = {"area_sqft": 50000.0, "annual_emissions_tco2e": 300.0}

        with pytest.raises(ComplianceError) as exc_info:
            checker.check_ll97(data, year=2025)
        assert exc_info.value.requirement == "occupancy_type"

    def test_ll97_unknown_occupancy_raises(self, checker):
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_tco2e": 300.0,
            "occupancy_type": "spaceport",
        }
        with pytest.raises(ComplianceError):
            checker.check_ll97(data, year=2025)

    @pytest.mark.parametrize(
        ("group", "year", "expected"),
        [
            ("A", 2024, 0.01074),
            ("B", 2029, 0.00846),
            ("B-healthcare", 2025, 0.02381),
            ("E", 2025, 0.00758),
            ("I-1", 2025, 0.01138),
            ("F", 2025, 0.00574),
            ("M", 2025, 0.01181),
            ("R-1", 2025, 0.00987),
            ("R-2", 2025, 0.00675),
            ("S", 2025, 0.00426),
            ("A", 2030, 0.00420),
            ("B", 2030, 0.00453),
            ("B-healthcare", 2034, 0.01330),
            ("E", 2030, 0.00344),
            ("I-1", 2030, 0.00598),
            ("F", 2030, 0.00167),
            ("M", 2030, 0.00403),
            ("R-1", 2030, 0.00526),
            ("R-2", 2030, 0.00407),
            ("U", 2030, 0.00110),
        ],
    )
    def test_ll97_group_limits_by_period(self, checker, group, year, expected):
        data = {
            "area_sqft": 10000.0,
            "annual_emissions_tco2e": 1.0,
            "occupancy_type": group,
        }
        result = checker.check_ll97(data, year=year)

        assert result.threshold == pytest.approx(expected)
        expected_period = "2024-2029" if year <= 2029 else "2030-2034"
        assert result.details["limit_period"] == expected_period

    def test_ll97_period_from_building_data_year(self, checker):
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 500.0,
            "occupancy_type": "B",
            "compliance_year": 2031,
        }
        result = checker.check_ll97(data)

        assert result.details["limit_period"] == "2030-2034"
        # 0.005 > 0.00453 in the second period.
        assert result.passed is False

    @pytest.mark.parametrize(
        ("property_type", "year", "expected"),
        [
            ("Office", 2026, 0.00758),
            ("multifamily housing", 2026, 0.00675),
            ("Hotel", 2027, 0.00987),
            ("Office", 2032, 0.002690852),
            ("Multifamily Housing", 2030, 0.003346640),
            ("K-12 School", 2031, 0.002230588),
        ],
    )
    def test_ll97_espm_property_type(self, checker, property_type, year, expected):
        data = {
            "area_sqft": 10000.0,
            "annual_emissions_tco2e": 1.0,
            "property_type": property_type,
        }
        result = checker.check_ll97(data, year=year)

        assert result.threshold == pytest.approx(expected)
        assert result.details["classification_basis"] == "espm_property_type"
        assert not any("2026 reporting onward" in n for n in result.notes)

    def test_ll97_unknown_property_type_raises(self, checker):
        data = {
            "area_sqft": 10000.0,
            "annual_emissions_tco2e": 1.0,
            "property_type": "Moon Base",
        }
        with pytest.raises(ComplianceError):
            checker.check_ll97(data, year=2026)

    def test_ll97_occupancy_group_after_2025_warns(self, checker):
        data = {
            "area_sqft": 10000.0,
            "annual_emissions_tco2e": 1.0,
            "occupancy_type": "B",
        }
        result = checker.check_ll97(data, year=2026)

        assert any("2026 reporting onward" in n for n in result.notes)

    @pytest.mark.parametrize(
        ("year", "period", "fragment"),
        [
            (2020, "2024-2029", "begin with calendar year 2024"),
            (2040, "2030-2034", "optimistic"),
        ],
    )
    def test_ll97_year_outside_periods_warns(self, checker, year, period, fragment):
        data = {
            "area_sqft": 10000.0,
            "annual_emissions_tco2e": 1.0,
            "property_type": "Office",
        }
        result = checker.check_ll97(data, year=year)

        assert result.details["limit_period"] == period
        assert any(fragment in n for n in result.notes)

    def test_ll97_limit_override(self, checker):
        data = {
            "area_sqft": 100000.0,
            "annual_emissions_tco2e": 500.0,
            "occupancy_type": "B",
        }
        result = checker.check_ll97(data, year=2025, limits={"B": 0.004})

        assert result.threshold == pytest.approx(0.004)
        assert result.passed is False
        assert result.details["limit_source"] == "caller-supplied"
        assert result.source == "caller-supplied"

    # --- BERDO Tests (built-in values are unverified placeholders) ---

    def test_berdo_pass(self, checker):
        """Test BERDO screening with passing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 200000.0,
            "building_type": "office",
        }
        result = checker.check_berdo(data)

        assert result.standard == ComplianceStandard.BERDO
        assert result.passed is True
        assert "unverified" in result.source
        assert any("unverified" in n for n in result.notes)

    def test_berdo_fail(self, checker):
        """Test BERDO screening with failing emissions."""
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 500000.0,
            "building_type": "office",
        }
        result = checker.check_berdo(data)

        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_berdo_zero_area_raises(self, checker):
        """Test BERDO raises error for zero building area."""
        data = {
            "area_sqft": 0.0,
            "annual_emissions_kgco2e": 100000.0,
            "building_type": "office",
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

        assert result.passed is True

    def test_berdo_requires_building_type(self, checker):
        data = {"area_sqft": 50000.0, "annual_emissions_kgco2e": 1.0}

        with pytest.raises(ComplianceError):
            checker.check_berdo(data)

    def test_berdo_unknown_type_without_limits_raises(self, checker):
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 1.0,
            "building_type": "laboratory",
        }
        with pytest.raises(ComplianceError):
            checker.check_berdo(data)

    def test_berdo_caller_limits(self, checker):
        data = {
            "area_sqft": 50000.0,
            "annual_emissions_kgco2e": 200000.0,
            "building_type": "laboratory",
        }
        result = checker.check_berdo(data, limits={"laboratory": 3.0})

        assert result.threshold == pytest.approx(3.0)
        assert result.passed is False
        assert result.source == "caller-supplied"

    # --- EPBD Tests (no pan-EU cap: limits must be supplied) ---

    NZEB = {"office": 120.0, "residential": 100.0}

    def test_epbd_pass(self, checker):
        """Test EPBD screening against a supplied limit."""
        data = {
            "area_m2": 5000.0,
            "primary_energy_kwh": 400000.0,
            "building_type": "office",
        }
        result = checker.check_epbd(
            data, limits=self.NZEB, limit_source="Example NZEB decree 2021"
        )

        assert result.standard == ComplianceStandard.EPBD
        # 400000 / 5000 = 80 < 120
        assert result.passed is True
        assert result.source == "Example NZEB decree 2021"
        assert any("caller-supplied limit" in n for n in result.notes)
        assert any("no pan-EU" in n for n in result.notes)

    def test_epbd_fail(self, checker):
        """Test EPBD screening with failing energy performance."""
        data = {
            "area_m2": 5000.0,
            "primary_energy_kwh": 1000000.0,
            "building_type": "office",
        }
        result = checker.check_epbd(data, limits=self.NZEB)

        assert result.passed is False
        assert len(result.recommendations) > 0

    def test_epbd_zero_area_raises(self, checker):
        """Test EPBD raises error for zero building area."""
        data = {
            "area_m2": 0.0,
            "primary_energy_kwh": 100000.0,
            "building_type": "office",
        }
        with pytest.raises(ComplianceError):
            checker.check_epbd(data, limits=self.NZEB)

    def test_epbd_residential_limit(self, checker):
        """Test EPBD with residential building type."""
        data = {
            "area_m2": 1000.0,
            "primary_energy_kwh": 90000.0,
            "building_type": "residential",
        }
        result = checker.check_epbd(data, limits=self.NZEB)

        assert result.threshold == pytest.approx(100.0)
        assert result.passed is True

    def test_epbd_without_limits_raises(self, checker):
        """There are no built-in EPBD limits to fall back on."""
        data = {
            "area_m2": 1000.0,
            "primary_energy_kwh": 90000.0,
            "building_type": "office",
        }
        with pytest.raises(ComplianceError) as exc_info:
            checker.check_epbd(data)
        assert exc_info.value.requirement == "limits"
        assert "no pan-EU" in str(exc_info.value)

    def test_epbd_wildcard_limit(self, checker):
        data = {
            "area_m2": 1000.0,
            "primary_energy_kwh": 90000.0,
            "building_type": "hospital",
        }
        result = checker.check_epbd(data, limits={"*": 150.0})

        assert result.threshold == pytest.approx(150.0)

    # --- ASHRAE 90.1-2019 Tests ---

    def test_ashrae_pass(self, checker):
        """Zone 4A: roof R-30 c.i., fixed fenestration U-0.36, WWR 40%."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope, "4A")

        assert result.standard == ComplianceStandard.ASHRAE_90_1
        assert result.passed is True
        assert result.actual_value == pytest.approx(1.0)
        assert result.details["table"] == "Table 5.5-4"
        assert "90.1-2019" in result.source

    def test_ashrae_walls_not_evaluated_without_override(self, checker):
        envelope = EnergyEnvelopeData(
            wall_r_value=1.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope, "4A")

        assert result.passed is True
        assert result.details["not_evaluated"] == ["wall"]
        assert any("Wall requirement not evaluated" in n for n in result.notes)

    def test_ashrae_fail_wall_r_value_with_override(self, checker):
        """Walls are checked against a caller-supplied minimum."""
        envelope = EnergyEnvelopeData(
            wall_r_value=10.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope, "4A", overrides={"wall_r_min": 13.0})

        assert result.passed is False
        assert any("Wall" in r for r in result.recommendations)
        assert result.details["overrides_applied"] == ["wall_r_min"]

    def test_ashrae_fail_window_u_value(self, checker):
        """Test ASHRAE fails with high window U-value."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.50,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope, "4A")

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
        result = checker.check_ashrae(envelope, "4A", overrides={"wall_r_min": 13.0})

        assert result.passed is False
        assert result.actual_value == pytest.approx(0.0)

    @pytest.mark.parametrize(
        ("zone", "roof_min", "window_max"),
        [
            ("0A", 25.0, 0.50),
            ("1A", 20.0, 0.50),
            ("2B", 25.0, 0.45),
            ("3C", 25.0, 0.42),
            ("4A", 30.0, 0.36),
            ("5A", 30.0, 0.34),
            ("6B", 30.0, 0.34),
            ("7", 35.0, 0.29),
            (8, 35.0, 0.26),
        ],
    )
    def test_ashrae_limits_by_climate_zone(self, checker, zone, roof_min, window_max):
        envelope = EnergyEnvelopeData(
            wall_r_value=20.0,
            roof_r_value=roof_min,
            window_u_value=window_max,
            glazing_ratio=0.40,
        )
        result = checker.check_ashrae(envelope, zone)

        assert result.details["roof_r_min"] == pytest.approx(roof_min)
        assert result.details["window_u_max"] == pytest.approx(window_max)
        assert result.details["glazing_ratio_max"] == pytest.approx(0.40)
        assert result.passed is True

    def test_ashrae_zone_7_roof_stricter_than_4(self, checker):
        envelope = EnergyEnvelopeData(
            wall_r_value=20.0,
            roof_r_value=30.0,
            window_u_value=0.25,
            glazing_ratio=0.30,
        )
        assert checker.check_ashrae(envelope, "4A").passed is True
        assert checker.check_ashrae(envelope, "7").passed is False

    @pytest.mark.parametrize("zone", ["9A", "4D", "", "four", -1, True])
    def test_ashrae_unsupported_zone_raises(self, checker, zone):
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        with pytest.raises(ComplianceError) as exc_info:
            checker.check_ashrae(envelope, zone)
        assert exc_info.value.requirement == "climate_zone"

    def test_ashrae_unknown_override_raises(self, checker):
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        with pytest.raises(ComplianceError):
            checker.check_ashrae(envelope, "4A", overrides={"door_u_max": 0.5})

    def test_ashrae_includes_details(self, checker):
        """Test ASHRAE result includes envelope performance details."""
        envelope = EnergyEnvelopeData(
            wall_r_value=15.0,
            roof_r_value=30.0,
            window_u_value=0.30,
            glazing_ratio=0.35,
        )
        result = checker.check_ashrae(envelope, "4A")

        assert "wall_r_value" in result.details
        assert "roof_r_value" in result.details
        assert "window_u_value" in result.details
        assert "glazing_ratio" in result.details
        assert result.details["climate_zone"] == "4A"

    def test_ashrae_dict_requires_climate_zone(self, checker, sample_building_data):
        data = dict(sample_building_data)
        del data["climate_zone"]

        with pytest.raises(ComplianceError) as exc_info:
            checker.check(ComplianceStandard.ASHRAE_90_1, data)
        assert exc_info.value.requirement == "climate_zone"

    def test_ashrae_dict_requires_envelope_values(self, checker, sample_building_data):
        data = dict(sample_building_data)
        del data["window_u_value"]

        with pytest.raises(ComplianceError):
            checker.check(ComplianceStandard.ASHRAE_90_1, data)

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
