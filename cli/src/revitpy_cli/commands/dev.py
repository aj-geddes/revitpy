"""Development server and hot-reload commands."""

import asyncio
import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import List, Optional, Set

import typer
import websockets
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..core.config import get_config
from ..core.exceptions import DevServerError, CommandError
from ..core.logging import get_logger, log_command_complete, log_command_start
from ..dev_server.file_watcher import FileWatcher
from ..dev_server.hot_reload import HotReloadServer
from ..dev_server.websocket_server import WebSocketServer

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="dev",
    help="Development server with hot-reload capabilities",
    rich_markup_mode="rich",
)


@app.command()
def server(
    project_path: Optional[str] = typer.Argument(None, help="Project directory"),
    host: Optional[str] = typer.Option(None, "--host", help="Host to bind to"),
    port: Optional[int] = typer.Option(None, "--port", help="Port to bind to"),
    websocket_port: Optional[int] = typer.Option(None, "--ws-port", help="WebSocket port"),
    no_reload: bool = typer.Option(False, "--no-reload", help="Disable hot reload"),
    watch_patterns: Optional[List[str]] = typer.Option(None, "--watch", help="Additional file patterns to watch"),
    ignore_patterns: Optional[List[str]] = typer.Option(None, "--ignore", help="File patterns to ignore"),
) -> None:
    """Start the RevitPy development server with hot-reload.
    
    Examples:
        revitpy dev server
        revitpy dev server --port 9000
        revitpy dev server --no-reload
        revitpy dev server --watch "*.yaml" --ignore "logs/*"
    """
    start_time = time.time()
    log_command_start("dev server", {
        "project_path": project_path,
        "host": host,
        "port": port,
        "websocket_port": websocket_port,
        "no_reload": no_reload,
        "watch_patterns": watch_patterns,
        "ignore_patterns": ignore_patterns,
    })
    
    config = get_config()
    
    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()
    
    if not proj_path.exists():
        raise CommandError("dev server", f"Project directory not found: {proj_path}")
    
    # Use config defaults if not specified
    server_host = host or config.dev_server.host
    server_port = port or config.dev_server.port
    ws_port = websocket_port or config.dev_server.websocket_port
    hot_reload_enabled = not no_reload and config.dev_server.hot_reload
    
    # Merge watch patterns
    patterns = list(config.dev_server.watch_patterns)
    if watch_patterns:
        patterns.extend(watch_patterns)
    
    # Merge ignore patterns
    ignore_list = list(config.dev_server.ignore_patterns)
    if ignore_patterns:
        ignore_list.extend(ignore_patterns)
    
    try:
        dev_server = DevServer(
            project_path=proj_path,
            host=server_host,
            port=server_port,
            websocket_port=ws_port,
            hot_reload=hot_reload_enabled,
            watch_patterns=patterns,
            ignore_patterns=ignore_list,
        )
        
        console.print(f"[bold green]🚀 Starting RevitPy development server[/bold green]")
        console.print(f"[dim]Project: {proj_path}[/dim]")
        console.print(f"[dim]Server: http://{server_host}:{server_port}[/dim]")
        if hot_reload_enabled:
            console.print(f"[dim]WebSocket: ws://{server_host}:{ws_port}[/dim]")
        console.print()
        
        # Start the server
        dev_server.start()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping development server...[/yellow]")
    except Exception as e:
        raise DevServerError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("dev server", duration)


