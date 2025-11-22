"""
Comprehensive test suite for revitpy_package_manager/registry/services/cache.py

Tests cover:
- CacheService connection/disconnection
- Cache get/set/delete operations
- Cache serialization (pickle, JSON, string)
- Cache expiration and TTL
- Cache exists checking
- Namespace clearing
- Increment operations
- Bulk operations (get_multiple, set_multiple)
- PackageCache high-level interface
- Global cache service functions
- Error handling and graceful degradation
"""

import json
import pickle
from unittest.mock import AsyncMock, Mock, patch

import pytest
from revitpy_package_manager.registry.services.cache import (
    CacheService,
    PackageCache,
    get_cache_service,
    get_package_cache,
)


class TestCacheService:
    """Tests for CacheService class."""

    @pytest.mark.asyncio
    async def test_init_with_redis_url(self):
        """Test CacheService initialization with explicit Redis URL."""
        cache = CacheService(redis_url="redis://localhost:6379")
        assert cache.redis_url == "redis://localhost:6379"
        assert cache.redis_client is None
        assert cache._connected is False

    @pytest.mark.asyncio
    async def test_init_without_redis_url(self):
        """Test CacheService initialization using config."""
        with patch(
            "revitpy_package_manager.registry.services.cache.get_settings"
        ) as mock_settings:
            mock_config = Mock()
            mock_config.cache.redis_url = "redis://config:6379"
            mock_settings.return_value = mock_config

            cache = CacheService()
            assert cache.redis_url == "redis://config:6379"

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to Redis."""
        cache = CacheService(redis_url="redis://localhost:6379")

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch(
            "revitpy_package_manager.registry.services.cache.redis.from_url",
            return_value=mock_redis,
        ):
            await cache.connect()

            assert cache.redis_client == mock_redis
            assert cache._connected is True
            mock_redis.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure with graceful degradation."""
        cache = CacheService(redis_url="redis://invalid:6379")

        with patch(
            "revitpy_package_manager.registry.services.cache.redis.from_url"
        ) as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")

            await cache.connect()

            assert cache._connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection from Redis."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache.redis_client = AsyncMock()
        cache._connected = True

        await cache.disconnect()

        cache.redis_client.close.assert_awaited_once()
        assert cache._connected is False

    def test_make_key(self):
        """Test cache key generation."""
        cache = CacheService(redis_url="redis://localhost:6379")
        key = cache._make_key("packages", "test-package")
        assert key == "revitpy:registry:packages:test-package"

    @pytest.mark.asyncio
    async def test_get_not_connected(self):
        """Test get returns None when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.get("packages", "test-package")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test get returns None on cache miss."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.get = AsyncMock(return_value=None)

        result = await cache.get("packages", "test-package")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pickle_serialized(self):
        """Test get with pickle-serialized data."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        test_data = {"name": "test", "version": "1.0.0", "nested": {"foo": "bar"}}
        pickled_data = pickle.dumps(test_data)
        cache.redis_client.get = AsyncMock(return_value=pickled_data)

        result = await cache.get("packages", "test-package")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_json_serialized(self):
        """Test get with JSON-serialized data (pickle fallback)."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        test_data = {"name": "test", "version": "1.0.0"}
        json_data = json.dumps(test_data).encode("utf-8")
        cache.redis_client.get = AsyncMock(return_value=json_data)

        # Mock pickle.loads to fail, triggering JSON fallback
        with patch("pickle.loads", side_effect=pickle.PickleError):
            result = await cache.get("packages", "test-package")
            assert result == test_data

    @pytest.mark.asyncio
    async def test_get_string_serialized(self):
        """Test get with plain string data."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        string_data = b"plain text data"
        cache.redis_client.get = AsyncMock(return_value=string_data)

        # Mock both pickle and json to fail, triggering string fallback
        with patch("pickle.loads", side_effect=pickle.PickleError):
            with patch("json.loads", side_effect=json.JSONDecodeError("test", "", 0)):
                result = await cache.get("packages", "test-package")
                assert result == "plain text data"

    @pytest.mark.asyncio
    async def test_get_error_handling(self):
        """Test get error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.get = AsyncMock(side_effect=Exception("Redis error"))

        result = await cache.get("packages", "test-package")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_not_connected(self):
        """Test set returns False when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.set("packages", "test-package", {"data": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_set_with_pickle(self):
        """Test set with pickle serialization."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        test_data = {"name": "test", "version": "1.0.0"}
        result = await cache.set("packages", "test-package", test_data, ttl=600)

        assert result is True
        cache.redis_client.setex.assert_awaited_once()
        call_args = cache.redis_client.setex.call_args
        assert call_args[0][0] == "revitpy:registry:packages:test-package"
        assert call_args[0][1] == 600
        assert pickle.loads(call_args[0][2]) == test_data

    @pytest.mark.asyncio
    async def test_set_with_json_fallback(self):
        """Test set with JSON fallback when pickle fails."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        test_data = {"name": "test"}

        with patch("pickle.dumps", side_effect=pickle.PickleError):
            result = await cache.set("packages", "test-package", test_data)

            assert result is True
            call_args = cache.redis_client.setex.call_args
            assert json.loads(call_args[0][2].decode("utf-8")) == test_data

    @pytest.mark.asyncio
    async def test_set_with_string_fallback(self):
        """Test set with string fallback when pickle and JSON fail."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        # Use a non-JSON-serializable object
        class CustomObject:
            def __str__(self):
                return "custom-value"

        test_data = CustomObject()

        with patch("pickle.dumps", side_effect=pickle.PickleError):
            result = await cache.set("packages", "test-package", test_data)

            assert result is True
            call_args = cache.redis_client.setex.call_args
            assert call_args[0][2] == b"custom-value"

    @pytest.mark.asyncio
    async def test_set_with_default_ttl(self):
        """Test set uses default TTL when not specified."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        await cache.set("packages", "test-package", {"data": "test"})

        call_args = cache.redis_client.setex.call_args
        assert call_args[0][1] == CacheService.DEFAULT_TTL

    @pytest.mark.asyncio
    async def test_set_error_handling(self):
        """Test set error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.setex = AsyncMock(side_effect=Exception("Redis error"))

        result = await cache.set("packages", "test-package", {"data": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_not_connected(self):
        """Test delete returns False when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.delete("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful delete operation."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.delete = AsyncMock(return_value=1)

        result = await cache.delete("packages", "test-package")

        assert result is True
        cache.redis_client.delete.assert_awaited_once_with(
            "revitpy:registry:packages:test-package"
        )

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test delete returns False when key doesn't exist."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.delete = AsyncMock(return_value=0)

        result = await cache.delete("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_error_handling(self):
        """Test delete error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.delete = AsyncMock(side_effect=Exception("Redis error"))

        result = await cache.delete("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_not_connected(self):
        """Test exists returns False when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.exists("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test exists returns True when key exists."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.exists = AsyncMock(return_value=1)

        result = await cache.exists("packages", "test-package")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test exists returns False when key doesn't exist."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.exists = AsyncMock(return_value=0)

        result = await cache.exists("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_error_handling(self):
        """Test exists error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.exists = AsyncMock(side_effect=Exception("Redis error"))

        result = await cache.exists("packages", "test-package")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_namespace_not_connected(self):
        """Test clear_namespace returns 0 when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.clear_namespace("packages")
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_namespace_with_keys(self):
        """Test clear_namespace deletes matching keys."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        # Mock scan_iter to return some keys
        keys = [
            b"revitpy:registry:packages:pkg1",
            b"revitpy:registry:packages:pkg2",
            b"revitpy:registry:packages:pkg3",
        ]

        async def mock_scan_iter(*args, **kwargs):
            for key in keys:
                yield key

        cache.redis_client.scan_iter = mock_scan_iter
        cache.redis_client.delete = AsyncMock(return_value=3)

        result = await cache.clear_namespace("packages")

        assert result == 3
        cache.redis_client.delete.assert_awaited_once_with(*keys)

    @pytest.mark.asyncio
    async def test_clear_namespace_no_keys(self):
        """Test clear_namespace with no matching keys."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            return
            yield  # Make it a generator

        cache.redis_client.scan_iter = mock_scan_iter

        result = await cache.clear_namespace("packages")
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_namespace_error_handling(self):
        """Test clear_namespace error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            raise Exception("Redis error")
            yield

        cache.redis_client.scan_iter = mock_scan_iter

        result = await cache.clear_namespace("packages")
        assert result == 0

    @pytest.mark.asyncio
    async def test_increment_not_connected(self):
        """Test increment returns None when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.increment("downloads", "package-name")
        assert result is None

    @pytest.mark.asyncio
    async def test_increment_without_ttl(self):
        """Test increment without TTL."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True

        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[5])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)

        cache.redis_client = AsyncMock()
        cache.redis_client.pipeline = Mock(return_value=mock_pipe)

        result = await cache.increment("downloads", "package-name", amount=1)

        assert result == 5
        mock_pipe.incrby.assert_called_once_with(
            "revitpy:registry:downloads:package-name", 1
        )

    @pytest.mark.asyncio
    async def test_increment_with_ttl(self):
        """Test increment with TTL."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True

        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[10])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)

        cache.redis_client = AsyncMock()
        cache.redis_client.pipeline = Mock(return_value=mock_pipe)

        result = await cache.increment("downloads", "package-name", amount=5, ttl=3600)

        assert result == 10
        mock_pipe.incrby.assert_called_once_with(
            "revitpy:registry:downloads:package-name", 5
        )
        mock_pipe.expire.assert_called_once_with(
            "revitpy:registry:downloads:package-name", 3600
        )

    @pytest.mark.asyncio
    async def test_increment_error_handling(self):
        """Test increment error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(side_effect=Exception("Redis error"))

        cache.redis_client = AsyncMock()
        cache.redis_client.pipeline = Mock(return_value=mock_pipe)

        result = await cache.increment("downloads", "package-name")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_multiple_not_connected(self):
        """Test get_multiple returns empty dict when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.get_multiple("packages", ["pkg1", "pkg2"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_multiple_empty_keys(self):
        """Test get_multiple with empty keys list."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        result = await cache.get_multiple("packages", [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_multiple_success(self):
        """Test get_multiple retrieves multiple values."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        data1 = {"name": "pkg1", "version": "1.0"}
        data2 = {"name": "pkg2", "version": "2.0"}

        cache.redis_client.mget = AsyncMock(
            return_value=[pickle.dumps(data1), pickle.dumps(data2), None]
        )

        result = await cache.get_multiple("packages", ["pkg1", "pkg2", "pkg3"])

        assert result == {"pkg1": data1, "pkg2": data2, "pkg3": None}

    @pytest.mark.asyncio
    async def test_get_multiple_error_handling(self):
        """Test get_multiple error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()
        cache.redis_client.mget = AsyncMock(side_effect=Exception("Redis error"))

        result = await cache.get_multiple("packages", ["pkg1", "pkg2"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_set_multiple_not_connected(self):
        """Test set_multiple returns False when not connected."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = False

        result = await cache.set_multiple("packages", {"pkg1": {"data": "test"}})
        assert result is False

    @pytest.mark.asyncio
    async def test_set_multiple_empty_values(self):
        """Test set_multiple with empty values dict."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        result = await cache.set_multiple("packages", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_set_multiple_success(self):
        """Test set_multiple stores multiple values."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True

        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)

        cache.redis_client = AsyncMock()
        cache.redis_client.pipeline = Mock(return_value=mock_pipe)

        values = {"pkg1": {"version": "1.0"}, "pkg2": {"version": "2.0"}}
        result = await cache.set_multiple("packages", values, ttl=600)

        assert result is True
        mock_pipe.mset.assert_called_once()
        assert mock_pipe.expire.call_count == 2

    @pytest.mark.asyncio
    async def test_set_multiple_error_handling(self):
        """Test set_multiple error handling."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(side_effect=Exception("Redis error"))

        cache.redis_client = AsyncMock()
        cache.redis_client.pipeline = Mock(return_value=mock_pipe)

        result = await cache.set_multiple("packages", {"pkg1": {"data": "test"}})
        assert result is False


class TestPackageCache:
    """Tests for PackageCache high-level interface."""

    @pytest.mark.asyncio
    async def test_get_package(self):
        """Test get_package delegates to cache service."""
        cache_service = Mock(spec=CacheService)
        cache_service.get = AsyncMock(return_value={"name": "test-package"})
        package_cache = PackageCache(cache_service)

        result = await package_cache.get_package("test-package")

        assert result == {"name": "test-package"}
        cache_service.get.assert_awaited_once_with("packages", "test-package")

    @pytest.mark.asyncio
    async def test_set_package(self):
        """Test set_package delegates to cache service."""
        cache_service = Mock(spec=CacheService)
        cache_service.set = AsyncMock(return_value=True)
        package_cache = PackageCache(cache_service)

        package_data = {"name": "test-package", "version": "1.0.0"}
        result = await package_cache.set_package("test-package", package_data, ttl=900)

        assert result is True
        cache_service.set.assert_awaited_once_with(
            "packages", "test-package", package_data, 900
        )

    @pytest.mark.asyncio
    async def test_set_package_default_ttl(self):
        """Test set_package uses default TTL."""
        cache_service = Mock(spec=CacheService)
        cache_service.set = AsyncMock(return_value=True)
        package_cache = PackageCache(cache_service)

        await package_cache.set_package("test-package", {"data": "test"})

        cache_service.set.assert_awaited_once_with(
            "packages", "test-package", {"data": "test"}, 1800
        )

    @pytest.mark.asyncio
    async def test_get_package_versions(self):
        """Test get_package_versions retrieves versions list."""
        cache_service = Mock(spec=CacheService)
        versions = [{"version": "1.0.0"}, {"version": "1.1.0"}]
        cache_service.get = AsyncMock(return_value=versions)
        package_cache = PackageCache(cache_service)

        result = await package_cache.get_package_versions("test-package")

        assert result == versions
        cache_service.get.assert_awaited_once_with("package_versions", "test-package")

    @pytest.mark.asyncio
    async def test_set_package_versions(self):
        """Test set_package_versions stores versions list."""
        cache_service = Mock(spec=CacheService)
        cache_service.set = AsyncMock(return_value=True)
        package_cache = PackageCache(cache_service)

        versions = [{"version": "1.0.0"}, {"version": "1.1.0"}]
        result = await package_cache.set_package_versions("test-package", versions)

        assert result is True
        cache_service.set.assert_awaited_once_with(
            "package_versions", "test-package", versions, 900
        )

    @pytest.mark.asyncio
    async def test_get_search_results(self):
        """Test get_search_results with hashed query."""
        cache_service = Mock(spec=CacheService)
        search_results = {"results": ["pkg1", "pkg2"]}
        cache_service.get = AsyncMock(return_value=search_results)
        package_cache = PackageCache(cache_service)

        query = "test query"
        result = await package_cache.get_search_results(query)

        assert result == search_results
        cache_service.get.assert_awaited_once()
        call_args = cache_service.get.call_args
        assert call_args[0][0] == "search"
        assert call_args[0][1].startswith("search:")

    @pytest.mark.asyncio
    async def test_set_search_results(self):
        """Test set_search_results with hashed query."""
        cache_service = Mock(spec=CacheService)
        cache_service.set = AsyncMock(return_value=True)
        package_cache = PackageCache(cache_service)

        query = "test query"
        results = {"results": ["pkg1", "pkg2"]}
        result = await package_cache.set_search_results(query, results)

        assert result is True
        cache_service.set.assert_awaited_once()
        call_args = cache_service.set.call_args
        assert call_args[0][0] == "search"
        assert call_args[0][1].startswith("search:")
        assert call_args[0][2] == results
        assert call_args[0][3] == 600

    @pytest.mark.asyncio
    async def test_increment_download_count(self):
        """Test increment_download_count increments counter."""
        cache_service = Mock(spec=CacheService)
        cache_service.increment = AsyncMock(return_value=42)
        package_cache = PackageCache(cache_service)

        result = await package_cache.increment_download_count("test-package")

        assert result == 42
        cache_service.increment.assert_awaited_once_with(
            "download_counts", "test-package", ttl=86400
        )

    @pytest.mark.asyncio
    async def test_get_popular_packages(self):
        """Test get_popular_packages retrieves popular list."""
        cache_service = Mock(spec=CacheService)
        popular = ["pkg1", "pkg2", "pkg3"]
        cache_service.get = AsyncMock(return_value=popular)
        package_cache = PackageCache(cache_service)

        result = await package_cache.get_popular_packages(limit=50)

        assert result == popular
        cache_service.get.assert_awaited_once_with("popular", "packages:50")

    @pytest.mark.asyncio
    async def test_set_popular_packages(self):
        """Test set_popular_packages stores popular list."""
        cache_service = Mock(spec=CacheService)
        cache_service.set = AsyncMock(return_value=True)
        package_cache = PackageCache(cache_service)

        popular = ["pkg1", "pkg2", "pkg3"]
        result = await package_cache.set_popular_packages(popular, limit=50)

        assert result is True
        cache_service.set.assert_awaited_once_with(
            "popular", "packages:50", popular, 3600
        )

    @pytest.mark.asyncio
    async def test_invalidate_package(self):
        """Test invalidate_package clears all related cache entries."""
        cache_service = Mock(spec=CacheService)
        cache_service.delete = AsyncMock(return_value=True)
        cache_service.clear_namespace = AsyncMock(return_value=5)
        package_cache = PackageCache(cache_service)

        result = await package_cache.invalidate_package("test-package")

        assert result is True
        assert cache_service.delete.call_count == 2
        cache_service.delete.assert_any_await("packages", "test-package")
        cache_service.delete.assert_any_await("package_versions", "test-package")
        cache_service.clear_namespace.assert_awaited_once_with("search")

    @pytest.mark.asyncio
    async def test_invalidate_package_partial_success(self):
        """Test invalidate_package with partial deletion success."""
        cache_service = Mock(spec=CacheService)
        cache_service.delete = AsyncMock(side_effect=[True, False])
        cache_service.clear_namespace = AsyncMock(return_value=0)
        package_cache = PackageCache(cache_service)

        result = await package_cache.invalidate_package("test-package")

        # Result should be False because one delete failed
        assert result is False


class TestGlobalCacheFunctions:
    """Tests for global cache service functions."""

    @pytest.mark.asyncio
    async def test_get_cache_service_creates_singleton(self):
        """Test get_cache_service creates and returns singleton instance."""
        # Reset global cache service
        import revitpy_package_manager.registry.services.cache as cache_module

        cache_module._cache_service = None

        with patch.object(
            CacheService, "connect", new_callable=AsyncMock
        ) as mock_connect:
            cache1 = await get_cache_service()
            cache2 = await get_cache_service()

            assert cache1 is cache2
            assert isinstance(cache1, CacheService)
            mock_connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_package_cache(self):
        """Test get_package_cache returns PackageCache instance."""
        import revitpy_package_manager.registry.services.cache as cache_module

        cache_module._cache_service = None

        with patch.object(CacheService, "connect", new_callable=AsyncMock):
            package_cache = await get_package_cache()

            assert isinstance(package_cache, PackageCache)
            assert isinstance(package_cache.cache, CacheService)


class TestIntegration:
    """Integration tests for cache service."""

    @pytest.mark.asyncio
    async def test_cache_lifecycle(self):
        """Test complete cache lifecycle: connect, set, get, delete."""
        cache = CacheService(redis_url="redis://localhost:6379")
        cache._connected = True
        cache.redis_client = AsyncMock()

        # Set value
        cache.redis_client.setex = AsyncMock()
        await cache.set("packages", "test-pkg", {"version": "1.0.0"}, ttl=300)

        # Get value
        cache.redis_client.get = AsyncMock(
            return_value=pickle.dumps({"version": "1.0.0"})
        )
        result = await cache.get("packages", "test-pkg")
        assert result == {"version": "1.0.0"}

        # Delete value
        cache.redis_client.delete = AsyncMock(return_value=1)
        deleted = await cache.delete("packages", "test-pkg")
        assert deleted is True

    @pytest.mark.asyncio
    async def test_package_cache_workflow(self):
        """Test typical package cache workflow."""
        cache_service = Mock(spec=CacheService)
        cache_service.get = AsyncMock(return_value=None)
        cache_service.set = AsyncMock(return_value=True)
        cache_service.delete = AsyncMock(return_value=True)
        cache_service.clear_namespace = AsyncMock(return_value=3)
        cache_service.increment = AsyncMock(return_value=1)

        package_cache = PackageCache(cache_service)

        # Cache miss
        result = await package_cache.get_package("new-package")
        assert result is None

        # Cache set
        package_data = {"name": "new-package", "version": "1.0.0"}
        await package_cache.set_package("new-package", package_data)

        # Track download
        count = await package_cache.increment_download_count("new-package")
        assert count == 1

        # Invalidate
        await package_cache.invalidate_package("new-package")

        assert cache_service.delete.call_count == 2
        assert cache_service.clear_namespace.call_count == 1
