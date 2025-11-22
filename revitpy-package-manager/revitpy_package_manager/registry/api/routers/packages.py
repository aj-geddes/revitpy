"""Package management endpoints."""

import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_db_session
from ...models.download import DownloadStats
from ...models.package import Package, PackageDependency, PackageVersion
from ...models.user import User
from ...services.cache import CacheService
from ...services.storage import StorageService
from ..schemas import (
    DownloadStatsResponse,
    PackageCreate,
    PackageListResponse,
    PackageResponse,
    PackageSearchResponse,
    PackageUpdate,
    PackageVersionCreate,
    PackageVersionResponse,
)
from .auth import get_current_active_user

router = APIRouter()


def normalize_package_name(name: str) -> str:
    """Normalize package name for consistent storage and lookup."""
    return name.lower().replace("_", "-").replace(" ", "-")


@router.get("/", response_model=PackageListResponse)
async def list_packages(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    revit_version: str | None = Query(None, description="Filter by Revit version"),
    db: AsyncSession = Depends(get_db_session),
):
    """List packages with pagination and filtering."""

    query = select(Package).where(Package.is_published, not Package.is_private)

    # Apply filters
    if category:
        query = query.where(Package.categories.contains([category]))

    if revit_version:
        # Join with package versions to filter by Revit version
        query = query.join(PackageVersion).where(
            PackageVersion.supported_revit_versions.contains([revit_version])
        )

    # Count total packages
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page).order_by(desc(Package.download_count))

    result = await db.execute(query)
    packages = result.scalars().all()

    return PackageListResponse(
        packages=packages,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1,
    )


@router.get("/search", response_model=PackageSearchResponse)
async def search_packages(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=50, description="Items per page"),
    db: AsyncSession = Depends(get_db_session),
):
    """Search packages by name, summary, or keywords."""

    # Build search query
    search_term = f"%{q.lower()}%"
    query = select(Package).where(
        and_(
            Package.is_published,
            not Package.is_private,
            or_(
                Package.name.ilike(search_term),
                Package.summary.ilike(search_term),
                Package.description.ilike(search_term),
                Package.keywords.contains([q.lower()]),
            ),
        )
    )

    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page).order_by(desc(Package.download_count))

    result = await db.execute(query)
    packages = result.scalars().all()

    return PackageSearchResponse(
        packages=packages,
        total=total,
        query=q,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_data: PackageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new package."""

    normalized_name = normalize_package_name(package_data.name)

    # Check if package already exists
    result = await db.execute(
        select(Package).where(Package.normalized_name == normalized_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Package '{package_data.name}' already exists",
        )

    # Create package
    package = Package(
        name=package_data.name,
        normalized_name=normalized_name,
        summary=package_data.summary,
        description=package_data.description,
        keywords=package_data.keywords,
        categories=package_data.categories,
        homepage_url=(
            str(package_data.homepage_url) if package_data.homepage_url else None
        ),
        repository_url=(
            str(package_data.repository_url) if package_data.repository_url else None
        ),
        documentation_url=(
            str(package_data.documentation_url)
            if package_data.documentation_url
            else None
        ),
        bug_tracker_url=(
            str(package_data.bug_tracker_url) if package_data.bug_tracker_url else None
        ),
        owner_id=current_user.id,
    )

    db.add(package)
    await db.commit()
    await db.refresh(package)

    return package


@router.get("/{package_name}", response_model=PackageResponse)
async def get_package(package_name: str, db: AsyncSession = Depends(get_db_session)):
    """Get package details."""

    normalized_name = normalize_package_name(package_name)

    result = await db.execute(
        select(Package)
        .options(selectinload(Package.versions))
        .where(Package.normalized_name == normalized_name, Package.is_published)
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )

    return package


@router.put("/{package_name}", response_model=PackageResponse)
async def update_package(
    package_name: str,
    package_update: PackageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update package details."""

    normalized_name = normalize_package_name(package_name)

    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id,
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied",
        )

    # Update package fields
    for field, value in package_update.dict(exclude_unset=True).items():
        if hasattr(package, field):
            if (
                field
                in (
                    "homepage_url",
                    "repository_url",
                    "documentation_url",
                    "bug_tracker_url",
                )
                and value
            ):
                setattr(package, field, str(value))
            else:
                setattr(package, field, value)

    await db.commit()
    await db.refresh(package)

    return package


@router.delete("/{package_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_name: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a package (soft delete by unpublishing)."""

    normalized_name = normalize_package_name(package_name)

    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id,
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied",
        )

    # Soft delete by unpublishing
    package.is_published = False
    await db.commit()


@router.get("/{package_name}/versions", response_model=list[PackageVersionResponse])
async def list_package_versions(
    package_name: str,
    include_prereleases: bool = Query(False, description="Include prerelease versions"),
    db: AsyncSession = Depends(get_db_session),
):
    """List all versions of a package."""

    normalized_name = normalize_package_name(package_name)

    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name, Package.is_published
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )

    # Query versions
    query = select(PackageVersion).where(
        PackageVersion.package_id == package.id, not PackageVersion.is_yanked
    )

    if not include_prereleases:
        query = query.where(not PackageVersion.is_prerelease)

    query = query.order_by(desc(PackageVersion.created_at))

    result = await db.execute(query)
    versions = result.scalars().all()

    return versions


