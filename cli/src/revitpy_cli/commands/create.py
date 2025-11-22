"""Project creation and scaffolding commands."""

import shutil
import time
from pathlib import Path

import typer
from cookiecutter.main import cookiecutter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..core.config import get_config
from ..core.exceptions import CommandError, TemplateError
from ..core.logging import get_logger, log_command_complete, log_command_start
from ..utils.git import GitManager
from ..utils.templates import TemplateManager

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="create",
    help="Create new RevitPy projects from templates",
    rich_markup_mode="rich",
)


@app.command()
def project(
    name: str = typer.Argument(..., help="Project name"),
    template: str | None = typer.Option(
        None, "--template", "-t", help="Template to use"
    ),
    output_dir: str | None = typer.Option(
        None, "--output", "-o", help="Output directory"
    ),
    no_git: bool = typer.Option(
        False, "--no-git", help="Don't initialize git repository"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing directory"),
) -> None:
    """Create a new RevitPy project from a template.

    Examples:
        revitpy create my-project
        revitpy create my-addin --template addin
        revitpy create my-plugin --template plugin --output ./projects
    """
    start_time = time.time()
    log_command_start(
        "create project",
        {
            "name": name,
            "template": template,
            "output_dir": output_dir,
            "no_git": no_git,
            "interactive": interactive,
            "force": force,
        },
    )

    config = get_config()
    template_manager = TemplateManager()

    # Determine template to use
    if not template:
        if interactive:
            template = select_template_interactively(template_manager)
        else:
            template = config.template.default_template

    # Determine output directory
    if output_dir:
        output_path = Path(output_dir).resolve()
    else:
        output_path = Path.cwd()

    project_path = output_path / name

    # Check if project directory already exists
    if project_path.exists():
        if not force:
            if interactive and not Confirm.ask(
                f"Directory '{project_path}' already exists. Overwrite?"
            ):
                console.print("[yellow]Project creation cancelled.[/yellow]")
                raise typer.Exit(0)
            elif not interactive:
                raise CommandError(
                    "create project",
                    f"Directory '{project_path}' already exists",
                    suggestion="Use --force to overwrite or choose a different name",
                )

        # Remove existing directory
        if project_path.is_dir():
            shutil.rmtree(project_path)
        else:
            project_path.unlink()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Step 1: Download/validate template
            task1 = progress.add_task("Preparing template...", total=None)
            template_path = template_manager.get_template(template)
            progress.update(task1, completed=True)

            # Step 2: Collect template variables
            task2 = progress.add_task("Collecting project information...", total=None)
            context = collect_template_context(name, template_path, interactive)
            progress.update(task2, completed=True)

            # Step 3: Generate project
            task3 = progress.add_task("Generating project...", total=None)
            generated_path = generate_project(template_path, context, output_path)
            progress.update(task3, completed=True)

            # Step 4: Initialize git repository
            if not no_git:
                task4 = progress.add_task("Initializing git repository...", total=None)
                init_git_repository(generated_path)
                progress.update(task4, completed=True)

            # Step 5: Post-processing
            task5 = progress.add_task("Finalizing project...", total=None)
            post_process_project(generated_path, template, context)
            progress.update(task5, completed=True)

    except Exception as e:
        raise CommandError("create project", str(e)) from e

    # Success message
    console.print()
    console.print(f"[bold green]✓[/bold green] Project '{name}' created successfully!")
    console.print(f"[dim]Location: {project_path}[/dim]")

    # Show next steps
    show_next_steps(project_path, template)

    duration = time.time() - start_time
    log_command_complete("create project", duration)


@app.command(name="list-templates")
def list_templates() -> None:
    """List available project templates."""
    log_command_start("list templates", {})

    template_manager = TemplateManager()
    templates = template_manager.list_templates()

    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        return

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Type", style="blue")
    table.add_column("Source", style="dim")

    for template_info in templates:
        table.add_row(
            template_info.name,
            template_info.description,
            template_info.type,
            template_info.source,
        )

    console.print(table)
    log_command_complete("list templates", 0)


@app.command(name="add-template")
def add_template(
    url: str = typer.Argument(..., help="Template repository URL or path"),
    name: str | None = typer.Option(None, "--name", help="Template name"),
    update: bool = typer.Option(
        False, "--update", help="Update if template already exists"
    ),
) -> None:
    """Add a new template source."""
    log_command_start("add template", {"url": url, "name": name, "update": update})

    template_manager = TemplateManager()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Adding template...", total=None)
            template_manager.add_template(url, name, update)
            progress.update(task, completed=True)

        console.print("[green]✓[/green] Template added successfully")

    except Exception as e:
        raise CommandError("add template", str(e)) from e

    log_command_complete("add template", 0)


@app.command(name="remove-template")
def remove_template(
    name: str = typer.Argument(..., help="Template name to remove"),
    force: bool = typer.Option(
        False, "--force", help="Force removal without confirmation"
    ),
) -> None:
    """Remove a template."""
    log_command_start("remove template", {"name": name, "force": force})

    template_manager = TemplateManager()

    if not force and not Confirm.ask(f"Remove template '{name}'?"):
        console.print("[yellow]Template removal cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        template_manager.remove_template(name)
        console.print(f"[green]✓[/green] Template '{name}' removed successfully")

    except Exception as e:
        raise CommandError("remove template", str(e)) from e

    log_command_complete("remove template", 0)


def select_template_interactively(template_manager: TemplateManager) -> str:
    """Interactively select a template.

    Args:
        template_manager: Template manager instance

    Returns:
        Selected template name
    """
    templates = template_manager.list_templates()

    if not templates:
        raise TemplateError("", "No templates available")

    console.print("\n[bold]Available Templates:[/bold]")
    for i, template_info in enumerate(templates, 1):
        console.print(
            f"  {i}. [cyan]{template_info.name}[/cyan] - {template_info.description}"
        )

    while True:
        choice = Prompt.ask(f"\nSelect template (1-{len(templates)})", default="1")

        try:
            index = int(choice) - 1
            if 0 <= index < len(templates):
                return templates[index].name
            else:
                console.print("[red]Invalid selection. Please try again.[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")


def collect_template_context(
    project_name: str, template_path: Path, interactive: bool
) -> dict[str, str]:
    """Collect context variables for template rendering.

    Args:
        project_name: Name of the project
        template_path: Path to template
        interactive: Whether to collect interactively

    Returns:
        Context dictionary for template rendering
    """
    context = {"project_name": project_name}

    # Load cookiecutter.json if it exists
    cookiecutter_json = template_path / "cookiecutter.json"
    if cookiecutter_json.exists():
        import json

        with open(cookiecutter_json) as f:
            template_context = json.load(f)

        # Override project name
        template_context["project_name"] = project_name

        if interactive:
            # Let cookiecutter handle interactive prompting
            return template_context
        else:
            # Use defaults for non-interactive mode
            for key, value in template_context.items():
                if isinstance(value, list):
                    context[key] = value[0]  # Use first option as default
                else:
                    context[key] = value

    return context


def generate_project(
    template_path: Path, context: dict[str, str], output_dir: Path
) -> Path:
    """Generate project from template.

    Args:
        template_path: Path to template
        context: Template context
        output_dir: Output directory

    Returns:
        Path to generated project

    Raises:
        TemplateError: If project generation fails
    """
    try:
        generated_path = cookiecutter(
            str(template_path),
            output_dir=str(output_dir),
            extra_context=context,
            no_input=True,
            overwrite_if_exists=True,
        )
        return Path(generated_path)

    except Exception as e:
        raise TemplateError(
            str(template_path), f"Failed to generate project: {e}"
        ) from e


def init_git_repository(project_path: Path) -> None:
    """Initialize git repository in project.

    Args:
        project_path: Path to project directory
    """
    try:
        git_manager = GitManager(project_path)
        git_manager.init()

        # Add initial commit
        git_manager.add_all()
        git_manager.commit("Initial commit from RevitPy CLI")

    except Exception as e:
        logger.warning(f"Failed to initialize git repository: {e}")


def post_process_project(
    project_path: Path, template: str, context: dict[str, str]
) -> None:
    """Perform post-processing tasks on generated project.

    Args:
        project_path: Path to generated project
        template: Template name used
        context: Template context used
    """
    # Create any additional directories that might be needed
    dirs_to_create = [
        project_path / "tests",
        project_path / "docs",
        project_path / ".vscode",
    ]

    for dir_path in dirs_to_create:
        if not dir_path.exists():
            dir_path.mkdir(exist_ok=True)

    # Create .gitignore if it doesn't exist
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# RevitPy
.revitpy/
*.revit.bak

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
        """.strip()

        gitignore_path.write_text(gitignore_content)

    # Run any template-specific post-processing
    post_process_hook = project_path / "hooks" / "post_gen_project.py"
    if post_process_hook.exists():
        try:
            import subprocess

            subprocess.run(
                ["python", str(post_process_hook)],
                cwd=project_path,
                check=True,
                capture_output=True,
            )
            # Remove hooks directory
            shutil.rmtree(project_path / "hooks")
        except Exception as e:
            logger.warning(f"Post-generation hook failed: {e}")


def show_next_steps(project_path: Path, template: str) -> None:
    """Show next steps after project creation.

    Args:
        project_path: Path to created project
        template: Template used
    """
    console.print("\n[bold blue]Next Steps:[/bold blue]")
    console.print(f"1. [dim]cd {project_path.name}[/dim]")

    # Check if requirements.txt or pyproject.toml exists
    if (project_path / "requirements.txt").exists():
        console.print("2. [dim]pip install -r requirements.txt[/dim]")
    elif (project_path / "pyproject.toml").exists():
        console.print("2. [dim]pip install -e .[dev][/dim]")

    console.print("3. [dim]revitpy dev[/dim] - Start development server")
    console.print("4. [dim]revitpy build[/dim] - Build your project")

    # Template-specific suggestions
    if template in ["addin", "plugin"]:
        console.print("5. [dim]Configure Revit installation path in revitpy.toml[/dim]")

    console.print("\n[dim]For help: revitpy --help[/dim]")
