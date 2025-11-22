#!/usr/bin/env python3
"""
Standalone test runner for database models tests.

IMPORTANT LIMITATION: This standalone runner cannot function properly due to
SQLAlchemy ORM requirements. The models use relationships that require foreign
key constraints, which cannot be configured without existing database tables.

Additionally, the models use PostgreSQL-specific types (ARRAY, JSONB, UUID) that
are not compatible with SQLite's in-memory database.

RECOMMENDATION: Use the pytest test suite for comprehensive model testing:
    pytest tests/test_models.py

The pytest suite properly creates database tables and covers:
- Model instantiation and validation
- Properties and methods (is_expired, is_scope_allowed, etc.)
- Relationships between models
- Cascading deletes
- Constraints and uniqueness

This file is kept for consistency with other test runners but will fail.

Usage:
    pytest tests/test_models.py          # Recommended approach
    python tests/run_models_tests.py     # Will fail due to ORM requirements
"""

import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    VulnerabilityReport,
)
from revitpy_package_manager.registry.models.user import APIKey, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestRunner:
    """Simple test runner for standalone execution."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.engine = None
        self.SessionLocal = None

    def setup_database(self):
        """Set up in-memory database.

        Note: Skips table creation since models use PostgreSQL-specific types.
        Tests focus on model methods and properties without full DB integration.
        """
        self.engine = create_engine("sqlite:///:memory:")
        # Skip creating tables - models use PostgreSQL ARRAY/JSONB types
        # Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def test(self, name: str):
        """Decorator to mark a test function."""

        def decorator(func):
            def wrapper():
                try:
                    func()
                    self.passed += 1
                    print(f"✓ {name}")
                except AssertionError as e:
                    self.failed += 1
                    error_msg = f"✗ {name}: {str(e)}"
                    print(error_msg)
                    self.errors.append(error_msg)
                except Exception as e:
                    self.failed += 1
                    error_msg = f"✗ {name}: {type(e).__name__}: {str(e)}"
                    print(error_msg)
                    self.errors.append(error_msg)

            return wrapper

        return decorator

    def print_summary(self):
        """Print test results summary."""
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  {error}")
        print("=" * 70)


# Create test runner instance
runner = TestRunner()


# ============================================================================
# Base Model Tests (without database persistence)
# ============================================================================


@runner.test("Base: Model can be instantiated")
def test_base_instantiation():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    assert user.username == "testuser"
    assert user.email == "test@example.com"


@runner.test("Base: __repr__() returns string representation")
def test_base_repr():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    # Manually set id for testing
    user.id = uuid.uuid4()
    repr_str = repr(user)
    assert "User" in repr_str
    assert "testuser" in repr_str


@runner.test("Base: to_dict() method exists")
def test_base_to_dict_method():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    assert hasattr(user, "to_dict")
    assert callable(user.to_dict)


@runner.test("Base: update_from_dict() updates fields")
def test_base_update_from_dict():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    user.full_name = "Original Name"

    user.update_from_dict({"full_name": "Updated Name", "bio": "New bio"})
    assert user.full_name == "Updated Name"
    assert user.bio == "New bio"


@runner.test("Base: update_from_dict() ignores protected fields")
def test_base_update_ignores_protected():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    original_id = uuid.uuid4()
    user.id = original_id

    user.update_from_dict({"id": uuid.uuid4(), "full_name": "New Name"})
    assert user.id == original_id  # ID should not change
    assert user.full_name == "New Name"


# ============================================================================
# User Model Tests
# ============================================================================


@runner.test("User: Create user with required fields")
def test_user_create():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    assert user.username == "testuser"
    assert user.is_active is True
    assert user.is_verified is False
    assert user.is_superuser is False


@runner.test("User: Create user with profile fields")
def test_user_with_profile():
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
    assert user.full_name == "Test User"
    assert user.bio == "A test user"
    assert user.website_url == "https://example.com"
    assert user.company == "Test Corp"
    assert user.location == "Test City"


@runner.test("User: Default values are set correctly")
def test_user_defaults():
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    assert user.is_active is True
    assert user.is_verified is False
    assert user.is_superuser is False
    assert user.last_login_at is None
    assert user.email_verified_at is None


# ============================================================================
# APIKey Model Tests
# ============================================================================


@runner.test("APIKey: Create API key")
def test_apikey_create():
    user_id = uuid.uuid4()
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        scopes="read,write",
    )
    assert api_key.name == "test-key"
    assert api_key.token_hash == "hash"
    assert api_key.is_active is True
    assert api_key.usage_count == 0


@runner.test("APIKey: is_expired returns False when no expiration")
def test_apikey_not_expired():
    user_id = uuid.uuid4()
    api_key = APIKey(
        user_id=user_id, name="test-key", token_hash="hash", token_prefix="rpk_1234"
    )
    assert api_key.is_expired is False


@runner.test("APIKey: is_expired returns False when future expiration")
def test_apikey_future_expiration():
    user_id = uuid.uuid4()
    future_date = datetime.utcnow() + timedelta(days=30)
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        expires_at=future_date,
    )
    assert api_key.is_expired is False


@runner.test("APIKey: is_expired returns True when expired")
def test_apikey_expired():
    user_id = uuid.uuid4()
    past_date = datetime.utcnow() - timedelta(days=1)
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        expires_at=past_date,
    )
    assert api_key.is_expired is True


@runner.test("APIKey: is_scope_allowed checks allowed scope")
def test_apikey_scope_allowed():
    user_id = uuid.uuid4()
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        scopes="read,write",
    )
    assert api_key.is_scope_allowed("read") is True
    assert api_key.is_scope_allowed("write") is True
    assert api_key.is_scope_allowed("delete") is False


@runner.test("APIKey: admin scope allows everything")
def test_apikey_admin_scope():
    user_id = uuid.uuid4()
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        scopes="admin",
    )
    assert api_key.is_scope_allowed("read") is True
    assert api_key.is_scope_allowed("write") is True
    assert api_key.is_scope_allowed("delete") is True


@runner.test("APIKey: is_scope_allowed returns False when inactive")
def test_apikey_inactive():
    user_id = uuid.uuid4()
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        scopes="read",
        is_active=False,
    )
    assert api_key.is_scope_allowed("read") is False


@runner.test("APIKey: is_scope_allowed returns False when expired")
def test_apikey_scope_when_expired():
    user_id = uuid.uuid4()
    past_date = datetime.utcnow() - timedelta(days=1)
    api_key = APIKey(
        user_id=user_id,
        name="test-key",
        token_hash="hash",
        token_prefix="rpk_1234",
        scopes="read",
        expires_at=past_date,
    )
    assert api_key.is_scope_allowed("read") is False


# ============================================================================
# Package Model Tests
# ============================================================================


@runner.test("Package: Create package with defaults")
def test_package_create():
    owner_id = uuid.uuid4()
    package = Package(
        name="test-package",
        normalized_name="test-package",
        owner_id=owner_id,
        summary="A test package",
        keywords=["test", "example"],
    )
    assert package.name == "test-package"
    assert package.normalized_name == "test-package"
    assert package.summary == "A test package"
    assert package.is_private is False
    assert package.download_count == 0


@runner.test("Package: Can instantiate with custom values")
def test_package_custom_values():
    owner_id = uuid.uuid4()
    package = Package(
        name="custom-package",
        normalized_name="custom-package",
        owner_id=owner_id,
        summary="Custom package",
        description="A detailed description",
        is_private=True,
        download_count=500,
    )
    assert package.name == "custom-package"
    assert package.is_private is True
    assert package.download_count == 500


# ============================================================================
# PackageVersion Model Tests
# ============================================================================


@runner.test("PackageVersion: Create package version")
def test_version_create():
    package_id = uuid.uuid4()
    user_id = uuid.uuid4()
    version = PackageVersion(
        package_id=package_id,
        version="1.0.0",
        filename="test-1.0.0.rpyx",
        file_size=1024,
        file_hash_sha256="a" * 64,
        file_hash_md5="b" * 32,
        storage_path="/path/to/file",
        uploaded_by_id=user_id,
        supported_revit_versions=["2022", "2023"],
    )
    assert version.version == "1.0.0"
    assert version.filename == "test-1.0.0.rpyx"
    assert version.file_size == 1024
    assert version.is_prerelease is False


@runner.test("PackageVersion: Prerelease detection")
def test_version_prerelease():
    package_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Test prerelease versions
    prerelease_version = PackageVersion(
        package_id=package_id,
        version="1.0.0-beta.1",
        filename="test-1.0.0-beta.1.rpyx",
        file_size=1024,
        file_hash_sha256="a" * 64,
        file_hash_md5="b" * 32,
        storage_path="/path/to/file",
        uploaded_by_id=user_id,
        is_prerelease=True,
    )
    assert prerelease_version.is_prerelease is True


# ============================================================================
# PackageDependency Model Tests
# ============================================================================


@runner.test("PackageDependency: Create dependency")
def test_dependency_create():
    version_id = uuid.uuid4()
    dependency = PackageDependency(
        version_id=version_id,
        dependency_name="requests",
        version_constraint=">=2.28.0",
        is_optional=False,
    )
    assert dependency.dependency_name == "requests"
    assert dependency.version_constraint == ">=2.28.0"
    assert dependency.is_optional is False


@runner.test("PackageDependency: Optional dependency")
def test_dependency_optional():
    version_id = uuid.uuid4()
    dependency = PackageDependency(
        version_id=version_id,
        dependency_name="pytest",
        version_constraint=">=7.0.0",
        is_optional=True,
    )
    assert dependency.is_optional is True


# ============================================================================
# Security Model Tests
# ============================================================================


@runner.test("PackageSignature: Create signature")
def test_signature_create():
    version_id = uuid.uuid4()
    signer_id = uuid.uuid4()
    signature = PackageSignature(
        version_id=version_id,
        signer_id=signer_id,
        algorithm="RSA",
        signature="base64_signature",
        public_key_fingerprint="fingerprint",
        signed_at=datetime.utcnow(),
    )
    assert signature.algorithm == "RSA"
    assert signature.signature == "base64_signature"
    assert signature.is_valid is True


@runner.test("PackageSignature: Invalid signature")
def test_signature_invalid():
    version_id = uuid.uuid4()
    signer_id = uuid.uuid4()
    signature = PackageSignature(
        version_id=version_id,
        signer_id=signer_id,
        algorithm="RSA",
        signature="base64_signature",
        public_key_fingerprint="fingerprint",
        signed_at=datetime.utcnow(),
        is_valid=False,
    )
    assert signature.is_valid is False


@runner.test("VulnerabilityReport: Create vulnerability")
def test_vulnerability_create():
    version_id = uuid.uuid4()
    vuln = VulnerabilityReport(
        version_id=version_id,
        vulnerability_id="GHSA-1234",
        title="Test Vulnerability",
        description="A test vulnerability",
        severity="high",
        source="GitHub",
        discovered_at=datetime.utcnow(),
    )
    assert vuln.vulnerability_id == "GHSA-1234"
    assert vuln.severity == "high"
    assert vuln.status == "open"


@runner.test("VulnerabilityReport: Fixed status")
def test_vulnerability_fixed():
    version_id = uuid.uuid4()
    vuln = VulnerabilityReport(
        version_id=version_id,
        vulnerability_id="GHSA-5678",
        title="Fixed Vulnerability",
        description="A fixed vulnerability",
        severity="medium",
        source="GitHub",
        discovered_at=datetime.utcnow(),
        status="fixed",
    )
    assert vuln.status == "fixed"


@runner.test("ScanResult: Create scan result")
def test_scan_result_create():
    version_id = uuid.uuid4()
    scan = ScanResult(
        version_id=version_id,
        scanner_name="bandit",
        scanner_version="1.7.0",
        scan_type="malware",
        started_at=datetime.utcnow(),
        status="completed",
        results_summary="Scan completed",
    )
    assert scan.scanner_name == "bandit"
    assert scan.scanner_version == "1.7.0"
    assert scan.status == "completed"


@runner.test("ScanResult: Failed scan")
def test_scan_result_failed():
    version_id = uuid.uuid4()
    scan = ScanResult(
        version_id=version_id,
        scanner_name="safety",
        scanner_version="2.0.0",
        scan_type="vulnerability",
        started_at=datetime.utcnow(),
        status="failed",
        results_summary="Scan failed due to timeout",
    )
    assert scan.status == "failed"


# ============================================================================
# Download Model Tests
# ============================================================================


@runner.test("DownloadStats: Create download stat")
def test_download_stat_create():
    package_id = uuid.uuid4()
    version_id = uuid.uuid4()
    download = DownloadStats(
        package_id=package_id,
        version_id=version_id,
        downloaded_at=datetime.utcnow(),
        country_code="US",
        file_size=1024,
    )
    assert download.country_code == "US"
    assert download.file_size == 1024
    assert download.download_completed is True


@runner.test("DownloadStats: Incomplete download")
def test_download_stat_incomplete():
    package_id = uuid.uuid4()
    version_id = uuid.uuid4()
    download = DownloadStats(
        package_id=package_id,
        version_id=version_id,
        downloaded_at=datetime.utcnow(),
        country_code="CA",
        file_size=2048,
        download_completed=False,
    )
    assert download.download_completed is False


@runner.test("DailyDownloadSummary: Create daily summary")
def test_daily_summary_create():
    package_id = uuid.uuid4()
    summary = DailyDownloadSummary(
        package_id=package_id,
        date=datetime.utcnow(),
        total_downloads=150,
        unique_ips=100,
        version_breakdown={"1.0.0": 50, "1.1.0": 100},
    )
    assert summary.total_downloads == 150
    assert summary.unique_ips == 100
    assert summary.version_breakdown["1.1.0"] == 100


# ============================================================================
# Relationship Tests
# ============================================================================
# NOTE: Relationship tests require database persistence with PostgreSQL.
# These tests are covered in the pytest test suite (test_models.py).
# Standalone tests focus on model instantiation and methods.


# ============================================================================
# Main Execution
# ============================================================================


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("Running Database Models Tests")
    print("=" * 70 + "\n")

    runner.setup_database()

    # Get all test functions
    test_functions = [
        obj
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]

    # Run each test
    for test_func in test_functions:
        test_func()

    # Print summary
    runner.print_summary()

    # Return exit code
    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
