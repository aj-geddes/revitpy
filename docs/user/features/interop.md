---
layout: page
title: Speckle Interoperability
description: Push and pull Revit elements to Speckle streams with RevitPy. Covers type mapping, real-time WebSocket subscriptions, property diffing, and merge.
doc_tier: user
---

# Speckle Interoperability

RevitPy includes a full interop layer for bidirectional synchronisation with [Speckle](https://speckle.systems/). The `revitpy.interop` module provides type mapping between RevitPy elements and Speckle objects, push/pull sync operations, property-level diffing, conflict-aware merging, and real-time commit subscriptions over WebSocket.

The Speckle integration is an optional dependency. Install it with:

```bash
pip install revitpy[speckle]
```

You can check at runtime whether the `specklepy` package is available:

```python
from revitpy.interop import speckle_available

if speckle_available():
    print("specklepy is installed")
```

## Quick Start

For simple one-shot operations, use the convenience functions at module level:

```python
from revitpy.interop import push_to_speckle, pull_from_speckle, sync
from revitpy.interop import SyncMode, SyncDirection, SpeckleConfig

# Push elements to a stream
result = await push_to_speckle(
    elements,
    stream_id="abc123",
    branch="main",
    message="Updated wall layout",
)
print(f"Sent {result.objects_sent} objects, commit {result.commit_id}")

# Pull elements from a stream
elements = await pull_from_speckle(
    stream_id="abc123",
    branch="main",
    commit_id="def456",  # optional; latest commit if omitted
)

# Full bidirectional sync
result = await sync(
    elements,
    stream_id="abc123",
    mode=SyncMode.INCREMENTAL,
    direction=SyncDirection.BIDIRECTIONAL,
)
```

All three convenience functions accept an optional `config` parameter of type `SpeckleConfig` for connecting to a self-hosted server or providing an auth token.

## SpeckleConfig

`SpeckleConfig` controls the connection to a Speckle server.

| Field | Type | Default | Description |
|---|---|---|---|
| `server_url` | `str` | `"https://app.speckle.systems"` | Speckle server URL |
| `token` | `str \| None` | `None` | Personal access token for authentication |
| `default_stream` | `str \| None` | `None` | Default stream identifier |

```python
from revitpy.interop import SpeckleConfig

config = SpeckleConfig(
    server_url="https://speckle.mycompany.com",
    token="your-personal-access-token",
    default_stream="abc123",
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

`SpeckleClient` is an async HTTP client that communicates with the Speckle server GraphQL API using `httpx.AsyncClient`.

### Connecting

```python
from revitpy.interop import SpeckleClient, SpeckleConfig

config = SpeckleConfig(
    server_url="https://speckle.mycompany.com",
    token="your-token",
)
client = SpeckleClient(config=config)

# Validate the connection (sends a serverInfo query)
await client.connect()
print(client.is_connected)  # True

# Always close when done
await client.close()
```

### Listing Streams and Branches

```python
# Get all visible streams
streams = await client.get_streams()
for s in streams:
    print(s["id"], s["name"], s["description"])

# Get a single stream by ID
stream = await client.get_stream("abc123")

# Get branches for a stream
branches = await client.get_branches("abc123")
for b in branches:
    print(b["name"], b["description"])
```

### Working with Commits

```python
# Get recent commits on a branch
commits = await client.get_commits(
    stream_id="abc123",
    branch="main",
    limit=10,
)
for commit in commits:
    print(commit.id, commit.message, commit.author, commit.total_objects)
```

Each commit is returned as a `SpeckleCommit` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | -- | Commit identifier |
| `message` | `str` | -- | Commit message |
| `author` | `str` | -- | Author name |
| `created_at` | `str` | -- | ISO timestamp |
| `source_application` | `str` | `"revitpy"` | Application that created the commit |
| `total_objects` | `int` | `0` | Number of child objects |

### Sending and Receiving Objects

```python
# Send objects and create a commit
commit = await client.send_objects(
    stream_id="abc123",
    objects=[{"speckle_type": "...", "id": "1", "name": "Wall-1"}],
    branch="main",
    message="Pushed walls from RevitPy",
)
print(commit.id)

# Receive objects from the latest commit on a branch
objects = await client.receive_objects(
    stream_id="abc123",
    branch="main",
)

# Receive objects from a specific commit
objects = await client.receive_objects(
    stream_id="abc123",
    commit_id="def456",
)
```

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

Push local elements to a Speckle stream. Each element is converted via the mapper before sending:

```python
result = await syncer.push(
    elements,
    stream_id="abc123",
    branch="main",
    message="Layout update",
)
print(f"Sent: {result.objects_sent}, Errors: {len(result.errors)}")
print(f"Commit: {result.commit_id}, Duration: {result.duration_ms:.0f}ms")
```

### Pull

Pull objects from a stream and map them back to RevitPy-compatible dicts:

```python
elements = await syncer.pull(
    stream_id="abc123",
    branch="main",
    commit_id="def456",  # optional
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
    stream_id="abc123",
    mode=SyncMode.INCREMENTAL,
    direction=SyncDirection.BIDIRECTIONAL,
)
print(f"Sent: {result.objects_sent}, Received: {result.objects_received}")
```

### SyncDirection Enum

| Value | Description |
|---|---|
| `PUSH` | Send local elements to the remote stream only |
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
| `commit_id` | `str \| None` | `None` | Commit ID created during push |
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
| `remote_value` | `Any` | `None` | Value in the remote stream |

Change types are determined as follows:
- **added** -- element exists locally but not on the remote stream
- **removed** -- element exists on the remote stream but not locally
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

`SpeckleSubscriptions` manages real-time GraphQL subscriptions over WebSocket to receive live commit notifications from Speckle streams.

```python
from revitpy.interop import SpeckleClient, SpeckleSubscriptions

client = SpeckleClient(config=config)
subs = SpeckleSubscriptions(client=client)

# Subscribe to a stream/branch with a callback
async def on_commit(payload):
    print(f"New commit: {payload}")

await subs.subscribe(
    stream_id="abc123",
    branch="main",
    callback=on_commit,
)

# List active subscriptions
print(subs.active_subscriptions)  # ["abc123/main"]

# Unsubscribe from all branches on a stream
await subs.unsubscribe(stream_id="abc123")

# Close all subscriptions
await subs.close()
```

The `subscribe` method also accepts an optional `event_manager` (passed at construction time) for dispatching subscription events through a centralised event system.

## Error Handling

All interop errors inherit from `InteropError`. Specific exception types let you handle different failure modes:

| Exception | Description |
|---|---|
| `InteropError` | Base exception for all interop errors |
| `SpeckleConnectionError` | Server is unreachable or returned an unexpected response |
| `SpeckleSyncError` | Push or pull operation failed |
| `TypeMappingError` | No mapping found for an element or Speckle type |
| `MergeConflictError` | Unresolved conflicts remain when using `MANUAL` resolution |

```python
from revitpy.interop import (
    SpeckleConnectionError,
    SpeckleSyncError,
    TypeMappingError,
    MergeConflictError,
)

try:
    result = await push_to_speckle(elements, stream_id="abc123")
except SpeckleConnectionError as exc:
    print(f"Connection failed: {exc}")
except TypeMappingError as exc:
    print(f"Type not mapped: {exc}")
except SpeckleSyncError as exc:
    print(f"Sync error: {exc}")
```
