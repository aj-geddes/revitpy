"""Authentication endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config import JWTConfig, Settings, get_settings
from ....security.config import SecurityConfig
from ...database import get_db_session
from ...models.user import User
from ..schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter()
# auto_error=False so a missing/empty bearer token yields our own 401 (with a
# WWW-Authenticate header) instead of FastAPI's generic response.
security = HTTPBearer(auto_error=False)

_DEFAULT_DEV_JWT_SECRET = JWTConfig.model_fields["secret_key"].default


def _ensure_secure_jwt_secret(settings: Settings) -> None:
    """Refuse to run in production with the public development JWT secret.

    Anyone can read the default secret in the source tree and forge tokens,
    so a production deployment must supply its own JWT_SECRET_KEY.
    """
    secret = settings.jwt.secret_key
    if settings.is_production and (
        secret == _DEFAULT_DEV_JWT_SECRET
        or not SecurityConfig.validate_jwt_secret(secret)
    ):
        raise ValueError(
            "JWT_SECRET_KEY must be set to a strong, non-default secret in production"
        )


# JWT configuration (loaded from centralized config)
_settings = get_settings()
_ensure_secure_jwt_secret(_settings)
JWT_SECRET_KEY = _settings.jwt.secret_key
JWT_ALGORITHM = _settings.jwt.algorithm
JWT_EXPIRE_HOURS = _settings.jwt.expire_hours
JWT_REFRESH_EXPIRE_DAYS = _settings.jwt.refresh_expire_days

# ``type`` claim values. Access tokens authenticate API calls; refresh tokens
# are only accepted by POST /auth/refresh. Neither can stand in for the other.
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - token type label, not a secret
REFRESH_TOKEN_TYPE = "refresh"  # noqa: S105 - token type label, not a secret

# Hash used to spend equivalent bcrypt time when a login names an unknown
# user, so response timing doesn't reveal which usernames exist.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode(
    "utf-8"
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a JWT access token (``type`` claim ``"access"``)."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))

    # The type is always forced: callers can't mint a refresh token here.
    to_encode.update({"exp": expire, "iat": now, "type": ACCESS_TOKEN_TYPE})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str, auth_time: int | None = None) -> str:
    """Create a JWT refresh token (``type`` claim ``"refresh"``).

    ``auth_time`` is the Unix time of the original password login. It is
    carried unchanged through every refresh, and the token's expiry is pinned
    to ``auth_time + JWT_REFRESH_EXPIRE_DAYS``, so rotating refresh tokens
    can never extend a session past that absolute lifetime; after it the user
    must log in again.
    """
    now = datetime.now(UTC)
    if auth_time is None:
        auth_time = int(now.timestamp())
    expire = datetime.fromtimestamp(auth_time, UTC) + timedelta(
        days=JWT_REFRESH_EXPIRE_DAYS
    )
    to_encode = {
        "sub": subject,
        "type": REFRESH_TOKEN_TYPE,
        "auth_time": auth_time,
        "iat": now,
        "exp": expire,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Verify signature and expiry; map failures to 401s."""
    try:
        # Explicitly specify algorithms to prevent algorithm confusion attacks
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
    except jwt.ExpiredSignatureError as e:
        raise _unauthorized("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise _unauthorized("Invalid authentication token") from e


def _subject_user_id(payload: dict) -> uuid.UUID:
    subject = payload.get("sub")
    if subject is None:
        raise _unauthorized("Invalid authentication token")
    try:
        # Tokens carry str(user.id); the id column is a UUID, and binding a
        # plain string fails on some backends (e.g. SQLite) with a 500.
        return uuid.UUID(str(subject))
    except ValueError as e:
        raise _unauthorized("Invalid authentication token") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Returns False (rather than raising) for inputs bcrypt rejects, e.g.
    passwords over bcrypt's 72-byte limit or a malformed stored hash, so a
    bad login attempt is a 401 and never a 500.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Get the current authenticated user from JWT token."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Invalid or missing authentication token")
    payload = _decode_token(credentials.credentials)
    # Tokens issued before refresh tokens existed carry no ``type`` claim;
    # they are access tokens and remain valid until they expire.
    if payload.get("type", ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
        raise _unauthorized("Invalid authentication token")
    user_id = _subject_user_id(payload)

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

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

    if not SecurityConfig.validate_username(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Username may only contain letters, digits, '.', '_' and '-', "
                "and must start and end with a letter or digit"
            ),
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

    if user is None:
        # Burn the same bcrypt cost as a real check so timing doesn't leak
        # whether the username exists.
        verify_password(login_data.password, _DUMMY_PASSWORD_HASH)
        raise _unauthorized("Incorrect username or password")

    if not verify_password(login_data.password, user.password_hash):
        raise _unauthorized("Incorrect username or password")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Create the token pair; this login starts a new session (auth_time)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh = create_refresh_token(str(user.id))

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=JWT_EXPIRE_HOURS * 3600,
        user=user,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    body: RefreshTokenRequest | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> TokenRefreshResponse:
    """Exchange a refresh token for a new access token and refresh token.

    The refresh token (from login or a previous refresh) is taken from the
    JSON body ``{"refresh_token": ...}`` or, failing that, the
    ``Authorization: Bearer`` header. Access tokens are rejected, so a stolen
    access token cannot be renewed. The returned refresh token replaces the
    old one and keeps the original ``auth_time``, so the session still ends
    ``JWT_REFRESH_EXPIRE_DAYS`` after the password login.
    """
    token = body.refresh_token if body is not None else None
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        raise _unauthorized("Missing refresh token")

    payload = _decode_token(token)
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise _unauthorized("A refresh token is required")
    auth_time = payload.get("auth_time")
    if not isinstance(auth_time, int):
        raise _unauthorized("Invalid refresh token")
    # Defence in depth: exp is already pinned to auth_time + max lifetime,
    # but enforce the absolute cap independently of the exp claim.
    session_age = datetime.now(UTC).timestamp() - auth_time
    if session_age > JWT_REFRESH_EXPIRE_DAYS * 86400:
        raise _unauthorized("Session has expired; please log in again")
    user_id = _subject_user_id(payload)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    return TokenRefreshResponse(
        access_token=create_access_token(data={"sub": str(user.id)}),
        refresh_token=create_refresh_token(str(user.id), auth_time=auth_time),
        token_type="bearer",
        expires_in=JWT_EXPIRE_HOURS * 3600,
    )
