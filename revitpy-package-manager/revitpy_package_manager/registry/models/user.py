"""User and authentication related models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .package import Package


class User(Base):
    """User model for package registry authentication and authorization."""

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
    )

    # Authentication
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile information
    full_name: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(2048))
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Account tracking
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    packages: Mapped[list[Package]] = relationship(
        "Package", back_populates="owner", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list[APIKey]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(username='{self.username}', email='{self.email}')>"


class APIKey(Base):
    """API keys for programmatic access to the package registry."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_user", "user_id"),
        Index("idx_api_keys_token_hash", "token_hash"),
    )

    # Key identification
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Token information
    token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    token_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # First 8 chars for display

    # Permissions and scope
    scopes: Mapped[list[str]] = mapped_column(
        String(1000), nullable=False, default="read"
    )  # Comma-separated list of scopes

    # Key status and lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey(name='{self.name}', prefix='{self.token_prefix}')>"

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_scope_allowed(self, required_scope: str) -> bool:
        """Check if the API key has the required scope."""
        if not self.is_active or self.is_expired:
            return False

        allowed_scopes = [scope.strip() for scope in self.scopes.split(",")]
        return required_scope in allowed_scopes or "admin" in allowed_scopes
