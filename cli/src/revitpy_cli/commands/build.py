"""Build and packaging commands."""

import shutil
import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..core.config import get_config
from ..core.exceptions import BuildError, CommandError
from ..core.logging import get_logger, log_command_complete, log_command_start
from ..utils.validation import ProjectValidator

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="build",
    help="Build and package RevitPy projects",
    rich_markup_mode="rich",
)


@app.command()
def package(
    project_path: str | None = typer.Argument(None, help="Project directory"),
    output_dir: str | None = typer.Option(
        None, "--output", "-o", help="Output directory"
    ),
    clean: bool = typer.Option(
        True, "--clean/--no-clean", help="Clean build artifacts"
    ),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate project"
    ),
    include_tests: bool = typer.Option(
        False, "--include-tests", help="Include tests in package"
    ),
    sign: bool = typer.Option(False, "--sign", help="Sign the package"),
    compression: str | None = typer.Option(
        None, "--compression", help="Compression type (gzip, bzip2, xz)"
    ),
) -> None:
    """Build a RevitPy project package.

    Examples:
        revitpy build package
        revitpy build package --output dist/
        revitpy build package --no-validate --include-tests
    """
    start_time = time.time()
    log_command_start(
        "build package",
        {
            "project_path": project_path,
            "output_dir": output_dir,
            "clean": clean,
            "validate": validate,
            "include_tests": include_tests,
            "sign": sign,
            "compression": compression,
        },
    )

    config = get_config()

    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()

    if not proj_path.exists():
        raise CommandError("build package", f"Project directory not found: {proj_path}")

    # Determine output directory
    if output_dir:
        output_path = Path(output_dir).resolve()
    else:
        output_path = proj_path / config.build.output_dir

    builder = PackageBuilder(proj_path, output_path, config)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Step 1: Validation
            if validate:
                task1 = progress.add_task("Validating project...", total=None)
                validation_issues = builder.validate_project()
                if validation_issues:
                    show_validation_issues(validation_issues)
                    # Only fail on errors, not warnings
                    if any(issue["type"] == "error" for issue in validation_issues):
                        raise BuildError("Project validation failed")
                progress.update(task1, completed=True)

            # Step 2: Clean
            if clean:
                task2 = progress.add_task("Cleaning build artifacts...", total=None)
                builder.clean()
                progress.update(task2, completed=True)

            # Step 3: Build
            task3 = progress.add_task("Building package...", total=None)
            package_paths = builder.build(
                include_tests=include_tests,
                compression=compression,
            )
            progress.update(task3, completed=True)

            # Step 4: Sign (optional)
            if sign:
                task4 = progress.add_task("Signing package...", total=None)
                builder.sign_packages(package_paths)
                progress.update(task4, completed=True)

    except Exception as e:
        raise BuildError(str(e)) from e

    # Success message
    console.print()
    console.print("[bold green]✓[/bold green] Package built successfully!")
    console.print(f"[dim]Output: {output_path}[/dim]")

    # Show built packages
    for package_path in package_paths:
        size = package_path.stat().st_size / 1024  # KB
        console.print(f"  📦 {package_path.name} ({size:.1f} KB)")

    duration = time.time() - start_time
    log_command_complete("build package", duration)


