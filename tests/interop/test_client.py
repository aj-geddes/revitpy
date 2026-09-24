"""
Unit tests for SpeckleClient.

The specklepy SDK is mocked at its boundary: the specklepy client object
(``client._sdk``), ``specklepy.api.operations.send/receive`` and
``specklepy.transports.server.ServerTransport``.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("specklepy")

from specklepy.api import operations as speckle_ops  # noqa: E402
from specklepy.objects.models.collections.collection import (  # noqa: E402
    Collection,
)

from revitpy.interop.client import (  # noqa: E402
    SpeckleClient,
    _parse_server_url,
    base_to_dict,
    dict_to_base,
    flatten_received,
)
from revitpy.interop.exceptions import (  # noqa: E402
    SpeckleConnectionError,
    SpeckleSyncError,
)
from revitpy.interop.types import SpeckleCommit, SpeckleConfig  # noqa: E402

WALL = {
    "id": "wall-1",
    "name": "Wall A",
    "speckle_type": "Objects.BuiltElements.Wall:Wall",
    "height": 10,
}
ROOM = {
    "id": "room-1",
    "name": "Room 101",
    "speckle_type": "Objects.BuiltElements.Room:Room",
    "area": 200,
}


def make_version(vid="ver-1", obj="obj-hash-1"):
    """Build a stand-in for a specklepy ``Version`` model."""
    return SimpleNamespace(
        id=vid,
        message="msg",
        author_user=SimpleNamespace(name="tester"),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        referenced_object=obj,
        source_application="revitpy",
    )


def dumpable(**fields):
    """Build a stand-in for a pydantic model with ``model_dump``."""
    return SimpleNamespace(**fields, model_dump=lambda: dict(fields))


@pytest.fixture
def config():
    return SpeckleConfig(server_url="https://test.speckle.dev", token="test-token")


@pytest.fixture
def sdk():
    sdk = MagicMock()
    sdk.server.get.return_value = SimpleNamespace(name="Test Server", version="3.0")
    sdk.model.get_models.return_value = SimpleNamespace(
        items=[dumpable(id="model-1", name="main")]
    )
    sdk.active_user.get_projects.return_value = SimpleNamespace(
        items=[dumpable(id="p1", name="Project 1")]
    )
    sdk.project.get.return_value = dumpable(id="p1", name="Project 1")
    sdk.version.get_versions.return_value = SimpleNamespace(items=[])
    return sdk


@pytest.fixture
def client(config, sdk):
    c = SpeckleClient(config)
    c._sdk = sdk
    return c


@pytest.fixture
def patched_transport():
    with patch("specklepy.transports.server.ServerTransport") as transport_cls:
        yield transport_cls


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_success_sets_is_connected(self, client, sdk):
        await client.connect()
        assert client.is_connected is True
        sdk.server.get.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self, client, sdk):
        sdk.server.get.side_effect = RuntimeError("boom")
        with pytest.raises(SpeckleConnectionError, match="Failed to connect"):
            await client.connect()
        assert client.is_connected is False


class TestBuildSdkClient:
    def test_build_sdk_client_with_token(self, config):
        with patch("specklepy.api.client.SpeckleClient") as sdk_cls:
            SpeckleClient(config)._build_sdk_client()
        sdk_cls.assert_called_once_with(host="test.speckle.dev", use_ssl=True)
        sdk_cls.return_value.authenticate_with_token.assert_called_once_with(
            "test-token"
        )

    def test_build_sdk_client_without_token(self):
        with patch("specklepy.api.client.SpeckleClient") as sdk_cls:
            SpeckleClient(SpeckleConfig())._build_sdk_client()
        sdk_cls.assert_called_once_with(host="app.speckle.systems", use_ssl=True)
        sdk_cls.return_value.authenticate_with_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sdk_is_lazy_and_cached(self, config):
        with patch("specklepy.api.client.SpeckleClient") as sdk_cls:
            c = SpeckleClient(config)
            assert c.sdk_client is None
            first = await c._get_sdk()
            second = await c._get_sdk()
        assert first is second is sdk_cls.return_value
        sdk_cls.assert_called_once()


class TestProjectsModelsVersions:
    @pytest.mark.asyncio
    async def test_get_projects(self, client, sdk):
        assert await client.get_projects(limit=5) == [{"id": "p1", "name": "Project 1"}]
        sdk.active_user.get_projects.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_get_project(self, client, sdk):
        assert await client.get_project("p1") == {"id": "p1", "name": "Project 1"}
        sdk.project.get.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_get_models(self, client, sdk):
        assert await client.get_models("p1") == [{"id": "model-1", "name": "main"}]
        sdk.model.get_models.assert_called_once_with("p1", models_limit=25)

    @pytest.mark.asyncio
    async def test_get_versions(self, client, sdk):
        sdk.version.get_versions.return_value = SimpleNamespace(
            items=[make_version("ver-1", "obj-1")]
        )
        versions = await client.get_versions("p1", model="main", limit=5)

        assert len(versions) == 1
        version = versions[0]
        assert isinstance(version, SpeckleCommit)
        assert version.id == "ver-1"
        assert version.author == "tester"
        assert version.referenced_object == "obj-1"
        assert version.model_id == "model-1"
        assert version.project_id == "p1"
        assert version.created_at.startswith("2025-01-01")
        sdk.version.get_versions.assert_called_once_with("model-1", "p1", limit=5)


class TestResolveModelId:
    @pytest.mark.asyncio
    async def test_by_name(self, client):
        assert await client.resolve_model_id("p1", "main") == "model-1"

    @pytest.mark.asyncio
    async def test_falls_back_to_get_by_id(self, client, sdk):
        sdk.model.get_models.return_value = SimpleNamespace(items=[])
        sdk.model.get.return_value = SimpleNamespace(id="model-2", name="design")

        assert await client.resolve_model_id("p1", "model-2") == "model-2"
        sdk.model.get.assert_called_once_with("model-2", "p1")

    @pytest.mark.asyncio
    async def test_creates_when_requested(self, client, sdk):
        sdk.model.get_models.return_value = SimpleNamespace(items=[])
        sdk.model.get.side_effect = Exception("not found")
        sdk.model.create.return_value = SimpleNamespace(id="model-new", name="design")

        assert await client.resolve_model_id("p1", "design", create=True) == (
            "model-new"
        )
        model_input = sdk.model.create.call_args.args[0]
        assert model_input.name == "design"
        assert model_input.project_id == "p1"

    @pytest.mark.asyncio
    async def test_missing_raises(self, client, sdk):
        sdk.model.get_models.return_value = SimpleNamespace(items=[])
        sdk.model.get.side_effect = Exception("not found")

        with pytest.raises(SpeckleSyncError, match="not found"):
            await client.resolve_model_id("p1", "design")
        sdk.model.create.assert_not_called()


class TestSendObjects:
    @pytest.mark.asyncio
    async def test_send_objects_returns_id_from_operations_send(
        self, client, sdk, patched_transport
    ):
        sdk.version.create.return_value = make_version("ver-99", None)
        object_hash = "f" * 32

        with patch(
            "specklepy.api.operations.send", return_value=object_hash
        ) as send_mock:
            commit = await client.send_objects("p1", [WALL], message="push")

        # The returned ids come from Speckle, not from local fabrication.
        assert commit.referenced_object == object_hash
        assert commit.id == "ver-99"
        assert commit.total_objects == 1
        assert commit.model_id == "model-1"
        assert commit.project_id == "p1"

        send_mock.assert_called_once()
        root, transports = send_mock.call_args.args
        assert isinstance(root, Collection)
        assert root.name == "revitpy"
        wall = root.elements[0]
        assert wall.speckle_type == "Objects.BuiltElements.Wall:Wall"
        assert wall.applicationId == "wall-1"
        assert wall["height"] == 10
        assert transports == [patched_transport.return_value]
        assert send_mock.call_args.kwargs == {"use_default_cache": False}
        patched_transport.assert_called_once_with(stream_id="p1", client=sdk)

        version_input = sdk.version.create.call_args.args[0]
        assert version_input.object_id == object_hash
        assert version_input.model_id == "model-1"
        assert version_input.project_id == "p1"
        assert version_input.source_application == "revitpy"
        assert version_input.total_children_count == 1
        assert version_input.message == "push"

    @pytest.mark.asyncio
    async def test_default_message(self, client, sdk, patched_transport):
        sdk.version.create.return_value = make_version("ver-1", None)
        with patch("specklepy.api.operations.send", return_value="a" * 32):
            await client.send_objects("p1", [WALL, ROOM])
        version_input = sdk.version.create.call_args.args[0]
        assert version_input.message == "revitpy push (2 objects)"

    @pytest.mark.asyncio
    async def test_creates_missing_model(self, client, sdk, patched_transport):
        sdk.model.get_models.return_value = SimpleNamespace(items=[])
        sdk.model.get.side_effect = Exception("not found")
        sdk.model.create.return_value = SimpleNamespace(id="model-new", name="design")
        sdk.version.create.return_value = make_version("ver-new", None)

        with patch("specklepy.api.operations.send", return_value="b" * 32):
            commit = await client.send_objects("p1", [WALL], model="design")

        assert commit.model_id == "model-new"
        sdk.model.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_wraps_operations_failure(self, client, sdk, patched_transport):
        with (
            patch("specklepy.api.operations.send", side_effect=RuntimeError("boom")),
            pytest.raises(SpeckleSyncError) as exc_info,
        ):
            await client.send_objects("p1", [WALL])

        assert exc_info.value.direction == "push"
        assert exc_info.value.stream_id == "p1"
        assert isinstance(exc_info.value.cause, RuntimeError)
        sdk.version.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_token(self, sdk):
        c = SpeckleClient(SpeckleConfig(server_url="https://test.speckle.dev"))
        c._sdk = sdk
        with (
            patch("specklepy.api.operations.send") as send_mock,
            pytest.raises(SpeckleSyncError, match="auth token"),
        ):
            await c.send_objects("p1", [WALL])
        send_mock.assert_not_called()


class TestReceiveObjects:
    @pytest.mark.asyncio
    async def test_receive_latest_version(self, client, sdk, patched_transport):
        sdk.version.get_versions.return_value = SimpleNamespace(
            items=[make_version("ver-1", "obj-1")]
        )
        root = Collection(
            name="root",
            elements=[
                dict_to_base(WALL),
                Collection(name="nested", elements=[dict_to_base(ROOM)]),
            ],
        )

        with patch(
            "specklepy.api.operations.receive", return_value=root
        ) as receive_mock:
            objects = await client.receive_objects("p1")

        assert [o["id"] for o in objects] == ["wall-1", "room-1"]
        assert [o["speckle_type"] for o in objects] == [
            "Objects.BuiltElements.Wall:Wall",
            "Objects.BuiltElements.Room:Room",
        ]
        assert objects[0]["height"] == 10
        assert objects[1]["area"] == 200
        receive_mock.assert_called_once_with(
            "obj-1", remote_transport=patched_transport.return_value
        )
        sdk.version.get_versions.assert_called_once_with("model-1", "p1", limit=1)

    @pytest.mark.asyncio
    async def test_receive_specific_version(self, client, sdk, patched_transport):
        sdk.version.get.return_value = make_version("ver-7", "obj-7")

        with patch(
            "specklepy.api.operations.receive",
            return_value=dict_to_base(WALL),
        ) as receive_mock:
            objects = await client.receive_objects("p1", version_id="ver-7")

        assert [o["id"] for o in objects] == ["wall-1"]
        sdk.version.get.assert_called_once_with(version_id="ver-7", project_id="p1")
        assert receive_mock.call_args.args == ("obj-7",)
        sdk.version.get_versions.assert_not_called()

    @pytest.mark.asyncio
    async def test_receive_without_versions(self, client, sdk):
        with patch("specklepy.api.operations.receive") as receive_mock:
            assert await client.receive_objects("p1") == []
        receive_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_receive_wraps_failure(self, client, sdk, patched_transport):
        sdk.version.get.return_value = make_version("ver-7", "obj-7")
        with (
            patch(
                "specklepy.api.operations.receive",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(SpeckleSyncError) as exc_info,
        ):
            await client.receive_objects("p1", version_id="ver-7")

        assert exc_info.value.direction == "pull"
        assert isinstance(exc_info.value.cause, RuntimeError)


class TestDeprecatedAliases:
    @pytest.mark.asyncio
    async def test_get_streams(self, client):
        with pytest.warns(DeprecationWarning, match="get_projects"):
            assert await client.get_streams() == [{"id": "p1", "name": "Project 1"}]

    @pytest.mark.asyncio
    async def test_get_stream(self, client):
        with pytest.warns(DeprecationWarning, match="get_project"):
            assert (await client.get_stream("p1"))["id"] == "p1"

    @pytest.mark.asyncio
    async def test_get_branches(self, client):
        with pytest.warns(DeprecationWarning, match="get_models"):
            assert (await client.get_branches("p1"))[0]["name"] == "main"

    @pytest.mark.asyncio
    async def test_get_commits(self, client, sdk):
        with pytest.warns(DeprecationWarning, match="get_versions"):
            await client.get_commits("p1", branch="main", limit=3)
        sdk.version.get_versions.assert_called_once_with("model-1", "p1", limit=3)

    @pytest.mark.asyncio
    async def test_send_branch_kwarg(self, client, sdk, patched_transport):
        sdk.version.create.return_value = make_version("ver-1", None)
        with (
            patch("specklepy.api.operations.send", return_value="c" * 32),
            pytest.warns(DeprecationWarning, match="branch"),
        ):
            await client.send_objects("p1", [WALL], branch="main")

    @pytest.mark.asyncio
    async def test_receive_commit_id_kwarg(self, client, sdk, patched_transport):
        sdk.version.get.return_value = make_version("ver-7", "obj-7")
        with (
            patch(
                "specklepy.api.operations.receive",
                return_value=dict_to_base(WALL),
            ),
            pytest.warns(DeprecationWarning, match="commit_id"),
        ):
            await client.receive_objects("p1", commit_id="ver-7")
        sdk.version.get.assert_called_once_with(version_id="ver-7", project_id="p1")


class TestMissingSpecklepy:
    @pytest.mark.asyncio
    async def test_connect_raises_install_hint(self, config, monkeypatch):
        monkeypatch.setattr("revitpy.interop._compat._HAS_SPECKLEPY", False)
        with pytest.raises(ImportError, match=r"revitpy\[interop\]"):
            await SpeckleClient(config).connect()

    @pytest.mark.asyncio
    async def test_send_raises_install_hint(self, config, monkeypatch):
        monkeypatch.setattr("revitpy.interop._compat._HAS_SPECKLEPY", False)
        with pytest.raises(ImportError, match=r"revitpy\[interop\]"):
            await SpeckleClient(config).send_objects("p1", [WALL])

    @pytest.mark.asyncio
    async def test_receive_raises_install_hint(self, config, monkeypatch):
        monkeypatch.setattr("revitpy.interop._compat._HAS_SPECKLEPY", False)
        with pytest.raises(ImportError, match=r"revitpy\[interop\]"):
            await SpeckleClient(config).receive_objects("p1")


class TestConversionHelpers:
    def test_round_trip_through_serialization(self):
        base = dict_to_base({**WALL, "comment": None})
        assert base.speckle_type == "Objects.BuiltElements.Wall:Wall"
        assert base.applicationId == "wall-1"
        assert "comment" not in base.get_dynamic_member_names()

        received = speckle_ops.deserialize(speckle_ops.serialize(base))
        result = base_to_dict(received)

        assert result["id"] == "wall-1"
        assert result["speckle_type"] == "Objects.BuiltElements.Wall:Wall"
        assert result["name"] == "Wall A"
        assert result["height"] == 10
        assert len(result["speckle_id"]) == 32
        int(result["speckle_id"], 16)
        assert "totalChildrenCount" not in result

    def test_content_hash_is_deterministic(self):
        first = speckle_ops.deserialize(speckle_ops.serialize(dict_to_base(WALL)))
        second = speckle_ops.deserialize(speckle_ops.serialize(dict_to_base(WALL)))
        assert first.id == second.id

    def test_flatten_non_collection(self):
        base = dict_to_base(WALL)
        assert flatten_received(base) == [base]

    def test_flatten_nested_collections(self):
        wall, room = dict_to_base(WALL), dict_to_base(ROOM)
        root = Collection(
            name="root",
            elements=[wall, Collection(name="nested", elements=[room])],
        )
        assert flatten_received(root) == [wall, room]

    def test_flatten_empty_collection(self):
        assert flatten_received(Collection(name="empty", elements=[])) == []

    def test_nested_base_values_converted(self):
        base = dict_to_base(WALL)
        base["material"] = dict_to_base({"id": "mat-1", "speckle_type": "Material"})
        result = base_to_dict(base)
        assert result["material"]["id"] == "mat-1"
        assert result["material"]["speckle_type"] == "Material"


class TestParseServerUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://app.speckle.systems", ("app.speckle.systems", True)),
            ("https://app.speckle.systems/", ("app.speckle.systems", True)),
            ("http://localhost:3000", ("localhost:3000", False)),
            ("speckle.example.com/", ("speckle.example.com", True)),
        ],
    )
    def test_parse_server_url(self, url, expected):
        assert _parse_server_url(url) == expected


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_close_resets_state(self, client):
        await client.connect()
        await client.close()
        assert client.sdk_client is None
        assert client.is_connected is False

    def test_config_property(self, client, config):
        assert client.config is config


def test_package_imports_without_specklepy():
    """revitpy.interop must import (and fail clearly) without specklepy."""
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import asyncio, sys
        sys.modules["specklepy"] = None  # simulate "not installed"
        import revitpy.interop as interop
        assert interop.speckle_available() is False
        try:
            asyncio.run(interop.SpeckleClient().connect())
        except ImportError as exc:
            assert "revitpy[interop]" in str(exc)
        else:
            raise SystemExit("expected ImportError")
        print("ok")
        """
    )
    result = subprocess.run(  # noqa: S603 - runs this interpreter
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")
