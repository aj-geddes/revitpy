"""System diagnostics and troubleshooting commands."""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.tree import Tree

from ..core.config import get_config
from ..core.exceptions import CommandError, DiagnosticsError
from ..core.logging import get_logger, log_command_complete, log_command_start

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="doctor",
    help="Diagnose and troubleshoot RevitPy installation",
    rich_markup_mode="rich",
)


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    fix_issues: bool = typer.Option(
        False, "--fix", help="Attempt to fix detected issues"
    ),
    output_file: str | None = typer.Option(
        None, "--output", help="Save report to file"
    ),
) -> None:
    """Run comprehensive system diagnostics.

    Examples:
        revitpy doctor check
        revitpy doctor check --verbose --fix
        revitpy doctor check --output diagnostics.txt
    """
    start_time = time.time()
    log_command_start(
        "doctor check",
        {
            "verbose": verbose,
            "fix_issues": fix_issues,
            "output_file": output_file,
        },
    )

    config = get_config()

    try:
        diagnostics = SystemDiagnostics(config, verbose=verbose)

        console.print("[bold blue]🔍 Running RevitPy system diagnostics...[/bold blue]")
        console.print()

        # Run diagnostics
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # System information
            task1 = progress.add_task("Checking system information...", total=None)
            system_info = diagnostics.check_system_info()
            progress.update(task1, completed=True)

            # Python environment
            task2 = progress.add_task("Checking Python environment...", total=None)
            python_info = diagnostics.check_python_environment()
            progress.update(task2, completed=True)

            # RevitPy installation
            task3 = progress.add_task("Checking RevitPy installation...", total=None)
            revitpy_info = diagnostics.check_revitpy_installation()
            progress.update(task3, completed=True)

            # Revit installation
            task4 = progress.add_task("Checking Revit installation...", total=None)
            revit_info = diagnostics.check_revit_installation()
            progress.update(task4, completed=True)

            # Dependencies
            task5 = progress.add_task("Checking dependencies...", total=None)
            deps_info = diagnostics.check_dependencies()
            progress.update(task5, completed=True)

            # Network connectivity
            task6 = progress.add_task("Checking network connectivity...", total=None)
            network_info = diagnostics.check_network_connectivity()
            progress.update(task6, completed=True)

            # Project configuration
            task7 = progress.add_task("Checking project configuration...", total=None)
            project_info = diagnostics.check_project_configuration()
            progress.update(task7, completed=True)

        # Collect all results
        diagnostic_results = {
            "system": system_info,
            "python": python_info,
            "revitpy": revitpy_info,
            "revit": revit_info,
            "dependencies": deps_info,
            "network": network_info,
            "project": project_info,
        }

        # Display results
        console.print()
        diagnostics.display_results(diagnostic_results)

        # Fix issues if requested
        if fix_issues:
            console.print(
                "\n[bold yellow]🔧 Attempting to fix detected issues...[/bold yellow]"
            )
            fix_count = diagnostics.fix_issues(diagnostic_results)
            if fix_count > 0:
                console.print(f"[green]✓[/green] Fixed {fix_count} issues")
            else:
                console.print("[yellow]No fixable issues found[/yellow]")

        # Save report if requested
        if output_file:
            diagnostics.save_report(diagnostic_results, Path(output_file))
            console.print(f"\n[dim]Report saved to: {output_file}[/dim]")

        # Summary
        issues_count = diagnostics.count_issues(diagnostic_results)
        if issues_count == 0:
            console.print(
                "\n[bold green]✓[/bold green] All checks passed! Your RevitPy installation looks healthy."
            )
        else:
            console.print(
                f"\n[bold yellow]⚠️[/bold yellow] Found {issues_count} issues that may affect functionality."
            )
            console.print("[dim]Run with --fix to attempt automatic repairs[/dim]")

    except Exception as e:
        raise DiagnosticsError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("doctor check", duration)


