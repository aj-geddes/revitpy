---
layout: api
title: Extensions Framework API
description: Plugin architecture for loading, managing, and coordinating RevitPy extensions
---

# Extensions Framework API

The Extensions Framework provides a singleton-based plugin architecture for dynamically discovering, loading, activating, and coordinating RevitPy extensions. It includes dependency injection, lifecycle management, and extension registry support.

---

## ExtensionManagerConfig

Configuration dataclass for the extension manager.

**Module:** `revitpy.extensions.manager`

### Constructor

```python
ExtensionManagerConfig(
    extension_directories: list[Path] = [],
    auto_load_extensions: bool = True,
    auto_activate_extensions: bool = True,
    dependency_resolution: bool = True,
    max_load_retries: int = 3,
    extension_timeout: float = 30.0
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `extension_directories` | `list[Path]` | `[]` | Directories to scan for extensions. |
| `auto_load_extensions` | `bool` | `True` | Automatically load discovered extensions. |
| `auto_activate_extensions` | `bool` | `True` | Automatically activate loaded extensions. |
| `dependency_resolution` | `bool` | `True` | Resolve extension dependencies before loading. |
| `max_load_retries` | `int` | `3` | Maximum retries when loading an extension fails. |
| `extension_timeout` | `float` | `30.0` | Timeout in seconds for extension operations. |

---

## ExtensionManager

Singleton manager that coordinates the lifecycle of all RevitPy extensions: discovery, loading, activation, deactivation, dependency resolution, and shutdown.

**Module:** `revitpy.extensions.manager`

### Constructor / Singleton

```python
mgr = ExtensionManager()                    # returns singleton
mgr = ExtensionManager(config)              # returns singleton with config (first call only)
mgr = ExtensionManager.get_instance(config) # explicit singleton access
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `ExtensionManagerConfig` or `None` | Configuration. Uses defaults if `None`. Only applied on first instantiation. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_initialized` | `bool` | Whether the manager has been initialized. |
| `extension_count` | `int` | Number of registered extensions. |
| `active_extension_count` | `int` | Number of currently active extensions. |
| `container` | `DIContainer` | The dependency injection container. |
| `registry` | `ExtensionRegistry` | The extension registry. |
| `loader` | `ExtensionLoader` | The extension loader. |
| `lifecycle_manager` | `LifecycleManager` | The lifecycle manager. |
| `config` | `ExtensionManagerConfig` | The current configuration. |

### Lifecycle Methods

#### `initialize()`

Initializes the extension manager asynchronously. Registers core services with the DI container and runs auto-discovery if `auto_load_extensions` is `True`.

```python
await mgr.initialize()
```

#### `shutdown(timeout=30.0)`

Shuts down the extension manager. Deactivates all extensions in reverse order, disposes them, clears the registry, and disposes the DI container.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Timeout in seconds. Default `30.0`. |

```python
await mgr.shutdown(timeout=10.0)
```

### Discovery and Loading

#### `discover_extensions()`

Discovers extensions in all configured directories, registers their metadata, and optionally loads them.

**Returns:** `list[ExtensionMetadata]` -- List of discovered extension metadata.

```python
discovered = await mgr.discover_extensions()
print(f"Found {len(discovered)} extensions")
```

#### `load_extension(name_or_id)`

Loads an extension by name or ID. Resolves dependencies first if `dependency_resolution` is enabled. Auto-activates if `auto_activate_extensions` is `True`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `bool` -- `True` if the extension was loaded successfully.

```python
success = await mgr.load_extension("wall_analyzer")
```

#### `unload_extension(name_or_id)`

Unloads an extension. Deactivates it first if active, then disposes it and removes it from all internal collections.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `bool` -- `True` if the extension was unloaded successfully.

### Activation / Deactivation

#### `activate_extension(name_or_id)`

Activates an extension. If the extension is not yet loaded, attempts to load it first.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `bool` -- `True` if the extension is now active.

#### `deactivate_extension(name_or_id)`

Deactivates an active extension.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `bool` -- `True` if the extension was deactivated (or was already inactive).

### Extension Access

#### `get_extension(name_or_id)`

Gets a loaded extension by name or ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `Extension` or `None`

#### `get_extensions()`

Returns all registered extensions as a dictionary.

**Returns:** `dict[str, Extension]`

#### `get_active_extensions()`

Returns only active extensions.

**Returns:** `dict[str, Extension]`

#### `get_extensions_by_status(status)`

Returns extensions matching a given status.

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | `ExtensionStatus` | Status to filter by. |

**Returns:** `list[Extension]`

#### `has_extension(name_or_id)`

Checks whether an extension is registered.

**Returns:** `bool`

#### `is_extension_active(name_or_id)`

Checks whether an extension is currently active.

**Returns:** `bool`

### Statistics and Information

#### `get_statistics()`

Returns extension manager statistics.

**Returns:** `dict[str, Any]` -- Contains `total_extensions`, `active_extensions`, `extensions_by_status`, `extension_directories`, `auto_load_enabled`, and `auto_activate_enabled`.

#### `get_extension_info(name_or_id)`

Returns detailed information about a specific extension.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name_or_id` | `str` | Extension name or ID. |

