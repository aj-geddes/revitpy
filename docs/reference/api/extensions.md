---
layout: api
title: Extensions Framework API
description: Extensions Framework API reference documentation
---

# Extensions Framework API

The Extensions Framework provides a powerful plugin architecture for extending RevitPy functionality with custom extensions.

## Overview

The Extensions Framework enables:

- **Plugin architecture**: Load and manage extensions dynamically
- **Dependency injection**: IoC container for dependency management
- **Lifecycle management**: Control extension initialization and teardown
- **Extension discovery**: Automatically discover and load extensions
- **Extension metadata**: Rich metadata for extension description
- **Inter-extension communication**: Extensions can interact with each other

## Core Classes

### Extension

Base class for all extensions.

::: revitpy.extensions.Extension
    options:
      members:
        - __init__
        - initialize
        - startup
        - shutdown
        - get_metadata
        - get_status
        - get_dependencies

### ExtensionManager

Manages extension lifecycle and coordination.

::: revitpy.extensions.ExtensionManager
    options:
      members:
        - load_extension
        - unload_extension
        - get_extension
        - get_all_extensions
        - start_all
        - stop_all
        - reload_extension

### ExtensionMetadata

Metadata describing an extension.

::: revitpy.extensions.ExtensionMetadata
    options:
      members:
        - name
        - version
        - author
        - description
        - dependencies
        - tags
        - homepage

### DIContainer

Dependency injection container.

::: revitpy.extensions.dependency_injection.DIContainer
    options:
      members:
        - register
        - register_singleton
        - register_transient
        - register_scoped
        - resolve
        - resolve_all

### ExtensionLoader

Loads extensions from various sources.

::: revitpy.extensions.ExtensionLoader
    options:
      members:
        - load_from_directory
        - load_from_file
        - load_from_package
        - discover_extensions

## Basic Usage

### Creating a Simple Extension

```python
from revitpy.extensions import Extension, ExtensionMetadata

class WallAnalyzerExtension(Extension):
    """Extension for analyzing walls."""

    def get_metadata(self):
        """Return extension metadata."""
        return ExtensionMetadata(
            name="Wall Analyzer",
            version="1.0.0",
            author="Your Name",
            description="Analyzes wall properties and generates reports",
            tags=["analysis", "walls", "reporting"]
        )

    def initialize(self):
        """Initialize the extension."""
        print("Wall Analyzer initializing...")
        self.wall_count = 0

    def startup(self):
        """Start the extension."""
        print("Wall Analyzer started")

    def shutdown(self):
        """Shutdown the extension."""
        print(f"Wall Analyzer shutting down. Analyzed {self.wall_count} walls")

    def analyze_walls(self, context):
        """Main extension functionality."""
        walls = context.elements.of_category('Walls').to_list()
        self.wall_count = len(walls)

        analysis = {
            'total_walls': len(walls),
            'avg_height': sum(w.Height for w in walls) / len(walls),
            'total_area': sum(w.Area for w in walls)
        }

        return analysis
```

### Loading and Using Extensions

```python
from revitpy.extensions import ExtensionManager

# Create extension manager
ext_mgr = ExtensionManager()

# Load extension
extension = WallAnalyzerExtension()
ext_mgr.load_extension(extension)

# Start extension
ext_mgr.start_all()

# Use extension
with RevitContext() as context:
    analysis = extension.analyze_walls(context)
    print(f"Analysis: {analysis}")

# Shutdown when done
ext_mgr.stop_all()
```

### Extension with Dependency Injection