@app.command()
def env(
    format: str = typer.Option(
        "table", "--format", help="Output format (table, json, env)"
    ),
) -> None:
    """Show environment information.

    Examples:
        revitpy doctor env
        revitpy doctor env --format json
        revitpy doctor env --format env
    """
    log_command_start("doctor env", {"format": format})

    config = get_config()

    try:
        env_collector = EnvironmentCollector(config)
        env_info = env_collector.collect()

        if format == "table":
            env_collector.display_table(env_info)
        elif format == "json":
            env_collector.display_json(env_info)
        elif format == "env":
            env_collector.display_env_format(env_info)
        else:
            raise CommandError("doctor env", f"Unknown format: {format}")

    except Exception as e:
        raise DiagnosticsError(str(e)) from e
    finally:
        log_command_complete("doctor env", 0)


@app.command()
def performance(
    benchmark: bool = typer.Option(
        False, "--benchmark", help="Run performance benchmarks"
    ),
    profile: bool = typer.Option(False, "--profile", help="Profile system performance"),
) -> None:
    """Check system performance and resource usage.

    Examples:
        revitpy doctor performance
        revitpy doctor performance --benchmark
        revitpy doctor performance --profile
    """
    start_time = time.time()
    log_command_start(
        "doctor performance",
        {
            "benchmark": benchmark,
            "profile": profile,
        },
    )

    config = get_config()

    try:
        perf_checker = PerformanceChecker(config)

        console.print("[bold blue]⚡ Checking system performance...[/bold blue]")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # System resources
            task1 = progress.add_task("Checking system resources...", total=None)
            resource_info = perf_checker.check_system_resources()
            progress.update(task1, completed=True)

            # Disk performance
            task2 = progress.add_task("Checking disk performance...", total=None)
            disk_info = perf_checker.check_disk_performance()
            progress.update(task2, completed=True)

            # Python performance
            if benchmark:
                task3 = progress.add_task("Running Python benchmarks...", total=None)
                python_perf = perf_checker.run_python_benchmarks()
                progress.update(task3, completed=True)
            else:
                python_perf = {}

            # Network performance
            task4 = progress.add_task("Checking network performance...", total=None)
            network_perf = perf_checker.check_network_performance()
            progress.update(task4, completed=True)

        # Display results
        perf_results = {
            "resources": resource_info,
            "disk": disk_info,
            "python": python_perf,
            "network": network_perf,
        }

        perf_checker.display_performance_results(perf_results)

        # Profiling
        if profile:
            console.print("\n[bold blue]🔍 System profiling...[/bold blue]")
            profile_info = perf_checker.run_system_profile()
            perf_checker.display_profile_results(profile_info)

    except Exception as e:
        raise DiagnosticsError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("doctor performance", duration)


