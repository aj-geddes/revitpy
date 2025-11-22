"""Package-related database models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .security import PackageSignature, VulnerabilityReport


class Package(Base):
    """Main package model containing package metadata."""

    __tablename__ = "packages"
    __table_args__ = (
        Index("idx_packages_name", "name"),
        Index("idx_packages_owner", "owner_id"),
        Index("idx_packages_created", "created_at"),
    )

    # Package identification
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Package metadata
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # URLs and links
    homepage_url: Mapped[str | None] = mapped_column(String(2048))
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    documentation_url: Mapped[str | None] = mapped_column(String(2048))
    bug_tracker_url: Mapped[str | None] = mapped_column(String(2048))

    # Ownership and access
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Package status
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deprecation_message: Mapped[str | None] = mapped_column(Text)

    # Statistics
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    star_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    versions: Mapped[list[PackageVersion]] = relationship(
        "PackageVersion",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="PackageVersion.created_at.desc()",
    )

    owner = relationship("User", back_populates="packages")

    def __repr__(self) -> str:
        return f"<Package(name='{self.name}', versions={len(self.versions)})>"


class PackageVersion(Base):
    """Specific version of a package with its metadata and files."""

    __tablename__ = "package_versions"
    __table_args__ = (
        UniqueConstraint("package_id", "version", name="uq_package_version"),
        Index("idx_package_versions_package", "package_id"),
        Index("idx_package_versions_version", "version"),
        Index("idx_package_versions_revit", "supported_revit_versions"),
        Index("idx_package_versions_python", "python_version"),
    )

    # Version identification
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)

    # Version metadata
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    # Technical requirements
    python_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default=">=3.11"
    )
    supported_revit_versions: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    # File information
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash_md5: Mapped[str] = mapped_column(String(32), nullable=False)

    # Storage information
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(50), nullable=False, default="s3"
    )

    # Publishing info
    author: Mapped[str | None] = mapped_column(String(255))
    author_email: Mapped[str | None] = mapped_column(String(255))
    license: Mapped[str | None] = mapped_column(String(100))

    # Version status
    is_prerelease: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_yanked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    yank_reason: Mapped[str | None] = mapped_column(Text)

    # Upload information
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Statistics
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Additional metadata as JSON (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    package: Mapped[Package] = relationship("Package", back_populates="versions")
    dependencies: Mapped[list[PackageDependency]] = relationship(
        "PackageDependency", back_populates="version", cascade="all, delete-orphan"
    )
    uploaded_by = relationship("User")
    signatures: Mapped[list[PackageSignature]] = relationship(
        "PackageSignature", back_populates="version", cascade="all, delete-orphan"
    )
    vulnerability_reports: Mapped[list[VulnerabilityReport]] = relationship(
        "VulnerabilityReport", back_populates="version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<PackageVersion(package='{self.package.name}', version='{self.version}')>"
        )


class PackageDependency(Base):
    """Dependencies for a specific package version."""

    __tablename__ = "package_dependencies"
    __table_args__ = (
        Index("idx_package_dependencies_version", "version_id"),
        Index("idx_package_dependencies_name", "dependency_name"),
    )

    # Dependency identification
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("package_versions.id"), nullable=False
    )
    dependency_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_constraint: Mapped[str] = mapped_column(String(255), nullable=False)

    # Dependency metadata
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[str | None] = mapped_column(String(100))  # For optional dependencies
    dependency_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="runtime",  # runtime, build, test, dev
    )

    # Relationships
    version: Mapped[PackageVersion] = relationship(
        "PackageVersion", back_populates="dependencies"
    )

    def __repr__(self) -> str:
        return f"<PackageDependency(name='{self.dependency_name}', constraint='{self.version_constraint}')>"
