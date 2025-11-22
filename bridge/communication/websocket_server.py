"""
WebSocket server for development and debugging communication.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import websockets

from ..core.config import CommunicationConfig
from ..core.exceptions import BridgeConnectionError, BridgeTimeoutError


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection."""

    websocket: Any
    connection_id: str
    connected_at: float
    last_activity: float
    user_agent: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if connection is still active."""
        return not self.websocket.closed

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()


class WebSocketBridgeServer:
    """WebSocket server for real-time bridge communication."""

    def __init__(self, config: CommunicationConfig):
        """Initialize WebSocket server."""
        self.config = config
        self.logger = logging.getLogger("revitpy_bridge.websocket_server")

        # Server state
        self.is_running = False
        self.connections: dict[str, WebSocketConnection] = {}
        self.message_handler: Callable | None = None

        # Server instance
        self.server = None

        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "uptime_start": None,
        }

    def set_message_handler(self, handler: Callable[[dict[str, Any]], dict[str, Any]]):
        """Set message handler for incoming messages."""
        self.message_handler = handler

    async def start(self):
        """Start the WebSocket server."""
        if self.is_running:
            self.logger.warning("WebSocket server is already running")
            return

        self.logger.info("Starting WebSocket server...")
        self.is_running = True
        self.stats["uptime_start"] = time.time()

        try:
            # Start WebSocket server
            self.server = await websockets.serve(
                self._handle_client_connection,
                self.config.websocket_host,
                self.config.websocket_port,
                path=self.config.websocket_path,
                ping_interval=30,
                ping_timeout=10,
            )

            self.logger.info(
                f"WebSocket server started on "
                f"ws://{self.config.websocket_host}:{self.config.websocket_port}{self.config.websocket_path}"
            )

            # Start background tasks
            asyncio.create_task(self._cleanup_task())
            asyncio.create_task(self._heartbeat_task())

        except Exception as e:
            self.is_running = False
            raise BridgeConnectionError(
                "websocket", f"Failed to start WebSocket server: {e}"
            )

    async def stop(self):
        """Stop the WebSocket server."""
        if not self.is_running:
            return

        self.logger.info("Stopping WebSocket server...")
        self.is_running = False

        # Close all connections
        if self.connections:
            close_tasks = []
            for connection in self.connections.values():
                if connection.is_active:
                    close_tasks.append(connection.websocket.close())

            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)

        self.connections.clear()

        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.logger.info("WebSocket server stopped")

    async def _handle_client_connection(self, websocket, path):
        """Handle a new client connection."""
        connection_id = f"ws_{int(time.time())}_{id(websocket)}"

        try:
            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                connection_id=connection_id,
                connected_at=time.time(),
                last_activity=time.time(),
                user_agent=websocket.request_headers.get("User-Agent"),
            )

            # Add to connections
            self.connections[connection_id] = connection
            self.stats["total_connections"] += 1
            self.stats["active_connections"] += 1

            self.logger.info(f"New WebSocket connection: {connection_id}")

            # Send welcome message
            welcome_message = {
                "type": "connection_established",
                "data": {
                    "connection_id": connection_id,
                    "server_time": time.time(),
                    "bridge_version": "1.0.0",
                },
            }
            await self._send_message(websocket, welcome_message)

            # Handle messages
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    connection.update_activity()
                    self.stats["messages_received"] += 1

                    # Process message
                    response = await self._process_message(message, connection_id)

                    if response:
                        await self._send_message(websocket, response)
                        self.stats["messages_sent"] += 1

                except json.JSONDecodeError as e:
                    error_response = {
                        "type": "error",
                        "data": {
                            "error": f"Invalid JSON: {e}",
                            "error_type": "json_decode_error",
                        },
                    }
                    await self._send_message(websocket, error_response)
                    self.stats["errors"] += 1

                except Exception as e:
                    self.logger.error(
                        f"Error processing message from {connection_id}: {e}"
                    )
                    error_response = {
                        "type": "error",
                        "data": {
                            "error": str(e),
                            "error_type": "message_processing_error",
                        },
                    }
                    await self._send_message(websocket, error_response)
                    self.stats["errors"] += 1

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"WebSocket connection closed: {connection_id}")

        except Exception as e:
            self.logger.error(f"Error in WebSocket connection {connection_id}: {e}")
            self.stats["errors"] += 1

        finally:
            # Clean up connection
            if connection_id in self.connections:
                del self.connections[connection_id]
                self.stats["active_connections"] -= 1
                self.logger.info(f"Cleaned up connection: {connection_id}")

    async def _process_message(
        self, message: dict[str, Any], connection_id: str
    ) -> dict[str, Any] | None:
        """Process incoming message."""
        try:
            message_type = message.get("type")

            # Handle built-in message types
            if message_type == "ping":
                return {
                    "type": "pong",
                    "data": {"timestamp": time.time(), "connection_id": connection_id},
                }

            elif message_type == "get_status":
                return {"type": "status", "data": self.get_server_status()}

            elif message_type == "get_connections":
                return {"type": "connections", "data": self.get_connection_info()}

            # Forward to custom message handler
            elif self.message_handler:
                response = await self.message_handler(message)
                return response

            else:
                return {
                    "type": "error",
                    "data": {
                        "error": f"Unknown message type: {message_type}",
                        "error_type": "unknown_message_type",
                    },
                }

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return {
                "type": "error",
                "data": {"error": str(e), "error_type": "processing_error"},
            }

    async def _send_message(self, websocket, message: dict[str, Any]):
        """Send message to WebSocket client."""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            raise

    async def broadcast_message(
        self, message: dict[str, Any], exclude_connection: str | None = None
    ) -> int:
        """Broadcast message to all active connections."""
        sent_count = 0

        for conn_id, connection in self.connections.items():
            if conn_id != exclude_connection and connection.is_active:
                try:
                    await self._send_message(connection.websocket, message)
                    sent_count += 1
                except Exception as e:
                    self.logger.error(f"Error broadcasting to {conn_id}: {e}")

        self.stats["messages_sent"] += sent_count
        return sent_count

    async def send_to_connection(
        self, connection_id: str, message: dict[str, Any]
    ) -> bool:
        """Send message to specific connection."""
        connection = self.connections.get(connection_id)
        if connection and connection.is_active:
            try:
                await self._send_message(connection.websocket, message)
                self.stats["messages_sent"] += 1
                return True
            except Exception as e:
                self.logger.error(f"Error sending to {connection_id}: {e}")

        return False

    async def _cleanup_task(self):
        """Background task to clean up inactive connections."""
        while self.is_running:
            try:
                current_time = time.time()
                inactive_connections = []

                for conn_id, connection in self.connections.items():
                    if not connection.is_active:
                        inactive_connections.append(conn_id)
                    elif current_time - connection.last_activity > 300:  # 5 minutes
                        self.logger.info(f"Closing inactive connection: {conn_id}")
                        try:
                            await connection.websocket.close()
                        except:
                            pass
                        inactive_connections.append(conn_id)

                # Remove inactive connections
                for conn_id in inactive_connections:
                    if conn_id in self.connections:
                        del self.connections[conn_id]
                        self.stats["active_connections"] -= 1

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Longer pause on error

    async def _heartbeat_task(self):
        """Background task to send heartbeat messages."""
        while self.is_running:
            try:
                heartbeat_message = {
                    "type": "heartbeat",
                    "data": {
                        "timestamp": time.time(),
                        "active_connections": len(self.connections),
                    },
                }

                await self.broadcast_message(heartbeat_message)
                await asyncio.sleep(60)  # Send every minute

            except Exception as e:
                self.logger.error(f"Error in heartbeat task: {e}")
                await asyncio.sleep(60)

    def get_active_connections(self) -> List[str]:
        """Get list of active connection IDs."""
        return [conn_id for conn_id, conn in self.connections.items() if conn.is_active]

    def get_connection_info(self) -> List[dict[str, Any]]:
        """Get detailed connection information."""
        connection_info = []

        for conn_id, connection in self.connections.items():
            if connection.is_active:
                info = {
                    "connection_id": conn_id,
                    "connected_at": connection.connected_at,
                    "last_activity": connection.last_activity,
                    "user_agent": connection.user_agent,
                    "uptime": time.time() - connection.connected_at,
                }
                connection_info.append(info)

        return connection_info

    def get_server_status(self) -> dict[str, Any]:
        """Get server status information."""
        uptime = (
            time.time() - self.stats["uptime_start"]
            if self.stats["uptime_start"]
            else 0
        )

        return {
            "is_running": self.is_running,
            "host": self.config.websocket_host,
            "port": self.config.websocket_port,
            "path": self.config.websocket_path,
            "uptime_seconds": uptime,
            "statistics": self.stats.copy(),
            "active_connections_count": len(
                [c for c in self.connections.values() if c.is_active]
            ),
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get detailed server statistics."""
        return {
            **self.stats,
            "active_connections_count": len(
                [c for c in self.connections.values() if c.is_active]
            ),
        }