@app.command()
def cleanup(
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Clean cache files"),
    logs: bool = typer.Option(False, "--logs", help="Clean log files"),
    temp: bool = typer.Option(True, "--temp/--no-temp", help="Clean temporary files"),
    backup: bool = typer.Option(False, "--backup", help="Create backup before cleanup"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be cleaned"),
) -> None:
    """Clean up system files and caches.

    Examples:
        revitpy doctor cleanup
        revitpy doctor cleanup --logs --backup
        revitpy doctor cleanup --dry-run
    """
    start_time = time.time()
    log_command_start(
        "doctor cleanup",
        {
            "cache": cache,
            "logs": logs,
            "temp": temp,
            "backup": backup,
            "dry_run": dry_run,
        },
    )

    config = get_config()

    try:
        cleaner = SystemCleaner(config)

        console.print("[bold blue]🧹 Cleaning up system files...[/bold blue]")

        # Find files to clean
        cleanup_plan = cleaner.plan_cleanup(
            clean_cache=cache,
            clean_logs=logs,
            clean_temp=temp,
        )

        if not cleanup_plan["files"]:
            console.print("[green]No files found to clean[/green]")
            return

        # Show cleanup plan
        cleaner.display_cleanup_plan(cleanup_plan)

        if dry_run:
            console.print("\n[yellow]Dry run - no files were cleaned[/yellow]")
            return

        # Create backup if requested
        if backup:
            backup_path = cleaner.create_backup(cleanup_plan["files"])
            console.print(f"\n[dim]Backup created: {backup_path}[/dim]")

        # Perform cleanup
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Cleaning files...", total=len(cleanup_plan["files"])
            )

            cleaned_files = []
            for file_path in cleanup_plan["files"]:
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        cleaned_files.append(file_path)
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                        cleaned_files.append(file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean {file_path}: {e}")

                progress.update(task, advance=1)

        # Show results
        total_size = sum(cleanup_plan["sizes"])
        console.print(
            f"\n[green]✓[/green] Cleaned {len(cleaned_files)} files ({cleaner.format_size(total_size)})"
        )

    except Exception as e:
        raise DiagnosticsError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("doctor cleanup", duration)


class SystemDiagnostics:
    """Performs comprehensive system diagnostics."""

    def __init__(self, config: Any, verbose: bool = False) -> None:
        """Initialize diagnostics system.

        Args:
            config: CLI configuration
            verbose: Enable verbose output
        """
        self.config = config
        self.verbose = verbose

    def check_system_info(self) -> dict[str, Any]:
        """Check basic system information.

        Returns:
            System information dictionary
        """
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture(),
            "hostname": platform.node(),
        }

    def check_python_environment(self) -> dict[str, Any]:
        """Check Python environment.

        Returns:
            Python environment information
        """
        import site

        info = {
            "version": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "path": sys.path[:5],  # First 5 entries
            "site_packages": site.getsitepackages(),
        }

        # Check if in virtual environment
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            info["virtual_env"] = os.environ.get("VIRTUAL_ENV", "Unknown")
            info["is_virtual"] = True
        else:
            info["is_virtual"] = False

        return info

    def check_revitpy_installation(self) -> dict[str, Any]:
        """Check RevitPy installation.

        Returns:
            RevitPy installation information
        """
        info = {
            "installed": False,
            "version": None,
            "location": None,
            "cli_version": None,
        }

        try:
            import revitpy

            info["installed"] = True
            info["version"] = getattr(revitpy, "__version__", "Unknown")
            info["location"] = revitpy.__file__
        except ImportError:
            pass

        # Check CLI version
        try:
            from revitpy_cli import __version__

            info["cli_version"] = __version__
        except ImportError:
            pass

        return info

    def check_revit_installation(self) -> dict[str, Any]:
        """Check Revit installation.

        Returns:
            Revit installation information
        """
        info = {
            "versions_found": [],
            "install_paths": [],
            "api_available": False,
        }

        # Common Revit installation paths
        if platform.system() == "Windows":
            base_paths = [
                Path("C:/Program Files/Autodesk"),
                Path("C:/Program Files (x86)/Autodesk"),
            ]

            for base_path in base_paths:
                if base_path.exists():
                    for revit_dir in base_path.glob("Revit*"):
                        if revit_dir.is_dir():
                            revit_exe = revit_dir / "Revit.exe"
                            if revit_exe.exists():
                                info["versions_found"].append(revit_dir.name)
                                info["install_paths"].append(str(revit_dir))

        # Check if Revit API is accessible
        try:
            import clr

            clr.AddReference("RevitAPI")
            clr.AddReference("RevitAPIUI")
            info["api_available"] = True
        except Exception:
            pass

        return info

    def check_dependencies(self) -> dict[str, Any]:
        """Check required dependencies.

        Returns:
            Dependencies information
        """
        required_packages = [
            "typer",
            "rich",
            "cookiecutter",
            "pydantic",
            "pyyaml",
            "watchdog",
            "websockets",
            "httpx",
            "packaging",
        ]

        info = {
            "required": required_packages,
            "installed": {},
            "missing": [],
        }

        for package in required_packages:
            try:
                __import__(package)
                # Try to get version
                try:
                    pkg = __import__(package)
                    version = getattr(pkg, "__version__", "Unknown")
                except AttributeError:
                    version = "Unknown"

                info["installed"][package] = version
            except ImportError:
                info["missing"].append(package)

        return info

    def check_network_connectivity(self) -> dict[str, Any]:
        """Check network connectivity.

        Returns:
            Network connectivity information
        """
        import socket

        info = {
            "dns_resolution": False,
            "registry_accessible": False,
            "github_accessible": False,
            "proxy_detected": False,
        }

        # Test DNS resolution
        try:
            socket.gethostbyname("google.com")
            info["dns_resolution"] = True
        except OSError:
            pass

        # Test registry access
        try:
            import httpx

            with httpx.Client(timeout=5.0) as client:
                response = client.get("https://pypi.org")
                if response.status_code == 200:
                    info["registry_accessible"] = True
        except Exception:
            pass

        # Test GitHub access
        try:
            import httpx

            with httpx.Client(timeout=5.0) as client:
                response = client.get("https://github.com")
                if response.status_code == 200:
                    info["github_accessible"] = True
        except Exception:
            pass

        # Check for proxy
        proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        for var in proxy_vars:
            if os.environ.get(var):
                info["proxy_detected"] = True
                break

        return info

    def check_project_configuration(self) -> dict[str, Any]:
        """Check project configuration.

        Returns:
            Project configuration information
        """
        info = {
            "has_pyproject": False,
            "has_setup_py": False,
            "has_revitpy_config": False,
            "has_vscode_settings": False,
            "git_repository": False,
        }

        current_dir = Path.cwd()

        # Check for project files
        if (current_dir / "pyproject.toml").exists():
            info["has_pyproject"] = True

        if (current_dir / "setup.py").exists():
            info["has_setup_py"] = True

        if (current_dir / "revitpy.toml").exists() or (
            current_dir / ".revitpy"
        ).exists():
            info["has_revitpy_config"] = True

        if (current_dir / ".vscode" / "settings.json").exists():
            info["has_vscode_settings"] = True

        if (current_dir / ".git").exists():
            info["git_repository"] = True

        return info

    def display_results(self, results: dict[str, Any]) -> None:
        """Display diagnostic results.

        Args:
            results: Diagnostic results
        """
        # System Information
        sys_info = results["system"]
        console.print("[bold]System Information[/bold]")
        sys_table = Table()
        sys_table.add_column("Property", style="cyan")
        sys_table.add_column("Value", style="green")

        sys_table.add_row("Platform", sys_info["platform"])
        sys_table.add_row("System", f"{sys_info['system']} {sys_info['release']}")
        sys_table.add_row("Architecture", " ".join(sys_info["architecture"]))
        sys_table.add_row("Processor", sys_info["processor"])

        console.print(sys_table)
        console.print()

        # Python Environment
        py_info = results["python"]
        console.print("[bold]Python Environment[/bold]")
        py_table = Table()
        py_table.add_column("Property", style="cyan")
        py_table.add_column("Value", style="green")

        py_table.add_row("Version", py_info["version"].split()[0])
        py_table.add_row("Executable", py_info["executable"])
        py_table.add_row(
            "Virtual Environment", "Yes" if py_info["is_virtual"] else "No"
        )
        if py_info["is_virtual"]:
            py_table.add_row("Virtual Env Path", py_info.get("virtual_env", "Unknown"))

        console.print(py_table)
        console.print()

        # RevitPy Installation
        revitpy_info = results["revitpy"]
        console.print("[bold]RevitPy Installation[/bold]")
        revitpy_table = Table()
        revitpy_table.add_column("Component", style="cyan")
        revitpy_table.add_column("Status", style="green")
        revitpy_table.add_column("Details", style="dim")

        if revitpy_info["installed"]:
            revitpy_table.add_row(
                "RevitPy Core", "✓ Installed", f"v{revitpy_info['version']}"
            )
        else:
            revitpy_table.add_row(
                "RevitPy Core", "✗ Not Found", "Install RevitPy package"
            )

        if revitpy_info["cli_version"]:
            revitpy_table.add_row(
                "RevitPy CLI", "✓ Installed", f"v{revitpy_info['cli_version']}"
            )
        else:
            revitpy_table.add_row("RevitPy CLI", "✗ Not Found", "Install RevitPy CLI")

        console.print(revitpy_table)
        console.print()

        # Dependencies
        deps_info = results["dependencies"]
        if deps_info["missing"]:
            console.print("[bold yellow]⚠️ Missing Dependencies[/bold yellow]")
            for dep in deps_info["missing"]:
                console.print(f"  ✗ {dep}")
            console.print()
        else:
            console.print("[bold green]✓ All Dependencies Satisfied[/bold green]")
            console.print()

    def count_issues(self, results: dict[str, Any]) -> int:
        """Count total issues found.

        Args:
            results: Diagnostic results

        Returns:
            Number of issues
        """
        issues = 0

        # RevitPy not installed
        if not results["revitpy"]["installed"]:
            issues += 1

        # Missing dependencies
        issues += len(results["dependencies"]["missing"])

        # No network connectivity
        if not results["network"]["dns_resolution"]:
            issues += 1

        # No Revit installation
        if not results["revit"]["versions_found"]:
            issues += 1

        return issues

    def fix_issues(self, results: dict[str, Any]) -> int:
        """Attempt to fix detected issues.

        Args:
            results: Diagnostic results

        Returns:
            Number of issues fixed
        """
        fixed = 0

        # Install missing dependencies
        missing_deps = results["dependencies"]["missing"]
        if missing_deps:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade"]
                    + missing_deps,
                    check=True,
                    capture_output=True,
                )
                fixed += len(missing_deps)
                console.print(
                    f"[green]✓[/green] Installed {len(missing_deps)} missing dependencies"
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗[/red] Failed to install dependencies: {e}")

        return fixed

    def save_report(self, results: dict[str, Any], output_file: Path) -> None:
        """Save diagnostic report to file.

        Args:
            results: Diagnostic results
            output_file: Output file path
        """
        import json

        report = {
            "timestamp": time.time(),
            "revitpy_version": results["revitpy"].get("cli_version", "Unknown"),
            "diagnostics": results,
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)


class EnvironmentCollector:
    """Collects environment information."""

    def __init__(self, config: Any) -> None:
        """Initialize environment collector.

        Args:
            config: CLI configuration
        """
        self.config = config

    def collect(self) -> dict[str, str]:
        """Collect environment variables.

        Returns:
            Environment variables dictionary
        """
        relevant_vars = [
            "PATH",
            "PYTHONPATH",
            "VIRTUAL_ENV",
            "CONDA_DEFAULT_ENV",
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "REVIT_VERSION",
            "REVIT_API_PATH",
        ]

        env_info = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value:
                env_info[var] = value

        return env_info

    def display_table(self, env_info: dict[str, str]) -> None:
        """Display environment in table format.

        Args:
            env_info: Environment information
        """
        table = Table(title="Environment Variables")
        table.add_column("Variable", style="cyan")
        table.add_column("Value", style="green")

        for var, value in sorted(env_info.items()):
            # Truncate long values
            if len(value) > 80:
                value = value[:77] + "..."
            table.add_row(var, value)

        console.print(table)

    def display_json(self, env_info: dict[str, str]) -> None:
        """Display environment in JSON format.

        Args:
            env_info: Environment information
        """
        import json

        console.print(json.dumps(env_info, indent=2))

    def display_env_format(self, env_info: dict[str, str]) -> None:
        """Display environment in shell format.

        Args:
            env_info: Environment information
        """
        for var, value in sorted(env_info.items()):
            console.print(f'export {var}="{value}"')


class PerformanceChecker:
    """Checks system performance."""

    def __init__(self, config: Any) -> None:
        """Initialize performance checker.

        Args:
            config: CLI configuration
        """
        self.config = config

    def check_system_resources(self) -> dict[str, Any]:
        """Check system resource usage.

        Returns:
            System resource information
        """
        import psutil

        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {
                "total": psutil.disk_usage("/").total,
                "free": psutil.disk_usage("/").free,
                "percent": psutil.disk_usage("/").percent,
            },
        }

    def check_disk_performance(self) -> dict[str, Any]:
        """Check disk performance.

        Returns:
            Disk performance information
        """
        # Simple disk speed test
        test_file = Path(tempfile.gettempdir()) / "revitpy_disk_test.tmp"
        test_data = b"0" * 1024 * 1024  # 1MB

        # Write test
        start_time = time.time()
        with open(test_file, "wb") as f:
            f.write(test_data)
        write_time = time.time() - start_time

        # Read test
        start_time = time.time()
        with open(test_file, "rb") as f:
            f.read()
        read_time = time.time() - start_time

        # Cleanup
        test_file.unlink()

        return {
            "write_speed_mbps": 1 / write_time if write_time > 0 else 0,
            "read_speed_mbps": 1 / read_time if read_time > 0 else 0,
        }

    def run_python_benchmarks(self) -> dict[str, Any]:
        """Run Python performance benchmarks.

        Returns:
            Benchmark results
        """
        # Simple CPU benchmark
        start_time = time.time()
        sum(i * i for i in range(100000))
        cpu_time = time.time() - start_time

        # Memory benchmark
        start_time = time.time()
        data = list(range(100000))
        del data
        memory_time = time.time() - start_time

        return {
            "cpu_benchmark_time": cpu_time,
            "memory_benchmark_time": memory_time,
        }

    def check_network_performance(self) -> dict[str, Any]:
        """Check network performance.

        Returns:
            Network performance information
        """
        # Simple connectivity test
        start_time = time.time()
        try:
            import socket

            socket.gethostbyname("google.com")
            dns_time = time.time() - start_time
            dns_success = True
        except Exception:
            dns_time = 0
            dns_success = False

        return {
            "dns_resolution_time": dns_time,
            "dns_success": dns_success,
        }

    def run_system_profile(self) -> dict[str, Any]:
        """Run system profiling.

        Returns:
            Profile information
        """
        import psutil

        # Process information
        process = psutil.Process()

        return {
            "process_id": process.pid,
            "memory_info": process.memory_info()._asdict(),
            "cpu_times": process.cpu_times()._asdict(),
            "open_files": len(process.open_files()),
            "num_threads": process.num_threads(),
        }

    def display_performance_results(self, results: dict[str, Any]) -> None:
        """Display performance results.

        Args:
            results: Performance results
        """
        # System Resources
        resources = results["resources"]
        console.print("[bold]System Resources[/bold]")
        res_table = Table()
        res_table.add_column("Resource", style="cyan")
        res_table.add_column("Usage", style="green")

        res_table.add_row("CPU", f"{resources['cpu_percent']:.1f}%")
        res_table.add_row(
            "Memory",
            f"{resources['memory_percent']:.1f}% ({self.format_bytes(resources['memory_available'])} available)",
        )
        res_table.add_row(
            "Disk",
            f"{resources['disk_usage']['percent']:.1f}% ({self.format_bytes(resources['disk_usage']['free'])} free)",
        )

        console.print(res_table)
        console.print()

        # Disk Performance
        if results.get("disk"):
            disk = results["disk"]
            console.print("[bold]Disk Performance[/bold]")
            console.print(f"Write Speed: {disk['write_speed_mbps']:.1f} MB/s")
            console.print(f"Read Speed: {disk['read_speed_mbps']:.1f} MB/s")
            console.print()

    def display_profile_results(self, profile: dict[str, Any]) -> None:
        """Display profiling results.

        Args:
            profile: Profile information
        """
        console.print("[bold]Process Profile[/bold]")
        prof_table = Table()
        prof_table.add_column("Metric", style="cyan")
        prof_table.add_column("Value", style="green")

        prof_table.add_row("Process ID", str(profile["process_id"]))
        prof_table.add_row(
            "Memory RSS", self.format_bytes(profile["memory_info"]["rss"])
        )
        prof_table.add_row(
            "Memory VMS", self.format_bytes(profile["memory_info"]["vms"])
        )
        prof_table.add_row("Open Files", str(profile["open_files"]))
        prof_table.add_row("Threads", str(profile["num_threads"]))

        console.print(prof_table)

    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format.

        Args:
            bytes_value: Bytes value

        Returns:
            Formatted string
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024
        return f"{bytes_value:.1f} PB"


