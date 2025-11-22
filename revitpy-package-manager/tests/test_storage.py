"""
Comprehensive test suite for revitpy_package_manager/registry/services/storage.py

Tests cover:
- LocalStorageBackend: file operations, path safety, download URLs
- S3StorageBackend: S3 operations, bucket management, presigned URLs
- StorageService: backend selection, package key generation, high-level operations
- Error handling and edge cases
"""

import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from botocore.exceptions import ClientError
from revitpy_package_manager.registry.services.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
    StorageService,
    get_storage_service,
)


class TestStorageBackend:
    """Tests for StorageBackend abstract base class."""

    def test_is_abstract(self):
        """Test that StorageBackend cannot be instantiated."""
        with pytest.raises(TypeError):
            StorageBackend()

    def test_has_required_methods(self):
        """Test that StorageBackend defines required abstract methods."""
        required_methods = [
            "store_file",
            "retrieve_file",
            "delete_file",
            "file_exists",
            "generate_download_url",
        ]
        for method in required_methods:
            assert hasattr(StorageBackend, method)


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend class."""

    @pytest.mark.asyncio
    async def test_init_creates_base_directory(self):
        """Test initialization creates base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "storage"
            backend = LocalStorageBackend(base_path)

            assert backend.base_path == base_path.resolve()
            assert backend.base_path.exists()

    @pytest.mark.asyncio
    async def test_get_file_path_basic(self):
        """Test file path generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            file_path = backend._get_file_path("test/file.txt")

            assert file_path == backend.base_path / "test" / "file.txt"

    @pytest.mark.asyncio
    async def test_get_file_path_prevents_directory_traversal(self):
        """Test path safety against directory traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)

            # Try to escape with ../
            malicious_key = "../../etc/passwd"
            safe_path = backend._get_file_path(malicious_key)

            # Should not escape base directory
            assert (
                backend.base_path in safe_path.parents or safe_path == backend.base_path
            )

    @pytest.mark.asyncio
    async def test_store_file_with_bytes(self):
        """Test storing a file from bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"test content"

            result = await backend.store_file("test.txt", content)

            assert result == "test.txt"
            stored_file = backend.base_path / "test.txt"
            assert stored_file.exists()
            assert stored_file.read_bytes() == content

    @pytest.mark.asyncio
    async def test_store_file_with_binary_io(self):
        """Test storing a file from BinaryIO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"test content from stream"
            file_obj = BytesIO(content)

            result = await backend.store_file("test.txt", file_obj)

            assert result == "test.txt"
            stored_file = backend.base_path / "test.txt"
            assert stored_file.exists()
            assert stored_file.read_bytes() == content

    @pytest.mark.asyncio
    async def test_store_file_creates_subdirectories(self):
        """Test storing a file creates necessary subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"nested content"

            result = await backend.store_file("sub/dir/test.txt", content)

            assert result == "sub/dir/test.txt"
            stored_file = backend.base_path / "sub" / "dir" / "test.txt"
            assert stored_file.exists()

    @pytest.mark.asyncio
    async def test_store_file_with_metadata(self):
        """Test storing a file with metadata (ignored for local storage)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"test content"
            metadata = {"version": "1.0.0", "author": "test"}

            result = await backend.store_file("test.txt", content, metadata)

            assert result == "test.txt"
            assert (backend.base_path / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_retrieve_file_success(self):
        """Test retrieving an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"test content to retrieve"
            await backend.store_file("test.txt", content)

            retrieved = await backend.retrieve_file("test.txt")

            assert retrieved == content

    @pytest.mark.asyncio
    async def test_retrieve_file_not_found(self):
        """Test retrieving a non-existent file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)

            with pytest.raises(FileNotFoundError):
                await backend.retrieve_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test deleting an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            content = b"test content"
            await backend.store_file("test.txt", content)

            result = await backend.delete_file("test.txt")

            assert result is True
            assert not (backend.base_path / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self):
        """Test deleting a non-existent file returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)

            result = await backend.delete_file("nonexistent.txt")

            assert result is False

    @pytest.mark.asyncio
    async def test_file_exists_true(self):
        """Test file_exists returns True for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            await backend.store_file("test.txt", b"content")

            exists = await backend.file_exists("test.txt")

            assert exists is True

    @pytest.mark.asyncio
    async def test_file_exists_false(self):
        """Test file_exists returns False for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)

            exists = await backend.file_exists("nonexistent.txt")

            assert exists is False

    @pytest.mark.asyncio
    async def test_generate_download_url_success(self):
        """Test generating download URL for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            await backend.store_file("test.txt", b"content")

            url = await backend.generate_download_url("test.txt")

            assert url == "/files/test.txt"

    @pytest.mark.asyncio
    async def test_generate_download_url_not_found(self):
        """Test generating download URL for non-existent file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)

            with pytest.raises(FileNotFoundError):
                await backend.generate_download_url("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_generate_download_url_ignores_expiration(self):
        """Test that expiration parameter is ignored for local storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(tmpdir)
            await backend.store_file("test.txt", b"content")

            url = await backend.generate_download_url("test.txt", expiration=7200)

            # URL should be the same regardless of expiration
            assert url == "/files/test.txt"


