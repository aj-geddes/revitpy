"""Tests for buildingSMART IDS 1.0 XML support in IdsValidator."""

from types import SimpleNamespace

import pytest

from revitpy.ifc.exceptions import IdsValidationError
from revitpy.ifc.validator import IdsValidator

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<ids:ids xmlns:ids="http://standards.buildingsmart.org/IDS" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="http://standards.buildingsmart.org/IDS '
    'http://standards.buildingsmart.org/IDS/1.0/ids.xsd">\n'
    "<ids:info><ids:title>RevitPy test</ids:title></ids:info>\n"
)


def _entity(name):
    return (
        '<ids:applicability minOccurs="0" maxOccurs="unbounded"><ids:entity>'
        f"<ids:name><ids:simpleValue>{name}</ids:simpleValue></ids:name>"
        "</ids:entity></ids:applicability>"
    )


IDS_XML = (
    _HEADER
    + "<ids:specifications>"
    + '<ids:specification name="Walls have fire rating" ifcVersion="IFC4">'
    + _entity("IFCWALL")
    + "<ids:requirements>"
    + '<ids:property dataType="IFCLABEL" cardinality="required">'
    + "<ids:propertySet><ids:simpleValue>Pset_WallCommon</ids:simpleValue>"
    + "</ids:propertySet>"
    + "<ids:baseName><ids:simpleValue>FireRating</ids:simpleValue></ids:baseName>"
    + '<ids:value><xs:restriction base="xs:string">'
    + '<xs:enumeration value="60"/><xs:enumeration value="90"/>'
    + "</xs:restriction></ids:value></ids:property>"
    + '<ids:attribute cardinality="required"><ids:name>'
    + "<ids:simpleValue>Name</ids:simpleValue></ids:name></ids:attribute>"
    + '<ids:property cardinality="prohibited">'
    + "<ids:propertySet><ids:simpleValue>Pset_WallCommon</ids:simpleValue>"
    + "</ids:propertySet>"
    + "<ids:baseName><ids:simpleValue>Legacy</ids:simpleValue></ids:baseName>"
    + "</ids:property>"
    + "</ids:requirements></ids:specification>"
    + '<ids:specification name="Doors are 0.9 wide" ifcVersion="IFC4">'
    + _entity("IFCDOOR")
    + '<ids:requirements><ids:attribute cardinality="optional">'
    + "<ids:name><ids:simpleValue>OverallWidth</ids:simpleValue></ids:name>"
    + "<ids:value><ids:simpleValue>0.9</ids:simpleValue></ids:value>"
    + "</ids:attribute></ids:requirements></ids:specification>"
    + "</ids:specifications></ids:ids>"
)

GOOD_WALL = SimpleNamespace(
    id=1,
    name="W1",
    category="WallElement",
    properties={"Pset_WallCommon": {"FireRating": "60"}},
)
BAD_WALL = SimpleNamespace(
    id=2,
    name="W2",
    category="WallElement",
    properties={"Pset_WallCommon": {"FireRating": "30", "Legacy": "x"}},
)
DOOR = SimpleNamespace(id=3, name="D", category="DoorElement", overallwidth=0.9)
DOOR_NO_WIDTH = SimpleNamespace(id=4, name="D2", category="DoorElement")


@pytest.fixture
def ids_file(tmp_path):
    path = tmp_path / "rules.ids"
    path.write_text(IDS_XML, encoding="utf-8")
    return path


def _for(results, entity_id):
    return [r for r in results if r.entity_id == entity_id]


def test_load_ids_xml_parses_facets(ids_file):
    reqs = IdsValidator().load_ids_xml(ids_file)
    assert len(reqs) == 4
    by_name = {r.property_name: r for r in reqs}

    fire = by_name["FireRating"]
    assert fire.entity_type == "IFCWALL"
    assert fire.property_set == "Pset_WallCommon"
    assert fire.allowed_values == ["60", "90"]
    assert fire.required is True
    assert fire.facet == "property"

    legacy = by_name["Legacy"]
    assert legacy.prohibited is True
    assert legacy.required is False

    assert by_name["Name"].facet == "attribute"

    width = by_name["OverallWidth"]
    assert width.entity_type == "IFCDOOR"
    assert width.required is False
    assert width.property_value == "0.9"


def test_ifc_entity_applicability_uses_mapper(ids_file):
    results = IdsValidator().validate_from_file([GOOD_WALL, DOOR], ids_file)
    door_vs_wall = [
        r for r in _for(results, 3) if r.requirement.entity_type == "IFCWALL"
    ]
    assert len(door_vs_wall) == 3
    assert all(
        r.message == "Requirement not applicable to this entity type"
        for r in door_vs_wall
    )


