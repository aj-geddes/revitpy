"""Hot reload server for development."""

import http.server
import socketserver
import threading
from pathlib import Path
from typing import Optional

from ..core.exceptions import DevServerError
from ..core.logging import get_logger

logger = get_logger(__name__)


class HotReloadHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with hot reload injection."""
    
    def __init__(self, *args, websocket_port: int = 8001, **kwargs) -> None:
        """Initialize hot reload handler.
        
        Args:
            websocket_port: WebSocket port for hot reload
        """
        self.websocket_port = websocket_port
        super().__init__(*args, **kwargs)
    
    def end_headers(self) -> None:
        """Add hot reload script injection headers."""
        # Inject hot reload client script for HTML responses
        if hasattr(self, '_should_inject_script') and self._should_inject_script:
            content_length = int(self.headers.get('Content-Length', 0))
            hot_reload_script = self._get_hot_reload_script()
            new_length = content_length + len(hot_reload_script.encode())
            
            self.send_header('Content-Length', str(new_length))
        
        super().end_headers()
    
    def do_GET(self) -> None:
        """Handle GET requests with hot reload injection."""
        path = self.translate_path(self.path)
        
        # Check if we should inject hot reload script
        if path.endswith('.html'):
            self._should_inject_script = True
        else:
            self._should_inject_script = False
        
        super().do_GET()
    
    def copyfile(self, source, outputfile) -> None:
        """Copy file content with potential hot reload injection.
        
        Args:
            source: Source file object
            outputfile: Output file object
        """
        if hasattr(self, '_should_inject_script') and self._should_inject_script:
            # Read content and inject script
            content = source.read()
            
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            
            # Inject hot reload script before closing body tag
            hot_reload_script = self._get_hot_reload_script()
            if '</body>' in content:
                content = content.replace('</body>', f'{hot_reload_script}\n</body>')
            else:
                content += hot_reload_script
            
            outputfile.write(content.encode('utf-8'))
        else:
            super().copyfile(source, outputfile)
    
    def _get_hot_reload_script(self) -> str:
        """Get hot reload client script.
        
        Returns:
            JavaScript hot reload client script
        """
        return f"""
<script>
(function() {{
    let socket;
    let reconnectInterval = 2000;
    let maxReconnectAttempts = 10;
    let reconnectAttempts = 0;
    
    function connect() {{
        socket = new WebSocket('ws://localhost:{self.websocket_port}');
        
        socket.onopen = function(event) {{
            console.log('[RevitPy] Hot reload connected');
            reconnectAttempts = 0;
        }};
        
        socket.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            console.log('[RevitPy] File changed:', data);
            
            if (data.type === 'file_change') {{
                // Reload the page on file changes
                window.location.reload();
            }}
        }};
        
        socket.onclose = function(event) {{
            console.log('[RevitPy] Hot reload disconnected');
            
            // Attempt to reconnect
            if (reconnectAttempts < maxReconnectAttempts) {{
                setTimeout(function() {{
                    reconnectAttempts++;
                    console.log(`[RevitPy] Reconnecting... (attempt ${{reconnectAttempts}})`);
                    connect();
                }}, reconnectInterval);
            }}
        }};
        
        socket.onerror = function(error) {{
            console.error('[RevitPy] WebSocket error:', error);
        }};
    }}
    
    // Start connection
    connect();
}})();
</script>
"""


class HotReloadServer:
    """HTTP server with hot reload capabilities."""
    
    def __init__(
        self,
        project_path: Path,
        host: str = "localhost",
        port: int = 8000,
        websocket_port: int = 8001,
    ) -> None:
        """Initialize hot reload server.
        
        Args:
            project_path: Path to serve files from
            host: Host to bind to
            port: Port to bind to
            websocket_port: WebSocket port for hot reload
        """
        self.project_path = project_path
        self.host = host
        self.port = port
        self.websocket_port = websocket_port
        
        self.httpd: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self) -> None:
        """Start the hot reload server."""
        if self.running:
            return
        
        try:
            # Create handler with hot reload injection
            def make_handler(*args, **kwargs):
                return HotReloadHTTPHandler(
                    *args,
                    websocket_port=self.websocket_port,
                    directory=str(self.project_path),
                    **kwargs
                )
            
            # Create server
            self.httpd = socketserver.TCPServer((self.host, self.port), make_handler)
            self.httpd.allow_reuse_address = True
            
            # Start server in thread
            self.thread = threading.Thread(
                target=self.httpd.serve_forever,
                daemon=True
            )
            self.thread.start()
            self.running = True
            
            logger.info(f"Hot reload server started at http://{self.host}:{self.port}")
            
        except Exception as e:
            raise DevServerError(
                f"Failed to start hot reload server: {e}",
                port=self.port
            ) from e
    
    def stop(self) -> None:
        """Stop the hot reload server."""
        if not self.running:
            return
        
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.running = False
        logger.info("Hot reload server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running.
        
        Returns:
            True if server is running
        """
        return self.running and self.thread is not None and self.thread.is_alive()


class StaticFileServer:
    """Simple static file server without hot reload."""
    
    def __init__(
        self,
        project_path: Path,
        host: str = "localhost", 
        port: int = 8000,
    ) -> None:
        """Initialize static file server.
        
        Args:
            project_path: Path to serve files from
            host: Host to bind to
            port: Port to bind to
        """
        self.project_path = project_path
        self.host = host
        self.port = port
        
        self.httpd: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self) -> None:
        """Start the static file server."""
        if self.running:
            return
        
        try:
            # Create handler
            def make_handler(*args, **kwargs):
                return http.server.SimpleHTTPRequestHandler(
                    *args,
                    directory=str(self.project_path),
                    **kwargs
                )
            
            # Create server
            self.httpd = socketserver.TCPServer((self.host, self.port), make_handler)
            self.httpd.allow_reuse_address = True
            
            # Start server in thread
            self.thread = threading.Thread(
                target=self.httpd.serve_forever,
                daemon=True
            )
            self.thread.start()
            self.running = True
            
            logger.info(f"Static file server started at http://{self.host}:{self.port}")
            
        except Exception as e:
            raise DevServerError(
                f"Failed to start static file server: {e}",
                port=self.port
            ) from e
    
    def stop(self) -> None:
        """Stop the static file server."""
        if not self.running:
            return
        
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.running = False
        logger.info("Static file server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running.
        
        Returns:
            True if server is running
        """
        return self.running and self.thread is not None and self.thread.is_alive()