class TestS3StorageBackend:
    """Tests for S3StorageBackend class."""

    @pytest.mark.asyncio
    async def test_init_creates_s3_client(self):
        """Test initialization creates S3 client."""
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
                mock_boto3.assert_called_once_with(
                    "s3",
                    aws_access_key_id="custom_key",
                    aws_secret_access_key="custom_secret",
                    region_name="us-west-2",
                    endpoint_url=None,
                )

    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_success(self):
        """Test bucket existence check succeeds."""
        with patch(
            "revitpy_package_manager.registry.services.storage.boto3.client"
        ) as mock_boto3:
            with patch(
                "revitpy_package_manager.registry.services.storage.get_settings"
            ) as mock_settings:
                mock_settings.return_value.storage.aws_access_key_id = "test_key"
                mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

                mock_client = Mock()
                mock_client.head_bucket = Mock()  # No exception = bucket exists
                mock_boto3.return_value = mock_client

                S3StorageBackend(bucket_name="existing-bucket")

                mock_client.head_bucket.assert_called_once_with(
                    Bucket="existing-bucket"
                )

    @pytest.mark.asyncio
    async def test_ensure_bucket_creates_missing_bucket(self):
        """Test bucket creation when bucket doesn't exist."""
        with patch(
            "revitpy_package_manager.registry.services.storage.boto3.client"
        ) as mock_boto3:
            with patch(
                "revitpy_package_manager.registry.services.storage.get_settings"
            ) as mock_settings:
                mock_settings.return_value.storage.aws_access_key_id = "test_key"
                mock_settings.return_value.storage.aws_secret_access_key = "test_secret"

                mock_client = Mock()
                # First call (head_bucket) raises 404, second call (create_bucket) succeeds
                mock_client.head_bucket = Mock(
                    side_effect=ClientError({"Error": {"Code": "404"}}, "head_bucket")
                )
                mock_client.create_bucket = Mock()
                mock_boto3.return_value = mock_client

                S3StorageBackend(bucket_name="new-bucket")

                mock_client.create_bucket.assert_called_once_with(Bucket="new-bucket")

    @pytest.mark.asyncio
    async def test_ensure_bucket_raises_on_other_errors(self):
        """Test bucket check raises on non-404 errors."""
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
                    side_effect=ClientError({"Error": {"Code": "403"}}, "head_bucket")
                )
                mock_boto3.return_value = mock_client

                with pytest.raises(RuntimeError, match="Failed to access bucket"):
                    S3StorageBackend(bucket_name="forbidden-bucket")

    @pytest.mark.asyncio
    async def test_store_file_with_bytes(self):
        """Test storing a file to S3 from bytes."""
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
                mock_client.put_object.assert_called_once_with(
                    Bucket="test-bucket",
                    Key="test.txt",
                    Body=content,
                    Metadata={"version": "1.0.0"},
                )

    @pytest.mark.asyncio
    async def test_store_file_with_binary_io(self):
        """Test storing a file to S3 from BinaryIO."""
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

    @pytest.mark.asyncio
    async def test_store_file_error_handling(self):
        """Test store_file handles S3 errors."""
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
                mock_client.put_object = Mock(
                    side_effect=ClientError({"Error": {"Code": "500"}}, "put_object")
                )
                mock_boto3.return_value = mock_client

                backend = S3StorageBackend(bucket_name="test-bucket")

                with pytest.raises(RuntimeError, match="Failed to store file"):
                    await backend.store_file("test.txt", b"content")

    @pytest.mark.asyncio
    async def test_retrieve_file_success(self):
        """Test retrieving a file from S3."""
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
                mock_client.get_object.assert_called_once_with(
                    Bucket="test-bucket", Key="test.txt"
                )

    @pytest.mark.asyncio
    async def test_retrieve_file_not_found(self):
        """Test retrieving non-existent file raises FileNotFoundError."""
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
                    side_effect=ClientError(
                        {"Error": {"Code": "NoSuchKey"}}, "get_object"
                    )
                )
                mock_boto3.return_value = mock_client

                backend = S3StorageBackend(bucket_name="test-bucket")

                with pytest.raises(FileNotFoundError):
                    await backend.retrieve_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test deleting a file from S3."""
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
                mock_client.delete_object.assert_called_once_with(
                    Bucket="test-bucket", Key="test.txt"
                )

    @pytest.mark.asyncio
    async def test_delete_file_error(self):
        """Test delete_file returns False on error."""
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
                mock_client.delete_object = Mock(
                    side_effect=ClientError({"Error": {"Code": "500"}}, "delete_object")
                )
                mock_boto3.return_value = mock_client

                backend = S3StorageBackend(bucket_name="test-bucket")

                result = await backend.delete_file("test.txt")

                assert result is False

    @pytest.mark.asyncio
    async def test_file_exists_true(self):
        """Test file_exists returns True for existing S3 object."""
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

    @pytest.mark.asyncio
    async def test_file_exists_false(self):
        """Test file_exists returns False for non-existent S3 object."""
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

    @pytest.mark.asyncio
    async def test_generate_download_url_success(self):
        """Test generating presigned download URL."""
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
                mock_client.generate_presigned_url.assert_called_once_with(
                    "get_object",
                    Params={"Bucket": "test-bucket", "Key": "test.txt"},
                    ExpiresIn=7200,
                )

    @pytest.mark.asyncio
    async def test_generate_download_url_error(self):
        """Test generate_download_url error handling."""
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
                    side_effect=ClientError(
                        {"Error": {"Code": "500"}}, "generate_presigned_url"
                    )
                )
                mock_boto3.return_value = mock_client

                backend = S3StorageBackend(bucket_name="test-bucket")

                with pytest.raises(
                    RuntimeError, match="Failed to generate download URL"
                ):
                    await backend.generate_download_url("test.txt")


class TestStorageService:
    """Tests for StorageService class."""

    @pytest.mark.asyncio
    async def test_init_with_custom_backend(self):
        """Test initialization with custom backend."""
        mock_backend = Mock(spec=StorageBackend)
        service = StorageService(backend=mock_backend)

        assert service.backend == mock_backend

    @pytest.mark.asyncio
    async def test_init_creates_local_backend_by_default(self):
        """Test initialization creates local backend from config."""
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.type = "local"
            mock_settings.return_value.storage.local_path = "/tmp/test"

            with patch(
                "revitpy_package_manager.registry.services.storage.LocalStorageBackend"
            ) as mock_local:
                StorageService()

                mock_local.assert_called_once_with(base_path="/tmp/test")

    @pytest.mark.asyncio
    async def test_init_creates_s3_backend_from_config(self):
        """Test initialization creates S3 backend from config."""
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.type = "s3"
            mock_settings.return_value.storage.s3_bucket_name = "test-bucket"
            mock_settings.return_value.storage.s3_region = "us-west-1"
            mock_settings.return_value.storage.aws_access_key_id = "key"
            mock_settings.return_value.storage.aws_secret_access_key = "secret"
            mock_settings.return_value.storage.s3_endpoint_url = None

            with patch(
                "revitpy_package_manager.registry.services.storage.S3StorageBackend"
            ) as mock_s3:
                StorageService()

                mock_s3.assert_called_once_with(
                    bucket_name="test-bucket",
                    aws_region="us-west-1",
                    aws_access_key_id="key",
                    aws_secret_access_key="secret",
                    endpoint_url=None,
                )

    @pytest.mark.asyncio
    async def test_init_raises_on_unsupported_storage_type(self):
        """Test initialization raises error for unsupported storage type."""
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.type = "azure"

            with pytest.raises(ValueError, match="Unsupported storage type"):
                StorageService()

    @pytest.mark.asyncio
    async def test_generate_package_key(self):
        """Test package key generation."""
        mock_backend = Mock(spec=StorageBackend)
        service = StorageService(backend=mock_backend)

        with patch(
            "revitpy_package_manager.registry.services.storage.datetime"
        ) as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 10, 28)

            key = service._generate_package_key("Test_Package", "1.0.0", "package.rpyx")

            assert key == "packages/2025/10/test-package/1.0.0/package.rpyx"

    @pytest.mark.asyncio
    async def test_generate_package_key_normalizes_name(self):
        """Test package key generation normalizes package name."""
        mock_backend = Mock(spec=StorageBackend)
        service = StorageService(backend=mock_backend)

        with patch(
            "revitpy_package_manager.registry.services.storage.datetime"
        ) as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 10, 28)

            key = service._generate_package_key("My_Package_NAME", "2.0.0", "file.rpyx")

            assert "my-package-name" in key
            assert key.startswith("packages/2025/10/")

    @pytest.mark.asyncio
    async def test_store_package(self):
        """Test storing a package."""
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
            call_args = mock_backend.store_file.call_args
            assert call_args[0][0] == "packages/2025/10/test/1.0.0/pkg.rpyx"
            assert call_args[0][1] == content
            metadata = call_args[0][2]
            assert metadata["package_name"] == "test-package"
            assert metadata["version"] == "1.0.0"
            assert metadata["filename"] == "pkg.rpyx"
            assert metadata["author"] == "test"
            assert "uploaded_at" in metadata

    @pytest.mark.asyncio
    async def test_retrieve_package(self):
        """Test retrieving a package."""
        mock_backend = Mock(spec=StorageBackend)
        mock_backend.retrieve_file = AsyncMock(return_value=b"package content")
        service = StorageService(backend=mock_backend)

        result = await service.retrieve_package("storage/path/package.rpyx")

        assert result == b"package content"
        mock_backend.retrieve_file.assert_awaited_once_with("storage/path/package.rpyx")

    @pytest.mark.asyncio
    async def test_delete_package(self):
        """Test deleting a package."""
        mock_backend = Mock(spec=StorageBackend)
        mock_backend.delete_file = AsyncMock(return_value=True)
        service = StorageService(backend=mock_backend)

        result = await service.delete_package("storage/path/package.rpyx")

        assert result is True
        mock_backend.delete_file.assert_awaited_once_with("storage/path/package.rpyx")

    @pytest.mark.asyncio
    async def test_package_exists(self):
        """Test checking package existence."""
        mock_backend = Mock(spec=StorageBackend)
        mock_backend.file_exists = AsyncMock(return_value=True)
        service = StorageService(backend=mock_backend)

        result = await service.package_exists("storage/path/package.rpyx")

        assert result is True
        mock_backend.file_exists.assert_awaited_once_with("storage/path/package.rpyx")

    @pytest.mark.asyncio
    async def test_generate_download_url(self):
        """Test generating download URL."""
        mock_backend = Mock(spec=StorageBackend)
        mock_backend.generate_download_url = AsyncMock(
            return_value="https://download.url/package.rpyx"
        )
        service = StorageService(backend=mock_backend)

        result = await service.generate_download_url(
            "storage/path/package.rpyx", expiration=7200
        )

        assert result == "https://download.url/package.rpyx"
        mock_backend.generate_download_url.assert_awaited_once_with(
            "storage/path/package.rpyx", 7200
        )


class TestGetStorageService:
    """Tests for get_storage_service function."""

    @pytest.mark.asyncio
    async def test_get_storage_service_returns_service_instance(self):
        """Test get_storage_service returns StorageService instance."""
        with patch(
            "revitpy_package_manager.registry.services.storage.get_settings"
        ) as mock_settings:
            mock_settings.return_value.storage.type = "local"
            mock_settings.return_value.storage.local_path = "/tmp/test"

            with tempfile.TemporaryDirectory() as tmpdir:
                mock_settings.return_value.storage.local_path = tmpdir

                service = get_storage_service()

                assert isinstance(service, StorageService)
                assert isinstance(service.backend, LocalStorageBackend)


class TestIntegration:
    """Integration tests for storage service."""

    @pytest.mark.asyncio
    async def test_local_storage_complete_workflow(self):
        """Test complete workflow with local storage."""
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

    @pytest.mark.asyncio
    async def test_s3_storage_workflow_with_mocks(self):
        """Test complete workflow with S3 storage (mocked)."""
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
