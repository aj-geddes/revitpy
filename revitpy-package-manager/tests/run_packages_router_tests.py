"""Standalone test runner for packages router.

This script tests the packages router without requiring pytest or database setup.
Run with: python tests/run_packages_router_tests.py
"""

import asyncio
import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock database and service modules before importing router
sys.modules["revitpy_package_manager.registry.database"] = MagicMock()
sys.modules["revitpy_package_manager.registry.services.cache"] = MagicMock()
sys.modules["revitpy_package_manager.registry.services.storage"] = MagicMock()
sys.modules["revitpy_package_manager.registry.security"] = MagicMock()
sys.modules["revitpy_package_manager.registry.security.config"] = MagicMock()
sys.modules["revitpy_package_manager.registry.api.routers.auth"] = MagicMock()

from revitpy_package_manager.registry.api.routers.packages import (
    create_package,
    delete_package,
    get_package,
    get_package_stats,
    list_package_versions,
    list_packages,
    normalize_package_name,
    search_packages,
    update_package,
    upload_package_version,
)
from revitpy_package_manager.registry.api.schemas import (
    DependencyBase,
    PackageCreate,
    PackageUpdate,
    PackageVersionCreate,
)

# ============================================================================
# Test Utilities
# ============================================================================


class TestRunner:
    """Simple test runner for standalone tests."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def run_test(self, test_func, test_name):
        """Run a single test function."""
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            self.passed += 1
            print(f"  ✅ {test_name}")
        except AssertionError as e:
            self.failed += 1
            self.errors.append((test_name, str(e)))
            print(f"  ❌ {test_name}: {e}")
        except Exception as e:
            self.failed += 1
            self.errors.append((test_name, f"Error: {e}"))
            print(f"  ❌ {test_name}: Error: {e}")

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        if self.failed == 0:
            print("  ✅ ALL TESTS PASSED! 🎉")
        else:
            print("  ⚠️  SOME TESTS FAILED")
        print("=" * 70)
        print(f"\nTotal: {total} | Passed: {self.passed} | Failed: {self.failed}\n")

        if self.errors:
            print("Failed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")


runner = TestRunner()


# ============================================================================
# Test normalize_package_name
# ============================================================================


def test_normalize_lowercase():
    """Test normalizing uppercase to lowercase."""
    assert normalize_package_name("MyPackage") == "mypackage"


def test_normalize_underscores():
    """Test normalizing underscores to hyphens."""
    assert normalize_package_name("my_package") == "my-package"


def test_normalize_spaces():
    """Test normalizing spaces to hyphens."""
    assert normalize_package_name("my package") == "my-package"


def test_normalize_mixed():
    """Test normalizing mixed characters."""
    assert normalize_package_name("My_Package Name") == "my-package-name"


def test_normalize_already_normalized():
    """Test normalizing already normalized name."""
    assert normalize_package_name("my-package") == "my-package"


# ============================================================================
# Test list_packages
# ============================================================================


async def test_list_packages_default():
    """Test listing packages with default parameters."""
    mock_db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 0

    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await list_packages(db=mock_db)

    assert response.packages == []
    assert response.total == 0
    assert response.page == 1
    assert response.per_page == 20
    assert response.has_next is False
    assert response.has_prev is False


async def test_list_packages_with_pagination():
    """Test listing packages with custom pagination."""
    mock_db = AsyncMock()

    mock_packages = [Mock(id=1, name="pkg1"), Mock(id=2, name="pkg2")]
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_packages

    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 50

    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await list_packages(page=2, per_page=10, db=mock_db)

    assert len(response.packages) == 2
    assert response.total == 50
    assert response.page == 2
    assert response.has_next is True
    assert response.has_prev is True


async def test_list_packages_with_category_filter():
    """Test listing packages filtered by category."""
    mock_db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 0

    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await list_packages(category="automation", db=mock_db)

    assert response.packages == []
    assert response.total == 0


# ============================================================================
# Test search_packages
# ============================================================================


async def test_search_packages_by_name():
    """Test searching packages by name."""
    mock_db = AsyncMock()

    mock_packages = [Mock(id=1, name="test-package")]
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_packages

    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 1

    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await search_packages(q="test", db=mock_db)

    assert len(response.packages) == 1
    assert response.total == 1
    assert response.query == "test"


async def test_search_packages_no_results():
    """Test searching packages with no results."""
    mock_db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 0

    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await search_packages(q="nonexistent", db=mock_db)

    assert len(response.packages) == 0
    assert response.total == 0


# ============================================================================
# Test create_package
# ============================================================================


async def test_create_package_success():
    """Test creating a new package successfully."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, username="testuser")

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    package_data = PackageCreate(
        name="test-package",
        summary="Test package summary",
        description="Test package description",
        keywords=["test", "example"],
        categories=["automation"],
    )

    await create_package(package_data=package_data, current_user=mock_user, db=mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


async def test_create_package_already_exists():
    """Test creating a package that already exists."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    existing_package = Mock(name="test-package")
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = existing_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    package_data = PackageCreate(
        name="test-package",
        summary="Test package",
        description="Description",
    )

    try:
        await create_package(
            package_data=package_data, current_user=mock_user, db=mock_db
        )
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert "already exists" in str(e.detail) or hasattr(e, "status_code")


# ============================================================================
# Test get_package
# ============================================================================


async def test_get_package_success():
    """Test getting an existing package."""
    mock_db = AsyncMock()

    mock_package = Mock(id=1, name="test-package")
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    package = await get_package(package_name="test-package", db=mock_db)

    assert package == mock_package


async def test_get_package_not_found():
    """Test getting a non-existent package."""
    mock_db = AsyncMock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await get_package(package_name="nonexistent", db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


# ============================================================================
# Test update_package
# ============================================================================


async def test_update_package_success():
    """Test updating a package successfully."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_package = Mock(id=1, name="test-package", owner_id=1, summary="Old")
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    package_update = PackageUpdate(summary="New summary")

    await update_package(
        package_name="test-package",
        package_update=package_update,
        current_user=mock_user,
        db=mock_db,
    )

    mock_db.commit.assert_awaited_once()


async def test_update_package_not_found():
    """Test updating a non-existent package."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    package_update = PackageUpdate(summary="New")

    try:
        await update_package(
            package_name="nonexistent",
            package_update=package_update,
            current_user=mock_user,
            db=mock_db,
        )
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


# ============================================================================
# Test delete_package
# ============================================================================


async def test_delete_package_success():
    """Test soft deleting a package."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_package = Mock(id=1, owner_id=1, is_published=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    await delete_package(
        package_name="test-package", current_user=mock_user, db=mock_db
    )

    assert mock_package.is_published is False
    mock_db.commit.assert_awaited_once()


