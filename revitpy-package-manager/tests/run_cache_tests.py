#!/usr/bin/env python3
"""
Standalone test runner for cache.py service tests.

This script runs tests for the CacheService and PackageCache classes
without requiring pytest or a real Redis connection.

Usage:
    python tests/run_cache_tests.py
"""

import asyncio
import json
import pickle
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from revitpy_package_manager.registry.services.cache import (
    CacheService,
    PackageCache,
    get_cache_service,
    get_package_cache,
)


class TestRunner:
    """Simple test runner for standalone execution."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name: str):
        """Decorator to mark a test function."""

        def decorator(func):
            async def wrapper():
                try:
                    await func()
                    self.passed += 1
                    print(f"✓ {name}")
                except AssertionError as e:
                    self.failed += 1
                    error_msg = f"✗ {name}: {str(e)}"
                    print(error_msg)
                    self.errors.append(error_msg)
                except Exception as e:
                    self.failed += 1
                    error_msg = f"✗ {name}: {type(e).__name__}: {str(e)}"
                    print(error_msg)
                    self.errors.append(error_msg)

            return wrapper

        return decorator

    def print_summary(self):
        """Print test results summary."""
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  {error}")
        print("=" * 70)


# Create test runner instance
runner = TestRunner()


# ============================================================================
# CacheService Tests
# ============================================================================


@runner.test("CacheService: Initialize with Redis URL")
async def test_init_with_redis_url():
    cache = CacheService(redis_url="redis://localhost:6379")
    assert cache.redis_url == "redis://localhost:6379"
    assert cache.redis_client is None
    assert cache._connected is False


@runner.test("CacheService: Initialize without Redis URL uses config")
async def test_init_without_redis_url():
    with patch(
        "revitpy_package_manager.registry.services.cache.get_settings"
    ) as mock_settings:
        mock_config = Mock()
        mock_config.cache.redis_url = "redis://config:6379"
        mock_settings.return_value = mock_config

        cache = CacheService()
        assert cache.redis_url == "redis://config:6379"


@runner.test("CacheService: Connect successfully")
async def test_connect_success():
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


@runner.test("CacheService: Handle connection failure gracefully")
async def test_connect_failure():
    cache = CacheService(redis_url="redis://invalid:6379")

    with patch(
        "revitpy_package_manager.registry.services.cache.redis.from_url"
    ) as mock_from_url:
        mock_from_url.side_effect = Exception("Connection failed")

        await cache.connect()

        assert cache._connected is False


@runner.test("CacheService: Disconnect from Redis")
async def test_disconnect():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache.redis_client = AsyncMock()
    cache._connected = True

    await cache.disconnect()

    assert cache._connected is False


@runner.test("CacheService: Generate namespaced cache key")
async def test_make_key():
    cache = CacheService(redis_url="redis://localhost:6379")
    key = cache._make_key("packages", "test-package")
    assert key == "revitpy:registry:packages:test-package"


@runner.test("CacheService: Get returns None when not connected")
async def test_get_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.get("packages", "test-package")
    assert result is None


@runner.test("CacheService: Get returns None on cache miss")
async def test_get_cache_miss():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.get = AsyncMock(return_value=None)

    result = await cache.get("packages", "test-package")
    assert result is None


@runner.test("CacheService: Get deserializes pickle data")
async def test_get_pickle_serialized():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    test_data = {"name": "test", "version": "1.0.0", "nested": {"foo": "bar"}}
    pickled_data = pickle.dumps(test_data)
    cache.redis_client.get = AsyncMock(return_value=pickled_data)

    result = await cache.get("packages", "test-package")
    assert result == test_data


@runner.test("CacheService: Get deserializes JSON data")
async def test_get_json_serialized():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    test_data = {"name": "test", "version": "1.0.0"}
    json_data = json.dumps(test_data).encode("utf-8")
    cache.redis_client.get = AsyncMock(return_value=json_data)

    with patch("pickle.loads", side_effect=pickle.PickleError):
        result = await cache.get("packages", "test-package")
        assert result == test_data


@runner.test("CacheService: Get deserializes string data")
async def test_get_string_serialized():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    string_data = b"plain text data"
    cache.redis_client.get = AsyncMock(return_value=string_data)

    with patch("pickle.loads", side_effect=pickle.PickleError):
        with patch("json.loads", side_effect=json.JSONDecodeError("test", "", 0)):
            result = await cache.get("packages", "test-package")
            assert result == "plain text data"


@runner.test("CacheService: Get handles errors gracefully")
async def test_get_error_handling():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.get = AsyncMock(side_effect=Exception("Redis error"))

    result = await cache.get("packages", "test-package")
    assert result is None


@runner.test("CacheService: Set returns False when not connected")
async def test_set_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.set("packages", "test-package", {"data": "test"})
    assert result is False


@runner.test("CacheService: Set with pickle serialization")
async def test_set_with_pickle():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    test_data = {"name": "test", "version": "1.0.0"}
    result = await cache.set("packages", "test-package", test_data, ttl=600)

    assert result is True
    call_args = cache.redis_client.setex.call_args
    assert call_args[0][0] == "revitpy:registry:packages:test-package"
    assert call_args[0][1] == 600


@runner.test("CacheService: Set uses default TTL")
async def test_set_with_default_ttl():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    await cache.set("packages", "test-package", {"data": "test"})

    call_args = cache.redis_client.setex.call_args
    assert call_args[0][1] == CacheService.DEFAULT_TTL


@runner.test("CacheService: Set handles errors gracefully")
async def test_set_error_handling():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.setex = AsyncMock(side_effect=Exception("Redis error"))

    result = await cache.set("packages", "test-package", {"data": "test"})
    assert result is False


@runner.test("CacheService: Delete returns False when not connected")
async def test_delete_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.delete("packages", "test-package")
    assert result is False


@runner.test("CacheService: Delete successfully removes key")
async def test_delete_success():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.delete = AsyncMock(return_value=1)

    result = await cache.delete("packages", "test-package")

    assert result is True


@runner.test("CacheService: Delete returns False when key not found")
async def test_delete_not_found():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.delete = AsyncMock(return_value=0)

    result = await cache.delete("packages", "test-package")
    assert result is False


@runner.test("CacheService: Exists returns False when not connected")
async def test_exists_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.exists("packages", "test-package")
    assert result is False


@runner.test("CacheService: Exists returns True when key exists")
async def test_exists_true():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.exists = AsyncMock(return_value=1)

    result = await cache.exists("packages", "test-package")
    assert result is True


@runner.test("CacheService: Exists returns False when key doesn't exist")
async def test_exists_false():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()
    cache.redis_client.exists = AsyncMock(return_value=0)

    result = await cache.exists("packages", "test-package")
    assert result is False


@runner.test("CacheService: Clear namespace returns 0 when not connected")
async def test_clear_namespace_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.clear_namespace("packages")
    assert result == 0


@runner.test("CacheService: Clear namespace deletes matching keys")
async def test_clear_namespace_with_keys():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

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


@runner.test("CacheService: Clear namespace with no matching keys")
async def test_clear_namespace_no_keys():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    async def mock_scan_iter(*args, **kwargs):
        return
        yield

    cache.redis_client.scan_iter = mock_scan_iter

    result = await cache.clear_namespace("packages")
    assert result == 0


@runner.test("CacheService: Increment returns None when not connected")
async def test_increment_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.increment("downloads", "package-name")
    assert result is None


@runner.test("CacheService: Increment without TTL")
async def test_increment_without_ttl():
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


@runner.test("CacheService: Increment with TTL")
async def test_increment_with_ttl():
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


@runner.test("CacheService: Get multiple returns empty dict when not connected")
async def test_get_multiple_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.get_multiple("packages", ["pkg1", "pkg2"])
    assert result == {}


@runner.test("CacheService: Get multiple with empty keys")
async def test_get_multiple_empty_keys():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    result = await cache.get_multiple("packages", [])
    assert result == {}


@runner.test("CacheService: Get multiple retrieves multiple values")
async def test_get_multiple_success():
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


@runner.test("CacheService: Set multiple returns False when not connected")
async def test_set_multiple_not_connected():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = False

    result = await cache.set_multiple("packages", {"pkg1": {"data": "test"}})
    assert result is False


@runner.test("CacheService: Set multiple with empty values")
async def test_set_multiple_empty_values():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    result = await cache.set_multiple("packages", {})
    assert result is False


@runner.test("CacheService: Set multiple stores multiple values")
async def test_set_multiple_success():
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


# ============================================================================
# PackageCache Tests
# ============================================================================


@runner.test("PackageCache: Get package delegates to cache service")
async def test_get_package():
    cache_service = Mock(spec=CacheService)
    cache_service.get = AsyncMock(return_value={"name": "test-package"})
    package_cache = PackageCache(cache_service)

    result = await package_cache.get_package("test-package")

    assert result == {"name": "test-package"}


@runner.test("PackageCache: Set package delegates to cache service")
async def test_set_package():
    cache_service = Mock(spec=CacheService)
    cache_service.set = AsyncMock(return_value=True)
    package_cache = PackageCache(cache_service)

    package_data = {"name": "test-package", "version": "1.0.0"}
    result = await package_cache.set_package("test-package", package_data, ttl=900)

    assert result is True


@runner.test("PackageCache: Set package uses default TTL")
async def test_set_package_default_ttl():
    cache_service = Mock(spec=CacheService)
    cache_service.set = AsyncMock(return_value=True)
    package_cache = PackageCache(cache_service)

    await package_cache.set_package("test-package", {"data": "test"})

    call_args = cache_service.set.call_args
    assert call_args[0][3] == 1800


@runner.test("PackageCache: Get package versions")
async def test_get_package_versions():
    cache_service = Mock(spec=CacheService)
    versions = [{"version": "1.0.0"}, {"version": "1.1.0"}]
    cache_service.get = AsyncMock(return_value=versions)
    package_cache = PackageCache(cache_service)

    result = await package_cache.get_package_versions("test-package")

    assert result == versions


@runner.test("PackageCache: Set package versions")
async def test_set_package_versions():
    cache_service = Mock(spec=CacheService)
    cache_service.set = AsyncMock(return_value=True)
    package_cache = PackageCache(cache_service)

    versions = [{"version": "1.0.0"}, {"version": "1.1.0"}]
    result = await package_cache.set_package_versions("test-package", versions)

    assert result is True


@runner.test("PackageCache: Get search results with hashed query")
async def test_get_search_results():
    cache_service = Mock(spec=CacheService)
    search_results = {"results": ["pkg1", "pkg2"]}
    cache_service.get = AsyncMock(return_value=search_results)
    package_cache = PackageCache(cache_service)

    query = "test query"
    result = await package_cache.get_search_results(query)

    assert result == search_results


@runner.test("PackageCache: Set search results with hashed query")
async def test_set_search_results():
    cache_service = Mock(spec=CacheService)
    cache_service.set = AsyncMock(return_value=True)
    package_cache = PackageCache(cache_service)

    query = "test query"
    results = {"results": ["pkg1", "pkg2"]}
    result = await package_cache.set_search_results(query, results)

    assert result is True


@runner.test("PackageCache: Increment download count")
async def test_increment_download_count():
    cache_service = Mock(spec=CacheService)
    cache_service.increment = AsyncMock(return_value=42)
    package_cache = PackageCache(cache_service)

    result = await package_cache.increment_download_count("test-package")

    assert result == 42


@runner.test("PackageCache: Get popular packages")
async def test_get_popular_packages():
    cache_service = Mock(spec=CacheService)
    popular = ["pkg1", "pkg2", "pkg3"]
    cache_service.get = AsyncMock(return_value=popular)
    package_cache = PackageCache(cache_service)

    result = await package_cache.get_popular_packages(limit=50)

    assert result == popular


@runner.test("PackageCache: Set popular packages")
async def test_set_popular_packages():
    cache_service = Mock(spec=CacheService)
    cache_service.set = AsyncMock(return_value=True)
    package_cache = PackageCache(cache_service)

    popular = ["pkg1", "pkg2", "pkg3"]
    result = await package_cache.set_popular_packages(popular, limit=50)

    assert result is True


@runner.test("PackageCache: Invalidate package clears all related entries")
async def test_invalidate_package():
    cache_service = Mock(spec=CacheService)
    cache_service.delete = AsyncMock(return_value=True)
    cache_service.clear_namespace = AsyncMock(return_value=5)
    package_cache = PackageCache(cache_service)

    result = await package_cache.invalidate_package("test-package")

    assert result is True
    assert cache_service.delete.call_count == 2


# ============================================================================
# Global Cache Functions Tests
# ============================================================================


@runner.test("Global: get_cache_service creates singleton")
async def test_get_cache_service_singleton():
    import revitpy_package_manager.registry.services.cache as cache_module

    cache_module._cache_service = None

    with patch.object(CacheService, "connect", new_callable=AsyncMock):
        cache1 = await get_cache_service()
        cache2 = await get_cache_service()

        assert cache1 is cache2
        assert isinstance(cache1, CacheService)


@runner.test("Global: get_package_cache returns PackageCache instance")
async def test_get_package_cache_instance():
    import revitpy_package_manager.registry.services.cache as cache_module

    cache_module._cache_service = None

    with patch.object(CacheService, "connect", new_callable=AsyncMock):
        package_cache = await get_package_cache()

        assert isinstance(package_cache, PackageCache)
        assert isinstance(package_cache.cache, CacheService)


# ============================================================================
# Integration Tests
# ============================================================================


@runner.test("Integration: Complete cache lifecycle")
async def test_cache_lifecycle():
    cache = CacheService(redis_url="redis://localhost:6379")
    cache._connected = True
    cache.redis_client = AsyncMock()

    # Set value
    cache.redis_client.setex = AsyncMock()
    await cache.set("packages", "test-pkg", {"version": "1.0.0"}, ttl=300)

    # Get value
    cache.redis_client.get = AsyncMock(return_value=pickle.dumps({"version": "1.0.0"}))
    result = await cache.get("packages", "test-pkg")
    assert result == {"version": "1.0.0"}

    # Delete value
    cache.redis_client.delete = AsyncMock(return_value=1)
    deleted = await cache.delete("packages", "test-pkg")
    assert deleted is True


@runner.test("Integration: Package cache workflow")
async def test_package_cache_workflow():
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


# ============================================================================
# Main Execution
# ============================================================================


async def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("Running Cache Service Tests")
    print("=" * 70 + "\n")

    # Get all test functions
    test_functions = [
        obj
        for name, obj in globals().items()
        if name.startswith("test_") and asyncio.iscoroutinefunction(obj)
    ]

    # Run each test
    for test_func in test_functions:
        await test_func()

    # Print summary
    runner.print_summary()

    # Return exit code
    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
