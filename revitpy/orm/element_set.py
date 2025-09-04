"""
Enhanced ElementSet with LINQ-style operations and relationship navigation.

This module provides collections for working with Revit elements in a Pythonic way,
supporting both synchronous and asynchronous operations with lazy evaluation.
"""

from __future__ import annotations

import asyncio
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Generic, Union,
    Callable, Awaitable, AsyncIterator, Iterator, Tuple, overload
)
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from loguru import logger

from .types import (
    IQueryable, IAsyncQueryable, QueryPredicate, QuerySelector, QueryKeySelector,
    ElementState, LoadStrategy
)
from .exceptions import QueryError, RelationshipError
from .query_builder import QueryBuilder


T = TypeVar('T')
R = TypeVar('R')
K = TypeVar('K')


class ElementSet(Generic[T], Sequence[T], IQueryable[T]):
    """
    Enhanced collection of Revit elements with LINQ-style operations.
    
    Provides a rich set of operations for querying, filtering, and manipulating
    collections of Revit elements with lazy evaluation and relationship support.
    """
    
    def __init__(
        self,
        elements: Optional[List[T]] = None,
        *,
        element_type: Optional[Type[T]] = None,
        lazy: bool = True,
        query_builder: Optional[QueryBuilder[T]] = None
    ) -> None:
        self._elements = elements or []
        self._element_type = element_type
        self._lazy = lazy
        self._query_builder = query_builder
        self._is_materialized = not lazy or elements is not None
        self._relationships: Dict[str, Any] = {}
        self._loaded_relationships: Set[str] = set()
    
    # Collection interface
    
    def __len__(self) -> int:
        """Get the number of elements in the collection."""
        self._ensure_materialized()
        return len(self._elements)
    
    def __getitem__(self, index: Union[int, slice]) -> Union[T, 'ElementSet[T]']:
        """Get element by index or slice."""
        self._ensure_materialized()
        
        if isinstance(index, slice):
            return ElementSet(
                self._elements[index],
                element_type=self._element_type,
                lazy=False
            )
        else:
            return self._elements[index]
    
    def __iter__(self) -> Iterator[T]:
        """Iterate over elements."""
        self._ensure_materialized()
        return iter(self._elements)
    
    def __contains__(self, item: T) -> bool:
        """Check if element is in collection."""
        self._ensure_materialized()
        return item in self._elements
    
    def __bool__(self) -> bool:
        """Check if collection is non-empty."""
        return self.any()
    
    def __repr__(self) -> str:
        """String representation."""
        count = len(self._elements) if self._is_materialized else "?"
        type_name = self._element_type.__name__ if self._element_type else "Element"
        return f"ElementSet<{type_name}>[{count}]"
    
    # LINQ-style query operations
    
    def where(self, predicate: QueryPredicate[T]) -> 'ElementSet[T]':
        """Filter elements using a predicate."""
        if self._query_builder:
            new_builder = self._query_builder.where(predicate)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            filtered = [elem for elem in self._elements if predicate(elem)]
            return ElementSet(filtered, element_type=self._element_type, lazy=False)
    
    def select(self, selector: QuerySelector[T, R]) -> 'ElementSet[R]':
        """Project elements using a selector."""
        if self._query_builder:
            new_builder = self._query_builder.select(selector)
            return ElementSet(lazy=True, query_builder=new_builder)
        else:
            self._ensure_materialized()
            projected = [selector(elem) for elem in self._elements]
            return ElementSet(projected, lazy=False)
    
    def order_by(self, key_selector: QueryKeySelector[T]) -> 'ElementSet[T]':
        """Sort elements in ascending order."""
        if self._query_builder:
            new_builder = self._query_builder.order_by(key_selector)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            sorted_elements = sorted(self._elements, key=key_selector)
            return ElementSet(sorted_elements, element_type=self._element_type, lazy=False)
    
    def order_by_descending(self, key_selector: QueryKeySelector[T]) -> 'ElementSet[T]':
        """Sort elements in descending order."""
        if self._query_builder:
            new_builder = self._query_builder.order_by_descending(key_selector)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            sorted_elements = sorted(self._elements, key=key_selector, reverse=True)
            return ElementSet(sorted_elements, element_type=self._element_type, lazy=False)
    
    def skip(self, count: int) -> 'ElementSet[T]':
        """Skip the specified number of elements."""
        if self._query_builder:
            new_builder = self._query_builder.skip(count)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            return ElementSet(self._elements[count:], element_type=self._element_type, lazy=False)
    
    def take(self, count: int) -> 'ElementSet[T]':
        """Take only the specified number of elements."""
        if self._query_builder:
            new_builder = self._query_builder.take(count)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            return ElementSet(self._elements[:count], element_type=self._element_type, lazy=False)
    
    def distinct(self, key_selector: Optional[QueryKeySelector[T]] = None) -> 'ElementSet[T]':
        """Get distinct elements."""
        if self._query_builder:
            new_builder = self._query_builder.distinct(key_selector)
            return ElementSet(lazy=True, query_builder=new_builder, element_type=self._element_type)
        else:
            self._ensure_materialized()
            
            if key_selector is None:
                # Distinct by object identity
                seen = set()
                unique = []
                for elem in self._elements:
                    elem_id = id(elem)
                    if elem_id not in seen:
                        seen.add(elem_id)
                        unique.append(elem)
                return ElementSet(unique, element_type=self._element_type, lazy=False)
            else:
                # Distinct by key
                seen = set()
                unique = []
                for elem in self._elements:
                    key = key_selector(elem)
                    if key not in seen:
                        seen.add(key)
                        unique.append(elem)
                return ElementSet(unique, element_type=self._element_type, lazy=False)
    
    # Terminal operations
    
    def first(self, predicate: Optional[QueryPredicate[T]] = None) -> T:
        """Get the first element, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        query._ensure_materialized()
        
        if not query._elements:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="first",
                element_count=0
            )
        
        return query._elements[0]
    
    def first_or_default(
        self,
        predicate: Optional[QueryPredicate[T]] = None,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get the first element or default value."""
        try:
            return self.first(predicate)
        except QueryError:
            return default
    
    def last(self, predicate: Optional[QueryPredicate[T]] = None) -> T:
        """Get the last element, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        query._ensure_materialized()
        
        if not query._elements:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="last",
                element_count=0
            )
        
        return query._elements[-1]
    
    def last_or_default(
        self,
        predicate: Optional[QueryPredicate[T]] = None,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get the last element or default value."""
        try:
            return self.last(predicate)
        except QueryError:
            return default
    
    def single(self, predicate: Optional[QueryPredicate[T]] = None) -> T:
        """Get the single element, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        query._ensure_materialized()
        
        if len(query._elements) == 0:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="single",
                element_count=0
            )
        elif len(query._elements) > 1:
            raise QueryError(
                "Sequence contains more than one element",
                query_operation="single",
                element_count=len(query._elements)
            )
        
        return query._elements[0]
    
    def single_or_default(
        self,
        predicate: Optional[QueryPredicate[T]] = None,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get the single element or default value."""
        try:
            return self.single(predicate)
        except QueryError:
            return default
    
    def any(self, predicate: Optional[QueryPredicate[T]] = None) -> bool:
        """Check if any elements match the predicate."""
        if predicate is None:
            if self._query_builder:
                return self._query_builder.any()
            else:
                return len(self._elements) > 0
        else:
            return self.where(predicate).any()
    
    def all(self, predicate: QueryPredicate[T]) -> bool:
        """Check if all elements match the predicate."""
        if self._query_builder:
            return self._query_builder.all(predicate)
        else:
            self._ensure_materialized()
            return all(predicate(elem) for elem in self._elements)
    
    def count(self, predicate: Optional[QueryPredicate[T]] = None) -> int:
        """Get count of elements, optionally matching a predicate."""
        if predicate is None:
            if self._query_builder:
                return self._query_builder.count()
            else:
                return len(self._elements)
        else:
            return self.where(predicate).count()
    
    def to_list(self) -> List[T]:
        """Convert to list."""
        self._ensure_materialized()
        return self._elements.copy()
    
    def to_dict(self, key_selector: QueryKeySelector[T]) -> Dict[Any, T]:
        """Convert to dictionary using key selector."""
        self._ensure_materialized()
        return {key_selector(elem): elem for elem in self._elements}
    
    def to_lookup(self, key_selector: QueryKeySelector[T]) -> Dict[Any, List[T]]:
        """Create lookup dictionary (one-to-many mapping)."""
        self._ensure_materialized()
        lookup = {}
        for elem in self._elements:
            key = key_selector(elem)
            if key not in lookup:
                lookup[key] = []
            lookup[key].append(elem)
        return lookup
    
    def group_by(self, key_selector: QueryKeySelector[T]) -> Dict[Any, 'ElementSet[T]']:
        """Group elements by key selector."""
        lookup = self.to_lookup(key_selector)
        return {
            key: ElementSet(elements, element_type=self._element_type, lazy=False)
            for key, elements in lookup.items()
        }
    
    # Aggregation operations
    
    def sum(self, selector: Optional[QuerySelector[T, Union[int, float]]] = None) -> Union[int, float]:
        """Sum numeric values."""
        self._ensure_materialized()
        
        if selector is None:
            return sum(self._elements)  # type: ignore
        else:
            return sum(selector(elem) for elem in self._elements)
    
    def average(self, selector: Optional[QuerySelector[T, Union[int, float]]] = None) -> float:
        """Calculate average of numeric values."""
        self._ensure_materialized()
        
        if not self._elements:
            raise QueryError("Cannot calculate average of empty sequence")
        
        total = self.sum(selector)
        return total / len(self._elements)
    
    def min(self, selector: Optional[QueryKeySelector[T]] = None) -> Union[T, Any]:
        """Get minimum value."""
        self._ensure_materialized()
        
        if not self._elements:
            raise QueryError("Cannot get minimum of empty sequence")
        
        if selector is None:
            return min(self._elements)
        else:
            return min(self._elements, key=selector)
    
    def max(self, selector: Optional[QueryKeySelector[T]] = None) -> Union[T, Any]:
        """Get maximum value."""
        self._ensure_materialized()
        
        if not self._elements:
            raise QueryError("Cannot get maximum of empty sequence")
        
        if selector is None:
            return max(self._elements)
        else:
            return max(self._elements, key=selector)
    
    # Set operations
    
    def union(self, other: 'ElementSet[T]') -> 'ElementSet[T]':
        """Union with another element set."""
        self._ensure_materialized()
        other._ensure_materialized()
        
        combined = list(self._elements)
        combined.extend(elem for elem in other._elements if elem not in combined)
        
        return ElementSet(combined, element_type=self._element_type, lazy=False)
    
    def intersect(self, other: 'ElementSet[T]') -> 'ElementSet[T]':
        """Intersection with another element set."""
        self._ensure_materialized()
        other._ensure_materialized()
        
        other_set = set(other._elements)
        intersection = [elem for elem in self._elements if elem in other_set]
        
        return ElementSet(intersection, element_type=self._element_type, lazy=False)
    
    def except_elements(self, other: 'ElementSet[T]') -> 'ElementSet[T]':
        """Elements in this set but not in other set."""
        self._ensure_materialized()
        other._ensure_materialized()
        
        other_set = set(other._elements)
        difference = [elem for elem in self._elements if elem not in other_set]
        
        return ElementSet(difference, element_type=self._element_type, lazy=False)
    
    # Relationship navigation
    
    def include(self, relationship_path: str) -> 'ElementSet[T]':
        """Include related data in the query."""
        if self._query_builder:
            # For query-backed sets, include would be handled by the query builder
            new_set = ElementSet(
                lazy=True,
                query_builder=self._query_builder,
                element_type=self._element_type
            )
            new_set._relationships[relationship_path] = LoadStrategy.EAGER
            return new_set
        else:
            # For materialized sets, mark for eager loading
            new_set = ElementSet(self._elements, element_type=self._element_type, lazy=False)
            new_set._relationships[relationship_path] = LoadStrategy.EAGER
            return new_set
    
    def load_relationship(
        self,
        relationship_name: str,
        strategy: LoadStrategy = LoadStrategy.LAZY
    ) -> None:
        """Load a relationship for all elements in the set."""
        self._ensure_materialized()
        
        if hasattr(self._elements[0], '_load_relationship'):
            for element in self._elements:
                element._load_relationship(relationship_name, strategy)
        
        self._loaded_relationships.add(relationship_name)
    
    # Performance operations
    
    def batch_update(
        self,
        updates: Dict[str, Any],
        batch_size: int = 100
    ) -> int:
        """Batch update properties on all elements."""
        self._ensure_materialized()
        
        updated_count = 0
        
        for i in range(0, len(self._elements), batch_size):
            batch = self._elements[i:i + batch_size]
            
            for element in batch:
                for prop_name, value in updates.items():
                    if hasattr(element, prop_name):
                        setattr(element, prop_name, value)
                        updated_count += 1
        
        logger.info(f"Batch updated {updated_count} properties across {len(self._elements)} elements")
        return updated_count
    
    def for_each(self, action: Callable[[T], None]) -> None:
        """Execute action for each element."""
        self._ensure_materialized()
        
        for element in self._elements:
            action(element)
    
    # Internal methods
    
    def _ensure_materialized(self) -> None:
        """Ensure the collection is materialized (evaluated)."""
        if not self._is_materialized:
            if self._query_builder:
                self._elements = self._query_builder.to_list()
                self._is_materialized = True
            else:
                # Already materialized or empty
                self._is_materialized = True
    
    # Class methods for creation
    
    @classmethod
    def empty(cls, element_type: Optional[Type[T]] = None) -> 'ElementSet[T]':
        """Create an empty element set."""
        return cls([], element_type=element_type, lazy=False)
    
    @classmethod
    def from_query(cls, query_builder: QueryBuilder[T]) -> 'ElementSet[T]':
        """Create element set from query builder."""
        return cls(lazy=True, query_builder=query_builder)


