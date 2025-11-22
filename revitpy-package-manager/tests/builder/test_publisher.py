"""Comprehensive tests for package publishing functionality."""

import hashlib
import tarfile
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest
import toml
from click.testing import CliRunner
from revitpy_package_manager.builder.cli.main import (
    _extract_package_metadata,
    _upload_package_to_registry,
    publish,
)


@pytest.fixture
def sample_package_tarball(tmp_path):
    """Create a sample .tar.gz package file for testing."""
    package_dir = tmp_path / "sample-package-1.0.0"
    package_dir.mkdir()

    # Create a sample pyproject.toml
    pyproject_content = {
        "project": {
            "name": "sample-package",
            "version": "1.0.0",
            "description": "A sample package for testing",
            "authors": [{"name": "Test Author", "email": "test@example.com"}],
            "license": {"text": "MIT"},
            "requires-python": ">=3.11",
            "dependencies": ["revitpy>=2.0.0"],
        }
    }

    with open(package_dir / "pyproject.toml", "w") as f:
        toml.dump(pyproject_content, f)

    # Create a sample Python file
    (package_dir / "main.py").write_text("print('Hello from sample package')")

    # Create README
    (package_dir / "README.md").write_text("# Sample Package\n\nA test package.")

    # Create tarball
    tarball_path = tmp_path / "sample-package-1.0.0.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname="sample-package-1.0.0")

    return tarball_path


