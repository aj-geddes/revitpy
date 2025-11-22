"""Tests for dependency resolution engine."""

import pytest
from revitpy_package_manager.installer.resolver import (
    ConflictType,
    DependencyConflict,
    DependencyResolver,
    PackageSpec,
    ResolutionResult,
)


class TestConflictType:
    """Test ConflictType enum."""

    def test_conflict_type_values(self):
        """Test that ConflictType enum has expected values."""
        assert ConflictType.VERSION_CONFLICT.value == "version_conflict"
        assert ConflictType.CIRCULAR_DEPENDENCY.value == "circular_dependency"
        assert ConflictType.MISSING_DEPENDENCY.value == "missing_dependency"
        assert ConflictType.REVIT_INCOMPATIBLE.value == "revit_incompatible"
        assert ConflictType.PYTHON_INCOMPATIBLE.value == "python_incompatible"


class TestPackageSpec:
    """Test PackageSpec dataclass."""

    def test_package_spec_basic_creation(self):
        """Test creating a basic package spec."""
        spec = PackageSpec(name="test-package", version="1.0.0")

        assert spec.name == "test-package"
        assert spec.version == "1.0.0"
        assert spec.python_version == ">=3.11"
        assert spec.supported_revit_versions == []
        assert spec.dependencies == {}
        assert spec.optional_dependencies == {}
        assert spec.is_prerelease is False

    def test_package_spec_with_dependencies(self):
        """Test creating a package spec with dependencies."""
        spec = PackageSpec(
            name="test-package",
            version="2.0.0",
            dependencies={"dep1": ">=1.0.0", "dep2": "^2.0.0"},
        )

        assert spec.dependencies == {"dep1": ">=1.0.0", "dep2": "^2.0.0"}

    def test_package_spec_with_optional_dependencies(self):
        """Test creating a package spec with optional dependencies."""
        spec = PackageSpec(
            name="test-package",
            version="1.0.0",
            optional_dependencies={"dev": {"pytest": ">=7.0.0", "black": ">=23.0.0"}},
        )

        assert "dev" in spec.optional_dependencies
        assert spec.optional_dependencies["dev"]["pytest"] == ">=7.0.0"

    def test_package_name_normalization(self):
        """Test that package names are normalized."""
        # Test various naming conventions
        spec1 = PackageSpec(name="Test_Package", version="1.0.0")
        spec2 = PackageSpec(name="test.package", version="1.0.0")
        spec3 = PackageSpec(name="TEST__PACKAGE", version="1.0.0")

        assert spec1.name == "test-package"
        assert spec2.name == "test-package"
        assert spec3.name == "test-package"

    def test_normalize_name_static_method(self):
        """Test the static normalize_name method."""
        assert PackageSpec.normalize_name("Test_Package") == "test-package"
        assert PackageSpec.normalize_name("test.package") == "test-package"
        assert PackageSpec.normalize_name("test--package") == "test-package"
        assert PackageSpec.normalize_name("TEST___PACKAGE") == "test-package"

    def test_revit_compatibility_no_restrictions(self):
        """Test Revit compatibility with no version restrictions."""
        spec = PackageSpec(name="test-package", version="1.0.0")

        # Should be compatible with any Revit version
        assert spec.is_compatible_with_revit("2025") is True
        assert spec.is_compatible_with_revit("2024") is True
        assert spec.is_compatible_with_revit("2023") is True

    def test_revit_compatibility_with_restrictions(self):
        """Test Revit compatibility with specific version restrictions."""
        spec = PackageSpec(
            name="test-package",
            version="1.0.0",
            supported_revit_versions=["2024", "2025"],
        )

        assert spec.is_compatible_with_revit("2025") is True
        assert spec.is_compatible_with_revit("2024") is True
        assert spec.is_compatible_with_revit("2023") is False
        assert spec.is_compatible_with_revit("2022") is False

    def test_python_compatibility(self):
        """Test Python version compatibility."""
        spec = PackageSpec(
            name="test-package", version="1.0.0", python_version=">=3.11"
        )

        assert spec.is_compatible_with_python("3.11.0") is True
        assert spec.is_compatible_with_python("3.12.0") is True
        assert spec.is_compatible_with_python("3.10.0") is False

    def test_python_compatibility_complex_spec(self):
        """Test Python compatibility with complex version specifier."""
        spec = PackageSpec(
            name="test-package", version="1.0.0", python_version=">=3.9,<3.12"
        )

        assert spec.is_compatible_with_python("3.9.0") is True
        assert spec.is_compatible_with_python("3.10.5") is True
        assert spec.is_compatible_with_python("3.11.2") is True
        assert spec.is_compatible_with_python("3.12.0") is False
        assert spec.is_compatible_with_python("3.8.0") is False

    def test_python_compatibility_invalid_version(self):
        """Test Python compatibility with invalid version string."""
        spec = PackageSpec(name="test-package", version="1.0.0")

        assert spec.is_compatible_with_python("invalid") is False


