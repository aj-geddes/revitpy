"""
Building emissions compliance checking.

This module provides compliance verification against major building
emissions standards including NYC Local Law 97, Boston BERDO,
EU EPBD, and ASHRAE 90.1 envelope requirements.
"""

from __future__ import annotations

from loguru import logger

from .exceptions import ComplianceError
from .types import ComplianceResult, ComplianceStandard, EnergyEnvelopeData

# NYC LL97 carbon intensity limits by occupancy (tCO2e/sqft/year, 2024-2029).
_LL97_LIMITS_2024: dict[str, float] = {
    "office": 0.00846,
    "residential": 0.00675,
    "retail": 0.01074,
    "hotel": 0.00987,
    "healthcare": 0.02381,
    "education": 0.00758,
    "warehouse": 0.00574,
    "default": 0.00846,
}

# Boston BERDO emissions standards (kgCO2e/sqft/year).
_BERDO_LIMITS: dict[str, float] = {
    "office": 5.4,
    "residential": 3.6,
    "retail": 6.1,
    "education": 4.8,
    "default": 5.4,
}

# EU EPBD maximum primary energy demand (kWh/m2/year).
_EPBD_LIMITS: dict[str, float] = {
    "residential": 100.0,
    "office": 120.0,
    "retail": 130.0,
    "education": 110.0,
    "default": 120.0,
}

# ASHRAE 90.1-2019 envelope requirements by climate zone 4A (mixed-humid).
_ASHRAE_ENVELOPE: dict[str, float] = {
    "wall_r_min": 13.0,
    "roof_r_min": 25.0,
    "window_u_max": 0.38,
    "glazing_ratio_max": 0.40,
}


