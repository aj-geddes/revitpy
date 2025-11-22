"""X.509 Certificate-based package signing and certificate management system."""

import base64
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from cryptography.x509 import (
    Certificate,
)
from cryptography.x509.oid import NameOID


class CertificateValidationError(Exception):
    """Exception raised when certificate validation fails."""

    pass


class CertificateRevocationError(Exception):
    """Exception raised when certificate is revoked."""

    pass


class CertificateStore:
    """Certificate store for managing trusted certificates and CRLs."""

    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.mkdir(parents=True, exist_ok=True)

        # Initialize subdirectories
        self.ca_certs_path = self.store_path / "ca_certificates"
        self.trusted_certs_path = self.store_path / "trusted_certificates"
        self.revoked_certs_path = self.store_path / "revoked_certificates"
        self.crl_path = self.store_path / "crls"

        for path in [
            self.ca_certs_path,
            self.trusted_certs_path,
            self.revoked_certs_path,
            self.crl_path,
        ]:
            path.mkdir(exist_ok=True)

    def add_ca_certificate(self, cert: Certificate, alias: str) -> str:
        """Add a CA certificate to the trust store."""
        cert_fingerprint = self._get_certificate_fingerprint(cert)
        cert_path = self.ca_certs_path / f"{alias}_{cert_fingerprint}.pem"

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Create metadata file
        metadata = {
            "alias": alias,
            "fingerprint": cert_fingerprint,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_valid_before": cert.not_valid_before.isoformat(),
            "not_valid_after": cert.not_valid_after.isoformat(),
            "added_at": datetime.utcnow().isoformat(),
            "is_ca": True,
        }

        metadata_path = self.ca_certs_path / f"{alias}_{cert_fingerprint}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return cert_fingerprint

    def add_trusted_certificate(
        self, cert: Certificate, alias: str, purpose: str = "code-signing"
    ) -> str:
        """Add a trusted certificate to the store."""
        cert_fingerprint = self._get_certificate_fingerprint(cert)
        cert_path = self.trusted_certs_path / f"{alias}_{cert_fingerprint}.pem"

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Create metadata file
        metadata = {
            "alias": alias,
            "fingerprint": cert_fingerprint,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_valid_before": cert.not_valid_before.isoformat(),
            "not_valid_after": cert.not_valid_after.isoformat(),
            "added_at": datetime.utcnow().isoformat(),
            "purpose": purpose,
            "is_ca": False,
        }

        metadata_path = self.trusted_certs_path / f"{alias}_{cert_fingerprint}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return cert_fingerprint

    def get_certificate(self, fingerprint: str) -> Certificate | None:
        """Get a certificate by fingerprint from any store."""
        for cert_dir in [self.ca_certs_path, self.trusted_certs_path]:
            for cert_file in cert_dir.glob(f"*{fingerprint}.pem"):
                with open(cert_file, "rb") as f:
                    return x509.load_pem_x509_certificate(f.read(), default_backend())
        return None

    def get_ca_certificates(self) -> list[Certificate]:
        """Get all CA certificates from the store."""
        certificates = []
        for cert_file in self.ca_certs_path.glob("*.pem"):
            with open(cert_file, "rb") as f:
                certificates.append(
                    x509.load_pem_x509_certificate(f.read(), default_backend())
                )
        return certificates

    def is_certificate_revoked(self, cert: Certificate) -> bool:
        """Check if a certificate is revoked using CRLs."""
        cert_fingerprint = self._get_certificate_fingerprint(cert)

        # Check local revocation list
        revoked_file = self.revoked_certs_path / f"{cert_fingerprint}.revoked"
        if revoked_file.exists():
            return True

        # Check CRLs for the issuer
        return self._check_crl_revocation(cert)

    def revoke_certificate(
        self, cert: Certificate, reason: str = "unspecified"
    ) -> None:
        """Add a certificate to the local revocation list."""
        cert_fingerprint = self._get_certificate_fingerprint(cert)
        revocation_info = {
            "fingerprint": cert_fingerprint,
            "subject": cert.subject.rfc4514_string(),
            "revoked_at": datetime.utcnow().isoformat(),
            "reason": reason,
        }

        revoked_file = self.revoked_certs_path / f"{cert_fingerprint}.revoked"
        with open(revoked_file, "w") as f:
            json.dump(revocation_info, f, indent=2)

    def update_crl(self, crl_url: str) -> bool:
        """Download and update a Certificate Revocation List."""
        try:
            # Parse URL to create filename
            parsed_url = urlparse(crl_url)
            crl_filename = f"{parsed_url.netloc}{parsed_url.path}".replace(
                "/", "_"
            ).replace(":", "_")
            crl_file = self.crl_path / f"{crl_filename}.crl"

            # Download CRL
            with httpx.Client() as client:
                response = client.get(crl_url, timeout=30.0)
                response.raise_for_status()

                # Try to parse as DER first, then PEM
                try:
                    crl = x509.load_der_x509_crl(response.content, default_backend())
                except ValueError:
                    crl = x509.load_pem_x509_crl(response.content, default_backend())

                # Verify CRL signature against known CA certificates
                ca_certs = self.get_ca_certificates()
                crl_verified = False

                for ca_cert in ca_certs:
                    try:
                        ca_cert.public_key().verify(
                            crl.signature,
                            crl.tbs_certlist_bytes,
                            crl.signature_algorithm_oid._name,
                        )
                        crl_verified = True
                        break
                    except Exception:
                        continue

                if not crl_verified:
                    raise CertificateValidationError(
                        "CRL signature verification failed"
                    )

                # Save CRL
                with open(crl_file, "wb") as f:
                    f.write(response.content)

                # Save metadata
                metadata = {
                    "url": crl_url,
                    "issuer": crl.issuer.rfc4514_string(),
                    "last_update": crl.last_update.isoformat(),
                    "next_update": (
                        crl.next_update.isoformat() if crl.next_update else None
                    ),
                    "downloaded_at": datetime.utcnow().isoformat(),
                }

                metadata_file = self.crl_path / f"{crl_filename}.json"
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)

                return True

        except Exception as e:
            print(f"Failed to update CRL from {crl_url}: {e}")
            return False

    def _get_certificate_fingerprint(self, cert: Certificate) -> str:
        """Get SHA-256 fingerprint of a certificate."""
        return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()

    def _check_crl_revocation(self, cert: Certificate) -> bool:
        """Check if certificate is revoked using downloaded CRLs."""
        cert_serial = cert.serial_number
        issuer_name = cert.issuer.rfc4514_string()

        for crl_file in self.crl_path.glob("*.crl"):
            try:
                with open(crl_file, "rb") as f:
                    crl_data = f.read()

                # Try DER first, then PEM
                try:
                    crl = x509.load_der_x509_crl(crl_data, default_backend())
                except ValueError:
                    crl = x509.load_pem_x509_crl(crl_data, default_backend())

                # Check if this CRL is for the certificate's issuer
                if crl.issuer.rfc4514_string() == issuer_name:
                    # Check if certificate is in this CRL
                    for revoked_cert in crl:
                        if revoked_cert.serial_number == cert_serial:
                            return True
            except Exception:
                continue

        return False


