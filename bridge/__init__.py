"""
PyRevit-RevitPy Interoperability Bridge

This module provides seamless data exchange and workflow integration between
PyRevit and RevitPy, positioning them as complementary platforms.

Core Components:
- Data serialization/deserialization for Revit elements
- Multiple communication protocols (named pipes, WebSocket, file-based)
- PyRevit integration library
- RevitPy analysis handlers
- Error handling and recovery mechanisms

Example Usage:
    # PyRevit side
    import revitpy_bridge
    elements = get_selected_walls()
    results = revitpy_bridge.execute_analysis(elements, "energy_performance")
    
    # RevitPy side
    from revitpy.integrations import pyrevit_bridge
    @pyrevit_bridge.analysis_handler("energy_performance")
    def analyze_energy(elements_data, parameters):
        return {"efficiency": 0.85, "recommendations": [...]}
"""

from .core.bridge_manager import BridgeManager
from .core.config import BridgeConfig
from .serialization.element_serializer import RevitElementSerializer
from .communication.pipe_server import NamedPipeServer
from .communication.websocket_server import WebSocketBridgeServer
from .communication.file_exchange import FileExchangeHandler

__version__ = "1.0.0"
__author__ = "RevitPy Development Team"

# Export main bridge components
__all__ = [
    "BridgeManager",
    "BridgeConfig", 
    "RevitElementSerializer",
    "NamedPipeServer",
    "WebSocketBridgeServer",
    "FileExchangeHandler",
    "create_bridge",
    "get_bridge_instance"
]

# Global bridge instance
_bridge_instance = None

def create_bridge(config=None):
    """Create a new bridge instance with optional configuration."""
    global _bridge_instance
    if config is None:
        config = BridgeConfig()
    _bridge_instance = BridgeManager(config)
    return _bridge_instance

def get_bridge_instance():
    """Get the current bridge instance, creating one if needed."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = create_bridge()
    return _bridge_instance