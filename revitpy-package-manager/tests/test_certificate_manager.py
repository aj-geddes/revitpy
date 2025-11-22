"""Tests for X.509 certificate management and package signing system."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID
from revitpy_package_manager.security.certificate_manager import (
    CertificateRevocationError,
    CertificateStore,
    CertificateValidationError,
    X509PackageSigner,
    create_default_certificate_store,
    get_x509_package_signer,
)


# Test fixtures
@pytest.fixture
def temp_cert_store():
    """Create a temporary certificate store for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        yield store


@pytest.fixture
def rsa_private_key():
    """Generate an RSA private key for testing."""
    return rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )


@pytest.fixture
def ed25519_private_key():
    """Generate an Ed25519 private key for testing."""
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def test_certificate(rsa_private_key):
    """Generate a test certificate."""
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Test Certificate"),
        ]
    )

    builder = x509.CertificateBuilder()
    builder = builder.subject_name(subject)
    builder = builder.issuer_name(subject)
    builder = builder.public_key(rsa_private_key.public_key())
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.not_valid_before(datetime.utcnow())
    builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True,
    )

    builder = builder.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            content_commitment=True,
            data_encipherment=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    )

    builder = builder.add_extension(
        x509.ExtendedKeyUsage(
            [
                x509.oid.ExtendedKeyUsageOID.CODE_SIGNING,
            ]
        ),
        critical=True,
    )

    certificate = builder.sign(rsa_private_key, hashes.SHA256(), default_backend())
    return certificate


class TestCertificateExceptions:
    """Test certificate exception classes."""

    def test_certificate_validation_error(self):
        """Test CertificateValidationError exception."""
        error = CertificateValidationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_certificate_revocation_error(self):
        """Test CertificateRevocationError exception."""
        error = CertificateRevocationError("Certificate revoked")
        assert str(error) == "Certificate revoked"
        assert isinstance(error, Exception)


