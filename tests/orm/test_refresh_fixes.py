"""Regression tests for ORM change tracking and DI disposal fixes."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from revitpy.extensions.dependency_injection import DIContainer
from revitpy.extensions.extension import Extension, ExtensionMetadata
from revitpy.orm import RevitContext
from revitpy.orm.change_tracker import ChangeTracker
from revitpy.orm.types import ElementState


@dataclass
class Item:
    id: int
    name: str
    comments: str = ""


def make_context(items: list[Item]) -> RevitContext:
    provider = SimpleNamespace(
        get_all_elements=lambda: list(items),
        get_elements_of_type=lambda t: [i for i in items if isinstance(i, t)],
        get_element_by_id=lambda eid: next((i for i in items if i.id == eid), None),
    )
    return RevitContext(provider)


class TestUpdateAndReject:
    def test_update_tracks_modification(self) -> None:
        item = Item(1, "a")
        ctx = make_context([item])
        ctx.update(item, comments="checked")
        assert item.comments == "checked"
        assert ctx.has_changes
        assert ctx.get_entity_state(item) == ElementState.MODIFIED

    def test_update_tracks_even_without_auto_tracking(self) -> None:
        item = Item(1, "a")
        ctx = make_context([item])
        ctx._change_tracker.auto_track = False
        ctx.update(item, comments="checked")
        assert ctx.has_changes
        assert ctx._change_tracker.auto_track is False

    def test_reject_restores_value_before_first_change(self) -> None:
        item = Item(1, "a", comments="orig")
        ctx = make_context([item])
        ctx.update(item, comments="x")
        ctx.update(item, comments="y")
        ctx.reject_changes()
        assert item.comments == "orig"
        assert not ctx.has_changes

    def test_reject_leaves_untracked_properties_alone(self) -> None:
        item = Item(1, "a")
        ctx = make_context([item])
        ctx.attach(item)
        ctx.update(item, comments="x")
        item.name = "renamed directly"
        ctx.reject_changes()
        assert item.name == "renamed directly"
        assert item.comments == ""

    def test_tracking_none_raises(self) -> None:
        with pytest.raises(ValueError):
            ChangeTracker().track_property_change(None, "x", 1, 2)


class TestAsyncWithSyncProvider:
    async def test_get_all_and_by_id(self) -> None:
        items = [Item(1, "a"), Item(2, "b")]
        actx = make_context(items).as_async()
        assert len(await actx.get_all_async()) == 2
        assert len(await actx.get_all_async(Item)) == 2
        found = await actx.get_by_id_async(2)
        assert found is items[1]


class SyncService:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class AsyncService:
    def __init__(self) -> None:
        self.dispose_calls = 0

    async def dispose(self) -> None:
        self.dispose_calls += 1


class OtherInterface:
    pass


class TestDIContainerDisposal:
    def test_sync_dispose_once_per_instance(self) -> None:
        service = SyncService()
        container = DIContainer()
        container.register_singleton(SyncService, instance=service)
        container.register_singleton(OtherInterface, instance=service)
        container.dispose()
        assert service.dispose_calls == 1

    def test_sync_dispose_skips_async_services(self) -> None:
        service = AsyncService()
        container = DIContainer()
        container.register_singleton(AsyncService, instance=service)
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # "never awaited" would fail
            container.dispose()
        assert service.dispose_calls == 0

    def test_sync_dispose_exclude(self) -> None:
        kept, disposed = SyncService(), SyncService()
        container = DIContainer()
        container.register_singleton(SyncService, instance=kept)
        container.register_singleton(OtherInterface, instance=disposed)
        container.dispose(exclude=(kept,))
        assert (kept.dispose_calls, disposed.dispose_calls) == (0, 1)

    async def test_dispose_async_handles_both_kinds(self) -> None:
        sync_service, async_service, excluded = (
            SyncService(),
            AsyncService(),
            AsyncService(),
        )
        container = DIContainer()
        container.register_singleton(SyncService, instance=sync_service)
        container.register_singleton(AsyncService, instance=async_service)
        container.register_singleton(OtherInterface, instance=excluded)
        await container.dispose_async(exclude=(excluded,))
        assert sync_service.dispose_calls == 1
        assert async_service.dispose_calls == 1
        assert excluded.dispose_calls == 0


class SampleExtension(Extension):
    async def load(self) -> None:
        pass

    async def activate(self) -> None:
        pass

    async def deactivate(self) -> None:
        pass


class TestExtensionDispose:
    async def test_dispose_does_not_recurse_or_leak_coroutines(self) -> None:
        extension = SampleExtension(ExtensionMetadata(name="x", version="1.0.0"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            await extension.dispose()
