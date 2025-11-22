"""
Tests for communication protocol functionality.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ..communication.file_exchange import FileExchangeHandler
from ..communication.named_pipe_server import NamedPipeClient, NamedPipeServer
from ..communication.websocket_server import WebSocketClient, WebSocketServer
from ..core.exceptions import CommunicationError


class TestNamedPipeServer:
    """Test named pipe server functionality."""

    @pytest.fixture
    def pipe_server(self, temp_dir):
        """Create named pipe server for testing."""
        pipe_name = str(temp_dir / "test_pipe")
        return NamedPipeServer(pipe_name)

    @pytest.mark.asyncio
    async def test_server_initialization(self, pipe_server):
        """Test server initialization."""
        assert not pipe_server.is_running
        assert pipe_server.pipe_name is not None
        assert pipe_server.client_count == 0

    @pytest.mark.asyncio
    async def test_server_start_stop(self, pipe_server):
        """Test server start and stop."""
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_process

            # Test start
            await pipe_server.start()
            assert pipe_server.is_running

            # Test stop
            await pipe_server.stop()
            assert not pipe_server.is_running

    @pytest.mark.asyncio
    async def test_message_handling(self, pipe_server):
        """Test message handling."""
        test_message = {"type": "analysis_request", "data": "test"}

        # Mock message handler
        handler_called = False

        async def test_handler(message):
            nonlocal handler_called
            handler_called = True
            assert message == test_message
            return {"success": True}

        pipe_server.message_handlers["analysis_request"] = test_handler

        # Simulate receiving message
        response = await pipe_server.handle_message(test_message)

        assert handler_called
        assert response["success"] is True

    @pytest.mark.asyncio
    async def test_client_connection_management(self, pipe_server):
        """Test client connection management."""
        # Simulate client connection
        client_id = "test_client_001"

        pipe_server.add_client(client_id)
        assert pipe_server.client_count == 1
        assert client_id in pipe_server.connected_clients

        pipe_server.remove_client(client_id)
        assert pipe_server.client_count == 0
        assert client_id not in pipe_server.connected_clients

    @pytest.mark.asyncio
    async def test_broadcast_message(self, pipe_server):
        """Test broadcasting messages to all clients."""
        # Add mock clients
        client_ids = ["client_001", "client_002", "client_003"]
        for client_id in client_ids:
            pipe_server.add_client(client_id)

        test_message = {"type": "broadcast", "data": "test broadcast"}

        with patch.object(pipe_server, "_send_to_client") as mock_send:
            mock_send.return_value = True

            success_count = await pipe_server.broadcast_message(test_message)

            assert success_count == 3
            assert mock_send.call_count == 3


class TestNamedPipeClient:
    """Test named pipe client functionality."""

    @pytest.fixture
    def pipe_client(self, temp_dir):
        """Create named pipe client for testing."""
        pipe_name = str(temp_dir / "test_pipe")
        return NamedPipeClient(pipe_name)

    @pytest.mark.asyncio
    async def test_client_connection(self, pipe_client):
        """Test client connection."""
        with patch.object(pipe_client, "_establish_connection") as mock_connect:
            mock_connect.return_value = True

            success = await pipe_client.connect()
            assert success
            assert pipe_client.is_connected

    @pytest.mark.asyncio
    async def test_send_message(self, pipe_client):
        """Test sending messages."""
        test_message = {"type": "test", "data": "hello"}

        with patch.object(pipe_client, "_send_raw_message") as mock_send:
            mock_send.return_value = {"success": True, "response": "ok"}
            pipe_client.is_connected = True

            response = await pipe_client.send_message(test_message)

            assert response["success"] is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_timeout(self, pipe_client):
        """Test connection timeout handling."""
        pipe_client.connection_timeout = 0.1  # Short timeout for testing

        with patch.object(pipe_client, "_establish_connection") as mock_connect:
            # Simulate slow connection
            mock_connect.side_effect = TimeoutError()

            with pytest.raises(CommunicationError):
                await pipe_client.connect()


class TestWebSocketServer:
    """Test WebSocket server functionality."""

    @pytest.fixture
    def websocket_server(self):
        """Create WebSocket server for testing."""
        return WebSocketServer(host="localhost", port=8765)

    @pytest.mark.asyncio
    async def test_server_startup(self, websocket_server):
        """Test server startup."""
        with patch("websockets.serve") as mock_serve:
            mock_serve.return_value = AsyncMock()

            await websocket_server.start()
            assert websocket_server.is_running
            mock_serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_shutdown(self, websocket_server):
        """Test server shutdown."""
        websocket_server.is_running = True
        websocket_server.server = Mock()
        websocket_server.server.close = Mock()
        websocket_server.server.wait_closed = AsyncMock()

        await websocket_server.stop()

        assert not websocket_server.is_running
        websocket_server.server.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, websocket_server):
        """Test WebSocket message handling."""
        # Mock WebSocket connection
        mock_websocket = Mock()
        mock_websocket.recv = AsyncMock(
            return_value='{"type": "test", "data": "hello"}'
        )
        mock_websocket.send = AsyncMock()

        # Mock message handler
        async def test_handler(message):
            return {"success": True, "echo": message}

        websocket_server.message_handlers["test"] = test_handler

        await websocket_server.handle_client(mock_websocket, "/")

        # Verify message was processed and response sent
        mock_websocket.send.assert_called()

    @pytest.mark.asyncio
    async def test_connection_management(self, websocket_server):
        """Test WebSocket connection management."""
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        # Test adding connection
        websocket_server.add_connection(mock_websocket)
        assert len(websocket_server.connections) == 1

        # Test removing connection
        websocket_server.remove_connection(mock_websocket)
        assert len(websocket_server.connections) == 0


class TestWebSocketClient:
    """Test WebSocket client functionality."""

    @pytest.fixture
    def websocket_client(self):
        """Create WebSocket client for testing."""
        return WebSocketClient("ws://localhost:8765")

    @pytest.mark.asyncio
    async def test_client_connection(self, websocket_client):
        """Test client connection."""
        with patch("websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket

            await websocket_client.connect()
            assert websocket_client.is_connected

    @pytest.mark.asyncio
    async def test_send_message(self, websocket_client):
        """Test sending messages via WebSocket."""
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value='{"success": true}')

        websocket_client.websocket = mock_websocket
        websocket_client.is_connected = True

        test_message = {"type": "analysis", "data": "test"}
        response = await websocket_client.send_message(test_message)

        assert response is not None
        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, websocket_client):
        """Test connection error handling."""
        with patch("websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(CommunicationError):
                await websocket_client.connect()


class TestFileExchangeHandler:
    """Test file-based communication functionality."""

    @pytest.fixture
    def file_exchange(self, temp_dir):
        """Create file exchange handler for testing."""
        return FileExchangeHandler(str(temp_dir))

    def test_request_file_creation(self, file_exchange, sample_analysis_request):
        """Test creating request files."""
        request_id = file_exchange.create_request_file(sample_analysis_request)

        assert request_id is not None
        request_file = Path(file_exchange.exchange_dir) / f"{request_id}_request.json"
        assert request_file.exists()

        # Verify content
        with open(request_file) as f:
            loaded_data = json.load(f)
        assert loaded_data["analysis_type"] == sample_analysis_request["analysis_type"]

    def test_result_file_creation(self, file_exchange, sample_analysis_result):
        """Test creating result files."""
        request_id = "test_request_001"

        file_exchange.create_result_file(request_id, sample_analysis_result)

        result_file = Path(file_exchange.exchange_dir) / f"{request_id}_result.json"
        assert result_file.exists()

        # Verify content
        with open(result_file) as f:
            loaded_data = json.load(f)
        assert loaded_data["success"] == sample_analysis_result["success"]

    def test_file_monitoring(self, file_exchange):
        """Test file system monitoring for new requests."""
        # Create a test request file manually
        test_request = {"analysis_type": "test", "elements": []}
        request_file = Path(file_exchange.exchange_dir) / "manual_request_request.json"

        with open(request_file, "w") as f:
            json.dump(test_request, f)

        # Check if handler detects the file
        pending_requests = file_exchange.get_pending_requests()
        assert len(pending_requests) > 0
        assert any(req["request_id"] == "manual_request" for req in pending_requests)

    def test_file_cleanup(self, file_exchange, sample_analysis_request):
        """Test cleanup of old exchange files."""
        # Create some test files
        request_id = file_exchange.create_request_file(sample_analysis_request)
        file_exchange.create_result_file(request_id, {"success": True})

        # Verify files exist
        request_file = Path(file_exchange.exchange_dir) / f"{request_id}_request.json"
        result_file = Path(file_exchange.exchange_dir) / f"{request_id}_result.json"
        assert request_file.exists()
        assert result_file.exists()

        # Cleanup files
        file_exchange.cleanup_processed_files(request_id)

        # Verify files are removed
        assert not request_file.exists()
        assert not result_file.exists()

    def test_error_file_handling(self, file_exchange):
        """Test handling of malformed request files."""
        # Create malformed JSON file
        malformed_file = Path(file_exchange.exchange_dir) / "malformed_request.json"
        malformed_file.write_text("{ invalid json")

        # Should handle gracefully
        pending_requests = file_exchange.get_pending_requests()

        # Should not crash and potentially log error
        assert isinstance(pending_requests, list)

    @pytest.mark.asyncio
    async def test_async_file_processing(self, file_exchange, sample_analysis_request):
        """Test asynchronous file processing."""
        request_id = file_exchange.create_request_file(sample_analysis_request)

        # Mock async processing
        async def mock_processor(request_data):
            await asyncio.sleep(0.1)  # Simulate processing time
            return {"success": True, "processed": True}

        # Process the request
        result = await mock_processor(sample_analysis_request)
        file_exchange.create_result_file(request_id, result)

        # Verify result file was created
        result_file = Path(file_exchange.exchange_dir) / f"{request_id}_result.json"
        assert result_file.exists()

        # Verify content
        with open(result_file) as f:
            loaded_result = json.load(f)
        assert loaded_result["processed"] is True