```python
from revitpy.extensions import Extension, inject, Injectable

# Define services
class DatabaseService(Injectable):
    """Service for database operations."""

    def save_analysis(self, data):
        """Save analysis to database."""
        print(f"Saving analysis: {data}")

class ReportGenerator(Injectable):
    """Service for generating reports."""

    def generate_report(self, analysis):
        """Generate report from analysis."""
        report = f"Wall Analysis Report\n"
        report += f"Total Walls: {analysis['total_walls']}\n"
        report += f"Average Height: {analysis['avg_height']:.2f} ft\n"
        return report

# Extension with injected dependencies
class AdvancedWallAnalyzer(Extension):
    """Advanced wall analyzer with DI."""

    @inject
    def __init__(self, db_service: DatabaseService, report_gen: ReportGenerator):
        """Initialize with injected dependencies."""
        self.db_service = db_service
        self.report_gen = report_gen

    def analyze_and_report(self, context):
        """Analyze walls and generate report."""
        walls = context.elements.of_category('Walls').to_list()

        analysis = {
            'total_walls': len(walls),
            'avg_height': sum(w.Height for w in walls) / len(walls)
        }

        # Use injected services
        self.db_service.save_analysis(analysis)
        report = self.report_gen.generate_report(analysis)

        return report

# Register services and load extension
ext_mgr = ExtensionManager()
ext_mgr.container.register_singleton(DatabaseService)
ext_mgr.container.register_singleton(ReportGenerator)

extension = ext_mgr.load_extension(AdvancedWallAnalyzer)
```

## Extension Decorators

### @extension Decorator

```python
from revitpy.extensions import extension

@extension(
    name="Room Optimizer",
    version="2.0.0",
    author="Your Name",
    description="Optimizes room layouts",
    dependencies=["wall_analyzer"]
)
class RoomOptimizerExtension(Extension):
    """Extension with metadata from decorator."""

    def startup(self):
        print("Room Optimizer started")

    def optimize_rooms(self, context):
        """Optimize room layouts."""
        rooms = context.elements.of_category('Rooms').to_list()
        # Optimization logic...
        return optimized_rooms
```

### @command Decorator

```python
from revitpy.extensions import Extension, command

class UtilityExtension(Extension):
    """Extension with commands."""

    @command(name="analyze-walls", description="Analyze all walls")
    def analyze_walls_command(self, args):
        """Command to analyze walls."""
        with RevitContext() as context:
            walls = context.elements.of_category('Walls').to_list()
            print(f"Found {len(walls)} walls")

    @command(name="export-data", description="Export data to file")
    def export_command(self, args):
        """Command to export data."""
        output_file = args.get('output', 'export.json')
        # Export logic...
        print(f"Data exported to {output_file}")

# Use commands
extension = UtilityExtension()
extension.analyze_walls_command({})
extension.export_command({'output': 'report.json'})
```

### @service Decorator

```python
from revitpy.extensions import service

@service(singleton=True)
class ConfigurationService:
    """Singleton service for configuration."""

    def __init__(self):
        self.config = {}

    def get(self, key, default=None):
        """Get configuration value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set configuration value."""
        self.config[key] = value

# Service is automatically registered and available for injection
```

## Dependency Injection

### Registering Services

```python
from revitpy.extensions import DIContainer

container = DIContainer()

# Singleton (one instance for entire application)
container.register_singleton(ConfigurationService)

# Transient (new instance each time)
container.register_transient(AnalysisService)

# Scoped (one instance per scope)
container.register_scoped(DatabaseConnection)

# Register with factory
container.register(
    ReportGenerator,
    factory=lambda: ReportGenerator(template_path='/templates')
)

# Register interface to implementation
container.register(IDataStore, SQLiteDataStore)
```

### Resolving Dependencies

```python
# Resolve single instance
config_service = container.resolve(ConfigurationService)

# Resolve with parameters
db_connection = container.resolve(
    DatabaseConnection,
    connection_string='...'
)

# Resolve all implementations of interface
data_stores = container.resolve_all(IDataStore)
```

### Constructor Injection

```python
from revitpy.extensions import inject

class WallAnalyzer:
    """Service with constructor injection."""

    @inject
    def __init__(self, config: ConfigurationService, db: DatabaseService):
        """Dependencies injected automatically."""
        self.config = config
        self.db = db

    def analyze(self, wall):
        """Analyze wall using injected services."""
        max_height = self.config.get('max_wall_height', 20.0)

        analysis = {
            'height': wall.Height,
            'exceeds_max': wall.Height > max_height
        }

        self.db.save_analysis(analysis)
        return analysis
```

