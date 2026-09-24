"""
Speckle client for RevitPy, built on the official ``specklepy`` SDK.

This module wraps ``specklepy`` using Speckle's current terminology:

* **Projects** (formerly *streams*)
* **Models** (formerly *branches*)
* **Versions** (formerly *commits*)

Sending serialises RevitPy element dicts into ``specklepy`` ``Base``
objects inside a ``Collection``, uploads them to the object store via a
``ServerTransport`` (which yields the content-addressed root object id)
and then creates a Version on the target model.  Receiving resolves a
Version's ``referencedObject`` and downloads it with
``operations.receive``.

``specklepy`` is an optional dependency (``pip install revitpy[interop]``).
It is imported lazily so that ``revitpy.interop`` can be imported without
it; every network entry point calls :func:`require_specklepy` first.

All ``specklepy`` calls are synchronous, so they are executed with
:func:`asyncio.to_thread` to keep the public API async.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from ._compat import require_specklepy, resolve_renamed, warn_deprecated
from .exceptions import SpeckleConnectionError, SpeckleSyncError
from .types import SpeckleCommit, SpeckleConfig

__all__ = ["SpeckleClient", "base_to_dict", "dict_to_base", "flatten_received"]

_EXCLUDED_MEMBERS = frozenset(
    {"id", "speckle_type", "applicationId", "totalChildrenCount"}
)


# ---------------------------------------------------------------------------
# Base <-> dict conversion helpers
# ---------------------------------------------------------------------------


def _is_base(value: Any) -> bool:
    """Return whether *value* looks like a specklepy ``Base`` object."""
    return hasattr(value, "speckle_type") and hasattr(value, "get_dynamic_member_names")


def dict_to_base(obj: dict[str, Any]) -> Any:
    """Convert a RevitPy/Speckle object dict into a specklepy ``Base``.

    The dict's ``speckle_type`` becomes the Base's type and its ``id``
    (the RevitPy element id) is stored as ``applicationId``; Speckle
    computes the object ``id`` itself as a content hash.

    Args:
        obj: Dict as produced by :meth:`SpeckleTypeMapper.to_speckle`.

    Returns:
        A ``specklepy.objects.base.Base`` instance.
    """
    require_specklepy()
    from specklepy.objects.base import Base

    base = Base.of_type(obj.get("speckle_type") or "Base")
    if obj.get("id") is not None:
        base.applicationId = str(obj["id"])
    for key, value in obj.items():
        if key in ("speckle_type", "id") or value is None:
            continue
        base[key] = value
    return base


def _convert_value(value: Any) -> Any:
    """Recursively convert nested ``Base`` values into dicts."""
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    if _is_base(value):
        return base_to_dict(value)
    return value


def base_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a specklepy ``Base`` into a plain dict.

    ``id`` is the ``applicationId`` (the originating element id) when
    available, otherwise the Speckle object hash; the hash is always
    available as ``speckle_id``.

    Args:
        obj: A specklepy ``Base`` instance.

    Returns:
        Dict with ``id``, ``speckle_id``, ``speckle_type`` and all
        dynamic properties.
    """
    result: dict[str, Any] = {
        "id": obj.applicationId or obj.id,
        "speckle_id": obj.id,
        "speckle_type": obj.speckle_type,
    }
    for name in obj.get_dynamic_member_names():
        if name in _EXCLUDED_MEMBERS:
            continue
        result[name] = _convert_value(obj[name])
    return result


def _children(obj: Any) -> list[Any] | None:
    """Return the child element list of a container ``Base``, if any."""
    elements = getattr(obj, "elements", None)
    if isinstance(elements, list):
        return elements
    try:
        detached = obj["@elements"]
    except (KeyError, AttributeError, TypeError):
        return None
    return detached if isinstance(detached, list) else None


def flatten_received(root: Any) -> list[Any]:
    """Flatten a received object tree into its leaf (non-container) objects.

    Collections (and any Base with an ``elements`` / ``@elements`` list)
    are traversed recursively; everything else is returned as-is.

    Args:
        root: The root ``Base`` returned by ``operations.receive``.

    Returns:
        List of leaf ``Base`` objects.
    """
    if not _is_base(root):
        return [] if root is None else [root]

    children = _children(root)
    is_container = "Collection" in str(root.speckle_type) or children is not None
    if not is_container:
        return [root]

    leaves: list[Any] = []
    for child in children or []:
        if _is_base(child):
            leaves.extend(flatten_received(child))
    return leaves


