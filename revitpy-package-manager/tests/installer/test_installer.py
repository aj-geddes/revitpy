"""Comprehensive tests for package installation functionality."""

import json
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from revitpy_package_manager.installer.cache_manager import CacheEntry
from revitpy_package_manager.installer.cli.desktop_cli import DesktopCLI


@pytest.fixture
def mock_revit_installation(tmp_path):
    """Create a mock Revit installation directory structure."""
    revit_dir = tmp_path / "Autodesk" / "Revit 2024"
    revit_dir.mkdir(parents=True)

    # Create mock Revit.exe
    (revit_dir / "Revit.exe").write_text("mock")

    # Create AddIns structure
    addins_dir = revit_dir / "AddIns" / "RevitPy"
    addins_dir.mkdir(parents=True)

    return revit_dir


@pytest.fixture
def mock_package_file(tmp_path):
    """Create a mock .rpyx package file."""
    package_dir = tmp_path / "test-package-1.0.0"
    package_dir.mkdir()

    # Create manifest
    manifest = {
        "name": "test-package",
        "version": "1.0.0",
        "description": "Test package",
        "author": "Test Author",
        "dependencies": [],
        "revit_versions": ["2024", "2025"],
    }

    (package_dir / "manifest.json").write_text(json.dumps(manifest))

    # Create some Python files
    (package_dir / "__init__.py").write_text("# Test package")
    (package_dir / "main.py").write_text("def main():\n    pass")

    # Create rpyx file (zip)
    rpyx_path = tmp_path / "test-package-1.0.0.rpyx"
    with zipfile.ZipFile(rpyx_path, "w") as zf:
        for file_path in package_dir.rglob("*"):
            if file_path.is_file():
                arcname = str(file_path.relative_to(package_dir))
                zf.write(file_path, arcname)

    return rpyx_path


@pytest.fixture
def mock_cache_entry(mock_package_file):
    """Create a mock cache entry."""
    now = datetime.now()
    return CacheEntry(
        package_name="test-package",
        version="1.0.0",
        file_path=str(mock_package_file),
        file_hash="abc123",
        cached_at=now,
        last_accessed=now,
        file_size=1024,
        access_count=0,
        metadata={
            "name": "test-package",
            "version": "1.0.0",
            "versions": [
                {
                    "version": "1.0.0",
                    "min_revit_version": "2022",
                    "max_revit_version": "2025",
                }
            ],
        },
    )


@pytest.fixture
def desktop_cli(tmp_path):
    """Create a DesktopCLI instance with mocked dependencies."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    cli = DesktopCLI(registry_url="http://test-registry:8000", cache_dir=str(cache_dir))

    return cli


class TestRevitInstallationDetection:
    """Tests for Revit installation detection."""

    def test_find_single_revit_installation(self, desktop_cli, tmp_path, monkeypatch):
        """Test finding a single Revit installation."""
        # Mock Windows environment
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("ProgramFiles", str(tmp_path))

        # Create Revit directory
        revit_dir = tmp_path / "Autodesk" / "Revit 2024"
        revit_dir.mkdir(parents=True)
        (revit_dir / "Revit.exe").write_text("mock")

        # Find installations
        installations = desktop_cli._find_revit_installations()

        assert len(installations) == 1
        assert installations[0] == revit_dir

    def test_find_multiple_revit_installations(
        self, desktop_cli, tmp_path, monkeypatch
    ):
        """Test finding multiple Revit versions."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("ProgramFiles", str(tmp_path))

        # Create multiple Revit versions
        for year in [2023, 2024, 2025]:
            revit_dir = tmp_path / "Autodesk" / f"Revit {year}"
            revit_dir.mkdir(parents=True)
            (revit_dir / "Revit.exe").write_text("mock")

        installations = desktop_cli._find_revit_installations()

        assert len(installations) == 3
        assert all("Revit" in str(path) for path in installations)

    def test_no_revit_installations_found(self, desktop_cli, tmp_path, monkeypatch):
        """Test when no Revit installations are present."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("ProgramFiles", str(tmp_path))

        installations = desktop_cli._find_revit_installations()

        assert len(installations) == 0

    def test_ignore_invalid_revit_directories(self, desktop_cli, tmp_path, monkeypatch):
        """Test that directories without Revit.exe are ignored."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("ProgramFiles", str(tmp_path))

        # Create Revit directory without Revit.exe
        revit_dir = tmp_path / "Autodesk" / "Revit 2024"
        revit_dir.mkdir(parents=True)

        installations = desktop_cli._find_revit_installations()

        assert len(installations) == 0