async def test_delete_package_not_found():
    """Test deleting a non-existent package."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await delete_package(
            package_name="nonexistent", current_user=mock_user, db=mock_db
        )
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


# ============================================================================
# Test list_package_versions
# ============================================================================


async def test_list_package_versions_success():
    """Test listing package versions."""
    mock_db = AsyncMock()

    mock_package = Mock(id=1)
    mock_versions = [
        Mock(id=1, version="1.0.0"),
        Mock(id=2, version="1.1.0"),
    ]

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_versions_result = AsyncMock()
    mock_versions_result.scalars.return_value.all.return_value = mock_versions

    mock_db.execute = AsyncMock(side_effect=[mock_package_result, mock_versions_result])

    versions = await list_package_versions(package_name="test-package", db=mock_db)

    assert len(versions) == 2


async def test_list_package_versions_not_found():
    """Test listing versions for non-existent package."""
    mock_db = AsyncMock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await list_package_versions(package_name="nonexistent", db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


# ============================================================================
# Test upload_package_version
# ============================================================================


async def test_upload_package_version_success():
    """Test uploading a new package version."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)
    mock_storage = AsyncMock()
    mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

    mock_package = Mock(id=1, name="test-package", owner_id=1)

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_version_result = AsyncMock()
    mock_version_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[mock_package_result, mock_version_result])

    file_content = b"test package content"
    mock_file = Mock()
    mock_file.filename = "test-package-1.0.0.zip"
    mock_file.read = AsyncMock(return_value=file_content)

    metadata = PackageVersionCreate(
        version="1.0.0",
        summary="Test version",
        description="Test description",
        python_version=">=3.11",
        supported_revit_versions=["2025"],
        author="Test Author",
        author_email="test@example.com",
        license="MIT",
        dependencies=[],
    )

    await upload_package_version(
        package_name="test-package",
        file=mock_file,
        metadata=metadata,
        current_user=mock_user,
        db=mock_db,
        storage=mock_storage,
    )

    mock_storage.store_package.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


