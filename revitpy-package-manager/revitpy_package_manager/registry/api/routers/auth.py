"""Authentication endpoints."""

from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config import get_settings
from ...database import get_db_session
from ...models.user import User
from ...security.config import SecurityConfig
from ..schemas import LoginRequest, LoginResponse, UserCreate, UserResponse

router = APIRouter()
security = HTTPBearer()

# JWT configuration (loaded from centralized config)
_settings = get_settings()
JWT_SECRET_KEY = _settings.jwt.secret_key
JWT_ALGORITHM = _settings.jwt.algorithm
JWT_EXPIRE_HOURS = _settings.jwt.expire_hours


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Get the current authenticated user from JWT token."""
    token = credentials.credentials

    try:
        # Explicitly specify algorithms to prevent algorithm confusion attacks
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Get the current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db_session)):
    """Register a new user."""

    # Validate password strength
    password_validation = SecurityConfig.validate_password_strength(user_data.password)
    if not password_validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password is too weak: {'; '.join(password_validation['issues'])}",
        )

    # Sanitize user inputs
    username = SecurityConfig.sanitize_user_input(user_data.username, 50)
    email = SecurityConfig.sanitize_user_input(user_data.email, 255)
    full_name = SecurityConfig.sanitize_user_input(user_data.full_name or "", 100)

    if not username or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and email are required",
        )

    # Check if username already exists
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user with sanitized inputs
    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(user_data.password),
        full_name=full_name or None,
        bio=SecurityConfig.sanitize_user_input(user_data.bio or "", 500),
        website_url=str(user_data.website_url) if user_data.website_url else None,
        company=SecurityConfig.sanitize_user_input(user_data.company or "", 100),
        location=SecurityConfig.sanitize_user_input(user_data.location or "", 100),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    """Authenticate a user and return an access token."""

    # Find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == login_data.username) | (User.email == login_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    return LoginResponse(access_token=access_token, token_type="bearer", user=user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user


@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_active_user)):
    """Refresh the access token."""
    access_token = create_access_token(data={"sub": str(current_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
