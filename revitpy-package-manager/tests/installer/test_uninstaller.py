"""Comprehensive tests for package uninstallation functionality."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from revitpy_package_manager.installer.cli.desktop_cli import DesktopCLI


@pytest.fixture
def installed_package(tmp_path):
    """Create a mock installed package with registry and files."""
    # Create Revit installation
    revit_dir = tmp_path / "Revit 2024"
    revit_dir.mkdir()
    (revit_dir / "Revit.exe").write_text("mock")

    # Create installed package
    package_dir = revit_dir / "AddIns" / "RevitPy" / "Packages" / "test-package"
    package_dir.mkdir(parents=True)

    # Create package files
    (package_dir / "file1.py").write_text("content1")
    (package_dir / "subdir").mkdir()
    (package_dir / "subdir" / "file2.py").write_text("content2")

    # Create registry
    registry_dir = revit_dir / "AddIns" / "RevitPy"
    registry_path = registry_dir / "installed_packages.json"

    registry = {
        "test-package": {
            "version": "1.0.0",
            "install_dir": str(package_dir),
            "installed_files": ["file1.py", str(Path("subdir") / "file2.py")],
            "installed_at": "2024-01-01T00:00:00",
            "manifest": {
                "name": "test-package",
                "version": "1.0.0",
                "dependencies": [],
            },
        }
    }

    registry_path.write_text(json.dumps(registry, indent=2))

    return {
        "revit_dir": revit_dir,
        "package_dir": package_dir,
        "registry_path": registry_path,
        "registry": registry,
    }


@pytest.fixture
def desktop_cli_with_cache(tmp_path):
    """Create a DesktopCLI instance with mock cache database."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    cli = DesktopCLI(registry_url="http://test-registry:8000", cache_dir=str(cache_dir))

    # Initialize cache database with test data
    with sqlite3.connect(cli.cache.db_path) as conn:
        conn.execute(
            """
            INSERT INTO cache_entries
            (package_name, version, file_path, file_hash, cached_at, last_accessed, file_size, access_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "test-package",
                "1.0.0",
                str(tmp_path / "cache" / "test-package-1.0.0.rpyx"),
                "hash123",
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                1024,
                0,
                json.dumps({"name": "test-package", "version": "1.0.0"}),
            ),
        )

    return cli


class TestUninstallPackageDiscovery:
    """Tests for finding installed packages to uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_finds_installed_package(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall finds an installed package."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # Mock user confirmation
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = await desktop_cli_with_cache.uninstall_package("test-package")

        assert result is True

    @pytest.mark.asyncio
    async def test_uninstall_no_revit_found(self, desktop_cli_with_cache, monkeypatch):
        """Test uninstall fails when no Revit installations found."""
        monkeypatch.setattr(
            desktop_cli_with_cache, "_find_revit_installations", lambda: []
        )

        result = await desktop_cli_with_cache.uninstall_package("test-package")

        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall_package_not_installed(
        self, desktop_cli_with_cache, tmp_path, monkeypatch
    ):
        """Test uninstall succeeds idempotently when package not installed."""
        # Create Revit dir without the package
        revit_dir = tmp_path / "Revit 2024"
        revit_dir.mkdir()
        (revit_dir / "Revit.exe").write_text("mock")

        registry_dir = revit_dir / "AddIns" / "RevitPy"
        registry_dir.mkdir(parents=True)
        (registry_dir / "installed_packages.json").write_text(json.dumps({}))

        monkeypatch.setattr(
            desktop_cli_with_cache, "_find_revit_installations", lambda: [revit_dir]
        )

        result = await desktop_cli_with_cache.uninstall_package("nonexistent-package")

        # Should return True (idempotent - package not installed is the desired state)
        assert result is True


class TestFileRemoval:
    """Tests for file and directory removal during uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_removes_all_files(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall removes all package files."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify files are removed
        package_dir = installed_package["package_dir"]
        assert not (package_dir / "file1.py").exists()
        assert not (package_dir / "subdir" / "file2.py").exists()

    @pytest.mark.asyncio
    async def test_uninstall_removes_empty_directories(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that empty directories are removed after file deletion."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify empty directories are removed
        package_dir = installed_package["package_dir"]
        assert not package_dir.exists()

    @pytest.mark.asyncio
    async def test_uninstall_handles_missing_files_gracefully(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall continues even if some files are missing."""
        # Remove one file before uninstall
        (installed_package["package_dir"] / "file1.py").unlink()

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = await desktop_cli_with_cache.uninstall_package("test-package")

        assert result is True
        # Remaining file should still be removed
        assert not (installed_package["package_dir"] / "subdir" / "file2.py").exists()

    @pytest.mark.asyncio
    async def test_uninstall_handles_permission_error(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall handles permission errors gracefully."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # Mock file unlink to raise permission error
        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if "file1.py" in str(self):
                raise PermissionError("Access denied")
            return original_unlink(self, *args, **kwargs)

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            with patch.object(Path, "unlink", mock_unlink):
                result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Should still succeed overall
        assert result is True


class TestRegistryManagement:
    """Tests for registry updates during uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_removes_package_from_registry(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall removes package entry from registry."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify registry entry is removed
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        assert "test-package" not in registry

    @pytest.mark.asyncio
    async def test_uninstall_preserves_other_packages_in_registry(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall preserves other package entries."""
        # Add another package to registry
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        registry["other-package"] = {
            "version": "2.0.0",
            "install_dir": str(installed_package["revit_dir"] / "other"),
            "installed_files": ["other.py"],
        }

        with open(installed_package["registry_path"], "w") as f:
            json.dump(registry, f)

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify other package is preserved
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        assert "other-package" in registry
        assert "test-package" not in registry


class TestBackupCreation:
    """Tests for backup creation before uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_creates_backup(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that backup is created before uninstall."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Check that backup directory was created
        backup_base = installed_package["revit_dir"] / "AddIns" / "RevitPy" / "Backups"
        assert backup_base.exists()

        # Should have a backup with timestamp
        backups = list(backup_base.glob("test-package_backup_*"))
        assert len(backups) > 0

    @pytest.mark.asyncio
    async def test_uninstall_backup_contains_files(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that backup contains all package files."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Find backup
        backup_base = installed_package["revit_dir"] / "AddIns" / "RevitPy" / "Backups"
        backups = list(backup_base.glob("test-package_backup_*"))
        backup_dir = backups[0]

        # Verify files are in backup
        assert (backup_dir / "file1.py").exists()
        assert (backup_dir / "subdir" / "file2.py").exists()

    @pytest.mark.asyncio
    async def test_uninstall_continues_on_backup_failure(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall continues when backup fails if user confirms."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # Mock backup creation to fail
        with patch.object(
            desktop_cli_with_cache,
            "_create_backup",
            side_effect=Exception("Backup failed"),
        ):
            with patch(
                "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
                return_value=True,
            ):
                result = await desktop_cli_with_cache.uninstall_package("test-package")

        assert result is True


class TestDependencyHandling:
    """Tests for dependency checking before uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_checks_dependencies(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that dependencies are checked before uninstall."""
        # Add a dependent package to registry
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        registry["dependent-package"] = {
            "version": "1.0.0",
            "install_dir": str(installed_package["revit_dir"] / "dependent"),
            "manifest": {"dependencies": ["test-package"]},
        }

        with open(installed_package["registry_path"], "w") as f:
            json.dump(registry, f)

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # User confirms uninstall, then confirms breaking dependencies
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Should succeed if user confirmed
        assert result is True

    @pytest.mark.asyncio
    async def test_uninstall_cancelled_due_to_dependencies(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall can be cancelled due to dependencies."""
        # Add a dependent package
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        registry["dependent-package"] = {
            "version": "1.0.0",
            "install_dir": str(installed_package["revit_dir"] / "dependent"),
            "manifest": {"dependencies": ["test-package"]},
        }

        with open(installed_package["registry_path"], "w") as f:
            json.dump(registry, f)

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # User confirms first prompt, but denies breaking dependencies
        confirm_responses = [
            True,
            False,
        ]  # First: uninstall confirmation, Second: dependency warning
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            side_effect=confirm_responses,
        ):
            _result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Should fail because user cancelled due to dependencies
        # Note: Still returns True because it didn't encounter errors, just user cancellation
        # But package should still exist
        assert (installed_package["package_dir"] / "file1.py").exists()


class TestHookExecution:
    """Tests for pre-uninstall hook execution."""

    @pytest.mark.asyncio
    async def test_uninstall_runs_hooks(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that pre-uninstall hooks are executed."""
        # Add hooks to manifest
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)

        registry["test-package"]["manifest"]["uninstall_hooks"] = {
            "cleanup": "cleanup.py"
        }

        with open(installed_package["registry_path"], "w") as f:
            json.dump(registry, f)

        # Create hook script
        hook_script = installed_package["package_dir"] / "cleanup.py"
        hook_script.write_text("# Cleanup script")

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            with patch("subprocess.run") as mock_run:
                await desktop_cli_with_cache.uninstall_package("test-package")

                # Verify hook was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert "cleanup.py" in str(call_args)


class TestCacheCleanup:
    """Tests for cache cleanup during uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_removes_from_cache_database(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that package is removed from cache database."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify removed from cache database
        with sqlite3.connect(desktop_cli_with_cache.cache.db_path) as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE package_name = ?",
                ("test-package",),
            ).fetchone()

        assert result[0] == 0

    @pytest.mark.asyncio
    async def test_uninstall_removes_cache_files(
        self, desktop_cli_with_cache, installed_package, tmp_path, monkeypatch
    ):
        """Test that cached package files are deleted."""
        # Create actual cache file
        cache_file = tmp_path / "cache" / "test-package-1.0.0.rpyx"
        cache_file.write_text("cached package")

        # Update database with correct path
        with sqlite3.connect(desktop_cli_with_cache.cache.db_path) as conn:
            conn.execute(
                "UPDATE cache_entries SET file_path = ? WHERE package_name = ?",
                (str(cache_file), "test-package"),
            )

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            await desktop_cli_with_cache.uninstall_package("test-package")

        # Verify cache file is removed
        assert not cache_file.exists()


class TestMultipleInstallations:
    """Tests for uninstalling from multiple Revit versions."""

    @pytest.mark.asyncio
    async def test_uninstall_from_multiple_revit_versions(
        self, desktop_cli_with_cache, tmp_path, monkeypatch
    ):
        """Test uninstalling package from multiple Revit installations."""
        # Create two Revit installations with the package
        installations = []
        for year in [2023, 2024]:
            revit_dir = tmp_path / f"Revit {year}"
            revit_dir.mkdir()
            (revit_dir / "Revit.exe").write_text("mock")

            package_dir = revit_dir / "AddIns" / "RevitPy" / "Packages" / "test-package"
            package_dir.mkdir(parents=True)
            (package_dir / "file.py").write_text("content")

            registry_dir = revit_dir / "AddIns" / "RevitPy"
            registry_path = registry_dir / "installed_packages.json"

            registry = {
                "test-package": {
                    "version": "1.0.0",
                    "install_dir": str(package_dir),
                    "installed_files": ["file.py"],
                    "manifest": {"dependencies": []},
                }
            }

            registry_path.write_text(json.dumps(registry))
            installations.append(revit_dir)

        monkeypatch.setattr(
            desktop_cli_with_cache, "_find_revit_installations", lambda: installations
        )

        # User confirms all uninstalls
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = await desktop_cli_with_cache.uninstall_package("test-package")

        assert result is True

        # Verify removed from both installations
        for revit_dir in installations:
            registry_path = revit_dir / "AddIns" / "RevitPy" / "installed_packages.json"
            with open(registry_path) as f:
                registry = json.load(f)
            assert "test-package" not in registry


class TestUserConfirmation:
    """Tests for user confirmation prompts."""

    @pytest.mark.asyncio
    async def test_uninstall_cancelled_by_user(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that user can cancel uninstall."""
        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        # User denies uninstall
        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=False,
        ):
            _result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Package should still exist
        assert (installed_package["package_dir"] / "file1.py").exists()

        # Verify registry still has entry
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)
        assert "test-package" in registry


class TestErrorHandling:
    """Tests for error handling during uninstall."""

    @pytest.mark.asyncio
    async def test_uninstall_handles_corrupted_registry(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall handles corrupted registry gracefully."""
        # Corrupt the registry file
        installed_package["registry_path"].write_text("invalid json {{{")

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Should fail gracefully
        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall_handles_missing_install_directory(
        self, desktop_cli_with_cache, installed_package, monkeypatch
    ):
        """Test that uninstall handles missing installation directory."""
        # Remove installation directory
        import shutil

        shutil.rmtree(installed_package["package_dir"])

        monkeypatch.setattr(
            desktop_cli_with_cache,
            "_find_revit_installations",
            lambda: [installed_package["revit_dir"]],
        )

        with patch(
            "revitpy_package_manager.installer.cli.desktop_cli.Confirm.ask",
            return_value=True,
        ):
            result = await desktop_cli_with_cache.uninstall_package("test-package")

        # Should still succeed (cleaning up registry)
        assert result is True

        # Verify registry entry is removed
        with open(installed_package["registry_path"]) as f:
            registry = json.load(f)
        assert "test-package" not in registry