@app.command()
def validate(
    project_path: str | None = typer.Argument(None, help="Project directory"),
    fix: bool = typer.Option(
        False, "--fix", help="Automatically fix issues where possible"
    ),
) -> None:
    """Validate a RevitPy project.

    Examples:
        revitpy build validate
        revitpy build validate --fix
        revitpy build validate /path/to/project
    """
    start_time = time.time()
    log_command_start("build validate", {"project_path": project_path, "fix": fix})

    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()

    if not proj_path.exists():
        raise CommandError(
            "build validate", f"Project directory not found: {proj_path}"
        )

    validator = ProjectValidator(proj_path)

    console.print(f"[bold]Validating project at:[/bold] {proj_path}")
    console.print()

    all_issues = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Project structure validation
        task1 = progress.add_task("Checking project structure...", total=None)
        structure_issues = validator.validate_project_structure()
        all_issues.extend(structure_issues)
        progress.update(task1, completed=True)

        # Configuration validation
        task2 = progress.add_task("Checking configuration...", total=None)
        config_issues = validator.validate_pyproject_toml()
        all_issues.extend(config_issues)
        progress.update(task2, completed=True)

        # Dependency validation
        task3 = progress.add_task("Checking dependencies...", total=None)
        dep_issues = validator.validate_dependencies()
        all_issues.extend(dep_issues)
        progress.update(task3, completed=True)

        # Code quality validation
        task4 = progress.add_task("Checking code quality...", total=None)
        code_issues = validator.validate_code_quality()
        all_issues.extend(code_issues)
        progress.update(task4, completed=True)

    console.print()

    if not all_issues:
        console.print("[bold green]✓[/bold green] Project validation passed!")
    else:
        show_validation_issues(all_issues)

        # Apply fixes if requested
        if fix:
            console.print("\n[yellow]Attempting to fix issues...[/yellow]")
            fixed_count = apply_fixes(proj_path, all_issues)
            if fixed_count > 0:
                console.print(f"[green]✓[/green] Fixed {fixed_count} issues")

    duration = time.time() - start_time
    log_command_complete("build validate", duration)