class TestDependencyConflict:
    """Test DependencyConflict dataclass."""

    def test_dependency_conflict_creation(self):
        """Test creating a dependency conflict."""
        conflict = DependencyConflict(
            type=ConflictType.VERSION_CONFLICT,
            package_name="test-package",
            conflicting_specs=["1.0.0", "2.0.0"],
            message="Version conflict",
        )

        assert conflict.type == ConflictType.VERSION_CONFLICT
        assert conflict.package_name == "test-package"
        assert conflict.conflicting_specs == ["1.0.0", "2.0.0"]
        assert conflict.message == "Version conflict"
        assert conflict.affected_packages == []

    def test_dependency_conflict_with_affected_packages(self):
        """Test creating a conflict with affected packages."""
        conflict = DependencyConflict(
            type=ConflictType.CIRCULAR_DEPENDENCY,
            package_name="package-a",
            conflicting_specs=[],
            message="Circular dependency",
            affected_packages=["package-a", "package-b", "package-c"],
        )

        assert len(conflict.affected_packages) == 3
        assert "package-b" in conflict.affected_packages


class TestResolutionResult:
    """Test ResolutionResult dataclass."""

    def test_resolution_result_successful(self):
        """Test a successful resolution result."""
        package1 = PackageSpec(name="package-a", version="1.0.0")
        package2 = PackageSpec(name="package-b", version="2.0.0")

        result = ResolutionResult(
            resolved_packages={"package-a": package1, "package-b": package2},
            conflicts=[],
            installation_order=["package-a", "package-b"],
        )

        assert result.is_successful is True
        assert len(result.resolved_packages) == 2
        assert len(result.conflicts) == 0

    def test_resolution_result_with_conflicts(self):
        """Test a resolution result with conflicts."""
        conflict = DependencyConflict(
            type=ConflictType.VERSION_CONFLICT,
            package_name="package-a",
            conflicting_specs=["1.0.0", "2.0.0"],
            message="Conflict",
        )

        result = ResolutionResult(
            resolved_packages={}, conflicts=[conflict], installation_order=[]
        )

        assert result.is_successful is False
        assert len(result.conflicts) == 1

    def test_get_critical_conflicts(self):
        """Test getting only critical conflicts."""
        conflicts = [
            DependencyConflict(
                ConflictType.VERSION_CONFLICT, "pkg1", [], "Version conflict"
            ),
            DependencyConflict(
                ConflictType.REVIT_INCOMPATIBLE, "pkg2", [], "Revit incompatible"
            ),
            DependencyConflict(
                ConflictType.CIRCULAR_DEPENDENCY, "pkg3", [], "Circular"
            ),
            DependencyConflict(ConflictType.MISSING_DEPENDENCY, "pkg4", [], "Missing"),
            DependencyConflict(
                ConflictType.PYTHON_INCOMPATIBLE, "pkg5", [], "Python incompatible"
            ),
        ]

        result = ResolutionResult(
            resolved_packages={}, conflicts=conflicts, installation_order=[]
        )

        critical = result.get_critical_conflicts()

        # Should have 3 critical conflicts
        assert len(critical) == 3
        assert any(c.type == ConflictType.VERSION_CONFLICT for c in critical)
        assert any(c.type == ConflictType.CIRCULAR_DEPENDENCY for c in critical)
        assert any(c.type == ConflictType.MISSING_DEPENDENCY for c in critical)


