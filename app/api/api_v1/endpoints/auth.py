"""
Authentication endpoints for AP Intake & Validation system.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import Token, UserCreate, UserResponse, LoginRequest
from app.core.auth import (
    create_access_token,
    get_current_user,
    generate_dev_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings
from app.db.session import get_db

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Authenticate user and return access token.

    For development purposes, this accepts simple credentials.
    In production, you should verify against a users table.
    """
    # Development mode - accept any credentials
    if settings.ENVIRONMENT.lower() in ["development", "dev"]:
        if login_data.email == "dev@example.com" and login_data.password == "dev":
            access_token_expires = timedelta(minutes=60 * 24 * 7)  # 7 days for dev
            access_token = create_access_token(
                subject="dev-user-123",
                expires_delta=access_token_expires
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 60 * 24 * 7,  # 7 days in minutes
                "user": {
                    "id": "dev-user-123",
                    "email": "dev@example.com",
                    "is_active": True,
                    "is_admin": True,
                }
            }

    # Production authentication would go here
    # For now, return a generic error
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/dev-token", response_model=Token)
async def get_dev_token() -> Any:
    """
    Generate a development token for testing purposes.
    Only available in development mode.
    """
    if settings.ENVIRONMENT.lower() not in ["development", "dev"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development token only available in development mode"
        )

    access_token = generate_dev_token()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 60 * 24 * 365,  # 1 year in minutes
        "user": {
            "id": "dev-user-123",
            "email": "dev@example.com",
            "is_active": True,
            "is_admin": True,
        }
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
) -> Any:
    """Get current user information."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        is_active=current_user["is_active"],
        is_admin=current_user.get("is_admin", False)
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: dict = Depends(get_current_user)
) -> Any:
    """Refresh access token."""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=current_user["id"],
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "user": current_user
    }


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user)
) -> Any:
    """Logout user (client-side token removal)."""
    return {"message": "Successfully logged out"}


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Register a new user.

    For development purposes only.
    In production, you would save to database and verify email.
    """
    if settings.ENVIRONMENT.lower() not in ["development", "dev"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration only available in development mode"
        )

    # Simple development registration
    # In production, you would check for existing users, hash password, etc.
    hashed_password = get_password_hash(user_data.password)

    # For now, just return success
    # In production, you would save to database
    return UserResponse(
        id="new-user-123",
        email=user_data.email,
        is_active=True,
        is_admin=False
    )