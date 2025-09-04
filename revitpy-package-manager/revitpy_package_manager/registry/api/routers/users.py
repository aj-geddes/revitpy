"""User management endpoints."""

import secrets
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    APIKeyCreate, APIKeyResponse, APIKeyWithToken,
    UserResponse, UserUpdate
)
from ...database import get_db_session
from ...models.user import User, APIKey
from .auth import get_current_active_user, get_password_hash

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update current user's profile."""
    
    # Update user fields
    for field, value in user_update.dict(exclude_unset=True).items():
        if hasattr(current_user, field):
            if field == "website_url" and value:
                setattr(current_user, field, str(value))
            else:
                setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/{username}", response_model=UserResponse)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get a user's public profile."""
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/me/api-keys", response_model=List[APIKeyResponse])
async def list_my_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List current user's API keys."""
    
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id)
    )
    api_keys = result.scalars().all()
    
    return api_keys


@router.post("/me/api-keys", response_model=APIKeyWithToken, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new API key for the current user."""
    
    # Generate a secure token
    token = f"rpk_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    token_hash = get_password_hash(token)
    token_prefix = token[:8]
    
    # Create API key
    api_key = APIKey(
        user_id=current_user.id,
        name=api_key_data.name,
        description=api_key_data.description,
        token_hash=token_hash,
        token_prefix=token_prefix,
        scopes=api_key_data.scopes,
        expires_at=api_key_data.expires_at,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    # Return the API key with the full token (only shown once)
    response = APIKeyWithToken.from_orm(api_key)
    response.token = token
    return response


@router.delete("/me/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete an API key."""
    
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await db.delete(api_key)
    await db.commit()


@router.put("/me/api-keys/{api_key_id}/deactivate", response_model=APIKeyResponse)
async def deactivate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Deactivate an API key."""
    
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    await db.commit()
    await db.refresh(api_key)
    
    return api_key


@router.put("/me/api-keys/{api_key_id}/activate", response_model=APIKeyResponse)
async def activate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Activate an API key."""
    
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = True
    await db.commit()
    await db.refresh(api_key)
    
    return api_key