class TestDependencyResolver:
    """Test DependencyResolver class."""

    def test_resolver_initialization(self):
        """Test resolver initialization."""
        resolver = DependencyResolver(
            python_version="3.11.0",
            revit_version="2025",
            allow_prereleases=False,
            prefer_installed=True,
        )

        assert resolver.python_version == "3.11.0"
        assert resolver.revit_version == "2025"
        assert resolver.allow_prereleases is False
        assert resolver.prefer_installed is True
        assert len(resolver.available_packages) == 0
        assert len(resolver.installed_packages) == 0

    def test_register_available_package(self):
        """Test registering available packages."""
        resolver = DependencyResolver()

        package1 = PackageSpec(name="test-package", version="1.0.0")
        package2 = PackageSpec(name="test-package", version="2.0.0")

        resolver.register_available_package(package1)
        resolver.register_available_package(package2)

        assert "test-package" in resolver.available_packages
        assert len(resolver.available_packages["test-package"]) == 2
        assert "1.0.0" in resolver.available_packages["test-package"]
        assert "2.0.0" in resolver.available_packages["test-package"]

    def test_register_installed_package(self):
        """Test registering installed packages."""
        resolver = DependencyResolver()

        package = PackageSpec(name="installed-package", version="1.5.0")
        resolver.register_installed_package(package)

        assert "installed-package" in resolver.installed_packages
        assert resolver.installed_packages["installed-package"].version == "1.5.0"

    def test_get_compatible_versions_basic(self):
        """Test getting compatible versions with basic version spec."""
        resolver = DependencyResolver(python_version="3.11.0", revit_version="2025")

        # Register several versions
        for version in ["1.0.0", "1.1.0", "1.2.0", "2.0.0", "2.1.0"]:
            package = PackageSpec(name="test-package", version=version)
            resolver.register_available_package(package)

        # Get versions matching >=1.0.0,<2.0.0
        compatible = resolver.get_compatible_versions("test-package", ">=1.0.0,<2.0.0")

        assert len(compatible) == 3
        assert all(p.name == "test-package" for p in compatible)
        # Should be sorted newest first
        assert compatible[0].version == "1.2.0"
        assert compatible[1].version == "1.1.0"
        assert compatible[2].version == "1.0.0"

    def test_get_compatible_versions_prerelease_filtering(self):
        """Test that prereleases are filtered when appropriate."""
        resolver = DependencyResolver(allow_prereleases=False)

        # Register stable and prerelease versions
        stable = PackageSpec(name="test-package", version="1.0.0", is_prerelease=False)
        prerelease = PackageSpec(
            name="test-package", version="1.1.0", is_prerelease=True
        )

        resolver.register_available_package(stable)
        resolver.register_available_package(prerelease)

        # Should only get stable version
        compatible = resolver.get_compatible_versions("test-package", ">=1.0.0")

        assert len(compatible) == 1
        assert compatible[0].version == "1.0.0"

    def test_get_compatible_versions_python_filtering(self):
        """Test that packages incompatible with Python version are filtered."""
        resolver = DependencyResolver(python_version="3.10.0")

        # Package requiring Python 3.11+
        package_new = PackageSpec(
            name="test-package", version="2.0.0", python_version=">=3.11"
        )
        # Package compatible with Python 3.9+
        package_old = PackageSpec(
            name="test-package", version="1.0.0", python_version=">=3.9"
        )

        resolver.register_available_package(package_new)
        resolver.register_available_package(package_old)

        compatible = resolver.get_compatible_versions("test-package", "*")

        # Should only get the version compatible with Python 3.10
        assert len(compatible) == 1
        assert compatible[0].version == "1.0.0"

    def test_get_compatible_versions_revit_filtering(self):
        """Test that packages incompatible with Revit version are filtered."""
        resolver = DependencyResolver(revit_version="2024")

        # Package for Revit 2025 only
        package_2025 = PackageSpec(
            name="test-package", version="2.0.0", supported_revit_versions=["2025"]
        )
        # Package for Revit 2024
        package_2024 = PackageSpec(
            name="test-package",
            version="1.0.0",
            supported_revit_versions=["2024", "2025"],
        )

        resolver.register_available_package(package_2025)
        resolver.register_available_package(package_2024)

        compatible = resolver.get_compatible_versions("test-package", "*")

        # Should only get the version compatible with Revit 2024
        assert len(compatible) == 1
        assert compatible[0].version == "1.0.0"

    def test_resolve_single_package(self):
        """Test resolving a single package with no dependencies."""
        resolver = DependencyResolver()

        package = PackageSpec(name="simple-package", version="1.0.0")
        resolver.register_available_package(package)

        result = resolver.resolve_dependencies({"simple-package": ">=1.0.0"})

        assert result.is_successful is True
        assert len(result.resolved_packages) == 1
        assert "simple-package" in result.resolved_packages
        assert result.resolved_packages["simple-package"].version == "1.0.0"

    def test_resolve_package_with_dependencies(self):
        """Test resolving a package with dependencies."""
        resolver = DependencyResolver()

        # Register dependency
        dep = PackageSpec(name="dependency", version="2.0.0")
        resolver.register_available_package(dep)

        # Register main package that depends on it
        main = PackageSpec(
            name="main-package", version="1.0.0", dependencies={"dependency": ">=2.0.0"}
        )
        resolver.register_available_package(main)

        result = resolver.resolve_dependencies({"main-package": ">=1.0.0"})

        assert result.is_successful is True
        assert len(result.resolved_packages) == 2
        assert "main-package" in result.resolved_packages
        assert "dependency" in result.resolved_packages

    def test_resolve_missing_dependency(self):
        """Test resolving a package with a missing dependency."""
        resolver = DependencyResolver()

        # Register package but not its dependency
        package = PackageSpec(
            name="broken-package",
            version="1.0.0",
            dependencies={"missing-dep": ">=1.0.0"},
        )
        resolver.register_available_package(package)

        result = resolver.resolve_dependencies({"broken-package": ">=1.0.0"})

        assert result.is_successful is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == ConflictType.MISSING_DEPENDENCY
        assert result.conflicts[0].package_name == "missing-dep"

    def test_resolve_version_conflict(self):
        """Test resolving packages with version conflicts."""
        resolver = DependencyResolver()

        # Register shared dependency
        dep_v1 = PackageSpec(name="shared-dep", version="1.0.0")
        dep_v2 = PackageSpec(name="shared-dep", version="2.0.0")
        resolver.register_available_package(dep_v1)
        resolver.register_available_package(dep_v2)

        # Register two packages requiring different versions
        pkg_a = PackageSpec(
            name="package-a",
            version="1.0.0",
            dependencies={"shared-dep": ">=1.0.0,<2.0.0"},
        )
        pkg_b = PackageSpec(
            name="package-b", version="1.0.0", dependencies={"shared-dep": ">=2.0.0"}
        )
        resolver.register_available_package(pkg_a)
        resolver.register_available_package(pkg_b)

        result = resolver.resolve_dependencies(
            {"package-a": ">=1.0.0", "package-b": ">=1.0.0"}
        )

        assert result.is_successful is False
        assert any(c.type == ConflictType.VERSION_CONFLICT for c in result.conflicts)

    def test_resolve_circular_dependency(self):
        """Test detecting circular dependencies."""
        resolver = DependencyResolver()

        # Create circular dependency: A -> B -> C -> A
        pkg_a = PackageSpec(
            name="package-a", version="1.0.0", dependencies={"package-b": "*"}
        )
        pkg_b = PackageSpec(
            name="package-b", version="1.0.0", dependencies={"package-c": "*"}
        )
        pkg_c = PackageSpec(
            name="package-c", version="1.0.0", dependencies={"package-a": "*"}
        )

        resolver.register_available_package(pkg_a)
        resolver.register_available_package(pkg_b)
        resolver.register_available_package(pkg_c)

        result = resolver.resolve_dependencies({"package-a": "*"})

        assert result.is_successful is False
        assert any(c.type == ConflictType.CIRCULAR_DEPENDENCY for c in result.conflicts)

    def test_resolve_optional_dependencies(self):
        """Test resolving optional dependencies (extras)."""
        resolver = DependencyResolver()

        # Register optional dependency
        optional_dep = PackageSpec(name="optional-dep", version="1.0.0")
        resolver.register_available_package(optional_dep)

        # Register package with optional dependency
        package = PackageSpec(
            name="main-package",
            version="1.0.0",
            optional_dependencies={"dev": {"optional-dep": ">=1.0.0"}},
        )
        resolver.register_available_package(package)

        # Resolve without extras
        result_no_extras = resolver.resolve_dependencies({"main-package": ">=1.0.0"})
        assert "optional-dep" not in result_no_extras.resolved_packages

        # Resolve with extras
        result_with_extras = resolver.resolve_dependencies(
            {"main-package": ">=1.0.0"}, extras={"main-package": ["dev"]}
        )
        assert "optional-dep" in result_with_extras.resolved_packages

    def test_installation_order(self):
        """Test that installation order is correct (dependencies before dependents)."""
        resolver = DependencyResolver()

        # Create chain: A depends on B, B depends on C
        pkg_c = PackageSpec(name="package-c", version="1.0.0")
        pkg_b = PackageSpec(
            name="package-b", version="1.0.0", dependencies={"package-c": "*"}
        )
        pkg_a = PackageSpec(
            name="package-a", version="1.0.0", dependencies={"package-b": "*"}
        )

        resolver.register_available_package(pkg_c)
        resolver.register_available_package(pkg_b)
        resolver.register_available_package(pkg_a)

        result = resolver.resolve_dependencies({"package-a": "*"})

        assert result.is_successful is True
        # C should be installed before B, B before A
        assert result.installation_order.index(
            "package-c"
        ) < result.installation_order.index("package-b")
        assert result.installation_order.index(
            "package-b"
        ) < result.installation_order.index("package-a")

    def test_prefer_installed_version(self):
        """Test that installed versions are preferred when compatible."""
        resolver = DependencyResolver(prefer_installed=True)

        # Register available versions
        pkg_v1 = PackageSpec(name="test-package", version="1.0.0")
        pkg_v2 = PackageSpec(name="test-package", version="2.0.0")
        resolver.register_available_package(pkg_v1)
        resolver.register_available_package(pkg_v2)

        # Register installed version
        installed = PackageSpec(name="test-package", version="1.5.0")
        resolver.register_available_package(installed)
        resolver.register_installed_package(installed)

        result = resolver.resolve_dependencies({"test-package": ">=1.0.0"})

        # Should prefer the installed version if compatible
        assert result.resolved_packages["test-package"].version == "1.5.0"

    def test_create_lock_file(self):
        """Test creating a lock file from resolution results."""
        resolver = DependencyResolver(python_version="3.11.0", revit_version="2025")

        pkg = PackageSpec(name="test-package", version="1.0.0")
        resolver.register_available_package(pkg)

        result = resolver.resolve_dependencies({"test-package": ">=1.0.0"})
        lock_data = resolver.create_lock_file(result)

        assert lock_data["version"] == "1.0"
        assert lock_data["python_version"] == "3.11.0"
        assert lock_data["revit_version"] == "2025"
        assert "test-package" in lock_data["packages"]
        assert lock_data["packages"]["test-package"]["version"] == "1.0.0"
        assert "installation_order" in lock_data

    def test_create_lock_file_fails_with_conflicts(self):
        """Test that creating lock file fails if there are conflicts."""
        resolver = DependencyResolver()

        result = ResolutionResult(
            resolved_packages={},
            conflicts=[
                DependencyConflict(ConflictType.VERSION_CONFLICT, "pkg", [], "Conflict")
            ],
            installation_order=[],
        )

        with pytest.raises(ValueError, match="unsuccessful resolution"):
            resolver.create_lock_file(result)

    def test_resolve_from_lock_file(self):
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
                    "supported_revit_versions": [],
                    "dependencies": {"package-b": ">=1.0.0"},
                    "optional_dependencies": {},
                    "is_prerelease": False,
                },
                "package-b": {
                    "version": "1.0.0",
                    "python_version": ">=3.11",
                    "supported_revit_versions": [],
                    "dependencies": {},
                    "optional_dependencies": {},
                    "is_prerelease": False,
                },
            },
            "installation_order": ["package-b", "package-a"],
        }

        result = resolver.resolve_from_lock_file(lock_data)

        assert result.is_successful is True
        assert len(result.resolved_packages) == 2
        assert "package-a" in result.resolved_packages
        assert "package-b" in result.resolved_packages
        assert result.installation_order == ["package-b", "package-a"]


