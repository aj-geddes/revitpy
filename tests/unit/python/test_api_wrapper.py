"""Unit tests for RevitPy API wrapper functionality.

This module tests the core API wrapper that handles communication
between Python and the C# bridge.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

import pytest

from revitpy.api.wrapper import RevitAPIWrapper
from revitpy.api.exceptions import RevitAPIException, RevitConnectionError


class TestRevitAPIWrapper:
    """Test suite for RevitAPIWrapper class."""
    
    @pytest.fixture
    def mock_bridge(self):
        """Mock C# bridge for testing."""
        bridge = MagicMock()
        bridge.IsConnected = True
        bridge.Version = "2024.1.0"
        bridge.Call = AsyncMock()
        bridge.CallAsync = AsyncMock()
        bridge.Subscribe = MagicMock()
        bridge.Unsubscribe = MagicMock()
        return bridge
    
    @pytest.fixture
    def api_wrapper(self, mock_bridge):
        """Create API wrapper instance for testing."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge
        wrapper._connected = True
        return wrapper
    
    @pytest.mark.unit
    def test_init_creates_wrapper_with_defaults(self):
        """Test that wrapper initializes with correct default values."""
        wrapper = RevitAPIWrapper()
        
        assert wrapper._bridge is None
        assert not wrapper._connected
        assert wrapper._timeout == 30.0
        assert wrapper._retry_count == 3
        assert wrapper._event_handlers == {}
    
    @pytest.mark.unit
    def test_init_with_custom_config(self):
        """Test wrapper initialization with custom configuration."""
        config = {
            "timeout": 60.0,
            "retry_count": 5,
            "bridge_host": "localhost",
            "bridge_port": 8080
        }
        
        wrapper = RevitAPIWrapper(config=config)
        
        assert wrapper._timeout == 60.0
        assert wrapper._retry_count == 5
        assert wrapper._bridge_host == "localhost"
        assert wrapper._bridge_port == 8080
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_bridge):
        """Test successful connection to bridge."""
        with patch('revitpy.api.wrapper.BridgeConnector') as mock_connector:
            mock_connector.return_value.connect.return_value = mock_bridge
            
            wrapper = RevitAPIWrapper()
            result = await wrapper.connect()
            
            assert result is True
            assert wrapper._connected is True
            assert wrapper._bridge == mock_bridge
            mock_connector.return_value.connect.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure handling."""
        with patch('revitpy.api.wrapper.BridgeConnector') as mock_connector:
            mock_connector.return_value.connect.side_effect = ConnectionError("Connection failed")
            
            wrapper = RevitAPIWrapper()
            
            with pytest.raises(RevitConnectionError):
                await wrapper.connect()
            
            assert wrapper._connected is False
            assert wrapper._bridge is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, api_wrapper):
        """Test disconnection when connected."""
        await api_wrapper.disconnect()
        
        assert api_wrapper._connected is False
        api_wrapper._bridge.Disconnect.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test disconnection when not connected."""
        wrapper = RevitAPIWrapper()
        await wrapper.disconnect()  # Should not raise exception
        
        assert wrapper._connected is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_api_success(self, api_wrapper):
        """Test successful API call."""
        expected_result = {"id": 1, "name": "Test Wall"}
        api_wrapper._bridge.CallAsync.return_value = json.dumps(expected_result)
        
        result = await api_wrapper.call_api("GetElement", {"elementId": 1})
        
        assert result == expected_result
        api_wrapper._bridge.CallAsync.assert_called_once_with(
            "GetElement", 
            json.dumps({"elementId": 1}),
            api_wrapper._timeout
        )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_api_with_retry_success(self, api_wrapper):
        """Test API call with retry mechanism."""
        expected_result = {"id": 1, "name": "Test Wall"}
        api_wrapper._bridge.CallAsync.side_effect = [
            Exception("Temporary error"),
            Exception("Another error"),
            json.dumps(expected_result)
        ]
        
        result = await api_wrapper.call_api("GetElement", {"elementId": 1})
        
        assert result == expected_result
        assert api_wrapper._bridge.CallAsync.call_count == 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_api_max_retries_exceeded(self, api_wrapper):
        """Test API call when max retries are exceeded."""
        api_wrapper._bridge.CallAsync.side_effect = Exception("Persistent error")
        
        with pytest.raises(RevitAPIException) as exc_info:
            await api_wrapper.call_api("GetElement", {"elementId": 1})
        
        assert "Max retries exceeded" in str(exc_info.value)
        assert api_wrapper._bridge.CallAsync.call_count == api_wrapper._retry_count + 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_api_when_not_connected(self):
        """Test API call when not connected."""
        wrapper = RevitAPIWrapper()
        
        with pytest.raises(RevitConnectionError):
            await wrapper.call_api("GetElement", {"elementId": 1})
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_api_with_timeout(self, api_wrapper):
        """Test API call with custom timeout."""
        api_wrapper._bridge.CallAsync.return_value = json.dumps({"result": "success"})
        
        await api_wrapper.call_api("GetElement", {"elementId": 1}, timeout=60.0)
        
        api_wrapper._bridge.CallAsync.assert_called_once_with(
            "GetElement", 
            json.dumps({"elementId": 1}),
            60.0
        )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_batch_call_success(self, api_wrapper):
        """Test successful batch API calls."""
        calls = [
            {"method": "GetElement", "params": {"elementId": 1}},
            {"method": "GetElement", "params": {"elementId": 2}},
            {"method": "GetElement", "params": {"elementId": 3}}
        ]
        
        expected_results = [
            {"id": 1, "name": "Wall 1"},
            {"id": 2, "name": "Wall 2"},
            {"id": 3, "name": "Wall 3"}
        ]
        
        api_wrapper._bridge.CallAsync.side_effect = [
            json.dumps(result) for result in expected_results
        ]
        
        results = await api_wrapper.batch_call(calls)
        
        assert results == expected_results
        assert api_wrapper._bridge.CallAsync.call_count == 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_batch_call_partial_failure(self, api_wrapper):
        """Test batch API calls with partial failures."""
        calls = [
            {"method": "GetElement", "params": {"elementId": 1}},
            {"method": "GetElement", "params": {"elementId": 999}},  # Non-existent
            {"method": "GetElement", "params": {"elementId": 3}}
        ]
        
        api_wrapper._bridge.CallAsync.side_effect = [
            json.dumps({"id": 1, "name": "Wall 1"}),
            Exception("Element not found"),
            json.dumps({"id": 3, "name": "Wall 3"})
        ]
        
        results = await api_wrapper.batch_call(calls, fail_fast=False)
        
        assert len(results) == 3
        assert results[0] == {"id": 1, "name": "Wall 1"}
        assert isinstance(results[1], Exception)
        assert results[2] == {"id": 3, "name": "Wall 3"}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_batch_call_fail_fast(self, api_wrapper):
        """Test batch API calls with fail fast enabled."""
        calls = [
            {"method": "GetElement", "params": {"elementId": 1}},
            {"method": "GetElement", "params": {"elementId": 999}},  # Non-existent
            {"method": "GetElement", "params": {"elementId": 3}}
        ]
        
        api_wrapper._bridge.CallAsync.side_effect = [
            json.dumps({"id": 1, "name": "Wall 1"}),
            Exception("Element not found"),
            json.dumps({"id": 3, "name": "Wall 3"})
        ]
        
        with pytest.raises(Exception):
            await api_wrapper.batch_call(calls, fail_fast=True)
    
    @pytest.mark.unit
    def test_subscribe_to_event(self, api_wrapper):
        """Test event subscription."""
        def event_handler(data):
            return f"Handled: {data}"
        
        api_wrapper.subscribe("ElementChanged", event_handler)
        
        assert "ElementChanged" in api_wrapper._event_handlers
        assert api_wrapper._event_handlers["ElementChanged"] == event_handler
        api_wrapper._bridge.Subscribe.assert_called_once_with("ElementChanged")
    
    @pytest.mark.unit
    def test_unsubscribe_from_event(self, api_wrapper):
        """Test event unsubscription."""
        def event_handler(data):
            return f"Handled: {data}"
        
        api_wrapper.subscribe("ElementChanged", event_handler)
        api_wrapper.unsubscribe("ElementChanged")
        
        assert "ElementChanged" not in api_wrapper._event_handlers
        api_wrapper._bridge.Unsubscribe.assert_called_once_with("ElementChanged")
    
    @pytest.mark.unit
    def test_handle_event(self, api_wrapper):
        """Test event handling."""
        handled_data = []
        
        def event_handler(data):
            handled_data.append(data)
        
        api_wrapper.subscribe("ElementChanged", event_handler)
        
        # Simulate event from bridge
        event_data = {"elementId": 1, "changeType": "modified"}
        api_wrapper._handle_event("ElementChanged", event_data)
        
        assert len(handled_data) == 1
        assert handled_data[0] == event_data
    
    @pytest.mark.unit
    def test_handle_unknown_event(self, api_wrapper):
        """Test handling of unknown events."""
        # Should not raise exception
        api_wrapper._handle_event("UnknownEvent", {"data": "test"})
    
    @pytest.mark.unit
    def test_get_connection_status(self, api_wrapper):
        """Test getting connection status."""
        status = api_wrapper.get_connection_status()
        
        assert status["connected"] is True
        assert status["bridge_version"] == "2024.1.0"
        assert "last_activity" in status
    
    @pytest.mark.unit
    def test_get_connection_status_when_disconnected(self):
        """Test getting connection status when disconnected."""
        wrapper = RevitAPIWrapper()
        status = wrapper.get_connection_status()
        
        assert status["connected"] is False
        assert status["bridge_version"] is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_success(self, api_wrapper):
        """Test successful health check."""
        api_wrapper._bridge.CallAsync.return_value = json.dumps({
            "status": "healthy",
            "timestamp": "2024-01-01T12:00:00Z"
        })
        
        result = await api_wrapper.health_check()
        
        assert result["status"] == "healthy"
        api_wrapper._bridge.CallAsync.assert_called_once_with("HealthCheck", "{}", 5.0)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_failure(self, api_wrapper):
        """Test health check failure."""
        api_wrapper._bridge.CallAsync.side_effect = Exception("Bridge unavailable")
        
        result = await api_wrapper.health_check()
        
        assert result["status"] == "unhealthy"
        assert "error" in result
    
    @pytest.mark.unit
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_api_calls(self, api_wrapper, concurrent_test_runner):
        """Test concurrent API calls for thread safety."""
        api_wrapper._bridge.CallAsync.return_value = json.dumps({"result": "success"})
        
        async def make_call(call_id):
            return await api_wrapper.call_api("TestMethod", {"id": call_id})
        
        # Run 50 concurrent calls
        call_ids = list(range(50))
        results = await asyncio.gather(*[make_call(i) for i in call_ids])
        
        assert len(results) == 50
        assert all(result["result"] == "success" for result in results)
        assert api_wrapper._bridge.CallAsync.call_count == 50
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_memory_cleanup_after_calls(self, api_wrapper, memory_leak_detector):
        """Test that memory is properly cleaned up after API calls."""
        memory_leak_detector.start()
        
        # Make many API calls
        api_wrapper._bridge.CallAsync.return_value = json.dumps({
            "data": "x" * 1000  # 1KB of data per call
        })
        
        for i in range(100):
            await api_wrapper.call_api("TestMethod", {"iteration": i})
        
        # Check for memory leaks
        memory_stats = memory_leak_detector.check()
        
        # Should not increase memory by more than 5MB
        assert memory_stats["memory_increase_mb"] < 5.0
    
    @pytest.mark.unit
    def test_repr(self, api_wrapper):
        """Test string representation."""
        repr_str = repr(api_wrapper)
        assert "RevitAPIWrapper" in repr_str
        assert "connected=True" in repr_str
    
    @pytest.mark.unit
    def test_context_manager_usage(self):
        """Test using wrapper as context manager."""
        with patch('revitpy.api.wrapper.BridgeConnector'):
            with RevitAPIWrapper() as wrapper:
                assert wrapper is not None
            
            # Should be disconnected after context exit
            assert not wrapper._connected


@pytest.mark.unit
class TestRevitAPIWrapperErrorHandling:
    """Test error handling in RevitAPIWrapper."""
    
    @pytest.mark.asyncio
    async def test_json_decode_error_handling(self):
        """Test handling of JSON decode errors."""
        wrapper = RevitAPIWrapper()
        wrapper._connected = True
        wrapper._bridge = MagicMock()
        wrapper._bridge.CallAsync.return_value = "invalid json {"
        
        with pytest.raises(RevitAPIException) as exc_info:
            await wrapper.call_api("TestMethod", {})
        
        assert "JSON decode error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        wrapper = RevitAPIWrapper()
        wrapper._connected = True
        wrapper._bridge = MagicMock()
        wrapper._bridge.CallAsync.side_effect = asyncio.TimeoutError("Timeout")
        
        with pytest.raises(RevitAPIException) as exc_info:
            await wrapper.call_api("TestMethod", {})
        
        assert "Timeout" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_bridge_disconnection_during_call(self):
        """Test handling of bridge disconnection during API call."""
        wrapper = RevitAPIWrapper()
        wrapper._connected = True
        wrapper._bridge = MagicMock()
        
        def side_effect(*args, **kwargs):
            wrapper._connected = False
            raise ConnectionError("Bridge disconnected")
        
        wrapper._bridge.CallAsync.side_effect = side_effect
        
        with pytest.raises(RevitConnectionError):
            await wrapper.call_api("TestMethod", {})
        
        assert not wrapper._connected


@pytest.mark.unit
class TestRevitAPIWrapperConfiguration:
    """Test configuration handling in RevitAPIWrapper."""
    
    def test_load_config_from_dict(self):
        """Test loading configuration from dictionary."""
        config = {
            "timeout": 45.0,
            "retry_count": 5,
            "bridge_host": "127.0.0.1",
            "bridge_port": 9090,
            "ssl_enabled": True
        }
        
        wrapper = RevitAPIWrapper(config=config)
        
        assert wrapper._timeout == 45.0
        assert wrapper._retry_count == 5
        assert wrapper._bridge_host == "127.0.0.1"
        assert wrapper._bridge_port == 9090
        assert wrapper._ssl_enabled is True
    
    @patch('revitpy.api.wrapper.load_config_file')
    def test_load_config_from_file(self, mock_load_config):
        """Test loading configuration from file."""
        mock_load_config.return_value = {
            "api": {
                "timeout": 60.0,
                "retry_count": 3
            }
        }
        
        wrapper = RevitAPIWrapper(config_file="test_config.yaml")
        
        assert wrapper._timeout == 60.0
        assert wrapper._retry_count == 3
        mock_load_config.assert_called_once_with("test_config.yaml")
    
    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        with pytest.raises(ValueError):
            RevitAPIWrapper(config={"timeout": -1})  # Invalid timeout
        
        with pytest.raises(ValueError):
            RevitAPIWrapper(config={"retry_count": -1})  # Invalid retry count


@pytest.mark.integration
class TestRevitAPIWrapperIntegration:
    """Integration tests for RevitAPIWrapper.
    
    These tests require more setup and may be slower.
    """
    
    @pytest.mark.asyncio
    async def test_real_connection_scenario(self):
        """Test a realistic connection scenario."""
        # This would be implemented with a real test bridge
        pytest.skip("Requires test bridge setup")
    
    @pytest.mark.asyncio
    async def test_event_system_integration(self):
        """Test event system with real events."""
        # This would test the full event flow
        pytest.skip("Requires test bridge setup")