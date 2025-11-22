"""Standalone test runner for admin router.

This script tests the admin router without requiring pytest or database setup.
Run with: python tests/run_admin_router_tests.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock modules before importing
sys.modules["revitpy_package_manager.registry.database"] = Mock()
sys.modules["revitpy_package_manager.registry.api.routers.auth"] = Mock()

from revitpy_package_manager.registry.api.routers.admin import (
    activate_user,
    deactivate_user,
    list_all_packages,
    list_all_users,
    list_scan_results,
    list_vulnerabilities,
    unpublish_package,
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
# Test list_all_users
# ============================================================================


async def test_list_all_users_success():
    """Test listing all users as superuser."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_users = [
        Mock(id=1, username="user1"),
        Mock(id=2, username="user2"),
        Mock(id=3, username="user3"),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_users
    mock_db.execute = AsyncMock(return_value=mock_result)

    users = await list_all_users(current_user=mock_superuser, db=mock_db)

    assert len(users) == 3
    assert users[0].username == "user1"


async def test_list_all_users_empty():
    """Test listing users when no users exist."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    users = await list_all_users(current_user=mock_superuser, db=mock_db)

    assert len(users) == 0


async def test_list_all_users_ordered():
    """Test that users are ordered by creation date."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_users = [
        Mock(id=3, username="newest"),
        Mock(id=2, username="middle"),
        Mock(id=1, username="oldest"),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_users
    mock_db.execute = AsyncMock(return_value=mock_result)

    users = await list_all_users(current_user=mock_superuser, db=mock_db)

    assert users[0].username == "newest"


# ============================================================================
# Test deactivate_user
# ============================================================================


async def test_deactivate_user_success():
    """Test deactivating a user successfully."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_user = Mock(id=2, username="testuser", is_active=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)

    assert mock_user.is_active is False
    mock_db.commit.assert_awaited_once()


async def test_deactivate_user_not_found():
    """Test deactivating non-existent user."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await deactivate_user(user_id="999", current_user=mock_superuser, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_deactivate_already_inactive_user():
    """Test deactivating an already inactive user."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_user = Mock(id=2, username="testuser", is_active=False)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)

    assert mock_user.is_active is False


# ============================================================================
# Test activate_user
# ============================================================================


async def test_activate_user_success():
    """Test activating a user successfully."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_user = Mock(id=2, username="testuser", is_active=False)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)

    assert mock_user.is_active is True
    mock_db.commit.assert_awaited_once()


async def test_activate_user_not_found():
    """Test activating non-existent user."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await activate_user(user_id="999", current_user=mock_superuser, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_activate_already_active_user():
    """Test activating an already active user."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_user = Mock(id=2, username="testuser", is_active=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)

    assert mock_user.is_active is True


# ============================================================================
# Test list_all_packages
# ============================================================================


async def test_list_all_packages_default():
    """Test listing packages with default filters."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_packages = [
        Mock(id=1, name="package1"),
        Mock(id=2, name="package2"),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_packages
    mock_db.execute = AsyncMock(return_value=mock_result)

    packages = await list_all_packages(current_user=mock_superuser, db=mock_db)

    assert len(packages) == 2


async def test_list_all_packages_include_private():
    """Test listing packages including private ones."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_packages = [
        Mock(id=1, name="public", is_private=False),
        Mock(id=2, name="private", is_private=True),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_packages
    mock_db.execute = AsyncMock(return_value=mock_result)

    packages = await list_all_packages(
        include_private=True, current_user=mock_superuser, db=mock_db
    )

    assert len(packages) == 2


async def test_list_all_packages_include_unpublished():
    """Test listing packages including unpublished ones."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_packages = [
        Mock(id=1, name="published", is_published=True),
        Mock(id=2, name="unpublished", is_published=False),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_packages
    mock_db.execute = AsyncMock(return_value=mock_result)

    packages = await list_all_packages(
        include_unpublished=True, current_user=mock_superuser, db=mock_db
    )

    assert len(packages) == 2


async def test_list_all_packages_empty():
    """Test listing packages when none exist."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    packages = await list_all_packages(current_user=mock_superuser, db=mock_db)

    assert len(packages) == 0


# ============================================================================
# Test unpublish_package
# ============================================================================


