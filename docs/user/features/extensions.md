---
layout: page
title: Extensions
description: Guide to the RevitPy extension framework with plugin lifecycle management, command and service decorators, and a built-in dependency injection container.
doc_tier: user
---

# Extensions

RevitPy has an extension framework for building modular, reusable plugins. Extensions have a defined lifecycle, can declare commands, services, tools, and analyzers, and benefit from a built-in dependency injection container.

## Extension Base Class

All extensions inherit from the abstract `Extension` class and must implement three lifecycle methods: `load`, `activate`, and `deactivate`.

```python
from revitpy.extensions.extension import Extension, ExtensionMetadata

class MyExtension(Extension):
    def __init__(self):
        metadata = ExtensionMetadata(
            name="My Extension",
            version="1.0.0",
            description="A sample extension",
            author="Your Name",
        )
        super().__init__(metadata)

    async def load(self) -> None:
        """Register services, set up configuration, prepare resources."""
        self.log_info("Loading...")

    async def activate(self) -> None:
        """Start background services, register commands and tools, show UI."""
        self.log_info("Activating...")

    async def deactivate(self) -> None:
        """Stop services, unregister commands, hide UI."""
        self.log_info("Deactivating...")
```

### Extension Lifecycle

Extensions go through these states, tracked by the `ExtensionStatus` enum:

| Status | Description |
|---|---|
| `UNLOADED` | Extension has been created but not loaded |
| `LOADING` | Load is in progress |
| `LOADED` | Extension has been loaded successfully |
| `INITIALIZING` | Activation is in progress |
| `ACTIVE` | Extension is fully active |
| `DEACTIVATING` | Deactivation is in progress |
| `DEACTIVATED` | Extension has been deactivated but can be reactivated |
| `ERROR` | An error occurred during a lifecycle transition |
| `DISPOSED` | Extension has been disposed and cannot be reactivated |

### Lifecycle Methods

Use the public lifecycle management methods rather than calling `load`/`activate`/`deactivate` directly. These methods include error handling and callback execution:

```python
ext = MyExtension()

# Load (sets up DI, loads config, calls load())
success = await ext.load_extension()

# Activate (calls activate(), discovers components)
success = await ext.activate_extension()

# Deactivate (unregisters components, calls deactivate())
success = await ext.deactivate_extension()

# Dispose (deactivates if needed, frees all resources)
await ext.dispose_extension()
```

### Extension Properties

- `ext.name` -- Extension name from metadata.
- `ext.version` -- Extension version from metadata.
- `ext.extension_id` -- Unique UUID string.
- `ext.status` -- Current `ExtensionStatus`.
- `ext.is_loaded` -- `True` if loaded (not unloaded, error, or disposed).
- `ext.is_active` -- `True` if status is `ACTIVE`.
- `ext.has_error` -- `True` if status is `ERROR`.
- `ext.last_error` -- The last exception, or `None`.

### Lifecycle Callbacks

Register callbacks for lifecycle events:

```python
ext.on_load(lambda e: print(f"{e.name} loaded"))
ext.on_activation(lambda e: print(f"{e.name} activated"))
ext.on_deactivation(lambda e: print(f"{e.name} deactivated"))
ext.on_disposal(lambda e: print(f"{e.name} disposed"))
```

Callbacks can be sync or async functions.

## ExtensionMetadata

The `ExtensionMetadata` dataclass describes an extension:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | Required | Extension name |
| `version` | `str` | Required | Version string |
| `description` | `str` | `""` | Description |
| `author` | `str` | `""` | Author name |
| `website` | `str` | `""` | Website URL |
| `license` | `str` | `""` | License identifier |
| `dependencies` | `list[str]` | `[]` | Names of required extensions |
| `revit_versions` | `list[str]` | `[]` | Compatible Revit versions |
| `python_version` | `str` | `">=3.11"` | Required Python version |
| `provides_commands` | `list[str]` | `[]` | Declared command names |
| `provides_services` | `list[str]` | `[]` | Declared service names |
| `provides_tools` | `list[str]` | `[]` | Declared tool names |
| `provides_analyzers` | `list[str]` | `[]` | Declared analyzer names |
| `config_schema` | `dict` or `None` | `None` | Configuration schema |
| `default_config` | `dict` or `None` | `None` | Default configuration values |

`ExtensionMetadata` has a `to_dict()` method for serialization. The `extension_id`, `load_time`, and `activation_time` fields are set automatically.

## ExtensionManager

`ExtensionManager` manages the lifecycle of all extensions. It is a singleton.

```python
from revitpy import ExtensionManager
from revitpy.extensions.manager import ExtensionManagerConfig

config = ExtensionManagerConfig(
    extension_directories=[Path("./extensions")],
    auto_load_extensions=True,
    auto_activate_extensions=True,
    dependency_resolution=True,
    max_load_retries=3,
    extension_timeout=30.0,
)

manager = ExtensionManager(config)

# Initialize (registers core services, discovers extensions)
await manager.initialize()

# Or use as an async context manager
async with ExtensionManager(config) as manager:
    # manager is initialized
    pass
# manager.shutdown() is called automatically
```

### Loading and Unloading

```python
# Load by name or ID
success = await manager.load_extension("My Extension")

# Unload
success = await manager.unload_extension("My Extension")

# Activate / deactivate
success = await manager.activate_extension("My Extension")
success = await manager.deactivate_extension("My Extension")
```

### Extension Discovery

Extensions are discovered in the directories listed in `ExtensionManagerConfig.extension_directories`:

```python
discovered = await manager.discover_extensions()
```

### Accessing Extensions

