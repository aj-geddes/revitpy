---
layout: page
title: Data Model
description: Explore the RevitPy ORM data model including Pydantic entity types, validation rules, cache system, change tracking, relationships, and query pipeline.
doc_tier: technical
---

# Data Model

This document covers the RevitPy ORM data model: the entity type hierarchy, Pydantic validation rules, cache system, change tracking, relationship management, and the query execution pipeline.

All types are defined in `revitpy/orm/validation.py`, `revitpy/orm/types.py`, `revitpy/orm/cache.py`, `revitpy/orm/change_tracker.py`, `revitpy/orm/relationships.py`, and `revitpy/orm/query_builder.py`.

## ORM Entity Types

### BaseElement

Defined in `revitpy/orm/validation.py`. All entity models inherit from `BaseElement`, which extends Pydantic v2's `BaseModel`.

```python
class BaseElement(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        validate_default=True,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        strict=False,
        arbitrary_types_allowed=True,
    )

    id: ElementId          # Required, unique identifier
    name: str | None       # max_length=1000, stripped of whitespace
    category: str | None   # max_length=255, stripped of whitespace
    level_id: ElementId | None
    family_name: str | None  # max_length=255
    type_name: str | None    # max_length=255
    created_at: datetime     # Auto-set to UTC now
    modified_at: datetime    # Auto-set to UTC now
    version: int             # >= 1, default 1
    is_valid: bool           # default True
    state: ElementState      # default UNCHANGED
```

The `validate_assignment=True` setting means every field assignment after construction is validated through Pydantic. The `extra="allow"` setting permits dynamic properties for Revit-specific attributes not covered by the base schema.

**Field validators** on `BaseElement`:
- `validate_name` -- strips whitespace; converts empty strings to `None`.
- `validate_category` -- strips whitespace; converts empty strings to `None`.

**Model validator** (`mode="after"`):
- `validate_element` -- updates `modified_at` timestamp on every model change.

### WallElement

```python
class WallElement(BaseElement):
    height: float      # gt=0, warns if > 100 ft
    length: float      # gt=0
    width: float       # gt=0, warns if > 5 ft (wall thickness)
    area: float | None   # ge=0, auto-calculated as height * length
    volume: float | None # ge=0, auto-calculated as height * length * width
    base_constraint: str | None
    top_constraint: str | None
    base_offset: float       # default 0.0
    top_offset: float        # default 0.0
    structural_material: str | None
    finish_material_interior: str | None
    finish_material_exterior: str | None
    structural: bool         # default False
    fire_rating: int | None  # ge=0, le=4 (hours)
```

**Validators:**
- `validate_height` -- rejects <= 0; logs warning if > 100 ft.
- `validate_width` -- rejects <= 0; logs warning if > 5 ft.
- `calculate_derived_properties` (model validator, `mode="after"`) -- auto-computes `area` and `volume` from dimensions if not provided.

**Cross-property validation** (in `ElementValidator._validate_element_specific`):
- Checks `area` consistency: `|area - height * length| <= 0.1`.
- Checks `volume` consistency: `|volume - height * length * width| <= 0.1`.

### RoomElement

```python
class RoomElement(BaseElement):
    number: str         # min_length=1, max_length=50
    area: float         # ge=0, warns if > 10,000 sq ft
    perimeter: float    # ge=0
    volume: float       # ge=0
    department: str | None     # max_length=255
    occupancy: int | None      # ge=0
    ceiling_height: float | None  # gt=0
    temperature: float | None  # ge=-50, le=150 (Fahrenheit)
    humidity: float | None     # ge=0, le=100 (percentage)
    air_flow_required: float | None  # ge=0 (CFM)
```

**Validators:**
- `validate_room_number` -- strips whitespace; rejects empty; allows only alphanumeric plus `.-_`.
- `validate_area` -- rejects negative; logs warning if > 10,000 sq ft.

**Cross-property validation:**
- Occupancy check: if `area / occupancy < 50`, flags as too high (minimum 50 sq ft per person).

### DoorElement

