"""Tests for monitoring, logging, and analytics infrastructure."""

import time
from datetime import datetime
from unittest.mock import patch

import pytest
from revitpy_package_manager.registry.services.monitoring import (
    AnalyticsTracker,
    HealthChecker,
    MetricsCollector,
    MonitoringService,
    PerformanceProfiler,
    StructuredLogger,
    get_monitoring_service,
)


class TestMetricsCollector:
    """Test MetricsCollector for tracking application metrics."""

    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initializes correctly."""
        collector = MetricsCollector()

        assert hasattr(collector, "start_time")
        assert isinstance(collector.start_time, float)
        assert len(collector._active_requests) == 0

    def test_record_request_lifecycle(self):
        """Test recording request start and end."""
        collector = MetricsCollector()

        # Record request start
        request_id = collector.record_request_start("GET", "/api/packages")
        assert request_id is not None
        assert request_id in collector._active_requests

        # Small delay to ensure duration > 0
        time.sleep(0.01)

        # Record request end
        collector.record_request_end(request_id, "GET", "/api/packages", 200)
        assert request_id not in collector._active_requests

    def test_record_request_end_missing_id(self):
        """Test recording end for non-existent request ID."""
        collector = MetricsCollector()

        # Should not raise error
        collector.record_request_end("nonexistent-id", "GET", "/api/test", 404)

    def test_record_download(self):
        """Test recording package download."""
        collector = MetricsCollector()

        # Should not raise error
        collector.record_download("test-package", "1.0.0")

    def test_record_upload(self):
        """Test recording package upload."""
        collector = MetricsCollector()

        # Should not raise error
        collector.record_upload("test-package")

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        collector = MetricsCollector()

        # Should not raise error
        collector.record_cache_hit("package_metadata")

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        collector = MetricsCollector()

        # Should not raise error
        collector.record_cache_miss("package_metadata")

    def test_set_active_users(self):
        """Test setting active users count."""
        collector = MetricsCollector()

        # Should not raise error
        collector.set_active_users(42)

    def test_set_database_connections(self):
        """Test setting database connections count."""
        collector = MetricsCollector()

        # Should not raise error
        collector.set_database_connections(10)

    def test_get_metrics(self):
        """Test getting Prometheus metrics."""
        collector = MetricsCollector()

        metrics = collector.get_metrics()
        assert isinstance(metrics, str | bytes)
        # Metrics should contain some prometheus format
        if isinstance(metrics, bytes):
            metrics = metrics.decode("utf-8")
        assert "revitpy_registry" in metrics.lower() or "#" in metrics


class TestStructuredLogger:
    """Test StructuredLogger for structured logging configuration."""

    def test_structured_logger_initialization(self):
        """Test StructuredLogger initializes with defaults."""
        logger = StructuredLogger()

        assert logger.level == "INFO"
        assert logger.service_name == "revitpy-registry"
        assert logger.logger is not None

    def test_structured_logger_custom_config(self):
        """Test StructuredLogger with custom configuration."""
        logger = StructuredLogger(level="DEBUG", service_name="test-service")

        assert logger.level == "DEBUG"
        assert logger.service_name == "test-service"

    def test_get_logger(self):
        """Test getting configured logger."""
        logger = StructuredLogger()

        log = logger.get_logger()
        assert log is not None
        # Should have structlog methods
        assert hasattr(log, "info")
        assert hasattr(log, "debug")
        assert hasattr(log, "error")
        assert hasattr(log, "warning")

    def test_logger_production_mode(self):
        """Test logger uses JSON in production mode."""
        with patch("revitpy_package_manager.config.get_settings") as mock_settings:
            mock_settings.return_value.is_production = True
            mock_settings.return_value.monitoring.log_json = True

            logger = StructuredLogger()
            # Should not raise error
            assert logger.logger is not None

    def test_logger_development_mode(self):
        """Test logger uses console renderer in development."""
        with patch("revitpy_package_manager.config.get_settings") as mock_settings:
            mock_settings.return_value.is_production = False
            mock_settings.return_value.monitoring.log_json = False

            logger = StructuredLogger()
            # Should not raise error
            assert logger.logger is not None


class TestAnalyticsTracker:
    """Test AnalyticsTracker for business intelligence."""

    def test_analytics_tracker_initialization(self):
        """Test AnalyticsTracker initializes correctly."""
        tracker = AnalyticsTracker()

        assert isinstance(tracker.events, list)
        assert len(tracker.events) == 0

    def test_track_event(self):
        """Test tracking a basic event."""
        tracker = AnalyticsTracker()

        tracker.track_event(
            "test_event", user_id="user123", properties={"key": "value"}
        )

        assert len(tracker.events) == 1
        event = tracker.events[0]
        assert event["event_name"] == "test_event"
        assert event["user_id"] == "user123"
        assert event["properties"]["key"] == "value"
        assert "timestamp" in event
        assert "session_id" in event

    def test_track_event_without_user(self):
        """Test tracking event without user ID."""
        tracker = AnalyticsTracker()

        tracker.track_event("anonymous_event")

        assert len(tracker.events) == 1
        event = tracker.events[0]
        assert event["user_id"] is None
        assert event["event_name"] == "anonymous_event"

    def test_track_event_custom_timestamp(self):
        """Test tracking event with custom timestamp."""
        tracker = AnalyticsTracker()
        custom_time = datetime(2024, 1, 1, 12, 0, 0)

        tracker.track_event("timed_event", timestamp=custom_time)

        event = tracker.events[0]
        assert "2024-01-01" in event["timestamp"]

    def test_track_package_view(self):
        """Test tracking package view event."""
        tracker = AnalyticsTracker()

        tracker.track_package_view(
            "my-package",
            user_id="user123",
            user_agent="Mozilla/5.0",
            referer="https://example.com",
        )

        assert len(tracker.events) == 1
        event = tracker.events[0]
        assert event["event_name"] == "package_view"
        assert event["properties"]["package_name"] == "my-package"
        assert event["properties"]["user_agent"] == "Mozilla/5.0"

    def test_track_package_download(self):
        """Test tracking package download event."""
        tracker = AnalyticsTracker()

        tracker.track_package_download(
            "my-package",
            "1.0.0",
            user_id="user123",
            ip_address="192.168.1.1",
            country="US",
        )

        event = tracker.events[0]
        assert event["event_name"] == "package_download"
        assert event["properties"]["package_name"] == "my-package"
        assert event["properties"]["version"] == "1.0.0"
        assert event["properties"]["country"] == "US"

    def test_track_package_upload(self):
        """Test tracking package upload event."""
        tracker = AnalyticsTracker()

        tracker.track_package_upload(
            "my-package",
            "2.0.0",
            "user123",
            1024 * 1024,  # 1MB
        )

        event = tracker.events[0]
        assert event["event_name"] == "package_upload"
        assert event["properties"]["file_size"] == 1024 * 1024

    def test_track_search(self):
        """Test tracking search event."""
        tracker = AnalyticsTracker()

        tracker.track_search("revit automation", 15, user_id="user123")

        event = tracker.events[0]
        assert event["event_name"] == "search"
        assert event["properties"]["query"] == "revit automation"
        assert event["properties"]["results_count"] == 15

    def test_track_user_registration(self):
        """Test tracking user registration."""
        tracker = AnalyticsTracker()

        tracker.track_user_registration("user123", "user@example.com")

        event = tracker.events[0]
        assert event["event_name"] == "user_registration"
        assert event["properties"]["email"] == "user@example.com"

    def test_track_api_key_creation(self):
        """Test tracking API key creation."""
        tracker = AnalyticsTracker()

        tracker.track_api_key_creation("user123", "read:packages,write:packages")

        event = tracker.events[0]
        assert event["event_name"] == "api_key_creation"
        assert "read:packages" in event["properties"]["scopes"]

    def test_get_events(self):
        """Test getting all events."""
        tracker = AnalyticsTracker()

        tracker.track_event("event1")
        tracker.track_event("event2")
        tracker.track_event("event3")

        events = tracker.get_events()
        assert len(events) == 3

    def test_get_events_with_limit(self):
        """Test getting limited number of events."""
        tracker = AnalyticsTracker()

        for i in range(10):
            tracker.track_event(f"event{i}")

        events = tracker.get_events(limit=5)
        assert len(events) == 5
        # Should return last 5 events
        assert events[0]["event_name"] == "event5"

    def test_clear_events(self):
        """Test clearing all events."""
        tracker = AnalyticsTracker()

        tracker.track_event("event1")
        tracker.track_event("event2")
        assert len(tracker.events) == 2

        tracker.clear_events()
        assert len(tracker.events) == 0


class TestHealthChecker:
    """Test HealthChecker for system health monitoring."""

    @pytest.mark.asyncio
    async def test_health_checker_initialization(self):
        """Test HealthChecker initializes correctly."""
        checker = HealthChecker()

        assert isinstance(checker.checks, dict)
        assert len(checker.checks) == 0

    @pytest.mark.asyncio
    async def test_register_check(self):
        """Test registering a health check."""
        checker = HealthChecker()

        async def dummy_check():
            return True

        checker.register_check("dummy", dummy_check)
        assert "dummy" in checker.checks
        assert checker.checks["dummy"] == dummy_check

    @pytest.mark.asyncio
    async def test_run_health_checks_all_healthy(self):
        """Test running health checks when all are healthy."""
        checker = HealthChecker()

        async def check1():
            return True

        async def check2():
            return {"status": "ok"}

        checker.register_check("check1", check1)
        checker.register_check("check2", check2)

        result = await checker.run_health_checks()

        assert result["status"] == "healthy"
        assert "check1" in result["checks"]
        assert "check2" in result["checks"]
        assert result["checks"]["check1"]["status"] == "healthy"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_run_health_checks_with_failure(self):
        """Test health checks with a failing check."""
        checker = HealthChecker()

        async def healthy_check():
            return True

        async def failing_check():
            return False

        checker.register_check("healthy", healthy_check)
        checker.register_check("failing", failing_check)

        result = await checker.run_health_checks()

        assert result["status"] == "unhealthy"
        assert result["checks"]["healthy"]["status"] == "healthy"
        assert result["checks"]["failing"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_run_health_checks_with_exception(self):
        """Test health checks when check raises exception."""
        checker = HealthChecker()

        async def error_check():
            raise RuntimeError("Check failed")

        checker.register_check("error", error_check)

        result = await checker.run_health_checks()

        assert result["status"] == "unhealthy"
        assert result["checks"]["error"]["status"] == "error"
        assert "Check failed" in result["checks"]["error"]["error"]

    @pytest.mark.asyncio
    async def test_empty_health_checks(self):
        """Test running health checks with no checks registered."""
        checker = HealthChecker()

        result = await checker.run_health_checks()

        assert result["status"] == "healthy"
        assert len(result["checks"]) == 0


class TestPerformanceProfiler:
    """Test PerformanceProfiler for performance monitoring."""

    def test_profiler_initialization(self):
        """Test PerformanceProfiler initializes correctly."""
        profiler = PerformanceProfiler()

        assert len(profiler.active_operations) == 0
        assert len(profiler.completed_operations) == 0

    def test_start_operation(self):
        """Test starting an operation."""
        profiler = PerformanceProfiler()

        op_id = profiler.start_operation("test_operation")

        assert op_id is not None
        assert op_id in profiler.active_operations

    def test_start_operation_with_metadata(self):
        """Test starting operation with metadata."""
        profiler = PerformanceProfiler()

        metadata = {"user": "test", "action": "upload"}
        op_id = profiler.start_operation("upload_package", metadata)

        assert profiler.active_operations[op_id]["metadata"] == metadata

    def test_end_operation(self):
        """Test ending an operation."""
        profiler = PerformanceProfiler()

        op_id = profiler.start_operation("test_operation")
        time.sleep(0.01)  # Ensure some duration
        profiler.end_operation(op_id, success=True)

        assert op_id not in profiler.active_operations
        assert len(profiler.completed_operations) == 1

        completed = profiler.completed_operations[0]
        assert completed["name"] == "test_operation"
        assert completed["success"] is True
        assert completed["duration"] > 0

    def test_end_operation_with_error(self):
        """Test ending operation with error."""
        profiler = PerformanceProfiler()

        op_id = profiler.start_operation("failing_operation")
        profiler.end_operation(op_id, success=False, error="Connection timeout")

        completed = profiler.completed_operations[0]
        assert completed["success"] is False
        assert completed["error"] == "Connection timeout"

    def test_end_nonexistent_operation(self):
        """Test ending operation that doesn't exist."""
        profiler = PerformanceProfiler()

        # Should not raise error
        profiler.end_operation("nonexistent-id")
        assert len(profiler.completed_operations) == 0

    def test_completed_operations_limit(self):
        """Test that completed operations are limited to 1000."""
        profiler = PerformanceProfiler()

        # Add more than 1000 operations
        for i in range(1100):
            op_id = profiler.start_operation(f"operation_{i}")
            profiler.end_operation(op_id)

        # Should keep only last 1000
        assert len(profiler.completed_operations) == 1000

    def test_get_operation_stats_all(self):
        """Test getting stats for all operations."""
        profiler = PerformanceProfiler()

        for _i in range(5):
            op_id = profiler.start_operation("test_op")
            time.sleep(0.01)
            profiler.end_operation(op_id, success=True)

        stats = profiler.get_operation_stats()

        assert stats["count"] == 5
        assert stats["success_rate"] == 1.0
        assert stats["avg_duration"] > 0
        assert stats["min_duration"] > 0
        assert stats["max_duration"] > 0
        assert len(stats["recent_operations"]) == 5

    def test_get_operation_stats_by_name(self):
        """Test getting stats for specific operation name."""
        profiler = PerformanceProfiler()

        # Add different operations
        for _i in range(3):
            op_id = profiler.start_operation("op_a")
            profiler.end_operation(op_id)

        for _i in range(2):
            op_id = profiler.start_operation("op_b")
            profiler.end_operation(op_id)

        stats_a = profiler.get_operation_stats("op_a")
        stats_b = profiler.get_operation_stats("op_b")

        assert stats_a["count"] == 3
        assert stats_b["count"] == 2

    def test_get_operation_stats_empty(self):
        """Test getting stats when no operations."""
        profiler = PerformanceProfiler()

        stats = profiler.get_operation_stats()

        assert stats["count"] == 0

    def test_get_operation_stats_nonexistent_name(self):
        """Test getting stats for non-existent operation."""
        profiler = PerformanceProfiler()

        op_id = profiler.start_operation("test")
        profiler.end_operation(op_id)

        stats = profiler.get_operation_stats("nonexistent")

        assert stats["count"] == 0


