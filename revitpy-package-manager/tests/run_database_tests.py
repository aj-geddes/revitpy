#!/usr/bin/env python3
"""
Standalone test runner for database module tests.

This test file can be run directly without pytest or database setup.

NOTE: Requires asyncpg package to be installed. The database module creates
a real PostgreSQL engine at import time, which requires asyncpg driver.

Install dependencies:
    pip install asyncpg sqlalchemy[asyncio] pydantic-settings

For pytest-based tests (recommended):
    pytest tests/test_database.py

Usage:
    python tests/run_database_tests.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Simple Test Runner
# ============================================================================


class TestRunner:
    """Simple test runner that doesn't require pytest."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, description: str):
        """Decorator to register a test."""

        def decorator(func):
            self.tests.append((description, func))
            return func

        return decorator

    def run_all(self):
        """Run all registered tests."""
        for description, func in self.tests:
            try:
                # Check if test is async
                if asyncio.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
                print(f"  ✓ {description}")
                self.passed += 1
            except AssertionError as e:
                print(f"  ✗ {description}: {e}")
                self.failed += 1
            except Exception as e:
                print(f"  ✗ {description}: {type(e).__name__}: {e}")
                self.failed += 1

    def print_summary(self):
        """Print test results summary."""
        total = self.passed + self.failed
        print(f"\n{'=' * 70}")
        print(f"Tests: {total} total, {self.passed} passed, {self.failed} failed")
        if self.failed == 0:
            print("✓ All tests passed!")
        print(f"{'=' * 70}")


runner = TestRunner()


# ============================================================================
# Mock Fixtures
# ============================================================================


def create_mock_settings():
    """Create mock settings for tests."""
    settings = MagicMock()
    settings.database.url = "postgresql+asyncpg://test:test@localhost/testdb"
    settings.database.echo = False
    settings.database.pool_size = 5
    settings.database.max_overflow = 10
    settings.database.pool_recycle = 3600
    return settings


def create_mock_engine():
    """Create mock async database engine."""
    engine = AsyncMock()
    engine.begin = AsyncMock()
    engine.dispose = AsyncMock()
    return engine


def create_mock_session():
    """Create mock async database session."""
    session = AsyncMock()
    session.close = AsyncMock()
    return session


# ============================================================================
# Module-level Configuration Tests
# ============================================================================


@runner.test("Module: All required attributes are available")
def test_module_imports():
    from revitpy_package_manager.registry import database

    assert hasattr(database, "DATABASE_URL")
    assert hasattr(database, "engine")
    assert hasattr(database, "AsyncSessionLocal")
    assert hasattr(database, "get_db_session")
    assert hasattr(database, "create_tables")
    assert hasattr(database, "drop_tables")
    assert hasattr(database, "DatabaseManager")


# ============================================================================
# get_db_session() Tests
# ============================================================================


@runner.test("get_db_session: Yields a session")
async def test_get_db_session_yields_session():
    from revitpy_package_manager.registry.database import get_db_session

    mock_session = create_mock_session()

    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        async for session in get_db_session():
            assert session == mock_session
            break


@runner.test("get_db_session: Closes session on exit")
async def test_get_db_session_closes_on_exit():
    from revitpy_package_manager.registry.database import get_db_session

    mock_session = create_mock_session()

    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        async for _session in get_db_session():
            pass

        mock_session.close.assert_called_once()


@runner.test("get_db_session: Closes session on exception")
async def test_get_db_session_closes_on_exception():
    from revitpy_package_manager.registry.database import get_db_session

    mock_session = create_mock_session()

    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        try:
            async for _session in get_db_session():
                raise ValueError("Test exception")
        except ValueError:
            pass

        mock_session.close.assert_called_once()


# ============================================================================
# create_tables() Tests
# ============================================================================


@runner.test("create_tables: Calls Base.metadata.create_all")
async def test_create_tables_calls_metadata_create_all():
    from revitpy_package_manager.registry.database import create_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base") as mock_base:
            await create_tables()

            mock_conn.run_sync.assert_called_once()
            call_args = mock_conn.run_sync.call_args[0]
            assert call_args[0] == mock_base.metadata.create_all