@app.command()
def clean(
    project_path: str | None = typer.Argument(None, help="Project directory"),
    all_artifacts: bool = typer.Option(
        False, "--all", help="Remove all build artifacts"
    ),
) -> None:
    """Clean build artifacts.

    Examples:
        revitpy build clean
        revitpy build clean --all
        revitpy build clean /path/to/project
    """
    start_time = time.time()
    log_command_start(
        "build clean", {"project_path": project_path, "all_artifacts": all_artifacts}
    )

    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()

    if not proj_path.exists():
        raise CommandError("build clean", f"Project directory not found: {proj_path}")

    config = get_config()
    cleaner = ArtifactCleaner(proj_path, config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Cleaning artifacts...", total=None)
        removed_files = cleaner.clean(all_artifacts)
        progress.update(task, completed=True)

    if removed_files:
        console.print(f"[green]✓[/green] Removed {len(removed_files)} artifacts")
        if config.debug:
            for file_path in removed_files:
                console.print(f"  🗑️  {file_path}")
    else:
        console.print("[dim]No artifacts to clean[/dim]")

    duration = time.time() - start_time
    log_command_complete("build clean", duration)


class PackageBuilder:
    """Builds RevitPy packages."""

    def __init__(self, project_path: Path, output_path: Path, config) -> None:
        """Initialize package builder.

        Args:
            project_path: Path to project directory
            output_path: Output directory for packages
            config: CLI configuration
        """
        self.project_path = project_path
        self.output_path = output_path
        self.config = config

    def validate_project(self) -> list[dict]:
        """Validate the project before building.

        Returns:
            List of validation issues
        """
        validator = ProjectValidator(self.project_path)
        issues = []

        issues.extend(validator.validate_project_structure())
        issues.extend(validator.validate_pyproject_toml())
        issues.extend(validator.validate_dependencies())
        issues.extend(validator.validate_code_quality())

        return issues

    def clean(self) -> None:
        """Clean build artifacts."""
        cleaner = ArtifactCleaner(self.project_path, self.config)
        cleaner.clean(all_artifacts=True)

    def build(
        self,
        include_tests: bool = False,
        compression: str | None = None,
    ) -> list[Path]:
        """Build the package.

        Args:
            include_tests: Include tests in package
            compression: Compression type

        Returns:
            List of built package paths
        """
        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Build using standard Python tools
        packages = []

        # Build wheel
        wheel_path = self._build_wheel()
        if wheel_path:
            packages.append(wheel_path)

        # Build source distribution
        sdist_path = self._build_sdist()
        if sdist_path:
            packages.append(sdist_path)

        return packages

    def sign_packages(self, package_paths: list[Path]) -> None:
        """Sign packages.

        Args:
            package_paths: List of package paths to sign
        """
        # This would integrate with signing tools
        logger.info("Package signing not implemented yet")

    def _build_wheel(self) -> Path | None:
        """Build wheel package.

        Returns:
            Path to built wheel or None if failed
        """
        try:
            subprocess.run(
                ["python", "-m", "build", "--wheel", "--outdir", str(self.output_path)],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Find the built wheel
            for file in self.output_path.glob("*.whl"):
                return file

        except subprocess.CalledProcessError as e:
            logger.error(f"Wheel build failed: {e.stderr}")
            raise BuildError(f"Failed to build wheel: {e.stderr}")

        return None

    def _build_sdist(self) -> Path | None:
        """Build source distribution.

        Returns:
            Path to built sdist or None if failed
        """
        try:
            subprocess.run(
                ["python", "-m", "build", "--sdist", "--outdir", str(self.output_path)],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Find the built sdist
            for file in self.output_path.glob("*.tar.gz"):
                return file

        except subprocess.CalledProcessError as e:
            logger.error(f"Sdist build failed: {e.stderr}")
            raise BuildError(f"Failed to build sdist: {e.stderr}")

        return None


class ArtifactCleaner:
    """Cleans build artifacts."""

    def __init__(self, project_path: Path, config) -> None:
        """Initialize artifact cleaner.

        Args:
            project_path: Path to project directory
            config: CLI configuration
        """
        self.project_path = project_path
        self.config = config

    def clean(self, all_artifacts: bool = False) -> list[Path]:
        """Clean build artifacts.

        Args:
            all_artifacts: Remove all artifacts, including caches

        Returns:
            List of removed file paths
        """
        removed_files = []

        # Standard build artifacts
        artifacts_to_remove = [
            "build/",
            "dist/",
            "*.egg-info/",
            "**/__pycache__/",
            "**/*.pyc",
            "**/*.pyo",
            ".pytest_cache/",
            ".coverage",
            ".mypy_cache/",
        ]

        if all_artifacts:
            artifacts_to_remove.extend(
                [
                    ".tox/",
                    ".venv/",
                    "venv/",
                    "env/",
                    ".cache/",
                ]
            )

        for pattern in artifacts_to_remove:
            for path in self.project_path.glob(pattern):
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    removed_files.append(path)
                except Exception as e:
                    logger.warning(f"Failed to remove {path}: {e}")

        return removed_files


def show_validation_issues(issues: list[dict]) -> None:
    """Display validation issues in a formatted table.

    Args:
        issues: List of validation issues
    """
    if not issues:
        return

    table = Table(title="Validation Issues")
    table.add_column("Type", style="cyan")
    table.add_column("Message", style="white")

    error_count = 0
    warning_count = 0

    for issue in issues:
        issue_type = issue["type"]
        message = issue["message"]

        if issue_type == "error":
            style = "red"
            error_count += 1
        elif issue_type == "warning":
            style = "yellow"
            warning_count += 1
        else:
            style = "blue"

        table.add_row(f"[{style}]{issue_type.upper()}[/{style}]", message)

    console.print(table)
    console.print(
        f"[red]{error_count}[/red] errors, [yellow]{warning_count}[/yellow] warnings"
    )


def apply_fixes(project_path: Path, issues: list[dict]) -> int:
    """Apply automatic fixes to validation issues.

    Args:
        project_path: Path to project directory
        issues: List of validation issues

    Returns:
        Number of issues fixed
    """
    fixed_count = 0

    for issue in issues:
        message = issue["message"]

        # Example fixes - in reality this would be more sophisticated
        if "No README file found" in message:
            readme_path = project_path / "README.md"
            if not readme_path.exists():
                readme_path.write_text("# Project\n\nDescription of your project.\n")
                fixed_count += 1

        elif "No LICENSE file found" in message:
            license_path = project_path / "LICENSE"
            if not license_path.exists():
                # Create basic MIT license template
                license_content = """MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
                license_path.write_text(license_content)
                fixed_count += 1

    return fixed_count
