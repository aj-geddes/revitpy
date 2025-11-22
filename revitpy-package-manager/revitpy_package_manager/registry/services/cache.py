"""Redis caching service for improved performance."""

import json
import pickle
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from ...config import get_settings


class CacheService:
    """Redis-based caching service for the package registry."""

    DEFAULT_TTL = 3600  # 1 hour default TTL

    def __init__(self, redis_url: str | None = None):
        """Initialize the cache service.

        Args:
            redis_url: Redis connection URL. If None, uses centralized config.
        """
        settings = get_settings()
        self.redis_url = redis_url or (
            str(settings.cache.redis_url) if settings.cache.redis_url else None
        )
        self.redis_client: Redis | None = None
        self._connected = False

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )

            # Test connection
            await self.redis_client.ping()
            self._connected = True

        except Exception as e:
            self._connected = False
            # Log error but don't fail - degrade gracefully
            print(f"Failed to connect to Redis: {e}")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False

    def _make_key(self, namespace: str, key: str) -> str:
        """Create a namespaced cache key."""
        return f"revitpy:registry:{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> Any | None:
        """Get a value from cache.

        Args:
            namespace: Cache namespace (e.g., 'packages', 'users')
            key: Cache key

        Returns:
            Cached value or None if not found or cache unavailable
        """
        if not self._connected or not self.redis_client:
            return None

        try:
            cache_key = self._make_key(namespace, key)
            value = await self.redis_client.get(cache_key)

            if value is None:
                return None

            # Try to deserialize
            try:
                return pickle.loads(value)
            except (pickle.PickleError, TypeError):
                # Fallback to JSON
                try:
                    return json.loads(value.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return value.decode("utf-8")

        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    async def set(
        self, namespace: str, key: str, value: Any, ttl: int | None = None
    ) -> bool:
        """Set a value in cache.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self.redis_client:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            ttl = ttl or self.DEFAULT_TTL

            # Serialize value
            try:
                serialized_value = pickle.dumps(value)
            except (pickle.PickleError, TypeError):
                # Fallback to JSON
                try:
                    serialized_value = json.dumps(value).encode("utf-8")
                except (TypeError, ValueError):
                    serialized_value = str(value).encode("utf-8")

            await self.redis_client.setex(cache_key, ttl, serialized_value)
            return True

        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from cache.

        Args:
            namespace: Cache namespace
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self.redis_client:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            result = await self.redis_client.delete(cache_key)
            return result > 0

        except Exception as e:
            print(f"Cache delete error: {e}")
            return False

    async def exists(self, namespace: str, key: str) -> bool:
        """Check if a key exists in cache.

        Args:
            namespace: Cache namespace
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        if not self._connected or not self.redis_client:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            result = await self.redis_client.exists(cache_key)
            return result > 0

        except Exception as e:
            print(f"Cache exists error: {e}")
            return False

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace.

        Args:
            namespace: Cache namespace to clear

        Returns:
            Number of keys deleted
        """
        if not self._connected or not self.redis_client:
            return 0

        try:
            pattern = self._make_key(namespace, "*")
            keys = []

            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis_client.delete(*keys)

            return 0

        except Exception as e:
            print(f"Cache clear namespace error: {e}")
            return 0

    async def increment(
        self, namespace: str, key: str, amount: int = 1, ttl: int | None = None
    ) -> int | None:
        """Increment a numeric value in cache.

        Args:
            namespace: Cache namespace
            key: Cache key
            amount: Amount to increment by
            ttl: TTL for the key if it doesn't exist

        Returns:
            New value after increment, or None if failed
        """
        if not self._connected or not self.redis_client:
            return None

        try:
            cache_key = self._make_key(namespace, key)

            # Use pipeline for atomic operation
            async with self.redis_client.pipeline() as pipe:
                pipe.incrby(cache_key, amount)
                if ttl:
                    pipe.expire(cache_key, ttl)

                results = await pipe.execute()
                return results[0]

        except Exception as e:
            print(f"Cache increment error: {e}")
            return None

    async def get_multiple(self, namespace: str, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache.

        Args:
            namespace: Cache namespace
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values (None for missing keys)
        """
        if not self._connected or not self.redis_client or not keys:
            return {}

        try:
            cache_keys = [self._make_key(namespace, key) for key in keys]
            values = await self.redis_client.mget(cache_keys)

            result = {}
            for i, key in enumerate(keys):
                value = values[i]
                if value is not None:
                    try:
                        result[key] = pickle.loads(value)
                    except (pickle.PickleError, TypeError):
                        try:
                            result[key] = json.loads(value.decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            result[key] = value.decode("utf-8")
                else:
                    result[key] = None

            return result

        except Exception as e:
            print(f"Cache get_multiple error: {e}")
            return {}

    async def set_multiple(
        self, namespace: str, values: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """Set multiple values in cache.

        Args:
            namespace: Cache namespace
            values: Dictionary of key-value pairs
            ttl: Time to live for all keys

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self.redis_client or not values:
            return False

        try:
            ttl = ttl or self.DEFAULT_TTL

            # Prepare data for mset
            cache_data = {}
            for key, value in values.items():
                cache_key = self._make_key(namespace, key)

                try:
                    serialized_value = pickle.dumps(value)
                except (pickle.PickleError, TypeError):
                    try:
                        serialized_value = json.dumps(value).encode("utf-8")
                    except (TypeError, ValueError):
                        serialized_value = str(value).encode("utf-8")

                cache_data[cache_key] = serialized_value

            # Use pipeline for atomic operation
            async with self.redis_client.pipeline() as pipe:
                pipe.mset(cache_data)
                for cache_key in cache_data.keys():
                    pipe.expire(cache_key, ttl)

                await pipe.execute()
                return True

        except Exception as e:
            print(f"Cache set_multiple error: {e}")
            return False


class PackageCache:
    """High-level caching interface for package-related data."""

    def __init__(self, cache_service: CacheService):
        self.cache = cache_service

    async def get_package(self, package_name: str) -> dict | None:
        """Get package metadata from cache."""
        return await self.cache.get("packages", package_name)

    async def set_package(
        self, package_name: str, package_data: dict, ttl: int = 1800
    ) -> bool:
        """Cache package metadata."""
        return await self.cache.set("packages", package_name, package_data, ttl)

    async def get_package_versions(self, package_name: str) -> list[dict] | None:
        """Get package versions from cache."""
        return await self.cache.get("package_versions", package_name)

    async def set_package_versions(
        self, package_name: str, versions: list[dict], ttl: int = 900
    ) -> bool:
        """Cache package versions."""
        return await self.cache.set("package_versions", package_name, versions, ttl)

    async def get_search_results(self, query: str) -> dict | None:
        """Get search results from cache."""
        cache_key = f"search:{hash(query)}"
        return await self.cache.get("search", cache_key)

    async def set_search_results(
        self, query: str, results: dict, ttl: int = 600
    ) -> bool:
        """Cache search results."""
        cache_key = f"search:{hash(query)}"
        return await self.cache.set("search", cache_key, results, ttl)

    async def increment_download_count(self, package_name: str) -> int | None:
        """Increment package download count."""
        return await self.cache.increment("download_counts", package_name, ttl=86400)

    async def get_popular_packages(self, limit: int = 50) -> list[str] | None:
        """Get popular packages list from cache."""
        return await self.cache.get("popular", f"packages:{limit}")

    async def set_popular_packages(
        self, packages: list[str], limit: int = 50, ttl: int = 3600
    ) -> bool:
        """Cache popular packages list."""
        return await self.cache.set("popular", f"packages:{limit}", packages, ttl)

    async def invalidate_package(self, package_name: str) -> bool:
        """Invalidate all cache entries for a package."""
        success = True
        success &= await self.cache.delete("packages", package_name)
        success &= await self.cache.delete("package_versions", package_name)

        # Clear search cache (simple approach - clear all search results)
        await self.cache.clear_namespace("search")

        return success


# Global cache service instance
_cache_service: CacheService | None = None


async def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()

    return _cache_service


async def get_package_cache() -> PackageCache:
    """Get the package cache instance."""
    cache_service = await get_cache_service()
    return PackageCache(cache_service)
