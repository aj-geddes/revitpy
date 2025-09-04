"""Monitoring, logging, and analytics infrastructure."""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_client.core import REGISTRY


# Prometheus metrics
REQUESTS_TOTAL = Counter(
    'revitpy_registry_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'revitpy_registry_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

PACKAGE_DOWNLOADS = Counter(
    'revitpy_registry_downloads_total',
    'Total package downloads',
    ['package_name', 'version']
)

PACKAGE_UPLOADS = Counter(
    'revitpy_registry_uploads_total',
    'Total package uploads',
    ['package_name']
)

ACTIVE_USERS = Gauge(
    'revitpy_registry_active_users',
    'Number of active users'
)

DATABASE_CONNECTIONS = Gauge(
    'revitpy_registry_db_connections',
    'Database connection pool size'
)

CACHE_HITS = Counter(
    'revitpy_registry_cache_hits_total',
    'Cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'revitpy_registry_cache_misses_total',
    'Cache misses',
    ['cache_type']
)


class MetricsCollector:
    """Collects and manages application metrics."""
    
    def __init__(self):
        self.start_time = time.time()
        self._active_requests: Dict[str, float] = {}
    
    def record_request_start(self, method: str, endpoint: str) -> str:
        """Record the start of an HTTP request."""
        request_id = str(uuid4())
        self._active_requests[request_id] = time.time()
        return request_id
    
    def record_request_end(
        self,
        request_id: str,
        method: str,
        endpoint: str,
        status_code: int
    ):
        """Record the end of an HTTP request."""
        if request_id in self._active_requests:
            duration = time.time() - self._active_requests[request_id]
            del self._active_requests[request_id]
            
            REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
    
    def record_download(self, package_name: str, version: str):
        """Record a package download."""
        PACKAGE_DOWNLOADS.labels(
            package_name=package_name,
            version=version
        ).inc()
    
    def record_upload(self, package_name: str):
        """Record a package upload."""
        PACKAGE_UPLOADS.labels(package_name=package_name).inc()
    
    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        CACHE_HITS.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        CACHE_MISSES.labels(cache_type=cache_type).inc()
    
    def set_active_users(self, count: int):
        """Set the number of active users."""
        ACTIVE_USERS.set(count)
    
    def set_database_connections(self, count: int):
        """Set the database connection count."""
        DATABASE_CONNECTIONS.set(count)
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest(REGISTRY)


class StructuredLogger:
    """Structured logging configuration."""
    
    def __init__(self, level: str = "INFO", service_name: str = "revitpy-registry"):
        self.level = level
        self.service_name = service_name
        self.logger = self._configure_logger()
    
    def _configure_logger(self):
        """Configure structured logging."""
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]
        
        # Add JSON formatting for production
        if os.getenv("ENVIRONMENT", "development") == "production":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        return structlog.get_logger(self.service_name)
    
    def get_logger(self):
        """Get the configured logger."""
        return self.logger


class AnalyticsTracker:
    """Tracks analytics events for business intelligence."""
    
    def __init__(self):
        self.events: List[Dict] = []
    
    def track_event(
        self,
        event_name: str,
        user_id: Optional[str] = None,
        properties: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ):
        """Track an analytics event."""
        event = {
            "event_name": event_name,
            "user_id": user_id,
            "properties": properties or {},
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "session_id": getattr(self, '_session_id', str(uuid4())),
        }
        
        self.events.append(event)
        
        # Also log the event
        logger = structlog.get_logger("analytics")
        logger.info("analytics_event", **event)
    
    def track_package_view(
        self,
        package_name: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None
    ):
        """Track a package view event."""
        self.track_event(
            "package_view",
            user_id=user_id,
            properties={
                "package_name": package_name,
                "user_agent": user_agent,
                "referer": referer,
            }
        )
    
    def track_package_download(
        self,
        package_name: str,
        version: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        country: Optional[str] = None
    ):
        """Track a package download event."""
        self.track_event(
            "package_download",
            user_id=user_id,
            properties={
                "package_name": package_name,
                "version": version,
                "ip_address": ip_address,
                "country": country,
            }
        )
    
    def track_package_upload(
        self,
        package_name: str,
        version: str,
        user_id: str,
        file_size: int
    ):
        """Track a package upload event."""
        self.track_event(
            "package_upload",
            user_id=user_id,
            properties={
                "package_name": package_name,
                "version": version,
                "file_size": file_size,
            }
        )
    
    def track_search(
        self,
        query: str,
        results_count: int,
        user_id: Optional[str] = None
    ):
        """Track a search event."""
        self.track_event(
            "search",
            user_id=user_id,
            properties={
                "query": query,
                "results_count": results_count,
            }
        )
    
    def track_user_registration(self, user_id: str, email: str):
        """Track a user registration event."""
        self.track_event(
            "user_registration",
            user_id=user_id,
            properties={
                "email": email,
            }
        )
    
    def track_api_key_creation(self, user_id: str, scopes: str):
        """Track API key creation event."""
        self.track_event(
            "api_key_creation",
            user_id=user_id,
            properties={
                "scopes": scopes,
            }
        )
    
    def get_events(self, limit: Optional[int] = None) -> List[Dict]:
        """Get tracked events."""
        events = self.events
        if limit:
            events = events[-limit:]
        return events
    
    def clear_events(self):
        """Clear all tracked events."""
        self.events.clear()


