"""
Adapters from the live Revit .NET API (via pythonnet) to the RevitPy host contract.

``revitpy.api`` is written against small protocols (``IRevitApplication``,
``IRevitDocument``, ``IRevitElement``). The classes here implement those
protocols on top of ``Autodesk.Revit.DB`` objects so that RevitPy can drive a
real Revit session::

    from revitpy import RevitAPI
    from revitpy.api import Wall

    api = RevitAPI()
    api.connect(__revit__)  # UIApplication from the RevitPy host or pyRevit
    walls = api.query(Wall).execute()

Notes:
    * Adapters must only be used on Revit's main API thread: inside an external
      command, a Revit event handler, or an ``ExternalEvent`` callback.
    * Lengths, areas and volumes are in Revit internal units (feet).
    * ``Autodesk.Revit.DB`` is loaded lazily, so this module imports on any
      platform; only *using* an adapter without an injected ``db`` requires Revit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from ..api.element import element_id_value
from ..api.exceptions import ConnectionError, PermissionError, TransactionError

__all__ = [
    "RevitApiUnavailableError",
    "RevitApplicationAdapter",
    "RevitDocumentAdapter",
    "RevitElementAdapter",
    "adapt_application",
    "load_revit_api",
]


class RevitApiUnavailableError(ConnectionError):
    """Raised when the Revit API cannot be loaded (e.g. outside Revit)."""


_revit_api_cache: Any | None = None


def load_revit_api() -> Any:
    """Load and cache the ``Autodesk.Revit.DB`` namespace.

    Raises:
        RevitApiUnavailableError: If the API cannot be loaded.
    """
    global _revit_api_cache
    if _revit_api_cache is not None:
        return _revit_api_cache

    try:
        import clr

        clr.AddReference("RevitAPI")
        from Autodesk.Revit import DB
    except Exception as e:
        raise RevitApiUnavailableError(
            "The Revit API is not available. RevitPy must run inside Revit "
            "(via the RevitPy host add-in or pyRevit) to connect to a live model.",
            cause=e,
        ) from e

    _revit_api_cache = DB
    return DB


def _enum_name(value: Any) -> str:
    """Return the member name of a .NET enum value ("StorageType.Double" -> "Double")."""
    return str(value).split(".")[-1]


class _UsesRevitApi:
    """Mixin resolving the ``Autodesk.Revit.DB`` namespace lazily."""

    _db_override: Any | None

    @property
    def _db(self) -> Any:
        if self._db_override is None:
            return load_revit_api()
        return self._db_override


class RevitElementAdapter(_UsesRevitApi):
    """Adapts a ``DB.Element`` to ``IRevitElement``."""

    def __init__(self, element: Any, db: Any | None = None) -> None:
        self.element = element
        self._db_override = db

    @property
    def Id(self) -> Any:
        """The raw Revit ``ElementId``."""
        return self.element.Id

    @property
    def Name(self) -> str:
        """The element name, or ``""`` if Revit refuses to provide one."""
        try:
            return self.element.Name or ""
        except Exception:
            return ""

    @property
    def Category(self) -> str | None:
        """Built-in category name (e.g. ``"OST_Walls"``), else display name."""
        category = self.element.Category
        if category is None:
            return None

        built_in = getattr(category, "BuiltInCategory", None)
        if built_in is not None:
            name = _enum_name(built_in)
            if name.startswith("OST_"):
                return name
        return category.Name

    def _convert(self, param: Any) -> Any:
        """Convert a ``DB.Parameter`` to a plain Python value."""
        kind = _enum_name(param.StorageType)
        if kind == "String":
            return param.AsString()
        if kind == "Double":
            return param.AsDouble()
        if kind == "Integer":
            return param.AsInteger()
        if kind == "ElementId":
            return element_id_value(param.AsElementId())
        return param.AsValueString()

    def _type_element(self) -> Any | None:
        get_type_id = getattr(self.element, "GetTypeId", None)
        if get_type_id is None:
            return None
        return self.element.Document.GetElement(get_type_id())

    def GetParameterValue(self, parameter_name: str) -> Any:
        """Return a parameter value as a plain Python value.

        Besides real parameters, supports the pseudo-parameters ``Name``,
        ``Category``, ``Type``, ``Family`` and ``Level``.

        Raises:
            KeyError: If the element has no such parameter.
        """
        param = self.element.LookupParameter(parameter_name)
        if param is not None:
            if parameter_name == "Level" and _enum_name(param.StorageType) == (
                "ElementId"
            ):
                # Rooms and many hosts store their level as an ElementId;
                # return its name, consistent with the pseudo-parameter.
                level = self.element.Document.GetElement(param.AsElementId())
                return level.Name if level is not None else None
            return self._convert(param)

        if parameter_name == "Name":
            return self.Name

        if parameter_name == "Category":
            category = self.element.Category
            return category.Name if category is not None else None

        if parameter_name == "Type":
            type_element = self._type_element()
            return type_element.Name if type_element is not None else None

        if parameter_name == "Family":
            type_element = self._type_element()
            return getattr(type_element, "FamilyName", None)

        if parameter_name == "Level":
            level_id = getattr(self.element, "LevelId", None)
            if level_id is None or element_id_value(level_id) == -1:
                return None
            level = self.element.Document.GetElement(level_id)
            return level.Name if level is not None else None

        raise KeyError(
            f"Parameter '{parameter_name}' not found on element "
            f"{element_id_value(self.element.Id)}"
        )

    def SetParameterValue(self, parameter_name: str, value: Any) -> None:
        """Set a parameter, converting ``value`` to the parameter's storage type.

        Must be called inside an open transaction.

        Raises:
            KeyError: If the element has no such parameter.
            PermissionError: If the parameter is read-only.
            ValueError: If Revit rejects the value.
        """
        param = self.element.LookupParameter(parameter_name)

        if param is None:
            if parameter_name == "Name":
                self.element.Name = str(value)
                return
            raise KeyError(
                f"Parameter '{parameter_name}' not found on element "
                f"{element_id_value(self.element.Id)}"
            )

        if param.IsReadOnly:
            raise PermissionError(f"Parameter '{parameter_name}' is read-only")

        kind = _enum_name(param.StorageType)
        converted: Any
        if kind == "String":
            converted = "" if value is None else str(value)
        elif kind == "Double":
            converted = float(value)
        elif kind == "Integer":
            converted = int(value)
        elif kind == "ElementId":
            converted = self._to_element_id(value)
        else:
            converted = value

        if param.Set(converted) is False:
            raise ValueError(
                f"Revit rejected value {value!r} for parameter '{parameter_name}'"
            )

    def _to_element_id(self, value: Any) -> Any:
        if isinstance(value, int) and not isinstance(value, bool):
            return self._db.ElementId(value)
        inner = getattr(value, "value", None)
        if isinstance(inner, int) and not isinstance(inner, bool):
            return self._db.ElementId(inner)
        return value

    def GetAllParameters(self) -> dict[str, Any]:
        """Return all parameters as ``{name: value}`` in Revit's order."""
        result: dict[str, Any] = {}
        for param in self.element.Parameters:
            name = param.Definition.Name
            try:
                result[name] = self._convert(param)
            except Exception as e:
                logger.debug(f"Could not read parameter '{name}': {e}")
                result[name] = None
        return result

    def __repr__(self) -> str:
        return (
            f"RevitElementAdapter(id={element_id_value(self.element.Id)}, "
            f"name={self.Name!r})"
        )


