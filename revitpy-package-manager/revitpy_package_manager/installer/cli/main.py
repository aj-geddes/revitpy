"""Main CLI entry point for the RevitPy package installer."""

import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from ..resolver import DependencyResolver, PackageSpec
from ..venv_manager import VirtualEnvironmentManager, VirtualEnvironmentError
from ....__init__ import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """RevitPy Package Installer - Manage packages and environments for RevitPy development."""
    ctx.ensure_object(dict)
    ctx.obj['console'] = console


@cli.group()
@click.pass_context
def env(ctx):
    """Manage virtual environments."""
    ctx.obj['venv_manager'] = VirtualEnvironmentManager()


@env.command('list')
@click.pass_context
def list_environments(ctx):
    """List all available environments."""
    venv_manager = ctx.obj['venv_manager']
    environments = venv_manager.list_environments()
    
    if not environments:
        console.print("No environments found.", style="yellow")
        return
    
    table = Table(title="RevitPy Environments")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Python Version", style="green")
    table.add_column("Revit Version", style="blue")
    table.add_column("Status", style="magenta")
    table.add_column("Path", style="dim")
    
    current_env = venv_manager.get_current_environment()
    current_name = current_env.name if current_env else None
    
    for environment in environments:
        status = "active" if environment.name == current_name else "inactive"
        if not environment.exists():
            status = "broken"
        
        table.add_row(
            environment.name,
            environment.python_version,
            environment.revit_version,
            status,
            str(environment.path)
        )
    
    console.print(table)


@env.command('create')
@click.argument('name')
@click.option('--python-version', default="3.11", help="Python version to use")
@click.option('--revit-version', default="2025", help="Target Revit version")
@click.option('--packages', multiple=True, help="Initial packages to install")
@click.pass_context
def create_environment(ctx, name: str, python_version: str, revit_version: str, packages: tuple):
    """Create a new virtual environment."""
    venv_manager = ctx.obj['venv_manager']
    
    try:
        with console.status(f"[bold green]Creating environment '{name}'..."):
            environment = venv_manager.create_environment(
                name=name,
                python_version=python_version,
                revit_version=revit_version,
                packages=list(packages) if packages else None
            )
        
        console.print(Panel(
            f"✅ Environment '{name}' created successfully!\n"
            f"Python: {python_version}\n"
            f"Revit: {revit_version}\n"
            f"Path: {environment.path}",
            title="Success",
            style="green"
        ))
        
        if packages:
            console.print(f"Installed packages: {', '.join(packages)}", style="dim")
        
    except VirtualEnvironmentError as e:
        console.print(f"❌ Failed to create environment: {e}", style="red")
        sys.exit(1)


@env.command('delete')
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete_environment(ctx, name: str, yes: bool):
    """Delete a virtual environment."""
    venv_manager = ctx.obj['venv_manager']
    
    # Check if environment exists
    environment = venv_manager.get_environment(name)
    if not environment:
        console.print(f"❌ Environment '{name}' not found.", style="red")
        sys.exit(1)
    
    # Confirmation prompt
    if not yes:
        if not click.confirm(f"Delete environment '{name}'? This cannot be undone."):
            console.print("Cancelled.", style="yellow")
            return
    
    # Delete environment
    with console.status(f"[bold red]Deleting environment '{name}'..."):
        success = venv_manager.delete_environment(name)
    
    if success:
        console.print(f"✅ Environment '{name}' deleted successfully.", style="green")
    else:
        console.print(f"❌ Failed to delete environment '{name}'.", style="red")
        sys.exit(1)


@env.command('clone')
@click.argument('source')
@click.argument('target')
@click.pass_context
def clone_environment(ctx, source: str, target: str):
    """Clone an existing environment."""
    venv_manager = ctx.obj['venv_manager']
    
    try:
        with console.status(f"[bold blue]Cloning environment '{source}' to '{target}'..."):
            environment = venv_manager.clone_environment(source, target)
        
        console.print(Panel(
            f"✅ Environment '{target}' created by cloning '{source}'!\n"
            f"Path: {environment.path}",
            title="Success",
            style="green"
        ))
        
    except VirtualEnvironmentError as e:
        console.print(f"❌ Failed to clone environment: {e}", style="red")
        sys.exit(1)


@env.command('info')
@click.argument('name')
@click.pass_context
def environment_info(ctx, name: str):
    """Show detailed information about an environment."""
    venv_manager = ctx.obj['venv_manager']
    environment = venv_manager.get_environment(name)
    
    if not environment:
        console.print(f"❌ Environment '{name}' not found.", style="red")
        sys.exit(1)
    
    # Basic info
    console.print(Panel(
        f"Name: {environment.name}\n"
        f"Python Version: {environment.python_version}\n"
        f"Revit Version: {environment.revit_version}\n"
        f"Path: {environment.path}\n"
        f"Status: {'Active' if environment.is_active else 'Inactive'}\n"
        f"Exists: {'Yes' if environment.exists() else 'No'}",
        title=f"Environment: {name}",
        style="blue"
    ))
    
    # Installed packages
    if environment.exists():
        packages = environment.list_packages()
        
        if packages:
            table = Table(title="Installed Packages")
            table.add_column("Package", style="cyan")
            table.add_column("Version", style="green")
            
            for package in sorted(packages, key=lambda p: p['name']):
                table.add_row(package['name'], package['version'])
            
            console.print(table)
        else:
            console.print("No packages installed.", style="yellow")