class TestCertificateStore:
    """Test CertificateStore functionality."""

    def test_certificate_store_initialization(self, temp_cert_store):
        """Test certificate store initialization creates directories."""
        assert temp_cert_store.store_path.exists()
        assert temp_cert_store.ca_certs_path.exists()
        assert temp_cert_store.trusted_certs_path.exists()
        assert temp_cert_store.revoked_certs_path.exists()
        assert temp_cert_store.crl_path.exists()

    def test_add_ca_certificate(self, temp_cert_store, test_certificate):
        """Test adding a CA certificate to the store."""
        fingerprint = temp_cert_store.add_ca_certificate(test_certificate, "test-ca")

        # Check certificate file was created
        cert_files = list(
            temp_cert_store.ca_certs_path.glob(f"test-ca_{fingerprint}.pem")
        )
        assert len(cert_files) == 1

        # Check metadata file was created
        metadata_files = list(
            temp_cert_store.ca_certs_path.glob(f"test-ca_{fingerprint}.json")
        )
        assert len(metadata_files) == 1

        # Verify metadata content
        with open(metadata_files[0]) as f:
            metadata = json.load(f)
            assert metadata["alias"] == "test-ca"
            assert metadata["fingerprint"] == fingerprint
            assert metadata["is_ca"] is True
            assert "subject" in metadata
            assert "issuer" in metadata

    def test_add_trusted_certificate(self, temp_cert_store, test_certificate):
        """Test adding a trusted certificate to the store."""
        fingerprint = temp_cert_store.add_trusted_certificate(
            test_certificate, "test-trusted", purpose="code-signing"
        )

        # Check certificate file was created
        cert_files = list(
            temp_cert_store.trusted_certs_path.glob(f"test-trusted_{fingerprint}.pem")
        )
        assert len(cert_files) == 1

        # Check metadata
        metadata_files = list(
            temp_cert_store.trusted_certs_path.glob(f"test-trusted_{fingerprint}.json")
        )
        with open(metadata_files[0]) as f:
            metadata = json.load(f)
            assert metadata["alias"] == "test-trusted"
            assert metadata["purpose"] == "code-signing"
            assert metadata["is_ca"] is False

    def test_get_certificate_by_fingerprint(self, temp_cert_store, test_certificate):
        """Test retrieving a certificate by fingerprint."""
        fingerprint = temp_cert_store.add_ca_certificate(test_certificate, "test-ca")

        retrieved_cert = temp_cert_store.get_certificate(fingerprint)

        assert retrieved_cert is not None
        assert retrieved_cert.subject == test_certificate.subject
        assert retrieved_cert.serial_number == test_certificate.serial_number

    def test_get_certificate_not_found(self, temp_cert_store):
        """Test getting a non-existent certificate returns None."""
        result = temp_cert_store.get_certificate("nonexistent_fingerprint")
        assert result is None

    def test_get_ca_certificates(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test retrieving all CA certificates."""
        # Add multiple CA certificates
        temp_cert_store.add_ca_certificate(test_certificate, "ca1")

        # Create another certificate
        subject2 = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org 2"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Test CA 2"),
            ]
        )
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject2)
        builder = builder.issuer_name(subject2)
        builder = builder.public_key(rsa_private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow())
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))
        cert2 = builder.sign(rsa_private_key, hashes.SHA256(), default_backend())

        temp_cert_store.add_ca_certificate(cert2, "ca2")

        # Get all CA certificates
        ca_certs = temp_cert_store.get_ca_certificates()

        assert len(ca_certs) == 2

    def test_revoke_certificate(self, temp_cert_store, test_certificate):
        """Test revoking a certificate."""
        temp_cert_store.revoke_certificate(test_certificate, reason="key_compromise")

        # Check revocation file was created
        fingerprint = temp_cert_store._get_certificate_fingerprint(test_certificate)
        revoked_file = temp_cert_store.revoked_certs_path / f"{fingerprint}.revoked"

        assert revoked_file.exists()

        # Check revocation info
        with open(revoked_file) as f:
            revocation_info = json.load(f)
            assert revocation_info["fingerprint"] == fingerprint
            assert revocation_info["reason"] == "key_compromise"
            assert "revoked_at" in revocation_info

    def test_is_certificate_revoked(self, temp_cert_store, test_certificate):
        """Test checking if a certificate is revoked."""
        # Certificate should not be revoked initially
        assert temp_cert_store.is_certificate_revoked(test_certificate) is False

        # Revoke the certificate
        temp_cert_store.revoke_certificate(test_certificate)

        # Certificate should now be revoked
        assert temp_cert_store.is_certificate_revoked(test_certificate) is True

    def test_get_certificate_fingerprint(self, temp_cert_store, test_certificate):
        """Test getting certificate fingerprint."""
        fingerprint = temp_cert_store._get_certificate_fingerprint(test_certificate)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in fingerprint)


class TestX509PackageSigner:
    """Test X509PackageSigner functionality."""

    def test_signer_initialization(self, temp_cert_store):
        """Test package signer initialization."""
        signer = X509PackageSigner(temp_cert_store)
        assert signer.certificate_store == temp_cert_store

    def test_create_self_signed_certificate_rsa(self, temp_cert_store, rsa_private_key):
        """Test creating a self-signed certificate with RSA key."""
        signer = X509PackageSigner(temp_cert_store)

        certificate = signer.create_self_signed_certificate(
            rsa_private_key,
            subject_name="Test Developer",
            organization="Test Org",
            country="US",
            validity_days=365,
        )

        assert certificate.subject == certificate.issuer  # Self-signed
        assert "Test Developer" in certificate.subject.rfc4514_string()
        assert certificate.not_valid_before <= datetime.utcnow()
        assert certificate.not_valid_after > datetime.utcnow()

    def test_create_self_signed_certificate_ed25519(
        self, temp_cert_store, ed25519_private_key
    ):
        """Test creating a self-signed certificate with Ed25519 key."""
        signer = X509PackageSigner(temp_cert_store)

        certificate = signer.create_self_signed_certificate(
            ed25519_private_key,
            subject_name="Ed25519 Developer",
            organization="Test Org",
        )

        assert certificate.subject == certificate.issuer
        assert "Ed25519 Developer" in certificate.subject.rfc4514_string()

    def test_certificate_has_code_signing_extension(
        self, temp_cert_store, rsa_private_key
    ):
        """Test that created certificate has code signing extension."""
        signer = X509PackageSigner(temp_cert_store)

        certificate = signer.create_self_signed_certificate(
            rsa_private_key, subject_name="Test Developer"
        )

        ext_key_usage = certificate.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
        ).value

        assert x509.oid.ExtendedKeyUsageOID.CODE_SIGNING in ext_key_usage

    def test_certificate_has_digital_signature_key_usage(
        self, temp_cert_store, rsa_private_key
    ):
        """Test that created certificate has digital signature key usage."""
        signer = X509PackageSigner(temp_cert_store)

        certificate = signer.create_self_signed_certificate(
            rsa_private_key, subject_name="Test Developer"
        )

        key_usage = certificate.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.KEY_USAGE
        ).value

        assert key_usage.digital_signature is True

    def test_create_certificate_signing_request(self, temp_cert_store, rsa_private_key):
        """Test creating a Certificate Signing Request."""
        signer = X509PackageSigner(temp_cert_store)

        csr = signer.create_certificate_signing_request(
            rsa_private_key,
            subject_name="Test Developer",
            organization="Test Org",
            email="test@example.com",
            country="US",
        )

        assert csr.is_signature_valid
        assert "Test Developer" in csr.subject.rfc4514_string()
        assert "test@example.com" in csr.subject.rfc4514_string()

    def test_sign_package_with_rsa_certificate(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test signing a package with RSA certificate."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"This is test package data"
        metadata = {"version": "1.0.0", "author": "Test"}

        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key, metadata=metadata
        )

        assert signature_info["signature_version"] == "2.0"
        assert signature_info["algorithm"] == "RSA-PSS"
        assert "signature" in signature_info
        assert "certificate" in signature_info
        assert "certificate_fingerprint" in signature_info
        assert "package_hash" in signature_info
        assert "metadata_hash" in signature_info
        assert signature_info["metadata"] == metadata

    def test_sign_package_with_ed25519_certificate(
        self, temp_cert_store, ed25519_private_key
    ):
        """Test signing a package with Ed25519 certificate."""
        signer = X509PackageSigner(temp_cert_store)

        # Create Ed25519 certificate
        certificate = signer.create_self_signed_certificate(
            ed25519_private_key, subject_name="Ed25519 Developer"
        )

        package_data = b"Test package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, ed25519_private_key
        )

        assert signature_info["algorithm"] == "Ed25519"

    def test_verify_package_signature_valid(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test verifying a valid package signature."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Test package data"
        metadata = {"version": "1.0.0"}

        # Sign the package
        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key, metadata=metadata
        )

        # Verify the signature
        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is True
        assert error is None

    def test_verify_package_signature_tampered_data(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test verifying signature with tampered package data."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Original package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key
        )

        # Try to verify with different data
        tampered_data = b"Tampered package data"
        is_valid, error = signer.verify_package_signature(tampered_data, signature_info)

        assert is_valid is False
        assert "hash mismatch" in error.lower()

    def test_verify_package_signature_tampered_metadata(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test verifying signature with tampered metadata."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Test package data"
        metadata = {"version": "1.0.0"}

        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key, metadata=metadata
        )

        # Tamper with metadata
        signature_info["metadata"]["version"] = "2.0.0"

        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is False
        assert "metadata hash mismatch" in error.lower()

    def test_verify_package_signature_revoked_certificate(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test verifying signature with revoked certificate."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Test package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key
        )

        # Revoke the certificate
        temp_cert_store.revoke_certificate(test_certificate)

        # Try to verify
        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is False
        assert "revoked" in error.lower()

    def test_validate_certificate_expired(self, temp_cert_store, rsa_private_key):
        """Test validating an expired certificate."""
        signer = X509PackageSigner(temp_cert_store)

        # Create expired certificate
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Expired Cert"),
            ]
        )

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)
        builder = builder.public_key(rsa_private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow() - timedelta(days=365))
        builder = builder.not_valid_after(datetime.utcnow() - timedelta(days=1))

        expired_cert = builder.sign(rsa_private_key, hashes.SHA256(), default_backend())

        with pytest.raises(CertificateValidationError, match="expired"):
            signer._validate_certificate(expired_cert)

    def test_validate_certificate_not_yet_valid(self, temp_cert_store, rsa_private_key):
        """Test validating a certificate that is not yet valid."""
        signer = X509PackageSigner(temp_cert_store)

        # Create future certificate
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Future Cert"),
            ]
        )

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)
        builder = builder.public_key(rsa_private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow() + timedelta(days=1))
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

        future_cert = builder.sign(rsa_private_key, hashes.SHA256(), default_backend())

        with pytest.raises(CertificateValidationError, match="not yet valid"):
            signer._validate_certificate(future_cert)

    def test_sign_package_with_timestamp(
        self, temp_cert_store, test_certificate, rsa_private_key
    ):
        """Test signing a package with timestamp."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Test package data"
        timestamp_url = "http://timestamp.example.com"

        signature_info = signer.sign_package_with_certificate(
            package_data, test_certificate, rsa_private_key, timestamp_url=timestamp_url
        )

        assert signature_info["timestamp"] is not None
        assert signature_info["timestamp"]["url"] == timestamp_url
        assert "timestamp" in signature_info["timestamp"]
        assert "data_hash" in signature_info["timestamp"]

    def test_verify_timestamp(self, temp_cert_store):
        """Test timestamp verification."""
        signer = X509PackageSigner(temp_cert_store)

        data = b"Test data"
        timestamp_info = signer._create_timestamp(data, "http://example.com")

        # Verify with correct data
        assert signer._verify_timestamp(data, timestamp_info) is True

        # Verify with wrong data
        assert signer._verify_timestamp(b"Wrong data", timestamp_info) is False


class TestCertificateChainValidation:
    """Test certificate chain validation."""

    def test_self_signed_certificate_validation(
        self, temp_cert_store, test_certificate
    ):
        """Test that self-signed certificates don't require chain validation."""
        signer = X509PackageSigner(temp_cert_store)

        # Should not raise exception for valid self-signed certificate
        signer._validate_certificate(test_certificate)

    def test_verify_certificate_chain_missing_issuer(
        self, temp_cert_store, rsa_private_key
    ):
        """Test certificate chain validation with missing issuer."""
        signer = X509PackageSigner(temp_cert_store)

        # Create CA certificate
        ca_subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Test CA Certificate"),
            ]
        )

        # Create end-entity certificate signed by non-existent CA
        ee_subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Test EE Certificate"),
            ]
        )

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(ee_subject)
        builder = builder.issuer_name(ca_subject)  # Different issuer
        builder = builder.public_key(rsa_private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow())
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=True,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

        builder = builder.add_extension(
            x509.ExtendedKeyUsage(
                [
                    x509.oid.ExtendedKeyUsageOID.CODE_SIGNING,
                ]
            ),
            critical=True,
        )

        ee_cert = builder.sign(rsa_private_key, hashes.SHA256(), default_backend())

        # Should raise exception because issuer not in store
        with pytest.raises(CertificateValidationError, match="issuer not found"):
            signer._validate_certificate(ee_cert)