class RevitDocumentAdapter(_UsesRevitApi):
    """Adapts a ``DB.Document`` to ``IRevitDocument``."""

    def __init__(self, document: Any, db: Any | None = None) -> None:
        self.document = document
        self._db_override = db

    @property
    def Title(self) -> str:
        return self.document.Title

    @property
    def PathName(self) -> str:
        return self.document.PathName

    @property
    def IsModified(self) -> bool:
        return bool(self.document.IsModified)

    @property
    def IsReadOnly(self) -> bool:
        return bool(self.document.IsReadOnly)

    @property
    def Version(self) -> str | None:
        """The Revit version number (e.g. ``"2025"``), if available."""
        try:
            return str(self.document.Application.VersionNumber)
        except Exception:
            return None

    def _to_element_id(self, element_id: Any) -> Any:
        """Convert ints / RevitPy ``ElementId`` to a raw ``DB.ElementId``."""
        if isinstance(element_id, int) and not isinstance(element_id, bool):
            return self._db.ElementId(element_id)
        inner = getattr(element_id, "value", None)
        if isinstance(inner, int) and not isinstance(inner, bool):
            return self._db.ElementId(inner)
        return element_id

    def _wrap(self, element: Any) -> RevitElementAdapter:
        return RevitElementAdapter(element, self._db_override)

    def _collector(self) -> Any:
        return self._db.FilteredElementCollector(self.document)

    def GetElements(
        self, filter_criteria: Callable[[RevitElementAdapter], bool] | None = None
    ) -> list[RevitElementAdapter]:
        """Return all non-type elements, optionally filtered by a predicate."""
        adapters = [
            self._wrap(e) for e in self._collector().WhereElementIsNotElementType()
        ]
        if callable(filter_criteria):
            adapters = [a for a in adapters if filter_criteria(a)]
        return adapters

    def GetElement(self, element_id: Any) -> RevitElementAdapter | None:
        """Return the element with ``element_id``, or ``None`` if absent."""
        element = self.document.GetElement(self._to_element_id(element_id))
        return self._wrap(element) if element is not None else None

    def GetElementsByCategory(self, category: str) -> list[RevitElementAdapter]:
        """Return non-type elements of a category.

        ``category`` may be a built-in name (``"OST_Walls"``) or a display
        name (``"Walls"``, locale dependent). Unknown categories yield ``[]``.
        """
        if category.startswith("OST_"):
            built_in = getattr(self._db.BuiltInCategory, category, None)
            if built_in is None:
                return []
            collector = self._collector().OfCategory(built_in)
        else:
            match = next(
                (c for c in self.document.Settings.Categories if c.Name == category),
                None,
            )
            if match is None:
                return []
            built_in = getattr(match, "BuiltInCategory", None)
            if built_in is not None and _enum_name(built_in) != "INVALID":
                collector = self._collector().OfCategory(built_in)
            else:
                collector = self._collector().OfCategoryId(match.Id)

        return [self._wrap(e) for e in collector.WhereElementIsNotElementType()]

    def Delete(self, element_ids: list[Any]) -> None:
        """Delete elements. Must be called inside an open transaction."""
        ids = [self._to_element_id(i) for i in element_ids]
        collection: Any
        try:
            from System.Collections.Generic import List
        except ImportError:  # not running under pythonnet (tests)
            collection = ids
        else:
            collection = List[self._db.ElementId]()
            for element_id in ids:
                collection.Add(element_id)
        self.document.Delete(collection)

    def Save(self) -> bool:
        """Save the document. Revit raises on failure."""
        self.document.Save()
        return True

    def Close(self, save_changes: bool = True) -> bool:
        return bool(self.document.Close(save_changes))

    def StartTransaction(self, name: str) -> Any:
        """Open and start a Revit transaction.

        A ``SubTransaction`` is used when the document is already modifiable
        (a transaction is open), since Revit forbids nested ``Transaction``s.
        The returned handle exposes ``Commit()`` and ``RollBack()``.

        Raises:
            TransactionError: If Revit refuses to start the transaction.
        """
        if self.document.IsModifiable:
            handle = self._db.SubTransaction(self.document)
        else:
            handle = self._db.Transaction(self.document, name)

        status = handle.Start()
        if _enum_name(status) != "Started":
            raise TransactionError(
                f"Revit refused to start transaction '{name}': {status}", name
            )
        return handle

    def __repr__(self) -> str:
        return f"RevitDocumentAdapter(title={self.Title!r}, path={self.PathName!r})"


