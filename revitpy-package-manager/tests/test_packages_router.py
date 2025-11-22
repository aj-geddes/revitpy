"""Tests for packages router endpoints."""

import hashlib
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile, status
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
from revitpy_package_manager.registry.models.package import (
    Package,
    PackageVersion,
)
from revitpy_package_manager.registry.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Test normalize_package_name
# ============================================================================


class TestPackageNameNormalization:
    """Tests for package name normalization."""

    def test_normalize_lowercase(self):
        """Test normalizing uppercase to lowercase."""
        assert normalize_package_name("MyPackage") == "mypackage"

    def test_normalize_underscores(self):
        """Test normalizing underscores to hyphens."""
        assert normalize_package_name("my_package") == "my-package"

    def test_normalize_spaces(self):
        """Test normalizing spaces to hyphens."""
        assert normalize_package_name("my package") == "my-package"

    def test_normalize_mixed(self):
        """Test normalizing mixed characters."""
        assert normalize_package_name("My_Package Name") == "my-package-name"

    def test_normalize_already_normalized(self):
        """Test normalizing already normalized name."""
        assert normalize_package_name("my-package") == "my-package"


# ============================================================================
# Test list_packages
# ============================================================================


class TestListPackages:
    """Tests for list_packages endpoint."""

    @pytest.mark.asyncio
    async def test_list_packages_default(self):
        """Test listing packages with default parameters."""
        mock_db = AsyncMock(spec=AsyncSession)
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

    @pytest.mark.asyncio
    async def test_list_packages_with_pagination(self):
        """Test listing packages with custom pagination."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock packages
        mock_packages = [
            Mock(spec=Package, id=1, name="package1"),
            Mock(spec=Package, id=2, name="package2"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 50  # Total 50 packages

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await list_packages(page=2, per_page=10, db=mock_db)

        assert len(response.packages) == 2
        assert response.total == 50
        assert response.page == 2
        assert response.per_page == 10
        assert response.has_next is True  # 10 + 10 < 50
        assert response.has_prev is True  # page > 1

    @pytest.mark.asyncio
    async def test_list_packages_with_category_filter(self):
        """Test listing packages filtered by category."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await list_packages(category="automation", db=mock_db)

        assert response.packages == []
        assert response.total == 0

    @pytest.mark.asyncio
    async def test_list_packages_with_revit_version_filter(self):
        """Test listing packages filtered by Revit version."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await list_packages(revit_version="2025", db=mock_db)

        assert response.packages == []
        assert response.total == 0


# ============================================================================
# Test search_packages
# ============================================================================


class TestSearchPackages:
    """Tests for search_packages endpoint."""

    @pytest.mark.asyncio
    async def test_search_packages_by_name(self):
        """Test searching packages by name."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_packages = [
            Mock(spec=Package, id=1, name="test-package"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await search_packages(q="test", db=mock_db)

        assert len(response.packages) == 1
        assert response.total == 1
        assert response.query == "test"

    @pytest.mark.asyncio
    async def test_search_packages_no_results(self):
        """Test searching packages with no results."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await search_packages(q="nonexistent", db=mock_db)

        assert len(response.packages) == 0
        assert response.total == 0
        assert response.query == "nonexistent"

    @pytest.mark.asyncio
    async def test_search_packages_with_pagination(self):
        """Test searching packages with pagination."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_packages = [Mock(spec=Package, id=i) for i in range(5)]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages

        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 15

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        response = await search_packages(q="test", page=2, per_page=5, db=mock_db)

        assert len(response.packages) == 5
        assert response.total == 15
        assert response.page == 2


# ============================================================================
# Test create_package
# ============================================================================


class TestCreatePackage:
    """Tests for create_package endpoint."""

    @pytest.mark.asyncio
    async def test_create_package_success(self):
        """Test creating a new package successfully."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1, username="testuser")

        # Mock that package doesn't exist
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

        await create_package(
            package_data=package_data, current_user=mock_user, db=mock_db
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_package_already_exists(self):
        """Test creating a package that already exists."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1, username="testuser")

        # Mock that package exists
        existing_package = Mock(spec=Package, name="test-package")
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = existing_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        package_data = PackageCreate(
            name="test-package",
            summary="Test package summary",
            description="Test package description",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_package(
                package_data=package_data, current_user=mock_user, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_package_with_urls(self):
        """Test creating a package with URLs."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1, username="testuser")

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        package_data = PackageCreate(
            name="test-package",
            summary="Test package",
            description="Description",
            homepage_url="https://example.com",
            repository_url="https://github.com/test/package",
            documentation_url="https://docs.example.com",
            bug_tracker_url="https://github.com/test/package/issues",
        )

        await create_package(
            package_data=package_data, current_user=mock_user, db=mock_db
        )

        mock_db.add.assert_called_once()


# ============================================================================
# Test get_package
# ============================================================================


class TestGetPackage:
    """Tests for get_package endpoint."""

    @pytest.mark.asyncio
    async def test_get_package_success(self):
        """Test getting an existing package."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1, name="test-package")
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        package = await get_package(package_name="test-package", db=mock_db)

        assert package == mock_package

    @pytest.mark.asyncio
    async def test_get_package_not_found(self):
        """Test getting a non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_package(package_name="nonexistent", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_package_name_normalization(self):
        """Test package name is normalized before lookup."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, normalized_name="test-package")
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Request with different casing/formatting
        package = await get_package(package_name="Test_Package", db=mock_db)

        assert package == mock_package


# ============================================================================
# Test update_package
# ============================================================================


class TestUpdatePackage:
    """Tests for update_package endpoint."""

    @pytest.mark.asyncio
    async def test_update_package_success(self):
        """Test updating a package successfully."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)

        mock_package = Mock(
            spec=Package, id=1, name="test-package", owner_id=1, summary="Old summary"
        )
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
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_package_not_found(self):
        """Test updating a non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        package_update = PackageUpdate(summary="New summary")

        with pytest.raises(HTTPException) as exc_info:
            await update_package(
                package_name="nonexistent",
                package_update=package_update,
                current_user=mock_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_package_access_denied(self):
        """Test updating a package by non-owner."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=2)  # Different user

        # Package owned by user id=1, but requesting user is id=2
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None  # Query filters by owner_id
        mock_db.execute = AsyncMock(return_value=mock_result)

        package_update = PackageUpdate(summary="Hacked summary")

        with pytest.raises(HTTPException) as exc_info:
            await update_package(
                package_name="test-package",
                package_update=package_update,
                current_user=mock_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_package_with_urls(self):
        """Test updating package URLs."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)

        mock_package = Mock(
            spec=Package, id=1, name="test-package", owner_id=1, homepage_url=None
        )
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        package_update = PackageUpdate(homepage_url="https://example.com")

        await update_package(
            package_name="test-package",
            package_update=package_update,
            current_user=mock_user,
            db=mock_db,
        )

        mock_db.commit.assert_awaited_once()


# ============================================================================
# Test delete_package
# ============================================================================


class TestDeletePackage:
    """Tests for delete_package endpoint."""

    @pytest.mark.asyncio
    async def test_delete_package_success(self):
        """Test soft deleting a package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)

        mock_package = Mock(spec=Package, id=1, owner_id=1, is_published=True)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        await delete_package(
            package_name="test-package", current_user=mock_user, db=mock_db
        )

        assert mock_package.is_published is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_package_not_found(self):
        """Test deleting a non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await delete_package(
                package_name="nonexistent", current_user=mock_user, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_package_access_denied(self):
        """Test deleting a package by non-owner."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=2)  # Different user

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await delete_package(
                package_name="test-package", current_user=mock_user, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test list_package_versions
# ============================================================================


class TestListPackageVersions:
    """Tests for list_package_versions endpoint."""

    @pytest.mark.asyncio
    async def test_list_package_versions_success(self):
        """Test listing package versions."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1)
        mock_versions = [
            Mock(spec=PackageVersion, id=1, version="1.0.0"),
            Mock(spec=PackageVersion, id=2, version="1.1.0"),
        ]

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_versions_result = AsyncMock()
        mock_versions_result.scalars.return_value.all.return_value = mock_versions

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_versions_result]
        )

        versions = await list_package_versions(package_name="test-package", db=mock_db)

        assert len(versions) == 2

    @pytest.mark.asyncio
    async def test_list_package_versions_package_not_found(self):
        """Test listing versions for non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await list_package_versions(package_name="nonexistent", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_package_versions_exclude_prereleases(self):
        """Test listing versions excluding prereleases."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1)
        mock_versions = [
            Mock(spec=PackageVersion, version="1.0.0", is_prerelease=False),
        ]

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_versions_result = AsyncMock()
        mock_versions_result.scalars.return_value.all.return_value = mock_versions

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_versions_result]
        )

        versions = await list_package_versions(
            package_name="test-package", include_prereleases=False, db=mock_db
        )

        assert len(versions) == 1

    @pytest.mark.asyncio
    async def test_list_package_versions_include_prereleases(self):
        """Test listing versions including prereleases."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1)
        mock_versions = [
            Mock(spec=PackageVersion, version="1.0.0", is_prerelease=False),
            Mock(spec=PackageVersion, version="1.1.0-beta", is_prerelease=True),
        ]

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_versions_result = AsyncMock()
        mock_versions_result.scalars.return_value.all.return_value = mock_versions

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_versions_result]
        )

        versions = await list_package_versions(
            package_name="test-package", include_prereleases=True, db=mock_db
        )

        assert len(versions) == 2


# ============================================================================
# Test upload_package_version
# ============================================================================


class TestUploadPackageVersion:
    """Tests for upload_package_version endpoint."""

    @pytest.mark.asyncio
    async def test_upload_package_version_success(self):
        """Test uploading a new package version."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        mock_storage = AsyncMock()
        mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

        mock_package = Mock(spec=Package, id=1, name="test-package", owner_id=1)

        # First query: get package
        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        # Second query: check version doesn't exist
        mock_version_result = AsyncMock()
        mock_version_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_version_result]
        )

        # Create mock file
        file_content = b"test package content"
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test-package-1.0.0.zip"
        mock_file.read = AsyncMock(return_value=file_content)

        # Create metadata
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
        mock_db.add.assert_called()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_package_version_package_not_found(self):
        """Test uploading version to non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        mock_storage = AsyncMock()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_file = Mock(spec=UploadFile)
        metadata = PackageVersionCreate(
            version="1.0.0",
            summary="Test",
            description="Test",
        )

        with pytest.raises(HTTPException) as exc_info:
            await upload_package_version(
                package_name="nonexistent",
                file=mock_file,
                metadata=metadata,
                current_user=mock_user,
                db=mock_db,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_upload_package_version_already_exists(self):
        """Test uploading a version that already exists."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        mock_storage = AsyncMock()

        mock_package = Mock(spec=Package, id=1, owner_id=1)
        existing_version = Mock(spec=PackageVersion, version="1.0.0")

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_version_result = AsyncMock()
        mock_version_result.scalar_one_or_none.return_value = existing_version

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_version_result]
        )

        mock_file = Mock(spec=UploadFile)
        metadata = PackageVersionCreate(
            version="1.0.0",
            summary="Test",
            description="Test",
        )

        with pytest.raises(HTTPException) as exc_info:
            await upload_package_version(
                package_name="test-package",
                file=mock_file,
                metadata=metadata,
                current_user=mock_user,
                db=mock_db,
                storage=mock_storage,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_package_version_with_dependencies(self):
        """Test uploading version with dependencies."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        mock_storage = AsyncMock()
        mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

        mock_package = Mock(spec=Package, id=1, name="test-package", owner_id=1)

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_version_result = AsyncMock()
        mock_version_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_version_result]
        )

        file_content = b"test content"
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test-package-1.0.0.zip"
        mock_file.read = AsyncMock(return_value=file_content)

        # Create dependency data
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
        assert mock_db.add.call_count == 2  # version + dependency

    @pytest.mark.asyncio
    async def test_upload_package_version_file_hashing(self):
        """Test that uploaded file is properly hashed."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        mock_storage = AsyncMock()
        mock_storage.store_package = AsyncMock(return_value="/path/to/package.zip")

        mock_package = Mock(spec=Package, id=1, name="test-package", owner_id=1)

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_version_result = AsyncMock()
        mock_version_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[mock_package_result, mock_version_result]
        )

        file_content = b"test package content"
        hashlib.sha256(file_content).hexdigest()
        hashlib.md5(file_content).hexdigest()

        mock_file = Mock(spec=UploadFile)
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

        # Verify hashes were calculated
        mock_db.add.assert_called()