class TestHelperFunctions:
    """Test helper functions."""

    def test_create_default_certificate_store(self):
        """Test creating default certificate store."""
        store = create_default_certificate_store()

        assert isinstance(store, CertificateStore)
        assert store.store_path.exists()

    def test_get_x509_package_signer(self):
        """Test getting default X509PackageSigner."""
        signer = get_x509_package_signer()

        assert isinstance(signer, X509PackageSigner)
        assert isinstance(signer.certificate_store, CertificateStore)


class TestIntegrationScenarios:
    """Test end-to-end scenarios."""

    def test_complete_signing_workflow(self, temp_cert_store, rsa_private_key):
        """Test complete workflow from key generation to signature verification."""
        signer = X509PackageSigner(temp_cert_store)

        # 1. Create certificate
        certificate = signer.create_self_signed_certificate(
            rsa_private_key,
            subject_name="Integration Test Developer",
            organization="Test Org",
        )

        # 2. Add to trusted store
        temp_cert_store.add_trusted_certificate(certificate, "integration-test")

        # 3. Sign package
        package_data = b"Integration test package data"
        metadata = {"version": "1.0.0", "author": "Integration Test"}

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, rsa_private_key, metadata=metadata
        )

        # 4. Verify signature
        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is True
        assert error is None

    def test_multi_algorithm_signing(
        self, temp_cert_store, rsa_private_key, ed25519_private_key
    ):
        """Test signing with different algorithms."""
        signer = X509PackageSigner(temp_cert_store)

        package_data = b"Multi-algorithm test data"

        # Sign with RSA
        rsa_cert = signer.create_self_signed_certificate(
            rsa_private_key, "RSA Developer"
        )
        rsa_signature = signer.sign_package_with_certificate(
            package_data, rsa_cert, rsa_private_key
        )

        # Sign with Ed25519
        ed25519_cert = signer.create_self_signed_certificate(
            ed25519_private_key, "Ed25519 Developer"
        )
        ed25519_signature = signer.sign_package_with_certificate(
            package_data, ed25519_cert, ed25519_private_key
        )

        # Verify both
        is_valid_rsa, _ = signer.verify_package_signature(package_data, rsa_signature)
        is_valid_ed25519, _ = signer.verify_package_signature(
            package_data, ed25519_signature
        )

        assert is_valid_rsa is True
        assert is_valid_ed25519 is True
