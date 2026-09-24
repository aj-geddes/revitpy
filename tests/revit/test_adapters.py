"""Tests for revitpy.revit.adapters against a fake Autodesk.Revit.DB namespace."""

from __future__ import annotations

import types
from typing import Any

import pytest

import revitpy.revit.adapters as adapters_module
from revitpy import RevitAPI
from revitpy.api import Door, Wall
from revitpy.api.exceptions import ConnectionError as RevitConnectionError
from revitpy.api.exceptions import PermissionError as RevitPermissionError
from revitpy.api.exceptions import TransactionError
from revitpy.revit.adapters import (
    RevitApiUnavailableError,
    RevitApplicationAdapter,
    RevitDocumentAdapter,
    RevitElementAdapter,
    adapt_application,
    load_revit_api,
)

# --------------------------------------------------------------------------
# Fake Revit API
# --------------------------------------------------------------------------


class FakeEnum:
    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeEnum) and self._text == other._text

    def __hash__(self) -> int:
        return hash(self._text)


class FakeElementId:
    def __init__(self, value: int) -> None:
        self.Value = value
        self.IntegerValue = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeElementId) and self.Value == other.Value

    def __hash__(self) -> int:
        return hash(self.Value)


class FakeParameter:
    def __init__(
        self,
        name: str,
        storage: str,
        value: Any,
        read_only: bool = False,
        accept: bool = True,
    ) -> None:
        self.Definition = types.SimpleNamespace(Name=name)
        self.StorageType = FakeEnum(f"StorageType.{storage}")
        self.value = value
        self.IsReadOnly = read_only
        self.accept = accept

    def AsString(self) -> str:
        return str(self.value)

    def AsDouble(self) -> float:
        return float(self.value)

    def AsInteger(self) -> int:
        return int(self.value)

    def AsElementId(self) -> FakeElementId:
        return (
            self.value
            if isinstance(self.value, FakeElementId)
            else FakeElementId(self.value)
        )

    def AsValueString(self) -> str:
        return str(self.value)

    def Set(self, value: Any) -> bool:
        if self.accept:
            self.value = value
        return self.accept


class FakeElement:
    def __init__(
        self,
        eid: int,
        name: str,
        bic: str | None,
        category_name: str = "",
        params: list[FakeParameter] | None = None,
        type_id: int = -1,
        level_id: int = -1,
    ) -> None:
        self.Id = FakeElementId(eid)
        self.Name = name
        self.Category = (
            types.SimpleNamespace(
                Name=category_name, BuiltInCategory=FakeEnum(f"BuiltInCategory.{bic}")
            )
            if bic is not None
            else None
        )
        self.Parameters = params or []
        self.Document: FakeDocument | None = None
        self._type_id = type_id
        self.LevelId = FakeElementId(level_id)

    def LookupParameter(self, name: str) -> FakeParameter | None:
        return next((p for p in self.Parameters if p.Definition.Name == name), None)

    def GetTypeId(self) -> FakeElementId:
        return FakeElementId(self._type_id)


class FakeDocument:
    def __init__(self) -> None:
        self.elements: dict[int, FakeElement] = {}
        self.Title = "Test Project"
        self.PathName = r"C:\Projects\test.rvt"
        self.IsModified = False
        self.IsReadOnly = False
        self.IsModifiable = False
        self.Application = types.SimpleNamespace(VersionNumber="2025")
        self.Settings = types.SimpleNamespace(
            Categories=[
                types.SimpleNamespace(
                    Name="Walls",
                    BuiltInCategory=FakeEnum("BuiltInCategory.OST_Walls"),
                    Id=FakeElementId(-2000011),
                )
            ]
        )
        self.deleted: list[int] = []

    def add(self, element: FakeElement) -> FakeElement:
        element.Document = self
        self.elements[element.Id.Value] = element
        return element

    def GetElement(self, element_id: FakeElementId) -> FakeElement | None:
        return self.elements.get(element_id.Value)

    def Delete(self, ids: list[FakeElementId]) -> None:
        for element_id in ids:
            self.deleted.append(element_id.Value)
            self.elements.pop(element_id.Value, None)


class FakeCollector:
    def __init__(self, doc: FakeDocument) -> None:
        self._elements = list(doc.elements.values())

    def WhereElementIsNotElementType(self) -> FakeCollector:
        return self

    def OfCategory(self, bic: FakeEnum) -> FakeCollector:
        self._elements = [
            e
            for e in self._elements
            if e.Category is not None and e.Category.BuiltInCategory == bic
        ]
        return self

    def __iter__(self) -> Any:
        return iter(self._elements)


