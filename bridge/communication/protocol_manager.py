"""
Protocol manager for coordinating multiple communication protocols.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List, Union
from enum import Enum

from ..core.config import CommunicationConfig
from ..core.exceptions import BridgeConnectionError, BridgeTimeoutError
from .pipe_server import NamedPipeServer
from .websocket_server import WebSocketBridgeServer
from .file_exchange import FileExchangeHandler


class ProtocolType(Enum):
    """Communication protocol types."""
    
    NAMED_PIPE = "named_pipe"
    WEBSOCKET = "websocket"
    FILE_EXCHANGE = "file_exchange"


class ProtocolManager:
    """Manages multiple communication protocols and routes messages appropriately."""
    
    def __init__(self, config: CommunicationConfig):
        """Initialize protocol manager."""
        self.config = config
        self.logger = logging.getLogger('revitpy_bridge.protocol_manager')
        
        # Protocol handlers
        self.pipe_server: Optional[NamedPipeServer] = None
        self.websocket_server: Optional[WebSocketBridgeServer] = None
        self.file_handler = FileExchangeHandler(config)
        
        # Protocol state
        self.enabled_protocols: Dict[ProtocolType, bool] = {
            ProtocolType.NAMED_PIPE: True,
            ProtocolType.WEBSOCKET: True,
            ProtocolType.FILE_EXCHANGE: True
        }
        
        # Message routing
        self.message_handlers: Dict[ProtocolType, Callable] = {}
        self.default_message_handler: Optional[Callable] = None
        
        # Statistics
        self.stats = {
            'messages_routed': {
                'named_pipe': 0,
                'websocket': 0,
                'file_exchange': 0
            },
            'errors': {
                'named_pipe': 0,
                'websocket': 0,
                'file_exchange': 0
            },
            'active_connections': {
                'named_pipe': 0,
                'websocket': 0
            }
        }
    
    async def start_all_protocols(self):
        """Start all enabled communication protocols."""
        self.logger.info("Starting all communication protocols...")
        
        startup_tasks = []
        
        # Start named pipe server
        if self.enabled_protocols[ProtocolType.NAMED_PIPE]:
            try:
                self.pipe_server = NamedPipeServer(self.config)
                self.pipe_server.set_message_handler(self._handle_pipe_message)
                startup_tasks.append(self.pipe_server.start())
                self.logger.info("Named pipe server initialization queued")
            except Exception as e:
                self.logger.error(f"Failed to initialize named pipe server: {e}")
                self.enabled_protocols[ProtocolType.NAMED_PIPE] = False
        
        # Start WebSocket server
        if self.enabled_protocols[ProtocolType.WEBSOCKET]:
            try:
                self.websocket_server = WebSocketBridgeServer(self.config)
                self.websocket_server.set_message_handler(self._handle_websocket_message)
                startup_tasks.append(self.websocket_server.start())
                self.logger.info("WebSocket server initialization queued")
            except Exception as e:
                self.logger.error(f"Failed to initialize WebSocket server: {e}")
                self.enabled_protocols[ProtocolType.WEBSOCKET] = False
        
        # Execute startup tasks
        if startup_tasks:
            try:
                await asyncio.gather(*startup_tasks, return_exceptions=True)
                self.logger.info("All protocols started successfully")
            except Exception as e:
                self.logger.error(f"Error during protocol startup: {e}")
                raise BridgeConnectionError("protocol_manager", f"Failed to start protocols: {e}")
        
        # Start background tasks
        asyncio.create_task(self._update_statistics_task())
    
    async def stop_all_protocols(self):
        """Stop all communication protocols."""
        self.logger.info("Stopping all communication protocols...")
        
        shutdown_tasks = []
        
        # Stop named pipe server
        if self.pipe_server:
            shutdown_tasks.append(self.pipe_server.stop())
        
        # Stop WebSocket server
        if self.websocket_server:
            shutdown_tasks.append(self.websocket_server.stop())
        
        # Execute shutdown tasks
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.logger.info("All protocols stopped")
    
    def set_message_handler(self, protocol: ProtocolType, handler: Callable):
        """Set message handler for specific protocol."""
        self.message_handlers[protocol] = handler
        self.logger.info(f"Set message handler for protocol: {protocol.value}")
    
    def set_default_message_handler(self, handler: Callable):
        """Set default message handler for all protocols."""
        self.default_message_handler = handler
        self.logger.info("Set default message handler for all protocols")
    
    async def _handle_pipe_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message from named pipe."""
        try:
            self.stats['messages_routed']['named_pipe'] += 1
            
            # Use protocol-specific handler if available
            if ProtocolType.NAMED_PIPE in self.message_handlers:
                return await self.message_handlers[ProtocolType.NAMED_PIPE](message)
            
            # Use default handler
            elif self.default_message_handler:
                return await self.default_message_handler(message)
            
            # No handler available
            else:
                return {
                    'error': 'No message handler configured',
                    'protocol': 'named_pipe'
                }
                
        except Exception as e:
            self.stats['errors']['named_pipe'] += 1
            self.logger.error(f"Error handling named pipe message: {e}")
            return {
                'error': str(e),
                'protocol': 'named_pipe'
            }
    
    async def _handle_websocket_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message from WebSocket."""
        try:
            self.stats['messages_routed']['websocket'] += 1
            
            # Use protocol-specific handler if available
            if ProtocolType.WEBSOCKET in self.message_handlers:
                return await self.message_handlers[ProtocolType.WEBSOCKET](message)
            
            # Use default handler
            elif self.default_message_handler:
                return await self.default_message_handler(message)
            
            # No handler available
            else:
                return {
                    'error': 'No message handler configured',
                    'protocol': 'websocket'
                }
                
        except Exception as e:
            self.stats['errors']['websocket'] += 1
            self.logger.error(f"Error handling WebSocket message: {e}")
            return {
                'error': str(e),
                'protocol': 'websocket'
            }
    
    async def broadcast_message(self, message: Dict[str, Any], 
                              exclude_protocols: Optional[List[ProtocolType]] = None) -> Dict[str, int]:
        """Broadcast message across all active protocols."""
        exclude_protocols = exclude_protocols or []
        results = {}
        
        # Broadcast via named pipe
        if (self.pipe_server and 
            ProtocolType.NAMED_PIPE not in exclude_protocols and
            self.enabled_protocols[ProtocolType.NAMED_PIPE]):
            try:
                count = await self.pipe_server.broadcast_message(message)
                results['named_pipe'] = count
            except Exception as e:
                self.logger.error(f"Error broadcasting via named pipe: {e}")
                results['named_pipe'] = 0
        
        # Broadcast via WebSocket
        if (self.websocket_server and 
            ProtocolType.WEBSOCKET not in exclude_protocols and
            self.enabled_protocols[ProtocolType.WEBSOCKET]):
            try:
                count = await self.websocket_server.broadcast_message(message)
                results['websocket'] = count
            except Exception as e:
                self.logger.error(f"Error broadcasting via WebSocket: {e}")
                results['websocket'] = 0
        
        return results
    
    async def send_to_protocol(self, protocol: ProtocolType, 
                              connection_id: str, 
                              message: Dict[str, Any]) -> bool:
        """Send message to specific connection on specific protocol."""
        try:
            if protocol == ProtocolType.NAMED_PIPE and self.pipe_server:
                return await self.pipe_server.send_to_connection(connection_id, message)
            
            elif protocol == ProtocolType.WEBSOCKET and self.websocket_server:
                return await self.websocket_server.send_to_connection(connection_id, message)
            
            else:
                self.logger.warning(f"Protocol not available or not supported: {protocol}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending to {protocol.value} connection {connection_id}: {e}")
            return False
    
    async def create_file_exchange_request(self, request_data: Dict[str, Any], 
                                         file_id: Optional[str] = None) -> str:
        """Create file exchange request."""
        try:
            file_id = await self.file_handler.create_request_file(request_data, file_id)
            self.stats['messages_routed']['file_exchange'] += 1
            return file_id
        except Exception as e:
            self.stats['errors']['file_exchange'] += 1
            raise
    
    async def get_file_exchange_response(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get file exchange response."""
        try:
            # Look for response file
            response_files = await self.file_handler.list_files(
                file_type='response', 
                status='completed'
            )
            
            for response_file in response_files:
                if response_file.metadata and response_file.metadata.get('request_id') == request_id:
                    response_data = await self.file_handler.read_file(
                        response_file.file_path.stem
                    )
                    return response_data
            
            return None
            
        except Exception as e:
            self.stats['errors']['file_exchange'] += 1
            self.logger.error(f"Error getting file exchange response: {e}")
            return None
    
    def enable_protocol(self, protocol: ProtocolType):
        """Enable a specific protocol."""
        self.enabled_protocols[protocol] = True
        self.logger.info(f"Enabled protocol: {protocol.value}")
    
    def disable_protocol(self, protocol: ProtocolType):
        """Disable a specific protocol."""
        self.enabled_protocols[protocol] = False
        self.logger.info(f"Disabled protocol: {protocol.value}")
    
    def is_protocol_enabled(self, protocol: ProtocolType) -> bool:
        """Check if a protocol is enabled."""
        return self.enabled_protocols.get(protocol, False)
    
    def get_active_connections(self) -> Dict[str, List[str]]:
        """Get active connections for all protocols."""
        connections = {}
        
        if self.pipe_server:
            connections['named_pipe'] = self.pipe_server.get_active_connections()
        
        if self.websocket_server:
            connections['websocket'] = self.websocket_server.get_active_connections()
        
        return connections
    
    def get_protocol_statistics(self) -> Dict[str, Any]:
        """Get statistics for all protocols."""
        protocol_stats = {}
        
        if self.pipe_server:
            protocol_stats['named_pipe'] = self.pipe_server.get_statistics()
        
        if self.websocket_server:
            protocol_stats['websocket'] = self.websocket_server.get_statistics()
        
        return {
            'manager_stats': self.stats,
            'protocol_stats': protocol_stats,
            'enabled_protocols': {p.value: enabled for p, enabled in self.enabled_protocols.items()}
        }
    
    async def _update_statistics_task(self):
        """Background task to update connection statistics."""
        while True:
            try:
                # Update active connection counts
                if self.pipe_server:
                    self.stats['active_connections']['named_pipe'] = (
                        self.pipe_server.get_connection_count()
                    )
                
                if self.websocket_server:
                    self.stats['active_connections']['websocket'] = len(
                        self.websocket_server.get_active_connections()
                    )
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error updating statistics: {e}")
                await asyncio.sleep(60)  # Longer pause on error
    
    def select_optimal_protocol(self, message_size: int, 
                               priority: str = "balanced") -> ProtocolType:
        """Select optimal protocol based on message characteristics."""
        
        # Large messages should use file exchange
        if message_size > 1024 * 1024:  # > 1MB
            if self.enabled_protocols[ProtocolType.FILE_EXCHANGE]:
                return ProtocolType.FILE_EXCHANGE
        
        # Real-time messages should use WebSocket or named pipe
        if priority == "realtime":
            if self.enabled_protocols[ProtocolType.WEBSOCKET]:
                return ProtocolType.WEBSOCKET
            elif self.enabled_protocols[ProtocolType.NAMED_PIPE]:
                return ProtocolType.NAMED_PIPE
        
        # High throughput should use named pipe
        elif priority == "throughput":
            if self.enabled_protocols[ProtocolType.NAMED_PIPE]:
                return ProtocolType.NAMED_PIPE
            elif self.enabled_protocols[ProtocolType.WEBSOCKET]:
                return ProtocolType.WEBSOCKET
        
        # Default balanced approach
        else:
            # Prefer WebSocket for moderate-sized messages
            if message_size < 100 * 1024 and self.enabled_protocols[ProtocolType.WEBSOCKET]:
                return ProtocolType.WEBSOCKET
            # Named pipe for larger messages
            elif self.enabled_protocols[ProtocolType.NAMED_PIPE]:
                return ProtocolType.NAMED_PIPE
            # File exchange as fallback
            elif self.enabled_protocols[ProtocolType.FILE_EXCHANGE]:
                return ProtocolType.FILE_EXCHANGE
        
        # Return first available protocol as last resort
        for protocol, enabled in self.enabled_protocols.items():
            if enabled:
                return protocol
        
        raise BridgeConnectionError("protocol_selection", "No protocols available")