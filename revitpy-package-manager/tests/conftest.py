"""Pytest configuration and fixtures for the RevitPy package manager tests."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from revitpy_package_manager.registry.api.main import create_app
from revitpy_package_manager.registry.database import get_db_session
from revitpy_package_manager.registry.models.base import Base
from revitpy_package_manager.registry.models.user import User
from revitpy_package_manager.registry.models.package import Package, PackageVersion
from revitpy_package_manager.registry.services.storage import StorageService, LocalStorageBackend


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db_engine():
    """Create a test database engine."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine):
    """Create a test database session."""
    AsyncSessionLocal = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def test_storage_dir():
    """Create a temporary directory for test file storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_storage_service(test_storage_dir):
    """Create a test storage service."""
    backend = LocalStorageBackend(test_storage_dir)
    return StorageService(backend)


@pytest.fixture
def test_app(test_db_session, test_storage_service):
    """Create a test FastAPI application."""
    app = create_app()
    
    # Override dependencies
    async def override_get_db():
        yield test_db_session
    
    def override_get_storage():
        return test_storage_service
    
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[StorageService] = override_get_storage
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def test_user(test_db_session):
    """Create a test user."""
    from revitpy_package_manager.registry.api.routers.auth import get_password_hash
    
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        full_name="Test User",
        is_active=True
    )
    
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_package(test_db_session, test_user):
    """Create a test package."""
    package = Package(
        name="test-package",
        normalized_name="test-package",
        summary="A test package",
        description="This is a test package for testing purposes",
        owner_id=test_user.id,
        is_published=True
    )
    
    test_db_session.add(package)
    await test_db_session.commit()
    await test_db_session.refresh(package)
    
    return package


@pytest_asyncio.fixture
async def test_package_version(test_db_session, test_package, test_user):
    """Create a test package version."""
    version = PackageVersion(
        package_id=test_package.id,
        version="1.0.0",
        summary="Test package version",
        description="Test version description",
        python_version=">=3.11",
        supported_revit_versions=["2024", "2025"],
        filename="test-package-1.0.0.tar.gz",
        file_size=1024,
        file_hash_sha256="a" * 64,
        file_hash_md5="b" * 32,
        storage_path="test/path/test-package-1.0.0.tar.gz",
        uploaded_by_id=test_user.id
    )
    
    test_db_session.add(version)
    await test_db_session.commit()
    await test_db_session.refresh(version)
    
    return version


@pytest.fixture
def test_package_file(test_storage_dir):
    """Create a test package file."""
    package_content = b"This is a test package file content"
    package_file = test_storage_dir / "test-package-1.0.0.tar.gz"
    package_file.write_bytes(package_content)
    return package_file


@pytest.fixture
def auth_headers(test_client, test_user):
    """Get authentication headers for API requests."""
    login_response = test_client.post(
        "/api/v1/auth/login",
        json={
            "username": test_user.username,
            "password": "testpassword"
        }
    )
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def mock_package_data():
    """Mock package data for testing."""
    return {
        "name": "mock-package",
        "summary": "A mock package for testing",
        "description": "This is a mock package used in tests",
        "keywords": ["test", "mock", "revitpy"],
        "categories": ["utilities"],
        "homepage_url": "https://example.com",
        "repository_url": "https://github.com/example/mock-package",
    }


@pytest.fixture
def mock_version_data():
    """Mock package version data for testing."""
    return {
        "version": "2.0.0",
        "summary": "Mock version 2.0.0",
        "description": "This is version 2.0.0 of the mock package",
        "python_version": ">=3.11",
        "supported_revit_versions": ["2024", "2025"],
        "author": "Test Author",
        "author_email": "author@example.com",
        "license": "MIT",
        "dependencies": [
            {
                "dependency_name": "requests",
                "version_constraint": ">=2.25.0",
                "is_optional": False,
                "dependency_type": "runtime"
            }
        ]
    }


class MockAsyncSession:
    """Mock async session for testing without database."""
    
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self._objects = []
    
    def add(self, obj):
        self._objects.append(obj)
    
    async def commit(self):
        self.committed = True
    
    async def rollback(self):
        self.rolled_back = True
    
    async def close(self):
        self.closed = True
    
    async def refresh(self, obj):
        pass
    
    async def execute(self, query):
        # Mock query execution
        class MockResult:
            def scalar_one_or_none(self):
                return None
            
            def scalars(self):
                class MockScalars:
                    def all(self):
                        return []
                return MockScalars()
        
        return MockResult()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MockAsyncSession()


# Test data factories
class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create(
        username: str = "testuser",
        email: str = "test@example.com",
        password: str = "testpassword",
        **kwargs
    ) -> User:
        from revitpy_package_manager.registry.api.routers.auth import get_password_hash
        
        return User(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            is_active=True,
            **kwargs
        )


class PackageFactory:
    """Factory for creating test packages."""
    
    @staticmethod
    def create(
        name: str = "test-package",
        owner_id: str = None,
        **kwargs
    ) -> Package:
        return Package(
            name=name,
            normalized_name=name.lower().replace("_", "-"),
            summary="A test package",
            description="This is a test package",
            owner_id=owner_id,
            is_published=True,
            **kwargs
        )


class PackageVersionFactory:
    """Factory for creating test package versions."""
    
    @staticmethod
    def create(
        package_id: str = None,
        version: str = "1.0.0",
        uploaded_by_id: str = None,
        **kwargs
    ) -> PackageVersion:
        return PackageVersion(
            package_id=package_id,
            version=version,
            summary="Test version",
            python_version=">=3.11",
            supported_revit_versions=["2024", "2025"],
            filename=f"test-package-{version}.tar.gz",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path=f"test/test-package-{version}.tar.gz",
            uploaded_by_id=uploaded_by_id,
            **kwargs
        )


# Pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Skip tests if dependencies are not available
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip markers."""
    skip_integration = pytest.mark.skip(reason="Integration test dependencies not available")
    
    for item in items:
        if "integration" in item.keywords:
            # Skip integration tests if test database is not configured
            if not os.getenv("TEST_DATABASE_URL"):
                item.add_marker(skip_integration)