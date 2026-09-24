"""Class-based event handlers and the native Revit event bridge."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from revitpy.events import EventManager, EventType, event_handler
from revitpy.events.handlers import CallableEventHandler
from revitpy.events.revit_bridge import RevitEventBridge

ALL_TYPES = [
    EventType.ELEMENT_CREATED,
    EventType.ELEMENT_MODIFIED,
    EventType.ELEMENT_DELETED,
    EventType.DOCUMENT_OPENED,
    EventType.DOCUMENT_SAVED,
    EventType.DOCUMENT_CLOSED,
]


class FakeRevitEvent:
    """Mimics a .NET event: supports ``+=`` / ``-=`` and firing."""

    def __init__(self) -> None:
        self.subscribers: list[Any] = []

    def __iadd__(self, handler: Any) -> FakeRevitEvent:
        self.subscribers.append(handler)
        return self

    def __isub__(self, handler: Any) -> FakeRevitEvent:
        self.subscribers.remove(handler)
        return self

    def fire(self, sender: Any, args: Any) -> None:
        for handler in list(self.subscribers):
            handler(sender, args)


class FakeApplication:
    def __init__(self) -> None:
        self.DocumentOpened = FakeRevitEvent()
        self.DocumentSaved = FakeRevitEvent()
        self.DocumentClosing = FakeRevitEvent()
        self.DocumentChanged = FakeRevitEvent()


def document(title: str) -> SimpleNamespace:
    return SimpleNamespace(Title=title, PathName=f"C:\\{title}", IsFamilyDocument=False)


class ChangedArgs:
    def __init__(
        self,
        added: list[int],
        modified: list[int],
        deleted: list[int],
        categories: dict[int, str],
    ) -> None:
        self._ids = (added, modified, deleted)
        doc = document("Model.rvt")
        doc.GetElement = lambda eid: SimpleNamespace(
            Category=SimpleNamespace(Name=categories[eid.Value])
        )
        self._doc = doc

    def GetDocument(self) -> Any:
        return self._doc

    def GetAddedElementIds(self) -> list[Any]:
        return [SimpleNamespace(Value=v) for v in self._ids[0]]

    def GetModifiedElementIds(self) -> list[Any]:
        return [SimpleNamespace(Value=v) for v in self._ids[1]]

    def GetDeletedElementIds(self) -> list[Any]:
        return [SimpleNamespace(Value=v) for v in self._ids[2]]

    def GetTransactionNames(self) -> list[str]:
        return ["Move walls"]


class Listener:
    def __init__(self) -> None:
        self.received: list[Any] = []

    @event_handler([EventType.ELEMENT_MODIFIED])
    def on_modified(self, event: Any) -> None:
        self.received.append(event)


@pytest.fixture
def manager() -> EventManager:
    return EventManager.get_instance()


@pytest.fixture
def received(manager: EventManager) -> Iterator[list[Any]]:
    events: list[Any] = []
    handler = CallableEventHandler(callback=events.append, name="collector")
    manager.register_handler(handler, ALL_TYPES)
    yield events
    manager.unregister_handler(handler, ALL_TYPES)


@pytest.fixture
def class_handlers(manager: EventManager) -> Iterator[list[Any]]:
    registered: list[Any] = []
    yield registered
    for handler in registered:
        manager.unregister_handler(handler, [EventType.ELEMENT_MODIFIED])


class TestClassHandlers:
    def test_bound_to_instance(
        self, manager: EventManager, class_handlers: list[Any]
    ) -> None:
        listener = Listener()
        class_handlers += manager.register_class_handlers(listener)

        manager.dispatch_event(
            EventType.ELEMENT_MODIFIED, immediate=True, element_id=7, category="Walls"
        )

        assert [e.element_id for e in listener.received] == [7]
        assert class_handlers[0].callback.__self__ is listener
        assert class_handlers[0].name == "Listener.on_modified"

    def test_instances_are_independent(
        self, manager: EventManager, class_handlers: list[Any]
    ) -> None:
        first, second = Listener(), Listener()
        class_handlers += manager.register_class_handlers(first)
        class_handlers += manager.register_class_handlers(second)

        manager.dispatch_event(EventType.ELEMENT_MODIFIED, immediate=True, element_id=1)

        assert len(first.received) == 1
        assert len(second.received) == 1


class TestRevitEventBridge:
    def test_connect_and_disconnect(self, manager: EventManager) -> None:
        app = FakeApplication()
        bridge = RevitEventBridge(manager, app)
        bridge.connect()
        bridge.connect()  # idempotent

        events = (
            app.DocumentOpened,
            app.DocumentSaved,
            app.DocumentClosing,
            app.DocumentChanged,
        )
        assert bridge.is_connected
        assert all(len(e.subscribers) == 1 for e in events)

        bridge.disconnect()
        assert not bridge.is_connected
        assert all(e.subscribers == [] for e in events)

    def test_ui_application_is_unwrapped(
        self, manager: EventManager, received: list[Any]
    ) -> None:
        uiapp = SimpleNamespace(Application=FakeApplication())
        bridge = RevitEventBridge(manager, uiapp)
        bridge.connect()
        try:
            uiapp.Application.DocumentOpened.fire(
                None, SimpleNamespace(Document=document("A.rvt"))
            )
        finally:
            bridge.disconnect()
        assert [e.document_title for e in received] == ["A.rvt"]

    @pytest.mark.parametrize(
        ("revit_event", "event_type"),
        [
            ("DocumentOpened", EventType.DOCUMENT_OPENED),
            ("DocumentSaved", EventType.DOCUMENT_SAVED),
            ("DocumentClosing", EventType.DOCUMENT_CLOSED),
        ],
    )
    def test_document_events(
        self,
        manager: EventManager,
        received: list[Any],
        revit_event: str,
        event_type: EventType,
    ) -> None:
        app = FakeApplication()
        bridge = RevitEventBridge(manager, app)
        bridge.connect()
        try:
            getattr(app, revit_event).fire(
                None, SimpleNamespace(Document=document("B.rvt"))
            )
        finally:
            bridge.disconnect()

        assert [(e.event_type, e.document_title) for e in received] == [
            (event_type, "B.rvt")
        ]

    def test_document_changed(self, manager: EventManager, received: list[Any]) -> None:
        app = FakeApplication()
        bridge = RevitEventBridge(manager, app)
        bridge.connect()
        try:
            app.DocumentChanged.fire(
                None,
                ChangedArgs(
                    added=[1, 2],
                    modified=[3],
                    deleted=[4],
                    categories={1: "Walls", 2: "Doors", 3: "Walls"},
                ),
            )
        finally:
            bridge.disconnect()

        assert [(e.event_type, e.element_id, e.category) for e in received] == [
            (EventType.ELEMENT_CREATED, 1, "Walls"),
            (EventType.ELEMENT_CREATED, 2, "Doors"),
            (EventType.ELEMENT_MODIFIED, 3, "Walls"),
            (EventType.ELEMENT_DELETED, 4, None),
        ]
        assert all(e.data["transactions"] == ["Move walls"] for e in received)

    def test_handler_errors_do_not_reach_revit(self, manager: EventManager) -> None:
        def explode(_event: Any) -> None:
            raise RuntimeError("boom")

        handler = CallableEventHandler(callback=explode, name="exploder")
        manager.register_handler(handler, [EventType.ELEMENT_MODIFIED])
        app = FakeApplication()
        bridge = RevitEventBridge(manager, app)
        bridge.connect()
        try:
            app.DocumentChanged.fire(
                None, ChangedArgs([], [9], [], categories={9: "Walls"})
            )
        finally:
            bridge.disconnect()
            manager.unregister_handler(handler, [EventType.ELEMENT_MODIFIED])
