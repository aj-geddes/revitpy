"""
Material takeoff extraction for RevitPy.

This module provides the MaterialTakeoff class for extracting material
data from Revit elements, aggregating by material, and classifying
materials against industry standard systems (UniFormat, MasterFormat).
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .exceptions import ExtractionError
from .types import MaterialQuantity

# Classification mappings for common materials
_CLASSIFICATION_MAP: dict[str, dict[str, str]] = {
    "UniFormat": {
        "concrete": "A1010",
        "steel": "A1020",
        "wood": "A1030",
        "masonry": "A1040",
        "glass": "B2020",
        "aluminum": "B2010",
        "gypsum": "C1010",
        "insulation": "C1020",
        "carpet": "C3020",
        "tile": "C3010",
        "paint": "C3030",
        "roofing": "B3010",
        "waterproofing": "B1020",
        "brick": "A1040",
        "stone": "A1050",
        "plaster": "C1030",
        "copper": "B2030",
        "asphalt": "G2020",
        "gravel": "G2010",
    },
    "MasterFormat": {
        "concrete": "03 00 00",
        "steel": "05 00 00",
        "wood": "06 00 00",
        "masonry": "04 00 00",
        "glass": "08 80 00",
        "aluminum": "08 40 00",
        "gypsum": "09 20 00",
        "insulation": "07 20 00",
        "carpet": "09 68 00",
        "tile": "09 30 00",
        "paint": "09 90 00",
        "roofing": "07 50 00",
        "waterproofing": "07 10 00",
        "brick": "04 20 00",
        "stone": "04 40 00",
        "plaster": "09 20 00",
        "copper": "05 50 00",
        "asphalt": "32 10 00",
        "gravel": "31 00 00",
    },
}


class MaterialTakeoff:
    """Extract and process material quantities from Revit elements.

    Elements are duck-typed objects with optional material_name,
    material_volume, material_area, material_mass, and category attributes.
    """

    def __init__(self, context: Any | None = None) -> None:
        self._context = context

    def extract(self, elements: list[Any]) -> list[MaterialQuantity]:
        """Extract material data from elements.

        Args:
            elements: List of duck-typed element objects.

        Returns:
            List of MaterialQuantity instances.

        Raises:
            ExtractionError: If extraction fails.
        """
        materials: list[MaterialQuantity] = []

        for element in elements:
            try:
                material = self._extract_element(element)
                if material is not None:
                    materials.append(material)
            except Exception as exc:
                element_id = getattr(element, "id", None)
                logger.warning(
                    "Failed to extract material from element {}: {}",
                    element_id,
                    exc,
                )
                raise ExtractionError(
                    f"Failed to extract material from element {element_id}",
                    operation="material_extraction",
                    element_id=element_id,
                    cause=exc,
                ) from exc

        logger.debug(
            "Extracted {} material records from {} elements",
            len(materials),
            len(elements),
        )
        return materials

    def _extract_element(self, element: Any) -> MaterialQuantity | None:
        """Extract material data from a single element."""
        material_name = getattr(element, "material_name", None)
        if material_name is None:
            material_name = getattr(element, "material", None)

        if material_name is None:
            return None

        category = str(getattr(element, "category", "Uncategorized"))
        volume = self._safe_float(getattr(element, "material_volume", None))
        area = self._safe_float(getattr(element, "material_area", None))
        mass = self._safe_float(getattr(element, "material_mass", None))

        # If no quantity attributes, try generic ones
        if volume == 0.0 and area == 0.0 and mass == 0.0:
            volume = self._safe_float(getattr(element, "volume", None))
            area = self._safe_float(getattr(element, "area", None))

        return MaterialQuantity(
            material_name=str(material_name),
            category=category,
            volume=volume,
            area=area,
            mass=mass,
        )

    def aggregate(self, materials: list[MaterialQuantity]) -> list[MaterialQuantity]:
        """Aggregate material quantities by material name.

        Sums volume, area, and mass for each unique material.

        Args:
            materials: List of MaterialQuantity instances.

        Returns:
            Aggregated list with one entry per unique material name.
        """
        aggregated: dict[str, MaterialQuantity] = {}

        for mat in materials:
            key = mat.material_name
            if key in aggregated:
                existing = aggregated[key]
                aggregated[key] = MaterialQuantity(
                    material_name=existing.material_name,
                    category=existing.category,
                    volume=existing.volume + mat.volume,
                    area=existing.area + mat.area,
                    mass=existing.mass + mat.mass,
                    classification_code=existing.classification_code,
                    classification_system=existing.classification_system,
                )
            else:
                aggregated[key] = MaterialQuantity(
                    material_name=mat.material_name,
                    category=mat.category,
                    volume=mat.volume,
                    area=mat.area,
                    mass=mat.mass,
                    classification_code=mat.classification_code,
                    classification_system=mat.classification_system,
                )

        logger.debug(
            "Aggregated {} materials into {} unique materials",
            len(materials),
            len(aggregated),
        )
        return list(aggregated.values())

    def classify(
        self,
        materials: list[MaterialQuantity],
        system: str = "UniFormat",
    ) -> list[MaterialQuantity]:
        """Classify materials against a standard system.

        Maps material names to classification codes using a built-in
        lookup table. Unrecognized materials retain empty codes.

        Args:
            materials: List of MaterialQuantity instances.
            system: Classification system name ("UniFormat" or "MasterFormat").

        Returns:
            New list with classification_code and classification_system set.
        """
        code_map = _CLASSIFICATION_MAP.get(system, {})
        classified: list[MaterialQuantity] = []

        for mat in materials:
            lookup_key = mat.material_name.lower().strip()
            code = code_map.get(lookup_key, "")

            # Try partial matching if exact match not found
            if not code:
                for material_key, material_code in code_map.items():
                    if material_key in lookup_key or lookup_key in material_key:
                        code = material_code
                        break

            classified.append(
                MaterialQuantity(
                    material_name=mat.material_name,
                    category=mat.category,
                    volume=mat.volume,
                    area=mat.area,
                    mass=mat.mass,
                    classification_code=code,
                    classification_system=system if code else "",
                )
            )

        logger.debug(
            "Classified {} materials using {} system",
            len(materials),
            system,
        )
        return classified

    @staticmethod
    def _safe_float(value: Any) -> float:
        """Safely convert a value to float, returning 0.0 on failure."""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
