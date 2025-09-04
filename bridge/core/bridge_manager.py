"""
Main bridge manager for coordinating PyRevit-RevitPy interoperability.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List, Union
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from pathlib import Path

from .config import BridgeConfig
from .exceptions import (
    BridgeException, BridgeTimeoutError, BridgeConnectionError,
    BridgeAnalysisError, BridgeResourceError
)
from ..serialization.element_serializer import RevitElementSerializer
from ..communication.pipe_server import NamedPipeServer
from ..communication.websocket_server import WebSocketBridgeServer
from ..communication.file_exchange import FileExchangeHandler


@dataclass
class AnalysisRequest:
    """Represents a request for RevitPy analysis."""
    
    request_id: str
    analysis_type: str
    elements_data: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    timeout: Optional[int] = None
    priority: int = 0
    callback: Optional[Callable] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'request_id': self.request_id,
            'analysis_type': self.analysis_type,
            'elements_data': self.elements_data,
            'parameters': self.parameters,
            'timeout': self.timeout,
            'priority': self.priority
        }


@dataclass
class AnalysisResult:
    """Represents the result of a RevitPy analysis."""
    
    request_id: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'request_id': self.request_id,
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'execution_time': self.execution_time,
            'metadata': self.metadata or {}
        }


class BridgeManager:
    """Main manager for PyRevit-RevitPy bridge operations."""
    
    def __init__(self, config: BridgeConfig):
        """Initialize the bridge manager."""
        self.config = config
        self.logger = self._setup_logging()
        self.serializer = RevitElementSerializer(config.serialization)
        
        # Communication handlers
        self.pipe_server: Optional[NamedPipeServer] = None
        self.websocket_server: Optional[WebSocketBridgeServer] = None
        self.file_handler = FileExchangeHandler(config.communication)
        
        # Analysis management
        self.analysis_handlers: Dict[str, Callable] = {}
        self.pending_requests: Dict[str, AnalysisRequest] = {}
        self.request_futures: Dict[str, Future] = {}
        
        # Threading and async management
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.loop_thread: Optional[threading.Thread] = None
        
        # State management
        self.is_running = False
        self.metrics = {
            'requests_processed': 0,
            'requests_failed': 0,
            'avg_processing_time': 0.0,
            'active_connections': 0
        }
        
        self.logger.info("Bridge manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('revitpy_bridge')
        logger.setLevel(getattr(logging, self.config.log_level))
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_format)
            logger.addHandler(console_handler)
            
            # File handler if specified
            if self.config.log_file:
                log_path = Path(self.config.log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                file_handler = logging.FileHandler(self.config.log_file)
                file_handler.setFormatter(console_format)
                logger.addHandler(file_handler)
        
        return logger
    
    async def start(self):
        """Start the bridge manager and all communication handlers."""
        if self.is_running:
            self.logger.warning("Bridge manager is already running")
            return
        
        self.logger.info("Starting bridge manager...")
        self.is_running = True
        
        try:
            # Start communication handlers
            await self._start_communication_handlers()
            
            # Start background tasks
            asyncio.create_task(self._monitoring_task())
            asyncio.create_task(self._cleanup_task())
            
            self.logger.info("Bridge manager started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start bridge manager: {e}")
            self.is_running = False
            raise BridgeException(f"Failed to start bridge: {e}")
    
    async def stop(self):
        """Stop the bridge manager and cleanup resources."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping bridge manager...")
        self.is_running = False
        
        # Cancel pending requests
        for request_id, future in self.request_futures.items():
            if not future.done():
                future.cancel()
        
        # Stop communication handlers
        if self.websocket_server:
            await self.websocket_server.stop()
        
        if self.pipe_server:
            await self.pipe_server.stop()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.logger.info("Bridge manager stopped")
    
    async def _start_communication_handlers(self):
        """Start all configured communication handlers."""
        # Start WebSocket server
        self.websocket_server = WebSocketBridgeServer(self.config.communication)
        self.websocket_server.set_message_handler(self._handle_websocket_message)
        await self.websocket_server.start()
        
        # Start named pipe server
        self.pipe_server = NamedPipeServer(self.config.communication)
        self.pipe_server.set_message_handler(self._handle_pipe_message)
        await self.pipe_server.start()
        
        self.logger.info("Communication handlers started")
    
    def register_analysis_handler(self, analysis_type: str, 
                                handler: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]):
        """Register a handler for a specific analysis type."""
        self.analysis_handlers[analysis_type] = handler
        self.logger.info(f"Registered analysis handler: {analysis_type}")
    
    def unregister_analysis_handler(self, analysis_type: str):
        """Unregister an analysis handler."""
        if analysis_type in self.analysis_handlers:
            del self.analysis_handlers[analysis_type]
            self.logger.info(f"Unregistered analysis handler: {analysis_type}")
    
    async def execute_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """Execute an analysis request."""
        start_time = time.time()
        self.logger.info(f"Executing analysis request: {request.request_id}")
        
        try:
            # Validate request
            self._validate_analysis_request(request)
            
            # Store request
            self.pending_requests[request.request_id] = request
            
            # Check if handler exists
            if request.analysis_type not in self.analysis_handlers:
                raise BridgeAnalysisError(
                    request.analysis_type,
                    f"No handler registered for analysis type: {request.analysis_type}"
                )
            
            # Execute analysis
            handler = self.analysis_handlers[request.analysis_type]
            
            # Run in thread pool to avoid blocking
            future = self.executor.submit(
                self._execute_analysis_sync, 
                handler, 
                request.elements_data, 
                request.parameters
            )
            
            self.request_futures[request.request_id] = future
            
            # Wait for result with timeout
            timeout = request.timeout or self.config.performance.analysis_timeout
            try:
                result_data = future.result(timeout=timeout)
            except TimeoutError:
                future.cancel()
                raise BridgeTimeoutError("analysis", timeout)
            
            # Create successful result
            execution_time = time.time() - start_time
            result = AnalysisResult(
                request_id=request.request_id,
                success=True,
                data=result_data,
                execution_time=execution_time,
                metadata={
                    'analysis_type': request.analysis_type,
                    'element_count': len(request.elements_data),
                    'parameters': request.parameters
                }
            )
            
            # Update metrics
            self.metrics['requests_processed'] += 1
            self._update_avg_processing_time(execution_time)
            
            self.logger.info(f"Analysis completed successfully: {request.request_id} "
                           f"({execution_time:.2f}s)")
            
            return result
            
        except Exception as e:
            # Create error result
            execution_time = time.time() - start_time
            result = AnalysisResult(
                request_id=request.request_id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
            
            # Update metrics
            self.metrics['requests_failed'] += 1
            
            self.logger.error(f"Analysis failed: {request.request_id}: {e}")
            return result
            
        finally:
            # Cleanup
            self.pending_requests.pop(request.request_id, None)
            self.request_futures.pop(request.request_id, None)
    
    def _execute_analysis_sync(self, handler: Callable, elements_data: List[Dict[str, Any]], 
                              parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis synchronously in thread pool."""
        try:
            return handler(elements_data, parameters)
        except Exception as e:
            self.logger.error(f"Analysis handler error: {e}")
            raise BridgeAnalysisError("execution", str(e))
    
    def _validate_analysis_request(self, request: AnalysisRequest):
        """Validate an analysis request."""
        errors = []
        
        if not request.request_id:
            errors.append("Request ID is required")
        
        if not request.analysis_type:
            errors.append("Analysis type is required")
        
        if not request.elements_data:
            errors.append("Elements data is required")
        
        # Check resource limits
        element_count = len(request.elements_data)
        if element_count > self.config.serialization.streaming_threshold:
            memory_estimate = element_count * 1024  # Rough estimate
            if memory_estimate > self.config.serialization.max_memory_mb * 1024 * 1024:
                errors.append(f"Dataset too large: {element_count} elements "
                            f"(estimated {memory_estimate/1024/1024:.1f}MB)")
        
        if errors:
            raise BridgeException(f"Request validation failed: {'; '.join(errors)}")
    
    async def _handle_websocket_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming WebSocket messages."""
        try:
            message_type = message.get('type')
            
            if message_type == 'analysis_request':
                request_data = message.get('data', {})
                request = AnalysisRequest(**request_data)
                result = await self.execute_analysis(request)
                return {'type': 'analysis_result', 'data': result.to_dict()}
            
            elif message_type == 'ping':
                return {'type': 'pong', 'data': {'timestamp': time.time()}}
            
            elif message_type == 'get_metrics':
                return {'type': 'metrics', 'data': self.metrics}
            
            else:
                return {'type': 'error', 'data': {'error': f'Unknown message type: {message_type}'}}
                
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            return {'type': 'error', 'data': {'error': str(e)}}
    
    async def _handle_pipe_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming named pipe messages."""
        return await self._handle_websocket_message(message)  # Same logic
    
    async def _monitoring_task(self):
        """Background task for monitoring and metrics."""
        while self.is_running:
            try:
                if self.config.performance.enable_monitoring:
                    self._update_connection_metrics()
                    
                    if self.config.performance.log_performance_metrics:
                        self.logger.info(f"Bridge metrics: {self.metrics}")
                
                await asyncio.sleep(self.config.performance.metrics_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring task error: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _cleanup_task(self):
        """Background task for cleanup operations."""
        while self.is_running:
            try:
                # Cleanup file exchange
                await self.file_handler.cleanup_old_files()
                
                # Cleanup expired requests
                current_time = time.time()
                expired_requests = []
                
                for request_id, request in self.pending_requests.items():
                    if (current_time - request.timestamp if hasattr(request, 'timestamp') 
                        else 0) > self.config.performance.analysis_timeout:
                        expired_requests.append(request_id)
                
                for request_id in expired_requests:
                    self.logger.warning(f"Cleaning up expired request: {request_id}")
                    self.pending_requests.pop(request_id, None)
                    future = self.request_futures.pop(request_id, None)
                    if future and not future.done():
                        future.cancel()
                
                await asyncio.sleep(self.config.communication.file_cleanup_interval)
                
            except Exception as e:
                self.logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(30)  # Longer pause on error
    
    def _update_connection_metrics(self):
        """Update connection-related metrics."""
        active_connections = 0
        
        if self.websocket_server:
            active_connections += len(self.websocket_server.get_active_connections())
        
        if self.pipe_server:
            active_connections += len(self.pipe_server.get_active_connections())
        
        self.metrics['active_connections'] = active_connections
    
    def _update_avg_processing_time(self, execution_time: float):
        """Update average processing time metric."""
        current_avg = self.metrics['avg_processing_time']
        total_requests = self.metrics['requests_processed']
        
        if total_requests == 1:
            self.metrics['avg_processing_time'] = execution_time
        else:
            # Running average
            self.metrics['avg_processing_time'] = (
                (current_avg * (total_requests - 1) + execution_time) / total_requests
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bridge status."""
        return {
            'running': self.is_running,
            'metrics': self.metrics.copy(),
            'registered_handlers': list(self.analysis_handlers.keys()),
            'pending_requests': len(self.pending_requests),
            'config': {
                'debug_mode': self.config.debug_mode,
                'log_level': self.config.log_level,
                'websocket_port': self.config.communication.websocket_port
            }
        }