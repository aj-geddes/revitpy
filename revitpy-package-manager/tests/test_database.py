"""Tests for database configuration and connection management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from revitpy_package_manager.registry.database import (
    DatabaseManager,
    create_tables,
    drop_tables,
    get_db_session,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_settings():
    """Mock settings for database tests."""
    settings = MagicMock()
    settings.database.url = "postgresql+asyncpg://test:test@localhost/testdb"
    settings.database.echo = False
    settings.database.pool_size = 5
    settings.database.max_overflow = 10
    settings.database.pool_recycle = 3600
    return settings


@pytest.fixture
def mock_engine():
    """Mock async database engine."""
    engine = AsyncMock()
    engine.begin = AsyncMock()
    engine.dispose = AsyncMock()
    return engine


@pytest.fixture
def mock_session():
    """Mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.close = AsyncMock()
    return session


# ============================================================================
# Module-level Configuration Tests
# ============================================================================


def test_module_imports():
    """Test that all necessary imports are available."""
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


@pytest.mark.asyncio
async def test_get_db_session_yields_session(mock_session):
    """Test that get_db_session yields a session."""
    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        # Setup mock session factory
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        # Get session from generator
        async for session in get_db_session():
            assert session == mock_session
            break


@pytest.mark.asyncio
async def test_get_db_session_closes_on_exit(mock_session):
    """Test that get_db_session closes session on exit."""
    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        # Setup mock session factory
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        # Use session in async generator
        async for _session in get_db_session():
            pass

        # Verify session was closed
        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_db_session_closes_on_exception(mock_session):
    """Test that get_db_session closes session even on exception."""
    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        # Setup mock session factory
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        # Simulate exception during session use
        try:
            async for _session in get_db_session():
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify session was still closed
        mock_session.close.assert_called_once()


# ============================================================================
# create_tables() Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_tables_calls_metadata_create_all():
    """Test that create_tables calls Base.metadata.create_all."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base") as mock_base:
            await create_tables()

            # Verify create_all was called via run_sync
            mock_conn.run_sync.assert_called_once()
            call_args = mock_conn.run_sync.call_args[0]
            assert call_args[0] == mock_base.metadata.create_all


@pytest.mark.asyncio
async def test_create_tables_uses_engine_begin():
    """Test that create_tables uses engine.begin() context."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            await create_tables()

            # Verify engine.begin() was called
            mock_engine.begin.assert_called_once()


# ============================================================================
# drop_tables() Tests
# ============================================================================


@pytest.mark.asyncio
async def test_drop_tables_calls_metadata_drop_all():
    """Test that drop_tables calls Base.metadata.drop_all."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base") as mock_base:
            await drop_tables()

            # Verify drop_all was called via run_sync
            mock_conn.run_sync.assert_called_once()
            call_args = mock_conn.run_sync.call_args[0]
            assert call_args[0] == mock_base.metadata.drop_all


@pytest.mark.asyncio
async def test_drop_tables_uses_engine_begin():
    """Test that drop_tables uses engine.begin() context."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            await drop_tables()

            # Verify engine.begin() was called
            mock_engine.begin.assert_called_once()


# ============================================================================
# DatabaseManager Initialization Tests
# ============================================================================


def test_database_manager_init_with_default_url(mock_settings):
    """Test DatabaseManager initialization with default database URL."""
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


def test_database_manager_init_with_custom_url(mock_settings):
    """Test DatabaseManager initialization with custom database URL."""
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
                # Verify engine was created with custom URL
                call_args = mock_create_engine.call_args[0]
                assert call_args[0] == custom_url


def test_database_manager_init_creates_session_factory(mock_settings):
    """Test that DatabaseManager creates session factory."""
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
                # Verify session factory was configured correctly
                call_kwargs = mock_sessionmaker.call_args[1]
                assert call_kwargs["class_"] == AsyncSession
                assert call_kwargs["expire_on_commit"] is False


# ============================================================================
# DatabaseManager Method Tests
# ============================================================================


@pytest.mark.asyncio
async def test_database_manager_create_tables(mock_settings):
    """Test DatabaseManager.create_tables method."""
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

                    # Verify create_all was called
                    mock_conn.run_sync.assert_called_once()
                    call_args = mock_conn.run_sync.call_args[0]
                    assert call_args[0] == mock_base.metadata.create_all


@pytest.mark.asyncio
async def test_database_manager_drop_tables(mock_settings):
    """Test DatabaseManager.drop_tables method."""
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

                    # Verify drop_all was called
                    mock_conn.run_sync.assert_called_once()
                    call_args = mock_conn.run_sync.call_args[0]
                    assert call_args[0] == mock_base.metadata.drop_all


@pytest.mark.asyncio
async def test_database_manager_get_session(mock_settings, mock_session):
    """Test DatabaseManager.get_session method."""
    with patch(
        "revitpy_package_manager.registry.database.get_settings",
        return_value=mock_settings,
    ):
        with patch("revitpy_package_manager.registry.database.create_async_engine"):
            with patch(
                "revitpy_package_manager.registry.database.sessionmaker"
            ) as mock_sessionmaker:
                # Setup mock session factory
                mock_factory = MagicMock()
                mock_factory.return_value = mock_session
                mock_sessionmaker.return_value = mock_factory

                manager = DatabaseManager()
                session = await manager.get_session()

                assert session == mock_session
                mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_database_manager_close(mock_settings):
    """Test DatabaseManager.close method."""
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

                # Verify engine.dispose() was called
                mock_engine.dispose.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_database_manager_full_lifecycle(mock_settings):
    """Test complete DatabaseManager lifecycle."""
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


@pytest.mark.asyncio
async def test_module_level_functions_integration():
    """Test integration between module-level functions."""
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


@pytest.mark.asyncio
async def test_get_db_session_handles_session_error(mock_session):
    """Test that get_db_session handles session errors gracefully."""
    with patch(
        "revitpy_package_manager.registry.database.AsyncSessionLocal"
    ) as mock_session_local:
        # Simulate session error
        mock_session.close.side_effect = Exception("Session close error")
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None

        # Should handle exception during cleanup
        with pytest.raises(Exception, match="Session close error"):
            async for _session in get_db_session():
                pass


@pytest.mark.asyncio
async def test_create_tables_propagates_errors():
    """Test that create_tables propagates errors from create_all."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.run_sync.side_effect = Exception("Create tables error")
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            with pytest.raises(Exception, match="Create tables error"):
                await create_tables()


@pytest.mark.asyncio
async def test_drop_tables_propagates_errors():
    """Test that drop_tables propagates errors from drop_all."""
    with patch("revitpy_package_manager.registry.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.run_sync.side_effect = Exception("Drop tables error")
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        with patch("revitpy_package_manager.registry.database.Base"):
            with pytest.raises(Exception, match="Drop tables error"):
                await drop_tables()


@pytest.mark.asyncio
async def test_database_manager_close_handles_errors(mock_settings):
    """Test that DatabaseManager.close handles disposal errors."""
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

                with pytest.raises(Exception, match="Disposal error"):
                    await manager.close()