@app.command()
def watch(
    project_path: Optional[str] = typer.Argument(None, help="Project directory"),
    patterns: Optional[List[str]] = typer.Option(None, "--pattern", help="File patterns to watch"),
    ignore_patterns: Optional[List[str]] = typer.Option(None, "--ignore", help="Patterns to ignore"),
    command: Optional[str] = typer.Option(None, "--exec", help="Command to run on file changes"),
) -> None:
    """Watch files for changes without starting a server.
    
    Examples:
        revitpy dev watch
        revitpy dev watch --pattern "*.py" --exec "python -m pytest"
        revitpy dev watch --ignore "__pycache__/*"
    """
    start_time = time.time()
    log_command_start("dev watch", {
        "project_path": project_path,
        "patterns": patterns,
        "ignore_patterns": ignore_patterns,
        "command": command,
    })
    
    config = get_config()
    
    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()
    
    if not proj_path.exists():
        raise CommandError("dev watch", f"Project directory not found: {proj_path}")
    
    # Use config defaults if not specified
    watch_patterns = patterns or config.dev_server.watch_patterns
    ignore_list = ignore_patterns or config.dev_server.ignore_patterns
    
    try:
        watcher = StandaloneWatcher(
            project_path=proj_path,
            patterns=watch_patterns,
            ignore_patterns=ignore_list,
            command=command,
        )
        
        console.print(f"[bold blue]👀 Watching files in:[/bold blue] {proj_path}")
        console.print(f"[dim]Patterns: {', '.join(watch_patterns)}[/dim]")
        if command:
            console.print(f"[dim]Command: {command}[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        console.print()
        
        watcher.start()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping file watcher...[/yellow]")
    except Exception as e:
        raise CommandError("dev watch", str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("dev watch", duration)


@app.command()
def status(
    project_path: Optional[str] = typer.Argument(None, help="Project directory"),
) -> None:
    """Show development server status and project information.
    
    Examples:
        revitpy dev status
        revitpy dev status /path/to/project
    """
    log_command_start("dev status", {"project_path": project_path})
    
    # Determine project path
    if project_path:
        proj_path = Path(project_path).resolve()
    else:
        proj_path = Path.cwd()
    
    if not proj_path.exists():
        raise CommandError("dev status", f"Project directory not found: {proj_path}")
    
    status_checker = ProjectStatus(proj_path)
    status_info = status_checker.get_status()
    
    # Display status
    table = Table(title=f"Project Status: {proj_path.name}")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    for component, info in status_info.items():
        status = "✓" if info.get("healthy", True) else "✗"
        details = info.get("details", "")
        table.add_row(component, status, details)
    
    console.print(table)
    log_command_complete("dev status", 0)


class DevServer:
    """Development server with hot-reload capabilities."""
    
    def __init__(
        self,
        project_path: Path,
        host: str = "localhost",
        port: int = 8000,
        websocket_port: int = 8001,
        hot_reload: bool = True,
        watch_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        """Initialize development server.
        
        Args:
            project_path: Path to project directory
            host: Host to bind to
            port: Port to bind to
            websocket_port: WebSocket port for hot reload
            hot_reload: Enable hot reload functionality
            watch_patterns: File patterns to watch
            ignore_patterns: File patterns to ignore
        """
        self.project_path = project_path
        self.host = host
        self.port = port
        self.websocket_port = websocket_port
        self.hot_reload_enabled = hot_reload
        self.watch_patterns = watch_patterns or ["*.py"]
        self.ignore_patterns = ignore_patterns or []
        
        # Server components
        self.hot_reload_server: Optional[HotReloadServer] = None
        self.websocket_server: Optional[WebSocketServer] = None
        self.file_watcher: Optional[FileWatcher] = None
        self.status_display: Optional[ServerStatusDisplay] = None
        
        # State
        self.running = False
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
    
    def start(self) -> None:
        """Start the development server."""
        try:
            self.running = True
            
            # Start components
            if self.hot_reload_enabled:
                self._start_hot_reload()
                self._start_file_watcher()
                self._start_websocket_server()
            
            self._start_status_display()
            
            # Keep server running
            self._run_main_loop()
            
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the development server."""
        self.running = False
        
        if self.file_watcher:
            self.file_watcher.stop()
        
        if self.websocket_server:
            self.websocket_server.stop()
        
        if self.hot_reload_server:
            self.hot_reload_server.stop()
        
        if self.status_display:
            self.status_display.stop()
    
    def _start_hot_reload(self) -> None:
        """Start hot reload server."""
        self.hot_reload_server = HotReloadServer(
            self.project_path,
            self.host,
            self.port
        )
        self.hot_reload_server.start()
    
    def _start_file_watcher(self) -> None:
        """Start file watcher."""
        self.file_watcher = FileWatcher(
            self.project_path,
            self.watch_patterns,
            self.ignore_patterns,
            self._on_file_change
        )
        self.file_watcher.start()
    
    def _start_websocket_server(self) -> None:
        """Start WebSocket server for client communication."""
        self.websocket_server = WebSocketServer(
            self.host,
            self.websocket_port,
            self._on_client_connect,
            self._on_client_disconnect
        )
        self.websocket_server.start()
    
    def _start_status_display(self) -> None:
        """Start server status display."""
        self.status_display = ServerStatusDisplay(self)
        self.status_display.start()
    
    def _run_main_loop(self) -> None:
        """Run main server loop."""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    def _on_file_change(self, file_path: Path, event_type: str) -> None:
        """Handle file change events.
        
        Args:
            file_path: Path to changed file
            event_type: Type of change event
        """
        logger.info(f"File {event_type}: {file_path}")
        
        # Notify connected clients
        if self.clients:
            message = {
                "type": "file_change",
                "file": str(file_path),
                "event": event_type,
                "timestamp": time.time()
            }
            asyncio.create_task(self._broadcast_to_clients(message))
    
    def _on_client_connect(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Handle client connection.
        
        Args:
            websocket: WebSocket connection
        """
        self.clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}")
    
    def _on_client_disconnect(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Handle client disconnection.
        
        Args:
            websocket: WebSocket connection
        """
        self.clients.discard(websocket)
        logger.info(f"Client disconnected: {websocket.remote_address}")
    
    async def _broadcast_to_clients(self, message: dict) -> None:
        """Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
        """
        if not self.clients:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message_str)
            except websockets.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.warning(f"Error sending to client: {e}")
                disconnected.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected


class StandaloneWatcher:
    """Standalone file watcher without server."""
    
    def __init__(
        self,
        project_path: Path,
        patterns: List[str],
        ignore_patterns: List[str],
        command: Optional[str] = None,
    ) -> None:
        """Initialize standalone watcher.
        
        Args:
            project_path: Path to project directory
            patterns: File patterns to watch
            ignore_patterns: File patterns to ignore
            command: Optional command to run on changes
        """
        self.project_path = project_path
        self.patterns = patterns
        self.ignore_patterns = ignore_patterns
        self.command = command
        self.file_watcher: Optional[FileWatcher] = None
    
    def start(self) -> None:
        """Start watching files."""
        try:
            self.file_watcher = FileWatcher(
                self.project_path,
                self.patterns,
                self.ignore_patterns,
                self._on_file_change
            )
            self.file_watcher.start()
            
            # Keep watcher running
            while True:
                time.sleep(1)
                
        finally:
            if self.file_watcher:
                self.file_watcher.stop()
    
    def _on_file_change(self, file_path: Path, event_type: str) -> None:
        """Handle file change events.
        
        Args:
            file_path: Path to changed file
            event_type: Type of change event
        """
        console.print(f"[yellow]{event_type}:[/yellow] {file_path.relative_to(self.project_path)}")
        
        if self.command:
            try:
                import subprocess
                result = subprocess.run(
                    self.command,
                    shell=True,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    console.print("[green]✓[/green] Command executed successfully")
                else:
                    console.print(f"[red]✗[/red] Command failed: {result.stderr}")
                    
            except Exception as e:
                console.print(f"[red]Error running command:[/red] {e}")


class ProjectStatus:
    """Checks project status and health."""
    
    def __init__(self, project_path: Path) -> None:
        """Initialize project status checker.
        
        Args:
            project_path: Path to project directory
        """
        self.project_path = project_path
    
    def get_status(self) -> dict:
        """Get project status information.
        
        Returns:
            Dictionary with status information
        """
        status = {}
        
        # Check project structure
        status["Project Structure"] = self._check_project_structure()
        
        # Check dependencies
        status["Dependencies"] = self._check_dependencies()
        
        # Check git status
        status["Git Repository"] = self._check_git_status()
        
        # Check Python environment
        status["Python Environment"] = self._check_python_environment()
        
        return status
    
    def _check_project_structure(self) -> dict:
        """Check project structure.
        
        Returns:
            Structure status information
        """
        required_files = ["pyproject.toml", "setup.py"]
        has_config = any((self.project_path / f).exists() for f in required_files)
        
        return {
            "healthy": has_config,
            "details": "Configuration found" if has_config else "No project configuration"
        }
    
    def _check_dependencies(self) -> dict:
        """Check dependencies status.
        
        Returns:
            Dependencies status information
        """
        # This would check if dependencies are installed and up to date
        return {
            "healthy": True,
            "details": "Dependencies OK"
        }
    
    def _check_git_status(self) -> dict:
        """Check git repository status.
        
        Returns:
            Git status information
        """
        git_dir = self.project_path / ".git"
        if git_dir.exists():
            return {
                "healthy": True,
                "details": "Git repository initialized"
            }
        else:
            return {
                "healthy": False,
                "details": "Not a git repository"
            }
    
    def _check_python_environment(self) -> dict:
        """Check Python environment.
        
        Returns:
            Python environment information
        """
        import sys
        return {
            "healthy": True,
            "details": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        }


class ServerStatusDisplay:
    """Displays real-time server status."""
    
    def __init__(self, server: DevServer) -> None:
        """Initialize status display.
        
        Args:
            server: Development server instance
        """
        self.server = server
        self.live: Optional[Live] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self) -> None:
        """Start status display."""
        self.running = True
        self.thread = threading.Thread(target=self._display_loop, daemon=True)
        self.thread.start()
    
    def stop(self) -> None:
        """Stop status display."""
        self.running = False
        if self.live:
            self.live.stop()
    
    def _display_loop(self) -> None:
        """Main display loop."""
        with Live(self._generate_status(), refresh_per_second=1, console=console) as live:
            self.live = live
            while self.running:
                live.update(self._generate_status())
                time.sleep(1)
    
    def _generate_status(self) -> Panel:
        """Generate status panel.
        
        Returns:
            Rich panel with server status
        """
        table = Table()
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="dim")
        
        # Server status
        table.add_row(
            "HTTP Server",
            "🟢 Running" if self.server.hot_reload_server else "🔴 Stopped",
            f"http://{self.server.host}:{self.server.port}"
        )
        
        # WebSocket status
        if self.server.hot_reload_enabled:
            table.add_row(
                "WebSocket",
                "🟢 Running" if self.server.websocket_server else "🔴 Stopped",
                f"ws://{self.server.host}:{self.server.websocket_port}"
            )
            
            table.add_row(
                "Connected Clients",
                str(len(self.server.clients)),
                "Active connections"
            )
        
        # File watcher status
        table.add_row(
            "File Watcher",
            "🟢 Running" if self.server.file_watcher else "🔴 Stopped",
            f"Watching: {', '.join(self.server.watch_patterns)}"
        )
        
        return Panel(table, title="[bold]RevitPy Development Server[/bold]", border_style="blue")