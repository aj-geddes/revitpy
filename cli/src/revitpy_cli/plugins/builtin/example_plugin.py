"""Example built-in plugin for RevitPy CLI."""

from rich.console import Console

from ...core.logging import get_logger

logger = get_logger(__name__)
console = Console()


class ExamplePlugin:
    """Example plugin demonstrating the plugin interface."""
    
    name = "example"
    version = "1.0.0"
    description = "Example plugin demonstrating RevitPy CLI plugin system"
    
    def __init__(self) -> None:
        """Initialize the example plugin."""
        self.initialized = False
    
    def initialize(self) -> None:
        """Initialize the plugin."""
        logger.info("Initializing example plugin")
        console.print("[dim]Example plugin initialized[/dim]")
        self.initialized = True
    
    def cleanup(self) -> None:
        """Cleanup plugin resources."""
        logger.info("Cleaning up example plugin")
        console.print("[dim]Example plugin cleaned up[/dim]")
        self.initialized = False
    
    def say_hello(self, name: str = "World") -> None:
        """Example plugin method.
        
        Args:
            name: Name to greet
        """
        if not self.initialized:
            console.print("[red]Plugin not initialized[/red]")
            return
        
        console.print(f"[green]Hello, {name}! - from Example Plugin[/green]")