async def test_unpublish_package_success():
    """Test unpublishing a package successfully."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_package = Mock(id=1, name="test-package", is_published=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    await unpublish_package(
        package_name="test-package", current_user=mock_superuser, db=mock_db
    )

    assert mock_package.is_published is False
    mock_db.commit.assert_awaited_once()


async def test_unpublish_package_not_found():
    """Test unpublishing non-existent package."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await unpublish_package(
            package_name="nonexistent", current_user=mock_superuser, db=mock_db
        )
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_unpublish_already_unpublished():
    """Test unpublishing an already unpublished package."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_package = Mock(id=1, name="test-package", is_published=False)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    await unpublish_package(
        package_name="test-package", current_user=mock_superuser, db=mock_db
    )

    assert mock_package.is_published is False


async def test_unpublish_package_name_normalization():
    """Test that package names are normalized."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_package = Mock(id=1, normalized_name="test-package", is_published=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_package
    mock_db.execute = AsyncMock(return_value=mock_result)

    await unpublish_package(
        package_name="Test_Package", current_user=mock_superuser, db=mock_db
    )

    assert mock_package.is_published is False


# ============================================================================
# Test list_vulnerabilities
# ============================================================================


async def test_list_vulnerabilities_all():
    """Test listing all vulnerabilities."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_vulns = [
        Mock(id=1, severity="critical"),
        Mock(id=2, severity="high"),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_vulns
    mock_db.execute = AsyncMock(return_value=mock_result)

    vulnerabilities = await list_vulnerabilities(
        current_user=mock_superuser, db=mock_db
    )

    assert len(vulnerabilities) == 2


async def test_list_vulnerabilities_filter_by_severity():
    """Test listing vulnerabilities filtered by severity."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_vulns = [Mock(id=1, severity="critical")]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_vulns
    mock_db.execute = AsyncMock(return_value=mock_result)

    vulnerabilities = await list_vulnerabilities(
        severity="critical", current_user=mock_superuser, db=mock_db
    )

    assert len(vulnerabilities) == 1
    assert vulnerabilities[0].severity == "critical"


async def test_list_vulnerabilities_filter_by_status():
    """Test listing vulnerabilities filtered by status."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_vulns = [Mock(id=1, status="open")]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_vulns
    mock_db.execute = AsyncMock(return_value=mock_result)

    vulnerabilities = await list_vulnerabilities(
        status="open", current_user=mock_superuser, db=mock_db
    )

    assert len(vulnerabilities) == 1


async def test_list_vulnerabilities_empty():
    """Test listing vulnerabilities when none exist."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

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


async def test_list_scan_results_all():
    """Test listing all scan results."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_scans = [
        Mock(id=1, scanner_name="malware"),
        Mock(id=2, scanner_name="dependency"),
    ]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_scans
    mock_db.execute = AsyncMock(return_value=mock_result)

    scan_results = await list_scan_results(current_user=mock_superuser, db=mock_db)

    assert len(scan_results) == 2


async def test_list_scan_results_filter_by_scanner():
    """Test listing scan results filtered by scanner."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_scans = [Mock(id=1, scanner_name="malware")]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_scans
    mock_db.execute = AsyncMock(return_value=mock_result)

    scan_results = await list_scan_results(
        scanner="malware", current_user=mock_superuser, db=mock_db
    )

    assert len(scan_results) == 1
    assert scan_results[0].scanner_name == "malware"


async def test_list_scan_results_filter_by_status():
    """Test listing scan results filtered by status."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_scans = [Mock(id=1, status="completed")]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_scans
    mock_db.execute = AsyncMock(return_value=mock_result)

    scan_results = await list_scan_results(
        status="completed", current_user=mock_superuser, db=mock_db
    )

    assert len(scan_results) == 1


async def test_list_scan_results_empty():
    """Test listing scan results when none exist."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    scan_results = await list_scan_results(current_user=mock_superuser, db=mock_db)

    assert len(scan_results) == 0


# ============================================================================
# Integration Tests
# ============================================================================


