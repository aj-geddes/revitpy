"""Download tracking and analytics models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DownloadStats(Base):
    """Track package download statistics for analytics."""
    
    __tablename__ = "download_stats"
    __table_args__ = (
        Index("idx_download_stats_package", "package_id"),
        Index("idx_download_stats_version", "version_id"),
        Index("idx_download_stats_date", "downloaded_at"),
        Index("idx_download_stats_country", "country_code"),
        Index("idx_download_stats_revit", "revit_version"),
    )

    # Download identification
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("packages.id"),
        nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_versions.id"),
        nullable=False
    )
    
    # Download metadata
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Client information
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    
    # Environment information
    python_version: Mapped[Optional[str]] = mapped_column(String(50))
    revit_version: Mapped[Optional[str]] = mapped_column(String(50))
    platform: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Installation context
    installer_name: Mapped[Optional[str]] = mapped_column(String(100))  # pip, revitpy-install, etc.
    installer_version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # File information
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_duration: Mapped[Optional[int]] = mapped_column(Integer)  # milliseconds
    
    # Success tracking
    download_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Relationships
    package = relationship("Package")
    version = relationship("PackageVersion")
    
    def __repr__(self) -> str:
        return f"<DownloadStats(package='{self.package.name}', version='{self.version.version}', date='{self.downloaded_at}')>"


class DailyDownloadSummary(Base):
    """Aggregated daily download statistics for reporting."""
    
    __tablename__ = "daily_download_summary"
    __table_args__ = (
        Index("idx_daily_summary_package", "package_id"),
        Index("idx_daily_summary_date", "date"),
    )

    # Summary identification
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("packages.id"),
        nullable=False
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    # Aggregated counts
    total_downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_ips: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Version breakdown (JSON field with version -> count mapping)
    version_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Geographic breakdown
    country_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Platform breakdown
    platform_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    package = relationship("Package")
    
    def __repr__(self) -> str:
        return f"<DailyDownloadSummary(package='{self.package.name}', date='{self.date}', downloads={self.total_downloads})>"