@runner.test("create_tables: Uses engine.begin() context")
async def test_create_tables_uses_engine_begin():
    from revitpy_package_manager.registry.database import create_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            await create_tables()

            mock_engine.begin.assert_called_once()


# ============================================================================
# drop_tables() Tests
# ============================================================================


@runner.test("drop_tables: Calls Base.metadata.drop_all")
async def test_drop_tables_calls_metadata_drop_all():
    from revitpy_package_manager.registry.database import drop_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base") as mock_base:
            await drop_tables()

            mock_conn.run_sync.assert_called_once()
            call_args = mock_conn.run_sync.call_args[0]
            assert call_args[0] == mock_base.metadata.drop_all


@runner.test("drop_tables: Uses engine.begin() context")
async def test_drop_tables_uses_engine_begin():
    from revitpy_package_manager.registry.database import drop_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            await drop_tables()

            mock_engine.begin.assert_called_once()


# ============================================================================
# DatabaseManager Initialization Tests
# ============================================================================


@runner.test("DatabaseManager: Initialize with default URL")
def test_database_manager_init_with_default_url():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.DATABASE_URL",
            "postgresql+asyncpg://default/db",
        ):
            with patch(
                "revitpy_package_manager.registry.database.create_async_engine"
            ) as mock_create_engine:
                with patch("revitpy_package_manager.registry.database.sessionmaker"):
                    manager = DatabaseManager()

                    assert manager.database_url == "postgresql+asyncpg://default/db"
                    mock_create_engine.assert_called_once()


@runner.test("DatabaseManager: Initialize with custom URL")
def test_database_manager_init_with_custom_url():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()
    custom_url = "postgresql+asyncpg://custom:pass@host:5432/customdb"

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            with patch("revitpy_package_manager.registry.database.sessionmaker"):
                manager = DatabaseManager(database_url=custom_url)

                assert manager.database_url == custom_url
                call_args = mock_create_engine.call_args[0]
                assert call_args[0] == custom_url


@runner.test("DatabaseManager: Creates session factory")
def test_database_manager_init_creates_session_factory():
    from revitpy_package_manager.registry.database import DatabaseManager
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch("revitpy_package_manager.registry.database.create_async_engine"):
            with patch(
                "revitpy_package_manager.registry.database.sessionmaker"
            ) as mock_sessionmaker:
                manager = DatabaseManager()

                assert manager.session_factory is not None
                mock_sessionmaker.assert_called_once()
                call_kwargs = mock_sessionmaker.call_args[1]
                assert call_kwargs["class_"] == AsyncSession
                assert call_kwargs["expire_on_commit"] is False


# ============================================================================
# DatabaseManager Method Tests
# ============================================================================


@runner.test("DatabaseManager: create_tables method")
async def test_database_manager_create_tables():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            with patch("revitpy_package_manager.registry.database.sessionmaker"):
                with patch(
                    "revitpy_package_manager.registry.database.Base"
                ) as mock_base:
                    manager = DatabaseManager()
                    await manager.create_tables()

                    mock_conn.run_sync.assert_called_once()
                    call_args = mock_conn.run_sync.call_args[0]
                    assert call_args[0] == mock_base.metadata.create_all


@runner.test("DatabaseManager: drop_tables method")
async def test_database_manager_drop_tables():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            with patch("revitpy_package_manager.registry.database.sessionmaker"):
                with patch(
                    "revitpy_package_manager.registry.database.Base"
                ) as mock_base:
                    manager = DatabaseManager()
                    await manager.drop_tables()

                    mock_conn.run_sync.assert_called_once()
                    call_args = mock_conn.run_sync.call_args[0]
                    assert call_args[0] == mock_base.metadata.drop_all


