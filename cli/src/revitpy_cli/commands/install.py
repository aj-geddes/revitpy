"""Package installation and dependency management commands."""

import builtins
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import typer
from packaging import requirements, version
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm
from rich.table import Table
from rich.tree import Tree

from ..core.config import get_config
from ..core.exceptions import CommandError, InstallError
from ..core.logging import get_logger, log_command_complete, log_command_start

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="install",
    help="Install and manage RevitPy packages",
    rich_markup_mode="rich",
)


@app.command()
def package(
    package_specs: list[str] = typer.Argument(
        ..., help="Package specifications (name[==version])"
    ),
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    upgrade: bool = typer.Option(
        False, "--upgrade", "-U", help="Upgrade packages to latest versions"
    ),
    pre: bool = typer.Option(False, "--pre", help="Include pre-release versions"),
    no_deps: bool = typer.Option(False, "--no-deps", help="Don't install dependencies"),
    force_reinstall: bool = typer.Option(
        False, "--force-reinstall", help="Force reinstall even if satisfied"
    ),
    user: bool = typer.Option(False, "--user", help="Install to user site-packages"),
    target: str | None = typer.Option(
        None, "--target", help="Install to specific directory"
    ),
    editable: bool = typer.Option(
        False, "--editable", "-e", help="Install in editable mode (for local paths)"
    ),
    requirements_file: str | None = typer.Option(
        None, "--requirement", "-r", help="Install from requirements file"
    ),
) -> None:
    """Install RevitPy packages from registry or local sources.

    Examples:
        revitpy install geometry-utils
        revitpy install "geometry-utils>=1.0.0" "ui-toolkit==2.1.0"
        revitpy install --upgrade geometry-utils
        revitpy install --editable ./local-package
        revitpy install --requirement requirements.txt
    """
    start_time = time.time()
    log_command_start(
        "install package",
        {
            "package_specs": package_specs,
            "registry": registry,
            "upgrade": upgrade,
            "pre": pre,
            "no_deps": no_deps,
            "force_reinstall": force_reinstall,
            "user": user,
            "target": target,
            "editable": editable,
            "requirements_file": requirements_file,
        },
    )

    config = get_config()

    try:
        installer = PackageInstaller(
            registry_url=registry or config.install.registry_url,
            config=config,
        )

        console.print("[bold blue]📦 Installing packages...[/bold blue]")

        # Collect packages to install
        packages_to_install = package_specs.copy()

        # Add packages from requirements file
        if requirements_file:
            req_packages = installer.parse_requirements_file(Path(requirements_file))
            packages_to_install.extend(req_packages)

        if not packages_to_install:
            raise CommandError("install package", "No packages specified")

        # Install packages
        install_result = installer.install_packages(
            packages=packages_to_install,
            upgrade=upgrade,
            include_pre=pre,
            install_deps=not no_deps,
            force_reinstall=force_reinstall,
            user_install=user,
            target_dir=target,
            editable=editable,
        )

        # Success message
        console.print()
        console.print(
            f"[bold green]✓[/bold green] Successfully installed {len(install_result['installed'])} packages"
        )

        # Show installed packages
        if install_result["installed"]:
            installer.show_install_summary(install_result)

        # Show any warnings
        if install_result.get("warnings"):
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in install_result["warnings"]:
                console.print(f"  ⚠️  {warning}")

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install package", duration)