class TestVersionConflictChecking:
    """Tests for version conflict detection."""

    def test_no_conflict_when_package_not_installed(
        self, desktop_cli, mock_revit_installation
    ):
        """Test no conflict when package is not yet installed."""
        result = desktop_cli._check_version_conflicts(
            mock_revit_installation, "test-package", "1.0.0"
        )

        assert result is True

    def test_upgrade_to_newer_version(self, desktop_cli, mock_revit_installation):
        """Test upgrading to a newer version is allowed."""
        # Create registry with old version
        registry_path = desktop_cli._get_install_registry_path(mock_revit_installation)
        registry = {
            "test-package": {"version": "1.0.0", "installed_at": "2024-01-01T00:00:00"}
        }
        registry_path.write_text(json.dumps(registry))

        # Check conflict for newer version
        result = desktop_cli._check_version_conflicts(
            mock_revit_installation, "test-package", "2.0.0"
        )

        assert result is True

    def test_downgrade_prompts_user(
        self, desktop_cli, mock_revit_installation, monkeypatch
    ):
        """Test downgrading version prompts for confirmation."""
        # Create registry with newer version
        registry_path = desktop_cli._get_install_registry_path(mock_revit_installation)
        registry = {
            "test-package": {"version": "2.0.0", "installed_at": "2024-01-01T00:00:00"}
        }
        registry_path.write_text(json.dumps(registry))

        # Mock user confirmation
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = desktop_cli._check_version_conflicts(
                mock_revit_installation, "test-package", "1.0.0"
            )

        assert result is True


class TestPackageDeployment:
    """Tests for package deployment functionality."""

    def test_deploy_package_creates_files(self, desktop_cli, tmp_path):
        """Test that package deployment creates all files."""
        # Create source directory with files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file1.py").write_text("# File 1")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file2.py").write_text("# File 2")

        # Deploy to target
        target_dir = tmp_path / "target"
        installed_files = desktop_cli._deploy_package(source_dir, target_dir)

        assert len(installed_files) == 2
        assert (target_dir / "file1.py").exists()
        assert (target_dir / "subdir" / "file2.py").exists()

    def test_deploy_package_overwrites_existing(self, desktop_cli, tmp_path):
        """Test that deployment overwrites existing installation."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.py").write_text("new content")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "file.py").write_text("old content")

        desktop_cli._deploy_package(source_dir, target_dir)

        assert (target_dir / "file.py").read_text() == "new content"

    def test_deploy_package_returns_file_list(self, desktop_cli, tmp_path):
        """Test that deployment returns correct file list."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "a.py").write_text("a")
        (source_dir / "b").mkdir(exist_ok=True)
        (source_dir / "b" / "c.py").write_text("c")

        target_dir = tmp_path / "target"
        installed_files = desktop_cli._deploy_package(source_dir, target_dir)

        assert "a.py" in installed_files
        assert str(Path("b") / "c.py") in installed_files


