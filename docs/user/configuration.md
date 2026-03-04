---
layout: page
title: Configuration
description: Complete reference for RevitPy configuration classes including Config, ConfigManager, TransactionOptions, CacheConfiguration, and ExtensionManager.
doc_tier: user
---

# Configuration

RevitPy uses several configuration classes to control framework behavior. This page is a reference for all configuration types and their fields.

## Config

`Config` is a simple key-value configuration container defined in `revitpy.config`.

```python
from revitpy import Config

config = Config(debug=True, log_level="INFO", max_retries=3)

# Get a value
value = config.get("debug", default=False)

# Set a value
config.set("debug", False)

# Attribute-style access
level = config.log_level  # "INFO"

# Check if a key exists
if "debug" in config:
    print("debug is configured")

# Export as dictionary
data = config.to_dict()
```

### Methods

| Method | Returns | Description |
|---|---|---|
| `get(key, default=None)` | `Any` | Get a value by key |
| `set(key, value)` | `None` | Set a value |
| `to_dict()` | `dict` | Export all values as a dictionary |

`Config` also supports `__contains__` for `in` checks and `__getattr__` for attribute-style access. Accessing a key that does not exist via attribute returns `None`.

## ConfigManager

`ConfigManager` handles loading configuration from YAML files.

```python
from revitpy import ConfigManager
from pathlib import Path

manager = ConfigManager(config_path=Path("revitpy.yaml"))

# Load configuration from the configured path
config = manager.load()

# Load from a specific path
config = manager.load(Path("other_config.yaml"))

# Access the current config
config = manager.config

# Get a value directly
value = manager.get("debug", default=False)
```

The `load` method reads a YAML file using `yaml.safe_load` and creates a `Config` instance from the resulting dictionary. If the file does not exist, the existing config is returned unchanged.

### Constructor

```python
ConfigManager(config_path: Path | None = None)
```

### Methods

| Method | Returns | Description |
|---|---|---|
| `load(path=None)` | `Config` | Load config from a YAML file |
| `get(key, default=None)` | `Any` | Get a value from the current config |

### Properties

| Property | Type | Description |
|---|---|---|
| `config` | `Config` | The current configuration |

## TransactionOptions

`TransactionOptions` controls transaction behavior. It is a dataclass defined in `revitpy.api.transaction`.

```python
from revitpy.api.transaction import TransactionOptions

options = TransactionOptions(
    name="My Transaction",
    description="Update wall parameters",
    auto_commit=True,
    timeout_seconds=30.0,
    retry_count=2,
    retry_delay=1.0,
    suppress_warnings=False,
)
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` or `None` | Auto-generated | Transaction name. If `None`, a name like `Transaction_<8-char-hex>` is generated automatically. |
| `description` | `str` or `None` | `None` | Human-readable description |
| `auto_commit` | `bool` | `True` | Commit automatically when the context manager exits without error |
| `timeout_seconds` | `float` or `None` | `None` | Timeout in seconds |
| `retry_count` | `int` | `0` | Number of retry attempts on failure |
| `retry_delay` | `float` | `1.0` | Delay between retries in seconds |
| `suppress_warnings` | `bool` | `False` | Suppress transaction warnings |

## ContextConfiguration

`ContextConfiguration` controls the ORM `RevitContext`. It is a dataclass defined in `revitpy.orm.context`.