@app.command()
def uninstall(
    packages: list[str] = typer.Argument(..., help="Package names to uninstall"),
    confirm: bool = typer.Option(
        True, "--confirm/--no-confirm", help="Confirm before uninstalling"
    ),
    user: bool = typer.Option(
        False, "--user", help="Uninstall from user site-packages"
    ),
) -> None:
    """Uninstall RevitPy packages.

    Examples:
        revitpy install uninstall geometry-utils
        revitpy install uninstall geometry-utils ui-toolkit
        revitpy install uninstall --no-confirm old-package
    """
    start_time = time.time()
    log_command_start(
        "install uninstall",
        {
            "packages": packages,
            "confirm": confirm,
            "user": user,
        },
    )

    config = get_config()

    try:
        uninstaller = PackageUninstaller(config)

        console.print("[bold red]🗑️  Uninstalling packages...[/bold red]")

        # Check which packages are installed
        installed_packages = uninstaller.check_installed_packages(
            packages, user_install=user
        )

        if not installed_packages:
            console.print("[yellow]No matching packages found to uninstall[/yellow]")
            return

        # Show packages to be uninstalled
        console.print("\nPackages to uninstall:")
        for pkg_info in installed_packages:
            console.print(f"  📦 [cyan]{pkg_info['name']}[/cyan] {pkg_info['version']}")

        # Confirm uninstallation
        if confirm:
            if not Confirm.ask(
                f"\nProceed with uninstalling {len(installed_packages)} packages?"
            ):
                console.print("[yellow]Uninstallation cancelled[/yellow]")
                return

        # Uninstall packages
        uninstall_result = uninstaller.uninstall_packages(
            packages=packages,
            user_install=user,
        )

        # Success message
        console.print()
        console.print(
            f"[bold green]✓[/bold green] Successfully uninstalled {len(uninstall_result['uninstalled'])} packages"
        )

        # Show uninstalled packages
        for pkg_name in uninstall_result["uninstalled"]:
            console.print(f"  🗑️  [dim]{pkg_name}[/dim]")

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install uninstall", duration)


@app.command()
def list(
    format: str = typer.Option(
        "table", "--format", help="Output format (table, json, freeze)"
    ),
    outdated: bool = typer.Option(
        False, "--outdated", help="List outdated packages only"
    ),
    user: bool = typer.Option(False, "--user", help="List user site-packages only"),
    show_dependencies: bool = typer.Option(
        False, "--show-dependencies", help="Show dependency tree"
    ),
) -> None:
    """List installed RevitPy packages.

    Examples:
        revitpy install list
        revitpy install list --outdated
        revitpy install list --format json
        revitpy install list --show-dependencies
    """
    start_time = time.time()
    log_command_start(
        "install list",
        {
            "format": format,
            "outdated": outdated,
            "user": user,
            "show_dependencies": show_dependencies,
        },
    )

    config = get_config()

    try:
        lister = PackageLister(
            registry_url=config.install.registry_url,
            config=config,
        )

        console.print("[bold blue]📋 Listing installed packages...[/bold blue]")

        # Get installed packages
        packages = lister.get_installed_packages(
            user_only=user,
            check_outdated=outdated,
        )

        if not packages:
            console.print("[yellow]No packages installed[/yellow]")
            return

        # Filter outdated if requested
        if outdated:
            packages = [pkg for pkg in packages if pkg.get("outdated", False)]
            if not packages:
                console.print("[green]All packages are up to date[/green]")
                return

        # Display packages
        if format == "table":
            lister.display_table(packages, show_dependencies)
        elif format == "json":
            lister.display_json(packages)
        elif format == "freeze":
            lister.display_freeze(packages)
        else:
            raise CommandError("install list", f"Unknown format: {format}")

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install list", duration)


@app.command()
def show(
    package_name: str = typer.Argument(
        ..., help="Package name to show information for"
    ),
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
) -> None:
    """Show detailed information about a package.

    Examples:
        revitpy install show geometry-utils
        revitpy install show --registry https://my-registry.com geometry-utils
    """
    start_time = time.time()
    log_command_start(
        "install show",
        {
            "package_name": package_name,
            "registry": registry,
        },
    )

    config = get_config()

    try:
        info_displayer = PackageInfoDisplayer(
            registry_url=registry or config.install.registry_url,
            config=config,
        )

        console.print(f"[bold blue]ℹ️  Package information: {package_name}[/bold blue]")
        console.print()

        # Get package information
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching package information...", total=None)

            package_info = info_displayer.get_package_info(package_name)

            progress.update(task, completed=True)

        # Display information
        info_displayer.display_package_info(package_info)

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install show", duration)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    limit: int = typer.Option(20, "--limit", help="Maximum number of results"),
) -> None:
    """Search for packages in the registry.

    Examples:
        revitpy install search geometry
        revitpy install search ui --limit 10
        revitpy install search --registry https://my-registry.com tools
    """
    start_time = time.time()
    log_command_start(
        "install search",
        {
            "query": query,
            "registry": registry,
            "limit": limit,
        },
    )

    config = get_config()

    try:
        searcher = PackageSearcher(
            registry_url=registry or config.install.registry_url,
            config=config,
        )

        console.print(f"[bold blue]🔍 Searching for: {query}[/bold blue]")
        console.print()

        # Search packages
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Searching packages...", total=None)

            search_results = searcher.search_packages(query, limit=limit)

            progress.update(task, completed=True)

        # Display results
        if search_results:
            searcher.display_search_results(search_results)
        else:
            console.print(f"[yellow]No packages found matching '{query}'[/yellow]")

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install search", duration)


