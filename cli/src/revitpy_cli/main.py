"""Main CLI entry point for RevitPy CLI tools."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.traceback import install

from revitpy_cli.commands import (
    build as build_cmd,
    create as create_cmd,
    dev as dev_cmd,
    publish as publish_cmd,
)

# Import install command - handle missing module gracefully
try:
    from revitpy_cli.commands import install as install_cmd
except ImportError:
    install_cmd = None

# Import doctor command - handle missing module gracefully  
try:
    from revitpy_cli.commands import doctor as doctor_cmd
except ImportError:
    doctor_cmd = None
from revitpy_cli.core.config import get_config
from revitpy_cli.core.exceptions import RevitPyCliError
from revitpy_cli.plugins.manager import PluginManager

# Install rich traceback handler
install(show_locals=True)

console = Console()

app = typer.Typer(
    name="revitpy",
    help="Professional CLI Development Tools for RevitPy Framework",
    epilog="Visit https://revitpy.dev/cli for documentation and examples.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Add command groups
app.add_typer(create_cmd.app, name="create")
app.add_typer(build_cmd.app, name="build") 
app.add_typer(dev_cmd.app, name="dev")
app.add_typer(publish_cmd.app, name="publish")

# Add install command if available
if install_cmd:
    app.add_typer(install_cmd.app, name="install")

# Add doctor command if available
if doctor_cmd:
    app.add_typer(doctor_cmd.app, name="doctor")


@app.command()
def version() -> None:
    """Show RevitPy CLI version information."""
    from revitpy_cli import __version__
    
    console.print(f"[bold blue]RevitPy CLI[/bold blue] version [green]{__version__}[/green]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", help="Edit configuration file"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default configuration"),
) -> None:
    """Manage RevitPy CLI configuration."""
    config_instance = get_config()
    
    if reset:
        config_instance.reset_to_defaults()
        console.print("[green]✓[/green] Configuration reset to defaults")
        return
    
    if edit:
        config_path = config_instance.config_file
        editor = config_instance.editor or "nano"
        typer.launch(str(config_path), application=editor)
        return
    
    if show:
        config_instance.show_config()
        return
    
    console.print("[yellow]Use --show, --edit, or --reset flags[/yellow]")


@app.command(name="completion")
def generate_completion(
    shell: str = typer.Option(
        None, 
        help="Shell type (bash, zsh, fish, powershell)"
    ),
    install: bool = typer.Option(
        False, 
        "--install", 
        help="Install completion automatically"
    ),
) -> None:
    """Generate shell completion scripts."""
    if not shell:
        # Auto-detect shell
        shell = detect_shell()
    
    if shell not in ["bash", "zsh", "fish", "powershell"]:
        console.print(f"[red]Error:[/red] Unsupported shell '{shell}'")
        raise typer.Exit(1)
    
    if install:
        install_completion(shell)
    else:
        generate_completion_script(shell)


@app.command()
def plugins(
    list_plugins: bool = typer.Option(False, "--list", help="List installed plugins"),
    install: Optional[str] = typer.Option(None, "--install", help="Install a plugin"),
    uninstall: Optional[str] = typer.Option(None, "--uninstall", help="Uninstall a plugin"),
) -> None:
    """Manage RevitPy CLI plugins."""
    manager = PluginManager()
    
    if list_plugins:
        manager.list_plugins()
    elif install:
        manager.install_plugin(install)
    elif uninstall:
        manager.uninstall_plugin(uninstall)
    else:
        console.print("[yellow]Use --list, --install, or --uninstall flags[/yellow]")


def detect_shell() -> str:
    """Auto-detect the current shell."""
    try:
        import shellingham
        shell_name, _ = shellingham.detect_shell()
        return shell_name
    except Exception:
        # Fallback to environment inspection
        shell_path = Path(sys.argv[0] if sys.argv else "bash")
        return shell_path.stem


def generate_completion_script(shell: str) -> None:
    """Generate completion script for specified shell."""
    try:
        from typer.main import get_command
        
        click_command = get_command(app)
        
        if shell == "bash":
            script = click_command.get_completion_script("bash", "revitpy")
        elif shell == "zsh":
            script = click_command.get_completion_script("zsh", "revitpy")
        elif shell == "fish":
            script = click_command.get_completion_script("fish", "revitpy")
        else:
            console.print(f"[red]Error:[/red] Completion for {shell} not implemented")
            raise typer.Exit(1)
        
        console.print(script)
        
    except Exception as e:
        console.print(f"[red]Error generating completion:[/red] {e}")
        raise typer.Exit(1)


def install_completion(shell: str) -> None:
    """Install completion script for specified shell."""
    try:
        from typer.main import get_command
        
        click_command = get_command(app)
        
        if shell == "bash":
            script = click_command.get_completion_script("bash", "revitpy")
            completion_file = Path.home() / ".bash_completion.d" / "revitpy"
        elif shell == "zsh":
            script = click_command.get_completion_script("zsh", "revitpy")
            completion_file = Path.home() / ".zsh" / "completions" / "_revitpy"
        elif shell == "fish":
            script = click_command.get_completion_script("fish", "revitpy")
            completion_file = Path.home() / ".config" / "fish" / "completions" / "revitpy.fish"
        else:
            console.print(f"[red]Error:[/red] Auto-install for {shell} not supported")
            raise typer.Exit(1)
        
        # Create directory if it doesn't exist
        completion_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write completion script
        completion_file.write_text(script)
        
        console.print(f"[green]✓[/green] Completion installed for {shell}")
        console.print(f"[dim]Restart your shell or run: source {completion_file}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error installing completion:[/red] {e}")
        raise typer.Exit(1)


def main() -> None:
    """Main CLI entry point with error handling."""
    try:
        app()
    except RevitPyCliError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if "--debug" in sys.argv:
            raise
        raise typer.Exit(1)


if __name__ == "__main__":
    main()