@cli.command('install')
@click.argument('packages', nargs=-1, required=True)
@click.option('--environment', '-e', help="Target environment name")
@click.option('--upgrade', '-U', is_flag=True, help="Upgrade packages to latest versions")
@click.option('--no-deps', is_flag=True, help="Don't install dependencies")
@click.option('--dry-run', is_flag=True, help="Show what would be installed without actually installing")
@click.pass_context
def install_packages(ctx, packages: tuple, environment: Optional[str], upgrade: bool, no_deps: bool, dry_run: bool):
    """Install packages."""
    venv_manager = VirtualEnvironmentManager()
    
    # Determine target environment
    if environment:
        target_env = venv_manager.get_environment(environment)
        if not target_env:
            console.print(f"❌ Environment '{environment}' not found.", style="red")
            sys.exit(1)
    else:
        target_env = venv_manager.get_current_environment()
        if not target_env:
            console.print("❌ No active environment. Please specify --environment or activate an environment.", style="red")
            sys.exit(1)
    
    console.print(f"Installing packages in environment: {target_env.name}", style="blue")
    
    if dry_run:
        console.print("🔍 Dry run mode - showing what would be installed:", style="yellow")
        for package in packages:
            console.print(f"  • {package}")
        return
    
    # Install each package
    success_count = 0
    with Progress() as progress:
        task = progress.add_task("Installing packages...", total=len(packages))
        
        for package in packages:
            progress.update(task, description=f"Installing {package}...")
            
            if target_env.install_package(package, upgrade=upgrade):
                console.print(f"✅ Installed {package}", style="green")
                success_count += 1
            else:
                console.print(f"❌ Failed to install {package}", style="red")
            
            progress.advance(task)
    
    console.print(f"\n📦 Installed {success_count}/{len(packages)} packages successfully.", style="blue")


@cli.command('uninstall')
@click.argument('packages', nargs=-1, required=True)
@click.option('--environment', '-e', help="Target environment name")
@click.option('--yes', '-y', is_flag=True, help="Skip confirmation prompts")
@click.pass_context
def uninstall_packages(ctx, packages: tuple, environment: Optional[str], yes: bool):
    """Uninstall packages."""
    venv_manager = VirtualEnvironmentManager()
    
    # Determine target environment
    if environment:
        target_env = venv_manager.get_environment(environment)
        if not target_env:
            console.print(f"❌ Environment '{environment}' not found.", style="red")
            sys.exit(1)
    else:
        target_env = venv_manager.get_current_environment()
        if not target_env:
            console.print("❌ No active environment. Please specify --environment or activate an environment.", style="red")
            sys.exit(1)
    
    # Confirmation
    if not yes:
        console.print(f"Packages to uninstall: {', '.join(packages)}")
        if not click.confirm("Continue?"):
            console.print("Cancelled.", style="yellow")
            return
    
    console.print(f"Uninstalling packages from environment: {target_env.name}", style="blue")
    
    # Uninstall each package
    success_count = 0
    for package in packages:
        if target_env.uninstall_package(package):
            console.print(f"✅ Uninstalled {package}", style="green")
            success_count += 1
        else:
            console.print(f"❌ Failed to uninstall {package}", style="red")
    
    console.print(f"\n📦 Uninstalled {success_count}/{len(packages)} packages successfully.", style="blue")


@cli.command('list')
@click.option('--environment', '-e', help="Target environment name")
@click.pass_context
def list_packages(ctx, environment: Optional[str]):
    """List installed packages."""
    venv_manager = VirtualEnvironmentManager()
    
    # Determine target environment
    if environment:
        target_env = venv_manager.get_environment(environment)
        if not target_env:
            console.print(f"❌ Environment '{environment}' not found.", style="red")
            sys.exit(1)
    else:
        target_env = venv_manager.get_current_environment()
        if not target_env:
            console.print("❌ No active environment. Please specify --environment or activate an environment.", style="red")
            sys.exit(1)
    
    packages = target_env.list_packages()
    
    if not packages:
        console.print("No packages installed.", style="yellow")
        return
    
    table = Table(title=f"Packages in {target_env.name}")
    table.add_column("Package", style="cyan")
    table.add_column("Version", style="green")
    
    for package in sorted(packages, key=lambda p: p['name']):
        table.add_row(package['name'], package['version'])
    
    console.print(table)


@cli.command('config')
@click.argument('key', required=False)
@click.argument('value', required=False)
@click.option('--list', 'list_config', is_flag=True, help="List all configuration values")
@click.option('--global', 'global_config', is_flag=True, help="Use global configuration")
@click.pass_context
def config_command(ctx, key: Optional[str], value: Optional[str], list_config: bool, global_config: bool):
    """Manage configuration settings."""
    config_dir = Path.home() / ".revitpy" if global_config else Path.cwd() / ".revitpy"
    config_file = config_dir / "config.json"
    
    # Load existing config
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    if list_config or (key is None and value is None):
        # List configuration
        if not config:
            console.print("No configuration found.", style="yellow")
            return
        
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        
        for k, v in config.items():
            table.add_row(k, str(v))
        
        console.print(table)
    
    elif key and value:
        # Set configuration
        config[key] = value
        
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        console.print(f"✅ Set {key} = {value}", style="green")
    
    elif key:
        # Get configuration
        if key in config:
            console.print(f"{key} = {config[key]}")
        else:
            console.print(f"❌ Configuration key '{key}' not found.", style="red")
            sys.exit(1)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n⏹️  Interrupted by user.", style="yellow")
        sys.exit(130)
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")
        if os.getenv("DEBUG"):
            console.print_exception()
        sys.exit(1)


if __name__ == '__main__':
    main()