def _snapshot(doc: FakeDocument) -> dict[int, tuple[str, dict[str, Any]]]:
    return {
        eid: (e.Name, {p.Definition.Name: p.value for p in e.Parameters})
        for eid, e in doc.elements.items()
    }


def _restore(
    doc: FakeDocument, snapshot: dict[int, tuple[str, dict[str, Any]]]
) -> None:
    for eid, (name, values) in snapshot.items():
        element = doc.elements[eid]
        element.Name = name
        for p in element.Parameters:
            p.value = values[p.Definition.Name]


class FakeTransaction:
    def __init__(self, doc: FakeDocument, name: str) -> None:
        self.doc = doc
        self.name = name

    def Start(self) -> FakeEnum:
        self.doc.IsModifiable = True
        self._snapshot = _snapshot(self.doc)
        return FakeEnum("TransactionStatus.Started")

    def Commit(self) -> FakeEnum:
        self.doc.IsModifiable = False
        return FakeEnum("TransactionStatus.Committed")

    def RollBack(self) -> FakeEnum:
        _restore(self.doc, self._snapshot)
        self.doc.IsModifiable = False
        return FakeEnum("TransactionStatus.RolledBack")


class FakeSubTransaction(FakeTransaction):
    def __init__(self, doc: FakeDocument) -> None:
        super().__init__(doc, "sub")

    def Start(self) -> FakeEnum:
        self._snapshot = _snapshot(self.doc)
        return FakeEnum("TransactionStatus.Started")

    def Commit(self) -> FakeEnum:
        return FakeEnum("TransactionStatus.Committed")

    def RollBack(self) -> FakeEnum:
        _restore(self.doc, self._snapshot)
        return FakeEnum("TransactionStatus.RolledBack")


class FakeApplication:
    DefaultProjectTemplate = "default.rte"

    def __init__(self, doc: FakeDocument) -> None:
        self.Documents = [doc]
        self.opened: list[str] = []
        self.templates: list[str] = []
        self._doc = doc

    def OpenDocumentFile(self, path: str) -> FakeDocument:
        self.opened.append(path)
        return self._doc

    def NewProjectDocument(self, template: str) -> FakeDocument:
        self.templates.append(template)
        return FakeDocument()


class FakeUIApplication:
    def __init__(self, doc: FakeDocument | None) -> None:
        self.ActiveUIDocument = (
            types.SimpleNamespace(Document=doc) if doc is not None else None
        )
        self.Application = FakeApplication(doc or FakeDocument())


def make_db() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        ElementId=FakeElementId,
        FilteredElementCollector=FakeCollector,
        BuiltInCategory=types.SimpleNamespace(
            OST_Walls=FakeEnum("BuiltInCategory.OST_Walls"),
            OST_Doors=FakeEnum("BuiltInCategory.OST_Doors"),
            OST_Levels=FakeEnum("BuiltInCategory.OST_Levels"),
        ),
        Transaction=FakeTransaction,
        SubTransaction=FakeSubTransaction,
    )


@pytest.fixture
def revit_env() -> tuple[types.SimpleNamespace, FakeDocument, FakeUIApplication]:
    doc = FakeDocument()
    doc.add(
        FakeElement(
            1,
            "W1",
            "OST_Walls",
            "Walls",
            [
                FakeParameter("Comments", "String", ""),
                FakeParameter("Width", "Double", 0.5),
                FakeParameter("Count", "Integer", 3),
                FakeParameter("Base", "ElementId", FakeElementId(30)),
                FakeParameter("Area", "None", "12 m²"),
                FakeParameter("Locked", "String", "no", read_only=True),
            ],
            type_id=40,
            level_id=30,
        )
    )
    doc.add(FakeElement(2, "W2", "OST_Walls", "Walls"))
    doc.add(FakeElement(3, "D1", "OST_Doors", "Doors"))
    doc.add(FakeElement(30, "Level 1", "OST_Levels", "Levels"))
    type_element = doc.add(FakeElement(40, "Generic 200mm", None))
    type_element.FamilyName = "Basic Wall"  # type: ignore[attr-defined]
    return make_db(), doc, FakeUIApplication(doc)


def wall(env: Any) -> RevitElementAdapter:
    db, doc, _ = env
    return RevitElementAdapter(doc.elements[1], db)


# --------------------------------------------------------------------------
# Element adapter
# --------------------------------------------------------------------------


