"""
Building emissions and envelope compliance *screening*.

This module screens building data against NYC Local Law 97, Boston
BERDO, EU EPBD national/local limits, and ASHRAE 90.1-2019 prescriptive
envelope values.

These are screening-level estimates, **not** compliance determinations.
Every built-in limit records its source, every limit can be overridden
by the caller, and no check silently falls back to a default building
category. Results carry ``source`` and ``notes`` explaining exactly what
was compared.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from .exceptions import ComplianceError
from .types import ComplianceResult, ComplianceStandard, EnergyEnvelopeData

SCREENING_DISCLAIMER = (
    "Screening-level estimate only; not a compliance determination. Verify "
    "against the governing code text with a qualified professional."
)

# ---------------------------------------------------------------------------
# NYC Local Law 97
# ---------------------------------------------------------------------------

_LL97_SOURCE = (
    "NYC Admin. Code §28-320.3.1 (2024-2029) / §28-320.3.2 (2030-2034), "
    "Local Law 97 of 2019 as amended; ESPM property-type factors from "
    "1 RCNY §103-14(c)(3)"
)

_LL97_PERIODS: dict[str, tuple[int, int]] = {
    "2024-2029": (2024, 2029),
    "2030-2034": (2030, 2034),
}

# Building emissions intensity limits by occupancy group (tCO2e/sf/yr).
# Source: NYC Admin. Code §28-320.3.1 items 1-10 (2024-2029) and
# §28-320.3.2 items 1-10 (2030-2034). "B-HEALTHCARE" is item 6: group B
# civic administrative facility for emergency response services, B
# non-production laboratory, and B ambulatory health care facility.
_LL97_GROUP_LIMITS: dict[str, dict[str, float]] = {
    "2024-2029": {
        "A": 0.01074,
        "B": 0.00846,
        "B-HEALTHCARE": 0.02381,
        "E": 0.00758,
        "I-4": 0.00758,
        "I-1": 0.01138,
        "F": 0.00574,
        "H": 0.02381,
        "I-2": 0.02381,
        "I-3": 0.02381,
        "M": 0.01181,
        "R-1": 0.00987,
        "R-2": 0.00675,
        "S": 0.00426,
        "U": 0.00426,
    },
    "2030-2034": {
        "A": 0.00420,
        "B": 0.00453,
        "B-HEALTHCARE": 0.01330,
        "E": 0.00344,
        "I-4": 0.00344,
        "I-1": 0.00598,
        "F": 0.00167,
        "H": 0.01330,
        "I-2": 0.01330,
        "I-3": 0.01330,
        "M": 0.00403,
        "R-1": 0.00526,
        "R-2": 0.00407,
        "S": 0.00110,
        "U": 0.00110,
    },
}

# Emissions factors by ENERGY STAR Portfolio Manager (ESPM) property type
# (tCO2e/sf/yr), transcribed from 1 RCNY §103-14(c)(3)(i) (2024-2029) and
# (c)(3)(iii) (2030-2034). From calendar year 2026 reporting onward the
# rule requires ESPM property types rather than occupancy groups.
_LL97_ESPM_2024_2029: dict[str, float] = {
    "Adult Education": 0.00758,
    "Ambulatory Surgical Center": 0.01181,
    "Automobile Dealership": 0.00675,
    "Bank Branch": 0.00987,
    "Bowling Alley": 0.00574,
    "College/University": 0.00987,
    "Convenience Store without Gas Station": 0.00675,
    "Courthouse": 0.00426,
    "Data Center": 0.02381,
    "Distribution Center": 0.00574,
    "Enclosed Mall": 0.01074,
    "Financial Office": 0.00846,
    "Fitness Center/Health Club/Gym": 0.00987,
    "Food Sales": 0.01181,
    "Food Service": 0.01181,
    "Hospital (General Medical & Surgical)": 0.02381,
    "Hotel": 0.00987,
    "K-12 School": 0.00675,
    "Laboratory": 0.02381,
    "Library": 0.00675,
    "Lifestyle Center": 0.00846,
    "Mailing Center/Post Office": 0.00426,
    "Manufacturing/Industrial Plant": 0.00758,
    "Medical Office": 0.01074,
    "Movie Theater": 0.01181,
    "Multifamily Housing": 0.00675,
    "Museum": 0.01181,
    "Non-Refrigerated Warehouse": 0.00426,
    "Office": 0.00758,
    "Other - Education": 0.00846,
    "Other - Entertainment/Public Assembly": 0.00987,
    "Other - Lodging/Residential": 0.00758,
    "Other - Mall": 0.01074,
    "Other - Public Services": 0.00758,
    "Other - Recreation": 0.00987,
    "Other - Restaurant/Bar": 0.02381,
    "Other - Services": 0.01074,
    "Other - Specialty Hospital": 0.02381,
    "Other - Technology/Science": 0.02381,
    "Outpatient Rehabilitation/Physical Therapy": 0.01181,
    "Parking": 0.00426,
    "Performing Arts": 0.00846,
    "Personal Services (Health/Beauty, Dry Cleaning, etc.)": 0.00574,
    "Pre-school/Daycare": 0.00675,
    "Refrigerated Warehouse": 0.00987,
    "Repair Services (Vehicle, Shoe, Locksmith, etc.)": 0.00426,
    "Residence Hall/Dormitory": 0.00758,
    "Residential Care Facility": 0.01138,
    "Restaurant": 0.01181,
    "Retail Store": 0.00758,
    "Self-Storage Facility": 0.00426,
    "Senior Care Community": 0.01138,
    "Social/Meeting Hall": 0.00987,
    "Strip Mall": 0.01181,
    "Supermarket/Grocery Store": 0.02381,
    "Transportation Terminal/Station": 0.00426,
    "Urgent Care/Clinic/Other Outpatient": 0.01181,
    "Vocational School": 0.00574,
    "Wholesale Club/Supercenter": 0.01138,
    "Worship Facility": 0.00574,
}

_LL97_ESPM_2030_2034: dict[str, float] = {
    "Adult Education": 0.003565528,
    "Ambulatory Surgical Center": 0.008980612,
    "Automobile Dealership": 0.002824097,
    "Bank Branch": 0.004036172,
    "Bowling Alley": 0.003103815,
    "College/University": 0.002099748,
    "Convenience Store without Gas Station": 0.003540032,
    "Courthouse": 0.001480533,
    "Data Center": 0.014791131,
    "Distribution Center": 0.000991600,
    "Enclosed Mall": 0.003983803,
    "Financial Office": 0.003697004,
    "Fitness Center/Health Club/Gym": 0.003946728,
    "Food Sales": 0.005208880,
    "Food Service": 0.007749414,
    "Hospital (General Medical & Surgical)": 0.007335204,
    "Hotel": 0.003850668,
    "K-12 School": 0.002230588,
    "Laboratory": 0.026029868,
    "Library": 0.002218412,
    "Lifestyle Center": 0.004705850,
    "Mailing Center/Post Office": 0.001980440,
    "Manufacturing/Industrial Plant": 0.001417030,
    "Medical Office": 0.002912778,
    "Movie Theater": 0.005395268,
    "Multifamily Housing": 0.003346640,
    "Museum": 0.005395800,
    "Non-Refrigerated Warehouse": 0.000883187,
    "Office": 0.002690852,
    "Other - Education": 0.002934006,
    "Other - Entertainment/Public Assembly": 0.002956738,
    "Other - Lodging/Residential": 0.001901982,
    "Other - Mall": 0.001928226,
    "Other - Public Services": 0.003808033,
    "Other - Recreation": 0.004479570,
    "Other - Restaurant/Bar": 0.008505075,
    "Other - Services": 0.001823381,
    "Other - Specialty Hospital": 0.006321819,
    "Other - Technology/Science": 0.010446456,
    "Outpatient Rehabilitation/Physical Therapy": 0.006018323,
    "Parking": 0.000214421,
    "Performing Arts": 0.002472539,
    "Personal Services (Health/Beauty, Dry Cleaning, etc.)": 0.004843037,
    "Pre-school/Daycare": 0.002362874,
    "Refrigerated Warehouse": 0.002852131,
    "Repair Services (Vehicle, Shoe, Locksmith, etc.)": 0.002210699,
    "Residence Hall/Dormitory": 0.002464089,
    "Residential Care Facility": 0.004893124,
    "Restaurant": 0.004038374,
    "Retail Store": 0.002104490,
    "Self-Storage Facility": 0.000611830,
    "Senior Care Community": 0.004410123,
    "Social/Meeting Hall": 0.003833108,
    "Strip Mall": 0.001361842,
    "Supermarket/Grocery Store": 0.006755190,
    "Transportation Terminal/Station": 0.000571669,
    "Urgent Care/Clinic/Other Outpatient": 0.005772375,
    "Vocational School": 0.004613122,
    "Wholesale Club/Supercenter": 0.004264962,
    "Worship Facility": 0.001230602,
}

_LL97_ESPM_LIMITS: dict[str, dict[str, float]] = {
    "2024-2029": _LL97_ESPM_2024_2029,
    "2030-2034": _LL97_ESPM_2030_2034,
}

# Convenience names -> occupancy group. Recorded in result notes when used.
_LL97_OCCUPANCY_ALIASES: dict[str, str] = {
    "office": "B",
    "residential": "R-2",
    "multifamily": "R-2",
    "hotel": "R-1",
    "retail": "M",
    "mercantile": "M",
    "healthcare": "I-2",
    "hospital": "I-2",
    "education": "E",
    "school": "E",
    "warehouse": "S",
    "storage": "S",
    "assembly": "A",
    "factory": "F",
    "industrial": "F",
}

# ---------------------------------------------------------------------------
# Boston BERDO
# ---------------------------------------------------------------------------

_BERDO_SOURCE = (
    "unverified: legacy placeholder values not checked against Boston "
    "BERDO 2.0 emissions standards"
)

# kgCO2e/sf/yr. UNVERIFIED -- retained for backwards compatibility only.
_BERDO_LIMITS: dict[str, float] = {
    "office": 5.4,
    "residential": 3.6,
    "retail": 6.1,
    "education": 4.8,
}

# ---------------------------------------------------------------------------
# ASHRAE 90.1-2019 envelope (nonresidential, prescriptive)
# ---------------------------------------------------------------------------

_ASHRAE_SOURCE = (
    "ANSI/ASHRAE/IES Standard 90.1-2019, Tables 5.5-0 to 5.5-8 "
    "(nonresidential, prescriptive)"
)

# Nonresidential roofs, insulation entirely above deck: minimum R c.i.
# Transcribed from US DOE Building Energy Codes Program, "ANSI/ASHRAE/IES
# Standard 90.1-2019: Envelope" training (Tables 5.5-0 .. 5.5-8).
_ASHRAE_ROOF_R_MIN: dict[int, float] = {
    0: 25.0,
    1: 20.0,
    2: 25.0,
    3: 25.0,
    4: 30.0,
    5: 30.0,
    6: 30.0,
    7: 35.0,
    8: 35.0,
}

# Fixed vertical fenestration, maximum assembly U-factor (Btu/h-ft2-F).
# SECONDARY SOURCE: National Glass Association Glass Technical Paper
# FB74-22 (2022), Table 1 ("90.1-2019, 2021 IECC" row). Verify against
# the standard before relying on it.
_ASHRAE_FIXED_FENESTRATION_U_MAX: dict[int, float] = {
    0: 0.50,
    1: 0.50,
    2: 0.45,
    3: 0.42,
    4: 0.36,
    5: 0.34,
    6: 0.34,
    7: 0.29,
    8: 0.26,
}

# 90.1-2019 §5.5.4.2.1: vertical fenestration area <= 40% of gross wall
# area, all climate zones (prescriptive path).
_ASHRAE_GLAZING_RATIO_MAX = 0.40

_ASHRAE_CRITERIA: tuple[str, ...] = (
    "wall_r_min",
    "roof_r_min",
    "window_u_max",
    "glazing_ratio_max",
)

_CLIMATE_ZONE_RE = re.compile(r"^([0-8])([ABC])?$")


def parse_climate_zone(zone: str | int) -> tuple[int, str]:
    """Parse an ASHRAE climate zone designation.

    Args:
        zone: Zone such as ``"4A"``, ``"5b"``, ``"7"`` or ``4``.

    Returns:
        Tuple of (zone number, normalized designation such as ``"4A"``).

    Raises:
        ComplianceError: If the zone is not 0-8 with optional A/B/C.
    """
    if isinstance(zone, bool) or not isinstance(zone, (str, int)):
        raise ComplianceError(
            f"Unsupported climate zone {zone!r}; expected 0-8 with optional "
            "moisture regime A/B/C (e.g. '4A')",
            standard="ASHRAE 90.1",
            requirement="climate_zone",
        )
    text = str(zone).strip().upper()
    match = _CLIMATE_ZONE_RE.match(text)
    if match is None:
        raise ComplianceError(
            f"Unsupported climate zone {zone!r}; ASHRAE 90.1-2019 zones are "
            "0-8 with optional moisture regime A/B/C (e.g. '4A', '5B', '7')",
            standard="ASHRAE 90.1",
            requirement="climate_zone",
        )
    return int(match.group(1)), text


def _require_positive(value: Any, *, standard: str, requirement: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ComplianceError(
            f"{requirement} must be a number for {standard} check",
            standard=standard,
            requirement=requirement,
            cause=exc,
        ) from exc
    if number <= 0:
        raise ComplianceError(
            f"Building area must be positive for {standard} check",
            standard=standard,
            requirement=requirement,
        )
    return number


class ComplianceChecker:
    """Screens building data against emissions and envelope standards.

    Results are screening-level estimates, not compliance
    determinations. See each ``check_*`` method for the source of its
    built-in limits and how to override them.
    """

    def __init__(self) -> None:
        logger.debug("ComplianceChecker initialized")

    def check(
        self,
        standard: ComplianceStandard,
        building_data: dict[str, Any],
    ) -> ComplianceResult:
        """Screen compliance against a specific standard.

        Args:
            standard: The compliance standard to check against.
            building_data: Building performance data. Required keys vary
                by standard; see the ``check_*`` methods. Limit overrides
                may be supplied as ``"ll97_limits"``, ``"berdo_limits"``,
                ``"epbd_limits"`` (plus ``"epbd_limit_source"``), and for
                ASHRAE 90.1 as ``"overrides"``.

        Returns:
            ComplianceResult with pass/fail, source and notes.

        Raises:
            ComplianceError: If the standard is unsupported or required
                data is missing.
        """
        if standard == ComplianceStandard.LL97:
            return self.check_ll97(
                building_data, limits=building_data.get("ll97_limits")
            )
        if standard == ComplianceStandard.BERDO:
            return self.check_berdo(
                building_data, limits=building_data.get("berdo_limits")
            )
        if standard == ComplianceStandard.EPBD:
            return self.check_epbd(
                building_data,
                limits=building_data.get("epbd_limits"),
                limit_source=building_data.get("epbd_limit_source"),
            )
        if standard == ComplianceStandard.ASHRAE_90_1:
            return self._check_ashrae_from_dict(building_data)
        raise ComplianceError(
            f"Unsupported compliance standard: {standard.value}",
            standard=standard.value,
        )

    # ------------------------------------------------------------------
    # LL97
    # ------------------------------------------------------------------

    @staticmethod
    def _ll97_period(year: int) -> tuple[str, list[str]]:
        warnings: list[str] = []
        for period, (start, end) in _LL97_PERIODS.items():
            if start <= year <= end:
                return period, warnings
        if year < 2024:
            warnings.append(
                f"Year {year} precedes LL97 building emissions limits, which "
                "begin with calendar year 2024; applied 2024-2029 limits."
            )
            return "2024-2029", warnings
        warnings.append(
            f"Year {year} is after 2034; limits for 2035 onward are stricter "
            "and are not modeled here. Applied 2030-2034 limits, so this "
            "result is likely optimistic."
        )
        return "2030-2034", warnings

    def check_ll97(
        self,
        building_data: dict[str, Any],
        *,
        year: int | None = None,
        limits: dict[str, float] | None = None,
    ) -> ComplianceResult:
        """Screen against NYC Local Law 97 building emissions limits.

        Building data keys:

        - ``area_sqft``: Gross floor area in square feet (required).
        - ``annual_emissions_tco2e``: Annual emissions in tCO2e.
        - ``property_type``: ENERGY STAR Portfolio Manager property type
          (e.g. ``"Office"``, ``"Multifamily Housing"``), **or**
        - ``occupancy_type``: LL97 occupancy group (``"B"``, ``"R-2"``,
          ``"B-healthcare"``...) or a convenience alias (``"office"``).
        - ``compliance_year`` (optional): Calendar year being evaluated.

        Args:
            building_data: Building performance data dictionary.
            year: Calendar year to evaluate. Defaults to
                ``building_data["compliance_year"]`` or the current year.
                Selects the 2024-2029 or 2030-2034 compliance period.
            limits: Optional overrides keyed by the resolved group/property
                type, or ``"*"`` for any.

        Returns:
            ComplianceResult for LL97.

        Raises:
            ComplianceError: If area or classification is missing/unknown.
        """
        area_sqft = _require_positive(
            building_data.get("area_sqft", 0.0),
            standard="LL97",
            requirement="area_sqft",
        )
        emissions = float(building_data.get("annual_emissions_tco2e", 0.0))

        if year is None:
            raw_year = building_data.get("compliance_year")
            year = int(raw_year) if raw_year is not None else datetime.now(UTC).year
        period, warnings = self._ll97_period(year)

        notes: list[str] = [SCREENING_DISCLAIMER]
        property_type: str | None = None
        group: str | None = None
        builtin: float

        raw_property = building_data.get("property_type")
        raw_occupancy = building_data.get("occupancy_type")
        if raw_property:
            espm = _LL97_ESPM_LIMITS[period]
            lookup = {name.lower(): name for name in espm}
            property_type = lookup.get(str(raw_property).strip().lower())
            if property_type is None:
                raise ComplianceError(
                    f"Unknown ESPM property type {raw_property!r} for LL97; "
                    "use a property type listed in 1 RCNY §103-14(c)(3)",
                    standard="LL97",
                    requirement="property_type",
                )
            builtin = espm[property_type]
            category = property_type
            basis = "espm_property_type"
        elif raw_occupancy:
            key = str(raw_occupancy).strip()
            groups = _LL97_GROUP_LIMITS[period]
            if key.upper() in groups:
                group = key.upper()
            elif key.lower() in _LL97_OCCUPANCY_ALIASES:
                group = _LL97_OCCUPANCY_ALIASES[key.lower()]
                notes.append(f"'{key}' interpreted as occupancy group {group}.")
            else:
                raise ComplianceError(
                    f"Unknown LL97 occupancy {raw_occupancy!r}; must be an LL97 "
                    f"occupancy group ({', '.join(sorted(groups))}), an alias "
                    f"({', '.join(sorted(_LL97_OCCUPANCY_ALIASES))}), or an ESPM "
                    "property type passed as 'property_type'",
                    standard="LL97",
                    requirement="occupancy_type",
                )
            builtin = groups[group]
            category = group
            basis = "occupancy_group"
            if year >= 2026:
                warnings.append(
                    "1 RCNY §103-14(c)(3) requires ESPM property-type emissions "
                    "factors for calendar year 2026 reporting onward; "
                    "occupancy-group limits were permitted only for 2024-2025. "
                    "Pass 'property_type' instead."
                )
        else:
            raise ComplianceError(
                "LL97 check requires 'property_type' (ESPM) or 'occupancy_type'",
                standard="LL97",
                requirement="occupancy_type",
            )

        limit, limit_source = builtin, "built-in"
        if limits:
            override = limits.get(category, limits.get("*"))
            if override is not None:
                limit, limit_source = float(override), "caller-supplied"

        for warning in warnings:
            logger.warning("LL97: {}", warning)
        notes.extend(warnings)

        actual_intensity = emissions / area_sqft
        passed = actual_intensity <= limit

        result = ComplianceResult(
            standard=ComplianceStandard.LL97,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 6),
            unit="tCO2e/sqft/year",
            recommendations=self._get_ll97_recommendations(
                actual_intensity, limit, passed
            ),
            details={
                "occupancy_type": group,
                "property_type": property_type,
                "classification_basis": basis,
                "area_sqft": area_sqft,
                "annual_emissions_tco2e": emissions,
                "compliance_year": year,
                "limit_period": period,
                "limit_source": limit_source,
            },
            source=_LL97_SOURCE if limit_source == "built-in" else "caller-supplied",
            notes=notes,
        )

        logger.info(
            "LL97 screening: {} (actual={:.6f}, limit={:.6f}, {} {}, period {})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
            basis,
            category,
            period,
        )
        return result

    # ------------------------------------------------------------------
    # BERDO
    # ------------------------------------------------------------------

    def check_berdo(
        self,
        building_data: dict[str, Any],
        *,
        limits: dict[str, float] | None = None,
    ) -> ComplianceResult:
        """Screen against Boston BERDO emissions standards.

        Building data keys: ``area_sqft``, ``annual_emissions_kgco2e`` and
        ``building_type`` (all required).

        The built-in BERDO values are **unverified placeholders**; pass
        ``limits`` (keyed by building type or ``"*"``) taken from the
        current BERDO 2.0 emissions standards for a meaningful result.

        Args:
            building_data: Building performance data dictionary.
            limits: Optional caller-supplied limits in kgCO2e/sf/yr.

        Returns:
            ComplianceResult for BERDO.
        """
        area_sqft = _require_positive(
            building_data.get("area_sqft", 0.0),
            standard="BERDO",
            requirement="area_sqft",
        )
        emissions = float(building_data.get("annual_emissions_kgco2e", 0.0))
        raw_type = building_data.get("building_type")
        if not raw_type:
            raise ComplianceError(
                "BERDO check requires 'building_type'",
                standard="BERDO",
                requirement="building_type",
            )
        btype = str(raw_type).strip().lower()

        notes: list[str] = [SCREENING_DISCLAIMER]
        limit: float | None = None
        limit_source = "caller-supplied"
        if limits:
            override = limits.get(btype, limits.get("*"))
            if override is not None:
                limit = float(override)
        if limit is None:
            if btype not in _BERDO_LIMITS:
                raise ComplianceError(
                    f"No BERDO limit for building type '{btype}'; supply limits",
                    standard="BERDO",
                    requirement="limits",
                )
            limit = _BERDO_LIMITS[btype]
            limit_source = "built-in (unverified)"
            warning = (
                "Built-in BERDO limits are unverified placeholders; supply "
                "limits from the current BERDO 2.0 emissions standards."
            )
            logger.warning("BERDO: {}", warning)
            notes.append(warning)

        actual_intensity = emissions / area_sqft
        passed = actual_intensity <= limit

        result = ComplianceResult(
            standard=ComplianceStandard.BERDO,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 4),
            unit="kgCO2e/sqft/year",
            recommendations=self._get_berdo_recommendations(
                actual_intensity, limit, passed
            ),
            details={
                "building_type": btype,
                "area_sqft": area_sqft,
                "annual_emissions_kgco2e": emissions,
                "limit_source": limit_source,
            },
            source=(
                "caller-supplied"
                if limit_source == "caller-supplied"
                else _BERDO_SOURCE
            ),
            notes=notes,
        )

        logger.info(
            "BERDO screening: {} (actual={:.4f}, limit={:.2f})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
        )
        return result

    # ------------------------------------------------------------------
    # EPBD
    # ------------------------------------------------------------------

    def check_epbd(
        self,
        building_data: dict[str, Any],
        *,
        limits: dict[str, float] | None = None,
        limit_source: str | None = None,
    ) -> ComplianceResult:
        """Screen primary energy use against supplied EPBD national limits.

        The EU Energy Performance of Buildings Directive (Directive (EU)
        2024/1275) sets **no pan-EU numeric kWh/m2/yr cap**: Member States
        define minimum energy performance requirements in national or
        regional law. This method therefore has no built-in limits; the
        caller must supply them.

        Building data keys: ``area_m2``, ``primary_energy_kwh`` and
        ``building_type`` (all required).

        Args:
            building_data: Building performance data dictionary.
            limits: Primary energy limits in kWh/m2/yr keyed by building
                type, or ``"*"`` for any type.
            limit_source: Citation for the supplied limits (e.g. the
                national regulation and edition).

        Returns:
            ComplianceResult for EPBD.

        Raises:
            ComplianceError: If no applicable limit was supplied.
        """
        source = limit_source or "caller-supplied"
        raw_type = building_data.get("building_type")
        if not raw_type:
            raise ComplianceError(
                "EPBD check requires 'building_type'",
                standard="EPBD",
                requirement="building_type",
            )
        btype = str(raw_type).strip().lower()

        limit_value = None
        if limits:
            limit_value = limits.get(btype, limits.get("*"))
        if limit_value is None:
            raise ComplianceError(
                "The EPBD sets no pan-EU numeric energy cap; supply the national "
                f"or local primary energy limit for '{btype}' via "
                "limits={'<building_type>': kWh_per_m2_yr}",
                standard="EPBD",
                requirement="limits",
            )
        limit = float(limit_value)

        area_m2 = _require_positive(
            building_data.get("area_m2", 0.0),
            standard="EPBD",
            requirement="area_m2",
        )
        energy_kwh = float(building_data.get("primary_energy_kwh", 0.0))

        actual_intensity = energy_kwh / area_m2
        passed = actual_intensity <= limit

        result = ComplianceResult(
            standard=ComplianceStandard.EPBD,
            passed=passed,
            threshold=limit,
            actual_value=round(actual_intensity, 2),
            unit="kWh/m2/year",
            recommendations=self._get_epbd_recommendations(
                actual_intensity, limit, passed
            ),
            details={
                "building_type": btype,
                "area_m2": area_m2,
                "primary_energy_kwh": energy_kwh,
                "limit_source": source,
            },
            source=source,
            notes=[
                SCREENING_DISCLAIMER,
                f"Checked against caller-supplied limit of {limit} kWh/m2/yr "
                f"({source}); the EPBD itself sets no pan-EU numeric cap.",
            ],
        )

        logger.info(
            "EPBD screening: {} (actual={:.2f}, supplied limit={:.1f})",
            "PASS" if passed else "FAIL",
            actual_intensity,
            limit,
        )
        return result

    # ------------------------------------------------------------------
    # ASHRAE 90.1
    # ------------------------------------------------------------------

    def check_ashrae(
        self,
        envelope_data: EnergyEnvelopeData,
        climate_zone: str | int,
        *,
        overrides: dict[str, float] | None = None,
    ) -> ComplianceResult:
        """Screen envelope values against ASHRAE 90.1-2019 prescriptive limits.

        Built-in limits (nonresidential, by climate zone 0-8):

        - roof: minimum R c.i. for insulation entirely above deck;
        - window: maximum U-factor for fixed vertical fenestration
          (secondary source, see module constants);
        - glazing ratio: maximum 40% of gross wall area.

        Walls are only evaluated when ``overrides["wall_r_min"]`` is given,
        because the 90.1 wall minimum depends on the wall type.

        Args:
            envelope_data: Building envelope thermal data.
            climate_zone: ASHRAE climate zone, e.g. ``"4A"`` (required).
            overrides: Optional replacement limits for any of
                ``wall_r_min``, ``roof_r_min``, ``window_u_max``,
                ``glazing_ratio_max``.

        Returns:
            ComplianceResult for ASHRAE 90.1.

        Raises:
            ComplianceError: For an unsupported climate zone or unknown
                override key.
        """
        zone_num, zone = parse_climate_zone(climate_zone)
        limits: dict[str, float | None] = {
            "wall_r_min": None,
            "roof_r_min": _ASHRAE_ROOF_R_MIN[zone_num],
            "window_u_max": _ASHRAE_FIXED_FENESTRATION_U_MAX[zone_num],
            "glazing_ratio_max": _ASHRAE_GLAZING_RATIO_MAX,
        }
        applied: list[str] = []
        for key, value in (overrides or {}).items():
            if key not in _ASHRAE_CRITERIA:
                raise ComplianceError(
                    f"Unknown ASHRAE override '{key}'; expected one of "
                    f"{', '.join(_ASHRAE_CRITERIA)}",
                    standard="ASHRAE 90.1",
                    requirement=key,
                )
            limits[key] = float(value)
            applied.append(key)

        checks: tuple[tuple[str, str, str, float, bool], ...] = (
            ("wall", "wall_r_value", "Wall R-value", envelope_data.wall_r_value, True),
            ("roof", "roof_r_value", "Roof R-value", envelope_data.roof_r_value, True),
            (
                "window",
                "window_u_value",
                "Window U-value",
                envelope_data.window_u_value,
                False,
            ),
            (
                "glazing",
                "glazing_ratio",
                "Glazing ratio",
                envelope_data.glazing_ratio,
                False,
            ),
        )

        failures: list[str] = []
        not_evaluated: list[str] = []
        details: dict[str, Any] = {
            "climate_zone": zone,
            "table": f"Table 5.5-{zone_num}",
        }
        evaluated = 0
        for (name, value_key, label, actual, is_minimum), limit_key in zip(
            checks, _ASHRAE_CRITERIA, strict=True
        ):
            limit = limits[limit_key]
            details[value_key] = actual
            details[limit_key] = limit
            if limit is None:
                not_evaluated.append(name)
                continue
            evaluated += 1
            if is_minimum and actual < limit:
                failures.append(f"{label} {actual} below minimum {limit}")
            elif not is_minimum and actual > limit:
                failures.append(f"{label} {actual} above maximum {limit}")
        details["not_evaluated"] = not_evaluated
        details["overrides_applied"] = applied

        notes = [SCREENING_DISCLAIMER]
        if "wall" in not_evaluated:
            notes.append(
                "Wall requirement not evaluated: ASHRAE 90.1-2019 wall minimums "
                "depend on wall type (mass, metal building, steel-framed, "
                "wood-framed); pass overrides={'wall_r_min': ...}."
            )
        if "roof_r_min" not in applied:
            notes.append(
                "Roof value compared with the nonresidential 'insulation "
                "entirely above deck' minimum (R c.i.)."
            )
        if "window_u_max" not in applied:
            notes.append(
                "Fenestration limit is the fixed vertical fenestration U-factor "
                "from a secondary source (NGA FB74-22); verify against the "
                "standard."
            )

        passed = not failures
        pass_count = evaluated - len(failures)
        score = pass_count / evaluated if evaluated else 0.0

        result = ComplianceResult(
            standard=ComplianceStandard.ASHRAE_90_1,
            passed=passed,
            threshold=1.0,
            actual_value=round(score, 2),
            unit="compliance_ratio",
            recommendations=(
                failures if failures else ["All evaluated envelope criteria met"]
            ),
            details=details,
            source=_ASHRAE_SOURCE,
            notes=notes,
        )

        logger.info(
            "ASHRAE 90.1-2019 screening (zone {}): {} ({}/{} evaluated criteria met)",
            zone,
            "PASS" if passed else "FAIL",
            pass_count,
            evaluated,
        )
        return result

    def _check_ashrae_from_dict(
        self,
        building_data: dict[str, Any],
    ) -> ComplianceResult:
        """Build :class:`EnergyEnvelopeData` from a dict and screen it.

        Requires ``climate_zone``, ``wall_r_value``, ``roof_r_value``,
        ``window_u_value`` and ``glazing_ratio``; no values are assumed.
        """
        required = (
            "climate_zone",
            "wall_r_value",
            "roof_r_value",
            "window_u_value",
            "glazing_ratio",
        )
        for key in required:
            if building_data.get(key) is None:
                raise ComplianceError(
                    f"ASHRAE 90.1 check requires '{key}'",
                    standard="ASHRAE 90.1",
                    requirement=key,
                )
        try:
            envelope = EnergyEnvelopeData(
                wall_r_value=float(building_data["wall_r_value"]),
                roof_r_value=float(building_data["roof_r_value"]),
                window_u_value=float(building_data["window_u_value"]),
                glazing_ratio=float(building_data["glazing_ratio"]),
                air_tightness=(
                    float(building_data["air_tightness"])
                    if building_data.get("air_tightness") is not None
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

        return self.check_ashrae(
            envelope,
            building_data["climate_zone"],
            overrides=building_data.get("overrides"),
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

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

        return list(dict.fromkeys(recs))

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
