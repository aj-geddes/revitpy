"""
Relationship management system for RevitPy ORM.

This module provides comprehensive relationship mapping between Revit elements,
supporting one-to-one, one-to-many, and many-to-many relationships with
lazy loading, eager loading, and intelligent caching.
"""

from __future__ import annotations

import asyncio
import weakref
from abc import ABC, abstractmethod
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Generic, Union,
    Callable, Awaitable, cast, ForwardRef
)
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from .types import (
    RelationshipType, LoadStrategy, IElementProvider, IRelationshipLoader,
    ElementId, CacheKey
)
from .exceptions import RelationshipError, LazyLoadingError
from .cache import CacheManager


T = TypeVar('T')  # Source entity type
R = TypeVar('R')  # Related entity type
K = TypeVar('K')  # Key type


class CascadeAction(Enum):
    """Actions for cascade operations."""
    
    NONE = "none"
    DELETE = "delete"
    DELETE_ORPHAN = "delete_orphan"
    MERGE = "merge"
    PERSIST = "persist"
    REFRESH = "refresh"
    DETACH = "detach"


@dataclass
class RelationshipConfiguration:
    """Configuration for a relationship."""
    
    name: str
    relationship_type: RelationshipType
    target_entity: Type
    foreign_key: Optional[str] = None
    inverse_property: Optional[str] = None
    load_strategy: LoadStrategy = LoadStrategy.LAZY
    cascade: Set[CascadeAction] = field(default_factory=set)
    cache_enabled: bool = True
    batch_size: int = 100
    
    def __post_init__(self) -> None:
        if self.relationship_type in (RelationshipType.ONE_TO_MANY, RelationshipType.MANY_TO_MANY):
            if self.load_strategy == LoadStrategy.EAGER and self.batch_size < 1:
                raise ValueError("Batch size must be positive for eager loading")


class Relationship(Generic[T, R], ABC):
    """Base class for all relationship types."""
    
    def __init__(
        self,
        config: RelationshipConfiguration,
        loader: IRelationshipLoader,
        cache_manager: Optional[CacheManager] = None
    ) -> None:
        self._config = config
        self._loader = loader
        self._cache_manager = cache_manager or CacheManager()
        self._loaded_entities: Dict[Any, Any] = {}  # Entity ID -> loaded data
        self._loading_promises: Dict[Any, asyncio.Future] = {}  # Pending async loads
    
    @property
    def name(self) -> str:
        """Get relationship name."""
        return self._config.name
    
    @property
    def relationship_type(self) -> RelationshipType:
        """Get relationship type."""
        return self._config.relationship_type
    
    @property
    def target_entity(self) -> Type:
        """Get target entity type."""
        return self._config.target_entity
    
    @abstractmethod
    def load(self, entity: T, force_reload: bool = False) -> Union[R, List[R], None]:
        """Load related data for an entity."""
        pass
    
    @abstractmethod
    async def load_async(self, entity: T, force_reload: bool = False) -> Union[R, List[R], None]:
        """Load related data asynchronously."""
        pass
    
    def get_cache_key(self, entity: T) -> CacheKey:
        """Get cache key for relationship data."""
        entity_id = self._get_entity_id(entity)
        return CacheKey(
            entity_type=self._config.target_entity.__name__,
            entity_id=entity_id,
            relationship_path=self._config.name
        )
    
    def _get_entity_id(self, entity: T) -> Any:
        """Get entity ID for caching."""
        if hasattr(entity, 'id'):
            return entity.id
        elif hasattr(entity, 'Id'):
            return entity.Id
        else:
            return id(entity)
    
    def _should_use_cache(self, entity: T) -> bool:
        """Check if caching should be used for this entity."""
        return (
            self._config.cache_enabled and
            self._cache_manager is not None and
            self._get_entity_id(entity) is not None
        )
    
    def invalidate_cache(self, entity: T) -> None:
        """Invalidate cached data for entity."""
        if self._should_use_cache(entity):
            cache_key = self.get_cache_key(entity)
            self._cache_manager.invalidate(cache_key)
        
        entity_id = self._get_entity_id(entity)
        if entity_id in self._loaded_entities:
            del self._loaded_entities[entity_id]


