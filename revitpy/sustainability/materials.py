"""
Material extraction and classification for sustainability analysis.

This module provides functionality to extract material data from building
elements, aggregate quantities, and classify materials using standard
classification systems (UniFormat, MasterFormat, OmniClass).
"""

from __future__ import annotations

from loguru import logger

from .exceptions import SustainabilityError
from .types import MaterialData

# Classification mappings for common building material categories.
_UNIFFORMAT_CLASSIFICATIONS: dict[str, str] = {
    "concrete": "B1010",
    "steel": "B1020",
    "timber": "B1030",
    "wood": "B1030",
    "masonry": "B1010",
    "brick": "B1010",
    "glass": "B2020",
    "aluminum": "B2010",
    "insulation": "B2010",
    "gypsum": "C1010",
    "plaster": "C1010",
    "roofing": "B3010",
    "flooring": "C3020",
    "carpet": "C3020",
    "tile": "C3020",
}

_MASTERFORMAT_CLASSIFICATIONS: dict[str, str] = {
    "concrete": "03 00 00",
    "steel": "05 00 00",
    "timber": "06 00 00",
    "wood": "06 00 00",
    "masonry": "04 00 00",
    "brick": "04 00 00",
    "glass": "08 80 00",
    "aluminum": "05 00 00",
    "insulation": "07 20 00",
    "gypsum": "09 20 00",
    "plaster": "09 20 00",
    "roofing": "07 50 00",
    "flooring": "09 60 00",
    "carpet": "09 68 00",
    "tile": "09 30 00",
}


class MaterialExtractor:
    """Extracts and processes material data from building elements.

    Supports duck-typed element objects that expose material_name,
    volume, area, mass, category, and level attributes.
    """

    def __init__(self, context: object | None = None) -> None:
        self._context = context
        logger.debug("MaterialExtractor initialized")

    def extract(self, elements: list[object]) -> list[MaterialData]:
        """Extract material information from building elements.

        Elements are duck-typed and should expose attributes such as
        ``material_name``, ``volume``, ``area``, ``mass``, ``category``,
        ``level``, ``element_id``, ``density``, and ``system``.

        Args:
            elements: Iterable of building element objects.

        Returns:
            List of MaterialData instances extracted from the elements.

        Raises:
            SustainabilityError: If extraction fails for an element.
        """
        materials: list[MaterialData] = []

        for elem in elements:
            try:
                name = getattr(elem, "material_name", None) or "Unknown"
                category = getattr(elem, "category", None) or "Uncategorized"
                volume = float(getattr(elem, "volume", 0.0) or 0.0)
                area = float(getattr(elem, "area", 0.0) or 0.0)
                mass = float(getattr(elem, "mass", 0.0) or 0.0)
                density = getattr(elem, "density", None)
                element_id = str(getattr(elem, "element_id", "")) or None
                level = getattr(elem, "level", None)
                system = getattr(elem, "system", None)

                if density is not None:
                    density = float(density)

                # Compute mass from volume and density when mass is missing.
                if mass == 0.0 and volume > 0.0 and density is not None:
                    mass = volume * density

                material = MaterialData(
                    name=name,
                    category=category,
                    volume_m3=volume,
                    area_m2=area,
                    mass_kg=mass,
                    density_kg_m3=density,
                    element_id=element_id,
                    level=str(level) if level is not None else None,
                    system=str(system) if system is not None else None,
                )
                materials.append(material)
                logger.trace(
                    "Extracted material: {} ({}kg)",
                    material.name,
                    material.mass_kg,
                )
            except (TypeError, ValueError) as exc:
                raise SustainabilityError(
                    f"Failed to extract material from element: {exc}",
                    cause=exc,
                ) from exc

        logger.info(
            "Extracted {} materials from {} elements",
            len(materials),
            len(elements),
        )
        return materials

    def aggregate(self, materials: list[MaterialData]) -> list[MaterialData]:
        """Aggregate material quantities by material name.

        Sums volume, area, and mass for materials sharing the same name.

        Args:
            materials: List of MaterialData to aggregate.

        Returns:
            Aggregated list with one entry per unique material name.
        """
        aggregated: dict[str, MaterialData] = {}

        for mat in materials:
            if mat.name in aggregated:
                existing = aggregated[mat.name]
                existing.volume_m3 += mat.volume_m3
                existing.area_m2 += mat.area_m2
                existing.mass_kg += mat.mass_kg
            else:
                aggregated[mat.name] = MaterialData(
                    name=mat.name,
                    category=mat.category,
                    volume_m3=mat.volume_m3,
                    area_m2=mat.area_m2,
                    mass_kg=mat.mass_kg,
                    density_kg_m3=mat.density_kg_m3,
                    element_id=None,
                    level=mat.level,
                    system=mat.system,
                )

        result = list(aggregated.values())
        logger.info(
            "Aggregated {} materials into {} groups",
            len(materials),
            len(result),
        )
        return result

    def classify(
        self,
        materials: list[MaterialData],
        system: str = "UniFormat",
    ) -> list[MaterialData]:
        """Add classification codes to materials.

        Args:
            materials: List of MaterialData to classify.
            system: Classification system name. Supported values are
                ``"UniFormat"`` and ``"MasterFormat"``.

        Returns:
            List of MaterialData with updated category fields that include
            classification codes.
        """
        if system == "MasterFormat":
            lookup = _MASTERFORMAT_CLASSIFICATIONS
        else:
            lookup = _UNIFFORMAT_CLASSIFICATIONS

        classified: list[MaterialData] = []
        for mat in materials:
            key = mat.name.lower().strip()
            code = None
            for keyword, classification in lookup.items():
                if keyword in key:
                    code = classification
                    break

            new_category = f"{mat.category} [{code}]" if code else mat.category
            classified.append(
                MaterialData(
                    name=mat.name,
                    category=new_category,
                    volume_m3=mat.volume_m3,
                    area_m2=mat.area_m2,
                    mass_kg=mat.mass_kg,
                    density_kg_m3=mat.density_kg_m3,
                    element_id=mat.element_id,
                    level=mat.level,
                    system=mat.system,
                )
            )

        logger.info(
            "Classified {} materials using {}",
            len(classified),
            system,
        )
        return classified
