"""
Unit tests for SpeckleSubscriptions.

The specklepy subscription resource (``sdk.subscription``) is replaced
with a fake async stream that feeds ``ProjectVersionsUpdatedMessage``
stand-ins to the handler.
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

pytest.importorskip("specklepy")

from revitpy.interop.client import SpeckleClient  # noqa: E402
from revitpy.interop.exceptions import SpeckleConnectionError  # noqa: E402
from revitpy.interop.subscriptions import (  # noqa: E402
    VERSION_CREATED_EVENT,
    SpeckleSubscriptions,
)
from revitpy.interop.types import SpeckleConfig  # noqa: E402


def make_message(model_id="model-1", version_id="ver-1"):
    return SimpleNamespace(
        id="p1",
        type=SimpleNamespace(value="CREATED"),
        model_id=model_id,
        version=SimpleNamespace(
            id=version_id,
            referenced_object="obj-1",
            message="m",
            source_application="revitpy",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            author_user=SimpleNamespace(name="tester"),
        ),
    )


def make_stream(messages, *, forever=True, raise_exc=None, calls=None):
    """Return a fake ``project_versions_updated`` coroutine function."""

    async def fake_stream(handler, id):  # noqa: A002 - mirrors specklepy
        if calls is not None:
            calls.append(id)
        for message in messages:
            handler(message)
        if raise_exc is not None:
            raise raise_exc
        if forever:
            await asyncio.Event().wait()

    return fake_stream


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.fixture
def stream_calls():
    return []


@pytest.fixture
def sdk(stream_calls):
    sdk = MagicMock()
    sdk.subscription.project_versions_updated = make_stream(
        [make_message("model-1", "ver-1"), make_message("other", "ver-2")],
        calls=stream_calls,
    )
    return sdk


@pytest.fixture
def client(sdk):
    c = SpeckleClient(SpeckleConfig(server_url="https://test.speckle.dev", token="t"))
    c._get_sdk = AsyncMock(return_value=sdk)
    c.resolve_model_id = AsyncMock(return_value="model-1")
    return c


@pytest_asyncio.fixture
async def subs(client):
    subscriptions = SpeckleSubscriptions(client)
    yield subscriptions
    await subscriptions.close()


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_delivers_only_matching_model_events(
        self, subs, client, stream_calls
    ):
        received = []
        await subs.subscribe("p1", "main", callback=received.append)
        await settle()

        assert len(received) == 1
        payload = received[0]
        assert payload["project_id"] == "p1"
        assert payload["model"] == "main"
        assert payload["model_id"] == "model-1"
        assert payload["type"] == "CREATED"
        assert payload["version_id"] == "ver-1"
        assert payload["referenced_object"] == "obj-1"
        assert payload["author"] == "tester"
        assert payload["created_at"].startswith("2025-01-01")
        assert stream_calls == ["p1"]
        client.resolve_model_id.assert_awaited_once_with("p1", "main")
        assert subs.active_subscriptions == ["p1/main"]

        await subs.close()
        assert subs.active_subscriptions == []

    @pytest.mark.asyncio
    async def test_async_callback_is_awaited(self, subs):
        event = asyncio.Event()

        async def callback(payload):
            event.set()

        await subs.subscribe("p1", callback=callback)
        await asyncio.wait_for(event.wait(), timeout=1)

    @pytest.mark.asyncio
    async def test_event_manager_dispatch(self, client):
        event_manager = MagicMock()
        subscriptions = SpeckleSubscriptions(client, event_manager=event_manager)
        try:
            await subscriptions.subscribe("p1")
            await settle()
        finally:
            await subscriptions.close()

        event_manager.dispatch.assert_called_once()
        event_name, payload = event_manager.dispatch.call_args.args
        assert event_name == VERSION_CREATED_EVENT
        assert payload["version_id"] == "ver-1"

    @pytest.mark.asyncio
    async def test_duplicate_subscribe_ignored(self, subs, client):
        await subs.subscribe("p1", "main")
        await subs.subscribe("p1", "main")
        assert client.resolve_model_id.await_count == 1
        assert subs.active_subscriptions == ["p1/main"]

    @pytest.mark.asyncio
    async def test_callback_exceptions_are_swallowed(self, subs):
        def callback(payload):
            raise ValueError("boom")

        await subs.subscribe("p1", callback=callback)
        await settle()
        assert subs.active_subscriptions == ["p1/main"]

    @pytest.mark.asyncio
    async def test_failing_stream_marks_inactive(self, subs, sdk):
        sdk.subscription.project_versions_updated = make_stream(
            [], raise_exc=RuntimeError("socket closed")
        )
        await subs.subscribe("p1")
        await settle()

        assert subs.active_subscriptions == []
        assert "p1/main" in subs._subscriptions

    @pytest.mark.asyncio
    async def test_setup_failure_raises_connection_error(self, subs, client):
        client.resolve_model_id.side_effect = RuntimeError("nope")
        with pytest.raises(SpeckleConnectionError, match="Failed to subscribe"):
            await subs.subscribe("p1")
        assert subs.active_subscriptions == []

    @pytest.mark.asyncio
    async def test_legacy_kwargs_warn(self, subs, client):
        with pytest.warns(DeprecationWarning):
            await subs.subscribe(stream_id="p1", branch="dev")
        client.resolve_model_id.assert_awaited_once_with("p1", "dev")
        assert subs.active_subscriptions == ["p1/dev"]

    @pytest.mark.asyncio
    async def test_missing_specklepy(self, subs, monkeypatch):
        monkeypatch.setattr("revitpy.interop._compat._HAS_SPECKLEPY", False)
        with pytest.raises(ImportError, match=r"revitpy\[interop\]"):
            await subs.subscribe("p1")


class TestUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_cancels_task(self, subs):
        await subs.subscribe("p1", "main")
        await subs.subscribe("p1", "dev")
        await settle()
        tasks = [entry["task"] for entry in subs._subscriptions.values()]

        await subs.unsubscribe("p1")

        assert subs.active_subscriptions == []
        assert all(task.done() for task in tasks)

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_project_is_noop(self, subs):
        await subs.subscribe("p1")
        await subs.unsubscribe("unknown")
        assert subs.active_subscriptions == ["p1/main"]