```python
class DoorElement(BaseElement):
    width: float        # gt=0, warns if > 20 ft
    height: float       # gt=0, warns if > 20 ft
    material: str | None
    fire_rating: float | None  # ge=0, le=4 (hours)
    hardware_set: str | None
    hand: str | None           # pattern: ^(Left|Right)$
    operation_type: str | None # e.g. Swing, Sliding
```

**Validators:**
- `validate_dimensions` -- applied to both `width` and `height`; rejects <= 0; logs warning if > 20 ft.

### WindowElement

```python
class WindowElement(BaseElement):
    width: float        # gt=0
    height: float       # gt=0
    glass_type: str | None
    frame_material: str | None
    u_factor: float | None           # gt=0
    solar_heat_gain: float | None    # ge=0, le=1 (SHGC coefficient)
    sound_transmission_class: int | None  # ge=0, le=100 (STC rating)
    energy_star_rated: bool          # default False
```

### ElementState Enum

Defined in `revitpy/orm/types.py`:

| State | Description |
|---|---|
| `UNCHANGED` | Entity matches the data source |
| `ADDED` | New entity, not yet persisted |
| `MODIFIED` | Entity has pending changes |
| `DELETED` | Entity marked for deletion |
| `DETACHED` | Entity is not tracked by any context |

### Validation Infrastructure

The `ElementValidator` class supports four strictness levels via the `ValidationLevel` enum:

| Level | Behaviour |
|---|---|
| `NONE` | Skip all validation |
| `BASIC` | Basic type checking only |
| `STANDARD` | Standard validation rules (default) |
| `STRICT` | Strict validation with all constraints |

Custom validation rules can be added at runtime via `ValidationRule` objects:

```python
rule = ValidationRule(
    property_name="height",
    constraint_type=ConstraintType.MAX_VALUE,
    constraint_value=50.0,
    error_message="Height exceeds project limit",
)
validator.add_custom_rule(rule)
```

Supported constraint types: `REQUIRED`, `MIN_VALUE`, `MAX_VALUE`, `MIN_LENGTH`, `MAX_LENGTH`, `PATTERN`, `CUSTOM`.

A global default validator is available via `get_validator()` and its level can be changed with `set_validation_level()`.

## Cache System

Defined in `revitpy/orm/cache.py`.

### CacheConfiguration

| Parameter | Default | Description |
|---|---|---|
| `max_size` | 10,000 | Maximum number of entries |
| `max_memory_mb` | 500 | Maximum memory usage in MB |
| `default_ttl_seconds` | 3,600 | Default time-to-live (1 hour) |
| `eviction_policy` | `LRU` | Eviction strategy |
| `enable_statistics` | `True` | Track hit/miss/eviction counters |
| `cleanup_interval_seconds` | 300 | Interval for expired entry cleanup (5 min) |
| `compression_enabled` | `False` | Data compression (reserved) |
| `thread_safe` | `True` | Use RLock for thread safety |

### Eviction Policies

Defined by the `EvictionPolicy` enum:

| Policy | Strategy |
|---|---|
| `LRU` | Least Recently Used -- evicts the entry that was accessed least recently. Implemented via `OrderedDict.move_to_end()`. |
| `LFU` | Least Frequently Used -- evicts the entry with the lowest `access_count`. |
| `FIFO` | First In, First Out -- evicts the oldest entry by insertion order. |
| `TTL` | Time To Live only -- relies solely on TTL expiration. |
| `SIZE_BASED` | Based on estimated memory size per entry. |

### Cache Architecture

```
CacheManager (high-level API)
  |
  +-- CacheBackend (abstract)
        |
        +-- MemoryCache (default in-memory implementation)
              |
              +-- OrderedDict[str, CacheEntry]
              +-- Dependency tracking (key -> dependent keys)
              +-- Reverse dependency index (dependent -> source keys)
```

`CacheManager` wraps a `CacheBackend` and adds:

- **CacheStatistics** -- tracks hits, misses, evictions, invalidations, and memory usage. All statistics counters are guarded by `threading.RLock`.
- **Invalidation callbacks** -- registered functions called whenever a cache entry is invalidated.
- **Dependency-based invalidation** -- `invalidate_by_dependency(dependency)` cascades to all entries that declared a dependency on the given key.
- **Pattern-based invalidation** -- `invalidate_by_pattern(pattern)` removes all entries whose key string contains the pattern.

