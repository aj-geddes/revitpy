"""
Lifecycle management for extensions.
"""

from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from loguru import logger


class LifecycleStage(Enum):
    """Extension lifecycle stages."""
    
    DISCOVERY = "discovery"
    REGISTRATION = "registration"
    LOADING = "loading"
    INITIALIZATION = "initialization"
    ACTIVATION = "activation"
    RUNTIME = "runtime"
    DEACTIVATION = "deactivation"
    DISPOSAL = "disposal"


@dataclass
class LifecycleEvent:
    """Lifecycle event data."""
    
    stage: LifecycleStage
    extension_name: str
    extension_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[Exception] = None


class LifecycleManager:
    """Manages extension lifecycle events and hooks."""
    
    def __init__(self) -> None:
        self._hooks: Dict[LifecycleStage, List[Callable]] = {
            stage: [] for stage in LifecycleStage
        }
        self._events: List[LifecycleEvent] = []
        self._max_events = 1000  # Limit event history
    
    def add_hook(
        self, 
        stage: LifecycleStage, 
        hook: Callable[[LifecycleEvent], Any]
    ) -> None:
        """
        Add a lifecycle hook.
        
        Args:
            stage: Lifecycle stage to hook into
            hook: Hook function to call
        """
        self._hooks[stage].append(hook)
        logger.debug(f"Added lifecycle hook for stage: {stage.value}")
    
    def remove_hook(
        self, 
        stage: LifecycleStage, 
        hook: Callable[[LifecycleEvent], Any]
    ) -> None:
        """
        Remove a lifecycle hook.
        
        Args:
            stage: Lifecycle stage
            hook: Hook function to remove
        """
        if hook in self._hooks[stage]:
            self._hooks[stage].remove(hook)
            logger.debug(f"Removed lifecycle hook for stage: {stage.value}")
    
    async def trigger_stage(
        self,
        stage: LifecycleStage,
        extension_name: str,
        extension_id: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Trigger a lifecycle stage.
        
        Args:
            stage: Lifecycle stage
            extension_name: Extension name
            extension_id: Extension ID
            data: Optional stage data
            error: Optional error if stage failed
        """
        event = LifecycleEvent(
            stage=stage,
            extension_name=extension_name,
            extension_id=extension_id,
            data=data or {},
            success=error is None,
            error=error
        )
        
        # Store event
        self._events.append(event)
        
        # Limit event history
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        
        # Execute hooks
        for hook in self._hooks[stage]:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(event)
                else:
                    hook(event)
            except Exception as hook_error:
                logger.error(f"Lifecycle hook failed for stage {stage.value}: {hook_error}")
    
    def get_events(
        self,
        extension_name: Optional[str] = None,
        stage: Optional[LifecycleStage] = None,
        limit: Optional[int] = None
    ) -> List[LifecycleEvent]:
        """
        Get lifecycle events.
        
        Args:
            extension_name: Filter by extension name
            stage: Filter by lifecycle stage
            limit: Limit number of events returned
            
        Returns:
            List of lifecycle events
        """
        events = self._events
        
        # Apply filters
        if extension_name:
            events = [e for e in events if e.extension_name == extension_name]
        
        if stage:
            events = [e for e in events if e.stage == stage]
        
        # Apply limit
        if limit:
            events = events[-limit:]
        
        return events
    
    def get_extension_lifecycle(self, extension_name: str) -> List[LifecycleEvent]:
        """Get complete lifecycle for an extension."""
        return self.get_events(extension_name=extension_name)
    
    def clear_events(self) -> None:
        """Clear all lifecycle events."""
        self._events.clear()
        logger.debug("Cleared lifecycle events")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get lifecycle statistics."""
        stage_counts = {stage.value: 0 for stage in LifecycleStage}
        success_counts = {stage.value: 0 for stage in LifecycleStage}
        
        for event in self._events:
            stage_counts[event.stage.value] += 1
            if event.success:
                success_counts[event.stage.value] += 1
        
        return {
            'total_events': len(self._events),
            'stage_counts': stage_counts,
            'success_counts': success_counts,
            'failure_counts': {
                stage.value: stage_counts[stage.value] - success_counts[stage.value]
                for stage in LifecycleStage
            },
        }