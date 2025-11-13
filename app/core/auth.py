"""
Authentication and authorization utilities for AP Intake & Validation system.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Token settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return the subject."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get the current authenticated user.

    For production, this should verify against a users table.
    For now, we'll use a simple token-based system.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # For now, return a simple user dict
    # In production, you would fetch user details from database
    return {
        "id": user_id,
        "email": "user@example.com",  # Placeholder
        "is_active": True,
    }


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get the current active user."""
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


# Development authentication bypass
def get_dev_user() -> dict:
    """
    Development user for testing purposes.
    This allows bypassing authentication in development mode.
    """
    if settings.ENVIRONMENT.lower() in ["development", "dev"]:
        return {
            "id": "dev-user-123",
            "email": "dev@example.com",
            "is_active": True,
            "is_admin": True,
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Development user only available in development mode"
    )


# Conditional authentication dependency
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work with or without authentication.
    """
    if settings.ENVIRONMENT.lower() in ["development", "dev"]:
        return get_dev_user()

    if credentials is None:
        return None

    user_id = verify_token(credentials.credentials)
    if user_id is None:
        return None

    return {
        "id": user_id,
        "email": "user@example.com",
        "is_active": True,
    }


def require_auth(
    current_user: dict = Depends(get_current_active_user)
) -> dict:
    """
    Require authentication for an endpoint.
    This is the main dependency for protected endpoints.
    """
    return current_user


def optional_auth(
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Optional[dict]:
    """
    Optional authentication for public endpoints.
    """
    return current_user


# Rate limiting
def create_rate_limiter(max_requests: int = 100, window_seconds: int = 3600):
    """
    Create a simple rate limiter.

    In production, you should use Redis-based rate limiting
    with proper user identification and distributed locking.
    """
    requests = {}

    def rate_limiter(request_id: str = None):
        if request_id is None:
            request_id = secrets.token_hex(8)

        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        # Clean old requests
        requests[request_id] = [
            req_time for req_time in requests.get(request_id, [])
            if req_time > window_start
        ]

        # Check rate limit
        if len(requests[request_id]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(window_seconds),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((now + timedelta(seconds=window_seconds)).timestamp()))
                }
            )

        # Add current request
        requests[request_id].append(now)

        return request_id

    return rate_limiter


# Development token generator
def generate_dev_token() -> str:
    """Generate a development token for testing."""
    return create_access_token(
        subject="dev-user-123",
        expires_delta=timedelta(days=365)  # Long-lived dev token
    )