"""
Comprehensive test suite for revitpy_package_manager/registry/models/*.py

Tests cover:
- Base model: common fields, to_dict(), update_from_dict(), __repr__()
- Package models: Package, PackageVersion, PackageDependency
- User models: User, APIKey
- Security models: PackageSignature, VulnerabilityReport, ScanResult, TrustedPublisher
- Download models: DownloadStats, DailyDownloadSummary
- Relationships and cascading deletes
- Constraints and validations
- Model methods and properties
"""

import uuid
from datetime import datetime, timedelta

import pytest
from revitpy_package_manager.registry.models.base import Base
from revitpy_package_manager.registry.models.download import (
    DailyDownloadSummary,
    DownloadStats,
)
from revitpy_package_manager.registry.models.package import (
    Package,
    PackageDependency,
    PackageVersion,
)
from revitpy_package_manager.registry.models.security import (
    PackageSignature,
    ScanResult,
    TrustedPublisher,
    VulnerabilityReport,
)
from revitpy_package_manager.registry.models.user import APIKey, User
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database for testing."""
    # Use SQLite in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()


class TestBaseModel:
    """Tests for Base model common functionality."""

    def test_base_model_has_id(self, db_session):
        """Test that base model includes UUID id field."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        assert isinstance(user.id, uuid.UUID)

    def test_base_model_has_timestamps(self, db_session):
        """Test that base model includes created_at and updated_at."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_to_dict_converts_model_to_dict(self, db_session):
        """Test to_dict() method converts model to dictionary."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hash",
            full_name="Test User",
        )
        db_session.add(user)
        db_session.commit()

        user_dict = user.to_dict()

        assert isinstance(user_dict, dict)
        assert user_dict["username"] == "testuser"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["full_name"] == "Test User"
        assert "id" in user_dict
        assert "created_at" in user_dict

    def test_update_from_dict_updates_fields(self, db_session):
        """Test update_from_dict() updates model fields."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        user.update_from_dict({"full_name": "Updated Name", "bio": "New bio"})

        assert user.full_name == "Updated Name"
        assert user.bio == "New bio"

    def test_update_from_dict_ignores_protected_fields(self, db_session):
        """Test update_from_dict() ignores id, created_at, updated_at."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        original_id = user.id
        original_created = user.created_at

        user.update_from_dict(
            {"id": uuid.uuid4(), "created_at": datetime.now(), "full_name": "New Name"}
        )

        assert user.id == original_id
        assert user.created_at == original_created
        assert user.full_name == "New Name"

    def test_repr_returns_string_representation(self, db_session):
        """Test __repr__() returns readable string."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        repr_str = repr(user)

        assert "User" in repr_str
        assert "testuser" in repr_str


class TestUserModel:
    """Tests for User model."""

    def test_create_user_with_required_fields(self, db_session):
        """Test creating a user with required fields only."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "hash"
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_superuser is False

    def test_create_user_with_profile_fields(self, db_session):
        """Test creating a user with profile information."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hash",
            full_name="Test User",
            bio="A test user",
            website_url="https://example.com",
            company="Test Corp",
            location="Test City",
        )
        db_session.add(user)
        db_session.commit()

        assert user.full_name == "Test User"
        assert user.bio == "A test user"
        assert user.website_url == "https://example.com"
        assert user.company == "Test Corp"
        assert user.location == "Test City"

    def test_username_must_be_unique(self, db_session):
        """Test username uniqueness constraint."""
        user1 = User(
            username="testuser", email="test1@example.com", password_hash="hash"
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            username="testuser", email="test2@example.com", password_hash="hash"
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_email_must_be_unique(self, db_session):
        """Test email uniqueness constraint."""
        user1 = User(
            username="testuser1", email="test@example.com", password_hash="hash"
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            username="testuser2", email="test@example.com", password_hash="hash"
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_packages_relationship(self, db_session):
        """Test user can have multiple packages."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package1 = Package(
            name="package1", normalized_name="package1", owner_id=user.id
        )
        package2 = Package(
            name="package2", normalized_name="package2", owner_id=user.id
        )
        db_session.add_all([package1, package2])
        db_session.commit()

        assert len(user.packages) == 2
        assert package1 in user.packages
        assert package2 in user.packages

    def test_user_api_keys_relationship(self, db_session):
        """Test user can have multiple API keys."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key1 = APIKey(
            user_id=user.id, name="key1", token_hash="hash1", token_prefix="rpk_1234"
        )
        api_key2 = APIKey(
            user_id=user.id, name="key2", token_hash="hash2", token_prefix="rpk_5678"
        )
        db_session.add_all([api_key1, api_key2])
        db_session.commit()

        assert len(user.api_keys) == 2


class TestAPIKeyModel:
    """Tests for APIKey model."""

    def test_create_api_key(self, db_session):
        """Test creating an API key."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="read,write",
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.name == "test-key"
        assert api_key.token_hash == "hash"
        assert api_key.token_prefix == "rpk_1234"
        assert api_key.scopes == "read,write"
        assert api_key.is_active is True
        assert api_key.usage_count == 0

    def test_api_key_is_expired_returns_false_when_no_expiration(self, db_session):
        """Test is_expired property returns False when no expiration set."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id, name="test-key", token_hash="hash", token_prefix="rpk_1234"
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_expired is False

    def test_api_key_is_expired_returns_false_when_not_expired(self, db_session):
        """Test is_expired returns False when expiration is in future."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        future_date = datetime.utcnow() + timedelta(days=30)
        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            expires_at=future_date,
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_expired is False

    def test_api_key_is_expired_returns_true_when_expired(self, db_session):
        """Test is_expired returns True when expiration is in past."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        past_date = datetime.utcnow() - timedelta(days=1)
        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            expires_at=past_date,
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_expired is True

    def test_is_scope_allowed_returns_true_for_allowed_scope(self, db_session):
        """Test is_scope_allowed returns True for allowed scope."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="read,write",
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_scope_allowed("read") is True
        assert api_key.is_scope_allowed("write") is True

    def test_is_scope_allowed_returns_false_for_disallowed_scope(self, db_session):
        """Test is_scope_allowed returns False for disallowed scope."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="read",
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_scope_allowed("write") is False

    def test_is_scope_allowed_returns_true_for_admin_scope(self, db_session):
        """Test admin scope allows all actions."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="admin",
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_scope_allowed("read") is True
        assert api_key.is_scope_allowed("write") is True
        assert api_key.is_scope_allowed("delete") is True

    def test_is_scope_allowed_returns_false_when_inactive(self, db_session):
        """Test is_scope_allowed returns False when key is inactive."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="read",
            is_active=False,
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_scope_allowed("read") is False

    def test_is_scope_allowed_returns_false_when_expired(self, db_session):
        """Test is_scope_allowed returns False when key is expired."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        past_date = datetime.utcnow() - timedelta(days=1)
        api_key = APIKey(
            user_id=user.id,
            name="test-key",
            token_hash="hash",
            token_prefix="rpk_1234",
            scopes="read",
            expires_at=past_date,
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.is_scope_allowed("read") is False


class TestPackageModel:
    """Tests for Package model."""

    def test_create_package(self, db_session):
        """Test creating a package."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package",
            normalized_name="test-package",
            owner_id=user.id,
            summary="A test package",
            description="This is a test package",
            keywords=["test", "example"],
            categories=["utilities"],
        )
        db_session.add(package)
        db_session.commit()

        assert package.name == "test-package"
        assert package.summary == "A test package"
        assert package.keywords == ["test", "example"]
        assert package.is_private is False
        assert package.is_published is True
        assert package.download_count == 0

    def test_package_name_must_be_unique(self, db_session):
        """Test package name uniqueness constraint."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package1 = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package1)
        db_session.commit()

        package2 = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_package_versions_relationship(self, db_session):
        """Test package can have multiple versions."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version1 = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        version2 = PackageVersion(
            package_id=package.id,
            version="1.1.0",
            filename="test-1.1.0.rpyx",
            file_size=2048,
            file_hash_sha256="c" * 64,
            file_hash_md5="d" * 32,
            storage_path="/path/to/file2",
            uploaded_by_id=user.id,
        )
        db_session.add_all([version1, version2])
        db_session.commit()

        assert len(package.versions) == 2

    def test_package_cascades_delete_to_versions(self, db_session):
        """Test deleting package cascades to versions."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        package_id = package.id
        db_session.delete(package)
        db_session.commit()

        # Version should be deleted
        remaining_versions = (
            db_session.query(PackageVersion)
            .filter(PackageVersion.package_id == package_id)
            .all()
        )
        assert len(remaining_versions) == 0


class TestPackageVersionModel:
    """Tests for PackageVersion model."""

    def test_create_package_version(self, db_session):
        """Test creating a package version."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
            python_version=">=3.11",
            supported_revit_versions=["2022", "2023", "2024"],
            extra_metadata={"build": "123"},
        )
        db_session.add(version)
        db_session.commit()

        assert version.version == "1.0.0"
        assert version.python_version == ">=3.11"
        assert version.supported_revit_versions == ["2022", "2023", "2024"]
        assert version.extra_metadata == {"build": "123"}
        assert version.is_prerelease is False
        assert version.is_yanked is False

    def test_package_version_unique_constraint(self, db_session):
        """Test package + version uniqueness constraint."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version1 = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version1)
        db_session.commit()

        version2 = PackageVersion(
            package_id=package.id,
            version="1.0.0",  # Same version
            filename="test-1.0.0-new.rpyx",
            file_size=2048,
            file_hash_sha256="c" * 64,
            file_hash_md5="d" * 32,
            storage_path="/path/to/file2",
            uploaded_by_id=user.id,
        )
        db_session.add(version2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_package_version_dependencies_relationship(self, db_session):
        """Test version can have multiple dependencies."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        dep1 = PackageDependency(
            version_id=version.id,
            dependency_name="dep1",
            version_constraint=">=1.0.0",
        )
        dep2 = PackageDependency(
            version_id=version.id,
            dependency_name="dep2",
            version_constraint="~=2.0",
            is_optional=True,
        )
        db_session.add_all([dep1, dep2])
        db_session.commit()

        assert len(version.dependencies) == 2


class TestPackageDependencyModel:
    """Tests for PackageDependency model."""

    def test_create_package_dependency(self, db_session):
        """Test creating a package dependency."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        dependency = PackageDependency(
            version_id=version.id,
            dependency_name="requests",
            version_constraint=">=2.28.0",
            is_optional=False,
            dependency_type="runtime",
        )
        db_session.add(dependency)
        db_session.commit()

        assert dependency.dependency_name == "requests"
        assert dependency.version_constraint == ">=2.28.0"
        assert dependency.is_optional is False
        assert dependency.dependency_type == "runtime"


class TestPackageSignatureModel:
    """Tests for PackageSignature model."""

    def test_create_package_signature(self, db_session):
        """Test creating a package signature."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        signature = PackageSignature(
            version_id=version.id,
            signer_id=user.id,
            algorithm="RSA",
            signature="base64_encoded_signature",
            public_key_fingerprint="fingerprint",
            signed_at=datetime.utcnow(),
        )
        db_session.add(signature)
        db_session.commit()

        assert signature.algorithm == "RSA"
        assert signature.is_valid is True


class TestVulnerabilityReportModel:
    """Tests for VulnerabilityReport model."""

    def test_create_vulnerability_report(self, db_session):
        """Test creating a vulnerability report."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        vuln = VulnerabilityReport(
            version_id=version.id,
            vulnerability_id="GHSA-1234-5678-90ab",
            cve_id="CVE-2023-12345",
            title="Test Vulnerability",
            description="A test vulnerability",
            severity="high",
            cvss_score=7.5,
            source="GitHub",
            discovered_at=datetime.utcnow(),
            affected_versions=["1.0.0", "1.1.0"],
        )
        db_session.add(vuln)
        db_session.commit()

        assert vuln.vulnerability_id == "GHSA-1234-5678-90ab"
        assert vuln.severity == "high"
        assert vuln.cvss_score == 7.5
        assert vuln.status == "open"


