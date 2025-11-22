"""Dependency resolution engine with Revit version compatibility."""

import re
from dataclasses import dataclass, field
from enum import Enum

from packaging.specifiers import SpecifierSet
from packaging.version import Version


class ConflictType(Enum):
    """Types of dependency conflicts."""

    VERSION_CONFLICT = "version_conflict"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    MISSING_DEPENDENCY = "missing_dependency"
    REVIT_INCOMPATIBLE = "revit_incompatible"
    PYTHON_INCOMPATIBLE = "python_incompatible"


@dataclass
class PackageSpec:
    """Specification for a package version."""

    name: str
    version: str
    python_version: str = ">=3.11"
    supported_revit_versions: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)  # name -> version_spec
    optional_dependencies: dict[str, dict[str, str]] = field(
        default_factory=dict
    )  # extra -> {name: version_spec}
    is_prerelease: bool = False

    def __post_init__(self):
        """Normalize package name after initialization."""
        self.name = self.normalize_name(self.name)

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize package name according to PEP 508."""
        return re.sub(r"[-_.]+", "-", name).lower()

    def is_compatible_with_revit(self, revit_version: str) -> bool:
        """Check if this package version is compatible with a Revit version."""
        if not self.supported_revit_versions:
            return True  # No restrictions means compatible with all versions

        return revit_version in self.supported_revit_versions

    def is_compatible_with_python(self, python_version: str) -> bool:
        """Check if this package version is compatible with a Python version."""
        try:
            spec = SpecifierSet(self.python_version)
            return Version(python_version) in spec
        except Exception:
            return False


@dataclass
class DependencyConflict:
    """Represents a dependency resolution conflict."""

    type: ConflictType
    package_name: str
    conflicting_specs: list[str]
    message: str
    affected_packages: list[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Result of dependency resolution."""

    resolved_packages: dict[str, PackageSpec]
    conflicts: list[DependencyConflict]
    installation_order: list[str]

    @property
    def is_successful(self) -> bool:
        """Check if resolution was successful."""
        return len(self.conflicts) == 0

    def get_critical_conflicts(self) -> list[DependencyConflict]:
        """Get only critical conflicts that prevent installation."""
        critical_types = {
            ConflictType.VERSION_CONFLICT,
            ConflictType.CIRCULAR_DEPENDENCY,
            ConflictType.MISSING_DEPENDENCY,
        }
        return [c for c in self.conflicts if c.type in critical_types]


