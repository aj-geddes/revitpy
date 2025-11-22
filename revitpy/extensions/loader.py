"""
Extension loader for discovering and loading RevitPy extensions.
"""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .dependency_injection import DIContainer
from .extension import Extension, ExtensionMetadata


class ExtensionLoader:
    """Loads and manages RevitPy extensions from various sources."""

    def __init__(self, registry: Any) -> None:
        self.registry = registry
        self._loaded_modules: dict[str, Any] = {}

    async def discover_extensions(self, directory: Path) -> list[ExtensionMetadata]:
        """
        Discover extensions in a directory.

        Args:
            directory: Directory to scan

        Returns:
            List of discovered extension metadata
        """
        extensions = []

        if not directory.exists() or not directory.is_dir():
            return extensions

        # Look for extension.yaml files
        for extension_dir in directory.iterdir():
            if extension_dir.is_dir():
                metadata_file = extension_dir / "extension.yaml"
                if metadata_file.exists():
                    try:
                        metadata = await self._load_metadata_from_file(
                            metadata_file, extension_dir
                        )
                        extensions.append(metadata)
                    except Exception as e:
                        logger.error(
                            f"Failed to load metadata from {metadata_file}: {e}"
                        )

        # Look for Python files with extension decorators
        for py_file in directory.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                metadata_list = await self._discover_extension_classes(py_file)
                extensions.extend(metadata_list)
            except Exception as e:
                logger.debug(f"No extensions found in {py_file}: {e}")

        return extensions

    async def _load_metadata_from_file(
        self, metadata_file: Path, extension_dir: Path
    ) -> ExtensionMetadata:
        """Load extension metadata from YAML file."""
        try:
            with open(metadata_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            metadata = ExtensionMetadata(
                name=data["name"],
                version=data["version"],
                description=data.get("description", ""),
                author=data.get("author", ""),
                website=data.get("website", ""),
                license=data.get("license", ""),
                dependencies=data.get("dependencies", []),
                revit_versions=data.get("revit_versions", []),
                python_version=data.get("python_version", ">=3.11"),
                config_schema=data.get("config_schema"),
                default_config=data.get("default_config"),
            )

            # Store extension directory
            metadata._extension_directory = extension_dir

            return metadata

        except Exception as e:
            raise ValueError(f"Invalid extension metadata in {metadata_file}: {e}")

    async def _discover_extension_classes(
        self, py_file: Path
    ) -> list[ExtensionMetadata]:
        """Discover extension classes in Python file."""
        extensions = []

        try:
            # Import the module
            spec = importlib.util.spec_from_file_location("temp_module", py_file)
            if not spec or not spec.loader:
                return extensions

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for extension classes
            for name in dir(module):
                obj = getattr(module, name)

                if (
                    inspect.isclass(obj)
                    and hasattr(obj, "_is_extension")
                    and hasattr(obj, "_extension_metadata")
                ):
                    metadata = obj._extension_metadata
                    metadata._extension_class = obj
                    metadata._extension_file = py_file
                    extensions.append(metadata)

        except Exception as e:
            logger.debug(f"Failed to scan {py_file} for extensions: {e}")

        return extensions

    async def load_extension(
        self, metadata: ExtensionMetadata, container: DIContainer
    ) -> Extension | None:
        """
        Load an extension from metadata.

        Args:
            metadata: Extension metadata
            container: DI container

        Returns:
            Loaded extension instance or None
        """
        try:
            # Create child container
            extension_container = container.create_child_container()

            # Load extension class
            extension_class = await self._load_extension_class(metadata)
            if not extension_class:
                return None

            # Create extension instance
            extension = extension_class(metadata, extension_container)

            # Set extension directory if available
            if hasattr(metadata, "_extension_directory"):
                extension._extension_directory = metadata._extension_directory

            # Load the extension
            success = await extension.load_extension()
            if not success:
                return None

            return extension

        except Exception as e:
            logger.error(f"Failed to load extension {metadata.name}: {e}")
            return None

    async def _load_extension_class(
        self, metadata: ExtensionMetadata
    ) -> type[Extension] | None:
        """Load the extension class from metadata."""
        # If class is already available
        if hasattr(metadata, "_extension_class"):
            return metadata._extension_class

        # Load from file
        if hasattr(metadata, "_extension_file"):
            return await self._load_class_from_file(
                metadata._extension_file, metadata.name
            )

        # Load from directory
        if hasattr(metadata, "_extension_directory"):
            return await self._load_class_from_directory(
                metadata._extension_directory, metadata.name
            )

        logger.error(f"No source found for extension {metadata.name}")
        return None

    async def _load_class_from_file(
        self, py_file: Path, extension_name: str
    ) -> type[Extension] | None:
        """Load extension class from Python file."""
        try:
            module_name = f"revitpy_ext_{extension_name.lower()}"

            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Store module reference
            self._loaded_modules[module_name] = module

            # Find extension class
            for name in dir(module):
                obj = getattr(module, name)

                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Extension)
                    and hasattr(obj, "_is_extension")
                ):
                    return obj

            logger.error(f"No extension class found in {py_file}")
            return None

        except Exception as e:
            logger.error(f"Failed to load extension class from {py_file}: {e}")
            return None

    async def _load_class_from_directory(
        self, extension_dir: Path, extension_name: str
    ) -> type[Extension] | None:
        """Load extension class from directory."""
        # Look for main.py or __init__.py
        main_files = [
            extension_dir / "main.py",
            extension_dir / "__init__.py",
            extension_dir / f"{extension_name.lower()}.py",
        ]

        for main_file in main_files:
            if main_file.exists():
                return await self._load_class_from_file(main_file, extension_name)

        logger.error(f"No main extension file found in {extension_dir}")
        return None

    def unload_extension_module(self, extension_name: str) -> None:
        """Unload extension module from memory."""
        module_name = f"revitpy_ext_{extension_name.lower()}"

        if module_name in self._loaded_modules:
            del self._loaded_modules[module_name]

        if module_name in sys.modules:
            del sys.modules[module_name]

        logger.debug(f"Unloaded extension module: {module_name}")

    def get_loaded_modules(self) -> dict[str, Any]:
        """Get all loaded extension modules."""
        return self._loaded_modules.copy()
