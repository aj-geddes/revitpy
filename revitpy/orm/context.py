"""
RevitContext - Main ORM context for RevitPy.

This module provides the main context class that orchestrates all ORM
functionality including querying, change tracking, caching, and relationships.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Any,
    TypeVar,
)

from loguru import logger

from .async_support import AsyncRevitContext
from .cache import CacheConfiguration, CacheManager
from .change_tracker import ChangeTracker
from .element_set import ElementSet
from .exceptions import ORMException, RelationshipError
from .query_builder import QueryBuilder
from .relationships import RelationshipManager
from .types import (
    CachePolicy,
    ElementId,
    ElementState,
    IElementProvider,
    IUnitOfWork,
    LoadStrategy,
)

T = TypeVar("T")
E = TypeVar("E", bound="Element")


@dataclass
class ContextConfiguration:
    """Configuration for RevitContext."""

    auto_track_changes: bool = True
    cache_policy: CachePolicy = CachePolicy.MEMORY
    cache_max_size: int = 10000
    cache_max_memory_mb: int = 500
    lazy_loading_enabled: bool = True
    batch_size: int = 100
    thread_safe: bool = True
    validation_enabled: bool = True
    performance_monitoring: bool = True


class RevitContext:
    """
    Main ORM context for RevitPy operations.

    Provides a high-level interface for all ORM functionality including:
    - LINQ-style querying with lazy evaluation
    - Automatic change tracking and batch updates
    - Intelligent caching with invalidation
    - Relationship navigation and loading
    - Transaction management
    - Performance monitoring and optimization
    """

    def __init__(
        self,
        provider: IElementProvider,
        *,
        config: ContextConfiguration | None = None,
        cache_manager: CacheManager | None = None,
        change_tracker: ChangeTracker | None = None,
        relationship_manager: RelationshipManager | None = None,
        unit_of_work: IUnitOfWork | None = None,
    ) -> None:
        self._config = config or ContextConfiguration()
        self._provider = provider

        # Initialize components
        if cache_manager is None:
            cache_config = CacheConfiguration(
                max_size=self._config.cache_max_size,
                max_memory_mb=self._config.cache_max_memory_mb,
                enable_statistics=self._config.performance_monitoring,
                thread_safe=self._config.thread_safe,
            )
            cache_manager = CacheManager(cache_config)

        self._cache_manager = cache_manager
        self._change_tracker = change_tracker or ChangeTracker(self._config.thread_safe)
        self._relationship_manager = relationship_manager
        self._unit_of_work = unit_of_work

        # Configure change tracking
        self._change_tracker.auto_track = self._config.auto_track_changes

        # State management
        self._is_disposed = False
        self._lock = threading.RLock() if self._config.thread_safe else None

        # Entity collections (for common Revit element types)
        self._entity_sets: dict[type, Any] = {}

        logger.debug("RevitContext initialized")

    @property
    def is_disposed(self) -> bool:
        """Check if context has been disposed."""
        return self._is_disposed

    @property
    def has_changes(self) -> bool:
        """Check if there are pending changes."""
        return self._change_tracker.has_changes

    @property
    def change_count(self) -> int:
        """Get number of pending changes."""
        return self._change_tracker.change_count

    @property
    def cache_statistics(self) -> Any | None:
        """Get cache statistics."""
        return self._cache_manager.statistics

    # Query interface

    def query(self, element_type: type[T] | None = None) -> QueryBuilder[T]:
        """Create a new query builder."""
        self._ensure_not_disposed()

        return QueryBuilder(
            self._provider,
            element_type,
            self._cache_manager,
            query_mode=self._config.cache_policy,
        )

    def all(self, element_type: type[T]) -> ElementSet[T]:
        """Get all elements of the specified type."""
        self._ensure_not_disposed()

        with self._lock if self._lock else self._no_op():
            # Check if we have a cached entity set
            if element_type in self._entity_sets:
                return self._entity_sets[element_type]

            # Create new query-backed entity set
            query_builder = self.query(element_type)
            entity_set = ElementSet.from_query(query_builder)

            # Cache the entity set
            self._entity_sets[element_type] = entity_set

            return entity_set

    def where(
        self, element_type: type[T], predicate: Callable[[T], bool]
    ) -> ElementSet[T]:
        """Query elements with a predicate."""
        return self.all(element_type).where(predicate)

    def first(
        self, element_type: type[T], predicate: Callable[[T], bool] | None = None
    ) -> T:
        """Get the first element of the specified type."""
        query = self.all(element_type)
        return query.first(predicate) if predicate else query.first()

    def first_or_default(
        self,
        element_type: type[T],
        predicate: Callable[[T], bool] | None = None,
        default: T | None = None,
    ) -> T | None:
        """Get the first element or default value."""
        query = self.all(element_type)
        return query.first_or_default(predicate, default)

    def single(
        self, element_type: type[T], predicate: Callable[[T], bool] | None = None
    ) -> T:
        """Get the single element of the specified type."""
        query = self.all(element_type)
        return query.single(predicate) if predicate else query.single()

    def count(
        self, element_type: type[T], predicate: Callable[[T], bool] | None = None
    ) -> int:
        """Get count of elements."""
        query = self.all(element_type)
        return query.count(predicate) if predicate else query.count()

    def any(
        self, element_type: type[T], predicate: Callable[[T], bool] | None = None
    ) -> bool:
        """Check if any elements match the predicate."""
        query = self.all(element_type)
        return query.any(predicate) if predicate else query.any()

    def get_by_id(self, element_type: type[T], element_id: ElementId) -> T | None:
        """Get element by ID."""
        self._ensure_not_disposed()

        # Try cache first
        if self._config.cache_policy != CachePolicy.NONE:
            from .cache import create_entity_cache_key

            cache_key = create_entity_cache_key(element_type.__name__, element_id)
            cached_element = self._cache_manager.get(cache_key)

            if cached_element is not None:
                # Ensure it's tracked
                if self._config.auto_track_changes:
                    self._change_tracker.attach(cached_element, element_id)
                return cached_element

        # Query from provider
        try:
            element = self._provider.get_element_by_id(element_id)

            if element and self._config.auto_track_changes:
                self._change_tracker.attach(element, element_id)

                # Cache the element
                if self._config.cache_policy != CachePolicy.NONE:
                    from .cache import create_entity_cache_key

                    cache_key = create_entity_cache_key(
                        element_type.__name__, element_id
                    )
                    self._cache_manager.set(cache_key, element)

            return element

        except Exception as e:
            logger.error(f"Failed to get element by ID {element_id}: {e}")
            raise ORMException(
                f"Failed to get element by ID {element_id}",
                operation="get_by_id",
                entity_type=element_type.__name__,
                entity_id=element_id,
                cause=e,
            )

    # Change tracking and persistence

    def attach(self, entity: T, entity_id: ElementId | None = None) -> None:
        """Attach an entity to the context for change tracking."""
        self._ensure_not_disposed()

        if entity_id is None:
            entity_id = self._get_entity_id(entity)

        self._change_tracker.attach(entity, entity_id)
        logger.debug(f"Attached entity {entity_id} to context")

    def detach(self, entity: T) -> None:
        """Detach an entity from change tracking."""
        self._ensure_not_disposed()

        entity_id = self._get_entity_id(entity)
        self._change_tracker.detach(entity_id)
        logger.debug(f"Detached entity {entity_id} from context")

    def add(self, entity: T) -> None:
        """Mark entity as added (for new entities)."""
        self._ensure_not_disposed()

        self._change_tracker.mark_as_added(entity)
        logger.debug(f"Marked entity as added: {self._get_entity_id(entity)}")

    def remove(self, entity: T) -> None:
        """Mark entity as deleted."""
        self._ensure_not_disposed()

        self._change_tracker.mark_as_deleted(entity)
        logger.debug(f"Marked entity as deleted: {self._get_entity_id(entity)}")

    def get_entity_state(self, entity: T) -> ElementState:
        """Get the current state of an entity."""
        entity_id = self._get_entity_id(entity)
        return self._change_tracker.get_entity_state(entity_id)

    def accept_changes(self, entity: T | None = None) -> None:
        """Accept changes for specific entity or all entities."""
        self._ensure_not_disposed()

        if entity is not None:
            entity_id = self._get_entity_id(entity)
            self._change_tracker.accept_changes(entity_id)
        else:
            self._change_tracker.accept_changes()

        logger.debug("Accepted changes")

    def reject_changes(self, entity: T | None = None) -> None:
        """Reject changes for specific entity or all entities."""
        self._ensure_not_disposed()

        if entity is not None:
            entity_id = self._get_entity_id(entity)
            self._change_tracker.reject_changes(entity_id)
        else:
            self._change_tracker.reject_changes()

        logger.debug("Rejected changes")

    def save_changes(self) -> int:
        """Save all pending changes to the data store."""
        self._ensure_not_disposed()

        if not self.has_changes:
            return 0

        try:
            # Get all changes
            changes = self._change_tracker.get_all_changes()

            # Process changes through unit of work
            if self._unit_of_work:
                for change in changes:
                    if change.state == ElementState.ADDED:
                        self._unit_of_work.register_new(change)
                    elif change.state == ElementState.MODIFIED:
                        self._unit_of_work.register_dirty(change)
                    elif change.state == ElementState.DELETED:
                        self._unit_of_work.register_removed(change)

                # Commit changes
                self._unit_of_work.commit()

            # Accept changes in tracker
            self._change_tracker.accept_changes()

            # Invalidate relevant cache entries
            self._invalidate_cache_for_changes(changes)

            logger.info(f"Saved {len(changes)} changes")
            return len(changes)

        except Exception as e:
            logger.error(f"Failed to save changes: {e}")
            # Attempt rollback if unit of work supports it
            if self._unit_of_work and hasattr(self._unit_of_work, "rollback"):
                try:
                    self._unit_of_work.rollback()
                except Exception as rollback_error:
                    logger.error(f"Rollback also failed: {rollback_error}")

            raise ORMException(
                f"Failed to save changes: {e}", operation="save_changes", cause=e
            )

    # Relationship management

    def load_relationship(
        self,
        entity: T,
        relationship_name: str,
        strategy: LoadStrategy = LoadStrategy.LAZY,
    ) -> Any | list[Any] | None:
        """Load relationship data for an entity."""
        self._ensure_not_disposed()

        if not self._relationship_manager:
            raise RelationshipError(
                "No relationship manager configured",
                relationship_name=relationship_name,
                source_entity=entity,
            )

        return self._relationship_manager.load_relationship(entity, relationship_name)

    def configure_relationship(
        self, source_type: type[T], relationship_name: str, target_type: type, **kwargs
    ) -> None:
        """Configure a relationship between entity types."""
        if not self._relationship_manager:
            from .relationships import RelationshipManager

            self._relationship_manager = RelationshipManager(
                self._provider, self._cache_manager
            )

        # This would delegate to appropriate registration method based on relationship type
        # Implementation depends on specific relationship configuration
        logger.debug(
            f"Configured relationship {source_type.__name__}.{relationship_name}"
        )

    # Transaction support

    @contextmanager
    def transaction(self, auto_commit: bool = True):
        """Create a transaction context manager."""
        self._ensure_not_disposed()

        # Simple transaction implementation
        # In a full implementation, this would integrate with Revit's transaction system
        original_auto_track = self._change_tracker.auto_track

        try:
            logger.debug("Transaction started")
            yield self

            if auto_commit and self.has_changes:
                self.save_changes()
                logger.debug("Transaction committed")

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            self.reject_changes()
            logger.debug("Transaction rolled back")
            raise

        finally:
            self._change_tracker.auto_track = original_auto_track

    # Async interface

    def as_async(self) -> AsyncRevitContext:
        """Get async version of this context."""
        return AsyncRevitContext(
            self._provider,
            cache_manager=self._cache_manager,
            change_tracker=self._change_tracker,
            relationship_manager=self._relationship_manager,
            unit_of_work=self._unit_of_work,
            auto_track_changes=self._config.auto_track_changes,
            default_cache_policy=self._config.cache_policy,
        )

    # Cache management

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._ensure_not_disposed()

        self._cache_manager.clear()
        self._entity_sets.clear()
        logger.debug("Cache cleared")

    def invalidate_cache(
        self, entity_type: type | None = None, entity_id: ElementId | None = None
    ) -> None:
        """Invalidate cache entries."""
        self._ensure_not_disposed()

        if entity_type and entity_id:
            # Invalidate specific entity
            from .cache import create_entity_cache_key

            cache_key = create_entity_cache_key(entity_type.__name__, entity_id)
            self._cache_manager.invalidate(cache_key)
        elif entity_type:
            # Invalidate all entities of type
            pattern = entity_type.__name__
            self._cache_manager.invalidate_by_pattern(pattern)
        else:
            # Clear all cache
            self.clear_cache()

    # Context management

    def dispose(self) -> None:
        """Dispose of the context and clean up resources."""
        if self._is_disposed:
            return

        try:
            # Reject any pending changes
            if self.has_changes:
                self.reject_changes()

            # Clear change tracker
            self._change_tracker.clear()

            # Clear cache
            self._cache_manager.clear()

            # Clear entity sets
            self._entity_sets.clear()

            self._is_disposed = True
            logger.debug("RevitContext disposed")

        except Exception as e:
            logger.error(f"Error during context disposal: {e}")

    def __enter__(self) -> RevitContext:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.dispose()

    # Internal methods

    def _ensure_not_disposed(self) -> None:
        """Ensure context is not disposed."""
        if self._is_disposed:
            raise ORMException(
                "RevitContext has been disposed", operation="context_check"
            )

    def _get_entity_id(self, entity: Any) -> ElementId:
        """Get entity ID from entity object."""
        if hasattr(entity, "id"):
            return entity.id
        elif hasattr(entity, "Id"):
            return entity.Id
        else:
            return id(entity)

    def _invalidate_cache_for_changes(self, changes: list[Any]) -> None:
        """Invalidate cache entries affected by changes."""
        for change in changes:
            # Invalidate entity cache
            from .cache import create_entity_cache_key

            cache_key = create_entity_cache_key(change.entity_type, change.entity_id)
            self._cache_manager.invalidate(cache_key)

            # Invalidate relationship cache if relationship manager exists
            if self._relationship_manager:
                self._relationship_manager.invalidate_entity(change)

    def _no_op(self):
        """No-op context manager for non-thread-safe mode."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Factory functions


def create_context(provider: IElementProvider, **kwargs) -> RevitContext:
    """Create a new RevitContext with default configuration."""
    return RevitContext(provider, **kwargs)


def create_async_context(provider: IElementProvider, **kwargs) -> AsyncRevitContext:
    """Create a new AsyncRevitContext with default configuration."""
    return AsyncRevitContext(provider, **kwargs)