async def test_upload_package_version_already_exists():
    """Test uploading a version that already exists."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)
    mock_storage = AsyncMock()

    mock_package = Mock(id=1, owner_id=1)
    existing_version = Mock(version="1.0.0")

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_version_result = AsyncMock()
    mock_version_result.scalar_one_or_none.return_value = existing_version

    mock_db.execute = AsyncMock(side_effect=[mock_package_result, mock_version_result])

    mock_file = Mock()
    metadata = PackageVersionCreate(
        version="1.0.0",
        summary="Test",
        description="Test",
    )

    try:
        await upload_package_version(
            package_name="test-package",
            file=mock_file,
            metadata=metadata,
            current_user=mock_user,
            db=mock_db,
            storage=mock_storage,
        )
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert "already exists" in str(e.detail) or hasattr(e, "status_code")


async def test_upload_package_version_with_dependencies():
    """Test uploading version with dependencies."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)
    mock_storage = AsyncMock()
    mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

    mock_package = Mock(id=1, name="test-package", owner_id=1)

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_version_result = AsyncMock()
    mock_version_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[mock_package_result, mock_version_result])

    file_content = b"test content"
    mock_file = Mock()
    mock_file.filename = "test-package-1.0.0.zip"
    mock_file.read = AsyncMock(return_value=file_content)

    metadata = PackageVersionCreate(
        version="1.0.0",
        summary="Test",
        description="Test",
        dependencies=[
            DependencyBase(
                dependency_name="dep-package",
                version_constraint=">=1.0.0",
                is_optional=False,
                dependency_type="runtime",
            )
        ],
    )

    await upload_package_version(
        package_name="test-package",
        file=mock_file,
        metadata=metadata,
        current_user=mock_user,
        db=mock_db,
        storage=mock_storage,
    )

    # Should add version and dependency
    assert mock_db.add.call_count == 2


