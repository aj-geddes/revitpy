"""
Screening-level embodied carbon (A1-A3) from Revit material quantities.

Each element's materials arrive as ``{"name", "material_class", "volume",
"area"}`` with volume in cubic feet and area in square feet (Revit's
``GetMaterialVolume`` / ``GetMaterialArea``). Volumes are converted to m3,
aggregated per material, and priced with :class:`revitpy.sustainability.
CarbonCalculator`: generic ICE v2.0 cradle-to-gate factors, per m3 via each
record's assumed density. Materials with area but no volume (paint, surface
finishes) cannot be estimated this way and are reported as unquantified.

This is a screening estimate, not a substitute for product EPDs or a full LCA.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from revitpy.sustainability import CarbonCalculator, EpdDatabase, MaterialData

from ._elements import (
    FT2_TO_M2,
    FT3_TO_M3,
    filter_categories,
    is_number,
    option,
    rounded,
    string_list_option,
)

__all__ = ["embodied_carbon"]

LOW_CONFIDENCE = 0.5

BASIS = (
    "Screening estimate: Revit material volumes (ft3, converted to m3) x generic "
    "ICE v2.0 cradle-to-gate factors (per-m3 values derived from assumed "
    "densities). Not a substitute for product EPDs."
)


def _aggregate(
    elements: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str | None], dict[str, Any]], int]:
    """Sum material volume/area per (name, class); count elements without any."""
    totals: dict[tuple[str, str | None], dict[str, Any]] = {}
    without = 0
    for element in elements:
        materials = element.get("materials")
        found = False
        for material in materials if isinstance(materials, list) else ():
            if not isinstance(material, dict):
                continue
            name = material.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            volume, area = material.get("volume"), material.get("area")
            if not is_number(volume) and not is_number(area):
                continue
            found = True
            material_class = material.get("material_class")
            if not isinstance(material_class, str) or not material_class:
                material_class = None
            entry = totals.setdefault(
                (name.strip(), material_class),
                {"volume_ft3": 0.0, "area_ft2": 0.0, "element_ids": set()},
            )
            entry["volume_ft3"] += float(volume) if is_number(volume) else 0.0
            entry["area_ft2"] += float(area) if is_number(area) else 0.0
            entry["element_ids"].add(element.get("id"))
        if not found:
            without += 1
    return totals, without


def embodied_carbon(elements: list[Any], options: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate A1-A3 embodied carbon of the elements' materials.

    Options: ``categories`` (list of category names), ``gross_floor_area_m2``
    (enables a RIBA 2030 benchmark), ``building_type`` (benchmark target,
    e.g. "office", "residential"; default "default").
    """
    filtered = filter_categories(elements, string_list_option(options, "categories"))
    floor_area = option(options, "gross_floor_area_m2", None, float)
    if floor_area is not None and floor_area <= 0:
        raise ValueError("option 'gross_floor_area_m2' must be greater than 0")
    building_type = option(options, "building_type", "default", str)

    totals, elements_without_materials = _aggregate(filtered)

    pending: list[tuple[MaterialData, int]] = []
    unquantified: list[dict[str, Any]] = []
    for (name, material_class), entry in sorted(
        totals.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        count = len(entry["element_ids"])
        if entry["volume_ft3"] > 0:
            material = MaterialData(
                name=name,
                category=material_class or "Uncategorized",
                volume_m3=entry["volume_ft3"] * FT3_TO_M3,
                area_m2=entry["area_ft2"] * FT2_TO_M2,
            )
            pending.append((material, count))
        elif entry["area_ft2"] > 0:
            unquantified.append(
                {
                    "material": name,
                    "material_class": material_class,
                    "area_m2": rounded(entry["area_ft2"] * FT2_TO_M2),
                    "element_count": count,
                }
            )

    calculator = CarbonCalculator(epd_database=EpdDatabase())
    results = calculator.calculate([material for material, _count in pending])
    by_material = {id(result.material): result for result in results}

    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    total = 0.0
    for material, count in pending:
        material_class = (
            None if material.category == "Uncategorized" else material.category
        )
        result = by_material.get(id(material))
        if result is None:
            unmatched.append(
                {
                    "material": material.name,
                    "material_class": material_class,
                    "volume_m3": rounded(material.volume_m3),
                    "element_count": count,
                }
            )
            continue
        epd = result.epd
        total += result.embodied_carbon_kgco2e
        rows.append(
            {
                "material": material.name,
                "material_class": material_class,
                "volume_m3": rounded(material.volume_m3),
                "element_count": count,
                "kgco2e": rounded(result.embodied_carbon_kgco2e, 2),
                "method": result.calculation_method,
                "epd": epd.material_name,
                "matched_key": epd.matched_key,
                "match_type": epd.match_type,
                "match_confidence": epd.match_confidence,
                "gwp_per_m3": epd.gwp_per_m3,
                "assumed_density_kg_m3": epd.assumed_density_kg_m3,
                "generic_fallback": epd.is_generic_fallback,
                "low_confidence": epd.match_confidence is not None
                and epd.match_confidence < LOW_CONFIDENCE,
            }
        )
    rows.sort(key=lambda row: (-(row["kgco2e"] or 0.0), row["material"]))

    benchmark = None
    if floor_area is not None:
        result = calculator.benchmark(
            calculator.summarize(results), floor_area, building_type
        )
        benchmark = {
            "kgco2e_per_m2": result.actual_kgco2e_per_m2,
            "target_kgco2e_per_m2": result.target_kgco2e_per_m2,
            "rating": result.rating,
            "source": result.benchmark_source,
        }

    return {
        "total_kgco2e": rounded(total, 2),
        "total_tco2e": rounded(total / 1000, 3),
        "lifecycle_stages": ["A1", "A2", "A3"],
        "materials": rows,
        "unmatched": unmatched,
        "unquantified": unquantified,
        "elements_without_materials": elements_without_materials,
        "element_count": len(filtered),
        "benchmark": benchmark,
        "basis": BASIS,
    }