class HealthChecker:
    """System health checking and monitoring."""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check function."""
        self.checks[name] = check_func
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_status = "healthy"
        
        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result if isinstance(result, dict) else {}
                }
                
                if not result:
                    overall_status = "unhealthy"
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat()
        }


class PerformanceProfiler:
    """Performance profiling and monitoring."""
    
    def __init__(self):
        self.active_operations: Dict[str, float] = {}
        self.completed_operations: List[Dict] = []
    
    def start_operation(self, operation_name: str, metadata: Optional[Dict] = None) -> str:
        """Start timing an operation."""
        operation_id = str(uuid4())
        self.active_operations[operation_id] = {
            "name": operation_name,
            "start_time": time.time(),
            "metadata": metadata or {}
        }
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, error: Optional[str] = None):
        """End timing an operation."""
        if operation_id not in self.active_operations:
            return
        
        operation = self.active_operations.pop(operation_id)
        duration = time.time() - operation["start_time"]
        
        completed_operation = {
            "name": operation["name"],
            "duration": duration,
            "success": success,
            "error": error,
            "metadata": operation["metadata"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.completed_operations.append(completed_operation)
        
        # Keep only last 1000 operations
        if len(self.completed_operations) > 1000:
            self.completed_operations = self.completed_operations[-1000:]
        
        # Log slow operations
        if duration > 5.0:  # 5 seconds threshold
            logger = structlog.get_logger("performance")
            logger.warning(
                "slow_operation",
                operation_name=operation["name"],
                duration=duration,
                **operation["metadata"]
            )
    
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict:
        """Get statistics for operations."""
        operations = self.completed_operations
        
        if operation_name:
            operations = [op for op in operations if op["name"] == operation_name]
        
        if not operations:
            return {"count": 0}
        
        durations = [op["duration"] for op in operations]
        successes = sum(1 for op in operations if op["success"])
        
        return {
            "count": len(operations),
            "success_rate": successes / len(operations),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "recent_operations": operations[-10:]  # Last 10 operations
        }


class MonitoringService:
    """Main monitoring service that coordinates all monitoring components."""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.logger = StructuredLogger()
        self.analytics = AnalyticsTracker()
        self.health = HealthChecker()
        self.profiler = PerformanceProfiler()
    
    async def initialize(self):
        """Initialize the monitoring service."""
        # Register default health checks
        self.health.register_check("database", self._check_database)
        self.health.register_check("cache", self._check_cache)
        self.health.register_check("storage", self._check_storage)
    
    async def _check_database(self) -> bool:
        """Check database connectivity."""
        try:
            # This would be implemented with actual database check
            return True
        except Exception:
            return False
    
    async def _check_cache(self) -> bool:
        """Check cache connectivity."""
        try:
            # This would be implemented with actual cache check
            return True
        except Exception:
            return False
    
    async def _check_storage(self) -> bool:
        """Check storage availability."""
        try:
            # This would be implemented with actual storage check
            return True
        except Exception:
            return False
    
    def get_dashboard_data(self) -> Dict:
        """Get data for monitoring dashboard."""
        return {
            "uptime": time.time() - self.metrics.start_time,
            "active_requests": len(self.metrics._active_requests),
            "recent_events": self.analytics.get_events(limit=50),
            "performance_stats": self.profiler.get_operation_stats(),
            "metrics_summary": {
                "total_requests": REQUESTS_TOTAL._value._value,
                "total_downloads": PACKAGE_DOWNLOADS._value._value,
                "total_uploads": PACKAGE_UPLOADS._value._value,
            }
        }


# Global monitoring service instance
monitoring_service = MonitoringService()


def get_monitoring_service() -> MonitoringService:
    """Get the global monitoring service instance."""
    return monitoring_service