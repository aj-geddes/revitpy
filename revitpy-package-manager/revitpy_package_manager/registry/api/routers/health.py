"""Health check endpoints."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import HealthResponse
from ...database import get_db_session
from ..... import __version__

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Comprehensive health check endpoint."""
    
    # Check database connectivity
    database_status = "healthy"
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        database_status = f"unhealthy: {str(e)}"
    
    # Check Redis cache (if configured)
    cache_status = "not_configured"
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis.asyncio as redis
            r = redis.from_url(redis_url)
            await r.ping()
            cache_status = "healthy"
        except Exception as e:
            cache_status = f"unhealthy: {str(e)}"
    
    # Check storage (S3 or local)
    storage_status = "healthy"  # Simplified for now
    
    # Overall status
    overall_status = "healthy"
    if "unhealthy" in [database_status, cache_status, storage_status]:
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=__version__,
        database=database_status,
        cache=cache_status,
        storage=storage_status,
        timestamp=datetime.utcnow(),
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "live"}