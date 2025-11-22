"""Standalone test runner for users router.

This script tests the users router without requiring pytest or database setup.
Run with: python tests/run_users_router_tests.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock modules before importing
sys.modules["revitpy_package_manager.registry.database"] = Mock()
sys.modules["revitpy_package_manager.registry.api.routers.auth"] = Mock()

from revitpy_package_manager.registry.api.routers.users import (
    activate_api_key,
    create_api_key,
    deactivate_api_key,
    delete_api_key,
    get_my_profile,
    get_user_profile,
    list_my_api_keys,
    update_my_profile,
)
from revitpy_package_manager.registry.api.schemas import APIKeyCreate, UserUpdate

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
# Test get_my_profile
# ============================================================================


async def test_get_my_profile_success():
    """Test getting current user's profile."""
    mock_user = Mock(id=1, username="testuser", email="test@example.com")

    profile = await get_my_profile(current_user=mock_user)

    assert profile == mock_user


# ============================================================================
# Test update_my_profile
# ============================================================================


async def test_update_my_profile_success():
    """Test updating current user's profile."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, username="testuser", full_name="Old Name", bio="Old bio")

    user_update = UserUpdate(full_name="New Name", bio="New bio")

    await update_my_profile(user_update=user_update, current_user=mock_user, db=mock_db)

    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()


async def test_update_my_profile_partial():
    """Test updating only some profile fields."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, username="testuser", full_name="Old Name", bio="Old bio")

    user_update = UserUpdate(bio="Updated bio only")

    await update_my_profile(user_update=user_update, current_user=mock_user, db=mock_db)

    mock_db.commit.assert_awaited_once()


async def test_update_my_profile_with_website_url():
    """Test updating profile with website URL."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, username="testuser", website_url=None)

    user_update = UserUpdate(website_url="https://example.com")

    await update_my_profile(user_update=user_update, current_user=mock_user, db=mock_db)

    mock_db.commit.assert_awaited_once()


# ============================================================================
# Test get_user_profile
# ============================================================================


async def test_get_user_profile_success():
    """Test getting a user's public profile."""
    mock_db = AsyncMock()

    mock_user = Mock(id=1, username="publicuser")
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    user = await get_user_profile(username="publicuser", db=mock_db)

    assert user == mock_user