### Cache Keys

`CacheKey` is a dataclass with four optional components:

```python
@dataclass
class CacheKey:
    entity_type: str
    query_hash: str | None = None
    entity_id: Any | None = None
    relationship_path: str | None = None
```

String representation: `entity_type|id:entity_id|query:query_hash|rel:relationship_path`.

Factory functions:
- `create_entity_cache_key(entity_type, entity_id)` -- for individual entity lookup.
- `create_query_cache_key(entity_type, query_hash)` -- for query result caching.
- `create_relationship_cache_key(entity_type, entity_id, relationship_path)` -- for relationship data.

### Cache Entries

`CacheEntry` carries the cached data along with metadata:

```python
@dataclass
class CacheEntry:
    key: CacheKey
    data: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    ttl_seconds: int | None = None
    dependencies: set[str] = field(default_factory=set)
```

The `is_expired` property checks `(now - created_at) > ttl_seconds`. The `mark_accessed()` method updates `accessed_at` and increments `access_count`.

Memory estimation uses a constant of approximately 1,000 bytes per entry (`MEMORY_USAGE_PER_ENTRY_BYTES`), and capacity checks use 0.001 MB per entry (`MEMORY_PER_ENTRY_ESTIMATE_MB`).

## Change Tracking

Defined in `revitpy/orm/change_tracker.py`.

### Change Types

The `ChangeType` enum covers:

| Type | Description |
|---|---|
| `PROPERTY_CHANGED` | A property value was modified |
| `RELATIONSHIP_ADDED` | A relationship was added |
| `RELATIONSHIP_REMOVED` | A relationship was removed |
| `ENTITY_ADDED` | A new entity was attached |
| `ENTITY_DELETED` | An entity was marked for deletion |
| `ENTITY_ATTACHED` | An entity was attached to the tracker |
| `ENTITY_DETACHED` | An entity was detached from the tracker |

### EntityTracker

Each tracked entity gets its own `EntityTracker` instance, which stores:

- `original_values` -- snapshot taken at attach time via `snapshot_current_state()`.
- `current_values` -- accumulated changes.
- `property_changes` -- dictionary of `PropertyChange` objects keyed by property name.
- `relationship_changes` -- list of `RelationshipChange` objects.
- `state` -- current `ElementState`.
- `version` -- incremented on each `accept_changes()` and `snapshot_current_state()`.

The `is_dirty` property returns `True` when `state != UNCHANGED` or when there are any tracked property or relationship changes.

### ChangeTracker

The main `ChangeTracker` class manages a collection of `EntityTracker` instances:

- `attach(entity, entity_id)` -- begins tracking; takes an initial state snapshot.
- `detach(entity_id)` -- stops tracking.
- `track_property_change(entity, property_name, old_value, new_value)` -- records a property change; auto-attaches if not tracked.
- `track_relationship_change(entity, relationship_name, change_type, related_entity)` -- records a relationship change.
- `mark_as_added(entity)` / `mark_as_deleted(entity)` -- set entity state.
- `accept_changes(entity_id=None)` -- moves current values to original; clears change records.
- `reject_changes(entity_id=None)` -- reverts entity attributes to `original_values`.
- `get_all_changes()` -- returns `ChangeSet` objects for all dirty entities.

Thread safety is controlled by the `thread_safe` constructor parameter. When enabled, all public methods acquire a `threading.RLock`.

A `@track_changes` decorator is provided for automatic change tracking on setter methods.

### Batch Operations

`ChangeTracker` also supports batch operations via `BatchOperation` objects:

```python
@dataclass
class BatchOperation:
    operation_type: BatchOperationType  # INSERT, UPDATE, DELETE, BULK_UPDATE
    entity: Any
    properties: dict[str, Any]
    operation_id: UUID
    dependencies: list[UUID]
```

## Relationship Management

Defined in `revitpy/orm/relationships.py`.

### Relationship Types