@pytest.fixture
def minimal_package_tarball(tmp_path):
    """Create a minimal package without pyproject.toml."""
    package_dir = tmp_path / "minimal-package-0.1.0"
    package_dir.mkdir()

    # Create just a Python file
    (package_dir / "main.py").write_text("# Minimal package")

    # Create tarball
    tarball_path = tmp_path / "minimal-package-0.1.0.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname="minimal-package-0.1.0")

    return tarball_path


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for testing HTTP requests."""
    with patch("revitpy_package_manager.builder.cli.main.httpx.Client") as mock_client:
        # Create mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "pkg-123",
            "name": "sample-package",
            "version": "1.0.0",
        }

        # Configure the mock client
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.return_value = mock_response
        mock_client.return_value = mock_instance

        yield mock_instance


class TestMetadataExtraction:
    """Tests for package metadata extraction."""

    def test_extract_metadata_from_valid_package(self, sample_package_tarball):
        """Test metadata extraction from a valid package with pyproject.toml."""
        metadata = _extract_package_metadata(sample_package_tarball)

        assert metadata["name"] == "sample-package"
        assert metadata["version"] == "1.0.0"
        assert metadata["summary"] == "A sample package for testing"
        assert metadata["author"] == "Test Author"
        assert metadata["author_email"] == "test@example.com"
        assert metadata["license"] == "MIT"
        assert "sha256" in metadata
        assert "md5" in metadata
        assert metadata["size_mb"] > 0

    def test_extract_metadata_computes_correct_hashes(self, sample_package_tarball):
        """Test that SHA256 and MD5 hashes are computed correctly."""
        metadata = _extract_package_metadata(sample_package_tarball)

        # Verify hash by computing it independently
        with open(sample_package_tarball, "rb") as f:
            content = f.read()
            expected_sha256 = hashlib.sha256(content).hexdigest()
            expected_md5 = hashlib.md5(content).hexdigest()

        assert metadata["sha256"] == expected_sha256
        assert metadata["md5"] == expected_md5

    def test_extract_metadata_from_minimal_package(self, minimal_package_tarball):
        """Test metadata extraction from package without pyproject.toml."""
        metadata = _extract_package_metadata(minimal_package_tarball)

        # Should infer from filename
        assert metadata["name"] == "minimal-package"
        assert metadata["version"] == "0.1.0"
        assert "sha256" in metadata
        assert "md5" in metadata

    def test_extract_metadata_invalid_package(self, tmp_path):
        """Test metadata extraction rejects corrupted/invalid tarball."""
        # Create a corrupted file (not a valid tarball)
        invalid_file = tmp_path / "test-package-1.5.0.tar.gz"
        invalid_file.write_text("not a tarball")

        # Should reject corrupted files, not fall back to filename
        with pytest.raises(ValueError, match="corrupted or invalid"):
            _extract_package_metadata(invalid_file)


class TestPublishCommand:
    """Tests for the publish CLI command."""

    def test_publish_dry_run_mode(self, sample_package_tarball):
        """Test publish command in dry-run mode."""
        runner = CliRunner()
        result = runner.invoke(
            publish, [str(sample_package_tarball), "--dry-run", "--token", "test-token"]
        )

        assert result.exit_code == 0
        assert "Dry run mode" in result.output
        assert "Would upload" in result.output
        assert "sample-package" in result.output

    def test_publish_requires_token(self, sample_package_tarball):
        """Test that publish command requires authentication token."""
        runner = CliRunner()

        # Without token and without env var
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                ],
            )

            assert result.exit_code == 1
            assert "Authentication token required" in result.output

    def test_publish_uses_env_token(self, sample_package_tarball, mock_httpx_client):
        """Test that publish command can use REVITPY_TOKEN environment variable."""
        runner = CliRunner()

        with patch.dict("os.environ", {"REVITPY_TOKEN": "env-token"}):
            result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                ],
            )

            # Should not fail due to missing token
            # (May fail for other reasons in test, but not auth)
            assert "Authentication token required" not in result.output

    def test_publish_successful_upload(self, sample_package_tarball, mock_httpx_client):
        """Test successful package upload."""
        runner = CliRunner()

        result = runner.invoke(
            publish,
            [
                str(sample_package_tarball),
                "--registry-url",
                "http://localhost:8000",
                "--token",
                "test-token",
            ],
        )

        assert result.exit_code == 0
        assert "Successfully published" in result.output
        assert "sample-package" in result.output

        # Verify httpx client was called
        assert mock_httpx_client.post.called

    def test_publish_with_custom_timeout(
        self, sample_package_tarball, mock_httpx_client
    ):
        """Test publish with custom timeout setting."""
        runner = CliRunner()

        result = runner.invoke(
            publish,
            [
                str(sample_package_tarball),
                "--registry-url",
                "http://localhost:8000",
                "--token",
                "test-token",
                "--timeout",
                "600",
            ],
        )

        assert result.exit_code == 0


class TestUploadFunctionality:
    """Tests for the upload functionality."""

    def test_upload_sends_correct_headers(
        self, sample_package_tarball, mock_httpx_client
    ):
        """Test that upload includes correct authorization headers."""
        metadata = _extract_package_metadata(sample_package_tarball)

        _upload_package_to_registry(
            package_path=sample_package_tarball,
            metadata=metadata,
            registry_url="http://localhost:8000",
            token="test-token",
            timeout=300,
        )

        # Verify post was called
        assert mock_httpx_client.post.called

        # Get the call arguments
        call_args = mock_httpx_client.post.call_args

        # Verify URL
        assert "http://localhost:8000/api/v1/packages" in call_args[0][0]

        # Verify headers were passed (in kwargs)
        if "headers" in call_args[1]:
            headers = call_args[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-token"

    def test_upload_sends_multipart_form(
        self, sample_package_tarball, mock_httpx_client
    ):
        """Test that upload sends file as multipart form data."""
        metadata = _extract_package_metadata(sample_package_tarball)

        _upload_package_to_registry(
            package_path=sample_package_tarball,
            metadata=metadata,
            registry_url="http://localhost:8000",
            token="test-token",
            timeout=300,
        )

        # Verify files were passed
        call_args = mock_httpx_client.post.call_args
        assert "files" in call_args[1]

        files = call_args[1]["files"]
        assert "file" in files


class TestRetryLogic:
    """Tests for upload retry logic."""

    def test_retry_on_500_error(self, sample_package_tarball):
        """Test that upload retries on 5xx server errors."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            # First two attempts fail with 500, third succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", request=Mock(), response=mock_response_fail
            )

            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"id": "pkg-123"}

            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = [
                mock_response_fail,
                mock_response_fail,
                mock_response_success,
            ]
            mock_client.return_value = mock_instance

            _result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                    "--token",
                    "test-token",
                    "--retry-attempts",
                    "3",
                ],
            )

            # Should eventually succeed after retries
            assert mock_instance.post.call_count == 3

    def test_no_retry_on_401_error(self, sample_package_tarball):
        """Test that upload does not retry on authentication errors."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )

            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response
            mock_client.return_value = mock_instance

            result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                    "--token",
                    "invalid-token",
                ],
            )

            # Should fail immediately without retries
            assert result.exit_code == 1
            assert "Authentication failed" in result.output
            assert mock_instance.post.call_count == 1

    def test_no_retry_on_409_conflict(self, sample_package_tarball):
        """Test that upload does not retry on version conflict (409)."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            mock_response = Mock()
            mock_response.status_code = 409
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Conflict", request=Mock(), response=mock_response
            )

            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response
            mock_client.return_value = mock_instance

            result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                    "--token",
                    "test-token",
                ],
            )

            # Should fail immediately
            assert result.exit_code == 1
            assert "already exists" in result.output
            assert mock_instance.post.call_count == 1

    def test_timeout_retry(self, sample_package_tarball):
        """Test that upload retries on timeout."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance

            # First attempt times out, second succeeds
            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"id": "pkg-123"}

            mock_instance.post.side_effect = [
                httpx.TimeoutException("Timeout"),
                mock_success,
            ]
            mock_client.return_value = mock_instance

            _result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                    "--token",
                    "test-token",
                    "--retry-attempts",
                    "2",
                ],
            )

            # Should retry and succeed
            assert mock_instance.post.call_count == 2


class TestErrorHandling:
    """Tests for error handling in publish command."""

    def test_invalid_package_path(self):
        """Test error handling for non-existent package file."""
        runner = CliRunner()

        result = runner.invoke(
            publish, ["/nonexistent/package.tar.gz", "--token", "test-token"]
        )

        assert result.exit_code != 0

    def test_corrupted_package_metadata(self, tmp_path):
        """Test error handling for corrupted package file."""
        corrupted_file = tmp_path / "corrupted.tar.gz"
        corrupted_file.write_bytes(b"corrupted data")

        runner = CliRunner()
        result = runner.invoke(
            publish, [str(corrupted_file), "--token", "test-token", "--dry-run"]
        )

        assert result.exit_code == 1
        assert "Failed to extract package metadata" in result.output

    def test_network_error_handling(self, sample_package_tarball):
        """Test handling of network errors during upload."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.ConnectError("Connection failed")
            mock_client.return_value = mock_instance

            result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--registry-url",
                    "http://localhost:8000",
                    "--token",
                    "test-token",
                ],
            )

            assert result.exit_code == 1