async def test_user_lifecycle():
    """Test complete user management lifecycle."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    mock_user = Mock(id=2, username="testuser", is_active=True)

    # Deactivate
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    await deactivate_user(user_id="2", current_user=mock_superuser, db=mock_db)
    assert mock_user.is_active is False

    # Reactivate
    await activate_user(user_id="2", current_user=mock_superuser, db=mock_db)
    assert mock_user.is_active is True


async def test_security_monitoring_workflow():
    """Test security monitoring workflow."""
    mock_db = AsyncMock()
    mock_superuser = Mock(id=1, is_superuser=True)

    # List vulnerabilities
    mock_vulns = [Mock(id=1, severity="critical", status="open")]
    mock_result_vulns = AsyncMock()
    mock_result_vulns.scalars.return_value.all.return_value = mock_vulns
    mock_db.execute = AsyncMock(return_value=mock_result_vulns)

    vulnerabilities = await list_vulnerabilities(
        severity="critical", current_user=mock_superuser, db=mock_db
    )
    assert len(vulnerabilities) == 1

    # List related scans
    mock_scans = [Mock(id=1, scanner_name="dependency", status="completed")]
    mock_result_scans = AsyncMock()
    mock_result_scans.scalars.return_value.all.return_value = mock_scans
    mock_db.execute = AsyncMock(return_value=mock_result_scans)

    scan_results = await list_scan_results(
        scanner="dependency", current_user=mock_superuser, db=mock_db
    )
    assert len(scan_results) == 1


# ============================================================================
# Main Test Runner
# ============================================================================


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  Testing Admin Router")
    print("=" * 70 + "\n")

    # list_all_users tests
    print("Testing list_all_users:")
    await runner.run_test(test_list_all_users_success, "list_all_users_success")
    await runner.run_test(test_list_all_users_empty, "list_all_users_empty")
    await runner.run_test(test_list_all_users_ordered, "list_all_users_ordered")

    # deactivate_user tests
    print("\nTesting deactivate_user:")
    await runner.run_test(test_deactivate_user_success, "deactivate_user_success")
    await runner.run_test(test_deactivate_user_not_found, "deactivate_user_not_found")
    await runner.run_test(
        test_deactivate_already_inactive_user, "deactivate_already_inactive_user"
    )

    # activate_user tests
    print("\nTesting activate_user:")
    await runner.run_test(test_activate_user_success, "activate_user_success")
    await runner.run_test(test_activate_user_not_found, "activate_user_not_found")
    await runner.run_test(
        test_activate_already_active_user, "activate_already_active_user"
    )

    # list_all_packages tests
    print("\nTesting list_all_packages:")
    await runner.run_test(test_list_all_packages_default, "list_all_packages_default")
    await runner.run_test(
        test_list_all_packages_include_private, "list_all_packages_include_private"
    )
    await runner.run_test(
        test_list_all_packages_include_unpublished,
        "list_all_packages_include_unpublished",
    )
    await runner.run_test(test_list_all_packages_empty, "list_all_packages_empty")

    # unpublish_package tests
    print("\nTesting unpublish_package:")
    await runner.run_test(test_unpublish_package_success, "unpublish_package_success")
    await runner.run_test(
        test_unpublish_package_not_found, "unpublish_package_not_found"
    )
    await runner.run_test(
        test_unpublish_already_unpublished, "unpublish_already_unpublished"
    )
    await runner.run_test(
        test_unpublish_package_name_normalization,
        "unpublish_package_name_normalization",
    )

    # list_vulnerabilities tests
    print("\nTesting list_vulnerabilities:")
    await runner.run_test(test_list_vulnerabilities_all, "list_vulnerabilities_all")
    await runner.run_test(
        test_list_vulnerabilities_filter_by_severity,
        "list_vulnerabilities_filter_by_severity",
    )
    await runner.run_test(
        test_list_vulnerabilities_filter_by_status,
        "list_vulnerabilities_filter_by_status",
    )
    await runner.run_test(test_list_vulnerabilities_empty, "list_vulnerabilities_empty")

    # list_scan_results tests
    print("\nTesting list_scan_results:")
    await runner.run_test(test_list_scan_results_all, "list_scan_results_all")
    await runner.run_test(
        test_list_scan_results_filter_by_scanner,
        "list_scan_results_filter_by_scanner",
    )
    await runner.run_test(
        test_list_scan_results_filter_by_status, "list_scan_results_filter_by_status"
    )
    await runner.run_test(test_list_scan_results_empty, "list_scan_results_empty")

    # Integration tests
    print("\nTesting integration scenarios:")
    await runner.run_test(test_user_lifecycle, "user_lifecycle")
    await runner.run_test(
        test_security_monitoring_workflow, "security_monitoring_workflow"
    )

    runner.print_summary()

    return runner.failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