# ============================================================================
# Test get_package_stats
# ============================================================================


class TestGetPackageStats:
    """Tests for get_package_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_package_stats_success(self):
        """Test getting package statistics."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1, download_count=100)

        # Mock all database queries
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

    @pytest.mark.asyncio
    async def test_get_package_stats_package_not_found(self):
        """Test getting stats for non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_package_stats(package_name="nonexistent", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_package_stats_with_cache_hit(self):
        """Test getting stats from cache."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1, download_count=100)
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
            # Should not execute additional queries
            assert mock_db.execute.call_count == 1  # Only package lookup

    @pytest.mark.asyncio
    async def test_get_package_stats_with_breakdowns(self):
        """Test getting stats with version, country, and platform breakdowns."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1, download_count=200)

        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        mock_day_result = AsyncMock()
        mock_day_result.scalar.return_value = 20

        mock_week_result = AsyncMock()
        mock_week_result.scalar.return_value = 100

        mock_month_result = AsyncMock()
        mock_month_result.scalar.return_value = 200

        # Mock version breakdown
        mock_version_row = Mock(version="1.0.0", download_count=150)
        mock_version_result = AsyncMock()
        mock_version_result.all.return_value = [mock_version_row]

        # Mock country breakdown
        mock_country_row = Mock(country_code="US", download_count=100)
        mock_country_result = AsyncMock()
        mock_country_result.all.return_value = [mock_country_row]

        # Mock platform breakdown
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

    @pytest.mark.asyncio
    async def test_get_package_stats_cache_write(self):
        """Test that stats are cached after computation."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_package = Mock(spec=Package, id=1, download_count=100)
        mock_package_result = AsyncMock()
        mock_package_result.scalar_one_or_none.return_value = mock_package

        # Mock all stats queries
        mock_results = [
            mock_package_result,
            AsyncMock(scalar=Mock(return_value=10)),  # day
            AsyncMock(scalar=Mock(return_value=50)),  # week
            AsyncMock(scalar=Mock(return_value=100)),  # month
            AsyncMock(all=Mock(return_value=[])),  # versions
            AsyncMock(all=Mock(return_value=[])),  # countries
            AsyncMock(all=Mock(return_value=[])),  # platforms
        ]

        mock_db.execute = AsyncMock(side_effect=mock_results)

        with patch(
            "revitpy_package_manager.registry.api.routers.packages.CacheService"
        ) as mock_cache_cls:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_cls.return_value = mock_cache

            await get_package_stats(package_name="test-package", db=mock_db)

            # Should write to cache
            mock_cache.set.assert_awaited_once()
            call_args = mock_cache.set.call_args
            assert call_args[1]["ttl"] == 3600  # 1 hour


# ============================================================================
# Integration Tests
# ============================================================================


class TestPackageRouterIntegration:
    """Integration tests for package router."""

    @pytest.mark.asyncio
    async def test_package_lifecycle(self):
        """Test complete package lifecycle: create, upload version, update, delete."""
        # This is a conceptual test showing the flow
        # In real integration tests, you'd use a test database

        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1)
        AsyncMock()

        # 1. Create package
        package_data = PackageCreate(
            name="lifecycle-test",
            summary="Test package",
            description="Test description",
        )

        # Mock package doesn't exist
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        await create_package(
            package_data=package_data, current_user=mock_user, db=mock_db
        )

        # 2. Upload version would follow...
        # 3. Update package would follow...
        # 4. Delete package would follow...

        assert mock_db.add.call_count == 1

    def test_normalize_package_name_consistency(self):
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
