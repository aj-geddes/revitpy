"""Package management endpoints."""

import hashlib
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..schemas import (
    PackageCreate, PackageListResponse, PackageResponse,
    PackageSearchResponse, PackageUpdate,
    PackageVersionCreate, PackageVersionResponse, PackageVersionUpdate,
    DownloadStatsResponse
)
from ...database import get_db_session
from ...models.package import Package, PackageVersion, PackageDependency
from ...models.user import User
from ...services.storage import StorageService
from .auth import get_current_active_user

router = APIRouter()


def normalize_package_name(name: str) -> str:
    """Normalize package name for consistent storage and lookup."""
    return name.lower().replace("_", "-").replace(" ", "-")


@router.get("/", response_model=PackageListResponse)
async def list_packages(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    revit_version: Optional[str] = Query(None, description="Filter by Revit version"),
    db: AsyncSession = Depends(get_db_session)
):
    """List packages with pagination and filtering."""
    
    query = select(Package).where(
        Package.is_published == True,
        Package.is_private == False
    )
    
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
    db: AsyncSession = Depends(get_db_session)
):
    """Search packages by name, summary, or keywords."""
    
    # Build search query
    search_term = f"%{q.lower()}%"
    query = select(Package).where(
        and_(
            Package.is_published == True,
            Package.is_private == False,
            or_(
                Package.name.ilike(search_term),
                Package.summary.ilike(search_term),
                Package.description.ilike(search_term),
                Package.keywords.contains([q.lower()])
            )
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
    db: AsyncSession = Depends(get_db_session)
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
            detail=f"Package '{package_data.name}' already exists"
        )
    
    # Create package
    package = Package(
        name=package_data.name,
        normalized_name=normalized_name,
        summary=package_data.summary,
        description=package_data.description,
        keywords=package_data.keywords,
        categories=package_data.categories,
        homepage_url=str(package_data.homepage_url) if package_data.homepage_url else None,
        repository_url=str(package_data.repository_url) if package_data.repository_url else None,
        documentation_url=str(package_data.documentation_url) if package_data.documentation_url else None,
        bug_tracker_url=str(package_data.bug_tracker_url) if package_data.bug_tracker_url else None,
        owner_id=current_user.id,
    )
    
    db.add(package)
    await db.commit()
    await db.refresh(package)
    
    return package


@router.get("/{package_name}", response_model=PackageResponse)
async def get_package(
    package_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get package details."""
    
    normalized_name = normalize_package_name(package_name)
    
    result = await db.execute(
        select(Package)
        .options(selectinload(Package.versions))
        .where(
            Package.normalized_name == normalized_name,
            Package.is_published == True
        )
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    return package


@router.put("/{package_name}", response_model=PackageResponse)
async def update_package(
    package_name: str,
    package_update: PackageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update package details."""
    
    normalized_name = normalize_package_name(package_name)
    
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id
        )
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied"
        )
    
    # Update package fields
    for field, value in package_update.dict(exclude_unset=True).items():
        if hasattr(package, field):
            if field in ("homepage_url", "repository_url", "documentation_url", "bug_tracker_url") and value:
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
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a package (soft delete by unpublishing)."""
    
    normalized_name = normalize_package_name(package_name)
    
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id
        )
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied"
        )
    
    # Soft delete by unpublishing
    package.is_published = False
    await db.commit()


@router.get("/{package_name}/versions", response_model=List[PackageVersionResponse])
async def list_package_versions(
    package_name: str,
    include_prereleases: bool = Query(False, description="Include prerelease versions"),
    db: AsyncSession = Depends(get_db_session)
):
    """List all versions of a package."""
    
    normalized_name = normalize_package_name(package_name)
    
    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.is_published == True
        )
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    # Query versions
    query = select(PackageVersion).where(
        PackageVersion.package_id == package.id,
        PackageVersion.is_yanked == False
    )
    
    if not include_prereleases:
        query = query.where(PackageVersion.is_prerelease == False)
    
    query = query.order_by(desc(PackageVersion.created_at))
    
    result = await db.execute(query)
    versions = result.scalars().all()
    
    return versions


@router.post("/{package_name}/versions", response_model=PackageVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_package_version(
    package_name: str,
    file: UploadFile = File(...),
    metadata: PackageVersionCreate = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends()
):
    """Upload a new version of a package."""
    
    normalized_name = normalize_package_name(package_name)
    
    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.owner_id == current_user.id
        )
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found or access denied"
        )
    
    # Check if version already exists
    result = await db.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == package.id,
            PackageVersion.version == metadata.version
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {metadata.version} already exists"
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
        content=file_content
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
        metadata=metadata.metadata,
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
    package_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get package download statistics."""
    from datetime import datetime, timedelta
    from ...models.download import DownloadStats

    normalized_name = normalize_package_name(package_name)

    # Get package
    result = await db.execute(
        select(Package).where(
            Package.normalized_name == normalized_name,
            Package.is_published == True
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Query download statistics for different time periods
    # Downloads in the last day
    day_result = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= day_ago,
                DownloadStats.download_completed == True
            )
        )
    )
    downloads_last_day = day_result.scalar() or 0

    # Downloads in the last week
    week_result = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= week_ago,
                DownloadStats.download_completed == True
            )
        )
    )
    downloads_last_week = week_result.scalar() or 0

    # Downloads in the last month
    month_result = await db.execute(
        select(func.count(DownloadStats.id)).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.downloaded_at >= month_ago,
                DownloadStats.download_completed == True
            )
        )
    )
    downloads_last_month = month_result.scalar() or 0

    # Version breakdown - get download counts per version
    version_result = await db.execute(
        select(
            PackageVersion.version,
            func.count(DownloadStats.id).label('count')
        ).join(
            DownloadStats, DownloadStats.version_id == PackageVersion.id
        ).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.download_completed == True
            )
        ).group_by(PackageVersion.version)
    )

    version_breakdown = {}
    for row in version_result:
        version_breakdown[row.version] = row.count

    # Country breakdown - get download counts per country
    country_result = await db.execute(
        select(
            DownloadStats.country_code,
            func.count(DownloadStats.id).label('count')
        ).where(
            and_(
                DownloadStats.package_id == package.id,
                DownloadStats.country_code.isnot(None),
                DownloadStats.download_completed == True
            )
        ).group_by(DownloadStats.country_code).order_by(desc('count')).limit(20)
    )

    country_breakdown = {}
    for row in country_result:
        if row.country_code:
            country_breakdown[row.country_code] = row.count

    return DownloadStatsResponse(
        package_id=package.id,
        total_downloads=package.download_count,
        downloads_last_day=downloads_last_day,
        downloads_last_week=downloads_last_week,
        downloads_last_month=downloads_last_month,
        version_breakdown=version_breakdown,
        country_breakdown=country_breakdown,
    )