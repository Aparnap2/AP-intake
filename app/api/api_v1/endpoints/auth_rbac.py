"""
Enhanced authentication and authorization endpoints with RBAC support.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.api.api_v1.deps import get_db
from app.services.auth_service import (
    AuthService,
    get_auth_service,
    get_current_user_with_permissions,
    get_current_user_with_permissions_optional,
    get_dev_user_with_permissions
)
from app.decorators.rbac import (
    require_permission,
    require_role,
    require_approval_level,
    require_user_manager,
    require_system_admin,
    conditional_auth
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)


# Pydantic models for requests/responses
class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    is_active: bool
    is_verified: bool
    roles: List[str]
    permissions: Dict[str, List[str]]
    can_approve: bool
    can_manage_users: bool
    can_manage_policies: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str
    role: str = "ap_clerk"
    department: Optional[str] = None


class AssignRoleRequest(BaseModel):
    role_name: str
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# Authentication endpoints
@router.post("/login", response_model=UserLoginResponse)
async def login(
    login_data: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Authenticate user and return tokens."""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create tokens
        access_token = await auth_service.create_access_token(
            user_id=str(user.id),
            include_roles=True
        )
        refresh_token = await auth_service.create_refresh_token(
            user_id=str(user.id)
        )

        # Get user permissions
        user_permissions = await auth_service.get_user_permissions(str(user.id))

        # Prepare user data
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "roles": user_permissions.roles,
            "permissions": user_permissions.permissions,
            "can_approve": user_permissions.can_approve(),
            "can_manage_users": user_permissions.can_manage_users(),
            "can_manage_policies": user_permissions.can_manage_policies(),
            "created_at": user.created_at,
            "last_login_at": user.last_login_at
        }

        return UserLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post("/refresh", response_model=Dict[str, str])
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh access token using refresh token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Verify refresh token
        payload = await auth_service.verify_token(credentials.credentials)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create new access token
        access_token = await auth_service.create_access_token(
            user_id=user_id,
            include_roles=True
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
@conditional_auth(require_auth=True)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions_optional),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Get current user information with permissions."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_permissions = current_user["permissions"]

    return UserResponse(
        id=current_user["user_id"],
        email="user@example.com",  # Would fetch from database
        username="user",
        full_name="User Name",
        is_active=True,
        is_verified=True,
        roles=user_permissions.roles,
        permissions=user_permissions.permissions,
        can_approve=user_permissions.can_approve(),
        can_manage_users=user_permissions.can_manage_users(),
        can_manage_policies=user_permissions.can_manage_policies(),
        created_at=datetime.utcnow(),
        last_login_at=datetime.utcnow()
    )


@router.post("/logout")
async def logout():
    """Logout user (client-side token invalidation)."""
    # In a real implementation, you'd invalidate the token on the server side
    # For now, we'll return success and let the client handle token removal
    return {"message": "Successfully logged out"}


# User management endpoints (require appropriate permissions)
@router.post("/users", response_model=UserResponse)
@require_user_manager()
async def create_user(
    user_data: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Create a new user."""
    try:
        user = await auth_service.create_user(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password=user_data.password,
            role=user_data.role,
            created_by=current_user["user_id"]
        )

        # Get user permissions
        user_permissions = await auth_service.get_user_permissions(str(user.id))

        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=user_permissions.roles,
            permissions=user_permissions.permissions,
            can_approve=user_permissions.can_approve(),
            can_manage_users=user_permissions.can_manage_users(),
            can_manage_policies=user_permissions.can_manage_policies(),
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.post("/users/{user_id}/roles")
@require_permission("user", "manage")
async def assign_role_to_user(
    user_id: str,
    role_data: AssignRoleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Assign a role to a user."""
    try:
        await auth_service.assign_role(
            user_id=user_id,
            role_name=role_data.role_name,
            assigned_by=current_user["user_id"],
            expires_at=role_data.expires_at,
            context={"notes": role_data.notes}
        )

        return {"message": f"Role '{role_data.role_name}' assigned to user successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Assign role error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@router.delete("/users/{user_id}/roles/{role_name}")
@require_permission("user", "manage")
async def revoke_role_from_user(
    user_id: str,
    role_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Revoke a role from a user."""
    try:
        success = await auth_service.revoke_role(
            user_id=user_id,
            role_name=role_name
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role assignment not found"
            )

        return {"message": f"Role '{role_name}' revoked from user successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke role error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role"
        )


@router.get("/users/{user_id}/permissions")
@require_permission("user", "read")
async def get_user_permissions(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Get permissions for a specific user."""
    try:
        user_permissions = await auth_service.get_user_permissions(user_id)

        return {
            "user_id": user_id,
            "roles": user_permissions.roles,
            "permissions": user_permissions.permissions,
            "can_approve": user_permissions.can_approve(),
            "can_manage_users": user_permissions.can_manage_users(),
            "can_manage_policies": user_permissions.can_manage_policies()
        }

    except Exception as e:
        logger.error(f"Get user permissions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user permissions"
        )


# System initialization endpoints (admin only)
@router.post("/initialize-roles")
@require_system_admin()
async def initialize_default_roles(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Initialize default roles in the system."""
    try:
        await auth_service.initialize_default_roles()
        return {"message": "Default roles initialized successfully"}

    except Exception as e:
        logger.error(f"Initialize roles error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize default roles"
        )


# Development endpoints (only available in development mode)
@router.get("/dev-token")
async def get_development_token():
    """Get a development token for testing."""
    if settings.ENVIRONMENT.lower() not in ["development", "dev"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development tokens only available in development mode"
        )

    from app.core.auth import generate_dev_token
    token = generate_dev_token()

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400 * 365,  # 1 year
        "message": "Development token - for testing only"
    }