"""
Extension registry for managing extension metadata.
"""

import json
from pathlib import Path

from loguru import logger

from .extension import ExtensionMetadata


class ExtensionRegistry:
    """Registry for managing extension metadata and relationships."""

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionMetadata] = {}
        self._extensions_by_name: dict[str, ExtensionMetadata] = {}

    def register_extension(self, metadata: ExtensionMetadata) -> None:
        """
        Register extension metadata.

        Args:
            metadata: Extension metadata to register
        """
        self._extensions[metadata.extension_id] = metadata
        self._extensions_by_name[metadata.name] = metadata

        logger.debug(f"Registered extension: {metadata.name} v{metadata.version}")

    def unregister_extension(self, name_or_id: str) -> bool:
        """
        Unregister extension metadata.

        Args:
            name_or_id: Extension name or ID

        Returns:
            True if unregistered
        """
        metadata = self.get_extension(name_or_id)
        if not metadata:
            return False

        if metadata.extension_id in self._extensions:
            del self._extensions[metadata.extension_id]

        if metadata.name in self._extensions_by_name:
            del self._extensions_by_name[metadata.name]

        logger.debug(f"Unregistered extension: {metadata.name}")
        return True

    def get_extension(self, name_or_id: str) -> ExtensionMetadata | None:
        """
        Get extension metadata by name or ID.

        Args:
            name_or_id: Extension name or ID

        Returns:
            Extension metadata or None
        """
        # Try by ID first
        if name_or_id in self._extensions:
            return self._extensions[name_or_id]

        # Try by name
        if name_or_id in self._extensions_by_name:
            return self._extensions_by_name[name_or_id]

        return None

    def get_all_extensions(self) -> list[ExtensionMetadata]:
        """Get all registered extensions."""
        return list(self._extensions.values())

    def get_extensions_by_author(self, author: str) -> list[ExtensionMetadata]:
        """Get extensions by author."""
        return [ext for ext in self._extensions.values() if ext.author == author]

    def has_extension(self, name_or_id: str) -> bool:
        """Check if extension is registered."""
        return self.get_extension(name_or_id) is not None

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Get dependency graph of all extensions."""
        graph = {}

        for metadata in self._extensions.values():
            graph[metadata.name] = metadata.dependencies.copy()

        return graph

    def resolve_load_order(self) -> list[str]:
        """
        Resolve the order in which extensions should be loaded.

        Returns:
            List of extension names in load order

        Raises:
            ValueError: If circular dependencies are detected
        """
        graph = self.get_dependency_graph()
        resolved = []
        unresolved = set(graph.keys())

        def visit(name: str, visiting: set[str]) -> None:
            if name in visiting:
                cycle = " -> ".join(visiting) + f" -> {name}"
                raise ValueError(f"Circular dependency detected: {cycle}")

            if name in resolved:
                return

            if name not in graph:
                # External dependency, skip
                return

            visiting.add(name)

            for dependency in graph[name]:
                visit(dependency, visiting)

            visiting.remove(name)
            resolved.append(name)
            unresolved.discard(name)

        while unresolved:
            visit(next(iter(unresolved)), set())

        return resolved

    def validate_dependencies(self) -> dict[str, list[str]]:
        """
        Validate all extension dependencies.

        Returns:
            Dictionary mapping extension names to missing dependencies
        """
        missing_deps = {}

        for metadata in self._extensions.values():
            missing = []

            for dependency in metadata.dependencies:
                if not self.has_extension(dependency):
                    missing.append(dependency)

            if missing:
                missing_deps[metadata.name] = missing

        return missing_deps

    def get_dependents(self, extension_name: str) -> list[str]:
        """
        Get extensions that depend on the given extension.

        Args:
            extension_name: Extension name

        Returns:
            List of dependent extension names
        """
        dependents = []

        for metadata in self._extensions.values():
            if extension_name in metadata.dependencies:
                dependents.append(metadata.name)

        return dependents

    def export_registry(self, file_path: Path) -> None:
        """
        Export registry to JSON file.

        Args:
            file_path: Path to export file
        """
        try:
            registry_data = {
                "extensions": [
                    metadata.to_dict() for metadata in self._extensions.values()
                ]
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(registry_data, f, indent=2, default=str)

            logger.info(f"Exported extension registry to {file_path}")

        except Exception as e:
            logger.error(f"Failed to export registry to {file_path}: {e}")
            raise

    def import_registry(self, file_path: Path) -> None:
        """
        Import registry from JSON file.

        Args:
            file_path: Path to import file
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                registry_data = json.load(f)

            for ext_data in registry_data.get("extensions", []):
                metadata = ExtensionMetadata(**ext_data)
                self.register_extension(metadata)

            logger.info(f"Imported extension registry from {file_path}")

        except Exception as e:
            logger.error(f"Failed to import registry from {file_path}: {e}")
            raise

    def clear(self) -> None:
        """Clear all registered extensions."""
        self._extensions.clear()
        self._extensions_by_name.clear()
        logger.debug("Cleared extension registry")

    def get_statistics(self) -> dict[str, int]:
        """Get registry statistics."""
        return {
            "total_extensions": len(self._extensions),
            "unique_authors": len(
                {ext.author for ext in self._extensions.values() if ext.author}
            ),
            "with_dependencies": len(
                [ext for ext in self._extensions.values() if ext.dependencies]
            ),
            "total_dependencies": sum(
                len(ext.dependencies) for ext in self._extensions.values()
            ),
        }
