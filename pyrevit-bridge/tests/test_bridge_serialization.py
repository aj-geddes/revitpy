"""Serialization of (fake) Revit elements by the pyRevit-side module."""

from __future__ import annotations

import json
from typing import Any

from bridge_fakes import (
    XYZ,
    BoundingBox,
    Curve,
    Element,
    ElementId,
    LocationCurve,
    LocationPoint,
    Parameter,
    make_wall,
)
from revitpy_bridge import element_id_value, serialize_element, serialize_elements


def test_wall() -> None:
    data = serialize_element(make_wall(316104))
    json.dumps(data, allow_nan=False)
    assert data["id"] == 316104
    assert data["unique_id"] == "uid-316104"
    assert data["category"] == "Walls"
    assert data["type_name"] == 'Generic - 8"'
    assert data["level"] == "Level 1"
    assert data["units"] == "ft"

    params = data["parameters"]
    assert params["Area"] == {
        "storage_type": "Double",
        "value": 300.0,
        "display": "300.00 SF",
        "builtin": "HOST_AREA_COMPUTED",
        "data_type": "autodesk.spec.aec:area-2.0.0",
        "read_only": True,
    }
    assert params["Mark"]["value"] == "W-1"
    assert params["Mark"]["storage_type"] == "String"
    assert params["Structural"]["value"] == 0
    assert params["Structural"]["display"] == "No"
    assert params["Base Constraint"]["value"] == 3001
    assert params["Base Constraint"]["builtin"] is None  # INVALID
    assert params["Base Constraint"]["data_type"] is None

    assert data["location"] == {
        "type": "curve",
        "start": [0.0, 0.0, 0.0],
        "end": [30.0, 0.0, 0.0],
        "length": 30.0,
    }
    assert data["bounding_box"] == {
        "min": [-0.33, -0.33, 0.0],
        "max": [30.33, 0.33, 10.0],
    }
    assert data["materials"] == [
        {
            "id": 4001,
            "name": "Concrete, Cast-in-Place",
            "material_class": "Concrete",
            "volume": 200.0,
            "area": 600.0,
        }
    ]


def test_element_id_value() -> None:
    assert element_id_value(ElementId(7)) == 7
    assert element_id_value(ElementId(8, legacy=True)) == 8
    assert element_id_value(None) is None
    assert element_id_value(object()) is None


def test_legacy_ids_and_missing_document_links() -> None:
    element = Element(ElementId(42, legacy=True), name="Thing")
    data = serialize_element(element)
    assert data["id"] == 42
    assert data["category"] is None
    assert data["type_name"] is None
    assert data["level"] is None
    assert data["location"] is None
    assert data["bounding_box"] is None
    assert data["materials"] == []
    assert data["parameters"] == {}


def test_parameter_edge_cases() -> None:
    element = Element(
        1,
        parameters=[
            Parameter("Comments", "String", None, has_value=False),
            Parameter("Nothing", "None", None),
            Parameter("Dup", "Double", 1.0),
            Parameter("Dup", "Double", 2.0),
            Parameter("Precise", "Double", 1.23456789),
            Parameter("No Builtin Attr", "Integer", 3, builtin=None),
        ],
    )
    params = serialize_element(element)["parameters"]
    assert params["Comments"]["value"] is None
    assert "Nothing" not in params
    assert params["Dup"]["value"] == 1.0
    assert params["Precise"]["value"] == 1.234568
    assert params["No Builtin Attr"]["builtin"] is None


class Exploding(Element):
    """Properties that throw, as some Revit elements do."""

    @property
    def Name(self) -> str:
        raise RuntimeError("no name")

    @Name.setter
    def Name(self, value: Any) -> None:
        pass

    def get_BoundingBox(self, view: Any) -> Any:
        raise RuntimeError("no box")

    def GetMaterialIds(self, paint: bool) -> Any:
        raise RuntimeError("no materials")


class PointRaises:
    """A LocationCurve-like object whose Point access throws."""

    def __init__(self) -> None:
        self.Curve = Curve(XYZ(0, 0, 0), XYZ(1, 1, 0), 1.414)

    @property
    def Point(self) -> Any:
        raise RuntimeError("not a point location")


def test_failing_properties_do_not_fail_the_element() -> None:
    data = serialize_element(
        Exploding(5, category="Generic Models", location=PointRaises())
    )
    assert data["id"] == 5
    assert data["name"] is None
    assert data["category"] == "Generic Models"
    assert data["bounding_box"] is None
    assert data["materials"] == []
    assert data["location"]["type"] == "curve"
    assert data["location"]["length"] == 1.414


def test_point_location() -> None:
    element = Element(3, location=LocationPoint(XYZ(1.5, 2.5, 3.5)))
    assert serialize_element(element)["location"] == {
        "type": "point",
        "point": [1.5, 2.5, 3.5],
    }


def test_curve_location_type() -> None:
    element = Element(4, location=LocationCurve(Curve(XYZ(0, 0, 0), XYZ(0, 5, 0), 5)))
    assert serialize_element(element)["location"]["end"] == [0.0, 5.0, 0.0]


def test_include_flags() -> None:
    wall = make_wall(9)
    data = serialize_element(
        wall, include_parameters=False, include_materials=False, include_geometry=False
    )
    for key in ("parameters", "materials", "location", "bounding_box"):
        assert key not in data
    assert data["id"] == 9
    many = serialize_elements(
        [wall, Element(10, bounding_box=BoundingBox(XYZ(0, 0, 0), XYZ(1, 1, 1)))]
    )
    assert [item["id"] for item in many] == [9, 10]
