"""
IDS (Information Delivery Specification) validator for RevitPy.

This module provides the IdsValidator class for checking element
properties against IDS requirements, supporting both programmatic
and file-based requirement definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from .exceptions import IdsValidationError
from .types import IdsRequirement, IdsValidationResult


class IdsValidator:
    """Validate elements against IDS requirements.

    Checks that elements satisfy a set of IDS requirements by inspecting
    their properties and comparing against expected values.
    """

    def __init__(self) -> None:
        self._custom_checkers: dict[str, Any] = {}

    def validate(
        self,
        elements: list[Any],
        requirements: list[IdsRequirement],
    ) -> list[IdsValidationResult]:
        """Validate elements against a list of IDS requirements.

        Each element is checked against every applicable requirement.
        A requirement is applicable when its ``entity_type`` is ``None``
        or matches the element's type.

        Args:
            elements: List of elements to validate. Each element should
                expose attributes such as ``id``, ``name``, and
                ``category`` (or a type name).
            requirements: List of IDS requirements to check.

        Returns:
            List of IdsValidationResult for each element/requirement pair.
        """
        results: list[IdsValidationResult] = []

        for element in elements:
            element_type = self._get_element_type(element)
            element_id = getattr(element, "id", None)

            for requirement in requirements:
                result = self._check_requirement(
                    element, element_type, element_id, requirement
                )
                results.append(result)

        passed = sum(1 for r in results if r.passed)
        logger.info(
            "IDS validation: {}/{} checks passed",
            passed,
            len(results),
        )
        return results

    def validate_from_file(
        self,
        elements: list[Any],
        ids_path: str | Path,
    ) -> list[IdsValidationResult]:
        """Validate elements against requirements loaded from a file.

        The file should be a JSON file containing a list of requirement
        objects with the fields: ``name``, ``description``,
        ``entity_type``, ``property_name``, ``property_value``,
        ``required``.

        Args:
            elements: List of elements to validate.
            ids_path: Path to the IDS requirements JSON file.

        Returns:
            List of IdsValidationResult.

        Raises:
            IdsValidationError: If the file cannot be read or parsed.
        """
        ids_path = Path(ids_path)

        if not ids_path.exists():
            raise IdsValidationError(
                f"IDS file not found: {ids_path}",
                requirement_name=str(ids_path),
            )

        try:
            data = json.loads(ids_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise IdsValidationError(
                f"Failed to parse IDS file: {exc}",
                requirement_name=str(ids_path),
                cause=exc,
            ) from exc

        requirements = [
            IdsRequirement(
                name=req.get("name", ""),
                description=req.get("description", ""),
                entity_type=req.get("entity_type"),
                property_name=req.get("property_name"),
                property_value=req.get("property_value"),
                required=req.get("required", True),
            )
            for req in data
        ]

        return self.validate(elements, requirements)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_element_type(element: Any) -> str:
        """Derive a type string from an element."""
        # Prefer a 'category' attribute, fall back to class name.
        category = getattr(element, "category", None)
        if category and isinstance(category, str):
            return category
        return type(element).__name__

    def _check_requirement(
        self,
        element: Any,
        element_type: str,
        element_id: Any,
        requirement: IdsRequirement,
    ) -> IdsValidationResult:
        """Check a single requirement against an element."""
        # If the requirement specifies an entity_type, skip non-matching
        if requirement.entity_type and requirement.entity_type != element_type:
            return IdsValidationResult(
                requirement=requirement,
                passed=True,
                entity_id=element_id,
                message="Requirement not applicable to this entity type",
            )

        # If no property to check, the requirement passes
        if not requirement.property_name:
            return IdsValidationResult(
                requirement=requirement,
                passed=True,
                entity_id=element_id,
                message="No property check specified",
            )

        actual_value = getattr(element, requirement.property_name, None)

        # Check if property exists
        if actual_value is None and requirement.required:
            return IdsValidationResult(
                requirement=requirement,
                passed=False,
                entity_id=element_id,
                actual_value=None,
                message=(f"Required property '{requirement.property_name}' is missing"),
            )

        # Check property value if expected value is specified
        if requirement.property_value is not None:
            passed = str(actual_value) == str(requirement.property_value)
            message = (
                "Property value matches"
                if passed
                else (f"Expected '{requirement.property_value}', got '{actual_value}'")
            )
            return IdsValidationResult(
                requirement=requirement,
                passed=passed,
                entity_id=element_id,
                actual_value=actual_value,
                message=message,
            )

        # Property exists and no specific value required
        return IdsValidationResult(
            requirement=requirement,
            passed=True,
            entity_id=element_id,
            actual_value=actual_value,
            message="Property exists",
        )
