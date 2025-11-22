"""
Enhanced QueryBuilder with lazy evaluation and async support.

This module provides the core LINQ-style query interface for the ORM layer,
featuring lazy evaluation, async operations, and intelligent query optimization.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Generic,
    TypeVar,
)

from loguru import logger

from .cache import CacheManager
from .exceptions import QueryError
from .types import (
    CacheKey,
    CachePolicy,
    IAsyncQueryable,
    IElementProvider,
    IQueryable,
    QueryKeySelector,
    QueryMode,
    QueryPredicate,
    QuerySelector,
)

T = TypeVar("T")
R = TypeVar("R")
E = TypeVar("E", bound="Element")


@dataclass
class QueryPlan:
    """Represents an optimized query execution plan."""

    operations: list[tuple[str, Any]] = field(default_factory=list)
    estimated_cost: float = 0.0
    use_index: bool = False
    parallel_execution: bool = False
    cache_strategy: CachePolicy = CachePolicy.MEMORY

    def add_operation(self, operation: str, details: Any, cost: float = 1.0) -> None:
        """Add an operation to the query plan."""
        self.operations.append((operation, details))
        self.estimated_cost += cost

    def optimize(self) -> QueryPlan:
        """Optimize the query plan."""
        # Move filters before projections
        filters = [op for op in self.operations if op[0] == "filter"]
        projections = [op for op in self.operations if op[0] == "select"]
        others = [op for op in self.operations if op[0] not in ("filter", "select")]

        optimized = QueryPlan()
        optimized.operations = filters + others + projections
        optimized.estimated_cost = self.estimated_cost * 0.8  # Assume 20% improvement
        optimized.use_index = len(filters) > 0
        optimized.parallel_execution = self.estimated_cost > 10.0
        optimized.cache_strategy = self.cache_strategy

        return optimized


class LazyQueryExecutor(Generic[T]):
    """Executor that provides lazy evaluation of queries."""

    def __init__(
        self,
        provider: IElementProvider,
        element_type: type[T] | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._provider = provider
        self._element_type = element_type
        self._cache_manager = cache_manager or CacheManager()
        self._query_plan = QueryPlan()
        self._is_executed = False
        self._results: list[T] | None = None
        self._query_hash: str | None = None

    def set_query_plan(self, plan: QueryPlan) -> None:
        """Set the query execution plan."""
        self._query_plan = plan
        self._query_hash = None  # Reset hash when plan changes

    @property
    def query_hash(self) -> str:
        """Get hash of the current query plan."""
        if self._query_hash is None:
            plan_str = json.dumps(
                [(op, str(details)) for op, details in self._query_plan.operations],
                sort_keys=True,
            )
            self._query_hash = hashlib.md5(plan_str.encode()).hexdigest()
        return self._query_hash

    def execute(self) -> list[T]:
        """Execute the query and return results."""
        if self._is_executed and self._results is not None:
            return self._results

        # Check cache first
        if self._query_plan.cache_strategy != CachePolicy.NONE:
            cache_key = CacheKey(
                entity_type=self._element_type.__name__
                if self._element_type
                else "Element",
                query_hash=self.query_hash,
            )

            cached_result = self._cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Query cache hit: {cache_key}")
                self._results = cached_result
                self._is_executed = True
                return self._results

        # Execute query
        start_time = datetime.utcnow()

        try:
            # Get initial elements
            if self._element_type:
                elements = self._provider.get_elements_of_type(self._element_type)
            else:
                elements = self._provider.get_all_elements()

            # Apply query operations
            current_results = elements
            for operation, details in self._query_plan.operations:
                current_results = self._apply_operation(
                    operation, details, current_results
                )

            self._results = current_results
            self._is_executed = True

            # Cache results if enabled
            if (
                self._query_plan.cache_strategy != CachePolicy.NONE
                and len(self._results) < 1000
            ):  # Don't cache huge result sets
                cache_key = CacheKey(
                    entity_type=self._element_type.__name__
                    if self._element_type
                    else "Element",
                    query_hash=self.query_hash,
                )
                self._cache_manager.set(cache_key, self._results)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(
                f"Query executed in {execution_time:.2f}ms, returned {len(self._results)} elements"
            )

            return self._results

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise QueryError(
                f"Failed to execute query: {e}",
                query_expression=str(self._query_plan.operations),
                cause=e,
            )

    async def execute_async(self) -> list[T]:
        """Execute the query asynchronously."""
        if self._is_executed and self._results is not None:
            return self._results

        return await asyncio.get_event_loop().run_in_executor(None, self.execute)

    async def execute_streaming(self, batch_size: int = 100) -> AsyncIterator[list[T]]:
        """Execute query with streaming results."""
        if self._query_plan.parallel_execution:
            # For large queries, execute in chunks
            full_results = await self.execute_async()

            for i in range(0, len(full_results), batch_size):
                yield full_results[i : i + batch_size]
        else:
            # For small queries, return all at once
            results = await self.execute_async()
            yield results

    def _apply_operation(
        self, operation: str, details: Any, elements: list[T]
    ) -> list[T]:
        """Apply a single query operation to elements."""
        if operation == "filter":
            predicate = details
            return [elem for elem in elements if predicate(elem)]

        elif operation == "select":
            selector = details
            return [selector(elem) for elem in elements]

        elif operation == "order_by":
            key_selector, reverse = details
            return sorted(elements, key=key_selector, reverse=reverse)

        elif operation == "skip":
            count = details
            return elements[count:]

        elif operation == "take":
            count = details
            return elements[:count]

        elif operation == "distinct":
            key_selector = details
            if key_selector is None:
                # Distinct by object identity
                seen = set()
                result = []
                for elem in elements:
                    elem_id = id(elem)
                    if elem_id not in seen:
                        seen.add(elem_id)
                        result.append(elem)
                return result
            else:
                # Distinct by key
                seen = set()
                result = []
                for elem in elements:
                    key = key_selector(elem)
                    if key not in seen:
                        seen.add(key)
                        result.append(elem)
                return result

        else:
            logger.warning(f"Unknown query operation: {operation}")
            return elements


class QueryBuilder(Generic[T], IQueryable[T], IAsyncQueryable[T]):
    """
    Enhanced LINQ-style query builder with lazy evaluation and async support.

    Provides a fluent interface for building complex queries with automatic
    optimization, caching, and both synchronous and asynchronous execution.
    """

    def __init__(
        self,
        provider: IElementProvider,
        element_type: type[T] | None = None,
        cache_manager: CacheManager | None = None,
        query_mode: QueryMode = QueryMode.LAZY,
    ) -> None:
        self._provider = provider
        self._element_type = element_type
        self._cache_manager = cache_manager or CacheManager()
        self._query_mode = query_mode
        self._query_plan = QueryPlan()
        self._executor = LazyQueryExecutor[T](provider, element_type, cache_manager)

    # Fluent interface methods

    def where(self, predicate: QueryPredicate[T]) -> QueryBuilder[T]:
        """Filter elements using a predicate function."""
        new_builder = self._clone()
        new_builder._query_plan.add_operation("filter", predicate, cost=2.0)
        return new_builder

    def select(self, selector: QuerySelector[T, R]) -> QueryBuilder[R]:
        """Project elements using a selector function."""
        new_builder = QueryBuilder[R](
            self._provider,
            cache_manager=self._cache_manager,
            query_mode=self._query_mode,
        )
        new_builder._query_plan = self._query_plan
        new_builder._query_plan.add_operation("select", selector, cost=1.0)
        return new_builder

    def order_by(self, key_selector: QueryKeySelector[T]) -> QueryBuilder[T]:
        """Sort elements in ascending order by key."""
        new_builder = self._clone()
        new_builder._query_plan.add_operation(
            "order_by", (key_selector, False), cost=3.0
        )
        return new_builder

    def order_by_descending(self, key_selector: QueryKeySelector[T]) -> QueryBuilder[T]:
        """Sort elements in descending order by key."""
        new_builder = self._clone()
        new_builder._query_plan.add_operation(
            "order_by", (key_selector, True), cost=3.0
        )
        return new_builder

    def skip(self, count: int) -> QueryBuilder[T]:
        """Skip the specified number of elements."""
        if count < 0:
            raise ValueError("Skip count cannot be negative")

        new_builder = self._clone()
        new_builder._query_plan.add_operation("skip", count, cost=0.1)
        return new_builder

    def take(self, count: int) -> QueryBuilder[T]:
        """Take only the specified number of elements."""
        if count <= 0:
            raise ValueError("Take count must be positive")

        new_builder = self._clone()
        new_builder._query_plan.add_operation("take", count, cost=0.1)
        return new_builder

    def distinct(
        self, key_selector: QueryKeySelector[T] | None = None
    ) -> QueryBuilder[T]:
        """Get distinct elements, optionally by key."""
        new_builder = self._clone()
        new_builder._query_plan.add_operation("distinct", key_selector, cost=2.5)
        return new_builder

    # Terminal operations (synchronous)

    def first(self, predicate: QueryPredicate[T] | None = None) -> T:
        """Get the first element, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        results = query.take(1).to_list()

        if not results:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="first",
                element_count=0,
            )

        return results[0]

    def first_or_default(
        self, predicate: QueryPredicate[T] | None = None, default: T | None = None
    ) -> T | None:
        """Get the first element or default value."""
        try:
            return self.first(predicate)
        except QueryError:
            return default

    def single(self, predicate: QueryPredicate[T] | None = None) -> T:
        """Get the single element, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        results = query.take(2).to_list()  # Take 2 to detect multiple

        if len(results) == 0:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="single",
                element_count=0,
            )
        elif len(results) > 1:
            raise QueryError(
                "Sequence contains more than one element",
                query_operation="single",
                element_count=len(results),
            )

        return results[0]

    def single_or_default(
        self, predicate: QueryPredicate[T] | None = None, default: T | None = None
    ) -> T | None:
        """Get the single element or default value."""
        try:
            return self.single(predicate)
        except QueryError:
            return default

    def any(self, predicate: QueryPredicate[T] | None = None) -> bool:
        """Check if any elements match the predicate."""
        query = self.where(predicate) if predicate else self
        return query.take(1).count() > 0

    def all(self, predicate: QueryPredicate[T]) -> bool:
        """Check if all elements match the predicate."""
        # Efficient implementation: check if any element does NOT match
        return not self.where(lambda x: not predicate(x)).any()

    def count(self, predicate: QueryPredicate[T] | None = None) -> int:
        """Get count of elements, optionally matching a predicate."""
        query = self.where(predicate) if predicate else self
        return len(query._execute())

    def to_list(self) -> list[T]:
        """Execute query and return results as list."""
        return self._execute()

    def to_dict(self, key_selector: QueryKeySelector[T]) -> dict[Any, T]:
        """Execute query and return results as dictionary."""
        results = self._execute()
        return {key_selector(item): item for item in results}

    def group_by(self, key_selector: QueryKeySelector[T]) -> dict[Any, list[T]]:
        """Group elements by key selector."""
        results = self._execute()
        groups = {}

        for item in results:
            key = key_selector(item)
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        return groups

    # Terminal operations (asynchronous)

    async def first_async(self, predicate: QueryPredicate[T] | None = None) -> T:
        """Async version of first()."""
        query = self.where(predicate) if predicate else self
        results = await query.take(1).to_list_async()

        if not results:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="first_async",
                element_count=0,
            )

        return results[0]

    async def first_or_default_async(
        self, predicate: QueryPredicate[T] | None = None, default: T | None = None
    ) -> T | None:
        """Async version of first_or_default()."""
        try:
            return await self.first_async(predicate)
        except QueryError:
            return default

    async def single_async(self, predicate: QueryPredicate[T] | None = None) -> T:
        """Async version of single()."""
        query = self.where(predicate) if predicate else self
        results = await query.take(2).to_list_async()

        if len(results) == 0:
            raise QueryError(
                "Sequence contains no elements",
                query_operation="single_async",
                element_count=0,
            )
        elif len(results) > 1:
            raise QueryError(
                "Sequence contains more than one element",
                query_operation="single_async",
                element_count=len(results),
            )

        return results[0]

    async def any_async(self, predicate: QueryPredicate[T] | None = None) -> bool:
        """Async version of any()."""
        query = self.where(predicate) if predicate else self
        count = await query.take(1).count_async()
        return count > 0

    async def count_async(self, predicate: QueryPredicate[T] | None = None) -> int:
        """Async version of count()."""
        query = self.where(predicate) if predicate else self
        results = await query._execute_async()
        return len(results)

    async def to_list_async(self) -> list[T]:
        """Async version of to_list()."""
        return await self._execute_async()

    async def to_dict_async(self, key_selector: QueryKeySelector[T]) -> dict[Any, T]:
        """Async version of to_dict()."""
        results = await self._execute_async()
        return {key_selector(item): item for item in results}

    # Streaming support

    def as_streaming(self, batch_size: int = 100) -> StreamingQuery[T]:
        """Convert to streaming query for large datasets."""
        return StreamingQuery(self, batch_size)

    async def __aiter__(self) -> AsyncIterator[T]:
        """Async iterator support."""
        results = await self._execute_async()
        for item in results:
            yield item

    # Iterator support

    def __iter__(self) -> Iterator[T]:
        """Synchronous iterator support."""
        results = self._execute()
        return iter(results)

    def __len__(self) -> int:
        """Length support."""
        return self.count()

    # Internal methods

    def _clone(self) -> QueryBuilder[T]:
        """Create a copy of this query builder."""
        clone = QueryBuilder[T](
            self._provider, self._element_type, self._cache_manager, self._query_mode
        )
        clone._query_plan = QueryPlan()
        clone._query_plan.operations = self._query_plan.operations.copy()
        clone._query_plan.estimated_cost = self._query_plan.estimated_cost
        clone._query_plan.cache_strategy = self._query_plan.cache_strategy
        return clone

    def _execute(self) -> list[T]:
        """Execute the query synchronously."""
        optimized_plan = self._query_plan.optimize()
        self._executor.set_query_plan(optimized_plan)

        if self._query_mode == QueryMode.EAGER:
            return self._executor.execute()
        else:
            # Lazy execution - return results immediately for now
            # In a real implementation, this could return a lazy collection
            return self._executor.execute()

    async def _execute_async(self) -> list[T]:
        """Execute the query asynchronously."""
        optimized_plan = self._query_plan.optimize()
        self._executor.set_query_plan(optimized_plan)
        return await self._executor.execute_async()


class StreamingQuery(Generic[T]):
    """Wrapper for streaming query execution."""

    def __init__(self, query_builder: QueryBuilder[T], batch_size: int = 100) -> None:
        self._query_builder = query_builder
        self._batch_size = batch_size

    async def __aiter__(self) -> AsyncIterator[list[T]]:
        """Iterate over batches of results."""
        executor = self._query_builder._executor
        optimized_plan = self._query_builder._query_plan.optimize()
        executor.set_query_plan(optimized_plan)

        async for batch in executor.execute_streaming(self._batch_size):
            yield batch

    async def foreach_async(self, action: Callable[[T], Awaitable[None]]) -> None:
        """Apply async action to each element."""
        async for batch in self:
            tasks = [action(item) for item in batch]
            await asyncio.gather(*tasks)

    async def to_list_async(self) -> list[T]:
        """Collect all batches into a single list."""
        result = []
        async for batch in self:
            result.extend(batch)
        return result


# Convenience functions for creating queries


def query(provider: IElementProvider) -> QueryBuilder[Any]:
    """Create a new query builder."""
    return QueryBuilder(provider)


def query_of_type(provider: IElementProvider, element_type: type[T]) -> QueryBuilder[T]:
    """Create a typed query builder."""
    return QueryBuilder(provider, element_type)


async def async_query(provider: IElementProvider) -> QueryBuilder[Any]:
    """Create a new async query builder."""
    builder = QueryBuilder(provider, query_mode=QueryMode.LAZY)
    return builder
