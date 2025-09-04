"""Plugin management system for RevitPy CLI."""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Protocol

from rich.console import Console
from rich.table import Table

from ..core.config import get_config
from ..core.exceptions import PluginError
from ..core.logging import get_logger

logger = get_logger(__name__)
console = Console()


class PluginInterface(Protocol):
    """Protocol defining the plugin interface."""
    
    name: str
    version: str
    description: str
    
    def initialize(self) -> None:
        """Initialize the plugin."""
        ...
    
    def cleanup(self) -> None:
        """Cleanup plugin resources."""
        ...


class PluginInfo:
    """Information about a plugin."""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        module_path: Optional[Path] = None,
        plugin_class: Optional[Type[PluginInterface]] = None,
        enabled: bool = True,
    ) -> None:
        """Initialize plugin info.
        
        Args:
            name: Plugin name
            version: Plugin version
            description: Plugin description
            module_path: Path to plugin module
            plugin_class: Plugin class
            enabled: Whether plugin is enabled
        """
        self.name = name
        self.version = version
        self.description = description
        self.module_path = module_path
        self.plugin_class = plugin_class
        self.enabled = enabled
        self.instance: Optional[PluginInterface] = None


class PluginManager:
    """Manages RevitPy CLI plugins."""
    
    def __init__(self) -> None:
        """Initialize plugin manager."""
        self.config = get_config()
        self.plugins: Dict[str, PluginInfo] = {}
        self._loaded_modules: Dict[str, Any] = {}
    
    def discover_plugins(self) -> None:
        """Discover available plugins."""
        if not self.config.plugins.enabled:
            logger.debug("Plugin system disabled")
            return
        
        # Discover built-in plugins
        self._discover_builtin_plugins()
        
        # Discover user plugins
        for plugin_dir in self.config.plugins.plugin_dirs:
            self._discover_plugins_in_directory(Path(plugin_dir))
        
        # Auto-load plugins if enabled
        if self.config.plugins.auto_load:
            self.load_all_plugins()
    
    def _discover_builtin_plugins(self) -> None:
        """Discover built-in plugins."""
        builtin_plugin_dir = Path(__file__).parent / "builtin"
        if builtin_plugin_dir.exists():
            self._discover_plugins_in_directory(builtin_plugin_dir)
    
    def _discover_plugins_in_directory(self, plugin_dir: Path) -> None:
        """Discover plugins in a directory.
        
        Args:
            plugin_dir: Directory to search for plugins
        """
        if not plugin_dir.exists() or not plugin_dir.is_dir():
            return
        
        logger.debug(f"Discovering plugins in {plugin_dir}")
        
        # Look for Python files
        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            try:
                self._load_plugin_module(plugin_file)
            except Exception as e:
                logger.warning(f"Failed to load plugin from {plugin_file}: {e}")
        
        # Look for plugin packages
        for plugin_package in plugin_dir.iterdir():
            if not plugin_package.is_dir() or plugin_package.name.startswith("_"):
                continue
            
            plugin_init = plugin_package / "__init__.py"
            if plugin_init.exists():
                try:
                    self._load_plugin_package(plugin_package)
                except Exception as e:
                    logger.warning(f"Failed to load plugin package {plugin_package}: {e}")
    
    def _load_plugin_module(self, plugin_file: Path) -> None:
        """Load plugin from a Python file.
        
        Args:
            plugin_file: Path to plugin file
        """
        module_name = f"revitpy_cli_plugin_{plugin_file.stem}"
        
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            self._loaded_modules[module_name] = module
            
            # Find plugin classes
            self._extract_plugin_classes(module, plugin_file)
            
        except Exception as e:
            raise PluginError(f"Failed to execute plugin module {plugin_file}: {e}") from e
    
    def _load_plugin_package(self, package_dir: Path) -> None:
        """Load plugin from a package directory.
        
        Args:
            package_dir: Path to plugin package
        """
        package_name = f"revitpy_cli_plugin_{package_dir.name}"
        
        # Add package directory to sys.path temporarily
        sys.path.insert(0, str(package_dir.parent))
        
        try:
            module = importlib.import_module(package_dir.name)
            self._loaded_modules[package_name] = module
            
            # Find plugin classes
            self._extract_plugin_classes(module, package_dir)
            
        except Exception as e:
            raise PluginError(f"Failed to import plugin package {package_dir}: {e}") from e
        
        finally:
            # Remove from sys.path
            if str(package_dir.parent) in sys.path:
                sys.path.remove(str(package_dir.parent))
    
    def _extract_plugin_classes(self, module: Any, module_path: Path) -> None:
        """Extract plugin classes from a module.
        
        Args:
            module: Plugin module
            module_path: Path to module
        """
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                obj is not PluginInterface and
                self._implements_plugin_interface(obj)):
                
                try:
                    # Get plugin metadata
                    plugin_name = getattr(obj, 'name', name)
                    plugin_version = getattr(obj, 'version', '1.0.0')
                    plugin_description = getattr(obj, 'description', 'No description')
                    
                    # Check if plugin is disabled
                    if plugin_name in self.config.plugins.disabled_plugins:
                        logger.debug(f"Plugin {plugin_name} is disabled")
                        continue
                    
                    # Create plugin info
                    plugin_info = PluginInfo(
                        name=plugin_name,
                        version=plugin_version,
                        description=plugin_description,
                        module_path=module_path,
                        plugin_class=obj,
                        enabled=True,
                    )
                    
                    self.plugins[plugin_name] = plugin_info
                    logger.debug(f"Discovered plugin: {plugin_name} v{plugin_version}")
                
                except Exception as e:
                    logger.warning(f"Failed to register plugin class {name}: {e}")
    
    def _implements_plugin_interface(self, cls: Type) -> bool:
        """Check if a class implements the plugin interface.
        
        Args:
            cls: Class to check
            
        Returns:
            True if class implements plugin interface
        """
        required_attributes = ['name', 'version', 'description']
        required_methods = ['initialize', 'cleanup']
        
        # Check required attributes
        for attr in required_attributes:
            if not hasattr(cls, attr):
                return False
        
        # Check required methods
        for method in required_methods:
            if not hasattr(cls, method) or not callable(getattr(cls, method)):
                return False
        
        return True
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin.
        
        Args:
            plugin_name: Name of plugin to load
            
        Returns:
            True if plugin loaded successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        if plugin_info.instance is not None:
            logger.debug(f"Plugin {plugin_name} already loaded")
            return True
        
        if not plugin_info.enabled:
            logger.debug(f"Plugin {plugin_name} is disabled")
            return False
        
        try:
            # Instantiate plugin
            plugin_info.instance = plugin_info.plugin_class()
            
            # Initialize plugin
            plugin_info.instance.initialize()
            
            logger.info(f"Loaded plugin: {plugin_name} v{plugin_info.version}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            plugin_info.instance = None
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin.
        
        Args:
            plugin_name: Name of plugin to unload
            
        Returns:
            True if plugin unloaded successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        
        if plugin_info.instance is None:
            logger.debug(f"Plugin {plugin_name} not loaded")
            return True
        
        try:
            # Cleanup plugin
            plugin_info.instance.cleanup()
            plugin_info.instance = None
            
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def load_all_plugins(self) -> None:
        """Load all discovered plugins."""
        for plugin_name in self.plugins:
            self.load_plugin(plugin_name)
    
    def unload_all_plugins(self) -> None:
        """Unload all loaded plugins."""
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin.
        
        Args:
            plugin_name: Name of plugin to enable
            
        Returns:
            True if plugin enabled successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        plugin_info = self.plugins[plugin_name]
        plugin_info.enabled = True
        
        # Remove from disabled list if present
        if plugin_name in self.config.plugins.disabled_plugins:
            self.config.plugins.disabled_plugins.remove(plugin_name)
        
        logger.info(f"Enabled plugin: {plugin_name}")
        return True
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin.
        
        Args:
            plugin_name: Name of plugin to disable
            
        Returns:
            True if plugin disabled successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        # Unload plugin first
        self.unload_plugin(plugin_name)
        
        plugin_info = self.plugins[plugin_name]
        plugin_info.enabled = False
        
        # Add to disabled list
        if plugin_name not in self.config.plugins.disabled_plugins:
            self.config.plugins.disabled_plugins.append(plugin_name)
        
        logger.info(f"Disabled plugin: {plugin_name}")
        return True
    
    def install_plugin(self, plugin_source: str) -> bool:
        """Install a plugin from source.
        
        Args:
            plugin_source: Plugin source (URL, path, or package name)
            
        Returns:
            True if plugin installed successfully
        """
        # This would implement plugin installation
        # For now, just show a placeholder message
        console.print(f"[yellow]Plugin installation not implemented yet: {plugin_source}[/yellow]")
        return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """Uninstall a plugin.
        
        Args:
            plugin_name: Name of plugin to uninstall
            
        Returns:
            True if plugin uninstalled successfully
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        # Unload plugin first
        self.unload_plugin(plugin_name)
        
        # Remove plugin info
        del self.plugins[plugin_name]
        
        # This would also remove plugin files
        # For now, just show a message
        console.print(f"[yellow]Plugin file removal not implemented yet: {plugin_name}[/yellow]")
        
        logger.info(f"Uninstalled plugin: {plugin_name}")
        return True
    
    def list_plugins(self) -> None:
        """List all discovered plugins."""
        if not self.plugins:
            console.print("[yellow]No plugins found[/yellow]")
            return
        
        table = Table(title="RevitPy CLI Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Description", style="white")
        
        for plugin_name, plugin_info in self.plugins.items():
            # Determine status
            if not plugin_info.enabled:
                status = "🔴 Disabled"
            elif plugin_info.instance is not None:
                status = "🟢 Loaded"
            else:
                status = "🟡 Available"
            
            table.add_row(
                plugin_name,
                plugin_info.version,
                status,
                plugin_info.description,
            )
        
        console.print(table)
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get information about a specific plugin.
        
        Args:
            plugin_name: Name of plugin
            
        Returns:
            Plugin information or None if not found
        """
        return self.plugins.get(plugin_name)
    
    def get_loaded_plugins(self) -> List[str]:
        """Get list of loaded plugin names.
        
        Returns:
            List of loaded plugin names
        """
        return [
            name for name, info in self.plugins.items()
            if info.instance is not None
        ]
    
    def cleanup(self) -> None:
        """Cleanup plugin manager."""
        logger.debug("Cleaning up plugin manager")
        self.unload_all_plugins()
        self.plugins.clear()
        self._loaded_modules.clear()


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance.
    
    Returns:
        Plugin manager instance
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def initialize_plugins() -> None:
    """Initialize the plugin system."""
    manager = get_plugin_manager()
    manager.discover_plugins()


def cleanup_plugins() -> None:
    """Cleanup the plugin system."""
    manager = get_plugin_manager()
    manager.cleanup()