@runner.test("DatabaseManager: get_session method")
async def test_database_manager_get_session():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()
    mock_session = create_mock_session()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch("revitpy_package_manager.registry.database.create_async_engine"):
            with patch(
                "revitpy_package_manager.registry.database.sessionmaker"
            ) as mock_sessionmaker:
                mock_factory = MagicMock()
                mock_factory.return_value = mock_session
                mock_sessionmaker.return_value = mock_factory

                manager = DatabaseManager()
                session = await manager.get_session()

                assert session == mock_session
                mock_factory.assert_called_once()


@runner.test("DatabaseManager: close method")
async def test_database_manager_close():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            with patch("revitpy_package_manager.registry.database.sessionmaker"):
                manager = DatabaseManager()
                await manager.close()

                mock_engine.dispose.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================


@runner.test("DatabaseManager: Full lifecycle integration")
async def test_database_manager_full_lifecycle():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            with patch(
                "revitpy_package_manager.registry.database.sessionmaker"
            ) as mock_sessionmaker:
                with patch("revitpy_package_manager.registry.database.Base"):
                    # Initialize
                    manager = DatabaseManager(
                        database_url="postgresql+asyncpg://test/db"
                    )
                    assert manager.database_url == "postgresql+asyncpg://test/db"

                    # Create tables
                    await manager.create_tables()
                    assert mock_conn.run_sync.call_count == 1

                    # Get session
                    mock_factory = MagicMock()
                    mock_sessionmaker.return_value = mock_factory
                    await manager.get_session()
                    mock_factory.assert_called_once()

                    # Drop tables
                    await manager.drop_tables()
                    assert mock_conn.run_sync.call_count == 2

                    # Close
                    await manager.close()
                    mock_engine.dispose.assert_called_once()


@runner.test("Module functions: Integration test")
async def test_module_level_functions_integration():
    from revitpy_package_manager.registry.database import create_tables, drop_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            # Create tables
            await create_tables()
            assert mock_conn.run_sync.call_count == 1

            # Drop tables
            await drop_tables()
            assert mock_conn.run_sync.call_count == 2


# ============================================================================
# Error Handling Tests
# ============================================================================


@runner.test("get_db_session: Handles session close error")
async def test_get_db_session_handles_session_error():
    from revitpy_package_manager.registry.database import get_db_session

    mock_session = create_mock_session()
    mock_session.close.side_effect = Exception("Session close error")

    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        try:
            async for _session in get_db_session():
                pass
            raise AssertionError("Should have raised exception")
        except Exception as e:
            assert "Session close error" in str(e)


@runner.test("create_tables: Propagates create_all errors")
async def test_create_tables_propagates_errors():
    from revitpy_package_manager.registry.database import create_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.run_sync.side_effect = Exception("Create tables error")
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            try:
                await create_tables()
                raise AssertionError("Should have raised exception")
            except Exception as e:
                assert "Create tables error" in str(e)


@runner.test("drop_tables: Propagates drop_all errors")
async def test_drop_tables_propagates_errors():
    from revitpy_package_manager.registry.database import drop_tables

    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.run_sync.side_effect = Exception("Drop tables error")
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            try:
                await drop_tables()
                raise AssertionError("Should have raised exception")
            except Exception as e:
                assert "Drop tables error" in str(e)


@runner.test("DatabaseManager: close handles disposal errors")
async def test_database_manager_close_handles_errors():
    from revitpy_package_manager.registry.database import DatabaseManager

    mock_settings = create_mock_settings()

    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "revitpy_package_manager.registry.database.create_async_engine"
        ) as mock_create_engine:
            mock_engine = AsyncMock()
            mock_engine.dispose.side_effect = Exception("Disposal error")
            mock_create_engine.return_value = mock_engine

            with patch("revitpy_package_manager.registry.database.sessionmaker"):
                manager = DatabaseManager()

                try:
                    await manager.close()
                    raise AssertionError("Should have raised exception")
                except Exception as e:
                    assert "Disposal error" in str(e)


# ============================================================================
# Main Execution
# ============================================================================


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("Running Database Module Tests")
    print("=" * 70 + "\n")

    runner.run_all()
    runner.print_summary()

    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
