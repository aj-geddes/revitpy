#!/usr/bin/env python
"""
Standalone test runner for certificate management tests.

Run this directly with: python tests/run_certificate_tests.py
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def generate_rsa_key():
    """Generate an RSA private key for testing."""
    return rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )


def generate_ed25519_key():
    """Generate an Ed25519 private key for testing."""
    return ed25519.Ed25519PrivateKey.generate()


def create_test_certificate(private_key):
    """Create a test certificate."""
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
    builder = builder.public_key(private_key.public_key())
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
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CODE_SIGNING]),
        critical=True,
    )

    certificate = builder.sign(private_key, hashes.SHA256(), default_backend())
    return certificate


def test_exception_classes():
    """Test certificate exception classes."""
    print("🔍 Testing exception classes...")

    # Test CertificateValidationError
    error = CertificateValidationError("Test error")
    assert str(error) == "Test error"
    print("  ✅ CertificateValidationError works")

    # Test CertificateRevocationError
    error = CertificateRevocationError("Certificate revoked")
    assert str(error) == "Certificate revoked"
    print("  ✅ CertificateRevocationError works")


def test_certificate_store_initialization():
    """Test certificate store initialization."""
    print("\n🔍 Testing CertificateStore initialization...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))

        assert store.store_path.exists()
        assert store.ca_certs_path.exists()
        assert store.trusted_certs_path.exists()
        assert store.revoked_certs_path.exists()
        assert store.crl_path.exists()

        print("  ✅ All directories created")


def test_add_ca_certificate():
    """Test adding a CA certificate."""
    print("\n🔍 Testing adding CA certificate...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        fingerprint = store.add_ca_certificate(certificate, "test-ca")

        # Check files were created
        cert_files = list(store.ca_certs_path.glob(f"test-ca_{fingerprint}.pem"))
        assert len(cert_files) == 1
        print("  ✅ Certificate file created")

        metadata_files = list(store.ca_certs_path.glob(f"test-ca_{fingerprint}.json"))
        assert len(metadata_files) == 1
        print("  ✅ Metadata file created")


def test_add_trusted_certificate():
    """Test adding a trusted certificate."""
    print("\n🔍 Testing adding trusted certificate...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        fingerprint = store.add_trusted_certificate(
            certificate, "test-trusted", purpose="code-signing"
        )

        cert_files = list(
            store.trusted_certs_path.glob(f"test-trusted_{fingerprint}.pem")
        )
        assert len(cert_files) == 1
        print("  ✅ Trusted certificate added")


def test_get_certificate():
    """Test retrieving certificate by fingerprint."""
    print("\n🔍 Testing certificate retrieval...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        fingerprint = store.add_ca_certificate(certificate, "test-ca")
        retrieved = store.get_certificate(fingerprint)

        assert retrieved is not None
        assert retrieved.subject == certificate.subject
        print("  ✅ Certificate retrieved successfully")

        # Test non-existent certificate
        result = store.get_certificate("nonexistent")
        assert result is None
        print("  ✅ Returns None for non-existent certificate")


def test_get_ca_certificates():
    """Test retrieving all CA certificates."""
    print("\n🔍 Testing CA certificate list retrieval...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()

        # Add multiple CA certificates
        cert1 = create_test_certificate(private_key)
        cert2 = create_test_certificate(private_key)

        store.add_ca_certificate(cert1, "ca1")
        store.add_ca_certificate(cert2, "ca2")

        ca_certs = store.get_ca_certificates()
        assert len(ca_certs) == 2
        print("  ✅ Retrieved all CA certificates")


def test_certificate_revocation():
    """Test certificate revocation."""
    print("\n🔍 Testing certificate revocation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        # Check not revoked initially
        assert store.is_certificate_revoked(certificate) is False
        print("  ✅ Certificate not revoked initially")

        # Revoke certificate
        store.revoke_certificate(certificate, reason="key_compromise")
        print("  ✅ Certificate revoked")

        # Check is now revoked
        assert store.is_certificate_revoked(certificate) is True
        print("  ✅ Revocation status detected")


def test_certificate_fingerprint():
    """Test certificate fingerprint generation."""
    print("\n🔍 Testing certificate fingerprint...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        fingerprint = store._get_certificate_fingerprint(certificate)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in fingerprint)
        print("  ✅ Fingerprint generated correctly")


def test_x509_signer_initialization():
    """Test X509PackageSigner initialization."""
    print("\n🔍 Testing X509PackageSigner initialization...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)

        assert signer.certificate_store == store
        print("  ✅ Signer initialized")


def test_create_self_signed_certificate_rsa():
    """Test creating self-signed certificate with RSA."""
    print("\n🔍 Testing RSA self-signed certificate creation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

        certificate = signer.create_self_signed_certificate(
            private_key,
            subject_name="Test Developer",
            organization="Test Org",
            validity_days=365,
        )

        assert certificate.subject == certificate.issuer  # Self-signed
        assert "Test Developer" in certificate.subject.rfc4514_string()
        print("  ✅ RSA self-signed certificate created")


def test_create_self_signed_certificate_ed25519():
    """Test creating self-signed certificate with Ed25519."""
    print("\n🔍 Testing Ed25519 self-signed certificate creation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_ed25519_key()

        certificate = signer.create_self_signed_certificate(
            private_key, subject_name="Ed25519 Developer"
        )

        assert certificate.subject == certificate.issuer
        assert "Ed25519 Developer" in certificate.subject.rfc4514_string()
        print("  ✅ Ed25519 self-signed certificate created")


def test_certificate_extensions():
    """Test that certificates have required extensions."""
    print("\n🔍 Testing certificate extensions...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

        certificate = signer.create_self_signed_certificate(
            private_key, subject_name="Test Developer"
        )

        # Check code signing extension
        ext_key_usage = certificate.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
        ).value
        assert x509.oid.ExtendedKeyUsageOID.CODE_SIGNING in ext_key_usage
        print("  ✅ Code signing extension present")

        # Check digital signature key usage
        key_usage = certificate.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.KEY_USAGE
        ).value
        assert key_usage.digital_signature is True
        print("  ✅ Digital signature key usage present")


def test_create_certificate_signing_request():
    """Test CSR creation."""
    print("\n🔍 Testing CSR creation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

        csr = signer.create_certificate_signing_request(
            private_key,
            subject_name="Test Developer",
            organization="Test Org",
            email="test@example.com",
        )

        assert csr.is_signature_valid
        assert "Test Developer" in csr.subject.rfc4514_string()
        print("  ✅ CSR created successfully")


def test_sign_package_rsa():
    """Test signing a package with RSA."""
    print("\n🔍 Testing package signing (RSA)...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Test package data"
        metadata = {"version": "1.0.0", "author": "Test"}

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key, metadata=metadata
        )

        assert signature_info["signature_version"] == "2.0"
        assert signature_info["algorithm"] == "RSA-PSS"
        assert "signature" in signature_info
        assert "certificate" in signature_info
        print("  ✅ Package signed with RSA")


def test_sign_package_ed25519():
    """Test signing a package with Ed25519."""
    print("\n🔍 Testing package signing (Ed25519)...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_ed25519_key()

        certificate = signer.create_self_signed_certificate(
            private_key, subject_name="Ed25519 Developer"
        )

        package_data = b"Test package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key
        )

        assert signature_info["algorithm"] == "Ed25519"
        print("  ✅ Package signed with Ed25519")


def test_verify_valid_signature():
    """Test verifying a valid signature."""
    print("\n🔍 Testing valid signature verification...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Test package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key
        )

        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is True
        assert error is None
        print("  ✅ Valid signature verified successfully")


def test_verify_tampered_data():
    """Test verification with tampered data."""
    print("\n🔍 Testing tampered data detection...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Original package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key
        )

        # Try with tampered data
        tampered_data = b"Tampered package data"
        is_valid, error = signer.verify_package_signature(tampered_data, signature_info)

        assert is_valid is False
        assert "hash mismatch" in error.lower()
        print("  ✅ Tampered data detected")


def test_verify_tampered_metadata():
    """Test verification with tampered metadata."""
    print("\n🔍 Testing tampered metadata detection...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Test package data"
        metadata = {"version": "1.0.0"}

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key, metadata=metadata
        )

        # Tamper with metadata
        signature_info["metadata"]["version"] = "2.0.0"

        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is False
        assert "metadata hash mismatch" in error.lower()
        print("  ✅ Tampered metadata detected")


def test_verify_revoked_certificate():
    """Test verification with revoked certificate."""
    print("\n🔍 Testing revoked certificate detection...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Test package data"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key
        )

        # Revoke the certificate
        store.revoke_certificate(certificate)

        is_valid, error = signer.verify_package_signature(package_data, signature_info)

        assert is_valid is False
        assert "revoked" in error.lower()
        print("  ✅ Revoked certificate detected")


def test_validate_expired_certificate():
    """Test validation of expired certificate."""
    print("\n🔍 Testing expired certificate detection...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

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
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow() - timedelta(days=365))
        builder = builder.not_valid_after(datetime.utcnow() - timedelta(days=1))

        expired_cert = builder.sign(private_key, hashes.SHA256(), default_backend())

        try:
            signer._validate_certificate(expired_cert)
            raise AssertionError("Should have raised CertificateValidationError")
        except CertificateValidationError as e:
            assert "expired" in str(e).lower()
            print("  ✅ Expired certificate detected")


def test_validate_future_certificate():
    """Test validation of not-yet-valid certificate."""
    print("\n🔍 Testing not-yet-valid certificate detection...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

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
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow() + timedelta(days=1))
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

        future_cert = builder.sign(private_key, hashes.SHA256(), default_backend())

        try:
            signer._validate_certificate(future_cert)
            raise AssertionError("Should have raised CertificateValidationError")
        except CertificateValidationError as e:
            assert "not yet valid" in str(e).lower()
            print("  ✅ Not-yet-valid certificate detected")


def test_timestamp_creation_and_verification():
    """Test timestamp creation and verification."""
    print("\n🔍 Testing timestamp functionality...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)

        data = b"Test data"
        timestamp_info = signer._create_timestamp(data, "http://example.com")

        assert timestamp_info is not None
        assert timestamp_info["url"] == "http://example.com"
        print("  ✅ Timestamp created")

        # Verify with correct data
        assert signer._verify_timestamp(data, timestamp_info) is True
        print("  ✅ Valid timestamp verified")

        # Verify with wrong data
        assert signer._verify_timestamp(b"Wrong data", timestamp_info) is False
        print("  ✅ Invalid timestamp detected")


def test_sign_with_timestamp():
    """Test signing with timestamp."""
    print("\n🔍 Testing signing with timestamp...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()
        certificate = create_test_certificate(private_key)

        package_data = b"Test package data"
        timestamp_url = "http://timestamp.example.com"

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key, timestamp_url=timestamp_url
        )

        assert signature_info["timestamp"] is not None
        assert signature_info["timestamp"]["url"] == timestamp_url
        print("  ✅ Package signed with timestamp")


def test_helper_functions():
    """Test helper functions."""
    print("\n🔍 Testing helper functions...")

    # Test create_default_certificate_store
    store = create_default_certificate_store()
    assert isinstance(store, CertificateStore)
    print("  ✅ create_default_certificate_store works")

    # Test get_x509_package_signer
    signer = get_x509_package_signer()
    assert isinstance(signer, X509PackageSigner)
    print("  ✅ get_x509_package_signer works")


def test_complete_workflow():
    """Test complete end-to-end workflow."""
    print("\n🔍 Testing complete signing workflow...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)
        private_key = generate_rsa_key()

        # 1. Create certificate
        certificate = signer.create_self_signed_certificate(
            private_key, subject_name="Integration Test Developer"
        )
        print("  ✅ Certificate created")

        # 2. Add to trusted store
        store.add_trusted_certificate(certificate, "integration-test")
        print("  ✅ Certificate added to store")

        # 3. Sign package
        package_data = b"Integration test package data"
        metadata = {"version": "1.0.0", "author": "Integration Test"}

        signature_info = signer.sign_package_with_certificate(
            package_data, certificate, private_key, metadata=metadata
        )
        print("  ✅ Package signed")

        # 4. Verify signature
        is_valid, error = signer.verify_package_signature(package_data, signature_info)
        assert is_valid is True
        print("  ✅ Signature verified successfully")


def test_multi_algorithm_signing():
    """Test signing with multiple algorithms."""
    print("\n🔍 Testing multi-algorithm signing...")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = CertificateStore(Path(temp_dir))
        signer = X509PackageSigner(store)

        package_data = b"Multi-algorithm test data"

        # Sign with RSA
        rsa_key = generate_rsa_key()
        rsa_cert = signer.create_self_signed_certificate(rsa_key, "RSA Developer")
        rsa_signature = signer.sign_package_with_certificate(
            package_data, rsa_cert, rsa_key
        )
        print("  ✅ RSA signature created")

        # Sign with Ed25519
        ed25519_key = generate_ed25519_key()
        ed25519_cert = signer.create_self_signed_certificate(
            ed25519_key, "Ed25519 Developer"
        )
        ed25519_signature = signer.sign_package_with_certificate(
            package_data, ed25519_cert, ed25519_key
        )
        print("  ✅ Ed25519 signature created")

        # Verify both
        is_valid_rsa, _ = signer.verify_package_signature(package_data, rsa_signature)
        is_valid_ed25519, _ = signer.verify_package_signature(
            package_data, ed25519_signature
        )

        assert is_valid_rsa is True
        assert is_valid_ed25519 is True
        print("  ✅ Both signatures verified")


def main():
    """Run all tests."""
    print("=" * 70)
    print("  CERTIFICATE MANAGER TEST SUITE")
    print("=" * 70)

    try:
        test_exception_classes()
        test_certificate_store_initialization()
        test_add_ca_certificate()
        test_add_trusted_certificate()
        test_get_certificate()
        test_get_ca_certificates()
        test_certificate_revocation()
        test_certificate_fingerprint()
        test_x509_signer_initialization()
        test_create_self_signed_certificate_rsa()
        test_create_self_signed_certificate_ed25519()
        test_certificate_extensions()
        test_create_certificate_signing_request()
        test_sign_package_rsa()
        test_sign_package_ed25519()
        test_verify_valid_signature()
        test_verify_tampered_data()
        test_verify_tampered_metadata()
        test_verify_revoked_certificate()
        test_validate_expired_certificate()
        test_validate_future_certificate()
        test_timestamp_creation_and_verification()
        test_sign_with_timestamp()
        test_helper_functions()
        test_complete_workflow()
        test_multi_algorithm_signing()

        print("\n" + "=" * 70)
        print("  ✅ ALL TESTS PASSED! 🎉")
        print("=" * 70)
        print("\n  Test categories: 9")
        print("  Test functions: 26")
        print("  Test cases: 50+")
        print("\n  Coverage:")
        print("    - Exception classes ✅")
        print("    - CertificateStore (8 features) ✅")
        print("    - X509PackageSigner (10+ features) ✅")
        print("    - RSA & Ed25519 algorithms ✅")
        print("    - Certificate validation ✅")
        print("    - Package signing & verification ✅")
        print("    - Revocation checking ✅")
        print("    - Timestamp support ✅")
        print("    - Helper functions ✅")
        print("\n  Security features tested:")
        print("    - X.509 certificate creation")
        print("    - Self-signed certificates")
        print("    - Certificate Signing Requests (CSR)")
        print("    - Package signing with RSA-PSS")
        print("    - Package signing with Ed25519")
        print("    - Signature verification")
        print("    - Certificate revocation")
        print("    - Certificate expiration")
        print("    - Tamper detection (data & metadata)")
        print("    - Timestamp creation & verification")
        print(
            "\n  This is a comprehensive test suite for production certificate management."
        )
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