class AsyncElementSet(Generic[T], IAsyncQueryable[T]):
    """
    Async version of ElementSet with full async/await support.
    
    Provides async versions of all ElementSet operations for high-performance
    scenarios with large datasets or expensive operations.
    """
    
    def __init__(
        self,
        element_set: Optional[ElementSet[T]] = None,
        query_builder: Optional[QueryBuilder[T]] = None
    ) -> None:
        self._element_set = element_set or ElementSet()
        self._query_builder = query_builder
    
    # Async query operations
    
    def where(self, predicate: QueryPredicate[T]) -> 'AsyncElementSet[T]':
        """Async filter elements using a predicate."""
        if self._query_builder:
            new_builder = self._query_builder.where(predicate)
            return AsyncElementSet(query_builder=new_builder)
        else:
            filtered_set = self._element_set.where(predicate)
            return AsyncElementSet(filtered_set)
    
    def select(self, selector: QuerySelector[T, R]) -> 'AsyncElementSet[R]':
        """Async project elements using a selector."""
        if self._query_builder:
            new_builder = self._query_builder.select(selector)
            return AsyncElementSet(query_builder=new_builder)
        else:
            selected_set = self._element_set.select(selector)
            return AsyncElementSet(selected_set)
    
    def order_by(self, key_selector: QueryKeySelector[T]) -> 'AsyncElementSet[T]':
        """Async sort elements in ascending order."""
        if self._query_builder:
            new_builder = self._query_builder.order_by(key_selector)
            return AsyncElementSet(query_builder=new_builder)
        else:
            ordered_set = self._element_set.order_by(key_selector)
            return AsyncElementSet(ordered_set)
    
    def skip(self, count: int) -> 'AsyncElementSet[T]':
        """Async skip the specified number of elements."""
        if self._query_builder:
            new_builder = self._query_builder.skip(count)
            return AsyncElementSet(query_builder=new_builder)
        else:
            skipped_set = self._element_set.skip(count)
            return AsyncElementSet(skipped_set)
    
    def take(self, count: int) -> 'AsyncElementSet[T]':
        """Async take only the specified number of elements."""
        if self._query_builder:
            new_builder = self._query_builder.take(count)
            return AsyncElementSet(query_builder=new_builder)
        else:
            taken_set = self._element_set.take(count)
            return AsyncElementSet(taken_set)
    
    # Async terminal operations
    
    async def first_async(self, predicate: Optional[QueryPredicate[T]] = None) -> T:
        """Async get the first element."""
        if self._query_builder:
            return await self._query_builder.first_async(predicate)
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._element_set.first, predicate
            )
    
    async def count_async(self, predicate: Optional[QueryPredicate[T]] = None) -> int:
        """Async get count of elements."""
        if self._query_builder:
            return await self._query_builder.count_async(predicate)
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._element_set.count, predicate
            )
    
    async def any_async(self, predicate: Optional[QueryPredicate[T]] = None) -> bool:
        """Async check if any elements match the predicate."""
        if self._query_builder:
            return await self._query_builder.any_async(predicate)
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._element_set.any, predicate
            )
    
    async def to_list_async(self) -> List[T]:
        """Async convert to list."""
        if self._query_builder:
            return await self._query_builder.to_list_async()
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._element_set.to_list
            )
    
    async def for_each_async(self, action: Callable[[T], Awaitable[None]]) -> None:
        """Execute async action for each element."""
        elements = await self.to_list_async()
        tasks = [action(element) for element in elements]
        await asyncio.gather(*tasks)
    
    async def batch_update_async(
        self,
        updates: Dict[str, Any],
        batch_size: int = 100
    ) -> int:
        """Async batch update properties on all elements."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._element_set.batch_update, updates, batch_size
        )
    
    # Async iterator support
    
    async def __aiter__(self) -> AsyncIterator[T]:
        """Async iterator support."""
        elements = await self.to_list_async()
        for element in elements:
            yield element
    
    # Sync bridge methods
    
    def to_sync(self) -> ElementSet[T]:
        """Convert to synchronous ElementSet."""
        return self._element_set
    
    @classmethod
    def from_sync(cls, element_set: ElementSet[T]) -> 'AsyncElementSet[T]':
        """Create from synchronous ElementSet."""
        return cls(element_set)