@app.command()
def update(
    packages: builtins.list[str] | None = typer.Argument(
        None, help="Specific packages to update (default: all)"
    ),
    pre: bool = typer.Option(False, "--pre", help="Include pre-release versions"),
    user: bool = typer.Option(False, "--user", help="Update user site-packages"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be updated"),
) -> None:
    """Update installed packages to latest versions.

    Examples:
        revitpy install update
        revitpy install update geometry-utils ui-toolkit
        revitpy install update --pre --dry-run
    """
    start_time = time.time()
    log_command_start(
        "install update",
        {
            "packages": packages,
            "pre": pre,
            "user": user,
            "dry_run": dry_run,
        },
    )

    config = get_config()

    try:
        updater = PackageUpdater(
            registry_url=config.install.registry_url,
            config=config,
        )

        console.print("[bold blue]🔄 Checking for updates...[/bold blue]")

        # Find packages to update
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Checking for updates...", total=None)

            updates_available = updater.check_updates(
                specific_packages=packages,
                user_only=user,
                include_pre=pre,
            )

            progress.update(task, completed=True)

        if not updates_available:
            console.print("[green]All packages are up to date[/green]")
            return

        # Show available updates
        updater.display_available_updates(updates_available)

        if dry_run:
            console.print("\n[yellow]Dry run - no packages were updated[/yellow]")
            return

        # Confirm updates
        if not Confirm.ask(f"\nUpdate {len(updates_available)} packages?"):
            console.print("[yellow]Update cancelled[/yellow]")
            return

        # Perform updates
        update_result = updater.update_packages(
            updates=updates_available,
            user_install=user,
        )

        # Success message
        console.print()
        console.print(
            f"[bold green]✓[/bold green] Successfully updated {len(update_result['updated'])} packages"
        )

        # Show updated packages
        for pkg_info in update_result["updated"]:
            console.print(
                f"  📦 [cyan]{pkg_info['name']}[/cyan] {pkg_info['old_version']} → {pkg_info['new_version']}"
            )

    except Exception as e:
        raise InstallError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("install update", duration)


class PackageInstaller:
    """Handles package installation from registries."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize package installer.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=30.0)

        # Dependency resolver
        self.resolver = DependencyResolver(registry_url, config)

    def parse_requirements_file(self, requirements_file: Path) -> builtins.list[str]:
        """Parse requirements file and return package specifications.

        Args:
            requirements_file: Path to requirements file

        Returns:
            List of package specifications
        """
        if not requirements_file.exists():
            raise CommandError(
                "install package", f"Requirements file not found: {requirements_file}"
            )

        packages = []
        with open(requirements_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    packages.append(line)

        return packages

    def install_packages(
        self,
        packages: builtins.list[str],
        upgrade: bool = False,
        include_pre: bool = False,
        install_deps: bool = True,
        force_reinstall: bool = False,
        user_install: bool = False,
        target_dir: str | None = None,
        editable: bool = False,
    ) -> dict[str, Any]:
        """Install packages.

        Args:
            packages: Package specifications to install
            upgrade: Upgrade existing packages
            include_pre: Include pre-release versions
            install_deps: Install dependencies
            force_reinstall: Force reinstall
            user_install: Install to user site-packages
            target_dir: Target directory for installation
            editable: Install in editable mode

        Returns:
            Installation result
        """
        installed_packages = []
        warnings = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Step 1: Parse and validate package specifications
            task1 = progress.add_task("Parsing package specifications...", total=None)
            parsed_packages = self._parse_package_specs(packages)
            progress.update(task1, completed=True)

            # Step 2: Resolve dependencies
            if install_deps:
                task2 = progress.add_task("Resolving dependencies...", total=None)
                resolved_deps = self.resolver.resolve_dependencies(
                    parsed_packages,
                    include_pre=include_pre,
                )
                progress.update(task2, completed=True)
                all_packages = resolved_deps
            else:
                all_packages = parsed_packages

            # Step 3: Check for conflicts
            task3 = progress.add_task("Checking for conflicts...", total=None)
            conflicts = self._check_conflicts(all_packages, force_reinstall)
            if conflicts and not force_reinstall:
                warnings.extend(
                    [f"Conflict detected: {conflict}" for conflict in conflicts]
                )
            progress.update(task3, completed=True)

            # Step 4: Download packages
            task4 = progress.add_task(
                "Downloading packages...", total=len(all_packages)
            )
            downloaded_packages = []
            for _i, pkg_spec in enumerate(all_packages):
                if not self._is_local_path(pkg_spec["name"]):
                    download_info = self._download_package(pkg_spec)
                    downloaded_packages.append(download_info)
                else:
                    downloaded_packages.append(
                        {
                            "name": pkg_spec["name"],
                            "path": pkg_spec["name"],
                            "local": True,
                        }
                    )
                progress.update(task4, advance=1)

            # Step 5: Install packages
            task5 = progress.add_task(
                "Installing packages...", total=len(downloaded_packages)
            )
            for _i, pkg_info in enumerate(downloaded_packages):
                try:
                    self._install_single_package(
                        pkg_info,
                        user_install=user_install,
                        target_dir=target_dir,
                        editable=editable and pkg_info.get("local", False),
                    )
                    installed_packages.append(pkg_info["name"])
                except Exception as e:
                    warnings.append(f"Failed to install {pkg_info['name']}: {e}")

                progress.update(task5, advance=1)

        return {
            "installed": installed_packages,
            "warnings": warnings,
        }

    def _parse_package_specs(
        self, packages: builtins.list[str]
    ) -> builtins.list[dict[str, Any]]:
        """Parse package specifications.

        Args:
            packages: Package specification strings

        Returns:
            List of parsed package specifications
        """
        parsed = []

        for pkg_spec in packages:
            if self._is_local_path(pkg_spec):
                parsed.append(
                    {
                        "name": pkg_spec,
                        "version": None,
                        "local": True,
                    }
                )
            else:
                try:
                    req = requirements.Requirement(pkg_spec)
                    parsed.append(
                        {
                            "name": req.name,
                            "version": str(req.specifier) if req.specifier else None,
                            "extras": list(req.extras),
                            "local": False,
                        }
                    )
                except Exception as e:
                    raise InstallError(
                        f"Invalid package specification '{pkg_spec}': {e}"
                    )

        return parsed

    def _is_local_path(self, package_spec: str) -> bool:
        """Check if package spec is a local path.

        Args:
            package_spec: Package specification

        Returns:
            True if local path
        """
        return (
            package_spec.startswith("./")
            or package_spec.startswith("../")
            or package_spec.startswith("/")
            or Path(package_spec).exists()
        )

    def _check_conflicts(
        self, packages: builtins.list[dict[str, Any]], force: bool = False
    ) -> builtins.list[str]:
        """Check for installation conflicts.

        Args:
            packages: Package specifications
            force: Force installation despite conflicts

        Returns:
            List of conflict descriptions
        """
        conflicts = []

        # Check for duplicate packages with different versions
        name_versions = {}
        for pkg in packages:
            name = pkg["name"]
            version_spec = pkg.get("version")

            if name in name_versions:
                existing_version = name_versions[name]
                if version_spec != existing_version:
                    conflicts.append(f"{name}: {existing_version} vs {version_spec}")
            else:
                name_versions[name] = version_spec

        return conflicts

    def _download_package(self, pkg_spec: dict[str, Any]) -> dict[str, Any]:
        """Download package from registry.

        Args:
            pkg_spec: Package specification

        Returns:
            Download information
        """
        name = pkg_spec["name"]
        version_spec = pkg_spec.get("version")

        try:
            # Query registry for package information
            params = {}
            if version_spec:
                params["version"] = version_spec

            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{name}/download",
                params=params,
            )

            if response.status_code == 200:
                download_info = response.json()

                # Download package file
                package_response = self.client.get(download_info["download_url"])

                if package_response.status_code == 200:
                    # Save to temporary file
                    temp_dir = Path(tempfile.mkdtemp())
                    package_file = temp_dir / download_info["filename"]

                    with open(package_file, "wb") as f:
                        f.write(package_response.content)

                    return {
                        "name": name,
                        "version": download_info["version"],
                        "path": str(package_file),
                        "local": False,
                    }
                else:
                    raise InstallError(
                        f"Failed to download {name}: HTTP {package_response.status_code}"
                    )
            else:
                raise InstallError(f"Package {name} not found in registry")

        except httpx.RequestError as e:
            raise InstallError(f"Network error downloading {name}: {e}")

    def _install_single_package(
        self,
        pkg_info: dict[str, Any],
        user_install: bool = False,
        target_dir: str | None = None,
        editable: bool = False,
    ) -> None:
        """Install a single package.

        Args:
            pkg_info: Package information
            user_install: Install to user site-packages
            target_dir: Target directory
            editable: Install in editable mode
        """
        cmd = ["pip", "install"]

        if user_install:
            cmd.append("--user")

        if target_dir:
            cmd.extend(["--target", target_dir])

        if editable and pkg_info.get("local", False):
            cmd.append("--editable")

        cmd.append(pkg_info["path"])

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise InstallError(f"Failed to install {pkg_info['name']}: {e.stderr}")

    def show_install_summary(self, result: dict[str, Any]) -> None:
        """Show installation summary.

        Args:
            result: Installation result
        """
        table = Table(title="Installed Packages")
        table.add_column("Package", style="cyan")
        table.add_column("Status", style="green")

        for pkg_name in result["installed"]:
            table.add_row(pkg_name, "✓ Installed")

        console.print(table)


class PackageUninstaller:
    """Handles package uninstallation."""

    def __init__(self, config: Any) -> None:
        """Initialize package uninstaller.

        Args:
            config: CLI configuration
        """
        self.config = config

    def check_installed_packages(
        self, packages: builtins.list[str], user_install: bool = False
    ) -> builtins.list[dict[str, str]]:
        """Check which packages are installed.

        Args:
            packages: Package names to check
            user_install: Check user site-packages

        Returns:
            List of installed package information
        """
        installed = []

        cmd = ["pip", "list", "--format=json"]
        if user_install:
            cmd.append("--user")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            installed_packages = json.loads(result.stdout)

            installed_dict = {pkg["name"].lower(): pkg for pkg in installed_packages}

            for pkg_name in packages:
                pkg_key = pkg_name.lower()
                if pkg_key in installed_dict:
                    installed.append(installed_dict[pkg_key])

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to list installed packages: {e}")

        return installed

    def uninstall_packages(
        self, packages: builtins.list[str], user_install: bool = False
    ) -> dict[str, Any]:
        """Uninstall packages.

        Args:
            packages: Package names to uninstall
            user_install: Uninstall from user site-packages

        Returns:
            Uninstallation result
        """
        uninstalled = []
        errors = []

        for package in packages:
            try:
                cmd = ["pip", "uninstall", "--yes", package]
                if user_install:
                    cmd.append("--user")

                subprocess.run(cmd, capture_output=True, text=True, check=True)
                uninstalled.append(package)

            except subprocess.CalledProcessError as e:
                errors.append(f"{package}: {e.stderr}")

        return {
            "uninstalled": uninstalled,
            "errors": errors,
        }


class PackageLister:
    """Lists installed packages."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize package lister.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def get_installed_packages(
        self, user_only: bool = False, check_outdated: bool = False
    ) -> builtins.list[dict[str, Any]]:
        """Get list of installed packages.

        Args:
            user_only: List user site-packages only
            check_outdated: Check for outdated packages

        Returns:
            List of package information
        """
        cmd = ["pip", "list", "--format=json"]
        if user_only:
            cmd.append("--user")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packages = json.loads(result.stdout)

            if check_outdated:
                # Check for updates
                for pkg in packages:
                    pkg["outdated"] = self._check_package_outdated(
                        pkg["name"], pkg["version"]
                    )

            return packages

        except subprocess.CalledProcessError as e:
            raise InstallError(f"Failed to list packages: {e}")

    def _check_package_outdated(self, name: str, current_version: str) -> bool:
        """Check if package is outdated.

        Args:
            name: Package name
            current_version: Current version

        Returns:
            True if package is outdated
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{name}/latest"
            )

            if response.status_code == 200:
                latest_info = response.json()
                latest_version = latest_info["version"]

                return version.parse(latest_version) > version.parse(current_version)

        except (httpx.RequestError, Exception):
            pass

        return False

    def display_table(
        self, packages: builtins.list[dict[str, Any]], show_dependencies: bool = False
    ) -> None:
        """Display packages in table format.

        Args:
            packages: Package information
            show_dependencies: Show dependency tree
        """
        if show_dependencies:
            # Show as dependency tree
            tree = Tree("Installed Packages")

            for pkg in packages:
                tree.add(f"[cyan]{pkg['name']}[/cyan] {pkg['version']}")
                # Would add dependencies here

            console.print(tree)
        else:
            table = Table(title="Installed Packages")
            table.add_column("Name", style="cyan")
            table.add_column("Version", style="green")

            if any(pkg.get("outdated") for pkg in packages):
                table.add_column("Status", style="yellow")

            for pkg in packages:
                row = [pkg["name"], pkg["version"]]

                if "outdated" in pkg:
                    if pkg["outdated"]:
                        row.append("⚠️ Outdated")
                    else:
                        row.append("✓ Current")

                table.add_row(*row)

            console.print(table)

    def display_json(self, packages: builtins.list[dict[str, Any]]) -> None:
        """Display packages in JSON format.

        Args:
            packages: Package information
        """
        console.print(json.dumps(packages, indent=2))

    def display_freeze(self, packages: builtins.list[dict[str, Any]]) -> None:
        """Display packages in freeze format.

        Args:
            packages: Package information
        """
        for pkg in packages:
            console.print(f"{pkg['name']}=={pkg['version']}")


class PackageInfoDisplayer:
    """Displays detailed package information."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize info displayer.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def get_package_info(self, package_name: str) -> dict[str, Any]:
        """Get detailed package information.

        Args:
            package_name: Package name

        Returns:
            Package information
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{package_name}"
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise InstallError(f"Package '{package_name}' not found")

        except httpx.RequestError as e:
            raise InstallError(f"Network error: {e}")

    def display_package_info(self, package_info: dict[str, Any]) -> None:
        """Display package information.

        Args:
            package_info: Package information
        """
        # Basic information
        basic_table = Table(title="Package Information")
        basic_table.add_column("Property", style="cyan")
        basic_table.add_column("Value", style="green")

        basic_table.add_row("Name", package_info["name"])
        basic_table.add_row("Version", package_info["latest_version"])
        basic_table.add_row("Author", package_info.get("author", "Unknown"))
        basic_table.add_row(
            "Description", package_info.get("description", "No description")
        )
        basic_table.add_row("Homepage", package_info.get("homepage", "Not specified"))
        basic_table.add_row("Downloads", str(package_info.get("downloads", 0)))

        console.print(basic_table)

        # Dependencies
        if package_info.get("dependencies"):
            console.print("\n[bold]Dependencies:[/bold]")
            for dep in package_info["dependencies"]:
                console.print(f"  📦 {dep}")

        # Available versions
        if package_info.get("versions"):
            console.print("\n[bold]Available Versions:[/bold]")
            for ver in package_info["versions"][:10]:  # Show latest 10
                console.print(f"  📋 {ver}")


class PackageSearcher:
    """Searches packages in registry."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize package searcher.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def search_packages(
        self, query: str, limit: int = 20
    ) -> builtins.list[dict[str, Any]]:
        """Search packages in registry.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/search",
                params={"q": query, "limit": limit},
            )

            if response.status_code == 200:
                return response.json()["packages"]
            else:
                raise InstallError(f"Search failed: {response.text}")

        except httpx.RequestError as e:
            raise InstallError(f"Network error: {e}")

    def display_search_results(self, results: builtins.list[dict[str, Any]]) -> None:
        """Display search results.

        Args:
            results: Search results
        """
        table = Table(title="Search Results")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description", style="white")

        for pkg in results:
            description = pkg.get("description", "")
            if len(description) > 50:
                description = description[:47] + "..."

            table.add_row(
                pkg["name"],
                pkg["latest_version"],
                description,
            )

        console.print(table)


class PackageUpdater:
    """Handles package updates."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize package updater.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def check_updates(
        self,
        specific_packages: builtins.list[str] | None = None,
        user_only: bool = False,
        include_pre: bool = False,
    ) -> builtins.list[dict[str, Any]]:
        """Check for package updates.

        Args:
            specific_packages: Check specific packages only
            user_only: Check user packages only
            include_pre: Include pre-release versions

        Returns:
            List of available updates
        """
        # Get installed packages
        lister = PackageLister(self.registry_url, self.config)
        installed = lister.get_installed_packages(user_only=user_only)

        if specific_packages:
            installed = [pkg for pkg in installed if pkg["name"] in specific_packages]

        updates = []

        for pkg in installed:
            try:
                response = self.client.get(
                    f"{self.registry_url}/api/v1/packages/{pkg['name']}/latest"
                )

                if response.status_code == 200:
                    latest_info = response.json()
                    latest_version = latest_info["version"]

                    if version.parse(latest_version) > version.parse(pkg["version"]):
                        updates.append(
                            {
                                "name": pkg["name"],
                                "current_version": pkg["version"],
                                "latest_version": latest_version,
                            }
                        )

            except httpx.RequestError:
                continue

        return updates

    def display_available_updates(self, updates: builtins.list[dict[str, Any]]) -> None:
        """Display available updates.

        Args:
            updates: Available updates
        """
        table = Table(title="Available Updates")
        table.add_column("Package", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Latest", style="green")

        for update in updates:
            table.add_row(
                update["name"],
                update["current_version"],
                update["latest_version"],
            )

        console.print(table)

    def update_packages(
        self, updates: builtins.list[dict[str, Any]], user_install: bool = False
    ) -> dict[str, Any]:
        """Update packages.

        Args:
            updates: Updates to apply
            user_install: Install to user site-packages

        Returns:
            Update result
        """
        updated = []
        errors = []

        for update in updates:
            try:
                cmd = ["pip", "install", "--upgrade"]
                if user_install:
                    cmd.append("--user")

                cmd.append(update["name"])

                subprocess.run(cmd, capture_output=True, text=True, check=True)

                updated.append(
                    {
                        "name": update["name"],
                        "old_version": update["current_version"],
                        "new_version": update["latest_version"],
                    }
                )

            except subprocess.CalledProcessError as e:
                errors.append(f"{update['name']}: {e.stderr}")

        return {
            "updated": updated,
            "errors": errors,
        }


class DependencyResolver:
    """Resolves package dependencies."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize dependency resolver.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def resolve_dependencies(
        self,
        packages: builtins.list[dict[str, Any]],
        include_pre: bool = False,
    ) -> builtins.list[dict[str, Any]]:
        """Resolve package dependencies.

        Args:
            packages: Root packages
            include_pre: Include pre-release versions

        Returns:
            List of all packages including dependencies
        """
        resolved = []
        visited = set()

        def resolve_recursive(pkg_spec: dict[str, Any]) -> None:
            name = pkg_spec["name"]

            if name in visited:
                return

            visited.add(name)
            resolved.append(pkg_spec)

            # Get package dependencies
            try:
                response = self.client.get(
                    f"{self.registry_url}/api/v1/packages/{name}"
                )

                if response.status_code == 200:
                    pkg_info = response.json()
                    dependencies = pkg_info.get("dependencies", [])

                    for dep_spec in dependencies:
                        try:
                            dep_req = requirements.Requirement(dep_spec)
                            dep_pkg_spec = {
                                "name": dep_req.name,
                                "version": str(dep_req.specifier)
                                if dep_req.specifier
                                else None,
                                "extras": list(dep_req.extras),
                                "local": False,
                            }
                            resolve_recursive(dep_pkg_spec)
                        except Exception:
                            continue

            except httpx.RequestError:
                pass

        for pkg_spec in packages:
            resolve_recursive(pkg_spec)

        return resolved