class TestMonitoringService:
    """Test MonitoringService that coordinates all monitoring."""

    def test_monitoring_service_initialization(self):
        """Test MonitoringService initializes all components."""
        service = MonitoringService()

        assert isinstance(service.metrics, MetricsCollector)
        assert isinstance(service.logger, StructuredLogger)
        assert isinstance(service.analytics, AnalyticsTracker)
        assert isinstance(service.health, HealthChecker)
        assert isinstance(service.profiler, PerformanceProfiler)

    @pytest.mark.asyncio
    async def test_monitoring_service_initialize(self):
        """Test initializing monitoring service."""
        service = MonitoringService()

        await service.initialize()

        # Should have registered default health checks
        assert "database" in service.health.checks
        assert "cache" in service.health.checks
        assert "storage" in service.health.checks

    @pytest.mark.asyncio
    async def test_check_database(self):
        """Test database health check."""
        service = MonitoringService()

        result = await service._check_database()
        # Default implementation returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_check_cache(self):
        """Test cache health check."""
        service = MonitoringService()

        result = await service._check_cache()
        # Default implementation returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_check_storage(self):
        """Test storage health check."""
        service = MonitoringService()

        result = await service._check_storage()
        # Default implementation returns True
        assert result is True

    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        service = MonitoringService()

        data = service.get_dashboard_data()

        assert "uptime" in data
        assert "active_requests" in data
        assert "recent_events" in data
        assert "performance_stats" in data
        assert "metrics_summary" in data

        # Verify structure
        assert isinstance(data["uptime"], float)
        assert isinstance(data["active_requests"], int)
        assert isinstance(data["recent_events"], list)


class TestGlobalMonitoringService:
    """Test global monitoring service instance."""

    def test_get_monitoring_service_returns_singleton(self):
        """Test get_monitoring_service returns same instance."""
        service1 = get_monitoring_service()
        service2 = get_monitoring_service()

        assert service1 is service2

    def test_global_service_is_initialized(self):
        """Test global monitoring service is properly initialized."""
        service = get_monitoring_service()

        assert isinstance(service, MonitoringService)
        assert service.metrics is not None
        assert service.logger is not None
