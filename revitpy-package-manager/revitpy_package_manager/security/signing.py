"""Package signing and verification system."""

import base64
import hashlib
import os
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


class PackageSigner:
    """Package signing utilities using modern cryptographic standards."""

    SUPPORTED_ALGORITHMS = {
        "Ed25519": {
            "key_type": ed25519.Ed25519PrivateKey,
            "public_key_type": ed25519.Ed25519PublicKey,
            "key_size": None,  # Ed25519 has fixed key size
        },
        "RSA-PSS": {
            "key_type": rsa.RSAPrivateKey,
            "public_key_type": rsa.RSAPublicKey,
            "key_size": 3072,  # Minimum recommended size for RSA
        },
    }

    def __init__(self, algorithm: str = "Ed25519"):
        """Initialize the package signer.

        Args:
            algorithm: Signing algorithm to use ('Ed25519' or 'RSA-PSS')
        """
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        self.algorithm = algorithm
        self.algorithm_info = self.SUPPORTED_ALGORITHMS[algorithm]

    def generate_key_pair(self) -> tuple[bytes, bytes]:
        """Generate a new key pair for signing.

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        if self.algorithm == "Ed25519":
            private_key = Ed25519PrivateKey.generate()
        elif self.algorithm == "RSA-PSS":
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.algorithm_info["key_size"],
                backend=default_backend(),
            )
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem, public_pem

    def generate_key_pair_to_files(
        self,
        private_key_path: Path,
        public_key_path: Path,
        passphrase: str | None = None,
    ) -> None:
        """Generate and save key pair to files.

        Args:
            private_key_path: Path to save private key
            public_key_path: Path to save public key
            passphrase: Optional passphrase to encrypt private key
        """
        private_pem, public_pem = self.generate_key_pair()

        # If passphrase is provided, encrypt the private key
        if passphrase:
            private_key = serialization.load_pem_private_key(
                private_pem, password=None, backend=default_backend()
            )
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    passphrase.encode()
                ),
            )

        # Save keys to files
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        public_key_path.parent.mkdir(parents=True, exist_ok=True)

        private_key_path.write_bytes(private_pem)
        public_key_path.write_bytes(public_pem)

        # Set restrictive permissions on private key
        os.chmod(private_key_path, 0o600)

    def load_private_key(
        self, key_data: bytes, passphrase: str | None = None
    ) -> Ed25519PrivateKey | RSAPrivateKey:
        """Load a private key from PEM data."""
        password = passphrase.encode() if passphrase else None
        return serialization.load_pem_private_key(
            key_data, password=password, backend=default_backend()
        )

    def load_public_key(self, key_data: bytes) -> Ed25519PublicKey | RSAPublicKey:
        """Load a public key from PEM data."""
        return serialization.load_pem_public_key(key_data, backend=default_backend())

    def sign_data(
        self, data: bytes, private_key: Ed25519PrivateKey | RSAPrivateKey
    ) -> bytes:
        """Sign data with a private key."""
        if self.algorithm == "Ed25519":
            return private_key.sign(data)
        elif self.algorithm == "RSA-PSS":
            return private_key.sign(
                data,
                rsa.PSS(mgf=rsa.MGF1(hashes.SHA256()), salt_length=rsa.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")

    def verify_signature(
        self, data: bytes, signature: bytes, public_key: Ed25519PublicKey | RSAPublicKey
    ) -> bool:
        """Verify a signature against data using a public key."""
        try:
            if self.algorithm == "Ed25519":
                public_key.verify(signature, data)
                return True
            elif self.algorithm == "RSA-PSS":
                public_key.verify(
                    signature,
                    data,
                    rsa.PSS(
                        mgf=rsa.MGF1(hashes.SHA256()), salt_length=rsa.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256(),
                )
                return True
        except Exception:
            return False

        return False

    def get_public_key_fingerprint(self, public_key: bytes) -> str:
        """Generate a SHA-256 fingerprint of a public key."""
        return hashlib.sha256(public_key).hexdigest()


class PackageSignatureManager:
    """High-level package signature management."""

    def __init__(self, algorithm: str = "Ed25519"):
        self.signer = PackageSigner(algorithm)
        self.algorithm = algorithm

    def sign_package(
        self,
        package_data: bytes,
        private_key_path: Path,
        passphrase: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Sign a package and return signature metadata.

        Args:
            package_data: The package file content
            private_key_path: Path to private key file
            passphrase: Optional passphrase for private key
            metadata: Additional metadata to include in signature

        Returns:
            Dictionary containing signature and metadata
        """
        # Load private key
        private_key_pem = private_key_path.read_bytes()
        private_key = self.signer.load_private_key(private_key_pem, passphrase)

        # Get public key and fingerprint
        public_key = private_key.public_key()
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        public_key_fingerprint = self.signer.get_public_key_fingerprint(public_key_pem)

        # Create data to sign (package data + metadata hash)
        package_hash = hashlib.sha256(package_data).hexdigest()
        metadata_str = str(sorted((metadata or {}).items()))
        metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()

        sign_data = f"{package_hash}:{metadata_hash}".encode()

        # Sign the data
        signature = self.signer.sign_data(sign_data, private_key)

        return {
            "algorithm": self.algorithm,
            "signature": base64.b64encode(signature).decode(),
            "public_key_fingerprint": public_key_fingerprint,
            "package_hash": package_hash,
            "metadata_hash": metadata_hash,
            "signed_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

    def verify_package_signature(
        self,
        package_data: bytes,
        signature_info: dict,
        public_key: bytes,
        trusted_fingerprints: set | None = None,
    ) -> tuple[bool, str | None]:
        """Verify a package signature.

        Args:
            package_data: The package file content
            signature_info: Signature metadata dictionary
            public_key: Public key PEM data
            trusted_fingerprints: Optional set of trusted key fingerprints

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if we trust this public key
            public_key_fingerprint = self.signer.get_public_key_fingerprint(public_key)
            if (
                trusted_fingerprints
                and public_key_fingerprint not in trusted_fingerprints
            ):
                return (
                    False,
                    f"Public key fingerprint {public_key_fingerprint} is not trusted",
                )

            # Verify the signature info matches our expectations
            if signature_info.get("algorithm") != self.algorithm:
                return (
                    False,
                    f"Algorithm mismatch: expected {self.algorithm}, got {signature_info.get('algorithm')}",
                )

            if signature_info.get("public_key_fingerprint") != public_key_fingerprint:
                return False, "Public key fingerprint mismatch"

            # Verify package hash
            package_hash = hashlib.sha256(package_data).hexdigest()
            if signature_info.get("package_hash") != package_hash:
                return False, "Package hash mismatch - file may have been tampered with"

            # Verify metadata hash
            metadata_str = str(sorted(signature_info.get("metadata", {}).items()))
            metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()
            if signature_info.get("metadata_hash") != metadata_hash:
                return False, "Metadata hash mismatch"

            # Recreate signed data
            sign_data = f"{package_hash}:{metadata_hash}".encode()

            # Decode signature
            signature = base64.b64decode(signature_info["signature"])

            # Load public key and verify
            public_key_obj = self.signer.load_public_key(public_key)
            is_valid = self.signer.verify_signature(
                sign_data, signature, public_key_obj
            )

            if not is_valid:
                return False, "Signature verification failed"

            return True, None

        except Exception as e:
            return False, f"Signature verification error: {str(e)}"

    def create_keyring_entry(
        self, public_key: bytes, owner: str, purpose: str = "package-signing"
    ) -> dict:
        """Create a keyring entry for a trusted public key.

        Args:
            public_key: Public key PEM data
            owner: Name/identifier of the key owner
            purpose: Purpose of this key

        Returns:
            Dictionary containing keyring entry
        """
        fingerprint = self.signer.get_public_key_fingerprint(public_key)

        return {
            "fingerprint": fingerprint,
            "public_key": base64.b64encode(public_key).decode(),
            "algorithm": self.algorithm,
            "owner": owner,
            "purpose": purpose,
            "created_at": datetime.utcnow().isoformat(),
        }


# Global package signature manager instance
default_signature_manager = PackageSignatureManager()


def get_signature_manager() -> PackageSignatureManager:
    """Get the default package signature manager."""
    return default_signature_manager