class WebSocketBridgeClient:
    """WebSocket client for connecting to the bridge server."""

    def __init__(
        self, host: str = "localhost", port: int = 8765, path: str = "/bridge"
    ):
        """Initialize WebSocket client."""
        self.host = host
        self.port = port
        self.path = path
        self.websocket = None
        self.is_connected = False
        self.connection_id = None

        # Message handling
        self.message_queue = asyncio.Queue()
        self.response_futures: dict[str, asyncio.Future] = {}
        self.message_handlers: dict[str, Callable] = {}

    async def connect(self, timeout: int = 10) -> bool:
        """Connect to the WebSocket server."""
        try:
            uri = f"ws://{self.host}:{self.port}{self.path}"
            self.websocket = await websockets.connect(uri, ping_interval=30)
            self.is_connected = True

            # Start message handling task
            asyncio.create_task(self._handle_messages())

            return True

        except Exception as e:
            raise BridgeConnectionError("websocket", f"Failed to connect: {e}")

    async def disconnect(self):
        """Disconnect from the server."""
        if self.websocket and self.is_connected:
            await self.websocket.close()
            self.is_connected = False

    async def send_message(
        self, message: dict[str, Any], expect_response: bool = False, timeout: int = 30
    ) -> dict[str, Any] | None:
        """Send message to server."""
        if not self.is_connected:
            raise BridgeConnectionError("websocket", "Not connected to server")

        try:
            # Add request ID for response tracking
            if expect_response:
                request_id = f"req_{int(time.time())}_{id(message)}"
                message["request_id"] = request_id

                # Create future for response
                response_future = asyncio.Future()
                self.response_futures[request_id] = response_future

            # Send message
            await self.websocket.send(json.dumps(message))

            # Wait for response if expected
            if expect_response:
                try:
                    response = await asyncio.wait_for(response_future, timeout=timeout)
                    return response
                except TimeoutError:
                    self.response_futures.pop(request_id, None)
                    raise BridgeTimeoutError("websocket_response", timeout)

            return None

        except Exception as e:
            if expect_response and "request_id" in locals():
                self.response_futures.pop(request_id, None)
            raise BridgeConnectionError("websocket", f"Failed to send message: {e}")

    async def _handle_messages(self):
        """Handle incoming messages."""
        try:
            async for raw_message in self.websocket:
                try:
                    message = json.loads(raw_message)
                    await self._process_incoming_message(message)
                except Exception as e:
                    logging.error(f"Error processing incoming message: {e}")

        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
        except Exception as e:
            logging.error(f"Error in message handling: {e}")
            self.is_connected = False

    async def _process_incoming_message(self, message: dict[str, Any]):
        """Process incoming message."""
        message_type = message.get("type")
        request_id = message.get("request_id")

        # Handle response to request
        if request_id and request_id in self.response_futures:
            future = self.response_futures.pop(request_id)
            if not future.done():
                future.set_result(message)
            return

        # Handle specific message types
        if message_type == "connection_established":
            self.connection_id = message.get("data", {}).get("connection_id")

        # Forward to registered handlers
        if message_type in self.message_handlers:
            try:
                await self.message_handlers[message_type](message)
            except Exception as e:
                logging.error(f"Error in message handler for {message_type}: {e}")

        # Add to message queue for general handling
        await self.message_queue.put(message)

    def register_message_handler(self, message_type: str, handler: Callable):
        """Register handler for specific message type."""
        self.message_handlers[message_type] = handler

    async def get_next_message(self, timeout: int | None = None) -> dict[str, Any]:
        """Get next message from queue."""
        if timeout:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        else:
            return await self.message_queue.get()

    async def ping_server(self) -> float:
        """Ping server and return response time."""
        start_time = time.time()

        ping_message = {"type": "ping"}
        response = await self.send_message(ping_message, expect_response=True)

        end_time = time.time()
        return end_time - start_time
