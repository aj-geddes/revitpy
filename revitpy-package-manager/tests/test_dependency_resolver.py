"""Tests for the dependency resolution engine."""

import pytest
from packaging.version import Version

from revitpy_package_manager.installer.resolver import (
    DependencyResolver, PackageSpec, ConflictType
)


@pytest.mark.unit
def test_package_spec_normalization():
    """Test package name normalization in PackageSpec."""
    spec = PackageSpec(name="My_Package-Name", version="1.0.0")
    assert spec.name == "my-package-name"


@pytest.mark.unit
def test_package_spec_revit_compatibility():
    """Test Revit version compatibility checking."""
    spec = PackageSpec(
        name="test-package",
        version="1.0.0",
        supported_revit_versions=["2024", "2025"]
    )
    
    assert spec.is_compatible_with_revit("2024")
    assert spec.is_compatible_with_revit("2025")
    assert not spec.is_compatible_with_revit("2023")
    
    # No restrictions means compatible with all
    spec_no_restrictions = PackageSpec(name="unrestricted", version="1.0.0")
    assert spec_no_restrictions.is_compatible_with_revit("2023")


@pytest.mark.unit
def test_package_spec_python_compatibility():
    """Test Python version compatibility checking."""
    spec = PackageSpec(
        name="test-package",
        version="1.0.0",
        python_version=">=3.11"
    )
    
    assert spec.is_compatible_with_python("3.11.0")
    assert spec.is_compatible_with_python("3.12.0")
    assert not spec.is_compatible_with_python("3.10.0")


@pytest.mark.unit
def test_resolver_initialization():
    """Test dependency resolver initialization."""
    resolver = DependencyResolver(
        python_version="3.11.0",
        revit_version="2025",
        allow_prereleases=True
    )
    
    assert resolver.python_version == "3.11.0"
    assert resolver.revit_version == "2025"
    assert resolver.allow_prereleases is True


@pytest.mark.unit
def test_register_available_package():
    """Test registering available packages."""
    resolver = DependencyResolver()
    
    package_spec = PackageSpec(
        name="test-package",
        version="1.0.0",
        python_version=">=3.11",
        supported_revit_versions=["2025"]
    )
    
    resolver.register_available_package(package_spec)
    
    assert "test-package" in resolver.available_packages
    assert "1.0.0" in resolver.available_packages["test-package"]


@pytest.mark.unit
def test_get_compatible_versions():
    """Test getting compatible versions of a package."""
    resolver = DependencyResolver(python_version="3.11.0", revit_version="2025")
    
    # Register multiple versions
    versions = ["1.0.0", "1.1.0", "2.0.0", "2.1.0-alpha"]
    for ver in versions:
        spec = PackageSpec(
            name="test-package",
            version=ver,
            python_version=">=3.11",
            supported_revit_versions=["2025"],
            is_prerelease="-alpha" in ver
        )
        resolver.register_available_package(spec)
    
    # Get compatible versions (excluding prereleases by default)
    compatible = resolver.get_compatible_versions("test-package", ">=1.0.0")
    
    assert len(compatible) == 3  # Excludes alpha version
    assert compatible[0].version == "2.0.0"  # Newest first
    
    # Include prereleases
    resolver.allow_prereleases = True
    compatible_with_prerel = resolver.get_compatible_versions("test-package", ">=1.0.0")
    assert len(compatible_with_prerel) == 4