### Property Injection

```python
from revitpy.extensions import inject_property

class ReportGenerator:
    """Service with property injection."""

    @inject_property
    def config(self) -> ConfigurationService:
        """Configuration service injected as property."""
        pass

    def generate_report(self, data):
        """Generate report using injected config."""
        template = self.config.get('report_template', 'default')
        # Generate report...
        return report
```

## Extension Discovery

### Auto-Discovery

```python
from revitpy.extensions import ExtensionManager, ExtensionLoader

# Create manager
ext_mgr = ExtensionManager()

# Discover extensions in directory
loader = ExtensionLoader()
extensions = loader.discover_extensions('./extensions')

# Load all discovered extensions
for extension_class in extensions:
    ext_mgr.load_extension(extension_class)

# Start all extensions
ext_mgr.start_all()
```

### Plugin Directory Structure

```
extensions/
├── wall_analyzer/
│   ├── __init__.py
│   ├── extension.py
│   └── manifest.json
├── room_optimizer/
│   ├── __init__.py
│   ├── extension.py
│   └── manifest.json
└── report_generator/
    ├── __init__.py
    ├── extension.py
    └── manifest.json
```

### Extension Manifest

```json
{
  "name": "Wall Analyzer",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Analyzes wall properties",
  "entry_point": "extension.WallAnalyzerExtension",
  "dependencies": [],
  "requires_revit": "2023",
  "tags": ["analysis", "walls"]
}
```

## Extension Lifecycle

### Lifecycle Stages

```python
from revitpy.extensions import Extension, LifecycleStage

class LifecycleAwareExtension(Extension):
    """Extension with lifecycle awareness."""

    def on_lifecycle_stage(self, stage):
        """React to lifecycle stage changes."""
        if stage == LifecycleStage.INITIALIZING:
            print("Extension initializing")
            self.load_configuration()

        elif stage == LifecycleStage.STARTING:
            print("Extension starting")
            self.connect_to_services()

        elif stage == LifecycleStage.RUNNING:
            print("Extension running")
            self.start_background_tasks()

        elif stage == LifecycleStage.STOPPING:
            print("Extension stopping")
            self.stop_background_tasks()

        elif stage == LifecycleStage.STOPPED:
            print("Extension stopped")
            self.cleanup_resources()
```

### Graceful Shutdown

```python
class ResilientExtension(Extension):
    """Extension with graceful shutdown."""

    def __init__(self):
        self.is_running = False
        self.tasks = []

    def startup(self):
        """Start extension."""
        self.is_running = True
        self.start_tasks()

    def shutdown(self):
        """Gracefully shutdown extension."""
        print("Shutting down extension...")
        self.is_running = False

        # Cancel all running tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        for task in self.tasks:
            task.wait(timeout=5.0)

        # Clean up resources
        self.cleanup()

        print("Extension shutdown complete")
```

## Inter-Extension Communication

### Extension Events

```python
from revitpy.extensions import Extension, ExtensionEvent

class ProducerExtension(Extension):
    """Extension that produces events."""

    def do_work(self):
        """Perform work and emit event."""
        result = perform_analysis()

        # Emit event
        event = ExtensionEvent(
            name="analysis_complete",
            source=self,
            data=result
        )
        self.emit_event(event)

class ConsumerExtension(Extension):
    """Extension that consumes events."""

    def initialize(self):
        """Subscribe to events."""
        ext_mgr = self.get_extension_manager()

        # Subscribe to events from ProducerExtension
        producer = ext_mgr.get_extension('ProducerExtension')
        producer.subscribe('analysis_complete', self.on_analysis_complete)

    def on_analysis_complete(self, event):
        """Handle analysis complete event."""
        result = event.data
        print(f"Received analysis result: {result}")
```

### Extension Registry