class OneToOneRelationship(Relationship[T, R]):
    """One-to-one relationship implementation."""
    
    def __init__(
        self,
        config: RelationshipConfiguration,
        loader: IRelationshipLoader,
        cache_manager: Optional[CacheManager] = None
    ) -> None:
        super().__init__(config, loader, cache_manager)
        if config.relationship_type != RelationshipType.ONE_TO_ONE:
            raise ValueError("Configuration must be for one-to-one relationship")
    
    def load(self, entity: T, force_reload: bool = False) -> Optional[R]:
        """Load the single related entity."""
        entity_id = self._get_entity_id(entity)
        
        # Check memory cache first
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        # Check persistent cache
        if not force_reload and self._should_use_cache(entity):
            cache_key = self.get_cache_key(entity)
            cached_result = self._cache_manager.get(cache_key)
            if cached_result is not None:
                self._loaded_entities[entity_id] = cached_result
                return cached_result
        
        try:
            # Load from data source
            related = self._loader.load_relationship(
                entity, self._config.name, self._config.load_strategy
            )
            
            # Cache the result
            self._loaded_entities[entity_id] = related
            if self._should_use_cache(entity):
                cache_key = self.get_cache_key(entity)
                self._cache_manager.set(cache_key, related)
            
            return related
            
        except Exception as e:
            logger.error(f"Failed to load one-to-one relationship {self._config.name}: {e}")
            raise RelationshipError(
                f"Failed to load relationship {self._config.name}",
                relationship_name=self._config.name,
                source_entity=entity,
                cause=e
            )
    
    async def load_async(self, entity: T, force_reload: bool = False) -> Optional[R]:
        """Load the single related entity asynchronously."""
        entity_id = self._get_entity_id(entity)
        
        # Check if already loading
        if entity_id in self._loading_promises:
            return await self._loading_promises[entity_id]
        
        # Check memory cache first
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        # Create loading promise
        async def _load():
            try:
                # Check persistent cache
                if not force_reload and self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    cached_result = self._cache_manager.get(cache_key)
                    if cached_result is not None:
                        self._loaded_entities[entity_id] = cached_result
                        return cached_result
                
                # Load from data source
                related = await self._loader.load_relationship_async(
                    entity, self._config.name, self._config.load_strategy
                )
                
                # Cache the result
                self._loaded_entities[entity_id] = related
                if self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    self._cache_manager.set(cache_key, related)
                
                return related
                
            except Exception as e:
                logger.error(f"Failed to load one-to-one relationship {self._config.name} async: {e}")
                raise RelationshipError(
                    f"Failed to load relationship {self._config.name} asynchronously",
                    relationship_name=self._config.name,
                    source_entity=entity,
                    cause=e
                )
            finally:
                # Clean up loading promise
                if entity_id in self._loading_promises:
                    del self._loading_promises[entity_id]
        
        # Store and return promise
        promise = asyncio.create_task(_load())
        self._loading_promises[entity_id] = promise
        return await promise