class TestElementAdapter:
    def test_identity(self, revit_env: Any) -> None:
        adapter = wall(revit_env)
        assert adapter.Id.Value == 1
        assert adapter.Name == "W1"
        assert adapter.Category == "OST_Walls"

    def test_category_none(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        assert RevitElementAdapter(doc.elements[40], db).Category is None

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Comments", ""),
            ("Width", 0.5),
            ("Count", 3),
            ("Base", 30),
            ("Area", "12 m²"),
        ],
    )
    def test_storage_type_conversion(
        self, revit_env: Any, name: str, expected: Any
    ) -> None:
        assert wall(revit_env).GetParameterValue(name) == expected

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Name", "W1"),
            ("Category", "Walls"),
            ("Type", "Generic 200mm"),
            ("Family", "Basic Wall"),
            ("Level", "Level 1"),
        ],
    )
    def test_pseudo_parameters(self, revit_env: Any, name: str, expected: str) -> None:
        assert wall(revit_env).GetParameterValue(name) == expected

    def test_level_without_level_id(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        assert (
            RevitElementAdapter(doc.elements[2], db).GetParameterValue("Level") is None
        )

    def test_missing_parameter(self, revit_env: Any) -> None:
        with pytest.raises(KeyError):
            wall(revit_env).GetParameterValue("Nope")

    @pytest.mark.parametrize(
        ("name", "value", "stored"),
        [
            ("Comments", 42, "42"),
            ("Comments", None, ""),
            ("Width", "1.25", 1.25),
            ("Count", 7.0, 7),
        ],
    )
    def test_set_converts(
        self, revit_env: Any, name: str, value: Any, stored: Any
    ) -> None:
        _, doc, _ = revit_env
        wall(revit_env).SetParameterValue(name, value)
        assert doc.elements[1].LookupParameter(name).value == stored

    def test_set_element_id_from_int(self, revit_env: Any) -> None:
        _, doc, _ = revit_env
        wall(revit_env).SetParameterValue("Base", 99)
        assert doc.elements[1].LookupParameter("Base").value == FakeElementId(99)

    def test_set_read_only(self, revit_env: Any) -> None:
        with pytest.raises(RevitPermissionError):
            wall(revit_env).SetParameterValue("Locked", "yes")

    def test_set_rejected(self, revit_env: Any) -> None:
        _, doc, _ = revit_env
        doc.elements[1].LookupParameter("Comments").accept = False
        with pytest.raises(ValueError, match="rejected"):
            wall(revit_env).SetParameterValue("Comments", "x")

    def test_set_name_without_parameter(self, revit_env: Any) -> None:
        _, doc, _ = revit_env
        wall(revit_env).SetParameterValue("Name", "Renamed")
        assert doc.elements[1].Name == "Renamed"

    def test_set_missing_parameter(self, revit_env: Any) -> None:
        with pytest.raises(KeyError):
            wall(revit_env).SetParameterValue("Nope", 1)

    def test_get_all_parameters(self, revit_env: Any) -> None:
        params = wall(revit_env).GetAllParameters()
        assert list(params) == ["Comments", "Width", "Count", "Base", "Area", "Locked"]
        assert params["Base"] == 30


# --------------------------------------------------------------------------
# Document adapter
# --------------------------------------------------------------------------


class TestDocumentAdapter:
    def test_properties(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        adapter = RevitDocumentAdapter(doc, db)
        assert adapter.Title == "Test Project"
        assert adapter.PathName == r"C:\Projects\test.rvt"
        assert adapter.IsModified is False
        assert adapter.IsReadOnly is False
        assert adapter.Version == "2025"

    def test_get_elements(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        adapter = RevitDocumentAdapter(doc, db)
        assert len(adapter.GetElements()) == 5
        filtered = adapter.GetElements(lambda e: e.Name.startswith("W"))
        assert [e.Name for e in filtered] == ["W1", "W2"]

    def test_get_element(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        adapter = RevitDocumentAdapter(doc, db)
        found = adapter.GetElement(3)
        assert found is not None and found.Name == "D1"
        assert adapter.GetElement(999) is None

    @pytest.mark.parametrize(
        ("category", "count"),
        [("OST_Walls", 2), ("Walls", 2), ("OST_Nope", 0), ("Nope", 0)],
    )
    def test_get_elements_by_category(
        self, revit_env: Any, category: str, count: int
    ) -> None:
        db, doc, _ = revit_env
        assert (
            len(RevitDocumentAdapter(doc, db).GetElementsByCategory(category)) == count
        )

    def test_delete(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        RevitDocumentAdapter(doc, db).Delete([1, 2])
        assert doc.deleted == [1, 2]
        assert set(doc.elements) == {3, 30, 40}

    def test_start_transaction(self, revit_env: Any) -> None:
        db, doc, _ = revit_env
        adapter = RevitDocumentAdapter(doc, db)
        outer = adapter.StartTransaction("outer")
        assert type(outer) is FakeTransaction
        inner = adapter.StartTransaction("inner")
        assert type(inner) is FakeSubTransaction

    def test_start_transaction_refused(
        self, revit_env: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db, doc, _ = revit_env

        class Refusing(FakeTransaction):
            def Start(self) -> FakeEnum:
                return FakeEnum("TransactionStatus.Error")

        monkeypatch.setattr(db, "Transaction", Refusing)
        with pytest.raises(TransactionError):
            RevitDocumentAdapter(doc, db).StartTransaction("t")


# --------------------------------------------------------------------------
# Application adapter
# --------------------------------------------------------------------------


class TestApplicationAdapter:
    def test_active_document(self, revit_env: Any) -> None:
        db, doc, uiapp = revit_env
        active = RevitApplicationAdapter(uiapp, db).ActiveDocument
        assert active is not None and active.document is doc

    def test_no_active_document(self, revit_env: Any) -> None:
        db, _, _ = revit_env
        assert (
            RevitApplicationAdapter(FakeUIApplication(None), db).ActiveDocument is None
        )

    def test_plain_application_has_no_active_document(self, revit_env: Any) -> None:
        db, _, uiapp = revit_env
        adapter = RevitApplicationAdapter(uiapp.Application, db)
        assert adapter.ui_application is None
        assert adapter.ActiveDocument is None

    def test_open_and_create(self, revit_env: Any) -> None:
        db, doc, uiapp = revit_env
        adapter = RevitApplicationAdapter(uiapp, db)
        assert adapter.OpenDocumentFile("a.rvt").document is doc
        assert uiapp.Application.opened == ["a.rvt"]
        created = adapter.CreateDocument()
        assert isinstance(created, RevitDocumentAdapter)
        assert uiapp.Application.templates == ["default.rte"]
        assert len(adapter.GetOpenDocuments()) == 1

    def test_adapt_application(self, revit_env: Any) -> None:
        db, _, uiapp = revit_env
        adapter = adapt_application(uiapp, db)
        assert adapt_application(adapter) is adapter
        with pytest.raises(RevitConnectionError):
            adapt_application(object())

    def test_load_revit_api_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(adapters_module, "_revit_api_cache", None)
        with pytest.raises(RevitApiUnavailableError):
            load_revit_api()


# --------------------------------------------------------------------------
# End to end through RevitAPI
# --------------------------------------------------------------------------


@pytest.fixture
def api(revit_env: Any) -> RevitAPI:
    db, _, uiapp = revit_env
    revit_api = RevitAPI()
    revit_api.connect(adapt_application(uiapp, db))
    return revit_api


class TestRevitAPIEndToEnd:
    def test_typed_queries(self, api: RevitAPI) -> None:
        walls = api.query(Wall).execute()
        assert sorted(w.id.value for w in walls) == [1, 2]
        assert all(isinstance(w, Wall) for w in walls)
        assert [d.id.value for d in api.query(Door).execute()] == [3]

    def test_rollback_on_exception(self, api: RevitAPI, revit_env: Any) -> None:
        _, doc, _ = revit_env
        with pytest.raises(RuntimeError, match="boom"):
            with api.transaction("t"):
                api.get_element_by_id(1).set_parameter_value("Comments", "x")
                raise RuntimeError("boom")
        assert doc.elements[1].LookupParameter("Comments").value == ""
        assert doc.IsModifiable is False

    def test_commit(self, api: RevitAPI, revit_env: Any) -> None:
        _, doc, _ = revit_env
        with api.transaction("t"):
            api.get_element_by_id(1).set_parameter_value("Comments", "x")
        assert doc.elements[1].LookupParameter("Comments").value == "x"

    def test_nested_transaction_uses_sub_transaction(self, api: RevitAPI) -> None:
        with api.transaction("outer"):
            with api.transaction("inner"):
                api.get_element_by_id(1).set_parameter_value("Count", 9)
        assert api.get_element_by_id(1).get_parameter_value("Count") == 9

    def test_document_info(self, api: RevitAPI) -> None:
        info = api.get_document_info()
        assert info.version == "2025"
        assert info.title == "Test Project"

    def test_connect_wraps_raw_revit_objects(
        self, revit_env: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db, _, uiapp = revit_env
        monkeypatch.setattr(adapters_module, "_revit_api_cache", db)
        revit_api = RevitAPI()
        revit_api.connect(uiapp)  # like api.connect(__revit__)
        assert len(revit_api.query(Wall).execute()) == 2


def test_level_element_id_parameter_returns_level_name(revit_env: Any) -> None:
    """Rooms store Level as an ElementId parameter; expose the level's name."""
    db, doc, _ = revit_env
    room = doc.add(
        FakeElement(
            50,
            "Office",
            "OST_Rooms",
            "Rooms",
            [FakeParameter("Level", "ElementId", FakeElementId(30))],
        )
    )
    assert RevitElementAdapter(room, db).GetParameterValue("Level") == "Level 1"
