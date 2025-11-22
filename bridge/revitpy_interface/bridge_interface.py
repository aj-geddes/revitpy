"""
RevitPy bridge interface for handling PyRevit integration requests.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from ..core.bridge_manager import AnalysisRequest, AnalysisResult, BridgeManager
from ..core.config import BridgeConfig
from ..core.exceptions import BridgeException
from .analysis_handlers import AnalysisHandlerRegistry, get_handler_registry


@dataclass
class BridgeStatus:
    """Status information for the RevitPy bridge."""

    is_running: bool
    registered_handlers: list[str]
    active_connections: int
    total_requests_processed: int
    average_response_time: float
    last_activity_time: float | None = None


class RevitPyBridgeInterface:
    """
    Main interface for RevitPy bridge server.

    This class coordinates between the bridge manager, analysis handlers,
    and external communication protocols to provide a complete bridge service.
    """

    def __init__(self, config: BridgeConfig | None = None):
        """Initialize the bridge interface."""
        self.config = config or BridgeConfig()
        self.logger = logging.getLogger("revitpy_bridge.interface")

        # Initialize components
        self.bridge_manager = BridgeManager(self.config)
        self.handler_registry: AnalysisHandlerRegistry = get_handler_registry()

        # Status tracking
        self.start_time: float | None = None
        self.last_activity_time: float | None = None

        # Register built-in analysis handlers with bridge manager
        self._register_analysis_handlers()

        self.logger.info("RevitPy bridge interface initialized")

    async def start(self):
        """Start the bridge interface and all its components."""
        try:
            self.logger.info("Starting RevitPy bridge interface...")
            self.start_time = time.time()

            # Start bridge manager
            await self.bridge_manager.start()

            self.logger.info("RevitPy bridge interface started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start bridge interface: {e}")
            raise BridgeException(f"Bridge interface startup failed: {e}")

    async def stop(self):
        """Stop the bridge interface and cleanup resources."""
        try:
            self.logger.info("Stopping RevitPy bridge interface...")

            # Stop bridge manager
            await self.bridge_manager.stop()

            self.logger.info("RevitPy bridge interface stopped")

        except Exception as e:
            self.logger.error(f"Error stopping bridge interface: {e}")

    def _register_analysis_handlers(self):
        """Register analysis handlers with the bridge manager."""
        # Get all registered handlers
        for analysis_type in self.handler_registry.handlers:
            # Create wrapper function for the bridge manager
            async def analysis_wrapper(
                elements_data: list[dict[str, Any]],
                parameters: dict[str, Any],
                analysis_type=analysis_type,
            ) -> dict[str, Any]:
                """Wrapper to execute analysis handlers."""
                self.last_activity_time = time.time()
                return await self.handler_registry.execute_handler(
                    analysis_type, elements_data, parameters
                )

            # Register with bridge manager
            self.bridge_manager.register_analysis_handler(
                analysis_type, analysis_wrapper
            )

            self.logger.debug(f"Registered analysis handler: {analysis_type}")

    async def execute_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Execute analysis request.

        Args:
            request: Analysis request to execute

        Returns:
            Analysis result
        """
        try:
            self.logger.info(f"Executing analysis request: {request.request_id}")

            # Execute through bridge manager
            result = await self.bridge_manager.execute_analysis(request)

            self.logger.info(
                f"Analysis completed: {request.request_id} "
                f"(success: {result.success})"
            )

            return result

        except Exception as e:
            self.logger.error(f"Analysis execution failed: {e}")
            # Return error result
            return AnalysisResult(
                request_id=request.request_id, success=False, error=str(e)
            )

    def get_available_analyses(self) -> dict[str, dict[str, Any]]:
        """
        Get information about available analysis types.

        Returns:
            Dictionary of analysis types and their information
        """
        return self.handler_registry.list_handlers()

    def get_analysis_info(self, analysis_type: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific analysis type.

        Args:
            analysis_type: Type of analysis to get info for

        Returns:
            Analysis information or None if not found
        """
        handler_info = self.handler_registry.get_handler(analysis_type)

        if handler_info:
            return {
                "name": handler_info.name,
                "description": handler_info.description,
                "required_parameters": handler_info.required_parameters,
                "optional_parameters": handler_info.optional_parameters,
                "expected_categories": handler_info.expected_categories,
                "processing_time_estimate": handler_info.processing_time_estimate,
                "supports_streaming": handler_info.supports_streaming,
                "supports_async": handler_info.supports_async,
                "output_schema": handler_info.output_schema,
            }

        return None

    def get_bridge_status(self) -> BridgeStatus:
        """
        Get current bridge status.

        Returns:
            Bridge status information
        """
        manager_status = self.bridge_manager.get_status()
        handler_stats = self.handler_registry.get_statistics()

        return BridgeStatus(
            is_running=manager_status["running"],
            registered_handlers=list(self.handler_registry.handlers.keys()),
            active_connections=manager_status["metrics"]["active_connections"],
            total_requests_processed=manager_status["metrics"]["requests_processed"],
            average_response_time=manager_status["metrics"]["avg_processing_time"],
            last_activity_time=self.last_activity_time,
        )

    def get_detailed_statistics(self) -> dict[str, Any]:
        """
        Get detailed statistics about bridge operations.

        Returns:
            Detailed statistics dictionary
        """
        manager_status = self.bridge_manager.get_status()
        handler_stats = self.handler_registry.get_statistics()

        uptime = time.time() - self.start_time if self.start_time else 0

        return {
            "bridge_info": {
                "uptime_seconds": uptime,
                "start_time": self.start_time,
                "last_activity": self.last_activity_time,
                "config_summary": {
                    "debug_mode": self.config.debug_mode,
                    "log_level": self.config.log_level,
                    "websocket_port": self.config.communication.websocket_port,
                    "compression_enabled": self.config.serialization.compression_enabled,
                },
            },
            "manager_status": manager_status,
            "handler_statistics": handler_stats,
            "performance_metrics": {
                "requests_per_minute": self._calculate_requests_per_minute(),
                "average_elements_per_request": self._calculate_avg_elements_per_request(),
                "success_rate": self._calculate_success_rate(),
            },
        }

    async def validate_analysis_request(
        self, request: AnalysisRequest
    ) -> dict[str, Any]:
        """
        Validate an analysis request without executing it.

        Args:
            request: Analysis request to validate

        Returns:
            Validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "estimated_time": 0.0,
            "handler_info": None,
        }

        try:
            # Check if handler exists
            handler_info = self.handler_registry.get_handler(request.analysis_type)
            if not handler_info:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Unknown analysis type: {request.analysis_type}"
                )
                return validation_result

            validation_result["handler_info"] = {
                "name": handler_info.name,
                "description": handler_info.description,
                "supports_async": handler_info.supports_async,
            }

            # Validate parameters
            missing_params = []
            for required_param in handler_info.required_parameters:
                if required_param not in request.parameters:
                    missing_params.append(required_param)

            if missing_params:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Missing required parameters: {', '.join(missing_params)}"
                )

            # Check for unknown parameters (warning only)
            known_params = set(
                handler_info.required_parameters + handler_info.optional_parameters
            )
            unknown_params = set(request.parameters.keys()) - known_params

            if unknown_params:
                validation_result["warnings"].append(
                    f"Unknown parameters will be ignored: {', '.join(unknown_params)}"
                )

            # Validate elements data
            if not request.elements_data:
                validation_result["valid"] = False
                validation_result["errors"].append("No elements data provided")
            else:
                # Check for expected categories
                if handler_info.expected_categories:
                    found_categories = set()
                    for element in request.elements_data:
                        category = element.get("category")
                        if category:
                            found_categories.add(category)

                    expected_categories = set(handler_info.expected_categories)
                    missing_categories = expected_categories - found_categories

                    if missing_categories:
                        validation_result["warnings"].append(
                            f"Expected categories not found: {', '.join(missing_categories)}"
                        )

            # Estimate processing time
            element_count = len(request.elements_data)
            estimated_time = element_count * handler_info.processing_time_estimate
            validation_result["estimated_time"] = estimated_time

            if estimated_time > 300:  # 5 minutes
                validation_result["warnings"].append(
                    f"Long processing time estimated: {estimated_time:.1f} seconds"
                )

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {e}")

        return validation_result

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on bridge components.

        Returns:
            Health check results
        """
        health_status = {
            "overall_health": "healthy",
            "components": {},
            "timestamp": time.time(),
        }

        try:
            # Check bridge manager
            manager_status = self.bridge_manager.get_status()
            if manager_status["running"]:
                health_status["components"]["bridge_manager"] = "healthy"
            else:
                health_status["components"]["bridge_manager"] = "unhealthy"
                health_status["overall_health"] = "unhealthy"

            # Check handler registry
            handler_count = len(self.handler_registry.handlers)
            if handler_count > 0:
                health_status["components"]["analysis_handlers"] = "healthy"
                health_status["handler_count"] = handler_count
            else:
                health_status["components"]["analysis_handlers"] = "warning"
                health_status["overall_health"] = "degraded"

            # Check communication protocols
            active_connections = manager_status["metrics"]["active_connections"]
            if active_connections >= 0:
                health_status["components"]["communication"] = "healthy"
                health_status["active_connections"] = active_connections
            else:
                health_status["components"]["communication"] = "warning"

            # Check recent activity
            if self.last_activity_time:
                time_since_activity = time.time() - self.last_activity_time
                if time_since_activity < 3600:  # 1 hour
                    health_status["components"]["recent_activity"] = "healthy"
                else:
                    health_status["components"]["recent_activity"] = "warning"
            else:
                health_status["components"]["recent_activity"] = "no_activity"

        except Exception as e:
            health_status["overall_health"] = "error"
            health_status["error"] = str(e)
            self.logger.error(f"Health check failed: {e}")

        return health_status

    def register_custom_handler(
        self, analysis_type: str, handler_function: callable, **handler_config
    ):
        """
        Register a custom analysis handler.

        Args:
            analysis_type: Unique identifier for the analysis
            handler_function: Function to handle the analysis
            **handler_config: Additional handler configuration
        """
        try:
            # Register with handler registry
            self.handler_registry.register(analysis_type, **handler_config)(
                handler_function
            )

            # Register with bridge manager
            async def custom_wrapper(
                elements_data: list[dict[str, Any]], parameters: dict[str, Any]
            ) -> dict[str, Any]:
                self.last_activity_time = time.time()
                return await self.handler_registry.execute_handler(
                    analysis_type, elements_data, parameters
                )

            self.bridge_manager.register_analysis_handler(analysis_type, custom_wrapper)

            self.logger.info(f"Registered custom analysis handler: {analysis_type}")

        except Exception as e:
            self.logger.error(f"Failed to register custom handler: {e}")
            raise BridgeException(f"Handler registration failed: {e}")

    def _calculate_requests_per_minute(self) -> float:
        """Calculate requests per minute based on recent activity."""
        manager_metrics = self.bridge_manager.metrics
        total_requests = manager_metrics["requests_processed"]

        if self.start_time and total_requests > 0:
            uptime_minutes = (time.time() - self.start_time) / 60
            return total_requests / max(uptime_minutes, 1)

        return 0.0

    def _calculate_avg_elements_per_request(self) -> float:
        """Calculate average elements per request."""
        # This would require tracking element counts
        # For now, return a placeholder
        return 0.0

    def _calculate_success_rate(self) -> float:
        """Calculate success rate of analysis requests."""
        manager_metrics = self.bridge_manager.metrics
        total = manager_metrics["requests_processed"]
        failed = manager_metrics["requests_failed"]

        if total > 0:
            return (total - failed) / total

        return 0.0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Convenience function for creating and running bridge
async def create_and_run_bridge(
    config: BridgeConfig | None = None, port: int | None = None
) -> RevitPyBridgeInterface:
    """
    Create and start a RevitPy bridge interface.

    Args:
        config: Bridge configuration
        port: WebSocket port override

    Returns:
        Running bridge interface
    """
    # Create config with port override if specified
    if config is None:
        config = BridgeConfig()

    if port is not None:
        config.communication.websocket_port = port

    # Create and start bridge
    bridge = RevitPyBridgeInterface(config)
    await bridge.start()

    return bridge


# Main entry point for running bridge as standalone service
async def main():
    """Main entry point for running bridge service."""
    import signal
    import sys

    # Create bridge with default configuration
    bridge = RevitPyBridgeInterface()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        asyncio.create_task(bridge.stop())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start bridge
        await bridge.start()

        print("RevitPy Bridge is running...")
        print(
            f"WebSocket server: ws://localhost:{bridge.config.communication.websocket_port}/bridge"
        )
        print("Press Ctrl+C to stop")

        # Run indefinitely
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