class TestScanResultModel:
    """Tests for ScanResult model."""

    def test_create_scan_result(self, db_session):
        """Test creating a scan result."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        scan = ScanResult(
            version_id=version.id,
            scanner_name="bandit",
            scanner_version="1.7.0",
            scan_type="malware",
            started_at=datetime.utcnow(),
            status="completed",
            passed=True,
            findings_count=5,
            critical_findings=0,
            high_findings=1,
            medium_findings=2,
            low_findings=2,
            results_summary="Scan completed successfully",
        )
        db_session.add(scan)
        db_session.commit()

        assert scan.scanner_name == "bandit"
        assert scan.status == "completed"
        assert scan.passed is True
        assert scan.findings_count == 5


class TestDownloadStatsModel:
    """Tests for DownloadStats model."""

    def test_create_download_stat(self, db_session):
        """Test creating a download stat record."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        download = DownloadStats(
            package_id=package.id,
            version_id=version.id,
            downloaded_at=datetime.utcnow(),
            user_agent="revitpy-cli/1.0.0",
            country_code="US",
            python_version="3.11",
            revit_version="2024",
            platform="Windows",
            file_size=1024,
            download_completed=True,
        )
        db_session.add(download)
        db_session.commit()

        assert download.country_code == "US"
        assert download.python_version == "3.11"
        assert download.download_completed is True