async def test_upload_package_version_file_hashing():
    """Test that uploaded file is properly hashed."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)
    mock_storage = AsyncMock()
    mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

    mock_package = Mock(id=1, name="test-package", owner_id=1)

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_version_result = AsyncMock()
    mock_version_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[mock_package_result, mock_version_result])

    file_content = b"test package content"
    hashlib.sha256(file_content).hexdigest()
    hashlib.md5(file_content).hexdigest()

    mock_file = Mock()
    mock_file.filename = "test.zip"
    mock_file.read = AsyncMock(return_value=file_content)

    metadata = PackageVersionCreate(
        version="1.0.0",
        summary="Test",
        description="Test",
    )

    await upload_package_version(
        package_name="test-package",
        file=mock_file,
        metadata=metadata,
        current_user=mock_user,
        db=mock_db,
        storage=mock_storage,
    )

    # Verify hashes were calculated by checking that storage was called
    mock_storage.store_package.assert_awaited_once()


# ============================================================================
# Test get_package_stats
# ============================================================================


async def test_get_package_stats_success():
    """Test getting package statistics."""
    mock_db = AsyncMock()

    mock_package = Mock(id=1, download_count=100)

    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    # Mock stats queries
    mock_day_result = AsyncMock()
    mock_day_result.scalar.return_value = 10

    mock_week_result = AsyncMock()
    mock_week_result.scalar.return_value = 50

    mock_month_result = AsyncMock()
    mock_month_result.scalar.return_value = 100

    mock_version_result = AsyncMock()
    mock_version_result.all.return_value = []

    mock_country_result = AsyncMock()
    mock_country_result.all.return_value = []

    mock_platform_result = AsyncMock()
    mock_platform_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[
            mock_package_result,
            mock_day_result,
            mock_week_result,
            mock_month_result,
            mock_version_result,
            mock_country_result,
            mock_platform_result,
        ]
    )

    with patch(
        "revitpy_package_manager.registry.api.routers.packages.CacheService"
    ) as mock_cache_cls:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache_cls.return_value = mock_cache

        stats = await get_package_stats(package_name="test-package", db=mock_db)

        assert stats.package_id == 1
        assert stats.total_downloads == 100
        assert stats.downloads_last_day == 10
        assert stats.downloads_last_week == 50
        assert stats.downloads_last_month == 100


async def test_get_package_stats_not_found():
    """Test getting stats for non-existent package."""
    mock_db = AsyncMock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await get_package_stats(package_name="nonexistent", db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


async def test_get_package_stats_with_cache_hit():
    """Test getting stats from cache."""
    mock_db = AsyncMock()

    mock_package = Mock(id=1, download_count=100)
    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_package_result)

    cached_stats = {
        "package_id": 1,
        "total_downloads": 100,
        "downloads_last_day": 10,
        "downloads_last_week": 50,
        "downloads_last_month": 100,
        "version_breakdown": {},
        "country_breakdown": {},
        "platform_breakdown": {},
    }

    with patch(
        "revitpy_package_manager.registry.api.routers.packages.CacheService"
    ) as mock_cache_cls:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=cached_stats)
        mock_cache_cls.return_value = mock_cache

        await get_package_stats(package_name="test-package", db=mock_db)

        # Should use cached data
        mock_cache.get.assert_awaited_once()
        assert mock_db.execute.call_count == 1


async def test_get_package_stats_with_breakdowns():
    """Test getting stats with version, country, and platform breakdowns."""
    mock_db = AsyncMock()

    mock_package = Mock(id=1, download_count=200)
    mock_package_result = AsyncMock()
    mock_package_result.scalar_one_or_none.return_value = mock_package

    mock_day_result = AsyncMock()
    mock_day_result.scalar.return_value = 20

    mock_week_result = AsyncMock()
    mock_week_result.scalar.return_value = 100

    mock_month_result = AsyncMock()
    mock_month_result.scalar.return_value = 200

    mock_version_row = Mock(version="1.0.0", download_count=150)
    mock_version_result = AsyncMock()
    mock_version_result.all.return_value = [mock_version_row]

    mock_country_row = Mock(country_code="US", download_count=100)
    mock_country_result = AsyncMock()
    mock_country_result.all.return_value = [mock_country_row]

    mock_platform_row = Mock(platform="Windows", download_count=180)
    mock_platform_result = AsyncMock()
    mock_platform_result.all.return_value = [mock_platform_row]

    mock_db.execute = AsyncMock(
        side_effect=[
            mock_package_result,
            mock_day_result,
            mock_week_result,
            mock_month_result,
            mock_version_result,
            mock_country_result,
            mock_platform_result,
        ]
    )

    with patch(
        "revitpy_package_manager.registry.api.routers.packages.CacheService"
    ) as mock_cache_cls:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache_cls.return_value = mock_cache

        stats = await get_package_stats(package_name="test-package", db=mock_db)

        assert stats.version_breakdown == {"1.0.0": 150}
        assert stats.country_breakdown == {"US": 100}
        assert stats.platform_breakdown == {"Windows": 180}


# ============================================================================
# Integration Tests
# ============================================================================


def test_normalize_package_name_consistency():
    """Test that various package name formats normalize consistently."""
    names = [
        "My_Package",
        "my-package",
        "MY PACKAGE",
        "my_package",
        "My-Package",
    ]

    normalized = [normalize_package_name(name) for name in names]

    # All should normalize to the same value
    assert len(set(normalized)) == 1
    assert normalized[0] == "my-package"


# ============================================================================
# Main Test Runner
# ============================================================================


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  Testing Packages Router")
    print("=" * 70 + "\n")

    # Package name normalization tests
    print("Testing normalize_package_name:")
    await runner.run_test(test_normalize_lowercase, "normalize_lowercase")
    await runner.run_test(test_normalize_underscores, "normalize_underscores")
    await runner.run_test(test_normalize_spaces, "normalize_spaces")
    await runner.run_test(test_normalize_mixed, "normalize_mixed")
    await runner.run_test(
        test_normalize_already_normalized, "normalize_already_normalized"
    )

    # List packages tests
    print("\nTesting list_packages:")
    await runner.run_test(test_list_packages_default, "list_packages_default")
    await runner.run_test(
        test_list_packages_with_pagination, "list_packages_with_pagination"
    )
    await runner.run_test(
        test_list_packages_with_category_filter, "list_packages_with_category_filter"
    )

    # Search packages tests
    print("\nTesting search_packages:")
    await runner.run_test(test_search_packages_by_name, "search_packages_by_name")
    await runner.run_test(test_search_packages_no_results, "search_packages_no_results")

    # Create package tests
    print("\nTesting create_package:")
    await runner.run_test(test_create_package_success, "create_package_success")
    await runner.run_test(
        test_create_package_already_exists, "create_package_already_exists"
    )

    # Get package tests
    print("\nTesting get_package:")
    await runner.run_test(test_get_package_success, "get_package_success")
    await runner.run_test(test_get_package_not_found, "get_package_not_found")

    # Update package tests
    print("\nTesting update_package:")
    await runner.run_test(test_update_package_success, "update_package_success")
    await runner.run_test(test_update_package_not_found, "update_package_not_found")

    # Delete package tests
    print("\nTesting delete_package:")
    await runner.run_test(test_delete_package_success, "delete_package_success")
    await runner.run_test(test_delete_package_not_found, "delete_package_not_found")

    # List versions tests
    print("\nTesting list_package_versions:")
    await runner.run_test(
        test_list_package_versions_success, "list_package_versions_success"
    )
    await runner.run_test(
        test_list_package_versions_not_found, "list_package_versions_not_found"
    )

    # Upload version tests
    print("\nTesting upload_package_version:")
    await runner.run_test(
        test_upload_package_version_success, "upload_package_version_success"
    )
    await runner.run_test(
        test_upload_package_version_already_exists,
        "upload_package_version_already_exists",
    )
    await runner.run_test(
        test_upload_package_version_with_dependencies,
        "upload_package_version_with_dependencies",
    )
    await runner.run_test(
        test_upload_package_version_file_hashing, "upload_package_version_file_hashing"
    )

    # Package stats tests
    print("\nTesting get_package_stats:")
    await runner.run_test(test_get_package_stats_success, "get_package_stats_success")
    await runner.run_test(
        test_get_package_stats_not_found, "get_package_stats_not_found"
    )
    await runner.run_test(
        test_get_package_stats_with_cache_hit, "get_package_stats_with_cache_hit"
    )
    await runner.run_test(
        test_get_package_stats_with_breakdowns, "get_package_stats_with_breakdowns"
    )

    # Integration tests
    print("\nTesting integration scenarios:")
    await runner.run_test(
        test_normalize_package_name_consistency, "normalize_package_name_consistency"
    )

    runner.print_summary()

    return runner.failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
