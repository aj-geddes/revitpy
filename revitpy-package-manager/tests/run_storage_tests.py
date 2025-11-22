#!/usr/bin/env python3
"""
Standalone test runner for storage.py service tests.

This script runs tests for the StorageBackend, LocalStorageBackend, S3StorageBackend,
and StorageService classes without requiring pytest or actual AWS/filesystem access.

Usage:
    python tests/run_storage_tests.py
"""

import asyncio
import sys
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock botocore if not installed
try:
    from botocore.exceptions import ClientError
except ImportError:

    class ClientError(Exception):
        """Mock ClientError for testing without botocore."""

        def __init__(self, error_response, operation_name):
            self.response = error_response
            self.operation_name = operation_name
            super().__init__(f"{operation_name}: {error_response}")


from revitpy_package_manager.registry.services.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
    StorageService,
)


class TestRunner:
    """Simple test runner for standalone execution."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name: str):
        """Decorator to mark a test function."""

        def decorator(func):
            async def wrapper():
                try:
                    await func()
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
# LocalStorageBackend Tests
# ============================================================================


@runner.test("LocalStorage: Initialize and create base directory")
async def test_local_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir) / "storage"
        backend = LocalStorageBackend(base_path)

        assert backend.base_path == base_path.resolve()
        assert backend.base_path.exists()


@runner.test("LocalStorage: Generate file path")
async def test_local_get_file_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        file_path = backend._get_file_path("test/file.txt")

        assert file_path == backend.base_path / "test" / "file.txt"


@runner.test("LocalStorage: Path sanitization removes .. characters")
async def test_local_path_safety():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)

        # Test that .. is removed from paths
        # NOTE: Current implementation has a security vulnerability - it removes ".." but doesn't
        # prevent absolute paths. A malicious key like "../../etc/passwd" becomes "//etc/passwd"
        # which is an absolute path that escapes the base directory.
        # This test verifies current behavior, not ideal security.

        # Test with relative path traversal - should remove ..
        key_with_dotdot = "subdir/../file.txt"
        safe_path = backend._get_file_path(key_with_dotdot)
        path_str = str(safe_path)

        # Verify ".." was removed from the path
        assert ".." not in path_str


@runner.test("LocalStorage: Store file from bytes")
async def test_local_store_bytes():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        content = b"test content"

        result = await backend.store_file("test.txt", content)

        assert result == "test.txt"
        stored_file = backend.base_path / "test.txt"
        assert stored_file.exists()
        assert stored_file.read_bytes() == content


@runner.test("LocalStorage: Store file from BinaryIO")
async def test_local_store_binary_io():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        content = b"test content from stream"
        file_obj = BytesIO(content)

        result = await backend.store_file("test.txt", file_obj)

        assert result == "test.txt"
        stored_file = backend.base_path / "test.txt"
        assert stored_file.exists()
        assert stored_file.read_bytes() == content


@runner.test("LocalStorage: Store file creates subdirectories")
async def test_local_store_nested():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        content = b"nested content"

        result = await backend.store_file("sub/dir/test.txt", content)

        assert result == "sub/dir/test.txt"
        stored_file = backend.base_path / "sub" / "dir" / "test.txt"
        assert stored_file.exists()


@runner.test("LocalStorage: Retrieve existing file")
async def test_local_retrieve_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        content = b"test content to retrieve"
        await backend.store_file("test.txt", content)

        retrieved = await backend.retrieve_file("test.txt")

        assert retrieved == content


@runner.test("LocalStorage: Retrieve non-existent file raises error")
async def test_local_retrieve_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)

        try:
            await backend.retrieve_file("nonexistent.txt")
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass


@runner.test("LocalStorage: Delete existing file")
async def test_local_delete_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        content = b"test content"
        await backend.store_file("test.txt", content)

        result = await backend.delete_file("test.txt")

        assert result is True
        assert not (backend.base_path / "test.txt").exists()


@runner.test("LocalStorage: Delete non-existent file returns False")
async def test_local_delete_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)

        result = await backend.delete_file("nonexistent.txt")

        assert result is False


@runner.test("LocalStorage: Check file exists returns True")
async def test_local_exists_true():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        await backend.store_file("test.txt", b"content")

        exists = await backend.file_exists("test.txt")

        assert exists is True


@runner.test("LocalStorage: Check file exists returns False")
async def test_local_exists_false():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)

        exists = await backend.file_exists("nonexistent.txt")

        assert exists is False


@runner.test("LocalStorage: Generate download URL for existing file")
async def test_local_download_url():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        await backend.store_file("test.txt", b"content")

        url = await backend.generate_download_url("test.txt")

        assert url == "/files/test.txt"


@runner.test("LocalStorage: Generate download URL for missing file raises error")
async def test_local_download_url_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)

        try:
            await backend.generate_download_url("nonexistent.txt")
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass


# ============================================================================
# S3StorageBackend Tests
# ============================================================================


@runner.test("S3Storage: Initialize creates S3 client")
async def test_s3_init():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(
                bucket_name="test-bucket",
                aws_access_key_id="custom_key",
                aws_secret_access_key="custom_secret",
                aws_region="us-west-2",
            )

            assert backend.bucket_name == "test-bucket"
            assert backend.s3_client == mock_client


@runner.test("S3Storage: Ensure bucket exists")
async def test_s3_bucket_exists():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_boto3.return_value = mock_client

            S3StorageBackend(bucket_name="existing-bucket")

            mock_client.head_bucket.assert_called_once_with(Bucket="existing-bucket")


@runner.test("S3Storage: Create missing bucket")
async def test_s3_create_bucket():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock(
                side_effect=ClientError({"Error": {"Code": "404"}}, "head_bucket")
            )
            mock_client.create_bucket = Mock()
            mock_boto3.return_value = mock_client

            S3StorageBackend(bucket_name="new-bucket")

            mock_client.create_bucket.assert_called_once_with(Bucket="new-bucket")


@runner.test("S3Storage: Store file from bytes")
async def test_s3_store_bytes():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.put_object = Mock()
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")
            content = b"test content"
            metadata = {"version": "1.0.0"}

            result = await backend.store_file("test.txt", content, metadata)

            assert result == "s3://test-bucket/test.txt"
            mock_client.put_object.assert_called_once()


@runner.test("S3Storage: Store file from BinaryIO")
async def test_s3_store_binary_io():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.upload_fileobj = Mock()
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")
            content = BytesIO(b"stream content")

            result = await backend.store_file("test.txt", content)

            assert result == "s3://test-bucket/test.txt"
            mock_client.upload_fileobj.assert_called_once()


@runner.test("S3Storage: Retrieve file")
async def test_s3_retrieve():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_body = Mock()
            mock_body.read = Mock(return_value=b"retrieved content")

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.get_object = Mock(return_value={"Body": mock_body})
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            result = await backend.retrieve_file("test.txt")

            assert result == b"retrieved content"


@runner.test("S3Storage: Retrieve non-existent file raises error")
async def test_s3_retrieve_not_found():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.get_object = Mock(
                side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
            )
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            try:
                await backend.retrieve_file("nonexistent.txt")
                raise AssertionError("Should have raised FileNotFoundError")
            except FileNotFoundError:
                pass


@runner.test("S3Storage: Delete file")
async def test_s3_delete():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.delete_object = Mock()
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            result = await backend.delete_file("test.txt")

            assert result is True


@runner.test("S3Storage: Check file exists returns True")
async def test_s3_exists_true():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.head_object = Mock()
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            result = await backend.file_exists("test.txt")

            assert result is True


@runner.test("S3Storage: Check file exists returns False")
async def test_s3_exists_false():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.head_object = Mock(
                side_effect=ClientError({"Error": {"Code": "404"}}, "head_object")
            )
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            result = await backend.file_exists("test.txt")

            assert result is False


@runner.test("S3Storage: Generate presigned download URL")
async def test_s3_download_url():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.generate_presigned_url = Mock(
                return_value="https://s3.amazonaws.com/test-bucket/test.txt?signature=abc"
            )
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")

            url = await backend.generate_download_url("test.txt", expiration=7200)

            assert url.startswith("https://s3.amazonaws.com/")


# ============================================================================
# StorageService Tests
# ============================================================================


@runner.test("StorageService: Initialize with custom backend")
async def test_service_custom_backend():
    mock_backend = Mock(spec=StorageBackend)
    service = StorageService(backend=mock_backend)

    assert service.backend == mock_backend


@runner.test("StorageService: Generate package key")
async def test_service_generate_key():
    mock_backend = Mock(spec=StorageBackend)
    service = StorageService(backend=mock_backend)

    with patch(
        "revitpy_package_manager.registry.services.storage.datetime"
    ) as mock_datetime:
        mock_datetime.utcnow.return_value = datetime(2025, 10, 28)

        key = service._generate_package_key("Test_Package", "1.0.0", "package.rpyx")

        assert key == "packages/2025/10/test-package/1.0.0/package.rpyx"


@runner.test("StorageService: Generate package key normalizes name")
async def test_service_key_normalization():
    mock_backend = Mock(spec=StorageBackend)
    service = StorageService(backend=mock_backend)

    with patch(
        "revitpy_package_manager.registry.services.storage.datetime"
    ) as mock_datetime:
        mock_datetime.utcnow.return_value = datetime(2025, 10, 28)

        key = service._generate_package_key("My_Package_NAME", "2.0.0", "file.rpyx")

        assert "my-package-name" in key
        assert key.startswith("packages/2025/10/")


@runner.test("StorageService: Store package")
async def test_service_store_package():
    mock_backend = Mock(spec=StorageBackend)
    mock_backend.store_file = AsyncMock(return_value="storage/path/package.rpyx")
    service = StorageService(backend=mock_backend)

    content = b"package content"
    custom_metadata = {"author": "test"}

    with patch.object(
        service,
        "_generate_package_key",
        return_value="packages/2025/10/test/1.0.0/pkg.rpyx",
    ):
        result = await service.store_package(
            "test-package", "1.0.0", "pkg.rpyx", content, custom_metadata
        )

        assert result == "storage/path/package.rpyx"
        mock_backend.store_file.assert_awaited_once()


@runner.test("StorageService: Retrieve package")
async def test_service_retrieve_package():
    mock_backend = Mock(spec=StorageBackend)
    mock_backend.retrieve_file = AsyncMock(return_value=b"package content")
    service = StorageService(backend=mock_backend)

    result = await service.retrieve_package("storage/path/package.rpyx")

    assert result == b"package content"


@runner.test("StorageService: Delete package")
async def test_service_delete_package():
    mock_backend = Mock(spec=StorageBackend)
    mock_backend.delete_file = AsyncMock(return_value=True)
    service = StorageService(backend=mock_backend)

    result = await service.delete_package("storage/path/package.rpyx")

    assert result is True


@runner.test("StorageService: Check package exists")
async def test_service_package_exists():
    mock_backend = Mock(spec=StorageBackend)
    mock_backend.file_exists = AsyncMock(return_value=True)
    service = StorageService(backend=mock_backend)

    result = await service.package_exists("storage/path/package.rpyx")

    assert result is True


@runner.test("StorageService: Generate download URL")
async def test_service_download_url():
    mock_backend = Mock(spec=StorageBackend)
    mock_backend.generate_download_url = AsyncMock(
        return_value="https://download.url/package.rpyx"
    )
    service = StorageService(backend=mock_backend)

    result = await service.generate_download_url(
        "storage/path/package.rpyx", expiration=7200
    )

    assert result == "https://download.url/package.rpyx"


# ============================================================================
# Integration Tests
# ============================================================================


@runner.test("Integration: Complete local storage workflow")
async def test_integration_local_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(tmpdir)
        service = StorageService(backend=backend)

        # Store package
        content = b"test package content"
        with patch(
            "revitpy_package_manager.registry.services.storage.datetime"
        ) as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 10, 28)

            storage_path = await service.store_package(
                "test-package", "1.0.0", "test.rpyx", content
            )

        # Check existence
        exists = await service.package_exists(storage_path)
        assert exists is True

        # Retrieve package
        retrieved = await service.retrieve_package(storage_path)
        assert retrieved == content

        # Generate download URL
        url = await service.generate_download_url(storage_path)
        assert "/files/" in url

        # Delete package
        deleted = await service.delete_package(storage_path)
        assert deleted is True

        # Verify deletion
        exists_after = await service.package_exists(storage_path)
        assert exists_after is False


@runner.test("Integration: S3 storage workflow with mocks")
async def test_integration_s3_workflow():
    with patch(
        "revitpy_package_manager.registry.services.storage.boto3.client"
    ) as mock_boto3:
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.aws_access_key_id = "test_key"
            mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

            mock_body = Mock()
            mock_body.read = Mock(return_value=b"package content")

            mock_client = Mock()
            mock_client.head_bucket = Mock()
            mock_client.put_object = Mock()
            mock_client.get_object = Mock(return_value={"Body": mock_body})
            mock_client.head_object = Mock()
            mock_client.delete_object = Mock()
            mock_client.generate_presigned_url = Mock(
                return_value="https://presigned.url/file"
            )
            mock_boto3.return_value = mock_client

            backend = S3StorageBackend(bucket_name="test-bucket")
            service = StorageService(backend=backend)

            # Store
            content = b"test content"
            with patch.object(
                service, "_generate_package_key", return_value="packages/test.rpyx"
            ):
                storage_path = await service.store_package(
                    "pkg", "1.0.0", "test.rpyx", content
                )

            # Check existence
            exists = await service.package_exists(storage_path)
            assert exists is True

            # Retrieve
            retrieved = await service.retrieve_package(storage_path)
            assert retrieved == b"package content"

            # Generate URL
            url = await service.generate_download_url(storage_path)
            assert url == "https://presigned.url/file"

            # Delete
            deleted = await service.delete_package(storage_path)
            assert deleted is True


# ============================================================================
# Main Execution
# ============================================================================


async def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("Running Storage Service Tests")
    print("=" * 70 + "\n")

    # Get all test functions
    test_functions = [
        obj
        for name, obj in globals().items()
        if name.startswith("test_") and asyncio.iscoroutinefunction(obj)
    ]

    # Run each test
    for test_func in test_functions:
        await test_func()

    # Print summary
    runner.print_summary()

    # Return exit code
    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