class X509PackageSigner:
    """X.509 certificate-based package signer with enterprise features."""

    def __init__(self, certificate_store: CertificateStore):
        self.certificate_store = certificate_store

    def create_self_signed_certificate(
        self,
        private_key: rsa.RSAPrivateKey | ed25519.Ed25519PrivateKey,
        subject_name: str,
        organization: str = "RevitPy Developer",
        country: str = "US",
        validity_days: int = 365,
    ) -> Certificate:
        """Create a self-signed certificate for package signing."""

        # Build subject name
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
            ]
        )

        # Create certificate
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)  # Self-signed
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow())
        builder = builder.not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        )

        # Add extensions
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

        # Sign the certificate
        # Ed25519 and Ed448 don't use a hash algorithm (sign with None)
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            certificate = builder.sign(private_key, None, default_backend())
        else:
            certificate = builder.sign(private_key, hashes.SHA256(), default_backend())

        return certificate

    def create_certificate_signing_request(
        self,
        private_key: rsa.RSAPrivateKey | ed25519.Ed25519PrivateKey,
        subject_name: str,
        organization: str,
        email: str,
        country: str = "US",
    ) -> x509.CertificateSigningRequest:
        """Create a Certificate Signing Request for CA signing."""

        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
                x509.NameAttribute(NameOID.EMAIL_ADDRESS, email),
            ]
        )

        builder = x509.CertificateSigningRequestBuilder()
        builder = builder.subject_name(subject)

        # Add Subject Alternative Name
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.RFC822Name(email),
                ]
            ),
            critical=False,
        )

        # Add Key Usage
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

        # Add Extended Key Usage
        builder = builder.add_extension(
            x509.ExtendedKeyUsage(
                [
                    x509.oid.ExtendedKeyUsageOID.CODE_SIGNING,
                ]
            ),
            critical=True,
        )

        # Sign the CSR
        # Ed25519 and Ed448 don't use a hash algorithm (sign with None)
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            csr = builder.sign(private_key, None, default_backend())
        else:
            csr = builder.sign(private_key, hashes.SHA256(), default_backend())

        return csr

    def sign_package_with_certificate(
        self,
        package_data: bytes,
        certificate: Certificate,
        private_key: rsa.RSAPrivateKey | ed25519.Ed25519PrivateKey,
        timestamp_url: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Sign a package using X.509 certificate."""

        # Validate certificate first
        self._validate_certificate(certificate)

        # Create package hash
        package_hash = hashlib.sha256(package_data).hexdigest()

        # Create metadata hash
        metadata = metadata or {}
        metadata_str = json.dumps(metadata, sort_keys=True)
        metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()

        # Data to sign
        sign_data = f"{package_hash}:{metadata_hash}".encode()

        # Sign the data
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            signature = private_key.sign(sign_data)
        elif isinstance(private_key, rsa.RSAPrivateKey):
            signature = private_key.sign(
                sign_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        else:
            raise ValueError("Unsupported private key type")

        # Get certificate info
        cert_fingerprint = self.certificate_store._get_certificate_fingerprint(
            certificate
        )

        # Create timestamp if URL provided
        timestamp_info = None
        if timestamp_url:
            timestamp_info = self._create_timestamp(sign_data, timestamp_url)

        return {
            "signature_version": "2.0",
            "algorithm": (
                "Ed25519"
                if isinstance(private_key, ed25519.Ed25519PrivateKey)
                else "RSA-PSS"
            ),
            "signature": base64.b64encode(signature).decode(),
            "certificate": base64.b64encode(
                certificate.public_bytes(serialization.Encoding.PEM)
            ).decode(),
            "certificate_fingerprint": cert_fingerprint,
            "certificate_subject": certificate.subject.rfc4514_string(),
            "certificate_issuer": certificate.issuer.rfc4514_string(),
            "package_hash": package_hash,
            "metadata_hash": metadata_hash,
            "signed_at": datetime.utcnow().isoformat(),
            "timestamp": timestamp_info,
            "metadata": metadata,
        }

    def verify_package_signature(
        self, package_data: bytes, signature_info: dict
    ) -> tuple[bool, str | None]:
        """Verify a package signature using X.509 certificate."""

        try:
            # Load certificate from signature
            cert_pem = base64.b64decode(signature_info["certificate"])
            certificate = x509.load_pem_x509_certificate(cert_pem, default_backend())

            # Validate certificate
            try:
                self._validate_certificate(certificate)
            except (CertificateValidationError, CertificateRevocationError) as e:
                return False, str(e)

            # Verify package hash
            package_hash = hashlib.sha256(package_data).hexdigest()
            if signature_info.get("package_hash") != package_hash:
                return False, "Package hash mismatch - file may have been tampered with"

            # Verify metadata hash
            metadata_str = json.dumps(
                signature_info.get("metadata", {}), sort_keys=True
            )
            metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()
            if signature_info.get("metadata_hash") != metadata_hash:
                return False, "Metadata hash mismatch"

            # Recreate signed data
            sign_data = f"{package_hash}:{metadata_hash}".encode()

            # Decode signature
            signature = base64.b64decode(signature_info["signature"])

            # Verify signature
            public_key = certificate.public_key()
            algorithm = signature_info.get("algorithm", "RSA-PSS")

            try:
                if algorithm == "Ed25519" and isinstance(
                    public_key, ed25519.Ed25519PublicKey
                ):
                    public_key.verify(signature, sign_data)
                elif algorithm == "RSA-PSS" and isinstance(
                    public_key, rsa.RSAPublicKey
                ):
                    public_key.verify(
                        signature,
                        sign_data,
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH,
                        ),
                        hashes.SHA256(),
                    )
                else:
                    return False, f"Unsupported algorithm or key type: {algorithm}"
            except Exception as e:
                return False, f"Signature verification failed: {e}"

            # Verify timestamp if present
            if signature_info.get("timestamp"):
                timestamp_valid = self._verify_timestamp(
                    sign_data, signature_info["timestamp"]
                )
                if not timestamp_valid:
                    return False, "Timestamp verification failed"

            return True, None

        except Exception as e:
            return False, f"Signature verification error: {str(e)}"

    def _validate_certificate(self, certificate: Certificate) -> None:
        """Validate certificate for code signing."""

        # Check if certificate is expired
        now = datetime.utcnow()
        if now < certificate.not_valid_before:
            raise CertificateValidationError("Certificate is not yet valid")
        if now > certificate.not_valid_after:
            raise CertificateValidationError("Certificate has expired")

        # Check if certificate is revoked
        if self.certificate_store.is_certificate_revoked(certificate):
            raise CertificateRevocationError("Certificate has been revoked")

        # Check key usage
        try:
            key_usage = certificate.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.KEY_USAGE
            ).value
            if not key_usage.digital_signature:
                raise CertificateValidationError(
                    "Certificate does not allow digital signatures"
                )
        except x509.ExtensionNotFound:
            pass  # Key usage extension is optional

        # Check extended key usage for code signing
        try:
            ext_key_usage = certificate.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
            ).value
            if x509.oid.ExtendedKeyUsageOID.CODE_SIGNING not in ext_key_usage:
                raise CertificateValidationError(
                    "Certificate is not valid for code signing"
                )
        except x509.ExtensionNotFound:
            pass  # Extended key usage extension is optional

        # Verify certificate chain if not self-signed
        if certificate.issuer != certificate.subject:
            self._verify_certificate_chain(certificate)

    def _verify_certificate_chain(self, certificate: Certificate) -> None:
        """Verify certificate chain against trusted CA certificates."""

        ca_certs = self.certificate_store.get_ca_certificates()

        # Find the issuer certificate
        issuer_cert = None
        for ca_cert in ca_certs:
            if ca_cert.subject == certificate.issuer:
                issuer_cert = ca_cert
                break

        if not issuer_cert:
            raise CertificateValidationError(
                "Certificate issuer not found in trusted CA store"
            )

        # Verify certificate signature
        try:
            issuer_cert.public_key().verify(
                certificate.signature,
                certificate.tbs_certificate_bytes,
                certificate.signature_algorithm_oid._name,
            )
        except Exception as e:
            raise CertificateValidationError(
                f"Certificate signature verification failed: {e}"
            ) from e

        # Recursively verify issuer certificate if not self-signed
        if issuer_cert.issuer != issuer_cert.subject:
            self._verify_certificate_chain(issuer_cert)

    def _create_timestamp(self, data: bytes, timestamp_url: str) -> dict | None:
        """Create a timestamp for the signed data."""
        try:
            # This is a simplified timestamp implementation
            # In production, you would use RFC 3161 timestamp servers
            timestamp_hash = hashlib.sha256(data).hexdigest()
            timestamp = datetime.utcnow().isoformat()

            return {
                "url": timestamp_url,
                "timestamp": timestamp,
                "data_hash": timestamp_hash,
                "algorithm": "SHA256",
            }
        except Exception:
            return None

    def _verify_timestamp(self, data: bytes, timestamp_info: dict) -> bool:
        """Verify a timestamp."""
        try:
            expected_hash = hashlib.sha256(data).hexdigest()
            return timestamp_info.get("data_hash") == expected_hash
        except Exception:
            return False


def create_default_certificate_store() -> CertificateStore:
    """Create a default certificate store in the user's config directory."""
    config_dir = Path.home() / ".revitpy" / "certificates"
    return CertificateStore(config_dir)


def get_x509_package_signer() -> X509PackageSigner:
    """Get the default X.509 package signer."""
    store = create_default_certificate_store()
    return X509PackageSigner(store)
