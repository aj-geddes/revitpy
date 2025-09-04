"""WebSocket server for RevitPy CLI development server."""

import asyncio
import json
import threading
from typing import Callable, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from ..core.logging import get_logger

logger = get_logger(__name__)


class WebSocketServer:
    """WebSocket server for client communication."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8001,
        on_connect: Optional[Callable[[WebSocketServerProtocol], None]] = None,
        on_disconnect: Optional[Callable[[WebSocketServerProtocol], None]] = None,
    ) -> None:
        """Initialize WebSocket server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            on_connect: Callback for client connection
            on_disconnect: Callback for client disconnection
        """
        self.host = host
        self.port = port
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        
        self.server = None
        self.clients: Set[WebSocketServerProtocol] = set()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def start(self) -> None:
        """Start the WebSocket server."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    def stop(self) -> None:
        """Stop the WebSocket server."""
        if not self._running:
            return
        
        self._running = False
        
        if self._loop and self.server:
            # Schedule server shutdown in the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._shutdown_server(), self._loop
            )
            try:
                future.result(timeout=5.0)
            except Exception as e:
                logger.warning(f"Error shutting down WebSocket server: {e}")
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        
        logger.info("WebSocket server stopped")
    
    def _run_server(self) -> None:
        """Run the WebSocket server in a separate thread."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            self._loop.run_until_complete(self._start_server())
            self._loop.run_forever()
            
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            if self._loop:
                self._loop.close()
    
    async def _start_server(self) -> None:
        """Start the WebSocket server."""
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
            )
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            self._running = False
    
    async def _shutdown_server(self) -> None:
        """Shutdown the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )
        
        # Stop the event loop
        if self._loop:
            self._loop.stop()
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a client connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        self.clients.add(websocket)
        
        if self.on_connect:
            self.on_connect(websocket)
        
        logger.debug(f"WebSocket client connected: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    await self._handle_message(websocket, message)
                except Exception as e:
                    logger.warning(f"Error handling WebSocket message: {e}")
                    
        except websockets.ConnectionClosed:
            logger.debug(f"WebSocket client disconnected: {websocket.remote_address}")
        except Exception as e:
            logger.warning(f"WebSocket client error: {e}")
        finally:
            self.clients.discard(websocket)
            
            if self.on_disconnect:
                self.on_disconnect(websocket)
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str) -> None:
        """Handle a message from a client.
        
        Args:
            websocket: WebSocket connection
            message: Message from client
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            # Handle different message types
            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            elif msg_type == "subscribe":
                # Handle subscription requests
                await self._handle_subscribe(websocket, data)
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message from {websocket.remote_address}")
        except Exception as e:
            logger.warning(f"Error processing message: {e}")
    
    async def _handle_subscribe(self, websocket: WebSocketServerProtocol, data: dict) -> None:
        """Handle subscription requests.
        
        Args:
            websocket: WebSocket connection
            data: Subscription data
        """
        # This would handle different subscription types
        # For now, just acknowledge the subscription
        await websocket.send(json.dumps({
            "type": "subscription_ack",
            "subscription": data.get("subscription", "default")
        }))
    
    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients.
        
        Args:
            message: Message to broadcast
        """
        if not self.clients:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for client in self.clients.copy():
            try:
                await client.send(message_str)
            except websockets.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}")
                disconnected.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected
    
    def broadcast_sync(self, message: dict) -> None:
        """Synchronously broadcast a message to all clients.
        
        Args:
            message: Message to broadcast
        """
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(message), self._loop
            )
    
    @property
    def is_running(self) -> bool:
        """Check if server is running.
        
        Returns:
            True if server is running
        """
        return self._running
    
    @property
    def client_count(self) -> int:
        """Get number of connected clients.
        
        Returns:
            Number of connected clients
        """
        return len(self.clients)