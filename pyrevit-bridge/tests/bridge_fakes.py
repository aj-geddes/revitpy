"""Duck-typed stand-ins for the Revit API objects revitpy_bridge serializes."""

from __future__ import annotations

from typing import Any


class NetEnum:
    """Prints like a .NET enum value seen from IronPython/pythonnet."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return self._name


class ElementId:
    """Revit 2024+ id (``Value``) or, with ``legacy=True``, pre-2024 (``IntegerValue``)."""

    def __init__(self, value: int, legacy: bool = False) -> None:
        if legacy:
            self.IntegerValue = value
        else:
            self.Value = value
            self.IntegerValue = value  # still present (deprecated) in 2024+


INVALID_ID = ElementId(-1)


class XYZ:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.X, self.Y, self.Z = x, y, z


class DataType:
    def __init__(self, type_id: str) -> None:
        self.TypeId = type_id


class Definition:
    def __init__(
        self, name: str, builtin: str | None = None, data_type: str = ""
    ) -> None:
        self.Name = name
        if builtin is not None:
            self.BuiltInParameter = NetEnum(builtin)
        self._data_type = data_type

    def GetDataType(self) -> DataType:
        return DataType(self._data_type)


class Parameter:
    def __init__(
        self,
        name: str,
        storage: str,
        value: Any,
        *,
        display: str | None = None,
        builtin: str | None = "INVALID",
        data_type: str = "",
        read_only: bool = False,
        has_value: bool = True,
    ) -> None:
        self.Definition = Definition(name, builtin, data_type)
        self.StorageType = NetEnum(storage)
        self.HasValue = has_value
        self.IsReadOnly = read_only
        self._value = value
        self._display = display

    def AsDouble(self) -> float:
        return float(self._value)

    def AsInteger(self) -> int:
        return int(self._value)

    def AsString(self) -> str | None:
        return self._value

    def AsElementId(self) -> ElementId:
        return self._value

    def AsValueString(self) -> str | None:
        return self._display


class Category:
    def __init__(self, name: str) -> None:
        self.Name = name


class Named:
    """A type, level or material element: only ``Name`` (and maybe a class)."""

    def __init__(self, name: str, material_class: str | None = None) -> None:
        self.Name = name
        if material_class is not None:
            self.MaterialClass = material_class


class LocationPoint:
    def __init__(self, point: XYZ) -> None:
        self.Point = point


class Curve:
    def __init__(self, start: XYZ, end: XYZ, length: float) -> None:
        self._points = (start, end)
        self.Length = length

    def GetEndPoint(self, index: int) -> XYZ:
        return self._points[index]


class LocationCurve:
    def __init__(self, curve: Curve) -> None:
        self.Curve = curve


class BoundingBox:
    def __init__(self, low: XYZ, high: XYZ) -> None:
        self.Min, self.Max = low, high


class Document:
    def __init__(self) -> None:
        self._elements: dict[int, Any] = {}

    def add(self, element_id: int, element: Any) -> ElementId:
        self._elements[element_id] = element
        return ElementId(element_id)

    def GetElement(self, element_id: ElementId) -> Any:
        return self._elements.get(getattr(element_id, "Value", None))


class Element:
    """A Revit element; pass only what a test needs."""

    def __init__(
        self,
        element_id: int | ElementId,
        *,
        document: Document | None = None,
        name: str | None = None,
        category: str | None = None,
        unique_id: str | None = None,
        type_id: ElementId | None = None,
        level_id: ElementId | None = None,
        parameters: list[Parameter] | None = None,
        location: Any = None,
        bounding_box: BoundingBox | None = None,
        materials: dict[int, tuple[float, float]] | None = None,
    ) -> None:
        self.Id = (
            element_id if isinstance(element_id, ElementId) else ElementId(element_id)
        )
        self.Document = document or Document()
        self.Name = name
        self.Category = Category(category) if category else None
        self.UniqueId = unique_id
        self._type_id = type_id or INVALID_ID
        self.LevelId = level_id or INVALID_ID
        self.Parameters = parameters or []
        self.Location = location
        self._bounding_box = bounding_box
        self._materials = materials or {}

    def GetTypeId(self) -> ElementId:
        return self._type_id

    def get_BoundingBox(self, view: Any) -> BoundingBox | None:
        return self._bounding_box

    def GetMaterialIds(self, paint: bool) -> list[ElementId]:
        return [ElementId(key) for key in self._materials]

    def GetMaterialVolume(self, material_id: ElementId) -> float:
        return self._materials[material_id.Value][0]

    def GetMaterialArea(self, material_id: ElementId, paint: bool) -> float:
        return self._materials[material_id.Value][1]


def make_wall(element_id: int = 316104, x0: float = 0.0) -> Element:
    """A 30 ft generic wall on Level 1 with one concrete material."""
    doc = Document()
    type_id = doc.add(2001, Named('Generic - 8"'))
    level_id = doc.add(3001, Named("Level 1"))
    doc.add(4001, Named("Concrete, Cast-in-Place", "Concrete"))
    return Element(
        element_id,
        document=doc,
        name='Generic - 8"',
        category="Walls",
        unique_id=f"uid-{element_id}",
        type_id=type_id,
        level_id=level_id,
        parameters=[
            Parameter(
                "Area",
                "Double",
                300.0,
                display="300.00 SF",
                builtin="HOST_AREA_COMPUTED",
                data_type="autodesk.spec.aec:area-2.0.0",
                read_only=True,
            ),
            Parameter(
                "Volume",
                "Double",
                200.0,
                display="200.00 CF",
                builtin="HOST_VOLUME_COMPUTED",
                data_type="autodesk.spec.aec:volume-2.0.0",
                read_only=True,
            ),
            Parameter(
                "Length",
                "Double",
                30.0,
                builtin="CURVE_ELEM_LENGTH",
                data_type="autodesk.spec.aec:length-2.0.0",
            ),
            Parameter("Mark", "String", "W-1", builtin="ALL_MODEL_MARK"),
            Parameter("Structural", "Integer", 0, display="No"),
            Parameter("Base Constraint", "ElementId", level_id, display="Level 1"),
        ],
        location=LocationCurve(Curve(XYZ(x0, 0, 0), XYZ(x0 + 30, 0, 0), 30.0)),
        bounding_box=BoundingBox(XYZ(x0 - 0.33, -0.33, 0), XYZ(x0 + 30.33, 0.33, 10)),
        materials={4001: (200.0, 600.0)},
    )