| Type | Class | Description |
|---|---|---|
| One-to-One | `OneToOneRelationship` | Single related entity |
| One-to-Many | `OneToManyRelationship` | Collection of related entities; supports `add()` and `remove()` |
| Many-to-Many | `ManyToManyRelationship` | Collection with junction table awareness |

All relationship classes inherit from `Relationship[T, R]` and implement both `load(entity)` and `load_async(entity)`.

### Load Strategies

Defined by the `LoadStrategy` enum in `revitpy/orm/types.py`:

| Strategy | Description |
|---|---|
| `LAZY` | Load on first access |
| `EAGER` | Load with parent entity |
| `SELECT` | Use a separate select query |
| `BATCH` | Batch load multiple entities |

### Relationship Configuration

```python
@dataclass
class RelationshipConfiguration:
    name: str
    relationship_type: RelationshipType
    target_entity: type
    foreign_key: str | None = None
    inverse_property: str | None = None
    load_strategy: LoadStrategy = LoadStrategy.LAZY
    cascade: set[CascadeAction] = field(default_factory=set)
    cache_enabled: bool = True
    batch_size: int = 100
```

Cascade actions: `NONE`, `DELETE`, `DELETE_ORPHAN`, `MERGE`, `PERSIST`, `REFRESH`, `DETACH`.

### RelationshipManager

`RelationshipManager` is the central registry for all relationships:

- `register_one_to_one(source_type, name, target_type, ...)` -- registers a 1:1 relationship.
- `register_one_to_many(source_type, name, target_type, ...)` -- registers a 1:N relationship.
- `register_many_to_many(source_type, name, target_type, ...)` -- registers an M:N relationship.
- `load_relationship(entity, relationship_name)` -- loads relationship data using the registered loader.
- `invalidate_entity(entity)` -- invalidates all cached relationship data for an entity.

Inverse relationships are tracked in a separate `_inverse_relationships` dictionary for bidirectional navigation.

### Caching Integration

Each relationship instance maintains:
- An in-memory `_loaded_entities` dictionary for fast re-access.
- Integration with `CacheManager` for persistent caching when `cache_enabled=True`.

When a relationship collection is modified (via `add()` or `remove()` on `OneToManyRelationship`), the corresponding cache entry is automatically invalidated.

## Query Execution Pipeline

### Pipeline Stages

```
1. QueryBuilder.where/select/order_by/skip/take/distinct
   (Appends operations to QueryPlan, returns new QueryBuilder clone)
       |
2. Terminal method called (to_list, first, count, etc.)
       |
3. QueryPlan.optimize()
   - Moves filters before projections
   - Estimates cost (filter=2.0, select=1.0, order_by=3.0, skip/take=0.1, distinct=2.5)
   - Sets use_index=True if any filters exist
   - Enables parallel_execution if estimated_cost > 10.0
   - Applies OPTIMIZATION_IMPROVEMENT_FACTOR (0.8) to total cost
       |
4. LazyQueryExecutor.execute()
   - Checks query cache (by MD5 hash of plan operations)
   - Fetches initial elements from provider (by type or all)
   - Builds lazy generator chain:
     * filter -> generator expression
     * select -> generator expression
     * order_by -> sorted() (materialises)
     * skip -> itertools.islice(elements, count, None)
     * take -> itertools.islice(elements, count)
     * distinct -> custom generator with seen-set
   - Materialises with list()
   - Caches results if < 1,000 elements and cache policy != NONE
       |
5. Result returned to caller
```

### Async Execution

Async terminal methods (`to_list_async`, `first_async`, `count_async`) delegate to `LazyQueryExecutor.execute_async()`, which runs the synchronous pipeline in a thread executor via `asyncio.get_event_loop().run_in_executor()`.

### Streaming Execution

`StreamingQuery` wraps a `QueryBuilder` and yields results in batches:

```python
streaming = context.query(WallElement).where(...).as_streaming(batch_size=100)
async for batch in streaming:
    process(batch)
```

For queries with `parallel_execution` enabled, the full result set is computed first and then yielded in chunks. For smaller queries, all results are yielded in a single batch.