class OneToManyRelationship(Relationship[T, List[R]]):
    """One-to-many relationship implementation."""
    
    def __init__(
        self,
        config: RelationshipConfiguration,
        loader: IRelationshipLoader,
        cache_manager: Optional[CacheManager] = None
    ) -> None:
        super().__init__(config, loader, cache_manager)
        if config.relationship_type != RelationshipType.ONE_TO_MANY:
            raise ValueError("Configuration must be for one-to-many relationship")
    
    def load(self, entity: T, force_reload: bool = False) -> List[R]:
        """Load the collection of related entities."""
        entity_id = self._get_entity_id(entity)
        
        # Check memory cache first
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        # Check persistent cache
        if not force_reload and self._should_use_cache(entity):
            cache_key = self.get_cache_key(entity)
            cached_result = self._cache_manager.get(cache_key)
            if cached_result is not None:
                self._loaded_entities[entity_id] = cached_result
                return cached_result
        
        try:
            # Load from data source
            related_collection = self._loader.load_relationship(
                entity, self._config.name, self._config.load_strategy
            )
            
            if not isinstance(related_collection, list):
                related_collection = [related_collection] if related_collection else []
            
            # Cache the result
            self._loaded_entities[entity_id] = related_collection
            if self._should_use_cache(entity):
                cache_key = self.get_cache_key(entity)
                self._cache_manager.set(cache_key, related_collection)
            
            return related_collection
            
        except Exception as e:
            logger.error(f"Failed to load one-to-many relationship {self._config.name}: {e}")
            raise RelationshipError(
                f"Failed to load relationship {self._config.name}",
                relationship_name=self._config.name,
                source_entity=entity,
                cause=e
            )
    
    async def load_async(self, entity: T, force_reload: bool = False) -> List[R]:
        """Load the collection of related entities asynchronously."""
        entity_id = self._get_entity_id(entity)
        
        # Check if already loading
        if entity_id in self._loading_promises:
            return await self._loading_promises[entity_id]
        
        # Check memory cache first
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        # Create loading promise
        async def _load():
            try:
                # Check persistent cache
                if not force_reload and self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    cached_result = self._cache_manager.get(cache_key)
                    if cached_result is not None:
                        self._loaded_entities[entity_id] = cached_result
                        return cached_result
                
                # Load from data source
                related_collection = await self._loader.load_relationship_async(
                    entity, self._config.name, self._config.load_strategy
                )
                
                if not isinstance(related_collection, list):
                    related_collection = [related_collection] if related_collection else []
                
                # Cache the result
                self._loaded_entities[entity_id] = related_collection
                if self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    self._cache_manager.set(cache_key, related_collection)
                
                return related_collection
                
            except Exception as e:
                logger.error(f"Failed to load one-to-many relationship {self._config.name} async: {e}")
                raise RelationshipError(
                    f"Failed to load relationship {self._config.name} asynchronously",
                    relationship_name=self._config.name,
                    source_entity=entity,
                    cause=e
                )
            finally:
                # Clean up loading promise
                if entity_id in self._loading_promises:
                    del self._loading_promises[entity_id]
        
        # Store and return promise
        promise = asyncio.create_task(_load())
        self._loading_promises[entity_id] = promise
        return await promise
    
    def add(self, entity: T, related: R) -> None:
        """Add a related entity to the collection."""
        entity_id = self._get_entity_id(entity)
        
        # Load existing collection if not loaded
        if entity_id not in self._loaded_entities:
            self.load(entity)
        
        collection = self._loaded_entities[entity_id]
        if related not in collection:
            collection.append(related)
            
            # Invalidate cache since collection changed
            if self._should_use_cache(entity):
                cache_key = self.get_cache_key(entity)
                self._cache_manager.invalidate(cache_key)
    
    def remove(self, entity: T, related: R) -> bool:
        """Remove a related entity from the collection."""
        entity_id = self._get_entity_id(entity)
        
        # Load existing collection if not loaded
        if entity_id not in self._loaded_entities:
            self.load(entity)
        
        collection = self._loaded_entities[entity_id]
        if related in collection:
            collection.remove(related)
            
            # Invalidate cache since collection changed
            if self._should_use_cache(entity):
                cache_key = self.get_cache_key(entity)
                self._cache_manager.invalidate(cache_key)
            
            return True
        
        return False