**Returns:** `dict[str, Any]` or `None` -- Contains `metadata`, `status`, `is_active`, `has_error`, `last_error`, `commands`, `services`, `tools`, and `analyzers`.

### Context Manager

```python
async with ExtensionManager(config) as mgr:
    # initialize() called on entry
    await mgr.load_extension("my_extension")
# shutdown() called on exit
```

---

## Global Convenience Functions

**Module:** `revitpy.extensions.manager`

```python
from revitpy.extensions.manager import (
    get_extension_manager,
    load_extension,
    activate_extension,
    get_extension,
)

# Get global singleton
mgr = get_extension_manager()

# Load an extension globally
await load_extension("wall_analyzer")

# Activate an extension globally
await activate_extension("wall_analyzer")

# Get an extension globally
ext = get_extension("wall_analyzer")
```

---

## Usage Examples

### Basic Lifecycle

```python
from pathlib import Path
from revitpy.extensions.manager import ExtensionManager, ExtensionManagerConfig

config = ExtensionManagerConfig(
    extension_directories=[Path("./extensions")],
    auto_load_extensions=True,
    auto_activate_extensions=True,
)

async with ExtensionManager(config) as mgr:
    # Extensions are discovered and loaded automatically
    print(f"Active: {mgr.active_extension_count}")

    # Get a specific extension
    ext = mgr.get_extension("wall_analyzer")
    if ext:
        print(f"Extension status: {ext.status}")
```

### Manual Loading and Activation

```python
from revitpy.extensions.manager import ExtensionManager

mgr = ExtensionManager()
await mgr.initialize()

# Load without auto-activation
mgr.config.auto_activate_extensions = False
success = await mgr.load_extension("report_generator")

if success:
    # Activate when ready
    await mgr.activate_extension("report_generator")

# Check extension info
info = mgr.get_extension_info("report_generator")
if info:
    print(f"Commands: {info['commands']}")
    print(f"Services: {info['services']}")

await mgr.shutdown()
```

### Monitoring Extension Statistics

```python
from revitpy.extensions.manager import get_extension_manager

mgr = get_extension_manager()
stats = mgr.get_statistics()

print(f"Total extensions: {stats['total_extensions']}")
print(f"Active extensions: {stats['active_extensions']}")
print(f"By status: {stats['extensions_by_status']}")
```

---

## Best Practices

1. **Use the async context manager** -- It handles `initialize()` and `shutdown()` automatically.
2. **Configure discovery directories** -- Set `extension_directories` to scan for extensions at startup.
3. **Enable dependency resolution** -- Keep `dependency_resolution=True` to ensure extensions load in the correct order.
4. **Check load results** -- `load_extension()` returns `bool`; always verify success before using the extension.
5. **Shut down cleanly** -- Call `shutdown()` or use the context manager to deactivate and dispose all extensions.
6. **Use `get_extension_info()` for debugging** -- It provides a full view of an extension's state, commands, services, and errors.

---

## Next Steps

- **[Event System]({{ '/reference/api/events/' | relative_url }})**: Combine extensions with event-driven patterns
- **[Core API]({{ '/reference/api/core/' | relative_url }})**: The underlying `RevitAPI` interface
- **[Testing]({{ '/reference/api/testing/' | relative_url }})**: Test extensions with mock objects
