"""Desktop-optimized CLI for RevitPy package management.

Integrates with VS Code and provides fast operations for desktop development.
"""

import asyncio
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import click
import packaging.version
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ...builder.rpyx_format import RPYXExtractor
from ...config import get_program_files_path, get_program_files_x86_path, is_debug_mode
from ...security.desktop_scanner import SecurityScanner
from ..cache_manager import CacheEntry, DesktopPackageCache

console = Console()


class DesktopCLI:
    """Desktop-optimized CLI for package management."""

    def __init__(
        self, registry_url: str = "http://localhost:8000", cache_dir: str | None = None
    ):
        self.registry_url = registry_url
        self.cache = DesktopPackageCache(cache_dir, registry_url)
        self.security_scanner = SecurityScanner()

    async def cleanup(self):
        """Cleanup resources."""
        await self.cache.close()

    async def search_packages(
        self,
        query: str,
        revit_version: str | None = None,
        package_type: str | None = None,
        offline: bool = False,
    ) -> list[dict]:
        """Search packages with desktop optimizations."""

        if offline:
            return await self.cache.search_packages_offline(query, revit_version)

        try:
            session = await self.cache.get_session()
            params = {"q": query}
            if revit_version:
                params["revit_version"] = revit_version
            if package_type:
                params["package_type"] = package_type

            async with session.get(
                f"{self.registry_url}/api/packages/search", params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("results", [])

        except Exception as e:
            console.print(f"[red]Search failed: {e}[/red]")
            console.print("[yellow]Falling back to offline search...[/yellow]")
            return await self.cache.search_packages_offline(query, revit_version)

    async def install_package(
        self,
        package_name: str,
        version: str | None = None,
        revit_version: str | None = None,
        force: bool = False,
        offline: bool = False,
    ) -> bool:
        """Install a package with desktop optimizations."""

        # Normalize package name
        normalized_name = self.cache.normalize_name(package_name)

        # Determine version to install
        if not version:
            version = await self._get_latest_compatible_version(
                normalized_name, revit_version, offline
            )
            if not version:
                console.print(
                    f"[red]No compatible version found for {package_name}[/red]"
                )
                return False

        # Check if already cached and compatible
        if not force:
            cached = await self.cache.get_cached_package(normalized_name, version)
            if cached:
                console.print(
                    f"[green]Package {package_name} {version} is already cached[/green]"
                )

                # Check compatibility
                if revit_version and not await self._check_revit_compatibility(
                    cached, revit_version
                ):
                    console.print(
                        f"[yellow]Warning: Package may not be compatible with Revit {revit_version}[/yellow]"
                    )
                    if not Confirm.ask("Continue anyway?"):
                        return False

                return await self._install_from_cache(cached)

        # Download and cache the package
        with console.status(f"[cyan]Downloading {package_name} {version}..."):
            try:
                cache_entry = await self.cache.get_package(
                    normalized_name, version, not offline
                )
                if not cache_entry:
                    console.print(
                        f"[red]Package {package_name} {version} not found[/red]"
                    )
                    return False

            except Exception as e:
                console.print(f"[red]Download failed: {e}[/red]")
                return False

        # Security scan
        if not await self._security_check(cache_entry):
            console.print("[red]Security check failed[/red]")
            if not force or not Confirm.ask("Install anyway? (NOT RECOMMENDED)"):
                return False

        # Install the package
        return await self._install_from_cache(cache_entry)

    async def _get_latest_compatible_version(
        self, package_name: str, revit_version: str | None, offline: bool = False
    ) -> str | None:
        """Get the latest compatible version for a package."""

        try:
            if offline:
                offline_metadata = await self.cache.load_offline_metadata()
                if offline_metadata and package_name in offline_metadata.version_index:
                    versions = offline_metadata.version_index[package_name]
                    # Return latest version (assuming sorted)
                    return versions[0] if versions else None
                return None

            session = await self.cache.get_session()
            async with session.get(
                f"{self.registry_url}/api/packages/{package_name}"
            ) as response:
                response.raise_for_status()
                data = await response.json()

                versions = data.get("versions", [])
                if not versions:
                    return None

                # Filter by Revit compatibility if specified
                if revit_version:
                    compatible_versions = []
                    for version_info in versions:
                        min_revit = version_info.get("min_revit_version")
                        max_revit = version_info.get("max_revit_version")

                        if min_revit and packaging.version.parse(
                            revit_version
                        ) < packaging.version.parse(min_revit):
                            continue

                        if max_revit and packaging.version.parse(
                            revit_version
                        ) > packaging.version.parse(max_revit):
                            continue

                        compatible_versions.append(version_info)

                    versions = compatible_versions

                # Return latest version
                return versions[0]["version"] if versions else None

        except Exception:
            return None

    async def _check_revit_compatibility(
        self, cache_entry: CacheEntry, revit_version: str
    ) -> bool:
        """Check if cached package is compatible with Revit version."""
        metadata = cache_entry.metadata

        # Check version compatibility from metadata
        for version_info in metadata.get("versions", []):
            if version_info["version"] == cache_entry.version:
                min_revit = version_info.get("min_revit_version")
                max_revit = version_info.get("max_revit_version")

                if min_revit and packaging.version.parse(
                    revit_version
                ) < packaging.version.parse(min_revit):
                    return False

                if max_revit and packaging.version.parse(
                    revit_version
                ) > packaging.version.parse(max_revit):
                    return False

                return True

        return True  # Assume compatible if no version info

    async def _security_check(self, cache_entry: CacheEntry) -> bool:
        """Perform security check on cached package."""
        try:
            scan_result = await self.security_scanner.scan_package_file(
                Path(cache_entry.file_path)
            )

            if scan_result.risk_level == "high":
                console.print("[red]HIGH SECURITY RISK DETECTED[/red]")
                for issue in scan_result.issues:
                    console.print(f"  [red]• {issue}[/red]")
                return False

            elif scan_result.risk_level == "medium":
                console.print("[yellow]Medium security risk detected[/yellow]")
                for issue in scan_result.issues:
                    console.print(f"  [yellow]• {issue}[/yellow]")
                return Confirm.ask("Continue with installation?")

            elif scan_result.issues:
                console.print("[blue]Security scan completed with warnings:[/blue]")
                for issue in scan_result.issues:
                    console.print(f"  [blue]• {issue}[/blue]")

            return True

        except Exception as e:
            console.print(f"[yellow]Security scan failed: {e}[/yellow]")
            return Confirm.ask("Continue without security scan?")

    async def _install_from_cache(self, cache_entry: CacheEntry) -> bool:
        """Install package from cache entry."""
        try:
            console.print(
                f"[blue]Installing {cache_entry.package_name} {cache_entry.version}...[/blue]"
            )

            # Find Revit installation directory
            revit_dirs = self._find_revit_installations()
            if not revit_dirs:
                console.print("[red]No Revit installations found[/red]")
                return False

            # Let user choose Revit version if multiple found
            revit_dir = (
                revit_dirs[0]
                if len(revit_dirs) == 1
                else self._select_revit_version(revit_dirs)
            )
            if not revit_dir:
                console.print("[yellow]Installation cancelled[/yellow]")
                return False

            console.print(f"[dim]Installing to: {revit_dir}[/dim]")

            # Extract and validate package
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Initialize extractor
                extractor = RPYXExtractor(cache_entry.file_path)

                # Validate package
                validation = extractor.validate_package()
                if not validation["valid"]:
                    console.print("[red]Package validation failed:[/red]")
                    for issue in validation["issues"]:
                        console.print(f"  [red]• {issue}[/red]")
                    return False

                # Get manifest
                manifest = extractor.get_manifest()
                package_name = manifest.get("name", cache_entry.package_name)
                version = manifest.get("version", cache_entry.version)

                # Check for version conflicts
                if not self._check_version_conflicts(revit_dir, package_name, version):
                    return False

                # Extract package to temp directory
                console.print("[blue]Extracting package...[/blue]")
                extractor.extract_to(temp_path / package_name, overwrite=True)

                # Deploy to Revit directory
                install_dir = self._get_install_directory(revit_dir, package_name)

                # Create backup if package exists
                if install_dir.exists():
                    backup_dir = self._create_backup(install_dir)
                    console.print(f"[dim]Backup created: {backup_dir}[/dim]")

                # Copy files to Revit directory
                console.print("[blue]Deploying package files...[/blue]")
                installed_files = self._deploy_package(
                    temp_path / package_name, install_dir
                )

                # Track installation for later uninstall
                self._track_installation(
                    package_name, version, install_dir, installed_files, manifest
                )

                # Run post-install hooks if specified
                install_hooks = manifest.get("install_hooks", {})
                if install_hooks:
                    console.print("[blue]Running post-install hooks...[/blue]")
                    self._run_hooks(install_hooks, install_dir)

                console.print(
                    f"[green]✓ Successfully installed {package_name} {version}[/green]"
                )
                console.print(f"[dim]Location: {install_dir}[/dim]")
                console.print(f"[dim]Files installed: {len(installed_files)}[/dim]")

                return True

        except Exception as e:
            console.print(f"[red]Installation failed: {e}[/red]")
            if is_debug_mode():
                import traceback

                console.print(traceback.format_exc())
            return False

    def _find_revit_installations(self) -> list[Path]:
        """Find installed Revit versions on the system."""
        revit_dirs = []

        if platform.system() == "Windows":
            # Common Revit installation paths
            program_files = Path(get_program_files_path())
            program_files_x86 = Path(get_program_files_x86_path())

            base_paths = [program_files, program_files_x86]

            for base in base_paths:
                revit_base = base / "Autodesk"
                if not revit_base.exists():
                    continue

                # Look for Revit 20XX folders
                for year in range(2020, 2026):  # Revit 2020-2025
                    revit_dir = revit_base / f"Revit {year}"
                    if revit_dir.exists() and (revit_dir / "Revit.exe").exists():
                        revit_dirs.append(revit_dir)

        return revit_dirs

    def _select_revit_version(self, revit_dirs: list[Path]) -> Path | None:
        """Let user select Revit version for installation."""
        console.print("\n[blue]Multiple Revit installations found:[/blue]")

        for idx, revit_dir in enumerate(revit_dirs, 1):
            console.print(f"  {idx}. {revit_dir.name}")

        choice = Prompt.ask(
            "Select Revit version",
            choices=[str(i) for i in range(1, len(revit_dirs) + 1)],
        )
        return revit_dirs[int(choice) - 1]

    def _check_version_conflicts(
        self, revit_dir: Path, package_name: str, version: str
    ) -> bool:
        """Check for version conflicts with existing installations."""
        install_registry = self._get_install_registry_path(revit_dir)

        if not install_registry.exists():
            return True

        with open(install_registry) as f:
            registry = json.load(f)

        if package_name in registry:
            existing_version = registry[package_name]["version"]

            console.print(
                f"[yellow]Package {package_name} {existing_version} is already installed[/yellow]"
            )

            # Compare versions
            try:
                if packaging.version.parse(version) <= packaging.version.parse(
                    existing_version
                ):
                    console.print(
                        f"[yellow]Installed version {existing_version} is same or newer[/yellow]"
                    )
                    return Confirm.ask("Overwrite existing installation?")
                else:
                    console.print(
                        f"[blue]Upgrading from {existing_version} to {version}[/blue]"
                    )
                    return True
            except (packaging.version.InvalidVersion, ValueError, TypeError):
                return Confirm.ask("Continue with installation?")

        return True

    def _get_install_directory(self, revit_dir: Path, package_name: str) -> Path:
        """Get installation directory for package."""
        # Install to AddIns directory
        addins_dir = revit_dir / "AddIns" / "RevitPy" / "Packages" / package_name
        addins_dir.mkdir(parents=True, exist_ok=True)
        return addins_dir

    def _create_backup(self, install_dir: Path) -> Path:
        """Create backup of existing installation."""
        from datetime import datetime

        backup_base = install_dir.parent.parent / "Backups"
        backup_base.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = backup_base / f"{install_dir.name}_backup_{timestamp}"

        shutil.copytree(install_dir, backup_dir)
        return backup_dir

    def _deploy_package(self, source_dir: Path, install_dir: Path) -> list[str]:
        """Deploy package files to installation directory."""
        installed_files = []

        # Remove existing installation if present
        if install_dir.exists():
            shutil.rmtree(install_dir)

        install_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files
        for item in source_dir.rglob("*"):
            if item.is_file():
                relative_path = item.relative_to(source_dir)
                target_path = install_dir / relative_path

                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_path)

                installed_files.append(str(relative_path))

        return installed_files

    def _get_install_registry_path(self, revit_dir: Path) -> Path:
        """Get path to installation registry file."""
        registry_dir = revit_dir / "AddIns" / "RevitPy"
        registry_dir.mkdir(parents=True, exist_ok=True)
        return registry_dir / "installed_packages.json"

    def _track_installation(
        self,
        package_name: str,
        version: str,
        install_dir: Path,
        installed_files: list[str],
        manifest: dict,
    ):
        """Track installation for later uninstall."""
        from datetime import datetime

        # Go up 4 levels from install_dir to get to Revit root directory
        # install_dir: .../Revit 2024/AddIns/RevitPy/Packages/package-name
        # We need: .../Revit 2024
        registry_path = self._get_install_registry_path(
            install_dir.parent.parent.parent.parent
        )

        # Load existing registry
        if registry_path.exists():
            with open(registry_path) as f:
                registry = json.load(f)
        else:
            registry = {}

        # Add/update package entry
        registry[package_name] = {
            "version": version,
            "install_dir": str(install_dir),
            "installed_files": installed_files,
            "installed_at": datetime.now().isoformat(),
            "manifest": manifest,
        }

        # Save registry
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def _run_hooks(self, hooks: dict[str, str], install_dir: Path):
        """Run installation hooks."""
        import subprocess

        for hook_name, hook_script in hooks.items():
            try:
                script_path = install_dir / hook_script
                if script_path.exists():
                    console.print(f"[dim]Running hook: {hook_name}[/dim]")
                    subprocess.run(
                        ["python", str(script_path)], check=True, cwd=install_dir
                    )
            except Exception as e:
                console.print(f"[yellow]Warning: Hook {hook_name} failed: {e}[/yellow]")

    def _check_dependencies_before_uninstall(
        self, registry: dict, package_name: str
    ) -> bool:
        """Check if other packages depend on this package before uninstalling."""
        dependents = []

        for pkg_name, pkg_info in registry.items():
            if pkg_name == package_name:
                continue

            manifest = pkg_info.get("manifest", {})
            dependencies = manifest.get("dependencies", [])

            for dep in dependencies:
                dep_name = dep.get("name", "") if isinstance(dep, dict) else dep
                if dep_name.lower().replace("_", "-") == package_name.lower().replace(
                    "_", "-"
                ):
                    dependents.append(pkg_name)
                    break

        if dependents:
            console.print(
                f"[yellow]Warning: The following packages depend on {package_name}:[/yellow]"
            )
            for dep_pkg in dependents:
                console.print(
                    f"  [yellow]• {dep_pkg} ({registry[dep_pkg]['version']})[/yellow]"
                )

            return Confirm.ask("Uninstall anyway? (This may break dependent packages)")

        return True

    async def list_installed(self) -> list[dict]:
        """List installed packages."""
        # This would typically read from Revit installation directory
        # For now, return cached packages as a proxy
        await self.cache.get_cache_stats()

        with self.cache._db.connect() as conn:
            conn.row_factory = sqlite3.Row
            entries = conn.execute(
                """SELECT package_name, version, last_accessed, access_count
                   FROM cache_entries
                   ORDER BY last_accessed DESC"""
            ).fetchall()

            return [dict(entry) for entry in entries]

    async def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a package."""
        normalized_name = self.cache.normalize_name(package_name)

        try:
            console.print(f"[blue]Uninstalling {package_name}...[/blue]")

            # Find Revit installations
            revit_dirs = self._find_revit_installations()
            if not revit_dirs:
                console.print("[red]No Revit installations found[/red]")
                return False

            # Track success across all installations
            installations_found = 0

            for revit_dir in revit_dirs:
                registry_path = self._get_install_registry_path(revit_dir)

                if not registry_path.exists():
                    continue

                with open(registry_path) as f:
                    registry = json.load(f)

                if normalized_name not in registry:
                    continue

                installations_found += 1
                package_info = registry[normalized_name]

                console.print(f"\n[blue]Found installation in {revit_dir.name}[/blue]")
                console.print(f"[dim]Version: {package_info['version']}[/dim]")
                console.print(f"[dim]Location: {package_info['install_dir']}[/dim]")

                # Confirm uninstall
                if not Confirm.ask(f"Uninstall from {revit_dir.name}?"):
                    continue

                # Check for dependencies
                if not self._check_dependencies_before_uninstall(
                    registry, normalized_name
                ):
                    console.print(
                        "[yellow]Uninstall cancelled due to dependencies[/yellow]"
                    )
                    continue

                # Create backup before uninstall
                install_dir = Path(package_info["install_dir"])
                if install_dir.exists():
                    try:
                        backup_dir = self._create_backup(install_dir)
                        console.print(f"[dim]Backup created: {backup_dir}[/dim]")
                    except Exception as e:
                        console.print(f"[yellow]Warning: Backup failed: {e}[/yellow]")
                        if not Confirm.ask("Continue without backup?"):
                            continue

                # Run pre-uninstall hooks
                manifest = package_info.get("manifest", {})
                uninstall_hooks = manifest.get("uninstall_hooks", {})
                if uninstall_hooks:
                    console.print("[blue]Running pre-uninstall hooks...[/blue]")
                    self._run_hooks(uninstall_hooks, install_dir)

                # Remove files
                console.print("[blue]Removing package files...[/blue]")
                files_removed = 0
                for file_rel_path in package_info.get("installed_files", []):
                    file_path = install_dir / file_rel_path
                    try:
                        if file_path.exists():
                            file_path.unlink()
                            files_removed += 1
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Could not remove {file_path}: {e}[/yellow]"
                        )

                # Remove installation directory if empty
                try:
                    if install_dir.exists():
                        # Remove empty directories bottom-up
                        for dirpath, _dirnames, _filenames in os.walk(
                            install_dir, topdown=False
                        ):
                            dir_to_check = Path(dirpath)
                            if not any(dir_to_check.iterdir()):
                                dir_to_check.rmdir()

                        # Remove base directory if empty
                        if install_dir.exists() and not any(install_dir.iterdir()):
                            install_dir.rmdir()
                            console.print(
                                f"[dim]Removed empty directory: {install_dir}[/dim]"
                            )
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not remove directory: {e}[/yellow]"
                    )

                # Update registry
                del registry[normalized_name]
                with open(registry_path, "w") as f:
                    json.dump(registry, f, indent=2)

                console.print(
                    f"[green]✓ Successfully uninstalled from {revit_dir.name}[/green]"
                )
                console.print(f"[dim]Files removed: {files_removed}[/dim]")

            # Remove from cache
            with sqlite3.connect(self.cache.db_path) as conn:
                result = conn.execute(
                    "SELECT file_path FROM cache_entries WHERE package_name = ?",
                    (normalized_name,),
                ).fetchall()

                for row in result:
                    file_path = Path(row[0])
                    if file_path.exists():
                        file_path.unlink()

                conn.execute(
                    "DELETE FROM cache_entries WHERE package_name = ?",
                    (normalized_name,),
                )

            console.print(f"[green]Successfully uninstalled {package_name}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Uninstallation failed: {e}[/red]")
            return False

    async def sync_registry(self) -> bool:
        """Sync with remote registry for offline use."""
        with console.status("[cyan]Syncing with registry..."):
            success = await self.cache.sync_metadata()

        if success:
            console.print("[green]Registry sync completed[/green]")
        else:
            console.print("[red]Registry sync failed[/red]")

        return success

    async def cache_stats(self) -> dict:
        """Get cache statistics."""
        return await self.cache.get_cache_stats()

    async def cleanup_cache(
        self, max_size_mb: int = 500, max_age_days: int = 30
    ) -> dict:
        """Clean up package cache."""
        with console.status("[cyan]Cleaning up cache..."):
            stats = await self.cache.cleanup_cache(max_size_mb, max_age_days)

        console.print("[green]Cache cleanup completed:[/green]")
        console.print(f"  • Removed {stats['removed_files']} files")
        console.print(f"  • Freed {stats['freed_bytes'] / 1024 / 1024:.1f} MB")
        console.print(f"  • Kept {stats['kept_files']} files")

        return stats


# CLI Commands using Click
@click.group()
@click.option("--registry-url", default="http://localhost:8000", help="Registry URL")
@click.option("--cache-dir", help="Cache directory path")
@click.pass_context
def cli(ctx, registry_url, cache_dir):
    """RevitPy Desktop Package Manager CLI."""
    ctx.ensure_object(dict)
    ctx.obj["cli"] = DesktopCLI(registry_url, cache_dir)


@cli.command()
@click.argument("query")
@click.option("--revit-version", help="Filter by Revit version")
@click.option("--package-type", help="Filter by package type")
@click.option("--offline", is_flag=True, help="Search offline only")
@click.pass_context
def search(ctx, query, revit_version, package_type, offline):
    """Search for packages."""

    async def _search():
        cli_obj = ctx.obj["cli"]
        try:
            results = await cli_obj.search_packages(
                query, revit_version, package_type, offline
            )

            if not results:
                console.print(f"[yellow]No packages found for '{query}'[/yellow]")
                return

            table = Table(title=f"Search Results for '{query}'")
            table.add_column("Package", style="cyan", no_wrap=True)
            table.add_column("Version", style="green")
            table.add_column("Summary", style="white")
            table.add_column("Type", style="blue")
            table.add_column("Downloads", style="magenta", justify="right")

            for pkg in results:
                table.add_row(
                    pkg.get("name", ""),
                    pkg.get("latest_version", ""),
                    (
                        pkg.get("summary", "")[:50] + "..."
                        if len(pkg.get("summary", "")) > 50
                        else pkg.get("summary", "")
                    ),
                    pkg.get("package_type", "addon"),
                    str(pkg.get("download_count", 0)),
                )

            console.print(table)

        finally:
            await cli_obj.cleanup()

    asyncio.run(_search())


@cli.command()
@click.argument("package_name")
@click.option("--version", help="Specific version to install")
@click.option("--revit-version", help="Target Revit version")
@click.option("--force", is_flag=True, help="Force reinstall")
@click.option("--offline", is_flag=True, help="Offline installation only")
@click.pass_context
def install(ctx, package_name, version, revit_version, force, offline):
    """Install a package."""

    async def _install():
        cli_obj = ctx.obj["cli"]
        try:
            success = await cli_obj.install_package(
                package_name, version, revit_version, force, offline
            )
            sys.exit(0 if success else 1)
        finally:
            await cli_obj.cleanup()

    asyncio.run(_install())


@cli.command()
@click.argument("package_name")
@click.pass_context
def uninstall(ctx, package_name):
    """Uninstall a package."""

    async def _uninstall():
        cli_obj = ctx.obj["cli"]
        try:
            success = await cli_obj.uninstall_package(package_name)
            sys.exit(0 if success else 1)
        finally:
            await cli_obj.cleanup()

    asyncio.run(_uninstall())


@cli.command()
@click.pass_context
def list(ctx):
    """List installed packages."""

    async def _list():
        cli_obj = ctx.obj["cli"]
        try:
            packages = await cli_obj.list_installed()

            if not packages:
                console.print("[yellow]No packages installed[/yellow]")
                return

            table = Table(title="Installed Packages")
            table.add_column("Package", style="cyan")
            table.add_column("Version", style="green")
            table.add_column("Last Used", style="blue")
            table.add_column("Usage Count", style="magenta", justify="right")

            for pkg in packages:
                table.add_row(
                    pkg["package_name"],
                    pkg["version"],
                    pkg.get("last_accessed", "Unknown"),
                    str(pkg.get("access_count", 0)),
                )

            console.print(table)

        finally:
            await cli_obj.cleanup()

    asyncio.run(_list())


@cli.command()
@click.pass_context
def sync(ctx):
    """Sync with registry for offline use."""

    async def _sync():
        cli_obj = ctx.obj["cli"]
        try:
            await cli_obj.sync_registry()
        finally:
            await cli_obj.cleanup()

    asyncio.run(_sync())


@cli.command()
@click.option("--max-size", default=500, help="Maximum cache size in MB")
@click.option("--max-age", default=30, help="Maximum age in days")
@click.pass_context
def cleanup(ctx, max_size, max_age):
    """Clean up package cache."""

    async def _cleanup():
        cli_obj = ctx.obj["cli"]
        try:
            await cli_obj.cleanup_cache(max_size, max_age)
        finally:
            await cli_obj.cleanup()

    asyncio.run(_cleanup())


@cli.command()
@click.pass_context
def stats(ctx):
    """Show cache statistics."""

    async def _stats():
        cli_obj = ctx.obj["cli"]
        try:
            stats = await cli_obj.cache_stats()

            panel = Panel.fit(
                f"""[cyan]Cache Statistics[/cyan]

[green]Total Packages:[/green] {stats['total_packages']}
[green]Total Size:[/green] {stats['total_size_mb']} MB
[green]Total Downloads:[/green] {stats['total_accesses']}
[green]Average Usage:[/green] {stats['avg_accesses']} per package
[green]Recent Activity:[/green] {stats['recent_accesses']} packages used in last 7 days
[green]Cache Directory:[/green] {stats['cache_directory']}""",
                title="RevitPy Package Cache",
            )

            console.print(panel)

        finally:
            await cli_obj.cleanup()

    asyncio.run(_stats())


if __name__ == "__main__":
    cli()
