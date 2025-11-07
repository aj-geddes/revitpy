"""Desktop-optimized CLI for RevitPy package management.

Integrates with VS Code and provides fast operations for desktop development.
"""

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import click
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, Prompt
from rich import print as rprint
from rich.panel import Panel
import packaging.version

from ..cache_manager import DesktopPackageCache, CacheEntry
from ...security.desktop_scanner import SecurityScanner


console = Console()


class DesktopCLI:
    """Desktop-optimized CLI for package management."""
    
    def __init__(self, registry_url: str = "http://localhost:8000", cache_dir: Optional[str] = None):
        self.registry_url = registry_url
        self.cache = DesktopPackageCache(cache_dir, registry_url)
        self.security_scanner = SecurityScanner()
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.cache.close()
    
    async def search_packages(
        self, 
        query: str, 
        revit_version: Optional[str] = None,
        package_type: Optional[str] = None,
        offline: bool = False
    ) -> List[Dict]:
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
            
            async with session.get(f"{self.registry_url}/api/packages/search", params=params) as response:
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
        version: Optional[str] = None,
        revit_version: Optional[str] = None,
        force: bool = False,
        offline: bool = False
    ) -> bool:
        """Install a package with desktop optimizations."""
        
        # Normalize package name
        normalized_name = self.cache.normalize_name(package_name)
        
        # Determine version to install
        if not version:
            version = await self._get_latest_compatible_version(normalized_name, revit_version, offline)
            if not version:
                console.print(f"[red]No compatible version found for {package_name}[/red]")
                return False
        
        # Check if already cached and compatible
        if not force:
            cached = await self.cache.get_cached_package(normalized_name, version)
            if cached:
                console.print(f"[green]Package {package_name} {version} is already cached[/green]")
                
                # Check compatibility
                if revit_version and not await self._check_revit_compatibility(cached, revit_version):
                    console.print(f"[yellow]Warning: Package may not be compatible with Revit {revit_version}[/yellow]")
                    if not Confirm.ask("Continue anyway?"):
                        return False
                
                return await self._install_from_cache(cached)
        
        # Download and cache the package
        with console.status(f"[cyan]Downloading {package_name} {version}..."):
            try:
                cache_entry = await self.cache.get_package(normalized_name, version, not offline)
                if not cache_entry:
                    console.print(f"[red]Package {package_name} {version} not found[/red]")
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
        self, 
        package_name: str, 
        revit_version: Optional[str],
        offline: bool = False
    ) -> Optional[str]:
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
            async with session.get(f"{self.registry_url}/api/packages/{package_name}") as response:
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
                        
                        if min_revit and packaging.version.parse(revit_version) < packaging.version.parse(min_revit):
                            continue
                        
                        if max_revit and packaging.version.parse(revit_version) > packaging.version.parse(max_revit):
                            continue
                        
                        compatible_versions.append(version_info)
                    
                    versions = compatible_versions
                
                # Return latest version
                return versions[0]["version"] if versions else None
                
        except Exception:
            return None
    
    async def _check_revit_compatibility(self, cache_entry: CacheEntry, revit_version: str) -> bool:
        """Check if cached package is compatible with Revit version."""
        metadata = cache_entry.metadata
        
        # Check version compatibility from metadata
        for version_info in metadata.get("versions", []):
            if version_info["version"] == cache_entry.version:
                min_revit = version_info.get("min_revit_version")
                max_revit = version_info.get("max_revit_version")
                
                if min_revit and packaging.version.parse(revit_version) < packaging.version.parse(min_revit):
                    return False
                
                if max_revit and packaging.version.parse(revit_version) > packaging.version.parse(max_revit):
                    return False
                
                return True
        
        return True  # Assume compatible if no version info
    
    async def _security_check(self, cache_entry: CacheEntry) -> bool:
        """Perform security check on cached package."""
        try:
            scan_result = await self.security_scanner.scan_package_file(Path(cache_entry.file_path))
            
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
            import zipfile
            import shutil
            import platform

            # Determine installation directory based on OS
            if platform.system() == "Windows":
                # Windows: %APPDATA%\RevitPy\packages
                install_base = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'RevitPy' / 'packages'
            elif platform.system() == "Darwin":
                # macOS: ~/Library/Application Support/RevitPy/packages
                install_base = Path.home() / 'Library' / 'Application Support' / 'RevitPy' / 'packages'
            else:
                # Linux: ~/.local/share/RevitPy/packages
                install_base = Path.home() / '.local' / 'share' / 'RevitPy' / 'packages'

            install_base.mkdir(parents=True, exist_ok=True)

            # Create package installation directory
            package_dir = install_base / cache_entry.package_name / cache_entry.version

            # Remove existing installation if present
            if package_dir.exists():
                shutil.rmtree(package_dir)

            package_dir.mkdir(parents=True, exist_ok=True)

            # Extract package based on file type
            source_file = Path(cache_entry.file_path)

            if source_file.suffix == '.zip' or source_file.name.endswith('.rpyx'):
                # Extract ZIP/RPYX file
                with zipfile.ZipFile(source_file, 'r') as zf:
                    zf.extractall(package_dir)
            elif source_file.name.endswith('.tar.gz'):
                # Extract tar.gz file
                import tarfile
                with tarfile.open(source_file, 'r:gz') as tf:
                    tf.extractall(package_dir)
            elif source_file.suffix == '.whl':
                # Extract wheel file
                with zipfile.ZipFile(source_file, 'r') as zf:
                    zf.extractall(package_dir)
            else:
                # Unknown format, just copy the file
                shutil.copy2(source_file, package_dir / source_file.name)

            # Create or update package registry file
            registry_file = install_base / 'installed_packages.json'
            registry_data = {}

            if registry_file.exists():
                with open(registry_file, 'r') as f:
                    registry_data = json.load(f)

            # Add package to registry
            if cache_entry.package_name not in registry_data:
                registry_data[cache_entry.package_name] = {}

            registry_data[cache_entry.package_name][cache_entry.version] = {
                'installed_at': datetime.now().isoformat(),
                'install_path': str(package_dir),
                'metadata': cache_entry.metadata
            }

            # Write updated registry
            with open(registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)

            console.print(f"[green]✅ Successfully installed {cache_entry.package_name} {cache_entry.version}[/green]")
            console.print(f"[dim]Installation directory: {package_dir}[/dim]")
            return True

        except Exception as e:
            console.print(f"[red]Installation failed: {e}[/red]")
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()
            return False
    
    async def list_installed(self) -> List[Dict]:
        """List installed packages from the installation registry."""
        import platform

        # Determine installation directory based on OS
        if platform.system() == "Windows":
            install_base = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'RevitPy' / 'packages'
        elif platform.system() == "Darwin":
            install_base = Path.home() / 'Library' / 'Application Support' / 'RevitPy' / 'packages'
        else:
            install_base = Path.home() / '.local' / 'share' / 'RevitPy' / 'packages'

        registry_file = install_base / 'installed_packages.json'

        if not registry_file.exists():
            return []

        try:
            with open(registry_file, 'r') as f:
                registry_data = json.load(f)

            packages = []
            for package_name, versions in registry_data.items():
                for version, info in versions.items():
                    packages.append({
                        'package_name': package_name,
                        'version': version,
                        'installed_at': info.get('installed_at', 'Unknown'),
                        'install_path': info.get('install_path', ''),
                    })

            # Sort by installation date (most recent first)
            packages.sort(key=lambda x: x.get('installed_at', ''), reverse=True)
            return packages

        except Exception as e:
            console.print(f"[yellow]Warning: Failed to read installation registry: {e}[/yellow]")
            return []
    
    async def uninstall_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Uninstall a package (or specific version)."""
        import platform
        import shutil

        normalized_name = self.cache.normalize_name(package_name)

        # Determine installation directory based on OS
        if platform.system() == "Windows":
            install_base = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'RevitPy' / 'packages'
        elif platform.system() == "Darwin":
            install_base = Path.home() / 'Library' / 'Application Support' / 'RevitPy' / 'packages'
        else:
            install_base = Path.home() / '.local' / 'share' / 'RevitPy' / 'packages'

        registry_file = install_base / 'installed_packages.json'

        if not registry_file.exists():
            console.print(f"[yellow]No installed packages found[/yellow]")
            return False

        try:
            # Read installation registry
            with open(registry_file, 'r') as f:
                registry_data = json.load(f)

            if normalized_name not in registry_data:
                console.print(f"[yellow]Package {package_name} is not installed[/yellow]")
                return False

            versions_to_remove = []
            if version:
                # Uninstall specific version
                if version in registry_data[normalized_name]:
                    versions_to_remove.append(version)
                else:
                    console.print(f"[yellow]Version {version} of {package_name} is not installed[/yellow]")
                    return False
            else:
                # Uninstall all versions
                versions_to_remove = list(registry_data[normalized_name].keys())

            # Remove package files for each version
            for ver in versions_to_remove:
                version_info = registry_data[normalized_name][ver]
                install_path = Path(version_info['install_path'])

                if install_path.exists():
                    console.print(f"[cyan]Removing {package_name} {ver} from {install_path}[/cyan]")
                    shutil.rmtree(install_path)
                else:
                    console.print(f"[yellow]Warning: Installation directory not found: {install_path}[/yellow]")

                # Remove from registry
                del registry_data[normalized_name][ver]

            # If no versions left, remove package entry
            if not registry_data[normalized_name]:
                del registry_data[normalized_name]

            # Write updated registry
            with open(registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)

            # Also remove from cache
            try:
                with sqlite3.connect(self.cache.db_path) as conn:
                    if version:
                        conn.execute(
                            "DELETE FROM cache_entries WHERE package_name = ? AND version = ?",
                            (normalized_name, version)
                        )
                    else:
                        conn.execute(
                            "DELETE FROM cache_entries WHERE package_name = ?",
                            (normalized_name,)
                        )
            except Exception:
                pass  # Cache removal is optional

            if len(versions_to_remove) == 1:
                console.print(f"[green]✅ Successfully uninstalled {package_name} {versions_to_remove[0]}[/green]")
            else:
                console.print(f"[green]✅ Successfully uninstalled {package_name} (all {len(versions_to_remove)} versions)[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Uninstallation failed: {e}[/red]")
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()
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
    
    async def cache_stats(self) -> Dict:
        """Get cache statistics."""
        return await self.cache.get_cache_stats()
    
    async def cleanup_cache(self, max_size_mb: int = 500, max_age_days: int = 30) -> Dict:
        """Clean up package cache."""
        with console.status("[cyan]Cleaning up cache..."):
            stats = await self.cache.cleanup_cache(max_size_mb, max_age_days)
        
        console.print(f"[green]Cache cleanup completed:[/green]")
        console.print(f"  • Removed {stats['removed_files']} files")
        console.print(f"  • Freed {stats['freed_bytes'] / 1024 / 1024:.1f} MB")
        console.print(f"  • Kept {stats['kept_files']} files")
        
        return stats


# CLI Commands using Click
@click.group()
@click.option('--registry-url', default="http://localhost:8000", help="Registry URL")
@click.option('--cache-dir', help="Cache directory path")
@click.pass_context
def cli(ctx, registry_url, cache_dir):
    """RevitPy Desktop Package Manager CLI."""
    ctx.ensure_object(dict)
    ctx.obj['cli'] = DesktopCLI(registry_url, cache_dir)


@cli.command()
@click.argument('query')
@click.option('--revit-version', help="Filter by Revit version")
@click.option('--package-type', help="Filter by package type")
@click.option('--offline', is_flag=True, help="Search offline only")
@click.pass_context
def search(ctx, query, revit_version, package_type, offline):
    """Search for packages."""
    async def _search():
        cli_obj = ctx.obj['cli']
        try:
            results = await cli_obj.search_packages(query, revit_version, package_type, offline)
            
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
                    pkg.get("summary", "")[:50] + "..." if len(pkg.get("summary", "")) > 50 else pkg.get("summary", ""),
                    pkg.get("package_type", "addon"),
                    str(pkg.get("download_count", 0))
                )
            
            console.print(table)
            
        finally:
            await cli_obj.cleanup()
    
    asyncio.run(_search())


@cli.command()
@click.argument('package_name')
@click.option('--version', help="Specific version to install")
@click.option('--revit-version', help="Target Revit version")
@click.option('--force', is_flag=True, help="Force reinstall")
@click.option('--offline', is_flag=True, help="Offline installation only")
@click.pass_context
def install(ctx, package_name, version, revit_version, force, offline):
    """Install a package."""
    async def _install():
        cli_obj = ctx.obj['cli']
        try:
            success = await cli_obj.install_package(
                package_name, version, revit_version, force, offline
            )
            sys.exit(0 if success else 1)
        finally:
            await cli_obj.cleanup()
    
    asyncio.run(_install())


@cli.command()
@click.argument('package_name')
@click.pass_context
def uninstall(ctx, package_name):
    """Uninstall a package."""
    async def _uninstall():
        cli_obj = ctx.obj['cli']
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
        cli_obj = ctx.obj['cli']
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
                    str(pkg.get("access_count", 0))
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
        cli_obj = ctx.obj['cli']
        try:
            await cli_obj.sync_registry()
        finally:
            await cli_obj.cleanup()
    
    asyncio.run(_sync())


@cli.command()
@click.option('--max-size', default=500, help="Maximum cache size in MB")
@click.option('--max-age', default=30, help="Maximum age in days")
@click.pass_context
def cleanup(ctx, max_size, max_age):
    """Clean up package cache."""
    async def _cleanup():
        cli_obj = ctx.obj['cli']
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
        cli_obj = ctx.obj['cli']
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
                title="RevitPy Package Cache"
            )
            
            console.print(panel)
            
        finally:
            await cli_obj.cleanup()
    
    asyncio.run(_stats())


if __name__ == "__main__":
    cli()