class TestInstallationTracking:
    """Tests for installation tracking and registry."""

    def test_track_new_installation(self, desktop_cli, mock_revit_installation):
        """Test tracking a new package installation."""
        install_dir = (
            mock_revit_installation / "AddIns" / "RevitPy" / "Packages" / "test-package"
        )
        install_dir.mkdir(parents=True)

        manifest = {"name": "test-package", "version": "1.0.0", "author": "Test"}

        desktop_cli._track_installation(
            "test-package", "1.0.0", install_dir, ["file1.py", "file2.py"], manifest
        )

        # Verify registry was created
        registry_path = desktop_cli._get_install_registry_path(mock_revit_installation)
        assert registry_path.exists()

        with open(registry_path) as f:
            registry = json.load(f)

        assert "test-package" in registry
        assert registry["test-package"]["version"] == "1.0.0"
        assert len(registry["test-package"]["installed_files"]) == 2

    def test_track_installation_updates_existing(
        self, desktop_cli, mock_revit_installation
    ):
        """Test that tracking updates existing registry entry."""
        # Create existing registry
        registry_path = desktop_cli._get_install_registry_path(mock_revit_installation)
        existing_registry = {
            "other-package": {"version": "1.0.0", "installed_at": "2024-01-01T00:00:00"}
        }
        registry_path.write_text(json.dumps(existing_registry))

        install_dir = (
            mock_revit_installation / "AddIns" / "RevitPy" / "Packages" / "test-package"
        )
        install_dir.mkdir(parents=True)

        desktop_cli._track_installation(
            "test-package", "1.0.0", install_dir, ["file.py"], {"name": "test-package"}
        )

        with open(registry_path) as f:
            registry = json.load(f)

        # Both packages should exist
        assert "other-package" in registry
        assert "test-package" in registry


class TestBackupCreation:
    """Tests for installation backup functionality."""

    def test_create_backup_preserves_files(self, desktop_cli, tmp_path):
        """Test that backup preserves all existing files."""
        # Create existing installation
        install_dir = (
            tmp_path / "Revit 2024" / "AddIns" / "RevitPy" / "Packages" / "test-package"
        )
        install_dir.mkdir(parents=True)
        (install_dir / "file1.py").write_text("content1")
        (install_dir / "subdir").mkdir()
        (install_dir / "subdir" / "file2.py").write_text("content2")

        # Create backup
        backup_dir = desktop_cli._create_backup(install_dir)

        assert backup_dir.exists()
        assert (backup_dir / "file1.py").exists()
        assert (backup_dir / "subdir" / "file2.py").exists()
        assert (backup_dir / "file1.py").read_text() == "content1"

    def test_backup_uses_timestamp(self, desktop_cli, tmp_path):
        """Test that backup directory includes timestamp."""
        install_dir = (
            tmp_path / "Revit 2024" / "AddIns" / "RevitPy" / "Packages" / "test-package"
        )
        install_dir.mkdir(parents=True)
        (install_dir / "file.py").write_text("content")

        backup_dir = desktop_cli._create_backup(install_dir)

        assert "backup_" in backup_dir.name
        assert backup_dir.name.startswith("test-package_backup_")


class TestInstallationIntegration:
    """Integration tests for complete installation workflow."""

    @pytest.mark.asyncio
    async def test_install_from_cache_success(
        self, desktop_cli, mock_cache_entry, tmp_path, monkeypatch
    ):
        """Test successful installation from cache."""
        # Mock Revit installation
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()
        (revit_dir / "Revit.exe").write_text("mock")

        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setattr(
            desktop_cli, "_find_revit_installations", lambda: [revit_dir]
        )

        # Mock RPYXExtractor
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.RPYXExtractor"
        ) as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor_class.return_value = mock_extractor

            mock_extractor.validate_package.return_value = {"valid": True, "issues": []}

            mock_extractor.get_manifest.return_value = {
                "name": "test-package",
                "version": "1.0.0",
                "dependencies": [],
            }

            mock_extractor.extract_to.return_value = {
                "extracted_files": ["file1.py", "file2.py"]
            }

            result = await desktop_cli._install_from_cache(mock_cache_entry)

        assert result is True

        # Verify installation directory was created
        install_dir = revit_dir / "AddIns" / "RevitPy" / "Packages" / "test-package"
        assert install_dir.exists()

    @pytest.mark.asyncio
    async def test_install_from_cache_no_revit_found(
        self, desktop_cli, mock_cache_entry, monkeypatch
    ):
        """Test installation fails gracefully when no Revit found."""
        monkeypatch.setattr(desktop_cli, "_find_revit_installations", lambda: [])

        result = await desktop_cli._install_from_cache(mock_cache_entry)

        assert result is False

    @pytest.mark.asyncio
    async def test_install_from_cache_validation_failure(
        self, desktop_cli, mock_cache_entry, tmp_path, monkeypatch
    ):
        """Test installation fails when package validation fails."""
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()
        (revit_dir / "Revit.exe").write_text("mock")

        monkeypatch.setattr(
            desktop_cli, "_find_revit_installations", lambda: [revit_dir]
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.RPYXExtractor"
        ) as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor_class.return_value = mock_extractor

            mock_extractor.validate_package.return_value = {
                "valid": False,
                "issues": ["Invalid package structure"],
            }

            result = await desktop_cli._install_from_cache(mock_cache_entry)

        assert result is False