class TestComplexScenarios:
    """Test complex resolution scenarios."""

    def test_diamond_dependency(self):
        """Test resolving diamond dependency pattern (A depends on B and C, both depend on D)."""
        resolver = DependencyResolver()

        # D has no dependencies
        pkg_d = PackageSpec(name="package-d", version="1.0.0")

        # B and C both depend on D
        pkg_b = PackageSpec(
            name="package-b", version="1.0.0", dependencies={"package-d": "*"}
        )
        pkg_c = PackageSpec(
            name="package-c", version="1.0.0", dependencies={"package-d": "*"}
        )

        # A depends on both B and C
        pkg_a = PackageSpec(
            name="package-a",
            version="1.0.0",
            dependencies={"package-b": "*", "package-c": "*"},
        )

        resolver.register_available_package(pkg_d)
        resolver.register_available_package(pkg_b)
        resolver.register_available_package(pkg_c)
        resolver.register_available_package(pkg_a)

        result = resolver.resolve_dependencies({"package-a": "*"})

        assert result.is_successful is True
        assert len(result.resolved_packages) == 4
        # D should only appear once
        assert result.resolved_packages["package-d"].version == "1.0.0"
        # D should be installed first
        assert result.installation_order[0] == "package-d"

    def test_multiple_version_resolution(self):
        """Test resolving with multiple compatible versions available."""
        resolver = DependencyResolver()

        # Register multiple versions
        for i in range(1, 6):
            pkg = PackageSpec(name="test-package", version=f"{i}.0.0")
            resolver.register_available_package(pkg)

        result = resolver.resolve_dependencies({"test-package": ">=2.0.0,<5.0.0"})

        assert result.is_successful is True
        # Should select the newest compatible version (4.0.0)
        assert result.resolved_packages["test-package"].version == "4.0.0"

    def test_wildcard_version_spec(self):
        """Test resolving with wildcard version specifier."""
        resolver = DependencyResolver()

        pkg = PackageSpec(name="test-package", version="3.2.1")
        resolver.register_available_package(pkg)

        result = resolver.resolve_dependencies({"test-package": "*"})

        assert result.is_successful is True
        assert result.resolved_packages["test-package"].version == "3.2.1"
