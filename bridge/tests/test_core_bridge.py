"""
Tests for core bridge functionality.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from ..core.bridge_manager import BridgeManager
from ..core.config import (
    BridgeConfig,
    CommunicationConfig,
)
from ..core.exceptions import BridgeException, CommunicationError, SerializationError


class TestBridgeConfig:
    """Test bridge configuration management."""

    def test_default_config_creation(self):
        """Test creating default configuration."""
        config = BridgeConfig()

        assert config.communication.default_protocol == "named_pipes"
        assert config.serialization.compression_enabled is True
        assert config.performance.enable_caching is True

    def test_config_from_dict(self):
        """Test creating configuration from dictionary."""
        config_dict = {
            "communication": {"default_protocol": "websocket", "websocket_port": 9000},
            "serialization": {"batch_size": 100},
        }

        config = BridgeConfig.from_dict(config_dict)

        assert config.communication.default_protocol == "websocket"
        assert config.communication.websocket_port == 9000
        assert config.serialization.batch_size == 100
        # Should keep defaults for unspecified values
        assert config.serialization.compression_enabled is True

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid configuration should not raise
        valid_config = BridgeConfig()
        errors = valid_config.validate()
        assert len(errors) == 0

        # Invalid configuration should raise
        invalid_config = BridgeConfig(
            communication=CommunicationConfig(connection_timeout=-1)
        )
        errors = invalid_config.validate()
        assert len(errors) > 0
        assert any("timeout" in error.lower() for error in errors)


class TestBridgeManager:
    """Test the main bridge manager."""

    @pytest.fixture
    def bridge_manager(self, mock_bridge_config):
        """Create bridge manager for testing."""
        config = BridgeConfig.from_dict(mock_bridge_config)
        return BridgeManager(config)

    def test_bridge_manager_initialization(self, bridge_manager):
        """Test bridge manager initialization."""
        assert bridge_manager is not None
        assert not bridge_manager.is_initialized
        assert bridge_manager.get_statistics()["total_analyses"] == 0

    @pytest.mark.asyncio
    async def test_bridge_initialization(self, bridge_manager):
        """Test bridge initialization process."""
        with patch.multiple(
            bridge_manager,
            _initialize_communication_handlers=AsyncMock(),
            _initialize_serialization=Mock(),
            _initialize_analysis_handlers=Mock(),
        ):
            await bridge_manager.initialize()
            assert bridge_manager.is_initialized

    @pytest.mark.asyncio
    async def test_bridge_shutdown(self, bridge_manager):
        """Test bridge shutdown process."""
        bridge_manager.is_initialized = True

        with patch.multiple(
            bridge_manager,
            _shutdown_communication_handlers=AsyncMock(),
            _cleanup_resources=Mock(),
        ):
            await bridge_manager.shutdown()
            assert not bridge_manager.is_initialized

    @pytest.mark.asyncio
    async def test_analysis_request_processing(
        self, bridge_manager, sample_analysis_request
    ):
        """Test processing analysis requests."""
        bridge_manager.is_initialized = True

        # Mock analysis handler
        mock_handler = AsyncMock(
            return_value={"success": True, "results": {"test": "result"}}
        )
        bridge_manager.analysis_handlers = {"energy_performance": mock_handler}

        result = await bridge_manager.process_analysis_request(sample_analysis_request)

        assert result["success"] is True
        assert "results" in result
        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_analysis_request_validation(self, bridge_manager):
        """Test analysis request validation."""
        bridge_manager.is_initialized = True

        # Invalid request - missing required fields
        invalid_request = {
            "analysis_type": "energy_performance"
            # Missing analysis_id and elements
        }

        result = await bridge_manager.process_analysis_request(invalid_request)

        assert result["success"] is False
        assert "error" in result
        assert "validation" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_analysis_type(self, bridge_manager, sample_analysis_request):
        """Test handling unknown analysis types."""
        bridge_manager.is_initialized = True
        bridge_manager.analysis_handlers = {}

        sample_analysis_request["analysis_type"] = "unknown_analysis"

        result = await bridge_manager.process_analysis_request(sample_analysis_request)

        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_statistics_tracking(self, bridge_manager):
        """Test statistics tracking."""
        initial_stats = bridge_manager.get_statistics()
        assert initial_stats["total_analyses"] == 0
        assert initial_stats["successful_analyses"] == 0

        # Simulate successful analysis
        bridge_manager.statistics.total_analyses = 5
        bridge_manager.statistics.successful_analyses = 4

        updated_stats = bridge_manager.get_statistics()
        assert updated_stats["total_analyses"] == 5
        assert updated_stats["successful_analyses"] == 4
        assert updated_stats["success_rate"] == 0.8

    def test_health_check(self, bridge_manager):
        """Test health check functionality."""
        # Uninitialized bridge should be unhealthy
        health = bridge_manager.get_health_status()
        assert health["healthy"] is False
        assert "not initialized" in health["status"].lower()

        # Initialized bridge should be healthy
        bridge_manager.is_initialized = True
        health = bridge_manager.get_health_status()
        assert health["healthy"] is True


class TestBridgeExceptions:
    """Test bridge exception handling."""

    def test_bridge_exception_creation(self):
        """Test BridgeException creation."""
        exception = BridgeException("Test error", error_code="TEST_001")

        assert str(exception) == "Test error"
        assert exception.error_code == "TEST_001"
        assert exception.timestamp is not None

    def test_communication_error(self):
        """Test CommunicationError specifics."""
        error = CommunicationError("Connection failed", protocol="websocket")

        assert str(error) == "Connection failed"
        assert error.protocol == "websocket"
        assert isinstance(error, BridgeException)

    def test_serialization_error(self):
        """Test SerializationError specifics."""
        error = SerializationError("Serialization failed", element_id="12345")

        assert str(error) == "Serialization failed"
        assert error.element_id == "12345"
        assert isinstance(error, BridgeException)

    def test_exception_with_details(self):
        """Test exception with additional details."""
        details = {"attempted_action": "connect", "retry_count": 3}
        exception = BridgeException("Operation failed", details=details)

        assert exception.details == details
        assert exception.details["retry_count"] == 3


# Mock for async methods
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)