```python
from revitpy.orm.context import ContextConfiguration
from revitpy.orm.types import CachePolicy

config = ContextConfiguration(
    auto_track_changes=True,
    cache_policy=CachePolicy.MEMORY,
    cache_max_size=10000,
    cache_max_memory_mb=500,
    lazy_loading_enabled=True,
    batch_size=100,
    thread_safe=True,
    validation_enabled=True,
    performance_monitoring=True,
)
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `auto_track_changes` | `bool` | `True` | Automatically track changes to attached entities |
| `cache_policy` | `CachePolicy` | `CachePolicy.MEMORY` | Caching strategy (`NONE`, `MEMORY`, `PERSISTENT`, `AGGRESSIVE`) |
| `cache_max_size` | `int` | `10000` | Maximum number of cached entries |
| `cache_max_memory_mb` | `int` | `500` | Maximum cache memory in MB |
| `lazy_loading_enabled` | `bool` | `True` | Enable lazy loading of relationships |
| `batch_size` | `int` | `100` | Batch size for bulk operations |
| `thread_safe` | `bool` | `True` | Use thread-safe data structures |
| `validation_enabled` | `bool` | `True` | Enable entity validation |
| `performance_monitoring` | `bool` | `True` | Enable cache statistics and monitoring |

## CacheConfiguration

`CacheConfiguration` controls the ORM cache manager. It is a dataclass defined in `revitpy.orm.cache`.

```python
from revitpy.orm.cache import CacheConfiguration, EvictionPolicy

config = CacheConfiguration(
    max_size=10000,
    max_memory_mb=500,
    default_ttl_seconds=3600,
    eviction_policy=EvictionPolicy.LRU,
    enable_statistics=True,
    cleanup_interval_seconds=300,
    compression_enabled=False,
    thread_safe=True,
)
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `max_size` | `int` | `10000` | Maximum number of cached entries (must be positive) |
| `max_memory_mb` | `int` | `500` | Maximum memory usage in MB (must be positive) |
| `default_ttl_seconds` | `int` or `None` | `3600` | Default time-to-live in seconds (1 hour). `None` for no expiry. |
| `eviction_policy` | `EvictionPolicy` | `EvictionPolicy.LRU` | Cache eviction strategy |
| `enable_statistics` | `bool` | `True` | Enable hit/miss statistics tracking |
| `cleanup_interval_seconds` | `int` | `300` | Interval for periodic cleanup (5 minutes) |
| `compression_enabled` | `bool` | `False` | Enable data compression in cache |
| `thread_safe` | `bool` | `True` | Use thread-safe data structures |

### EvictionPolicy Enum

| Policy | Description |
|---|---|
| `LRU` | Least Recently Used -- evict the entry that was accessed longest ago |
| `LFU` | Least Frequently Used -- evict the entry with fewest accesses |
| `FIFO` | First In, First Out -- evict the oldest entry |
| `TTL` | Time To Live only -- evict only when TTL expires |
| `SIZE_BASED` | Based on memory size -- evict largest entries first |

## ExtensionManagerConfig

`ExtensionManagerConfig` controls the extension manager. It is a dataclass defined in `revitpy.extensions.manager`.

```python
from revitpy.extensions.manager import ExtensionManagerConfig
from pathlib import Path

config = ExtensionManagerConfig(
    extension_directories=[Path("./extensions"), Path("./plugins")],
    auto_load_extensions=True,
    auto_activate_extensions=True,
    dependency_resolution=True,
    max_load_retries=3,
    extension_timeout=30.0,
)
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `extension_directories` | `list[Path]` | `[]` | Directories to scan for extensions |
| `auto_load_extensions` | `bool` | `True` | Automatically load discovered extensions |
| `auto_activate_extensions` | `bool` | `True` | Automatically activate loaded extensions |
| `dependency_resolution` | `bool` | `True` | Resolve extension dependencies automatically |
| `max_load_retries` | `int` | `3` | Maximum retries when loading an extension |
| `extension_timeout` | `float` | `30.0` | Timeout in seconds for extension operations |

## DocumentInfo

`DocumentInfo` is a dataclass returned by `RevitAPI.get_document_info()`. It is defined in `revitpy.api.wrapper`.

```python
info = api.get_document_info()
print(info.title)       # "MyProject.rvt"
print(info.path)        # "/path/to/MyProject.rvt"
print(info.name)        # "MyProject" (title without extension)
print(info.is_modified) # False
print(info.is_read_only)# False
print(info.version)     # None or a version string
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | Required | Document title (filename) |
| `path` | `str` | Required | Full file path |
| `is_modified` | `bool` | `False` | Whether the document has unsaved changes |
| `is_read_only` | `bool` | `False` | Whether the document is read-only |
| `version` | `str` or `None` | `None` | Revit version |

The `name` property returns the title without the file extension.