def test_good_wall_passes_all(ids_file):
    results = IdsValidator().validate_from_file([GOOD_WALL], ids_file)
    assert results
    assert all(r.passed for r in results)


def test_bad_wall_fails_enumeration_and_prohibited(ids_file):
    results = IdsValidator().validate_from_file([BAD_WALL], ids_file)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 2
    messages = " | ".join(r.message for r in failures)
    assert "Expected one of" in messages
    assert "Prohibited property 'Legacy' is present" in messages


def test_optional_attribute(ids_file):
    results = IdsValidator().validate_from_file([DOOR_NO_WIDTH, DOOR], ids_file)

    (missing,) = [
        r for r in _for(results, 4) if r.requirement.property_name == "OverallWidth"
    ]
    assert missing.passed
    assert missing.message.startswith("Optional property")

    (present,) = [
        r for r in _for(results, 3) if r.requirement.property_name == "OverallWidth"
    ]
    assert present.passed
    assert present.message == "Property value matches"


def test_not_ids_document_raises(tmp_path):
    path = tmp_path / "x.ids"
    path.write_text("<root/>", encoding="utf-8")
    with pytest.raises(IdsValidationError, match="Not a buildingSMART IDS"):
        IdsValidator().load_ids_xml(path)


def test_malformed_xml_raises(tmp_path):
    path = tmp_path / "bad.xml"
    path.write_text("<ids:ids", encoding="utf-8")
    with pytest.raises(IdsValidationError, match="Failed to parse"):
        IdsValidator().validate_from_file([GOOD_WALL], path)


def test_unsupported_facets_are_ignored(tmp_path):
    xml = (
        _HEADER
        + '<ids:specifications><ids:specification name="S" ifcVersion="IFC4">'
        + '<ids:applicability minOccurs="0" maxOccurs="unbounded">'
        + "<ids:entity><ids:name><ids:simpleValue>IFCWALL</ids:simpleValue>"
        + "</ids:name></ids:entity>"
        + "<ids:classification><ids:system><ids:simpleValue>Uniclass"
        + "</ids:simpleValue></ids:system></ids:classification>"
        + "</ids:applicability><ids:requirements>"
        + "<ids:material/>"
        + '<ids:attribute cardinality="required"><ids:name>'
        + "<ids:simpleValue>Name</ids:simpleValue></ids:name></ids:attribute>"
        + "</ids:requirements></ids:specification></ids:specifications></ids:ids>"
    )
    path = tmp_path / "unsupported.ids"
    path.write_text(xml, encoding="utf-8")

    (req,) = IdsValidator().load_ids_xml(path)
    assert req.property_name == "Name"
    assert req.entity_type == "IFCWALL"


def test_validate_ifc_file_with_ifctester(tmp_path, ids_file):
    pytest.importorskip("ifcopenshell")
    pytest.importorskip("ifctester")
    from revitpy.ifc import IfcExporter

    ifc_path = tmp_path / "m.ifc"
    IfcExporter().export(
        [SimpleNamespace(id=1, name="W1", category="WallElement")], ifc_path
    )

    results = IdsValidator().validate_ifc_file(ifc_path, ids_file)

    fire = [r for r in results if r.requirement.name == "Walls have fire rating"]
    assert fire
    assert any(not r.passed for r in fire)
    for r in fire:
        if not r.passed and r.entity_id is not None:
            assert isinstance(r.entity_id, str)
            assert len(r.entity_id) == 22

    doors = [r for r in results if r.requirement.name == "Doors are 0.9 wide"]
    assert doors
    assert all(r.passed for r in doors)


def test_validate_ifc_file_missing_file(tmp_path, ids_file):
    pytest.importorskip("ifcopenshell")
    pytest.importorskip("ifctester")
    with pytest.raises(IdsValidationError, match="not found"):
        IdsValidator().validate_ifc_file(tmp_path / "missing.ifc", ids_file)


def test_validate_ifc_file_requires_ifcopenshell(tmp_path, ids_file, monkeypatch):
    def _missing():
        raise ImportError("ifcopenshell is required")

    monkeypatch.setattr("revitpy.ifc.validator.require_ifcopenshell", _missing)
    with pytest.raises(ImportError):
        IdsValidator().validate_ifc_file(tmp_path / "m.ifc", ids_file)
