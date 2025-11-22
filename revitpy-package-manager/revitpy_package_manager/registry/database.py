"""Database configuration and connection management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..config import get_settings
from .models.base import Base

# Load database configuration from centralized config
_settings = get_settings()
DATABASE_URL = str(_settings.database.url)

# Create async engine with settings from config
engine = create_async_engine(
    DATABASE_URL,
    echo=_settings.database.echo,
    pool_size=_settings.database.pool_size,
    max_overflow=_settings.database.max_overflow,
    pool_pre_ping=True,
    pool_recycle=_settings.database.pool_recycle,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class DatabaseManager:
    """Database management utilities."""

    def __init__(self, database_url: str | None = None):
        settings = get_settings()
        self.database_url = database_url or DATABASE_URL
        self.engine = create_async_engine(
            self.database_url,
            echo=settings.database.echo,
        )
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        return self.session_factory()

    async def close(self):
        """Close the database engine."""
        await self.engine.dispose()
