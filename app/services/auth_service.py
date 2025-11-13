"""
Enhanced authentication service with role-based access control (RBAC).
"""

import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.select import select

from app.core.config import settings
from app.core.auth import verify_token
from app.db.session import get_db
from app.models.rbac import (
    Role,
    Permission,
    UserRole,
    RolePermissionCache,
    PermissionType,
    ResourceType,
    DEFAULT_ROLES,
    DEFAULT_POLICY_GATES
)
from app.models.user import User
from app.models.approval_models import ApprovalRequest

# JWT Token settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


class UserPermissions:
    """User permission container with role-based access."""

    def __init__(
        self,
        user_id: str,
        roles: List[str],
        permissions: Dict[str, List[str]]
    ):
        self.user_id = user_id
        self.roles = roles
        self.permissions = permissions
        self._permission_cache: Dict[str, bool] = {}

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has permission for a specific resource and action."""
        cache_key = f"{resource}:{action}"

        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]

        # Check direct permissions
        resource_permissions = self.permissions.get(resource, [])
        has_direct_permission = action in resource_permissions

        # Check admin permissions (admin role has access to everything)
        has_admin_permission = (
            "admin" in self.roles or
            "admin" in self.permissions.get(resource, [])
        )

        # Check system permissions
        has_system_permission = (
            "admin" in self.permissions.get("system", []) and
            action in ["read", "write", "delete", "manage", "admin"]
        )

        result = has_direct_permission or has_admin_permission or has_system_permission
        self._permission_cache[cache_key] = result
        return result

    def has_any_permission(self, resource: str, actions: List[str]) -> bool:
        """Check if user has any of the specified permissions for a resource."""
        return any(self.has_permission(resource, action) for action in actions)

    def has_all_permissions(self, resource: str, actions: List[str]) -> bool:
        """Check if user has all of the specified permissions for a resource."""
        return all(self.has_permission(resource, action) for action in actions)

    def can_approve(self, approval_level: int = 1) -> bool:
        """Check if user can approve at the specified level."""
        if "admin" in self.roles:
            return True

        role_levels = {
            "admin": 100,
            "manager": 80,
            "ap_clerk": 50,
            "viewer": 20,
            "vendor": 10
        }

        user_level = max(role_levels.get(role, 0) for role in self.roles)
        return user_level >= (approval_level * 50)  # Level 1 needs 50, Level 2 needs 100, etc.

    def can_manage_users(self) -> bool:
        """Check if user can manage other users."""
        return self.has_permission("user", "manage") or "admin" in self.roles

    def can_manage_policies(self) -> bool:
        """Check if user can manage policies."""
        return self.has_permission("policy", "manage") or "admin" in self.roles

    def get_effective_roles(self) -> List[str]:
        """Get the effective roles for the user (including inherited permissions)."""
        # For now, return direct roles. In a more complex system,
        # this would include role hierarchy and inheritance
        return self.roles.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "user_id": self.user_id,
            "roles": self.roles,
            "permissions": self.permissions,
            "can_approve": self.can_approve(),
            "can_manage_users": self.can_manage_users(),
            "can_manage_policies": self.can_manage_policies()
        }


class AuthService:
    """Enhanced authentication service with RBAC support."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_access_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None,
        include_roles: bool = True
    ) -> str:
        """Create a JWT access token with optional role information."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "exp": expire,
            "sub": user_id,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        # Add role information if requested
        if include_roles:
            user_permissions = await self.get_user_permissions(user_id)
            payload["roles"] = user_permissions.roles
            payload["permissions"] = user_permissions.permissions

        encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def create_refresh_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        payload = {
            "exp": expire,
            "sub": user_id,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }

        encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token and return the payload."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    async def get_user_permissions(self, user_id: str) -> UserPermissions:
        """Get user permissions with caching."""
        # Check cache first
        cache_key = f"user_permissions:{user_id}"
        cache_entry = await self.db.get(
            RolePermissionCache,
            cache_key
        )

        if cache_entry and cache_entry.expires_at > datetime.utcnow():
            # Update hit count and last accessed
            cache_entry.hit_count += 1
            cache_entry.last_accessed_at = datetime.utcnow()
            await self.db.commit()

            return UserPermissions(
                user_id=user_id,
                roles=cache_entry.roles,
                permissions=cache_entry.permissions
            )

        # Build permissions from database
        user_roles = await self._get_user_roles(user_id)
        permissions = await self._build_permissions_from_roles(user_roles)

        # Cache the result
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        cache_entry = RolePermissionCache(
            user_id=user_id,
            cache_key=cache_key,
            roles=user_roles,
            permissions=permissions,
            expires_at=expires_at
        )
        await self.db.merge(cache_entry)
        await self.db.commit()

        return UserPermissions(
            user_id=user_id,
            roles=user_roles,
            permissions=permissions
        )

    async def _get_user_roles(self, user_id: str) -> List[str]:
        """Get active roles for a user."""
        stmt = (
            select(UserRole.role_id, Role.name)
            .join(Role, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.is_active == True,
                Role.is_active == True
            )
            .where(
                (UserRole.expires_at.is_(None)) |
                (UserRole.expires_at > datetime.utcnow())
            )
        )
        result = await self.db.execute(stmt)
        return [row[1] for row in result.all()]

    async def _build_permissions_from_roles(self, role_names: List[str]) -> Dict[str, List[str]]:
        """Build permission dictionary from role names."""
        if not role_names:
            return {}

        # Get roles with their permissions
        stmt = (
            select(Role)
            .where(Role.name.in_(role_names), Role.is_active == True)
            .options(selectinload(Role.permissions_detail))
        )
        result = await self.db.execute(stmt)
        roles = result.scalars().all()

        permissions = {}

        # Build permissions from role definitions
        for role in roles:
            # Legacy permissions from role.permissions JSON field
            if role.permissions:
                for resource, actions in role.permissions.items():
                    if resource not in permissions:
                        permissions[resource] = []
                    permissions[resource].extend(actions)

            # Granular permissions from permissions table
            for perm in role.permissions_detail:
                if perm.is_granted:  # Only include granted permissions
                    resource = perm.resource_type
                    action = perm.permission_type

                    if resource not in permissions:
                        permissions[resource] = []

                    if action not in permissions[resource]:
                        permissions[resource].append(action)

        # Remove duplicates while preserving order
        for resource in permissions:
            permissions[resource] = list(dict.fromkeys(permissions[resource]))

        return permissions

    async def assign_role(
        self,
        user_id: str,
        role_name: str,
        assigned_by: str,
        expires_at: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> UserRole:
        """Assign a role to a user."""
        # Get the role
        stmt = select(Role).where(Role.name == role_name, Role.is_active == True)
        result = await self.db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found"
            )

        # Check if user already has this role
        existing_stmt = (
            select(UserRole)
            .where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        existing_role = existing_result.scalar_one_or_none()

        if existing_role:
            # Reactivate existing role assignment
            existing_role.is_active = True
            existing_role.expires_at = expires_at
            existing_role.assigned_by = assigned_by
            existing_role.context = context
            existing_role.assigned_at = datetime.utcnow()
            await self.db.commit()
            return existing_role

        # Create new role assignment
        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by,
            expires_at=expires_at,
            context=context
        )
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)

        # Clear permission cache for this user
        await self._clear_permission_cache(user_id)

        return user_role

    async def revoke_role(self, user_id: str, role_name: str) -> bool:
        """Revoke a role from a user."""
        stmt = (
            select(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.name == role_name
            )
        )
        result = await self.db.execute(stmt)
        user_role = result.scalar_one_or_none()

        if not user_role:
            return False

        user_role.is_active = False
        await self.db.commit()

        # Clear permission cache for this user
        await self._clear_permission_cache(user_id)

        return True

    async def _clear_permission_cache(self, user_id: str):
        """Clear permission cache for a user."""
        # Delete cache entries for this user
        cache_entries = await self.db.execute(
            select(RolePermissionCache).where(RolePermissionCache.user_id == user_id)
        )
        for entry in cache_entries.scalars().all():
            await self.db.delete(entry)
        await self.db.commit()

    async def initialize_default_roles(self):
        """Initialize default roles in the database."""
        for role_data in DEFAULT_ROLES:
            # Check if role already exists
            stmt = select(Role).where(Role.name == role_data["name"])
            result = await self.db.execute(stmt)
            existing_role = result.scalar_one_or_none()

            if existing_role:
                # Update existing role if needed
                for key, value in role_data.items():
                    if key != "name" and hasattr(existing_role, key):
                        setattr(existing_role, key, value)
            else:
                # Create new role
                role = Role(**role_data)
                self.db.add(role)

        await self.db.commit()

    async def create_user(
        self,
        email: str,
        username: str,
        full_name: str,
        password: str,
        role: str = "ap_clerk",
        created_by: Optional[str] = None
    ) -> User:
        """Create a new user with role assignment."""
        # Check if user already exists
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create user
        from app.core.auth import get_password_hash
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
            is_verified=True
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Assign role
        await self.assign_role(
            user_id=str(user.id),
            role_name=role,
            assigned_by=created_by or "system"
        )

        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        from app.core.auth import verify_password
        if not verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login_at = datetime.utcnow()
        user.login_count += 1
        await self.db.commit()

        return user


# Dependency functions for FastAPI
async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Get authentication service instance."""
    return AuthService(db)


