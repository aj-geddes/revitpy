"""Pydantic schemas for API request/response models."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    website_url: Optional[HttpUrl] = None
    company: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    """Schema for user creation."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for user updates."""
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    website_url: Optional[HttpUrl] = None
    company: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)


class UserResponse(UserBase):
    """Schema for user responses."""
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PackageBase(BaseModel):
    """Base package schema."""
    name: str = Field(..., min_length=1, max_length=255)
    summary: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    homepage_url: Optional[HttpUrl] = None
    repository_url: Optional[HttpUrl] = None
    documentation_url: Optional[HttpUrl] = None
    bug_tracker_url: Optional[HttpUrl] = None


class PackageCreate(PackageBase):
    """Schema for package creation."""
    pass


class PackageUpdate(BaseModel):
    """Schema for package updates."""
    summary: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    homepage_url: Optional[HttpUrl] = None
    repository_url: Optional[HttpUrl] = None
    documentation_url: Optional[HttpUrl] = None
    bug_tracker_url: Optional[HttpUrl] = None


class PackageResponse(PackageBase):
    """Schema for package responses."""
    id: uuid.UUID
    normalized_name: str
    owner_id: uuid.UUID
    is_private: bool
    is_published: bool
    is_deprecated: bool
    deprecation_message: Optional[str] = None
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
    extra: Optional[str] = Field(None, max_length=100)
    dependency_type: str = Field(default="runtime")


class DependencyResponse(DependencyBase):
    """Schema for dependency responses."""
    id: uuid.UUID

    class Config:
        from_attributes = True


class PackageVersionBase(BaseModel):
    """Base package version schema."""
    version: str = Field(..., min_length=1, max_length=100)
    summary: Optional[str] = None
    description: Optional[str] = None
    python_version: str = Field(default=">=3.11", max_length=50)
    supported_revit_versions: List[str] = Field(default_factory=list)
    author: Optional[str] = Field(None, max_length=255)
    author_email: Optional[EmailStr] = None
    license: Optional[str] = Field(None, max_length=100)
    is_prerelease: bool = False
    metadata: Dict = Field(default_factory=dict)


class PackageVersionCreate(PackageVersionBase):
    """Schema for package version creation."""
    dependencies: List[DependencyBase] = Field(default_factory=list)


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
    yank_reason: Optional[str] = None
    download_count: int
    created_at: datetime
    dependencies: List[DependencyResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PackageVersionUpdate(BaseModel):
    """Schema for package version updates."""
    is_yanked: bool
    yank_reason: Optional[str] = None


class PackageListResponse(BaseModel):
    """Schema for package list responses."""
    packages: List[PackageResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class PackageSearchResponse(BaseModel):
    """Schema for package search responses."""
    packages: List[PackageResponse]
    total: int
    query: str
    page: int
    per_page: int


class APIKeyBase(BaseModel):
    """Base API key schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: str = Field(default="read")
    expires_at: Optional[datetime] = None


class APIKeyCreate(APIKeyBase):
    """Schema for API key creation."""
    pass


class APIKeyResponse(BaseModel):
    """Schema for API key responses."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    token_prefix: str
    scopes: str
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
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
    version_breakdown: Dict[str, int]
    country_breakdown: Dict[str, int]


class VulnerabilityReportResponse(BaseModel):
    """Schema for vulnerability report responses."""
    id: uuid.UUID
    vulnerability_id: str
    cve_id: Optional[str]
    title: str
    description: str
    severity: str
    cvss_score: Optional[float]
    affected_versions: List[str]
    fixed_in_version: Optional[str]
    source: str
    source_url: Optional[str]
    discovered_at: datetime
    status: str
    tags: List[str]
    references: List[str]

    class Config:
        from_attributes = True


class ScanResultResponse(BaseModel):
    """Schema for scan result responses."""
    id: uuid.UUID
    scanner_name: str
    scanner_version: str
    scan_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    passed: Optional[bool]
    score: Optional[float]
    findings_count: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    results_summary: Optional[str]

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
    details: Optional[Dict] = None