class ComplianceChecker:
    """Checks building data against emissions compliance standards.

    Dispatches to standard-specific checkers and provides improvement
    recommendations when checks fail.
    """

    def __init__(self) -> None:
        logger.debug("ComplianceChecker initialized")

    def check(
        self,
        standard: ComplianceStandard,
        building_data: dict,
    ) -> ComplianceResult:
        """Check compliance against a specific standard.

        Args:
            standard: The compliance standard to check against.
            building_data: Dictionary containing building performance data.
                Required keys vary by standard.

        Returns:
            ComplianceResult with pass/fail and recommendations.

        Raises:
            ComplianceError: If the standard is not supported or required
                data is missing.
        """
        dispatch = {
            ComplianceStandard.LL97: self.check_ll97,
            ComplianceStandard.BERDO: self.check_berdo,
            ComplianceStandard.EPBD: self.check_epbd,
            ComplianceStandard.ASHRAE_90_1: self._check_ashrae_from_dict,
        }

        checker = dispatch.get(standard)
        if checker is None:
            raise ComplianceError(
                f"Unsupported compliance standard: {standard.value}",
                standard=standard.value,
            )

        return checker(building_data)

    def check_ll97(self, building_data: dict) -> ComplianceResult:
        """Check NYC Local Law 97 compliance.

        Building data must include:
        - ``area_sqft``: Gross floor area in square feet.
        - ``annual_emissions_tco2e``: Annual emissions in tCO2e.
        - ``occupancy_type`` (optional): Building occupancy type.

        Args:
            building_data: Building performance data dictionary.

        Returns:
            ComplianceResult for LL97.
        """
        area_sqft = building_data.get("area_sqft", 0.0)
        emissions = building_data.get("annual_emissions_tco2e", 0.0)
        occupancy = building_data.get("occupancy_type", "default").lower()

        if area_sqft <= 0:
            raise ComplianceError(
                "Building area must be positive for LL97 check",
                standard="LL97",
                requirement="area_sqft",
            )

        limit = _LL97_LIMITS_2024.get(occupancy, _LL97_LIMITS_2024["default"])
        actual_intensity = emissions / area_sqft
        passed = actual_intensity <= limit

        recommendations = self._get_ll97_recommendations(
            actual_intensity, limit, passed
        )

        result = ComplianceResult(
            standard=ComplianceStandard.LL97,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 6),
            unit="tCO2e/sqft/year",
            recommendations=recommendations,
            details={
                "occupancy_type": occupancy,
                "area_sqft": area_sqft,
                "annual_emissions_tco2e": emissions,
                "limit_period": "2024-2029",
            },
        )

        logger.info(
            "LL97 check: {} (actual={:.6f}, limit={:.5f})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
        )
        return result

    def check_berdo(self, building_data: dict) -> ComplianceResult:
        """Check Boston BERDO compliance.

        Building data must include:
        - ``area_sqft``: Gross floor area in square feet.
        - ``annual_emissions_kgco2e``: Annual emissions in kgCO2e.
        - ``building_type`` (optional): Building type.

        Args:
            building_data: Building performance data dictionary.

        Returns:
            ComplianceResult for BERDO.
        """
        area_sqft = building_data.get("area_sqft", 0.0)
        emissions = building_data.get("annual_emissions_kgco2e", 0.0)
        btype = building_data.get("building_type", "default").lower()

        if area_sqft <= 0:
            raise ComplianceError(
                "Building area must be positive for BERDO check",
                standard="BERDO",
                requirement="area_sqft",
            )

        limit = _BERDO_LIMITS.get(btype, _BERDO_LIMITS["default"])
        actual_intensity = emissions / area_sqft
        passed = actual_intensity <= limit

        recommendations = self._get_berdo_recommendations(
            actual_intensity, limit, passed
        )

        result = ComplianceResult(
            standard=ComplianceStandard.BERDO,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 4),
            unit="kgCO2e/sqft/year",
            recommendations=recommendations,
            details={
                "building_type": btype,
                "area_sqft": area_sqft,
                "annual_emissions_kgco2e": emissions,
            },
        )

        logger.info(
            "BERDO check: {} (actual={:.4f}, limit={:.1f})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
        )
        return result

    def check_epbd(self, building_data: dict) -> ComplianceResult:
        """Check EU Energy Performance of Buildings Directive compliance.

        Building data must include:
        - ``area_m2``: Gross floor area in square meters.
        - ``primary_energy_kwh``: Annual primary energy demand in kWh.
        - ``building_type`` (optional): Building type.

        Args:
            building_data: Building performance data dictionary.

        Returns:
            ComplianceResult for EPBD.
        """
        area_m2 = building_data.get("area_m2", 0.0)
        energy_kwh = building_data.get("primary_energy_kwh", 0.0)
        btype = building_data.get("building_type", "default").lower()

        if area_m2 <= 0:
            raise ComplianceError(
                "Building area must be positive for EPBD check",
                standard="EPBD",
                requirement="area_m2",
            )

        limit = _EPBD_LIMITS.get(btype, _EPBD_LIMITS["default"])
        actual_intensity = energy_kwh / area_m2
        passed = actual_intensity <= limit

        recommendations = self._get_epbd_recommendations(
            actual_intensity, limit, passed
        )

        result = ComplianceResult(
            standard=ComplianceStandard.EPBD,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 2),
            unit="kWh/m2/year",
            recommendations=recommendations,
            details={
                "building_type": btype,
                "area_m2": area_m2,
                "primary_energy_kwh": energy_kwh,
            },
        )

        logger.info(
            "EPBD check: {} (actual={:.2f}, limit={:.1f})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
        )
        return result

    def check_ashrae(
        self,
        envelope_data: EnergyEnvelopeData,
    ) -> ComplianceResult:
        """Check ASHRAE 90.1 envelope compliance.

        Evaluates wall R-value, roof R-value, window U-value, and
        glazing ratio against ASHRAE 90.1-2019 requirements for
        climate zone 4A.

        Args:
            envelope_data: Building envelope thermal data.

        Returns:
            ComplianceResult for ASHRAE 90.1.
        """
        failures: list[str] = []
        details: dict[str, object] = {}

        wall_min = _ASHRAE_ENVELOPE["wall_r_min"]
        roof_min = _ASHRAE_ENVELOPE["roof_r_min"]
        window_max = _ASHRAE_ENVELOPE["window_u_max"]
        glazing_max = _ASHRAE_ENVELOPE["glazing_ratio_max"]

        if envelope_data.wall_r_value < wall_min:
            failures.append(
                f"Wall R-value {envelope_data.wall_r_value} below minimum {wall_min}"
            )
        details["wall_r_value"] = envelope_data.wall_r_value
        details["wall_r_min"] = wall_min

        if envelope_data.roof_r_value < roof_min:
            failures.append(
                f"Roof R-value {envelope_data.roof_r_value} below minimum {roof_min}"
            )
        details["roof_r_value"] = envelope_data.roof_r_value
        details["roof_r_min"] = roof_min

        if envelope_data.window_u_value > window_max:
            failures.append(
                f"Window U-value {envelope_data.window_u_value} "
                f"above maximum {window_max}"
            )
        details["window_u_value"] = envelope_data.window_u_value
        details["window_u_max"] = window_max

        if envelope_data.glazing_ratio > glazing_max:
            failures.append(
                f"Glazing ratio {envelope_data.glazing_ratio} "
                f"above maximum {glazing_max}"
            )
        details["glazing_ratio"] = envelope_data.glazing_ratio
        details["glazing_ratio_max"] = glazing_max

        passed = len(failures) == 0

        # Score as ratio of passing criteria (0 to 1).
        criteria_count = 4
        pass_count = criteria_count - len(failures)
        score = pass_count / criteria_count

        recommendations = failures if not passed else ["All envelope criteria met"]

        result = ComplianceResult(
            standard=ComplianceStandard.ASHRAE_90_1,
            passed=passed,
            threshold=1.0,
            actual_value=round(score, 2),
            unit="compliance_ratio",
            recommendations=recommendations,
            details=details,
        )

        logger.info(
            "ASHRAE 90.1 check: {} ({}/{} criteria met)",
            "PASS" if passed else "FAIL",
            pass_count,
            criteria_count,
        )
        return result

    def _check_ashrae_from_dict(
        self,
        building_data: dict,
    ) -> ComplianceResult:
        """Adapter to check ASHRAE 90.1 from a dictionary.

        Converts dictionary keys to an EnergyEnvelopeData instance and
        delegates to :meth:`check_ashrae`.
        """
        try:
            envelope = EnergyEnvelopeData(
                wall_r_value=float(building_data.get("wall_r_value", 0.0)),
                roof_r_value=float(building_data.get("roof_r_value", 0.0)),
                window_u_value=float(building_data.get("window_u_value", 1.0)),
                glazing_ratio=float(building_data.get("glazing_ratio", 0.5)),
                air_tightness=(
                    float(building_data["air_tightness"])
                    if "air_tightness" in building_data
                    else None
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ComplianceError(
                f"Invalid envelope data: {exc}",
                standard="ASHRAE 90.1",
                requirement="envelope_data",
                cause=exc,
            ) from exc

        return self.check_ashrae(envelope)

    def get_recommendations(
        self,
        result: ComplianceResult,
    ) -> list[str]:
        """Get improvement recommendations based on a compliance result.

        Args:
            result: The compliance result to analyze.

        Returns:
            List of recommendation strings.
        """
        if result.passed:
            return ["Compliance achieved. Consider exceeding targets."]

        recs: list[str] = list(result.recommendations)

        if result.standard == ComplianceStandard.LL97:
            recs.extend(
                self._get_ll97_recommendations(
                    result.actual_value, result.threshold, result.passed
                )
            )
        elif result.standard == ComplianceStandard.BERDO:
            recs.extend(
                self._get_berdo_recommendations(
                    result.actual_value, result.threshold, result.passed
                )
            )
        elif result.standard == ComplianceStandard.EPBD:
            recs.extend(
                self._get_epbd_recommendations(
                    result.actual_value, result.threshold, result.passed
                )
            )

        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for rec in recs:
            if rec not in seen:
                seen.add(rec)
                unique.append(rec)

        return unique

    @staticmethod
    def _get_ll97_recommendations(
        actual: float,
        limit: float,
        passed: bool,
    ) -> list[str]:
        """Generate LL97-specific recommendations."""
        if passed:
            return []

        recs = [
            "Upgrade HVAC systems to high-efficiency equipment",
            "Install building energy management system (BEMS)",
            "Consider on-site renewable energy generation",
        ]
        overshoot = (actual - limit) / limit if limit > 0 else 0
        if overshoot > 0.5:
            recs.append("Significant reduction needed: consider deep retrofit")
        return recs

    @staticmethod
    def _get_berdo_recommendations(
        actual: float,
        limit: float,
        passed: bool,
    ) -> list[str]:
        """Generate BERDO-specific recommendations."""
        if passed:
            return []

        return [
            "Improve building envelope insulation",
            "Electrify heating systems (heat pumps)",
            "Procure renewable energy certificates (RECs)",
        ]

    @staticmethod
    def _get_epbd_recommendations(
        actual: float,
        limit: float,
        passed: bool,
    ) -> list[str]:
        """Generate EPBD-specific recommendations."""
        if passed:
            return []

        return [
            "Improve thermal insulation of building envelope",
            "Install high-performance glazing systems",
            "Integrate renewable energy systems (solar PV, heat pumps)",
        ]
