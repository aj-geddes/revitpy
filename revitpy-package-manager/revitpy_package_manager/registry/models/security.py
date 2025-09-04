"""Security-related models for package signing and vulnerability tracking."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import ARRAY, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PackageSignature(Base):
    """Digital signatures for package verification."""
    
    __tablename__ = "package_signatures"
    __table_args__ = (
        Index("idx_package_signatures_version", "version_id"),
        Index("idx_package_signatures_signer", "signer_id"),
        Index("idx_package_signatures_algorithm", "algorithm"),
    )

    # Signature identification
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_versions.id"),
        nullable=False
    )
    signer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Cryptographic information
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)  # RSA, ECDSA, EdDSA
    signature: Mapped[str] = mapped_column(Text, nullable=False)  # Base64 encoded signature
    public_key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Signature metadata
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Verification status
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verification_error: Mapped[Optional[str]] = mapped_column(Text)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Additional metadata
    signature_metadata: Mapped[Dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    version = relationship("PackageVersion", back_populates="signatures")
    signer = relationship("User")
    
    def __repr__(self) -> str:
        return f"<PackageSignature(version='{self.version.version}', algorithm='{self.algorithm}')>"


class VulnerabilityReport(Base):
    """Security vulnerability reports for packages."""
    
    __tablename__ = "vulnerability_reports"
    __table_args__ = (
        Index("idx_vulnerability_reports_version", "version_id"),
        Index("idx_vulnerability_reports_severity", "severity"),
        Index("idx_vulnerability_reports_status", "status"),
        Index("idx_vulnerability_reports_cve", "cve_id"),
    )

    # Vulnerability identification
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_versions.id"),
        nullable=False
    )
    
    # Vulnerability details
    vulnerability_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cve_id: Mapped[Optional[str]] = mapped_column(String(20))  # CVE-2023-12345
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Severity and scoring
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium"  # critical, high, medium, low, info
    )
    cvss_score: Mapped[Optional[float]] = mapped_column(Float)
    cvss_vector: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Affected versions
    affected_versions: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    fixed_in_version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Source information
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # NVD, GitHub, OSV, etc.
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    
    # Discovery and reporting
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_by: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open"  # open, confirmed, fixed, false_positive, wont_fix
    )
    
    # Additional details
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    references: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    vulnerability_metadata: Mapped[Dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    version = relationship("PackageVersion", back_populates="vulnerability_reports")
    
    def __repr__(self) -> str:
        return f"<VulnerabilityReport(id='{self.vulnerability_id}', severity='{self.severity}')>"


class ScanResult(Base):
    """Results of security scans performed on packages."""
    
    __tablename__ = "scan_results"
    __table_args__ = (
        Index("idx_scan_results_version", "version_id"),
        Index("idx_scan_results_scanner", "scanner_name"),
        Index("idx_scan_results_status", "status"),
    )

    # Scan identification
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_versions.id"),
        nullable=False
    )
    
    # Scanner information
    scanner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(50), nullable=False)
    scan_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # malware, vulnerability, license, quality
    
    # Scan execution
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration: Mapped[Optional[int]] = mapped_column(Integer)  # seconds
    
    # Results
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # running, completed, failed, timeout
    
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    score: Mapped[Optional[float]] = mapped_column(Float)  # 0.0 to 1.0
    
    # Findings
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Detailed results
    results_summary: Mapped[str] = mapped_column(Text)
    detailed_results: Mapped[Dict] = mapped_column(JSONB, default=dict)
    
    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    version = relationship("PackageVersion")
    
    def __repr__(self) -> str:
        return f"<ScanResult(scanner='{self.scanner_name}', status='{self.status}', findings={self.findings_count})>"


class TrustedPublisher(Base):
    """Trusted publishers for package verification."""
    
    __tablename__ = "trusted_publishers"
    __table_args__ = (
        Index("idx_trusted_publishers_user", "user_id"),
        Index("idx_trusted_publishers_type", "publisher_type"),
    )

    # Publisher identification
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Publisher details
    publisher_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # github, gitlab, jenkins, etc.
    
    publisher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repository_url: Mapped[Optional[str]] = mapped_column(String(2048))
    
    # Verification details
    verification_token: Mapped[str] = mapped_column(String(512), nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Publisher status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trust_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="verified"  # verified, trusted, premium
    )
    
    # Configuration
    allowed_packages: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    configuration: Mapped[Dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self) -> str:
        return f"<TrustedPublisher(type='{self.publisher_type}', name='{self.publisher_name}')>"