async def test_get_user_profile_not_found():
    """Test getting non-existent user's profile."""
    mock_db = AsyncMock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await get_user_profile(username="nonexistent", db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


# ============================================================================
# Test list_my_api_keys
# ============================================================================


async def test_list_my_api_keys_success():
    """Test listing current user's API keys."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_keys = [Mock(id=1, name="Key 1"), Mock(id=2, name="Key 2")]

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = mock_api_keys
    mock_db.execute = AsyncMock(return_value=mock_result)

    api_keys = await list_my_api_keys(current_user=mock_user, db=mock_db)

    assert len(api_keys) == 2


async def test_list_my_api_keys_empty():
    """Test listing API keys when user has none."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    api_keys = await list_my_api_keys(current_user=mock_user, db=mock_db)

    assert len(api_keys) == 0


# ============================================================================
# Test create_api_key
# ============================================================================


async def test_create_api_key_success():
    """Test creating a new API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    api_key_data = APIKeyCreate(
        name="Test Key",
        description="Test API key",
        scopes=["read", "write"],
    )

    with patch(
        "revitpy_package_manager.registry.api.routers.users.get_password_hash"
    ) as mock_hash:
        mock_hash.return_value = "hashed_token"

        await create_api_key(
            api_key_data=api_key_data, current_user=mock_user, db=mock_db
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()


async def test_create_api_key_with_expiration():
    """Test creating API key with expiration date."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    expires_at = datetime.utcnow() + timedelta(days=30)
    api_key_data = APIKeyCreate(
        name="Expiring Key",
        description="Key that expires",
        scopes=["read"],
        expires_at=expires_at,
    )

    with patch(
        "revitpy_package_manager.registry.api.routers.users.get_password_hash"
    ) as mock_hash:
        mock_hash.return_value = "hashed_token"

        await create_api_key(
            api_key_data=api_key_data, current_user=mock_user, db=mock_db
        )

        mock_db.add.assert_called_once()


# ============================================================================
# Test delete_api_key
# ============================================================================


async def test_delete_api_key_success():
    """Test deleting an API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_key = Mock(id=1, user_id=1)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key
    mock_db.execute = AsyncMock(return_value=mock_result)

    await delete_api_key(api_key_id="1", current_user=mock_user, db=mock_db)

    mock_db.delete.assert_awaited_once_with(mock_api_key)
    mock_db.commit.assert_awaited_once()


async def test_delete_api_key_not_found():
    """Test deleting non-existent API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await delete_api_key(api_key_id="999", current_user=mock_user, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_delete_api_key_wrong_user():
    """Test deleting API key that belongs to another user."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await delete_api_key(api_key_id="1", current_user=mock_user, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


# ============================================================================
# Test deactivate_api_key
# ============================================================================


async def test_deactivate_api_key_success():
    """Test deactivating an API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_key = Mock(id=1, user_id=1, is_active=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key
    mock_db.execute = AsyncMock(return_value=mock_result)

    await deactivate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)

    assert mock_api_key.is_active is False
    mock_db.commit.assert_awaited_once()


async def test_deactivate_api_key_not_found():
    """Test deactivating non-existent API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await deactivate_api_key(api_key_id="999", current_user=mock_user, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_deactivate_already_inactive_key():
    """Test deactivating an already inactive key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_key = Mock(id=1, user_id=1, is_active=False)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key
    mock_db.execute = AsyncMock(return_value=mock_result)

    await deactivate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)

    assert mock_api_key.is_active is False


# ============================================================================
# Test activate_api_key
# ============================================================================


async def test_activate_api_key_success():
    """Test activating an API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_key = Mock(id=1, user_id=1, is_active=False)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key
    mock_db.execute = AsyncMock(return_value=mock_result)

    await activate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)

    assert mock_api_key.is_active is True
    mock_db.commit.assert_awaited_once()


async def test_activate_api_key_not_found():
    """Test activating non-existent API key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    try:
        await activate_api_key(api_key_id="999", current_user=mock_user, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 404


async def test_activate_already_active_key():
    """Test activating an already active key."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    mock_api_key = Mock(id=1, user_id=1, is_active=True)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key
    mock_db.execute = AsyncMock(return_value=mock_result)

    await activate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)

    assert mock_api_key.is_active is True


# ============================================================================
# Integration Tests
# ============================================================================


async def test_api_key_lifecycle():
    """Test complete API key lifecycle."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1)

    api_key_data = APIKeyCreate(
        name="Lifecycle Test Key",
        description="Test key lifecycle",
        scopes=["read", "write"],
    )

    with patch(
        "revitpy_package_manager.registry.api.routers.users.get_password_hash"
    ) as mock_hash:
        mock_hash.return_value = "hashed_token"

        # Create
        await create_api_key(
            api_key_data=api_key_data, current_user=mock_user, db=mock_db
        )
        assert mock_db.add.call_count == 1

        # Deactivate
        mock_api_key = Mock(id=1, user_id=1, is_active=True)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        await deactivate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)
        assert mock_api_key.is_active is False

        # Reactivate
        await activate_api_key(api_key_id="1", current_user=mock_user, db=mock_db)
        assert mock_api_key.is_active is True

        # Delete
        await delete_api_key(api_key_id="1", current_user=mock_user, db=mock_db)
        mock_db.delete.assert_awaited()


async def test_profile_update_workflow():
    """Test profile update workflow."""
    mock_db = AsyncMock()
    mock_user = Mock(
        id=1,
        username="testuser",
        full_name="Original Name",
        bio="Original bio",
        location=None,
    )

    # Update full name
    update1 = UserUpdate(full_name="Updated Name")
    await update_my_profile(user_update=update1, current_user=mock_user, db=mock_db)

    # Update bio
    update2 = UserUpdate(bio="Updated bio")
    await update_my_profile(user_update=update2, current_user=mock_user, db=mock_db)

    # Update location
    update3 = UserUpdate(location="New York")
    await update_my_profile(user_update=update3, current_user=mock_user, db=mock_db)

    # Should have committed 3 times
    assert mock_db.commit.await_count == 3


# ============================================================================
# Main Test Runner
# ============================================================================


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  Testing Users Router")
    print("=" * 70 + "\n")

    # get_my_profile tests
    print("Testing get_my_profile:")
    await runner.run_test(test_get_my_profile_success, "get_my_profile_success")

    # update_my_profile tests
    print("\nTesting update_my_profile:")
    await runner.run_test(test_update_my_profile_success, "update_my_profile_success")
    await runner.run_test(test_update_my_profile_partial, "update_my_profile_partial")
    await runner.run_test(
        test_update_my_profile_with_website_url, "update_my_profile_with_website_url"
    )

    # get_user_profile tests
    print("\nTesting get_user_profile:")
    await runner.run_test(test_get_user_profile_success, "get_user_profile_success")
    await runner.run_test(test_get_user_profile_not_found, "get_user_profile_not_found")

    # list_my_api_keys tests
    print("\nTesting list_my_api_keys:")
    await runner.run_test(test_list_my_api_keys_success, "list_my_api_keys_success")
    await runner.run_test(test_list_my_api_keys_empty, "list_my_api_keys_empty")

    # create_api_key tests
    print("\nTesting create_api_key:")
    await runner.run_test(test_create_api_key_success, "create_api_key_success")
    await runner.run_test(
        test_create_api_key_with_expiration, "create_api_key_with_expiration"
    )

    # delete_api_key tests
    print("\nTesting delete_api_key:")
    await runner.run_test(test_delete_api_key_success, "delete_api_key_success")
    await runner.run_test(test_delete_api_key_not_found, "delete_api_key_not_found")
    await runner.run_test(test_delete_api_key_wrong_user, "delete_api_key_wrong_user")

    # deactivate_api_key tests
    print("\nTesting deactivate_api_key:")
    await runner.run_test(test_deactivate_api_key_success, "deactivate_api_key_success")
    await runner.run_test(
        test_deactivate_api_key_not_found, "deactivate_api_key_not_found"
    )
    await runner.run_test(
        test_deactivate_already_inactive_key, "deactivate_already_inactive_key"
    )

    # activate_api_key tests
    print("\nTesting activate_api_key:")
    await runner.run_test(test_activate_api_key_success, "activate_api_key_success")
    await runner.run_test(test_activate_api_key_not_found, "activate_api_key_not_found")
    await runner.run_test(
        test_activate_already_active_key, "activate_already_active_key"
    )

    # Integration tests
    print("\nTesting integration scenarios:")
    await runner.run_test(test_api_key_lifecycle, "api_key_lifecycle")
    await runner.run_test(test_profile_update_workflow, "profile_update_workflow")

    runner.print_summary()

    return runner.failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