class ManyToManyRelationship(Relationship[T, List[R]]):
    """Many-to-many relationship implementation."""
    
    def __init__(
        self,
        config: RelationshipConfiguration,
        loader: IRelationshipLoader,
        cache_manager: Optional[CacheManager] = None,
        junction_table: Optional[str] = None
    ) -> None:
        super().__init__(config, loader, cache_manager)
        if config.relationship_type != RelationshipType.MANY_TO_MANY:
            raise ValueError("Configuration must be for many-to-many relationship")
        
        self._junction_table = junction_table or f"{config.name}_junction"
    
    @property
    def junction_table(self) -> str:
        """Get the junction table name."""
        return self._junction_table
    
    def load(self, entity: T, force_reload: bool = False) -> List[R]:
        """Load the collection of related entities."""
        # Implementation similar to OneToManyRelationship
        # but with junction table awareness
        entity_id = self._get_entity_id(entity)
        
        # Check memory cache first
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        # Check persistent cache
        if not force_reload and self._should_use_cache(entity):
            cache_key = self.get_cache_key(entity)
            cached_result = self._cache_manager.get(cache_key)
            if cached_result is not None:
                self._loaded_entities[entity_id] = cached_result
                return cached_result
        
        try:
            # Load from data source (through junction table)
            related_collection = self._loader.load_relationship(
                entity, self._config.name, self._config.load_strategy
            )
            
            if not isinstance(related_collection, list):
                related_collection = [related_collection] if related_collection else []
            
            # Cache the result
            self._loaded_entities[entity_id] = related_collection
            if self._should_use_cache(entity):
                cache_key = self.get_cache_key(entity)
                self._cache_manager.set(cache_key, related_collection)
            
            return related_collection
            
        except Exception as e:
            logger.error(f"Failed to load many-to-many relationship {self._config.name}: {e}")
            raise RelationshipError(
                f"Failed to load relationship {self._config.name}",
                relationship_name=self._config.name,
                source_entity=entity,
                cause=e
            )
    
    async def load_async(self, entity: T, force_reload: bool = False) -> List[R]:
        """Load the collection of related entities asynchronously."""
        # Similar to OneToManyRelationship but async
        entity_id = self._get_entity_id(entity)
        
        if entity_id in self._loading_promises:
            return await self._loading_promises[entity_id]
        
        if not force_reload and entity_id in self._loaded_entities:
            return self._loaded_entities[entity_id]
        
        async def _load():
            try:
                if not force_reload and self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    cached_result = self._cache_manager.get(cache_key)
                    if cached_result is not None:
                        self._loaded_entities[entity_id] = cached_result
                        return cached_result
                
                related_collection = await self._loader.load_relationship_async(
                    entity, self._config.name, self._config.load_strategy
                )
                
                if not isinstance(related_collection, list):
                    related_collection = [related_collection] if related_collection else []
                
                self._loaded_entities[entity_id] = related_collection
                if self._should_use_cache(entity):
                    cache_key = self.get_cache_key(entity)
                    self._cache_manager.set(cache_key, related_collection)
                
                return related_collection
                
            except Exception as e:
                logger.error(f"Failed to load many-to-many relationship {self._config.name} async: {e}")
                raise RelationshipError(
                    f"Failed to load relationship {self._config.name} asynchronously",
                    relationship_name=self._config.name,
                    source_entity=entity,
                    cause=e
                )
            finally:
                if entity_id in self._loading_promises:
                    del self._loading_promises[entity_id]
        
        promise = asyncio.create_task(_load())
        self._loading_promises[entity_id] = promise
        return await promise