```python
from revitpy.extensions import ExtensionRegistry

class CollaborativeExtension(Extension):
    """Extension that uses other extensions."""

    def initialize(self):
        """Get references to other extensions."""
        registry = ExtensionRegistry.get_instance()

        # Get other extensions
        self.wall_analyzer = registry.get('WallAnalyzer')
        self.report_gen = registry.get('ReportGenerator')

    def generate_wall_report(self, context):
        """Use multiple extensions together."""
        # Use wall analyzer extension
        analysis = self.wall_analyzer.analyze_walls(context)

        # Use report generator extension
        report = self.report_gen.generate_report(analysis)

        return report
```

## Advanced Features

### Hot Reload

```python
from revitpy.extensions import ExtensionManager

ext_mgr = ExtensionManager()

# Enable hot reload
ext_mgr.enable_hot_reload(watch_directory='./extensions')

# Extension files are watched and reloaded on change
# Changes to extension code are applied without restart
```

### Extension Configuration

```python
class ConfigurableExtension(Extension):
    """Extension with configuration."""

    def initialize(self):
        """Load configuration."""
        config = self.get_configuration()

        self.max_elements = config.get('max_elements', 1000)
        self.output_dir = config.get('output_directory', './output')
        self.enable_logging = config.get('enable_logging', True)

    def save_configuration(self):
        """Save current configuration."""
        config = {
            'max_elements': self.max_elements,
            'output_directory': self.output_dir,
            'enable_logging': self.enable_logging
        }
        self.set_configuration(config)
```

### Extension Versioning

```python
from revitpy.extensions import version_required

class VersionAwareExtension(Extension):
    """Extension with version requirements."""

    @version_required('1.5.0')
    def new_feature(self):
        """Feature available in v1.5.0+."""
        print("This feature requires v1.5.0 or higher")

    def get_metadata(self):
        return ExtensionMetadata(
            name="Version Aware",
            version="2.0.0",
            min_revit_version="2023",
            min_revitpy_version="1.5.0"
        )
```

## Testing Extensions

### Unit Testing Extensions

```python
import pytest
from revitpy.testing import MockExtensionManager, MockDIContainer

def test_extension_initialization():
    """Test extension initialization."""
    extension = WallAnalyzerExtension()
    extension.initialize()

    assert extension.wall_count == 0

def test_extension_with_di():
    """Test extension with dependency injection."""
    # Create mock container
    container = MockDIContainer()
    container.register_singleton(MockDatabaseService)

    # Create extension
    extension = AdvancedWallAnalyzer(
        db_service=container.resolve(MockDatabaseService),
        report_gen=MockReportGenerator()
    )

    # Test functionality
    result = extension.analyze_and_report(mock_context)
    assert result is not None
```

### Integration Testing

```python
def test_extension_loading():
    """Test extension loading and lifecycle."""
    ext_mgr = ExtensionManager()

    # Load extension
    extension = WallAnalyzerExtension()
    ext_mgr.load_extension(extension)

    # Verify loaded
    assert ext_mgr.get_extension('Wall Analyzer') is not None

    # Start extension
    ext_mgr.start_all()
    assert extension.get_status() == 'running'

    # Stop extension
    ext_mgr.stop_all()
    assert extension.get_status() == 'stopped'
```

## Best Practices

1. **Single Responsibility**: Each extension should have one clear purpose
2. **Dependency Injection**: Use DI for better testability and maintainability
3. **Graceful Degradation**: Handle missing dependencies gracefully
4. **Configuration**: Make extensions configurable through external config
5. **Documentation**: Provide clear documentation for your extensions
6. **Versioning**: Use semantic versioning for extensions
7. **Testing**: Write comprehensive tests for extension functionality

## Next Steps

- **[Dependency Injection](dependency-injection.md)**: Deep dive into DI container
- **[Event System](events.md)**: Use events with extensions
- **[Extension Development Guide](../../guides/extension-development.md)**: Build your first extension
- **[Extension Examples](../../examples/extensions/)**: Example extensions