class TestDependencyChecking:
    """Tests for dependency checking before uninstall."""

    def test_no_dependencies_allows_uninstall(self, desktop_cli):
        """Test uninstall allowed when no dependencies exist."""
        registry = {"package-a": {"version": "1.0.0", "manifest": {"dependencies": []}}}

        result = desktop_cli._check_dependencies_before_uninstall(registry, "package-a")

        assert result is True

    def test_dependencies_prompt_user(self, desktop_cli, monkeypatch):
        """Test that dependencies prompt user for confirmation."""
        registry = {
            "package-a": {"version": "1.0.0", "manifest": {"dependencies": []}},
            "package-b": {
                "version": "1.0.0",
                "manifest": {"dependencies": ["package-a"]},
            },
        }

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = desktop_cli._check_dependencies_before_uninstall(
                registry, "package-a"
            )

        assert result is True


class TestErrorHandling:
    """Tests for error handling during installation."""

    @pytest.mark.asyncio
    async def test_install_handles_extraction_error(
        self, desktop_cli, mock_cache_entry, tmp_path, monkeypatch
    ):
        """Test that installation handles extraction errors gracefully."""
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()
        (revit_dir / "Revit.exe").write_text("mock")

        monkeypatch.setattr(
            desktop_cli, "_find_revit_installations", lambda: [revit_dir]
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.RPYXExtractor"
        ) as mock_extractor_class:
            mock_extractor_class.side_effect = Exception("Extraction failed")

            result = await desktop_cli._install_from_cache(mock_cache_entry)

        assert result is False

    @pytest.mark.asyncio
    async def test_install_handles_permission_error(
        self, desktop_cli, mock_cache_entry, tmp_path, monkeypatch
    ):
        """Test installation handles permission errors."""
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()
        (revit_dir / "Revit.exe").write_text("mock")

        monkeypatch.setattr(
            desktop_cli, "_find_revit_installations", lambda: [revit_dir]
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.RPYXExtractor"
        ) as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor_class.return_value = mock_extractor

            mock_extractor.validate_package.return_value = {"valid": True, "issues": []}
            mock_extractor.get_manifest.return_value = {
                "name": "test-package",
                "version": "1.0.0",
            }
            mock_extractor.extract_to.side_effect = PermissionError("Access denied")

            result = await desktop_cli._install_from_cache(mock_cache_entry)

        assert result is False


class TestInstallationDirectory:
    """Tests for installation directory management."""

    def test_get_install_directory_creates_structure(self, desktop_cli, tmp_path):
        """Test that installation directory structure is created."""
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()

        install_dir = desktop_cli._get_install_directory(revit_dir, "test-package")

        assert install_dir.exists()
        assert install_dir.parent.name == "Packages"
        assert "RevitPy" in str(install_dir)

    def test_get_install_directory_uses_package_name(self, desktop_cli, tmp_path):
        """Test that install directory uses package name."""
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()

        install_dir = desktop_cli._get_install_directory(revit_dir, "my-custom-package")

        assert install_dir.name == "my-custom-package"