class DependencyResolver:
    """Advanced dependency resolver with Revit version compatibility."""

    def __init__(
        self,
        python_version: str = "3.11.0",
        revit_version: str = "2025",
        allow_prereleases: bool = False,
        prefer_installed: bool = True,
    ):
        self.python_version = python_version
        self.revit_version = revit_version
        self.allow_prereleases = allow_prereleases
        self.prefer_installed = prefer_installed

        # Available packages registry: name -> {version -> PackageSpec}
        self.available_packages: dict[str, dict[str, PackageSpec]] = {}

        # Currently installed packages: name -> PackageSpec
        self.installed_packages: dict[str, PackageSpec] = {}

    def register_available_package(self, package_spec: PackageSpec):
        """Register an available package version."""
        name = package_spec.name
        version = package_spec.version

        if name not in self.available_packages:
            self.available_packages[name] = {}

        self.available_packages[name][version] = package_spec

    def register_installed_package(self, package_spec: PackageSpec):
        """Register an installed package."""
        self.installed_packages[package_spec.name] = package_spec

    def get_compatible_versions(
        self, package_name: str, version_spec: str, exclude_prereleases: bool = None
    ) -> list[PackageSpec]:
        """Get all compatible versions of a package."""
        if exclude_prereleases is None:
            exclude_prereleases = not self.allow_prereleases

        normalized_name = PackageSpec.normalize_name(package_name)

        if normalized_name not in self.available_packages:
            return []

        compatible_versions = []
        spec = (
            SpecifierSet(version_spec)
            if version_spec != "*"
            else SpecifierSet(">=0.0.0")
        )

        for version_str, package_spec in self.available_packages[
            normalized_name
        ].items():
            try:
                version_obj = Version(version_str)

                # Check version compatibility
                if version_obj not in spec:
                    continue

                # Check prerelease policy
                if exclude_prereleases and (
                    version_obj.is_prerelease or package_spec.is_prerelease
                ):
                    continue

                # Check Python compatibility
                if not package_spec.is_compatible_with_python(self.python_version):
                    continue

                # Check Revit compatibility
                if not package_spec.is_compatible_with_revit(self.revit_version):
                    continue

                compatible_versions.append(package_spec)

            except Exception:
                continue

        # Sort by version (newest first)
        compatible_versions.sort(key=lambda p: Version(p.version), reverse=True)

        return compatible_versions

    def resolve_dependencies(
        self, requirements: dict[str, str], extras: dict[str, list[str]] | None = None
    ) -> ResolutionResult:
        """Resolve dependencies for a set of requirements.

        Args:
            requirements: Dictionary of package_name -> version_spec
            extras: Optional extras to include for each package

        Returns:
            ResolutionResult with resolved packages or conflicts
        """
        extras = extras or {}
        conflicts = []
        resolved_packages = {}

        # Track what we're trying to resolve to detect circular dependencies
        resolution_stack = []

        # Start with direct requirements
        to_resolve = [(name, spec, None) for name, spec in requirements.items()]

        while to_resolve:
            package_name, version_spec, required_by = to_resolve.pop(0)
            normalized_name = PackageSpec.normalize_name(package_name)

            # Check for circular dependencies
            if normalized_name in resolution_stack:
                cycle = resolution_stack[resolution_stack.index(normalized_name) :] + [
                    normalized_name
                ]
                conflicts.append(
                    DependencyConflict(
                        type=ConflictType.CIRCULAR_DEPENDENCY,
                        package_name=normalized_name,
                        conflicting_specs=[version_spec],
                        message=f"Circular dependency detected: {' -> '.join(cycle)}",
                        affected_packages=cycle,
                    )
                )
                continue

            resolution_stack.append(normalized_name)

            # If already resolved, check for version conflicts
            if normalized_name in resolved_packages:
                existing_spec = resolved_packages[normalized_name]
                if not self._is_version_compatible(existing_spec.version, version_spec):
                    conflicts.append(
                        DependencyConflict(
                            type=ConflictType.VERSION_CONFLICT,
                            package_name=normalized_name,
                            conflicting_specs=[existing_spec.version, version_spec],
                            message=f"Version conflict for {normalized_name}: {existing_spec.version} vs {version_spec}",
                            affected_packages=[required_by] if required_by else [],
                        )
                    )
                resolution_stack.pop()
                continue

            # Find compatible versions
            compatible_versions = self.get_compatible_versions(
                normalized_name, version_spec
            )

            if not compatible_versions:
                conflicts.append(
                    DependencyConflict(
                        type=ConflictType.MISSING_DEPENDENCY,
                        package_name=normalized_name,
                        conflicting_specs=[version_spec],
                        message=f"No compatible version found for {normalized_name} {version_spec}",
                        affected_packages=[required_by] if required_by else [],
                    )
                )
                resolution_stack.pop()
                continue

            # Prefer installed version if compatible
            selected_spec = None
            if self.prefer_installed and normalized_name in self.installed_packages:
                installed_spec = self.installed_packages[normalized_name]
                if installed_spec in compatible_versions:
                    selected_spec = installed_spec

            # Otherwise, select the best version (newest stable, or newest if allowing prereleases)
            if selected_spec is None:
                selected_spec = compatible_versions[0]

            resolved_packages[normalized_name] = selected_spec

            # Add dependencies to resolution queue
            for dep_name, dep_spec in selected_spec.dependencies.items():
                to_resolve.append((dep_name, dep_spec, normalized_name))

            # Add optional dependencies if requested
            package_extras = extras.get(normalized_name, [])
            for extra in package_extras:
                if extra in selected_spec.optional_dependencies:
                    for dep_name, dep_spec in selected_spec.optional_dependencies[
                        extra
                    ].items():
                        to_resolve.append(
                            (dep_name, dep_spec, f"{normalized_name}[{extra}]")
                        )

            resolution_stack.pop()

        # Calculate installation order (topological sort)
        installation_order = self._calculate_installation_order(resolved_packages)

        return ResolutionResult(
            resolved_packages=resolved_packages,
            conflicts=conflicts,
            installation_order=installation_order,
        )

    def _is_version_compatible(self, version1: str, version_spec: str) -> bool:
        """Check if a specific version is compatible with a version specifier."""
        try:
            spec = (
                SpecifierSet(version_spec)
                if version_spec != "*"
                else SpecifierSet(">=0.0.0")
            )
            return Version(version1) in spec
        except Exception:
            return False

    def _calculate_installation_order(
        self, resolved_packages: dict[str, PackageSpec]
    ) -> list[str]:
        """Calculate the order in which packages should be installed (topological sort)."""
        # Build dependency graph
        dependencies = {}
        for name, spec in resolved_packages.items():
            dependencies[name] = [
                PackageSpec.normalize_name(dep_name)
                for dep_name in spec.dependencies.keys()
                if PackageSpec.normalize_name(dep_name) in resolved_packages
            ]

        # Topological sort using Kahn's algorithm
        in_degree = dict.fromkeys(resolved_packages, 0)
        for name in dependencies:
            for dep in dependencies[name]:
                if dep in in_degree:
                    in_degree[dep] += 1

        queue = [name for name, degree in in_degree.items() if degree == 0]
        installation_order = []

        while queue:
            current = queue.pop(0)
            installation_order.append(current)

            for dependent in dependencies.get(current, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return installation_order

    def create_lock_file(self, resolution_result: ResolutionResult) -> dict:
        """Create a lock file from resolution results."""
        if not resolution_result.is_successful:
            raise ValueError("Cannot create lock file from unsuccessful resolution")

        from datetime import datetime

        lock_data = {
            "version": "1.0",
            "python_version": self.python_version,
            "revit_version": self.revit_version,
            "generated_at": datetime.utcnow().isoformat(),
            "packages": {},
        }

        for name, spec in resolution_result.resolved_packages.items():
            lock_data["packages"][name] = {
                "version": spec.version,
                "python_version": spec.python_version,
                "supported_revit_versions": spec.supported_revit_versions,
                "dependencies": spec.dependencies,
                "optional_dependencies": spec.optional_dependencies,
                "is_prerelease": spec.is_prerelease,
            }

        lock_data["installation_order"] = resolution_result.installation_order

        return lock_data

    def resolve_from_lock_file(self, lock_data: dict) -> ResolutionResult:
        """Resolve dependencies from a lock file."""
        resolved_packages = {}

        for name, package_data in lock_data["packages"].items():
            spec = PackageSpec(
                name=name,
                version=package_data["version"],
                python_version=package_data["python_version"],
                supported_revit_versions=package_data["supported_revit_versions"],
                dependencies=package_data["dependencies"],
                optional_dependencies=package_data["optional_dependencies"],
                is_prerelease=package_data["is_prerelease"],
            )
            resolved_packages[name] = spec

        installation_order = lock_data.get(
            "installation_order", list(resolved_packages.keys())
        )

        return ResolutionResult(
            resolved_packages=resolved_packages,
            conflicts=[],
            installation_order=installation_order,
        )
