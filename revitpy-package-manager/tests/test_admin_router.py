"""Tests for admin router endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, status
from revitpy_package_manager.registry.api.routers.admin import (
    activate_user,
    deactivate_user,
    list_all_packages,
    list_all_users,
    list_scan_results,
    list_vulnerabilities,
    unpublish_package,
)
from revitpy_package_manager.registry.models.package import Package
from revitpy_package_manager.registry.models.security import (
    ScanResult,
    VulnerabilityReport,
)
from revitpy_package_manager.registry.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Test list_all_users
# ============================================================================


class TestListAllUsers:
    """Tests for list_all_users endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_users_success(self):
        """Test listing all users as superuser."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_users = [
            Mock(spec=User, id=1, username="user1"),
            Mock(spec=User, id=2, username="user2"),
            Mock(spec=User, id=3, username="user3"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_db.execute = AsyncMock(return_value=mock_result)

        users = await list_all_users(current_user=mock_superuser, db=mock_db)

        assert len(users) == 3
        assert users[0].username == "user1"

    @pytest.mark.asyncio
    async def test_list_all_users_empty(self):
        """Test listing users when no users exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        users = await list_all_users(current_user=mock_superuser, db=mock_db)

        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_list_all_users_ordered(self):
        """Test that users are ordered by creation date."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_users = [
            Mock(spec=User, id=3, username="newest"),
            Mock(spec=User, id=2, username="middle"),
            Mock(spec=User, id=1, username="oldest"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_db.execute = AsyncMock(return_value=mock_result)

        users = await list_all_users(current_user=mock_superuser, db=mock_db)

        # Should be ordered newest first
        assert users[0].username == "newest"


# ============================================================================
# Test deactivate_user
# ============================================================================


class TestDeactivateUser:
    """Tests for deactivate_user endpoint."""

    @pytest.mark.asyncio
    async def test_deactivate_user_success(self):
        """Test deactivating a user successfully."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_user = Mock(spec=User, id=2, username="testuser", is_active=True)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)

        assert mock_user.is_active is False
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_user_not_found(self):
        """Test deactivating non-existent user."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await deactivate_user(
                user_id="999", current_user=mock_superuser, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive_user(self):
        """Test deactivating an already inactive user."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_user = Mock(spec=User, id=2, username="testuser", is_active=False)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)

        # Should still set to False
        assert mock_user.is_active is False


# ============================================================================
# Test activate_user
# ============================================================================


