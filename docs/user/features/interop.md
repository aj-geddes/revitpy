---
layout: page
title: Speckle Interoperability
description: Push and pull Revit elements to Speckle projects, models and versions with RevitPy and specklepy. Covers type mapping, real-time version subscriptions, property diffing, and merge.
doc_tier: user
---

RevitPy includes an interop layer for bidirectional synchronisation with [Speckle](https://speckle.systems/). The `revitpy.interop` module provides type mapping between RevitPy elements and Speckle objects, push/pull sync operations built on the official [`specklepy`](https://pypi.org/project/specklepy/) SDK, property-level diffing, conflict-aware merging, and real-time version subscriptions over WebSocket.

## Speckle Terminology

RevitPy follows Speckle's current data model:

| Speckle (current) | Formerly | Meaning |
|---|---|---|
| **Project** | Stream | Top-level container you share with collaborators |
| **Model** | Branch | A named line of data inside a project (e.g. `main`, `structure`) |
| **Version** | Commit | An immutable snapshot of a model that points at one root object |

Objects themselves live in Speckle's content-addressed object store: every object id is a hash of its content, computed by `specklepy` when the object is sent.

## Installation

Speckle network operations need the optional `interop` extra, which installs `specklepy`:

```bash
pip install "revitpy[interop]"
```

`revitpy.interop` always imports without it -- type mapping, diffing and merging work offline -- but any call that talks to a Speckle server raises an `ImportError` with the install hint above. Check availability at runtime:

```python
from revitpy.interop import speckle_available

if speckle_available():
    print("specklepy is installed")
```

## Quick Start

For simple one-shot operations, use the convenience functions at module level. Sending requires a [personal access token](https://speckle.guide/dev/tokens.html):

```python
from revitpy.interop import push_to_speckle, pull_from_speckle, sync
from revitpy.interop import SyncMode, SyncDirection, SpeckleConfig

config = SpeckleConfig(token="your-personal-access-token")

# Push elements as a new version of a model
result = await push_to_speckle(
    elements,
    project_id="abc123",
    model="main",            # created automatically if it does not exist
    message="Updated wall layout",
    config=config,
)
print(f"Sent {result.objects_sent} objects")
print(f"Version {result.version_id}, root object {result.object_id}")

# Pull elements from a model (latest version unless version_id is given)
elements = await pull_from_speckle(
    project_id="abc123",
    model="main",
    version_id="def456",     # optional
    config=config,
)

# Full bidirectional sync
result = await sync(
    elements,
    project_id="abc123",
    mode=SyncMode.INCREMENTAL,
    direction=SyncDirection.BIDIRECTIONAL,
    config=config,
)
```

All three convenience functions accept an optional `config` parameter of type `SpeckleConfig` for connecting to a self-hosted server or providing an auth token. When `project_id` is omitted, `config.default_project` is used.

### Migrating from stream/branch/commit arguments

Earlier releases used Speckle's legacy names. They still work but emit a `DeprecationWarning`:

| Deprecated | Use instead |
|---|---|
| `stream_id=` | `project_id=` |
| `branch=` | `model=` |
| `commit_id=` | `version_id=` |
| `SpeckleClient.get_streams()` / `get_stream()` | `get_projects()` / `get_project()` |
| `SpeckleClient.get_branches()` | `get_models()` |
| `SpeckleClient.get_commits()` | `get_versions()` |
| `SpeckleConfig.default_stream` | `SpeckleConfig.default_project` |

`SyncResult.commit_id` is kept and holds the *version* id (also available as `SyncResult.version_id`). Positional arguments keep their old order and meaning (project, model, version).

## SpeckleConfig

`SpeckleConfig` controls the connection to a Speckle server.

| Field | Type | Default | Description |
|---|---|---|---|
| `server_url` | `str` | `"https://app.speckle.systems"` | Speckle server URL (`http://` disables TLS, e.g. for a local server) |
| `token` | `str \| None` | `None` | Personal access token; required for sending and for subscriptions |
| `default_project` | `str \| None` | `None` | Project used when `project_id` is omitted |
| `default_stream` | `str \| None` | `None` | Deprecated alias of `default_project` |

```python
from revitpy.interop import SpeckleConfig

config = SpeckleConfig(
    server_url="https://speckle.mycompany.com",
    token="your-personal-access-token",
    default_project="abc123",
)
```

## SpeckleTypeMapper

`SpeckleTypeMapper` maintains a bidirectional registry of mappings between RevitPy element type names and Speckle object type identifiers. A default set of mappings is pre-loaded at construction time.

### Default Mappings

| RevitPy Type | Speckle Type |
|---|---|
| `WallElement` | `Objects.BuiltElements.Wall:Wall` |
| `RoomElement` | `Objects.BuiltElements.Room:Room` |
| `DoorElement` | `Objects.BuiltElements.Door:Door` |
| `WindowElement` | `Objects.BuiltElements.Window:Window` |
| `SlabElement` | `Objects.BuiltElements.Floor:Floor` |
| `RoofElement` | `Objects.BuiltElements.Roof:Roof` |
| `ColumnElement` | `Objects.BuiltElements.Column:Column` |
| `BeamElement` | `Objects.BuiltElements.Beam:Beam` |
| `StairElement` | `Objects.BuiltElements.Stair:Stair` |
| `RailingElement` | `Objects.BuiltElements.Railing:Railing` |

### Registering Custom Mappings

Use `register_mapping` to add custom type mappings with an optional property map that controls how attribute names are translated between systems:

```python
from revitpy.interop import SpeckleTypeMapper

mapper = SpeckleTypeMapper()

mapper.register_mapping(
    revitpy_type="CurtainWallElement",
    speckle_type="Objects.BuiltElements.CurtainWall:CurtainWall",
    property_map={
        "panel_count": "panelCount",
        "grid_spacing": "gridSpacing",
    },
)
```

The `property_map` dict maps RevitPy attribute names (keys) to Speckle property names (values). When no `property_map` is provided, all public non-callable attributes are copied automatically.

### Converting Elements

Convert a RevitPy element to a Speckle-compatible dict with `to_speckle`, or convert a Speckle object dict back with `from_speckle`:

```python
# RevitPy element -> Speckle dict
speckle_dict = mapper.to_speckle(wall_element)
# Returns: {"speckle_type": "Objects.BuiltElements.Wall:Wall", "id": ..., "name": ..., ...}

# Speckle dict -> RevitPy-compatible dict
revitpy_dict = mapper.from_speckle(speckle_dict)
# Returns: {"type": "WallElement", "speckle_type": ..., "id": ..., "name": ..., ...}

# Override target type explicitly
revitpy_dict = mapper.from_speckle(speckle_dict, target_type="WallElement")
```

Both methods raise `TypeMappingError` when no mapping is found for the element type.

### Inspecting the Registry

```python
# List all registered RevitPy types
mapper.registered_types
# ["WallElement", "RoomElement", "DoorElement", ...]

# List all registered Speckle types
mapper.registered_speckle_types
# ["Objects.BuiltElements.Wall:Wall", ...]

# Get a specific mapping
mapping = mapper.get_mapping("WallElement")
# Returns TypeMapping or None

# Get an UNMAPPED placeholder for an unregistered type
placeholder = mapper.get_unmapped_status("CustomElement")
# Returns TypeMapping with status=MappingStatus.UNMAPPED
```

### TypeMapping Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `revitpy_type` | `str` | -- | RevitPy element type name |
| `speckle_type` | `str` | -- | Speckle object type identifier |
| `property_map` | `dict[str, str]` | `{}` | RevitPy-to-Speckle property name map |
| `status` | `MappingStatus` | `MappingStatus.MAPPED` | Current mapping status |

### MappingStatus Enum

| Value | Description |
|---|---|
| `MAPPED` | Mapping is fully established |
| `UNMAPPED` | No mapping exists for this type |
| `PARTIAL` | Some properties are mapped but not all |
| `FAILED` | Mapping was attempted but failed |

## SpeckleClient

`SpeckleClient` is an async wrapper around the `specklepy` SDK (`specklepy.api.client.SpeckleClient`). The SDK client is created lazily and authenticated with `authenticate_with_token` when `config.token` is set. `specklepy` is synchronous, so every call runs in a worker thread via `asyncio.to_thread`. The underlying SDK client is available as `client.sdk_client` for anything RevitPy does not wrap.

### Connecting

```python
from revitpy.interop import SpeckleClient, SpeckleConfig

config = SpeckleConfig(
    server_url="https://speckle.mycompany.com",
    token="your-token",
)
client = SpeckleClient(config=config)

# Validate the connection (fetches server info)
await client.connect()
print(client.is_connected)  # True

# Release the SDK client when done
await client.close()
```

### Projects and Models

```python
# Projects visible to the authenticated user
projects = await client.get_projects(limit=25)
for p in projects:
    print(p["id"], p["name"])

# A single project by ID
project = await client.get_project("abc123")

# Models in a project
models = await client.get_models("abc123")
for m in models:
    print(m["id"], m["name"])

# Resolve a model name to its id (optionally creating it)
model_id = await client.resolve_model_id("abc123", "main", create=True)
```

### Versions

```python
versions = await client.get_versions("abc123", model="main", limit=10)
for v in versions:
    print(v.id, v.message, v.author, v.referenced_object)
```

Each version is returned as a `SpeckleCommit` dataclass (also exported as `SpeckleVersion`):

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | -- | Version identifier |
| `message` | `str` | -- | Version message |
| `author` | `str` | -- | Author name |
| `created_at` | `str` | -- | ISO timestamp |
| `source_application` | `str` | `"revitpy"` | Application that created the version |
| `total_objects` | `int` | `0` | Number of objects sent (set by `send_objects`) |
| `referenced_object` | `str \| None` | `None` | Content hash of the root object the version points at |
| `model_id` | `str \| None` | `None` | Model the version belongs to |
| `project_id` | `str \| None` | `None` | Project the version belongs to |

### Sending and Receiving Objects

`send_objects` converts each dict into a `specklepy` `Base` object (its `speckle_type` is preserved and the RevitPy `id` is stored as `applicationId`), wraps them in a `Collection`, uploads them with `operations.send` through a `ServerTransport`, and creates a version on the model with `client.version.create(CreateVersionInput(...))`. The model is created if it does not exist.

```python
version = await client.send_objects(
    "abc123",
    [{"speckle_type": "Objects.BuiltElements.Wall:Wall", "id": "1", "name": "Wall-1"}],
    model="main",
    message="Pushed walls from RevitPy",
)
print(version.id)                 # version id
print(version.referenced_object)  # root object hash returned by operations.send
```

`receive_objects` looks up the version's `referencedObject`, downloads it with `operations.receive`, flattens any (nested) collections and returns plain dicts. Each dict carries `id` (the original `applicationId` when present), `speckle_id` (the object hash), `speckle_type` and the object's properties.

```python
# Latest version of a model
objects = await client.receive_objects("abc123", model="main")

# A specific version
objects = await client.receive_objects("abc123", version_id="def456")
```

`send_objects` requires `config.token`; without one it raises `SpeckleSyncError`. Any other failure is wrapped in `SpeckleSyncError` with the original exception in `.cause`.

## SpeckleSync

`SpeckleSync` orchestrates push, pull, and bidirectional sync operations. It delegates transport to `SpeckleClient` and type conversion to `SpeckleTypeMapper`.

### Creating a Sync Instance

```python
from revitpy.interop import SpeckleClient, SpeckleSync, SpeckleTypeMapper

client = SpeckleClient(config=config)
mapper = SpeckleTypeMapper()
syncer = SpeckleSync(client=client, mapper=mapper)
```

The `mapper` argument is optional; a default `SpeckleTypeMapper` is created when omitted. You can also pass a `change_tracker` for incremental sync support.

### Push

Push local elements as a new version of a model. Each element is converted via the mapper before sending:

```python
result = await syncer.push(
    elements,
    project_id="abc123",
    model="main",
    message="Layout update",
)
print(f"Sent: {result.objects_sent}, Errors: {len(result.errors)}")
print(f"Version: {result.version_id}, Object: {result.object_id}")
print(f"Duration: {result.duration_ms:.0f}ms")
```

Mapping failures and `SpeckleSyncError`s are collected in `result.errors` rather than raised.

### Pull

Pull objects from a model version and map them back to RevitPy-compatible dicts:

```python
elements = await syncer.pull(
    project_id="abc123",
    model="main",
    version_id="def456",  # optional; latest version if omitted
)
for elem in elements:
    print(elem["type"], elem["name"])
```

### Bidirectional Sync

The `sync` method combines push and pull in a single operation, controlled by `SyncDirection` and `SyncMode`:

```python
from revitpy.interop import SyncMode, SyncDirection

result = await syncer.sync(
    elements,
    project_id="abc123",
    mode=SyncMode.INCREMENTAL,
    direction=SyncDirection.BIDIRECTIONAL,
    model="main",
)
print(f"Sent: {result.objects_sent}, Received: {result.objects_received}")
```

### SyncDirection Enum

| Value | Description |
|---|---|
| `PUSH` | Send local elements to the remote model only |
| `PULL` | Receive remote objects only |
| `BIDIRECTIONAL` | Push then pull in a single operation |

### SyncMode Enum

| Value | Description |
|---|---|
| `FULL` | Synchronise all elements regardless of change state |
| `INCREMENTAL` | Only synchronise elements marked as changed by the change tracker |
| `SELECTIVE` | Synchronise a specific subset of elements |

### SyncResult Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `direction` | `SyncDirection` | -- | Direction of the sync operation |
| `objects_sent` | `int` | `0` | Number of objects pushed |
| `objects_received` | `int` | `0` | Number of objects pulled |
| `errors` | `list[str]` | `[]` | Error messages encountered |
| `commit_id` | `str \| None` | `None` | Id of the version created during push (alias: `version_id` property) |
| `object_id` | `str \| None` | `None` | Root object hash uploaded during push |
| `duration_ms` | `float` | `0.0` | Total operation time in milliseconds |

## SpeckleDiff

`SpeckleDiff` compares two lists of element dicts (local vs. remote) and produces a list of `DiffEntry` records describing additions, removals, and per-property modifications. Elements are matched by their `id`, `element_id`, or `Id` key.

```python
from revitpy.interop import SpeckleDiff

differ = SpeckleDiff()

local = [{"id": "1", "name": "Wall-A", "height": 3.0}]
remote = [{"id": "1", "name": "Wall-A", "height": 4.0}, {"id": "2", "name": "Wall-B"}]

entries = differ.compare(local, remote)
for entry in entries:
    print(entry.element_id, entry.change_type, entry.property_name)
    # "1" "modified" "height" (local_value=3.0, remote_value=4.0)
    # "2" "removed"  None

# Quick boolean check
if differ.has_changes(local, remote):
    print("Models have diverged")
```

### DiffEntry Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `element_id` | `str` | -- | Element identifier |
| `change_type` | `str` | -- | One of `"added"`, `"removed"`, or `"modified"` |
| `property_name` | `str \| None` | `None` | Property that differs (for `"modified"` entries) |
| `local_value` | `Any` | `None` | Value in the local model |
| `remote_value` | `Any` | `None` | Value in the remote model version |

Change types are determined as follows:
- **added** -- element exists locally but not in the remote version
- **removed** -- element exists in the remote version but not locally
- **modified** -- element exists in both but one or more properties differ

## SpeckleMerge

`SpeckleMerge` resolves differences between local and remote element sets using a configurable conflict resolution strategy. It uses `SpeckleDiff` internally.

### Merging Element Sets

```python
from revitpy.interop import SpeckleMerge, ConflictResolution

merger = SpeckleMerge(resolution=ConflictResolution.LOCAL_WINS)

result = merger.merge(
    local_elements=local,
    remote_elements=remote,
    diff_entries=None,  # computed automatically when None
)
print(f"Merged: {result.merged_count}, Conflicts: {result.conflict_count}")
print(f"Strategy: {result.resolution.value}")  # "local_wins"
```

When `diff_entries` is `None`, the merge method calls `SpeckleDiff.compare` internally. You can also pass pre-computed diff entries to avoid redundant computation.

### Resolving Conflicts Manually

If the initial merge used `LOCAL_WINS` or `REMOTE_WINS`, conflicts are auto-resolved. For finer control, retrieve unresolved conflicts from the result and resolve them explicitly:

```python
resolved = merger.resolve_conflicts(
    conflicts=result.conflicts,
    strategy=ConflictResolution.REMOTE_WINS,
)
for r in resolved:
    print(r["element_id"], r["property_name"], r["resolved_value"])
```

When `ConflictResolution.MANUAL` is used as the default strategy, `merge()` raises `MergeConflictError` if any conflicts exist, forcing the caller to handle each one.

### ConflictResolution Enum

| Value | Description |
|---|---|
| `LOCAL_WINS` | Keep local values when properties conflict |
| `REMOTE_WINS` | Keep remote values when properties conflict |
| `MANUAL` | Raise `MergeConflictError` on any conflict; caller must resolve |

### MergeResult Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `merged_count` | `int` | `0` | Number of entries successfully merged |
| `conflict_count` | `int` | `0` | Number of property-level conflicts detected |
| `conflicts` | `list[DiffEntry]` | `[]` | Conflict entries (change_type `"modified"`) |
| `resolution` | `ConflictResolution` | `ConflictResolution.LOCAL_WINS` | Strategy that was applied |

## SpeckleSubscriptions

`SpeckleSubscriptions` listens for new versions in real time using Speckle's current `projectVersionsUpdated` GraphQL subscription (via `specklepy`'s `client.subscription.project_versions_updated`). The legacy `commitCreated` stream subscription no longer exists on current servers.

Requirements and behaviour:

- `specklepy` must be installed and `SpeckleConfig.token` must be set (WebSocket subscriptions require authentication).
- Each subscription runs as an `asyncio` task in the current event loop.
- The server reports version events for every model in the project; RevitPy filters them to the subscribed model.

```python
from revitpy.interop import SpeckleClient, SpeckleSubscriptions

client = SpeckleClient(config=config)
subs = SpeckleSubscriptions(client=client)

# Callbacks may be sync or async
async def on_version(payload):
    print(f"New version {payload['version_id']} on {payload['model']}")

await subs.subscribe(project_id="abc123", model="main", callback=on_version)

# List active subscriptions
print(subs.active_subscriptions)  # ["abc123/main"]

# Unsubscribe from all models in a project
await subs.unsubscribe("abc123")

# Close all subscriptions
await subs.close()
```

Each payload is a dict with `project_id`, `model`, `model_id`, `type` (`CREATED`, `UPDATED` or `DELETED`), `version_id`, `referenced_object`, `message`, `source_application`, `created_at` and `author`.

If an `event_manager` with a `dispatch(name, payload)` method is passed to the constructor, every matching event is also dispatched as `"speckle.version_created"`. If the WebSocket connection drops, the subscription is marked inactive (it disappears from `active_subscriptions`); call `unsubscribe` and `subscribe` again to reconnect.

## Error Handling

All interop errors inherit from `InteropError`. Specific exception types let you handle different failure modes:

| Exception | Description |
|---|---|
| `InteropError` | Base exception for all interop errors |
| `SpeckleConnectionError` | Server is unreachable, authentication failed, or a subscription could not be set up |
| `SpeckleSyncError` | Send or receive failed (the original error is in `.cause`) |
| `TypeMappingError` | No mapping found for an element or Speckle type |
| `MergeConflictError` | Unresolved conflicts remain when using `MANUAL` resolution |
| `ImportError` | `specklepy` is not installed (`pip install "revitpy[interop]"`) |

`SpeckleSync.push` (and `push_to_speckle`) collect mapping and send errors in `SyncResult.errors`; the lower-level `SpeckleClient` methods raise them.

```python
from revitpy.interop import SpeckleClient, SpeckleConnectionError, SpeckleSyncError

client = SpeckleClient(config=config)
try:
    await client.connect()
    version = await client.send_objects("abc123", objects, model="main")
except SpeckleConnectionError as exc:
    print(f"Connection failed: {exc}")
except SpeckleSyncError as exc:
    print(f"Send failed: {exc} (cause: {exc.cause!r})")
finally:
    await client.close()

result = await push_to_speckle(elements, project_id="abc123", config=config)
if result.errors:
    print("Push had problems:", result.errors)
```