class TestPublishIntegration:
    """Integration tests for the publish workflow."""

    def test_complete_publish_workflow(self, sample_package_tarball, mock_httpx_client):
        """Test complete publish workflow from start to finish."""
        runner = CliRunner()

        # Test the complete flow
        result = runner.invoke(
            publish,
            [
                str(sample_package_tarball),
                "--registry-url",
                "http://test-registry.com",
                "--token",
                "integration-test-token",
                "--timeout",
                "120",
            ],
        )

        # Verify success
        assert result.exit_code == 0
        assert "Successfully published" in result.output
        assert "sample-package" in result.output
        assert "v1.0.0" in result.output

        # Verify the upload was called with correct parameters
        assert mock_httpx_client.post.called
        call_args = mock_httpx_client.post.call_args
        assert "http://test-registry.com/api/v1/packages" in call_args[0][0]

    def test_publish_displays_package_info(self, sample_package_tarball):
        """Test that publish displays package information before upload."""
        runner = CliRunner()

        result = runner.invoke(
            publish, [str(sample_package_tarball), "--dry-run", "--token", "test-token"]
        )

        # Should display package info
        assert "sample-package" in result.output
        assert "1.0.0" in result.output
        assert "SHA256" in result.output


class TestPublishConfiguration:
    """Tests for publish command configuration options."""

    def test_custom_registry_url(self, sample_package_tarball, mock_httpx_client):
        """Test publish with custom registry URL."""
        runner = CliRunner()

        _result = runner.invoke(
            publish,
            [
                str(sample_package_tarball),
                "--registry-url",
                "https://custom-registry.example.com",
                "--token",
                "test-token",
            ],
        )

        call_args = mock_httpx_client.post.call_args
        assert "https://custom-registry.example.com" in call_args[0][0]

    def test_custom_retry_attempts(self, sample_package_tarball):
        """Test publish with custom retry attempts."""
        runner = CliRunner()

        with patch(
            "revitpy_package_manager.builder.cli.main.httpx.Client"
        ) as mock_client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", request=Mock(), response=mock_response
            )

            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response
            mock_client.return_value = mock_instance

            _result = runner.invoke(
                publish,
                [
                    str(sample_package_tarball),
                    "--token",
                    "test-token",
                    "--retry-attempts",
                    "5",
                ],
            )

            # Should attempt 5 times
            assert mock_instance.post.call_count == 5
