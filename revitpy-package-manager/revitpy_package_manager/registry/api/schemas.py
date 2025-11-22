"""Pydantic schemas for API request/response models."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: str | None = Field(None, max_length=255)
    bio: str | None = None
    website_url: HttpUrl | None = None
    company: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)


class UserCreate(UserBase):
    """Schema for user creation."""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for user updates."""

    full_name: str | None = Field(None, max_length=255)
    bio: str | None = None
    website_url: HttpUrl | None = None
    company: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)


class UserResponse(UserBase):
    """Schema for user responses."""

    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class PackageBase(BaseModel):
    """Base package schema."""

    name: str = Field(..., min_length=1, max_length=255)
    summary: str | None = None
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    homepage_url: HttpUrl | None = None
    repository_url: HttpUrl | None = None
    documentation_url: HttpUrl | None = None
    bug_tracker_url: HttpUrl | None = None


class PackageCreate(PackageBase):
    """Schema for package creation."""

    pass


class PackageUpdate(BaseModel):
    """Schema for package updates."""

    summary: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    categories: list[str] | None = None
    homepage_url: HttpUrl | None = None
    repository_url: HttpUrl | None = None
    documentation_url: HttpUrl | None = None
    bug_tracker_url: HttpUrl | None = None


class PackageResponse(PackageBase):
    """Schema for package responses."""

    id: uuid.UUID
    normalized_name: str
    owner_id: uuid.UUID
    is_private: bool
    is_published: bool
    is_deprecated: bool
    deprecation_message: str | None = None
    download_count: int
    star_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DependencyBase(BaseModel):
    """Base dependency schema."""

    dependency_name: str = Field(..., min_length=1, max_length=255)
    version_constraint: str = Field(..., min_length=1, max_length=255)
    is_optional: bool = False
    extra: str | None = Field(None, max_length=100)
    dependency_type: str = Field(default="runtime")


class DependencyResponse(DependencyBase):
    """Schema for dependency responses."""

    id: uuid.UUID

    class Config:
        from_attributes = True


class PackageVersionBase(BaseModel):
    """Base package version schema."""

    version: str = Field(..., min_length=1, max_length=100)
    summary: str | None = None
    description: str | None = None
    python_version: str = Field(default=">=3.11", max_length=50)
    supported_revit_versions: list[str] = Field(default_factory=list)
    author: str | None = Field(None, max_length=255)
    author_email: EmailStr | None = None
    license: str | None = Field(None, max_length=100)
    is_prerelease: bool = False
    metadata: dict = Field(default_factory=dict)


class PackageVersionCreate(PackageVersionBase):
    """Schema for package version creation."""

    dependencies: list[DependencyBase] = Field(default_factory=list)


class PackageVersionResponse(PackageVersionBase):
    """Schema for package version responses."""

    id: uuid.UUID
    package_id: uuid.UUID
    filename: str
    file_size: int
    file_hash_sha256: str
    file_hash_md5: str
    storage_path: str
    storage_backend: str
    uploaded_by_id: uuid.UUID
    is_yanked: bool
    yank_reason: str | None = None
    download_count: int
    created_at: datetime
    dependencies: list[DependencyResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PackageVersionUpdate(BaseModel):
    """Schema for package version updates."""

    is_yanked: bool
    yank_reason: str | None = None


class PackageListResponse(BaseModel):
    """Schema for package list responses."""

    packages: list[PackageResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class PackageSearchResponse(BaseModel):
    """Schema for package search responses."""

    packages: list[PackageResponse]
    total: int
    query: str
    page: int
    per_page: int


class APIKeyBase(BaseModel):
    """Base API key schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    scopes: str = Field(default="read")
    expires_at: datetime | None = None


class APIKeyCreate(APIKeyBase):
    """Schema for API key creation."""

    pass


class APIKeyResponse(BaseModel):
    """Schema for API key responses."""

    id: uuid.UUID
    name: str
    description: str | None
    token_prefix: str
    scopes: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyWithToken(APIKeyResponse):
    """Schema for API key responses including the full token (only on creation)."""

    token: str


class DownloadStatsResponse(BaseModel):
    """Schema for download statistics."""

    package_id: uuid.UUID
    total_downloads: int
    downloads_last_day: int
    downloads_last_week: int
    downloads_last_month: int
    version_breakdown: dict[str, int]
    country_breakdown: dict[str, int]


class VulnerabilityReportResponse(BaseModel):
    """Schema for vulnerability report responses."""

    id: uuid.UUID
    vulnerability_id: str
    cve_id: str | None
    title: str
    description: str
    severity: str
    cvss_score: float | None
    affected_versions: list[str]
    fixed_in_version: str | None
    source: str
    source_url: str | None
    discovered_at: datetime
    status: str
    tags: list[str]
    references: list[str]

    class Config:
        from_attributes = True


class ScanResultResponse(BaseModel):
    """Schema for scan result responses."""

    id: uuid.UUID
    scanner_name: str
    scanner_version: str
    scan_type: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    passed: bool | None
    score: float | None
    findings_count: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    results_summary: str | None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Schema for login requests."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Schema for login responses."""

    access_token: str
    token_type: str
    user: UserResponse


class HealthResponse(BaseModel):
    """Schema for health check responses."""

    status: str
    version: str
    database: str
    cache: str
    storage: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str
    message: str
    details: dict | None = None
