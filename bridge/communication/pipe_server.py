"""
Named pipe server for high-performance local communication.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import os
import tempfile

from ..core.config import CommunicationConfig
from ..core.exceptions import BridgeConnectionError, BridgeTimeoutError


class NamedPipeConnection:
    """Represents a single named pipe connection."""
    
    def __init__(self, pipe_path: str, connection_id: str):
        """Initialize pipe connection."""
        self.pipe_path = pipe_path
        self.connection_id = connection_id
        self.is_connected = False
        self.last_activity = time.time()
        self.read_pipe = None
        self.write_pipe = None
    
    async def open(self):
        """Open pipe connection."""
        try:
            # Create named pipes (FIFOs on Unix-like systems)
            read_pipe_path = f"{self.pipe_path}_read_{self.connection_id}"
            write_pipe_path = f"{self.pipe_path}_write_{self.connection_id}"
            
            # Create FIFOs if they don't exist
            if not os.path.exists(read_pipe_path):
                os.mkfifo(read_pipe_path)
            if not os.path.exists(write_pipe_path):
                os.mkfifo(write_pipe_path)
            
            # Open pipes
            self.read_pipe = open(read_pipe_path, 'r')
            self.write_pipe = open(write_pipe_path, 'w')
            
            self.is_connected = True
            self.last_activity = time.time()
            
        except Exception as e:
            raise BridgeConnectionError("named_pipe", f"Failed to open pipe connection: {e}")
    
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send message through pipe."""
        try:
            if not self.is_connected or not self.write_pipe:
                return False
            
            message_json = json.dumps(message)
            self.write_pipe.write(message_json + '\n')
            self.write_pipe.flush()
            
            self.last_activity = time.time()
            return True
            
        except Exception as e:
            logging.error(f"Failed to send message through pipe: {e}")
            return False
    
    async def receive(self, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Receive message from pipe."""
        try:
            if not self.is_connected or not self.read_pipe:
                return None
            
            # Read with timeout
            line = self.read_pipe.readline()
            if line:
                self.last_activity = time.time()
                return json.loads(line.strip())
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to receive message from pipe: {e}")
            return None
    
    async def close(self):
        """Close pipe connection."""
        try:
            if self.read_pipe:
                self.read_pipe.close()
                self.read_pipe = None
            
            if self.write_pipe:
                self.write_pipe.close()
                self.write_pipe = None
            
            # Clean up FIFO files
            read_pipe_path = f"{self.pipe_path}_read_{self.connection_id}"
            write_pipe_path = f"{self.pipe_path}_write_{self.connection_id}"
            
            for pipe_path in [read_pipe_path, write_pipe_path]:
                if os.path.exists(pipe_path):
                    os.unlink(pipe_path)
            
            self.is_connected = False
            
        except Exception as e:
            logging.error(f"Error closing pipe connection: {e}")


class NamedPipeServer:
    """Named pipe server for inter-process communication."""
    
    def __init__(self, config: CommunicationConfig):
        """Initialize named pipe server."""
        self.config = config
        self.logger = logging.getLogger('revitpy_bridge.pipe_server')
        
        # Server state
        self.is_running = False
        self.connections: Dict[str, NamedPipeConnection] = {}
        self.message_handler: Optional[Callable] = None
        
        # Pipe configuration
        self.base_pipe_path = self._get_pipe_path()
        self.server_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }
    
    def _get_pipe_path(self) -> str:
        """Get the base path for named pipes."""
        # Use temp directory for pipes
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, f"revitpy_{self.config.pipe_name}")
    
    def set_message_handler(self, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Set message handler for incoming messages."""
        self.message_handler = handler
    
    async def start(self):
        """Start the named pipe server."""
        if self.is_running:
            self.logger.warning("Pipe server is already running")
            return
        
        self.logger.info("Starting named pipe server...")
        self.is_running = True
        
        try:
            # Start server in separate thread
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.logger.info(f"Named pipe server started at: {self.base_pipe_path}")
            
        except Exception as e:
            self.is_running = False
            raise BridgeConnectionError("named_pipe", f"Failed to start pipe server: {e}")
    
    async def stop(self):
        """Stop the named pipe server."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping named pipe server...")
        self.is_running = False
        
        # Close all connections
        for connection in list(self.connections.values()):
            await connection.close()
        
        self.connections.clear()
        
        # Wait for server thread to finish
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        
        self.logger.info("Named pipe server stopped")
    
    def _run_server(self):
        """Run the pipe server in a separate thread."""
        try:
            # Create main control pipe
            control_pipe_path = f"{self.base_pipe_path}_control"
            
            if not os.path.exists(control_pipe_path):
                os.mkfifo(control_pipe_path)
            
            self.logger.info(f"Listening on control pipe: {control_pipe_path}")
            
            while self.is_running:
                try:
                    # Listen for connection requests
                    with open(control_pipe_path, 'r') as control_pipe:
                        while self.is_running:
                            line = control_pipe.readline()
                            if line:
                                self._handle_control_message(line.strip())
                            
                            # Clean up inactive connections
                            self._cleanup_inactive_connections()
                            
                            time.sleep(0.1)  # Small delay to prevent busy loop
                
                except Exception as e:
                    if self.is_running:
                        self.logger.error(f"Error in server loop: {e}")
                        self.stats['errors'] += 1
                        time.sleep(1)  # Brief pause on error
        
        finally:
            # Clean up control pipe
            control_pipe_path = f"{self.base_pipe_path}_control"
            if os.path.exists(control_pipe_path):
                os.unlink(control_pipe_path)
    
    def _handle_control_message(self, message: str):
        """Handle control messages for connection management."""
        try:
            control_data = json.loads(message)
            command = control_data.get('command')
            
            if command == 'connect':
                connection_id = control_data.get('connection_id')
                if connection_id:
                    asyncio.run(self._create_connection(connection_id))
            
            elif command == 'disconnect':
                connection_id = control_data.get('connection_id')
                if connection_id and connection_id in self.connections:
                    asyncio.run(self.connections[connection_id].close())
                    del self.connections[connection_id]
                    self.stats['connections_closed'] += 1
            
        except Exception as e:
            self.logger.error(f"Error handling control message: {e}")
    
    async def _create_connection(self, connection_id: str):
        """Create a new pipe connection."""
        try:
            connection = NamedPipeConnection(self.base_pipe_path, connection_id)
            await connection.open()
            
            self.connections[connection_id] = connection
            self.stats['connections_created'] += 1
            
            self.logger.info(f"Created pipe connection: {connection_id}")
            
            # Start message handling for this connection
            asyncio.create_task(self._handle_connection_messages(connection_id))
            
        except Exception as e:
            self.logger.error(f"Failed to create connection {connection_id}: {e}")
    
    async def _handle_connection_messages(self, connection_id: str):
        """Handle messages for a specific connection."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        while connection.is_connected and self.is_running:
            try:
                # Receive message
                message = await connection.receive(timeout=self.config.pipe_timeout)
                
                if message:
                    self.stats['messages_received'] += 1
                    
                    # Process message with handler
                    if self.message_handler:
                        try:
                            response = await self.message_handler(message)
                            if response:
                                await connection.send(response)
                                self.stats['messages_sent'] += 1
                        except Exception as e:
                            error_response = {
                                'error': str(e),
                                'request_id': message.get('request_id')
                            }
                            await connection.send(error_response)
                            self.stats['errors'] += 1
                
                await asyncio.sleep(0.01)  # Small delay
                
            except Exception as e:
                self.logger.error(f"Error handling messages for connection {connection_id}: {e}")
                break
        
        # Clean up disconnected connection
        if connection_id in self.connections:
            await self.connections[connection_id].close()
            del self.connections[connection_id]
    
    def _cleanup_inactive_connections(self):
        """Clean up inactive connections."""
        current_time = time.time()
        inactive_connections = []
        
        for conn_id, connection in self.connections.items():
            if current_time - connection.last_activity > self.config.pipe_timeout / 1000:
                inactive_connections.append(conn_id)
        
        for conn_id in inactive_connections:
            try:
                asyncio.run(self.connections[conn_id].close())
                del self.connections[conn_id]
                self.logger.info(f"Cleaned up inactive connection: {conn_id}")
            except Exception as e:
                self.logger.error(f"Error cleaning up connection {conn_id}: {e}")
    
    async def broadcast_message(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all active connections."""
        sent_count = 0
        
        for connection in self.connections.values():
            if connection.is_connected:
                success = await connection.send(message)
                if success:
                    sent_count += 1
        
        self.stats['messages_sent'] += sent_count
        return sent_count
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection."""
        connection = self.connections.get(connection_id)
        if connection and connection.is_connected:
            success = await connection.send(message)
            if success:
                self.stats['messages_sent'] += 1
            return success
        return False
    
    def get_active_connections(self) -> List[str]:
        """Get list of active connection IDs."""
        return [conn_id for conn_id, conn in self.connections.items() if conn.is_connected]
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len([conn for conn in self.connections.values() if conn.is_connected])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            **self.stats,
            'active_connections': self.get_connection_count(),
            'is_running': self.is_running,
            'pipe_path': self.base_pipe_path
        }


class NamedPipeClient:
    """Named pipe client for connecting to the pipe server."""
    
    def __init__(self, pipe_name: str, connection_id: Optional[str] = None):
        """Initialize pipe client."""
        self.pipe_name = pipe_name
        self.connection_id = connection_id or f"client_{int(time.time())}"
        self.is_connected = False
        self.base_pipe_path = os.path.join(tempfile.gettempdir(), f"revitpy_{pipe_name}")
    
    async def connect(self, timeout: int = 10) -> bool:
        """Connect to the pipe server."""
        try:
            # Send connection request to control pipe
            control_pipe_path = f"{self.base_pipe_path}_control"
            
            if not os.path.exists(control_pipe_path):
                raise BridgeConnectionError("named_pipe", "Control pipe not found. Server may not be running.")
            
            connect_message = {
                'command': 'connect',
                'connection_id': self.connection_id
            }
            
            with open(control_pipe_path, 'w') as control_pipe:
                control_pipe.write(json.dumps(connect_message) + '\n')
                control_pipe.flush()
            
            # Wait for connection to be established
            start_time = time.time()
            while time.time() - start_time < timeout:
                read_pipe_path = f"{self.base_pipe_path}_read_{self.connection_id}"
                write_pipe_path = f"{self.base_pipe_path}_write_{self.connection_id}"
                
                if os.path.exists(read_pipe_path) and os.path.exists(write_pipe_path):
                    self.is_connected = True
                    return True
                
                await asyncio.sleep(0.1)
            
            raise BridgeTimeoutError("pipe_connection", timeout)
            
        except Exception as e:
            raise BridgeConnectionError("named_pipe", f"Failed to connect: {e}")
    
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message and receive response."""
        if not self.is_connected:
            raise BridgeConnectionError("named_pipe", "Not connected to server")
        
        try:
            # Send message
            write_pipe_path = f"{self.base_pipe_path}_write_{self.connection_id}"
            with open(write_pipe_path, 'w') as write_pipe:
                write_pipe.write(json.dumps(message) + '\n')
                write_pipe.flush()
            
            # Receive response
            read_pipe_path = f"{self.base_pipe_path}_read_{self.connection_id}"
            with open(read_pipe_path, 'r') as read_pipe:
                response_line = read_pipe.readline()
                if response_line:
                    return json.loads(response_line.strip())
            
            return {'error': 'No response received'}
            
        except Exception as e:
            raise BridgeConnectionError("named_pipe", f"Failed to send message: {e}")
    
    async def disconnect(self):
        """Disconnect from the server."""
        if not self.is_connected:
            return
        
        try:
            # Send disconnect request
            control_pipe_path = f"{self.base_pipe_path}_control"
            disconnect_message = {
                'command': 'disconnect',
                'connection_id': self.connection_id
            }
            
            with open(control_pipe_path, 'w') as control_pipe:
                control_pipe.write(json.dumps(disconnect_message) + '\n')
                control_pipe.flush()
            
            self.is_connected = False
            
        except Exception as e:
            logging.error(f"Error during disconnect: {e}")