class TestActivateUser:
    """Tests for activate_user endpoint."""

    @pytest.mark.asyncio
    async def test_activate_user_success(self):
        """Test activating a user successfully."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_user = Mock(spec=User, id=2, username="testuser", is_active=False)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)

        assert mock_user.is_active is True
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_activate_user_not_found(self):
        """Test activating non-existent user."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await activate_user(user_id="999", current_user=mock_superuser, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_activate_already_active_user(self):
        """Test activating an already active user."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_user = Mock(spec=User, id=2, username="testuser", is_active=True)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)

        # Should still set to True
        assert mock_user.is_active is True


# ============================================================================
# Test list_all_packages
# ============================================================================


class TestListAllPackages:
    """Tests for list_all_packages endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_packages_default(self):
        """Test listing packages with default filters."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_packages = [
            Mock(spec=Package, id=1, name="package1"),
            Mock(spec=Package, id=2, name="package2"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages
        mock_db.execute = AsyncMock(return_value=mock_result)

        packages = await list_all_packages(current_user=mock_superuser, db=mock_db)

        assert len(packages) == 2

    @pytest.mark.asyncio
    async def test_list_all_packages_include_private(self):
        """Test listing packages including private ones."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_packages = [
            Mock(spec=Package, id=1, name="public", is_private=False),
            Mock(spec=Package, id=2, name="private", is_private=True),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages
        mock_db.execute = AsyncMock(return_value=mock_result)

        packages = await list_all_packages(
            include_private=True, current_user=mock_superuser, db=mock_db
        )

        assert len(packages) == 2

    @pytest.mark.asyncio
    async def test_list_all_packages_include_unpublished(self):
        """Test listing packages including unpublished ones."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_packages = [
            Mock(spec=Package, id=1, name="published", is_published=True),
            Mock(spec=Package, id=2, name="unpublished", is_published=False),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages
        mock_db.execute = AsyncMock(return_value=mock_result)

        packages = await list_all_packages(
            include_unpublished=True, current_user=mock_superuser, db=mock_db
        )

        assert len(packages) == 2

    @pytest.mark.asyncio
    async def test_list_all_packages_all_filters(self):
        """Test listing packages with all filters enabled."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_packages = [
            Mock(spec=Package, id=1, name="package1"),
            Mock(spec=Package, id=2, name="package2"),
            Mock(spec=Package, id=3, name="package3"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_packages
        mock_db.execute = AsyncMock(return_value=mock_result)

        packages = await list_all_packages(
            include_private=True,
            include_unpublished=True,
            current_user=mock_superuser,
            db=mock_db,
        )

        assert len(packages) == 3

    @pytest.mark.asyncio
    async def test_list_all_packages_empty(self):
        """Test listing packages when none exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        packages = await list_all_packages(current_user=mock_superuser, db=mock_db)

        assert len(packages) == 0


# ============================================================================
# Test unpublish_package
# ============================================================================


class TestUnpublishPackage:
    """Tests for unpublish_package endpoint."""

    @pytest.mark.asyncio
    async def test_unpublish_package_success(self):
        """Test unpublishing a package successfully."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_package = Mock(spec=Package, id=1, name="test-package", is_published=True)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        await unpublish_package(
            package_name="test-package", current_user=mock_superuser, db=mock_db
        )

        assert mock_package.is_published is False
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unpublish_package_not_found(self):
        """Test unpublishing non-existent package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await unpublish_package(
                package_name="nonexistent", current_user=mock_superuser, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unpublish_already_unpublished(self):
        """Test unpublishing an already unpublished package."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_package = Mock(spec=Package, id=1, name="test-package", is_published=False)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        await unpublish_package(
            package_name="test-package", current_user=mock_superuser, db=mock_db
        )

        # Should still set to False
        assert mock_package.is_published is False

    @pytest.mark.asyncio
    async def test_unpublish_package_name_normalization(self):
        """Test that package names are normalized."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_package = Mock(
            spec=Package, id=1, normalized_name="test-package", is_published=True
        )
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_package
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Request with different formatting
        await unpublish_package(
            package_name="Test_Package", current_user=mock_superuser, db=mock_db
        )

        # Should find and unpublish
        assert mock_package.is_published is False


# ============================================================================
# Test list_vulnerabilities
# ============================================================================


class TestListVulnerabilities:
    """Tests for list_vulnerabilities endpoint."""

    @pytest.mark.asyncio
    async def test_list_vulnerabilities_all(self):
        """Test listing all vulnerabilities."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_vulns = [
            Mock(spec=VulnerabilityReport, id=1, severity="critical"),
            Mock(spec=VulnerabilityReport, id=2, severity="high"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_vulns
        mock_db.execute = AsyncMock(return_value=mock_result)

        vulnerabilities = await list_vulnerabilities(
            current_user=mock_superuser, db=mock_db
        )

        assert len(vulnerabilities) == 2

    @pytest.mark.asyncio
    async def test_list_vulnerabilities_filter_by_severity(self):
        """Test listing vulnerabilities filtered by severity."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_vulns = [Mock(spec=VulnerabilityReport, id=1, severity="critical")]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_vulns
        mock_db.execute = AsyncMock(return_value=mock_result)

        vulnerabilities = await list_vulnerabilities(
            severity="critical", current_user=mock_superuser, db=mock_db
        )

        assert len(vulnerabilities) == 1
        assert vulnerabilities[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_list_vulnerabilities_filter_by_status(self):
        """Test listing vulnerabilities filtered by status."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_vulns = [Mock(spec=VulnerabilityReport, id=1, status="open")]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_vulns
        mock_db.execute = AsyncMock(return_value=mock_result)

        vulnerabilities = await list_vulnerabilities(
            status="open", current_user=mock_superuser, db=mock_db
        )

        assert len(vulnerabilities) == 1

    @pytest.mark.asyncio
    async def test_list_vulnerabilities_filter_both(self):
        """Test listing vulnerabilities with both filters."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_vulns = [
            Mock(spec=VulnerabilityReport, id=1, severity="critical", status="open")
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_vulns
        mock_db.execute = AsyncMock(return_value=mock_result)

        vulnerabilities = await list_vulnerabilities(
            severity="critical", status="open", current_user=mock_superuser, db=mock_db
        )

        assert len(vulnerabilities) == 1

    @pytest.mark.asyncio
    async def test_list_vulnerabilities_empty(self):
        """Test listing vulnerabilities when none exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        vulnerabilities = await list_vulnerabilities(
            current_user=mock_superuser, db=mock_db
        )

        assert len(vulnerabilities) == 0


# ============================================================================
# Test list_scan_results
# ============================================================================


class TestListScanResults:
    """Tests for list_scan_results endpoint."""

    @pytest.mark.asyncio
    async def test_list_scan_results_all(self):
        """Test listing all scan results."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_scans = [
            Mock(spec=ScanResult, id=1, scanner_name="malware"),
            Mock(spec=ScanResult, id=2, scanner_name="dependency"),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_scans
        mock_db.execute = AsyncMock(return_value=mock_result)

        scan_results = await list_scan_results(current_user=mock_superuser, db=mock_db)

        assert len(scan_results) == 2

    @pytest.mark.asyncio
    async def test_list_scan_results_filter_by_scanner(self):
        """Test listing scan results filtered by scanner."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_scans = [Mock(spec=ScanResult, id=1, scanner_name="malware")]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_scans
        mock_db.execute = AsyncMock(return_value=mock_result)

        scan_results = await list_scan_results(
            scanner="malware", current_user=mock_superuser, db=mock_db
        )

        assert len(scan_results) == 1
        assert scan_results[0].scanner_name == "malware"

    @pytest.mark.asyncio
    async def test_list_scan_results_filter_by_status(self):
        """Test listing scan results filtered by status."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_scans = [Mock(spec=ScanResult, id=1, status="completed")]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_scans
        mock_db.execute = AsyncMock(return_value=mock_result)

        scan_results = await list_scan_results(
            status="completed", current_user=mock_superuser, db=mock_db
        )

        assert len(scan_results) == 1

    @pytest.mark.asyncio
    async def test_list_scan_results_filter_both(self):
        """Test listing scan results with both filters."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_scans = [
            Mock(spec=ScanResult, id=1, scanner_name="malware", status="completed")
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_scans
        mock_db.execute = AsyncMock(return_value=mock_result)

        scan_results = await list_scan_results(
            scanner="malware",
            status="completed",
            current_user=mock_superuser,
            db=mock_db,
        )

        assert len(scan_results) == 1

    @pytest.mark.asyncio
    async def test_list_scan_results_empty(self):
        """Test listing scan results when none exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        scan_results = await list_scan_results(current_user=mock_superuser, db=mock_db)

        assert len(scan_results) == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestAdminIntegration:
    """Integration tests for admin endpoints."""

    @pytest.mark.asyncio
    async def test_user_lifecycle(self):
        """Test complete user management lifecycle."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        # Create a test user
        mock_user = Mock(spec=User, id=2, username="testuser", is_active=True)

        # Deactivate
        mock_result_deactivate = AsyncMock()
        mock_result_deactivate.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result_deactivate)

        await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)
        assert mock_user.is_active is False

        # Reactivate
        mock_result_activate = AsyncMock()
        mock_result_activate.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result_activate)

        await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)
        assert mock_user.is_active is True

    @pytest.mark.asyncio
    async def test_security_monitoring_workflow(self):
        """Test security monitoring workflow."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_superuser = Mock(spec=User, id=1, is_superuser=True)

        # List vulnerabilities
        mock_vulns = [
            Mock(spec=VulnerabilityReport, id=1, severity="critical", status="open")
        ]
        mock_result_vulns = AsyncMock()
        mock_result_vulns.scalars.return_value.all.return_value = mock_vulns
        mock_db.execute = AsyncMock(return_value=mock_result_vulns)

        vulnerabilities = await list_vulnerabilities(
            severity="critical", current_user=mock_superuser, db=mock_db
        )
        assert len(vulnerabilities) == 1

        # List related scans
        mock_scans = [
            Mock(spec=ScanResult, id=1, scanner_name="dependency", status="completed")
        ]
        mock_result_scans = AsyncMock()
        mock_result_scans.scalars.return_value.all.return_value = mock_scans
        mock_db.execute = AsyncMock(return_value=mock_result_scans)

        scan_results = await list_scan_results(
            scanner="dependency", current_user=mock_superuser, db=mock_db
        )
        assert len(scan_results) == 1
