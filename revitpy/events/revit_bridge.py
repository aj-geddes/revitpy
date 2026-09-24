"""
Bridge from native Revit application events to :class:`EventManager`.

Revit raises its events on the main API thread and only allows model access
while the callback runs, so events are dispatched *immediately* (synchronously)
rather than queued for the background dispatcher thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from ..api.element import element_id_value
from .types import EventType

if TYPE_CHECKING:
    from .manager import EventManager


def _document_info(document: Any) -> dict[str, Any]:
    return {
        "document_title": getattr(document, "Title", None),
        "document_path": getattr(document, "PathName", None),
        "is_family_document": bool(getattr(document, "IsFamilyDocument", False)),
    }


class RevitEventBridge:
    """Subscribes to Revit ``Application`` events and re-emits them.

    ======================  ==========================================
    Revit event             RevitPy event(s)
    ======================  ==========================================
    ``DocumentOpened``      ``DOCUMENT_OPENED``
    ``DocumentSaved``       ``DOCUMENT_SAVED``
    ``DocumentClosing``     ``DOCUMENT_CLOSED``
    ``DocumentChanged``     ``ELEMENT_CREATED`` / ``ELEMENT_MODIFIED`` /
                            ``ELEMENT_DELETED`` (one per element id)
    ======================  ==========================================
    """

    _SUBSCRIPTIONS = (
        ("DocumentOpened", "_on_document_opened"),
        ("DocumentSaved", "_on_document_saved"),
        ("DocumentClosing", "_on_document_closing"),
        ("DocumentChanged", "_on_document_changed"),
    )

    def __init__(self, manager: EventManager, revit_application: Any) -> None:
        self._manager = manager
        # A UIApplication exposes the DB Application as ``.Application``.
        self._application = getattr(revit_application, "Application", revit_application)
        self._connected: list[tuple[str, Any]] = []

    @property
    def is_connected(self) -> bool:
        return bool(self._connected)

    def connect(self) -> None:
        """Subscribe to the Revit events. Call on Revit's main thread."""
        if self._connected:
            return
        for event_name, method_name in self._SUBSCRIPTIONS:
            revit_event = getattr(self._application, event_name, None)
            if revit_event is None:
                logger.debug(f"Revit application has no {event_name} event")
                continue
            handler = getattr(self, method_name)
            revit_event += handler
            setattr(self._application, event_name, revit_event)
            self._connected.append((event_name, handler))

    def disconnect(self) -> None:
        """Unsubscribe from every event subscribed by :meth:`connect`."""
        while self._connected:
            event_name, handler = self._connected.pop()
            revit_event = getattr(self._application, event_name)
            revit_event -= handler
            setattr(self._application, event_name, revit_event)

    # -- handlers ---------------------------------------------------------

    def _emit(self, event_type: EventType, source: Any, **payload: Any) -> None:
        try:
            self._manager.dispatch_event(
                event_type, immediate=True, source=source, **payload
            )
        except Exception as e:
            # Never let a Python failure propagate into Revit's event loop.
            logger.error(f"Handling {event_type.value} failed: {e}")

    def _on_document_opened(self, _sender: Any, args: Any) -> None:
        document = args.Document
        self._emit(EventType.DOCUMENT_OPENED, document, **_document_info(document))

    def _on_document_saved(self, _sender: Any, args: Any) -> None:
        document = args.Document
        self._emit(EventType.DOCUMENT_SAVED, document, **_document_info(document))

    def _on_document_closing(self, _sender: Any, args: Any) -> None:
        document = args.Document
        self._emit(EventType.DOCUMENT_CLOSED, document, **_document_info(document))

    def _on_document_changed(self, _sender: Any, args: Any) -> None:
        document = args.GetDocument()
        transactions = list(args.GetTransactionNames())
        groups = (
            (EventType.ELEMENT_CREATED, args.GetAddedElementIds()),
            (EventType.ELEMENT_MODIFIED, args.GetModifiedElementIds()),
            (EventType.ELEMENT_DELETED, args.GetDeletedElementIds()),
        )
        for event_type, element_ids in groups:
            for revit_id in element_ids:
                element_id = element_id_value(revit_id)
                category = None
                if event_type is not EventType.ELEMENT_DELETED:
                    element = document.GetElement(revit_id)
                    element_category = getattr(element, "Category", None)
                    category = getattr(element_category, "Name", None)
                self._emit(
                    event_type,
                    document,
                    element_id=element_id,
                    category=category,
                    data={"transactions": transactions},
                )