```python
ext = manager.get_extension("My Extension")
all_exts = manager.get_extensions()
active = manager.get_active_extensions()
by_status = manager.get_extensions_by_status(ExtensionStatus.ACTIVE)

manager.has_extension("My Extension")      # True/False
manager.is_extension_active("My Extension") # True/False
manager.extension_count                     # Total count
manager.active_extension_count              # Active count
```

### Statistics

```python
stats = manager.get_statistics()
info = manager.get_extension_info("My Extension")
```

## Component Decorators

RevitPy provides decorators to declare extension components. When an extension is activated, it auto-discovers methods decorated with these decorators.

### @extension

Marks a class as an extension and attaches metadata:

```python
from revitpy.extensions.decorators import extension

@extension(
    name="My Extension",
    version="1.0.0",
    description="A sample extension",
    author="Your Name",
    dependencies=["Core Extension"],
)
class MyExtension(Extension):
    async def load(self): ...
    async def activate(self): ...
    async def deactivate(self): ...
```

### @command

Marks a method as a user-triggered command:

```python
from revitpy.extensions.decorators import command

class MyExtension(Extension):
    @command(
        name="Rename Walls",
        description="Rename all walls in the project",
        icon="rename.png",
        tooltip="Renames walls based on naming convention",
        shortcut="Ctrl+Shift+R",
        category="Editing",
        enabled=True,
        visible=True,
    )
    def rename_walls(self):
        pass

    # Access: ext.get_command("Rename Walls")
    # All:    ext.get_commands()
```

### @service

Marks a method or class as a background service:

```python
from revitpy.extensions.decorators import service

class MyExtension(Extension):
    @service(
        name="Model Watcher",
        description="Watches for model changes",
        auto_start=True,
        singleton=True,
        dependencies=["EventService"],
    )
    def model_watcher(self):
        pass

    # Access: ext.get_service("Model Watcher")
    # All:    ext.get_services()
```

### @tool

Marks a method as an interactive tool:

```python
from revitpy.extensions.decorators import tool

class MyExtension(Extension):
    @tool(
        name="Wall Placer",
        description="Place walls interactively",
        icon="wall.png",
        category="Tools",
        interactive=True,
        preview=True,
    )
    def wall_placer(self):
        pass

    # Access: ext.get_tool("Wall Placer")
    # All:    ext.get_tools()
```

### @analyzer

Marks a method as a model analyzer:

```python
from revitpy.extensions.decorators import analyzer

class MyExtension(Extension):
    @analyzer(
        name="Clash Detector",
        description="Detect clashes between elements",
        element_types=["Wall", "Floor"],
        categories=["Structural"],
        real_time=True,
        on_demand=True,
    )
    def clash_detector(self):
        pass

    # Access: ext.get_analyzer("Clash Detector")
    # All:    ext.get_analyzers()
```

### Other Decorators

- `@panel(name, title, width, height, resizable, dockable, floating)` -- Marks a method as a UI panel.
- `@startup(priority)` -- Marks a method as a startup task. Lower priority values run first.
- `@shutdown(priority)` -- Marks a method as a shutdown task.
- `@config(key, default_value, description, required, validator)` -- Marks a property as configurable.
- `@permission(name, description, required, category)` -- Declares a permission requirement.
- `@cache(ttl, max_size, key_func)` -- Caches method results with optional TTL and size limits.

## Dependency Injection

RevitPy includes a dependency injection (DI) container in `revitpy.extensions.dependency_injection`.

### DIContainer

The `DIContainer` class supports three service lifetimes:

| Lifetime | Description |
|---|---|
| `SINGLETON` | One instance for the entire application |
| `SCOPED` | One instance per scope |
| `TRANSIENT` | New instance every time |

### Registering Services

```python
from revitpy.extensions.dependency_injection import DIContainer

container = DIContainer()

# Register a singleton with an existing instance
container.register_singleton(MyService, instance=my_service_instance)

# Register a singleton by type (created on first resolve)
container.register_singleton(IMyService, implementation_type=MyService)

# Register with a factory function
container.register_singleton(IMyService, factory=lambda: MyService())

# Register scoped and transient services
container.register_scoped(IScopedService, implementation_type=ScopedService)
container.register_transient(ITransientService, implementation_type=TransientService)
```

Registration methods return the container for chaining:

```python
container.register_singleton(ServiceA, instance=a).register_transient(ServiceB)
```

### Resolving Services

```python
service = container.get_service(IMyService)
```

The container automatically resolves constructor dependencies by inspecting type annotations. Circular dependencies are detected and raise a `RuntimeError`.

### Scopes

```python
with container.scope():
    # Scoped services are created once within this block
    service = container.get_service(IScopedService)
# Scoped services are disposed when the block exits
```

Or explicitly:

```python
scope = container.create_scope()
with scope:
    service = container.get_service(IScopedService)
```

### Child Containers

Create a child container that inherits registrations from the parent:

```python
child = container.create_child_container()
child.register_singleton(ISpecialService, instance=special)
# child can resolve services from both itself and the parent
```

### DI Decorators

```python
from revitpy.extensions.dependency_injection import singleton, transient, scoped, inject

@singleton
class MyService:
    pass

@singleton(IMyService)  # Register as an interface
class MyServiceImpl:
    pass

@transient
class PerRequestService:
    pass

@scoped
class PerScopeService:
    pass

@inject
def my_function(service: IMyService):
    # service is automatically resolved from the global container
    service.do_work()
```

### Global Container

```python
from revitpy.extensions.dependency_injection import (
    set_current_container,
    get_current_container,
    get_service,
)

set_current_container(container)

# Resolve from the global container
service = get_service(IMyService)
```