@router.post(
    "/{package_name}/versions",
    response_model=PackageVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_package_version(
    package_name: str,
    file: UploadFile = File(...),
    metadata: PackageVersionCreate = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(),
):
    """Upload a new version of a package."""

    normalized_name = normalize_package_name(package_name)

    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id,
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied",
        )

    # Check if version already exists
    result = await db.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == package.id,
            PackageVersion.version == metadata.version,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {metadata.version} already exists",
        )

    # Read and hash the file
    file_content = await file.read()
    file_size = len(file_content)

    sha256_hash = hashlib.sha256(file_content).hexdigest()
    md5_hash = hashlib.md5(file_content).hexdigest()

    # Store file
    storage_path = await storage.store_package(
        package_name=package.name,
        version=metadata.version,
        filename=file.filename,
        content=file_content,
    )

    # Create package version
    version = PackageVersion(
        package_id=package.id,
        version=metadata.version,
        summary=metadata.summary,
        description=metadata.description,
        python_version=metadata.python_version,
        supported_revit_versions=metadata.supported_revit_versions,
        filename=file.filename,
        file_size=file_size,
        file_hash_sha256=sha256_hash,
        file_hash_md5=md5_hash,
        storage_path=storage_path,
        author=metadata.author,
        author_email=metadata.author_email,
        license=metadata.license,
        is_prerelease=metadata.is_prerelease,
        extra_metadata=metadata.metadata,
        uploaded_by_id=current_user.id,
    )

    db.add(version)

    # Add dependencies
    for dep_data in metadata.dependencies:
        dependency = PackageDependency(
            version_id=version.id,
            dependency_name=dep_data.dependency_name,
            version_constraint=dep_data.version_constraint,
            is_optional=dep_data.is_optional,
            extra=dep_data.extra,
            dependency_type=dep_data.dependency_type,
        )
        db.add(dependency)

    await db.commit()
    await db.refresh(version)

    return version


@router.get("/{package_name}/stats", response_model=DownloadStatsResponse)
async def get_package_stats(
    package_name: str, db: AsyncSession = Depends(get_db_session)
):
    """Get package download statistics."""

    normalized_name = normalize_package_name(package_name)

    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name, Package.is_published
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )

    # Calculate time ranges
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(days=7)
    one_month_ago = now - timedelta(days=30)

    # Try to get cached statistics first
    cache_key = f"stats:package:{package.id}:{now.date().isoformat()}"
    cache_service = CacheService()

    try:
        cached_stats = await cache_service.get(cache_key)
        if cached_stats:
            return DownloadStatsResponse(**cached_stats)
    except Exception:
        pass  # Cache miss or error, proceed with database query

    # Query download statistics
    # Last day downloads
    result_day = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_day_ago,
                DownloadStats.download_completed,
            )
        )
    )
    downloads_last_day = result_day.scalar() or 0

    # Last week downloads
    result_week = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_week_ago,
                DownloadStats.download_completed,
            )
        )
    )
    downloads_last_week = result_week.scalar() or 0

    # Last month downloads
    result_month = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_month_ago,
                DownloadStats.download_completed,
            )
        )
    )
    downloads_last_month = result_month.scalar() or 0

    # Version breakdown - get download counts by version
    version_result = await db.execute(
        select(
            PackageVersion.version, func.count(DownloadStats.id).label("download_count")
        )
        .join(DownloadStats, DownloadStats.version_id == PackageVersion.id)
        .where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_month_ago,
                DownloadStats.download_completed,
            )
        )
        .group_by(PackageVersion.version)
        .order_by(desc("download_count"))
    )

    version_breakdown = {
        row.version: row.download_count for row in version_result.all()
    }

    # Country breakdown - get download counts by country
    country_result = await db.execute(
        select(
            DownloadStats.country_code,
            func.count(DownloadStats.id).label("download_count"),
        )
        .where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_month_ago,
                DownloadStats.download_completed,
                DownloadStats.country_code.is_not(None),
            )
        )
        .group_by(DownloadStats.country_code)
        .order_by(desc("download_count"))
        .limit(10)  # Top 10 countries
    )

    country_breakdown = {
        row.country_code: row.download_count for row in country_result.all()
    }

    # Platform breakdown - get download counts by platform
    platform_result = await db.execute(
        select(
            DownloadStats.platform, func.count(DownloadStats.id).label("download_count")
        )
        .where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= one_month_ago,
                DownloadStats.download_completed,
                DownloadStats.platform.is_not(None),
            )
        )
        .group_by(DownloadStats.platform)
        .order_by(desc("download_count"))
    )

    platform_breakdown = {
        row.platform: row.download_count for row in platform_result.all()
    }

    # Construct response
    stats_response = DownloadStatsResponse(
        package_id=package.id,
        total_downloads=package.download_count,
        downloads_last_day=downloads_last_day,
        downloads_last_week=downloads_last_week,
        downloads_last_month=downloads_last_month,
        version_breakdown=version_breakdown,
        country_breakdown=country_breakdown,
        platform_breakdown=platform_breakdown,
    )

    # Cache the results for 1 hour
    try:
        await cache_service.set(
            cache_key,
            stats_response.dict(),
            ttl=3600,  # 1 hour cache
        )
    except Exception:
        pass  # Cache write failure, not critical

    return stats_response