def _parse_server_url(url: str) -> tuple[str, bool]:
    """Split a server URL into ``(host, use_ssl)`` for ``specklepy``."""
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc.rstrip("/"), parsed.scheme != "http"
    return (parsed.path or url).rstrip("/"), True


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SpeckleClient:
    """Async client for a Speckle server, backed by ``specklepy``.

    The underlying ``specklepy.api.client.SpeckleClient`` is created
    lazily on first use and authenticated with ``config.token`` when
    provided.  Blocking SDK calls run in a worker thread.

    Args:
        config: Optional Speckle server configuration.  When ``None``
            the public Speckle server is used without authentication.
    """

    def __init__(self, config: SpeckleConfig | None = None) -> None:
        self._config = config or SpeckleConfig()
        self._sdk: Any | None = None
        self._connected = False

    # ------------------------------------------------------------------
    # SDK plumbing
    # ------------------------------------------------------------------

    def _build_sdk_client(self) -> Any:
        """Create and authenticate a ``specklepy`` client (blocking)."""
        require_specklepy()
        from specklepy.api.client import SpeckleClient as _SDKClient

        host, use_ssl = _parse_server_url(self._config.server_url)
        sdk = _SDKClient(host=host, use_ssl=use_ssl)
        if self._config.token:
            sdk.authenticate_with_token(self._config.token)
        return sdk

    async def _get_sdk(self) -> Any:
        """Return (and lazily create) the underlying ``specklepy`` client."""
        require_specklepy()
        if self._sdk is None:
            self._sdk = await asyncio.to_thread(self._build_sdk_client)
        return self._sdk

    @property
    def sdk_client(self) -> Any | None:
        """The underlying ``specklepy`` client, if created."""
        return self._sdk

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Validate the connection to the Speckle server.

        Raises:
            ImportError: If ``specklepy`` is not installed.
            SpeckleConnectionError: If the server is unreachable or
                authentication fails.
        """
        url = self._config.server_url
        try:
            sdk = await self._get_sdk()
            info = await asyncio.to_thread(sdk.server.get)
        except ImportError:
            raise
        except Exception as exc:
            raise SpeckleConnectionError(
                f"Failed to connect to {url}",
                server_url=url,
                cause=exc,
            ) from exc

        logger.info(
            "Connected to Speckle server: {} ({})",
            getattr(info, "name", None) or "unknown",
            getattr(info, "version", None) or "unknown",
        )
        self._connected = True

    # ------------------------------------------------------------------
    # Projects / Models / Versions
    # ------------------------------------------------------------------

    async def get_projects(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return projects visible to the authenticated user.

        Args:
            limit: Maximum number of projects to return.

        Returns:
            List of project dicts (``id``, ``name``, ...).
        """
        sdk = await self._get_sdk()
        result = await asyncio.to_thread(sdk.active_user.get_projects, limit=limit)
        return [project.model_dump() for project in result.items]

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """Return details of a single project.

        Args:
            project_id: The Speckle project identifier.

        Returns:
            Project dict.
        """
        sdk = await self._get_sdk()
        project = await asyncio.to_thread(sdk.project.get, project_id)
        return project.model_dump()

    async def get_models(
        self,
        project_id: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Return the models of a project.

        Args:
            project_id: The Speckle project identifier.
            limit: Maximum number of models to return.

        Returns:
            List of model dicts.
        """
        sdk = await self._get_sdk()
        result = await asyncio.to_thread(
            sdk.model.get_models, project_id, models_limit=limit
        )
        return [model.model_dump() for model in result.items]

    async def resolve_model_id(
        self,
        project_id: str,
        model: str,
        *,
        create: bool = False,
    ) -> str:
        """Resolve a model name (or id) to a model id.

        Args:
            project_id: The Speckle project identifier.
            model: Model name (e.g. ``"main"``) or model id.
            create: Create the model when it does not exist.

        Returns:
            The model id.

        Raises:
            SpeckleSyncError: If the model does not exist and
                ``create`` is ``False``.
        """
        require_specklepy()
        from specklepy.core.api.inputs.model_inputs import CreateModelInput
        from specklepy.core.api.inputs.project_inputs import ProjectModelsFilter

        sdk = await self._get_sdk()
        result = await asyncio.to_thread(
            sdk.model.get_models,
            project_id,
            models_limit=100,
            models_filter=ProjectModelsFilter(search=model),
        )
        for item in result.items:
            if item.name == model or item.id == model:
                return str(item.id)

        try:
            found = await asyncio.to_thread(sdk.model.get, model, project_id)
            return str(found.id)
        except Exception as exc:
            logger.debug("Model {!r} not found by id: {}", model, exc)

        if create:
            created = await asyncio.to_thread(
                sdk.model.create,
                CreateModelInput(name=model, project_id=project_id),
            )
            logger.info("Created model {!r} in project {}", model, project_id)
            return str(created.id)

        raise SpeckleSyncError(
            f"Model '{model}' not found in project {project_id}",
            stream_id=project_id,
        )

    @staticmethod
    def _version_to_commit(
        version: Any,
        *,
        project_id: str,
        model_id: str | None,
    ) -> SpeckleCommit:
        """Convert a ``specklepy`` Version model into a ``SpeckleCommit``."""
        author_user = getattr(version, "author_user", None)
        created = getattr(version, "created_at", None)
        if created is None:
            created_at = ""
        elif hasattr(created, "isoformat"):
            created_at = created.isoformat()
        else:
            created_at = str(created)

        return SpeckleCommit(
            id=str(version.id),
            message=getattr(version, "message", None) or "",
            author=(getattr(author_user, "name", None) or "") if author_user else "",
            created_at=created_at,
            source_application=getattr(version, "source_application", None) or "",
            referenced_object=getattr(version, "referenced_object", None),
            model_id=model_id,
            project_id=project_id,
        )

    async def get_versions(
        self,
        project_id: str,
        model: str = "main",
        limit: int = 10,
    ) -> list[SpeckleCommit]:
        """Return the most recent versions of a model.

        Args:
            project_id: The Speckle project identifier.
            model: Model name or id (default ``"main"``).
            limit: Maximum number of versions to return.

        Returns:
            List of ``SpeckleCommit`` (version) instances, newest first.
        """
        model_id = await self.resolve_model_id(project_id, model)
        sdk = await self._get_sdk()
        result = await asyncio.to_thread(
            sdk.version.get_versions, model_id, project_id, limit=limit
        )
        return [
            self._version_to_commit(v, project_id=project_id, model_id=model_id)
            for v in result.items
        ]

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------

    async def send_objects(
        self,
        project_id: str,
        objects: list[dict[str, Any]],
        model: str = "main",
        message: str = "",
        *,
        branch: str | None = None,
    ) -> SpeckleCommit:
        """Upload objects and create a new Version on a model.

        The objects are wrapped in a ``Collection``, uploaded with
        ``operations.send`` through a ``ServerTransport``, and a Version
        referencing the returned root object id is created.  The model
        is created if it does not exist yet.

        Args:
            project_id: The Speckle project identifier.
            objects: List of Speckle-compatible object dicts.
            model: Target model name or id.
            message: Version message.
            branch: Deprecated alias of ``model``.

        Returns:
            The created version as a ``SpeckleCommit``; ``id`` is the
            version id and ``referenced_object`` the root object hash.

        Raises:
            ImportError: If ``specklepy`` is not installed.
            SpeckleSyncError: If no auth token is configured, or the
                upload or version creation fails.
        """
        if branch is not None:
            model = resolve_renamed(
                None if model == "main" else model,
                branch,
                new_name="model",
                old_name="branch",
            )

        commit_message = message or f"revitpy push ({len(objects)} objects)"

        require_specklepy()
        if not self._config.token:
            raise SpeckleSyncError(
                "Sending to Speckle requires an auth token (SpeckleConfig.token)",
                stream_id=project_id,
                direction="push",
            )

        try:
            sdk = await self._get_sdk()
            from specklepy.api import operations
            from specklepy.core.api.inputs.version_inputs import CreateVersionInput
            from specklepy.objects.models.collections.collection import Collection
            from specklepy.transports.server import ServerTransport

            root = Collection(
                name="revitpy",
                elements=[dict_to_base(obj) for obj in objects],
            )
            transport = ServerTransport(stream_id=project_id, client=sdk)
            object_id: str = await asyncio.to_thread(
                operations.send, root, [transport], use_default_cache=False
            )

            model_id = await self.resolve_model_id(project_id, model, create=True)
            version = await asyncio.to_thread(
                sdk.version.create,
                CreateVersionInput(
                    object_id=object_id,
                    model_id=model_id,
                    project_id=project_id,
                    message=commit_message,
                    source_application="revitpy",
                    total_children_count=len(objects),
                ),
            )
        except (ImportError, SpeckleSyncError):
            raise
        except Exception as exc:
            raise SpeckleSyncError(
                f"Failed to send objects to project {project_id}",
                stream_id=project_id,
                direction="push",
                cause=exc,
            ) from exc

        commit = self._version_to_commit(
            version, project_id=project_id, model_id=model_id
        )
        commit = replace(
            commit,
            message=commit.message or commit_message,
            total_objects=len(objects),
            referenced_object=object_id,
        )
        logger.info(
            "Created version {} (object {}) on {}/{}",
            commit.id,
            object_id,
            project_id,
            model,
        )
        return commit

    async def receive_objects(
        self,
        project_id: str,
        version_id: str | None = None,
        model: str = "main",
        *,
        commit_id: str | None = None,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """Download the objects referenced by a Version.

        When ``version_id`` is ``None`` the latest version of ``model``
        is used.

        Args:
            project_id: The Speckle project identifier.
            version_id: Optional specific version to fetch.
            model: Model name or id used when ``version_id`` is ``None``.
            commit_id: Deprecated alias of ``version_id``.
            branch: Deprecated alias of ``model``.

        Returns:
            List of object dicts (see :func:`base_to_dict`).

        Raises:
            ImportError: If ``specklepy`` is not installed.
            SpeckleSyncError: If the download fails.
        """
        if commit_id is not None:
            version_id = resolve_renamed(
                version_id,
                commit_id,
                new_name="version_id",
                old_name="commit_id",
            )
        if branch is not None:
            model = resolve_renamed(
                None if model == "main" else model,
                branch,
                new_name="model",
                old_name="branch",
            )

        try:
            sdk = await self._get_sdk()
            from specklepy.api import operations
            from specklepy.transports.server import ServerTransport

            if version_id is None:
                versions = await self.get_versions(project_id, model=model, limit=1)
                if not versions:
                    logger.info("No versions on {}/{}", project_id, model)
                    return []
                object_id = versions[0].referenced_object
            else:
                version = await asyncio.to_thread(
                    sdk.version.get, version_id=version_id, project_id=project_id
                )
                object_id = version.referenced_object

            if not object_id:
                return []

            transport = ServerTransport(stream_id=project_id, client=sdk)
            root = await asyncio.to_thread(
                operations.receive, object_id, remote_transport=transport
            )
            objects = [base_to_dict(obj) for obj in flatten_received(root)]
        except (ImportError, SpeckleSyncError):
            raise
        except Exception as exc:
            raise SpeckleSyncError(
                f"Failed to receive objects from project {project_id}",
                stream_id=project_id,
                direction="pull",
                cause=exc,
            ) from exc

        logger.info(
            "Received {} objects from {} (object {})",
            len(objects),
            project_id,
            object_id,
        )
        return objects

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying ``specklepy`` client."""
        self._sdk = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether the client has successfully connected."""
        return self._connected

    @property
    def config(self) -> SpeckleConfig:
        """The current server configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Deprecated stream/branch/commit aliases
    # ------------------------------------------------------------------

    async def get_streams(self) -> list[dict[str, Any]]:
        """Deprecated alias of :meth:`get_projects`."""
        warn_deprecated("SpeckleClient.get_streams", "SpeckleClient.get_projects")
        return await self.get_projects()

    async def get_stream(self, stream_id: str) -> dict[str, Any]:
        """Deprecated alias of :meth:`get_project`."""
        warn_deprecated("SpeckleClient.get_stream", "SpeckleClient.get_project")
        return await self.get_project(stream_id)

    async def get_branches(self, stream_id: str) -> list[dict[str, Any]]:
        """Deprecated alias of :meth:`get_models`."""
        warn_deprecated("SpeckleClient.get_branches", "SpeckleClient.get_models")
        return await self.get_models(stream_id)

    async def get_commits(
        self,
        stream_id: str,
        branch: str = "main",
        limit: int = 10,
    ) -> list[SpeckleCommit]:
        """Deprecated alias of :meth:`get_versions`."""
        warn_deprecated("SpeckleClient.get_commits", "SpeckleClient.get_versions")
        return await self.get_versions(stream_id, model=branch, limit=limit)