class RelationshipManager:
    """
    Central manager for all relationship operations.
    
    Provides registration, loading, and caching of relationships
    between Revit elements with full lifecycle management.
    """
    
    def __init__(
        self,
        loader: IRelationshipLoader,
        cache_manager: Optional[CacheManager] = None
    ) -> None:
        self._loader = loader
        self._cache_manager = cache_manager or CacheManager()
        self._relationships: Dict[Type, Dict[str, Relationship]] = {}
        self._inverse_relationships: Dict[Type, Dict[str, str]] = {}
    
    def register_one_to_one(
        self,
        source_type: Type[T],
        relationship_name: str,
        target_type: Type[R],
        *,
        foreign_key: Optional[str] = None,
        inverse_property: Optional[str] = None,
        load_strategy: LoadStrategy = LoadStrategy.LAZY,
        cache_enabled: bool = True
    ) -> None:
        """Register a one-to-one relationship."""
        config = RelationshipConfiguration(
            name=relationship_name,
            relationship_type=RelationshipType.ONE_TO_ONE,
            target_entity=target_type,
            foreign_key=foreign_key,
            inverse_property=inverse_property,
            load_strategy=load_strategy,
            cache_enabled=cache_enabled
        )
        
        relationship = OneToOneRelationship(config, self._loader, self._cache_manager)
        self._register_relationship(source_type, relationship)
        
        # Register inverse if specified
        if inverse_property:
            self._register_inverse(source_type, target_type, relationship_name, inverse_property)
    
    def register_one_to_many(
        self,
        source_type: Type[T],
        relationship_name: str,
        target_type: Type[R],
        *,
        foreign_key: Optional[str] = None,
        inverse_property: Optional[str] = None,
        load_strategy: LoadStrategy = LoadStrategy.LAZY,
        cascade: Optional[Set[CascadeAction]] = None,
        cache_enabled: bool = True,
        batch_size: int = 100
    ) -> None:
        """Register a one-to-many relationship."""
        config = RelationshipConfiguration(
            name=relationship_name,
            relationship_type=RelationshipType.ONE_TO_MANY,
            target_entity=target_type,
            foreign_key=foreign_key,
            inverse_property=inverse_property,
            load_strategy=load_strategy,
            cascade=cascade or set(),
            cache_enabled=cache_enabled,
            batch_size=batch_size
        )
        
        relationship = OneToManyRelationship(config, self._loader, self._cache_manager)
        self._register_relationship(source_type, relationship)
        
        # Register inverse if specified
        if inverse_property:
            self._register_inverse(source_type, target_type, relationship_name, inverse_property)
    
    def register_many_to_many(
        self,
        source_type: Type[T],
        relationship_name: str,
        target_type: Type[R],
        *,
        junction_table: Optional[str] = None,
        inverse_property: Optional[str] = None,
        load_strategy: LoadStrategy = LoadStrategy.LAZY,
        cascade: Optional[Set[CascadeAction]] = None,
        cache_enabled: bool = True,
        batch_size: int = 100
    ) -> None:
        """Register a many-to-many relationship."""
        config = RelationshipConfiguration(
            name=relationship_name,
            relationship_type=RelationshipType.MANY_TO_MANY,
            target_entity=target_type,
            inverse_property=inverse_property,
            load_strategy=load_strategy,
            cascade=cascade or set(),
            cache_enabled=cache_enabled,
            batch_size=batch_size
        )
        
        relationship = ManyToManyRelationship(
            config, self._loader, self._cache_manager, junction_table
        )
        self._register_relationship(source_type, relationship)
        
        # Register inverse if specified
        if inverse_property:
            self._register_inverse(source_type, target_type, relationship_name, inverse_property)
    
    def get_relationship(self, entity_type: Type, relationship_name: str) -> Optional[Relationship]:
        """Get a registered relationship."""
        return self._relationships.get(entity_type, {}).get(relationship_name)
    
    def load_relationship(
        self,
        entity: T,
        relationship_name: str,
        force_reload: bool = False
    ) -> Union[Any, List[Any], None]:
        """Load a relationship for an entity."""
        entity_type = type(entity)
        relationship = self.get_relationship(entity_type, relationship_name)
        
        if relationship is None:
            raise RelationshipError(
                f"Relationship '{relationship_name}' not found for type {entity_type.__name__}",
                relationship_name=relationship_name,
                source_entity=entity
            )
        
        return relationship.load(entity, force_reload)
    
    async def load_relationship_async(
        self,
        entity: T,
        relationship_name: str,
        force_reload: bool = False
    ) -> Union[Any, List[Any], None]:
        """Load a relationship for an entity asynchronously."""
        entity_type = type(entity)
        relationship = self.get_relationship(entity_type, relationship_name)
        
        if relationship is None:
            raise RelationshipError(
                f"Relationship '{relationship_name}' not found for type {entity_type.__name__}",
                relationship_name=relationship_name,
                source_entity=entity
            )
        
        return await relationship.load_async(entity, force_reload)
    
    def invalidate_relationship(self, entity: T, relationship_name: str) -> None:
        """Invalidate cached relationship data."""
        entity_type = type(entity)
        relationship = self.get_relationship(entity_type, relationship_name)
        
        if relationship:
            relationship.invalidate_cache(entity)
    
    def invalidate_entity(self, entity: T) -> None:
        """Invalidate all cached relationship data for an entity."""
        entity_type = type(entity)
        relationships = self._relationships.get(entity_type, {})
        
        for relationship in relationships.values():
            relationship.invalidate_cache(entity)
    
    def get_registered_relationships(self, entity_type: Type) -> Dict[str, Relationship]:
        """Get all registered relationships for an entity type."""
        return self._relationships.get(entity_type, {}).copy()
    
    def _register_relationship(self, source_type: Type, relationship: Relationship) -> None:
        """Register a relationship for a source type."""
        if source_type not in self._relationships:
            self._relationships[source_type] = {}
        
        self._relationships[source_type][relationship.name] = relationship
        
        logger.debug(
            f"Registered {relationship.relationship_type.value} relationship "
            f"'{relationship.name}' for {source_type.__name__} -> {relationship.target_entity.__name__}"
        )
    
    def _register_inverse(
        self,
        source_type: Type,
        target_type: Type,
        relationship_name: str,
        inverse_property: str
    ) -> None:
        """Register inverse relationship mapping."""
        if target_type not in self._inverse_relationships:
            self._inverse_relationships[target_type] = {}
        
        self._inverse_relationships[target_type][inverse_property] = relationship_name
        
        logger.debug(
            f"Registered inverse relationship: {target_type.__name__}.{inverse_property} "
            f"<-> {source_type.__name__}.{relationship_name}"
        )