class TestDailyDownloadSummaryModel:
    """Tests for DailyDownloadSummary model."""

    def test_create_daily_summary(self, db_session):
        """Test creating a daily download summary."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        summary = DailyDownloadSummary(
            package_id=package.id,
            date=datetime.utcnow(),
            total_downloads=150,
            unique_ips=100,
            version_breakdown={"1.0.0": 50, "1.1.0": 100},
            country_breakdown={"US": 80, "UK": 30, "DE": 40},
            platform_breakdown={"Windows": 120, "Mac": 30},
        )
        db_session.add(summary)
        db_session.commit()

        assert summary.total_downloads == 150
        assert summary.unique_ips == 100
        assert summary.version_breakdown["1.1.0"] == 100


class TestTrustedPublisherModel:
    """Tests for TrustedPublisher model."""

    def test_create_trusted_publisher(self, db_session):
        """Test creating a trusted publisher."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        publisher = TrustedPublisher(
            user_id=user.id,
            publisher_type="github",
            publisher_name="test-org/test-repo",
            repository_url="https://github.com/test-org/test-repo",
            verification_token="token123",
            is_active=True,
            trust_level="verified",
            allowed_packages=["test-package1", "test-package2"],
        )
        db_session.add(publisher)
        db_session.commit()

        assert publisher.publisher_type == "github"
        assert publisher.trust_level == "verified"
        assert len(publisher.allowed_packages) == 2


