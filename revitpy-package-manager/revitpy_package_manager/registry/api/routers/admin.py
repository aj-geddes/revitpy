"""Administrative endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db_session
from ...models.package import Package
from ...models.security import ScanResult, VulnerabilityReport
from ...models.user import User
from ..schemas import (
    PackageResponse,
    ScanResultResponse,
    UserResponse,
    VulnerabilityReportResponse,
)
from .auth import get_current_superuser

router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
async def list_all_users(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """List all users (admin only)."""

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return users


@router.put("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """Deactivate a user (admin only)."""

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.is_active = False
    await db.commit()
    await db.refresh(user)

    return user


@router.put("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """Activate a user (admin only)."""

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.is_active = True
    await db.commit()
    await db.refresh(user)

    return user


@router.get("/packages", response_model=list[PackageResponse])
async def list_all_packages(
    include_private: bool = False,
    include_unpublished: bool = False,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """List all packages (admin only)."""

    query = select(Package)

    if not include_private:
        query = query.where(not Package.is_private)

    if not include_unpublished:
        query = query.where(Package.is_published)

    query = query.order_by(Package.created_at.desc())

    result = await db.execute(query)
    packages = result.scalars().all()

    return packages


@router.put("/packages/{package_name}/unpublish", response_model=PackageResponse)
async def unpublish_package(
    package_name: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """Unpublish a package (admin only)."""

    normalized_name = package_name.lower().replace("_", "-")

    result = await db.execute(
        select(Package).where(Package.normalized_name == normalized_name)
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )

    package.is_published = False
    await db.commit()
    await db.refresh(package)

    return package


@router.get(
    "/security/vulnerabilities", response_model=list[VulnerabilityReportResponse]
)
async def list_vulnerabilities(
    severity: str = None,
    status: str = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """List vulnerability reports (admin only)."""

    query = select(VulnerabilityReport)

    if severity:
        query = query.where(VulnerabilityReport.severity == severity)

    if status:
        query = query.where(VulnerabilityReport.status == status)

    query = query.order_by(VulnerabilityReport.discovered_at.desc())

    result = await db.execute(query)
    vulnerabilities = result.scalars().all()

    return vulnerabilities


@router.get("/security/scans", response_model=list[ScanResultResponse])
async def list_scan_results(
    scanner: str = None,
    status: str = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db_session),
):
    """List security scan results (admin only)."""

    query = select(ScanResult)

    if scanner:
        query = query.where(ScanResult.scanner_name == scanner)

    if status:
        query = query.where(ScanResult.status == status)

    query = query.order_by(ScanResult.started_at.desc())

    result = await db.execute(query)
    scan_results = result.scalars().all()

    return scan_results