class RevitApplicationAdapter(_UsesRevitApi):
    """Adapts a ``UIApplication`` or ``Application`` to ``IRevitApplication``."""

    def __init__(self, app: Any, db: Any | None = None) -> None:
        self._db_override = db
        if hasattr(app, "ActiveUIDocument"):
            self.ui_application: Any | None = app
            self.application = app.Application
        else:
            self.ui_application = None
            self.application = app

    @property
    def ActiveDocument(self) -> RevitDocumentAdapter | None:
        """The active document, or ``None`` without a UI or open document."""
        if self.ui_application is None:
            return None
        ui_document = self.ui_application.ActiveUIDocument
        if ui_document is None:
            return None
        return RevitDocumentAdapter(ui_document.Document, self._db_override)

    def OpenDocumentFile(self, file_path: str) -> RevitDocumentAdapter:
        return RevitDocumentAdapter(
            self.application.OpenDocumentFile(file_path), self._db_override
        )

    def CreateDocument(self, template_path: str | None = None) -> RevitDocumentAdapter:
        template = template_path or self.application.DefaultProjectTemplate
        return RevitDocumentAdapter(
            self.application.NewProjectDocument(template), self._db_override
        )

    def GetOpenDocuments(self) -> list[RevitDocumentAdapter]:
        return [
            RevitDocumentAdapter(doc, self._db_override)
            for doc in self.application.Documents
        ]


def adapt_application(app: Any, db: Any | None = None) -> RevitApplicationAdapter:
    """Wrap a Revit ``UIApplication``/``Application`` for use with ``RevitAPI``.

    Raises:
        ConnectionError: If ``app`` does not look like a Revit application.
    """
    if isinstance(app, RevitApplicationAdapter):
        return app
    if not (hasattr(app, "ActiveUIDocument") or hasattr(app, "OpenDocumentFile")):
        raise ConnectionError(
            f"Object of type {type(app).__name__} is not a Revit UIApplication "
            "or Application"
        )
    return RevitApplicationAdapter(app, db)