class TestCascadingDeletes:
    """Tests for cascading delete behavior."""

    def test_deleting_user_cascades_to_packages(self, db_session):
        """Test deleting user cascades to their packages."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        user_id = user.id
        db_session.delete(user)
        db_session.commit()

        # Package should be deleted
        remaining_packages = (
            db_session.query(Package).filter(Package.owner_id == user_id).all()
        )
        assert len(remaining_packages) == 0

    def test_deleting_user_cascades_to_api_keys(self, db_session):
        """Test deleting user cascades to their API keys."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        api_key = APIKey(
            user_id=user.id, name="test-key", token_hash="hash", token_prefix="rpk_1234"
        )
        db_session.add(api_key)
        db_session.commit()

        user_id = user.id
        db_session.delete(user)
        db_session.commit()

        # API key should be deleted
        remaining_keys = (
            db_session.query(APIKey).filter(APIKey.user_id == user_id).all()
        )
        assert len(remaining_keys) == 0

    def test_deleting_version_cascades_to_dependencies(self, db_session):
        """Test deleting version cascades to its dependencies."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        package = Package(
            name="test-package", normalized_name="test-package", owner_id=user.id
        )
        db_session.add(package)
        db_session.commit()

        version = PackageVersion(
            package_id=package.id,
            version="1.0.0",
            filename="test-1.0.0.rpyx",
            file_size=1024,
            file_hash_sha256="a" * 64,
            file_hash_md5="b" * 32,
            storage_path="/path/to/file",
            uploaded_by_id=user.id,
        )
        db_session.add(version)
        db_session.commit()

        dependency = PackageDependency(
            version_id=version.id,
            dependency_name="dep1",
            version_constraint=">=1.0.0",
        )
        db_session.add(dependency)
        db_session.commit()

        version_id = version.id
        db_session.delete(version)
        db_session.commit()

        # Dependency should be deleted
        remaining_deps = (
            db_session.query(PackageDependency)
            .filter(PackageDependency.version_id == version_id)
            .all()
        )
        assert len(remaining_deps) == 0