@pytest.mark.unit
def test_simple_dependency_resolution():
    """Test simple dependency resolution without conflicts."""
    resolver = DependencyResolver()
    
    # Register package A (no dependencies)
    spec_a = PackageSpec(name="package-a", version="1.0.0")
    resolver.register_available_package(spec_a)
    
    # Register package B (depends on A)
    spec_b = PackageSpec(
        name="package-b",
        version="1.0.0",
        dependencies={"package-a": ">=1.0.0"}
    )
    resolver.register_available_package(spec_b)
    
    # Resolve dependencies
    requirements = {"package-b": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert result.is_successful
    assert len(result.resolved_packages) == 2
    assert "package-a" in result.resolved_packages
    assert "package-b" in result.resolved_packages
    
    # Check installation order
    assert result.installation_order.index("package-a") < result.installation_order.index("package-b")


@pytest.mark.unit
def test_version_conflict_detection():
    """Test detection of version conflicts."""
    resolver = DependencyResolver()
    
    # Register packages
    spec_a1 = PackageSpec(name="package-a", version="1.0.0")
    spec_a2 = PackageSpec(name="package-a", version="2.0.0")
    spec_b = PackageSpec(
        name="package-b",
        version="1.0.0",
        dependencies={"package-a": ">=1.0.0,<2.0.0"}  # Wants 1.x
    )
    spec_c = PackageSpec(
        name="package-c",
        version="1.0.0",
        dependencies={"package-a": ">=2.0.0"}  # Wants 2.x
    )
    
    for spec in [spec_a1, spec_a2, spec_b, spec_c]:
        resolver.register_available_package(spec)
    
    # Try to resolve conflicting requirements
    requirements = {"package-b": ">=1.0.0", "package-c": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert not result.is_successful
    assert len(result.conflicts) > 0
    
    # Should have a version conflict
    version_conflicts = [c for c in result.conflicts if c.type == ConflictType.VERSION_CONFLICT]
    assert len(version_conflicts) > 0


@pytest.mark.unit
def test_circular_dependency_detection():
    """Test detection of circular dependencies."""
    resolver = DependencyResolver()
    
    # Create circular dependency: A -> B -> A
    spec_a = PackageSpec(
        name="package-a",
        version="1.0.0",
        dependencies={"package-b": ">=1.0.0"}
    )
    spec_b = PackageSpec(
        name="package-b",
        version="1.0.0",
        dependencies={"package-a": ">=1.0.0"}
    )
    
    resolver.register_available_package(spec_a)
    resolver.register_available_package(spec_b)
    
    requirements = {"package-a": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert not result.is_successful
    circular_conflicts = [c for c in result.conflicts if c.type == ConflictType.CIRCULAR_DEPENDENCY]
    assert len(circular_conflicts) > 0


@pytest.mark.unit
def test_missing_dependency():
    """Test handling of missing dependencies."""
    resolver = DependencyResolver()
    
    # Register package B that depends on non-existent package A
    spec_b = PackageSpec(
        name="package-b",
        version="1.0.0",
        dependencies={"nonexistent-package": ">=1.0.0"}
    )
    resolver.register_available_package(spec_b)
    
    requirements = {"package-b": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert not result.is_successful
    missing_conflicts = [c for c in result.conflicts if c.type == ConflictType.MISSING_DEPENDENCY]
    assert len(missing_conflicts) > 0


@pytest.mark.unit
def test_optional_dependencies():
    """Test handling of optional dependencies with extras."""
    resolver = DependencyResolver()
    
    # Register optional dependency
    spec_optional = PackageSpec(name="optional-package", version="1.0.0")
    resolver.register_available_package(spec_optional)
    
    # Register main package with optional dependencies
    spec_main = PackageSpec(
        name="main-package",
        version="1.0.0",
        optional_dependencies={
            "extra1": {"optional-package": ">=1.0.0"}
        }
    )
    resolver.register_available_package(spec_main)
    
    # Resolve with extras
    requirements = {"main-package": ">=1.0.0"}
    extras = {"main-package": ["extra1"]}
    result = resolver.resolve_dependencies(requirements, extras)
    
    assert result.is_successful
    assert "optional-package" in result.resolved_packages


@pytest.mark.unit
def test_prefer_installed_packages():
    """Test preferring already installed packages."""
    resolver = DependencyResolver(prefer_installed=True)
    
    # Register multiple versions
    spec_old = PackageSpec(name="test-package", version="1.0.0")
    spec_new = PackageSpec(name="test-package", version="2.0.0")
    
    resolver.register_available_package(spec_old)
    resolver.register_available_package(spec_new)
    
    # Mark old version as installed
    resolver.register_installed_package(spec_old)
    
    requirements = {"test-package": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert result.is_successful
    assert result.resolved_packages["test-package"].version == "1.0.0"  # Prefers installed


@pytest.mark.unit
def test_lock_file_creation():
    """Test creation of lock files."""
    resolver = DependencyResolver()
    
    # Set up simple resolution
    spec_a = PackageSpec(name="package-a", version="1.0.0")
    resolver.register_available_package(spec_a)
    
    requirements = {"package-a": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert result.is_successful
    
    # Create lock file
    lock_data = resolver.create_lock_file(result)
    
    assert lock_data["version"] == "1.0"
    assert "package-a" in lock_data["packages"]
    assert lock_data["packages"]["package-a"]["version"] == "1.0.0"
    assert "installation_order" in lock_data


@pytest.mark.unit
def test_resolve_from_lock_file():
    """Test resolving dependencies from a lock file."""
    resolver = DependencyResolver()
    
    lock_data = {
        "version": "1.0",
        "python_version": "3.11.0",
        "revit_version": "2025",
        "packages": {
            "package-a": {
                "version": "1.0.0",
                "python_version": ">=3.11",
                "supported_revit_versions": ["2025"],
                "dependencies": {},
                "optional_dependencies": {},
                "is_prerelease": False
            }
        },
        "installation_order": ["package-a"]
    }
    
    result = resolver.resolve_from_lock_file(lock_data)
    
    assert result.is_successful
    assert "package-a" in result.resolved_packages
    assert result.resolved_packages["package-a"].version == "1.0.0"
    assert result.installation_order == ["package-a"]


@pytest.mark.unit
def test_complex_dependency_tree():
    """Test resolving a complex dependency tree."""
    resolver = DependencyResolver()
    
    # Create a complex dependency tree:
    # app -> lib1, lib2
    # lib1 -> common
    # lib2 -> common, util
    
    specs = [
        PackageSpec(name="common", version="1.0.0"),
        PackageSpec(name="util", version="1.0.0"),
        PackageSpec(
            name="lib1",
            version="1.0.0",
            dependencies={"common": ">=1.0.0"}
        ),
        PackageSpec(
            name="lib2",
            version="1.0.0",
            dependencies={"common": ">=1.0.0", "util": ">=1.0.0"}
        ),
        PackageSpec(
            name="app",
            version="1.0.0",
            dependencies={"lib1": ">=1.0.0", "lib2": ">=1.0.0"}
        ),
    ]
    
    for spec in specs:
        resolver.register_available_package(spec)
    
    requirements = {"app": ">=1.0.0"}
    result = resolver.resolve_dependencies(requirements)
    
    assert result.is_successful
    assert len(result.resolved_packages) == 5
    
    # Check that installation order respects dependencies
    order = result.installation_order
    assert order.index("common") < order.index("lib1")
    assert order.index("common") < order.index("lib2")
    assert order.index("util") < order.index("lib2")
    assert order.index("lib1") < order.index("app")
    assert order.index("lib2") < order.index("app")


@pytest.mark.unit
def test_revit_version_filtering():
    """Test that packages are filtered by Revit version compatibility."""
    resolver = DependencyResolver(revit_version="2024")
    
    # Package that only supports 2025
    spec_new = PackageSpec(
        name="test-package",
        version="2.0.0",
        supported_revit_versions=["2025"]
    )
    
    # Package that supports 2024
    spec_old = PackageSpec(
        name="test-package",
        version="1.0.0",
        supported_revit_versions=["2024", "2025"]
    )
    
    resolver.register_available_package(spec_new)
    resolver.register_available_package(spec_old)
    
    compatible = resolver.get_compatible_versions("test-package", ">=1.0.0")
    
    # Should only get the version compatible with 2024
    assert len(compatible) == 1
    assert compatible[0].version == "1.0.0"