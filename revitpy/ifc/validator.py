"""
IDS (Information Delivery Specification) validation for RevitPy.

Three levels of support are provided, and it is important to be clear
about what each one is:

1. :meth:`IdsValidator.validate` and JSON rule files are a **RevitPy
   rule set, inspired by IDS**. They check attributes/properties of
   in-memory RevitPy elements and are not a buildingSMART format.
2. :meth:`IdsValidator.load_ids_xml` (used by
   :meth:`IdsValidator.validate_from_file` for ``.ids`` / ``.xml``
   files) reads real **buildingSMART IDS 1.0 XML** and maps a subset of
   it onto that rule set: ``entity`` applicability plus ``attribute``
   and ``property`` requirement facets whose values are ``simpleValue``
   or ``xs:enumeration``. Other facets (``partOf``, ``classification``,
   ``material``), other restrictions (patterns, bounds, lengths),
   ``predefinedType``, ``dataType``, ``ifcVersion`` and specification
   cardinality are ignored (with a logged warning where applicable).
3. :meth:`IdsValidator.validate_ifc_file` performs **full IDS 1.0
   validation of an IFC file** by delegating to ``ifctester``
   (IfcOpenShell's IDS implementation, PyPI package ``ifctester``).
   Use it on files produced by :class:`~revitpy.ifc.IfcExporter` when
   standards conformance matters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET  # noqa: N817

from loguru import logger

from ._compat import require_ifcopenshell
from .exceptions import IdsValidationError
from .mapper import IfcElementMapper
from .types import IdsRequirement, IdsValidationResult

try:
    from defusedxml import DefusedXmlException
    from defusedxml.ElementTree import parse as _safe_parse

    _XML_ERRORS: tuple[type[Exception], ...] = (ET.ParseError, DefusedXmlException)
except ImportError:  # pragma: no cover - optional dependency
    _safe_parse = None
    _XML_ERRORS = (ET.ParseError,)

IDS_NS = "http://standards.buildingsmart.org/IDS"
XS_NS = "http://www.w3.org/2001/XMLSchema"


def _q(tag: str) -> str:
    """Qualify a tag name with the IDS namespace."""
    return f"{{{IDS_NS}}}{tag}"


def _localname(tag: str) -> str:
    """Strip the namespace from an element tag."""
    return tag.rsplit("}", 1)[-1]


def _parse_ids_value(el: ET.Element | None) -> tuple[str | None, list[str]]:
    """Parse an IDS ``idsValue`` element.

    Args:
        el: The value element (e.g. ``ids:name``, ``ids:value``) or None.

    Returns:
        ``(simple_value, enumeration_values)``. Both are empty/None when
        the element is absent or uses an unsupported restriction.
    """
    if el is None:
        return None, []

    simple = el.find(_q("simpleValue"))
    if simple is not None:
        return (simple.text or "").strip(), []

    restriction = el.find(f"{{{XS_NS}}}restriction")
    if restriction is not None:
        enums = [
            e.get("value", "") for e in restriction.findall(f"{{{XS_NS}}}enumeration")
        ]
        if enums:
            return None, enums
        logger.warning(
            "Unsupported IDS value restriction; only presence will be checked"
        )

    return None, []


class IdsValidator:
    """Validate elements against IDS-style requirements.

    See the module docstring for exactly which parts of buildingSMART IDS
    are supported by each method.
    """

    def __init__(self, mapper: IfcElementMapper | None = None) -> None:
        self._mapper = mapper or IfcElementMapper()
        self._custom_checkers: dict[str, Any] = {}

    def validate(
        self,
        elements: list[Any],
        requirements: list[IdsRequirement],
    ) -> list[IdsValidationResult]:
        """Validate elements against a list of requirements.

        Each element is checked against every requirement. A requirement
        is applicable when its ``entity_type`` is ``None``, equals the
        element's RevitPy type/category, or is an IFC entity name
        (e.g. ``IFCWALL``) that the element's type maps to.

        Args:
            elements: List of elements to validate. Each element should
                expose attributes such as ``id``, ``name``, and
                ``category`` (or a type name).
            requirements: List of requirements to check.

        Returns:
            List of IdsValidationResult for each element/requirement pair.
        """
        results: list[IdsValidationResult] = []

        for element in elements:
            element_type = self._get_element_type(element)
            element_id = getattr(element, "id", None)

            for requirement in requirements:
                results.append(
                    self._check_requirement(
                        element, element_type, element_id, requirement
                    )
                )

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

        ``.ids`` and ``.xml`` files are read as buildingSMART IDS 1.0 XML
        (see :meth:`load_ids_xml` for the supported subset). Any other
        file is read as a RevitPy JSON rule list whose objects have the
        fields ``name``, ``description``, ``entity_type``,
        ``property_name``, ``property_value``, ``required`` and,
        optionally, ``property_set``, ``allowed_values``, ``prohibited``.

        Args:
            elements: List of elements to validate.
            ids_path: Path to the IDS XML or JSON rule file.

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

        if ids_path.suffix.lower() in {".ids", ".xml"}:
            requirements = self.load_ids_xml(ids_path)
        else:
            requirements = self._load_json_rules(ids_path)

        return self.validate(elements, requirements)

    def load_ids_xml(self, ids_path: str | Path) -> list[IdsRequirement]:
        """Load requirements from a buildingSMART IDS 1.0 XML file.

        Supported: ``entity`` applicability (name as ``simpleValue`` or
        enumeration) and ``attribute`` / ``property`` requirement facets
        with ``simpleValue`` or ``xs:enumeration`` values and
        ``cardinality`` (required / optional / prohibited). Unsupported
        facets and restrictions are logged and ignored.

        Args:
            ids_path: Path to the IDS XML file.

        Returns:
            List of IdsRequirement objects.

        Raises:
            IdsValidationError: If the file cannot be parsed or is not an
                IDS document.
        """
        ids_path = Path(ids_path)
        try:
            if _safe_parse is not None:
                tree = _safe_parse(str(ids_path))
            else:  # pragma: no cover - defusedxml not installed
                tree = ET.parse(str(ids_path))  # noqa: S314
        except (*_XML_ERRORS, OSError) as exc:
            raise IdsValidationError(
                f"Failed to parse IDS file: {exc}",
                requirement_name=str(ids_path),
                cause=exc,
            ) from exc

        root = tree.getroot()
        if root.tag != _q("ids"):
            raise IdsValidationError(
                f"Not a buildingSMART IDS document: {ids_path}",
                requirement_name=str(ids_path),
            )

        requirements: list[IdsRequirement] = []
        for spec in root.iterfind(f"{_q('specifications')}/{_q('specification')}"):
            requirements.extend(self._spec_to_requirements(spec))

        logger.info(
            "Loaded {} requirements from IDS file {}", len(requirements), ids_path
        )
        return requirements

    def validate_ifc_file(
        self,
        ifc_path: str | Path,
        ids_path: str | Path,
    ) -> list[IdsValidationResult]:
        """Validate an IFC file against an IDS file using ifctester.

        This is full buildingSMART IDS 1.0 validation (all facets and
        restrictions) performed by ``ifctester``.

        Args:
            ifc_path: Path to the IFC file.
            ids_path: Path to the IDS XML file.

        Returns:
            One failed result per failing entity/facet, or one result per
            specification without entity failures carrying its overall
            status.

        Raises:
            ImportError: If ifcopenshell or ifctester is not installed.
            IdsValidationError: If a file is missing or validation fails.
        """
        require_ifcopenshell()
        try:
            import ifcopenshell
            from ifctester import ids as ifctester_ids
        except ImportError as exc:
            raise ImportError(
                "ifctester is required for IFC-file IDS validation. "
                "Install it with: pip install ifctester"
            ) from exc

        ifc_path = Path(ifc_path)
        ids_path = Path(ids_path)
        for label, file_path in (("IFC", ifc_path), ("IDS", ids_path)):
            if not file_path.exists():
                raise IdsValidationError(
                    f"{label} file not found: {file_path}",
                    requirement_name=str(file_path),
                )

        try:
            specs = ifctester_ids.open(str(ids_path))
            model = ifcopenshell.open(str(ifc_path))
            specs.validate(model)
        except Exception as exc:
            raise IdsValidationError(
                f"IDS validation failed: {exc}",
                requirement_name=str(ids_path),
                cause=exc,
            ) from exc

        results: list[IdsValidationResult] = []
        for spec in specs.specifications:
            requirement = IdsRequirement(
                name=spec.name,
                description=getattr(spec, "description", "") or "",
            )
            failures = 0
            for facet in getattr(spec, "requirements", None) or []:
                for failure in getattr(facet, "failures", None) or []:
                    element = failure.get("element")
                    results.append(
                        IdsValidationResult(
                            requirement=requirement,
                            passed=False,
                            entity_id=getattr(element, "GlobalId", None),
                            message=str(failure.get("reason", "")),
                        )
                    )
                    failures += 1

            if failures == 0:
                status = bool(getattr(spec, "status", True))
                results.append(
                    IdsValidationResult(
                        requirement=requirement,
                        passed=status,
                        message=(
                            "Specification passed" if status else "Specification failed"
                        ),
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _spec_to_requirements(spec: ET.Element) -> list[IdsRequirement]:
        """Convert one ``ids:specification`` into IdsRequirements."""
        spec_name = spec.get("name", "")
        spec_desc = spec.get("description", "")

        entity_types: list[str | None] = [None]
        applicability = spec.find(_q("applicability"))
        if applicability is not None:
            for child in applicability:
                localname = _localname(child.tag)
                if localname == "entity":
                    value, options = _parse_ids_value(child.find(_q("name")))
                    names = [value] if value else options
                    if names:
                        entity_types = [n.upper() for n in names]
                else:
                    logger.warning(
                        "IDS applicability facet {} in {!r} is not supported "
                        "for element validation; ignored",
                        localname,
                        spec_name,
                    )

        req_el = spec.find(_q("requirements"))
        facets = list(req_el) if req_el is not None else []
        if not facets:
            return [
                IdsRequirement(name=spec_name, description=spec_desc, entity_type=et)
                for et in entity_types
            ]

        requirements: list[IdsRequirement] = []
        for facet in facets:
            localname = _localname(facet.tag)
            if localname == "attribute":
                pset: str | None = None
                name_value, _ = _parse_ids_value(facet.find(_q("name")))
            elif localname == "property":
                pset, _ = _parse_ids_value(facet.find(_q("propertySet")))
                name_value, _ = _parse_ids_value(facet.find(_q("baseName")))
            else:
                logger.warning(
                    "IDS requirement facet {} in {!r} is not supported; ignored",
                    localname,
                    spec_name,
                )
                continue

            if not name_value:
                logger.warning(
                    "IDS {} name in {!r} must be a simpleValue; ignored",
                    localname,
                    spec_name,
                )
                continue

            value, allowed = _parse_ids_value(facet.find(_q("value")))
            cardinality = facet.get("cardinality", "required")
            prohibited = cardinality == "prohibited"
            required = cardinality not in {"optional", "prohibited"}

            label = f"{pset}.{name_value}" if pset else name_value
            for et in entity_types:
                requirements.append(
                    IdsRequirement(
                        name=f"{spec_name}: {localname} {label}",
                        description=spec_desc,
                        entity_type=et,
                        property_name=name_value,
                        property_value=value,
                        required=required,
                        property_set=pset,
                        allowed_values=allowed,
                        prohibited=prohibited,
                        facet=localname,
                    )
                )
        return requirements

    @staticmethod
    def _load_json_rules(path: Path) -> list[IdsRequirement]:
        """Load the RevitPy JSON rule format."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise IdsValidationError(
                f"Failed to parse IDS file: {exc}",
                requirement_name=str(path),
                cause=exc,
            ) from exc

        if not isinstance(data, list):
            raise IdsValidationError(
                "Failed to parse IDS file: expected a JSON list of requirements",
                requirement_name=str(path),
            )

        return [
            IdsRequirement(
                name=req.get("name", ""),
                description=req.get("description", ""),
                entity_type=req.get("entity_type"),
                property_name=req.get("property_name"),
                property_value=req.get("property_value"),
                required=req.get("required", True),
                property_set=req.get("property_set"),
                allowed_values=list(req.get("allowed_values", [])),
                prohibited=bool(req.get("prohibited", False)),
            )
            for req in data
            if isinstance(req, Mapping)
        ]

    @staticmethod
    def _get_element_type(element: Any) -> str:
        """Derive a type string from an element."""
        # Prefer a 'category' attribute, fall back to class name.
        category = getattr(element, "category", None)
        if category and isinstance(category, str):
            return category
        return type(element).__name__

    def _applies(self, entity_type: str, element: Any, element_type: str) -> bool:
        """Return True if a requirement's entity_type matches the element."""
        if entity_type == element_type:
            return True
        wanted = entity_type.upper()
        if not wanted.startswith("IFC"):
            return False
        mapped = self._mapper.get_ifc_type(element_type)
        if mapped is not None and mapped.upper() == wanted:
            return True
        ifc_type = getattr(element, "ifc_type", None)
        return isinstance(ifc_type, str) and ifc_type.upper() == wanted

    @staticmethod
    def _get_value(element: Any, requirement: IdsRequirement) -> Any:
        """Look up a requirement's property/attribute value on an element."""
        name = requirement.property_name or ""
        props: Mapping[str, Any] | None = None
        for attr in ("properties", "parameters"):
            candidate = getattr(element, attr, None)
            if isinstance(candidate, Mapping):
                props = candidate
                break

        if requirement.property_set and props is not None:
            pset = props.get(requirement.property_set)
            if isinstance(pset, Mapping) and name in pset:
                return pset[name]

        value = getattr(element, name, None)
        if value is None and name.lower() != name:
            value = getattr(element, name.lower(), None)
        if value is None and props is not None and name in props:
            value = props[name]
        return value

    def _check_requirement(
        self,
        element: Any,
        element_type: str,
        element_id: Any,
        requirement: IdsRequirement,
    ) -> IdsValidationResult:
        """Check a single requirement against an element."""

        def result(
            passed: bool, message: str, actual: Any = None
        ) -> IdsValidationResult:
            return IdsValidationResult(
                requirement=requirement,
                passed=passed,
                entity_id=element_id,
                actual_value=actual,
                message=message,
            )

        if requirement.entity_type and not self._applies(
            requirement.entity_type, element, element_type
        ):
            return result(True, "Requirement not applicable to this entity type")

        name = requirement.property_name
        if not name:
            return result(True, "No property check specified")

        actual = self._get_value(element, requirement)

        if requirement.prohibited:
            if actual is None:
                return result(True, "Prohibited property absent")
            return result(False, f"Prohibited property '{name}' is present", actual)

        if actual is None:
            if requirement.required:
                return result(False, f"Required property '{name}' is missing")
            return result(True, f"Optional property '{name}' not present")

        if requirement.allowed_values:
            if str(actual) in requirement.allowed_values:
                return result(True, "Property value matches", actual)
            return result(
                False,
                f"Expected one of {requirement.allowed_values}, got '{actual}'",
                actual,
            )

        if requirement.property_value is not None:
            if str(actual) == str(requirement.property_value):
                return result(True, "Property value matches", actual)
            return result(
                False,
                f"Expected '{requirement.property_value}', got '{actual}'",
                actual,
            )

        return result(True, "Property exists", actual)