async def get_current_user_with_permissions(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """Get current user with their permissions."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token
    payload = await auth_service.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user permissions
    user_permissions = await auth_service.get_user_permissions(user_id)

    return {
        "user_id": user_id,
        "permissions": user_permissions
    }


def require_permission(resource: str, action: str):
    """Decorator to require specific permission for an endpoint."""
    def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user_with_permissions)
    ) -> Dict[str, Any]:
        user_permissions = current_user["permissions"]

        if not user_permissions.has_permission(resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return current_user

    return permission_checker


def require_any_permission(resource: str, actions: List[str]):
    """Decorator to require any of the specified permissions for an endpoint."""
    def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user_with_permissions)
    ) -> Dict[str, Any]:
        user_permissions = current_user["permissions"]

        if not user_permissions.has_any_permission(resource, actions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: any of {actions} on {resource}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return current_user

    return permission_checker


def require_role(role: str):
    """Decorator to require a specific role for an endpoint."""
    def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user_with_permissions)
    ) -> Dict[str, Any]:
        user_permissions = current_user["permissions"]

        if role not in user_permissions.roles and "admin" not in user_permissions.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return current_user

    return role_checker


def require_approval_level(level: int = 1):
    """Decorator to require a specific approval level for an endpoint."""
    def level_checker(
        current_user: Dict[str, Any] = Depends(get_current_user_with_permissions)
    ) -> Dict[str, Any]:
        user_permissions = current_user["permissions"]

        if not user_permissions.can_approve(level):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval level {level} required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return current_user

    return level_checker


# Development authentication bypass
async def get_dev_user_with_permissions() -> Dict[str, Any]:
    """Development user with permissions for testing purposes."""
    if settings.ENVIRONMENT.lower() in ["development", "dev"]:
        # Create a dev user with admin permissions
        permissions = UserPermissions(
            user_id="dev-user-123",
            roles=["admin"],
            permissions={
                "system": ["read", "write", "delete", "manage", "admin"],
                "user": ["read", "write", "delete", "manage"],
                "role": ["read", "write", "delete", "manage"],
                "invoice": ["read", "write", "delete", "approve"],
                "vendor": ["read", "write", "delete", "approve"],
                "approval": ["read", "write", "delete", "approve", "manage"],
                "policy": ["read", "write", "delete", "manage"],
                "report": ["read", "write"],
                "export": ["read", "write", "delete"],
                "exception": ["read", "write", "delete", "approve"]
            }
        )

        return {
            "user_id": "dev-user-123",
            "permissions": permissions
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Development user only available in development mode"
    )


# Conditional authentication for development
def get_current_user_with_permissions_optional(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    dev_user: Dict[str, Any] = Depends(get_dev_user_with_permissions)
) -> Dict[str, Any]:
    """Get current user with permissions, with development bypass."""
    if settings.ENVIRONMENT.lower() in ["development", "dev"]:
        return dev_user
    return current_user