class SystemCleaner:
    """Cleans up system files and caches."""

    def __init__(self, config: Any) -> None:
        """Initialize system cleaner.

        Args:
            config: CLI configuration
        """
        self.config = config

    def plan_cleanup(
        self,
        clean_cache: bool = True,
        clean_logs: bool = False,
        clean_temp: bool = True,
    ) -> dict[str, Any]:
        """Plan cleanup operations.

        Args:
            clean_cache: Clean cache files
            clean_logs: Clean log files
            clean_temp: Clean temporary files

        Returns:
            Cleanup plan
        """
        files_to_clean = []
        total_size = 0

        # Cache files
        if clean_cache:
            cache_dirs = [
                Path.home() / ".cache" / "revitpy",
                Path.home() / ".revitpy" / "cache",
                Path.cwd() / ".revitpy" / "cache",
            ]

            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    for file_path in cache_dir.rglob("*"):
                        if file_path.is_file():
                            files_to_clean.append(file_path)
                            total_size += file_path.stat().st_size

        # Log files
        if clean_logs:
            log_dirs = [
                Path.home() / ".revitpy" / "logs",
                Path.cwd() / "logs",
            ]

            for log_dir in log_dirs:
                if log_dir.exists():
                    for log_file in log_dir.glob("*.log*"):
                        files_to_clean.append(log_file)
                        total_size += log_file.stat().st_size

        # Temporary files
        if clean_temp:
            temp_patterns = [
                "**/*.tmp",
                "**/*.temp",
                "**/__pycache__",
                "**/*.pyc",
                "**/*.pyo",
            ]

            for pattern in temp_patterns:
                for file_path in Path.cwd().glob(pattern):
                    files_to_clean.append(file_path)
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                    elif file_path.is_dir():
                        total_size += self._get_dir_size(file_path)

        return {
            "files": files_to_clean,
            "sizes": [self._get_path_size(p) for p in files_to_clean],
            "total_size": total_size,
        }

    def display_cleanup_plan(self, plan: dict[str, Any]) -> None:
        """Display cleanup plan.

        Args:
            plan: Cleanup plan
        """
        console.print(f"[bold]Files to clean: {len(plan['files'])}[/bold]")
        console.print(
            f"[bold]Total size: {self.format_size(plan['total_size'])}[/bold]"
        )

        if plan["files"]:
            tree = Tree("Cleanup Plan")
            for file_path in plan["files"][:20]:  # Show first 20
                tree.add(str(file_path))

            if len(plan["files"]) > 20:
                tree.add(f"... and {len(plan['files']) - 20} more files")

            console.print(tree)

    def create_backup(self, files: list[Path]) -> Path:
        """Create backup of files before cleanup.

        Args:
            files: Files to backup

        Returns:
            Backup directory path
        """
        backup_dir = (
            Path.home() / ".revitpy" / "backups" / f"cleanup_{int(time.time())}"
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        for file_path in files[:10]:  # Backup first 10 files only
            if file_path.is_file():
                backup_file = backup_dir / file_path.name
                shutil.copy2(file_path, backup_file)

        return backup_dir

    def _get_path_size(self, path: Path) -> int:
        """Get size of path (file or directory).

        Args:
            path: Path to check

        Returns:
            Size in bytes
        """
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return self._get_dir_size(path)
        return 0

    def _get_dir_size(self, directory: Path) -> int:
        """Get total size of directory.

        Args:
            directory: Directory path

        Returns:
            Total size in bytes
        """
        total_size = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size

    def format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
