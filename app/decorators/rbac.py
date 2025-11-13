"""
RBAC decorators for FastAPI route protection with role-based access control.
"""

import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth_service import (
    get_current_user_with_permissions,
    get_current_user_with_permissions_optional,
    get_dev_user_with_permissions,
    AuthService,
    UserPermissions
)

logger = logging.getLogger(__name__)

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


def require_permissions(resource: str, actions: Union[str, List[str]], require_all: bool = False):
    """
    Decorator to require specific permissions for an endpoint.

    Args:
        resource: The resource type (e.g., 'invoice', 'user', 'approval')
        actions: Single action or list of actions required
        require_all: If True, user must have ALL specified actions
                    If False, user must have ANY of the specified actions
    """
    if isinstance(actions, str):
        actions = [actions]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current user from kwargs or dependencies
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_permissions = current_user.get("permissions")
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found for user",
                )

            # Check permissions
            if require_all:
                # User must have ALL specified permissions
                if not all(user_permissions.has_permission(resource, action) for action in actions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: requires all actions {actions} on {resource}",
                    )
            else:
                # User must have ANY of the specified permissions
                if not user_permissions.has_any_permission(resource, actions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: requires any action {actions} on {resource}",
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_permission(resource: str, action: str):
    """
    Decorator to require a specific permission for an endpoint.

    Args:
        resource: The resource type (e.g., 'invoice', 'user', 'approval')
        action: The action required (e.g., 'read', 'write', 'delete', 'approve')
    """
    return require_permissions(resource, action, require_all=True)


def require_any_permission(resource: str, actions: List[str]):
    """
    Decorator to require any of the specified permissions for an endpoint.

    Args:
        resource: The resource type (e.g., 'invoice', 'user', 'approval')
        actions: List of actions, user must have at least one
    """
    return require_permissions(resource, actions, require_all=False)


def require_all_permissions(resource: str, actions: List[str]):
    """
    Decorator to require all of the specified permissions for an endpoint.

    Args:
        resource: The resource type (e.g., 'invoice', 'user', 'approval')
        actions: List of actions, user must have all
    """
    return require_permissions(resource, actions, require_all=True)


def require_role(role: str, allow_admin: bool = True):
    """
    Decorator to require a specific role for an endpoint.

    Args:
        role: The required role name
        allow_admin: Whether admin users automatically have access
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_permissions = current_user.get("permissions")
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found for user",
                )

            # Check role
            if role not in user_permissions.roles:
                if allow_admin and "admin" not in user_permissions.roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role required: {role}",
                    )
                elif not allow_admin:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role required: {role}",
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_role(roles: List[str], allow_admin: bool = True):
    """
    Decorator to require any of the specified roles for an endpoint.

    Args:
        roles: List of acceptable role names
        allow_admin: Whether admin users automatically have access
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_permissions = current_user.get("permissions")
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found for user",
                )

            # Check if user has any of the required roles
            has_role = any(role in user_permissions.roles for role in roles)
            has_admin = "admin" in user_permissions.roles

            if not has_role:
                if allow_admin and has_admin:
                    pass  # Admin is allowed
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"One of these roles required: {roles}",
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_approval_level(level: int = 1):
    """
    Decorator to require a specific approval level for an endpoint.

    Args:
        level: The minimum approval level required (1=basic, 2=manager, 3=admin)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_permissions = current_user.get("permissions")
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found for user",
                )

            if not user_permissions.can_approve(level):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Approval level {level} required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_self_or_permission(resource: str, action: str, user_id_param: str = "user_id"):
    """
    Decorator to allow access to own resources or require specific permission.

    Args:
        resource: The resource type
        action: The action required for non-self access
        user_id_param: Parameter name containing the user ID to check against
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check if user is accessing their own resource
            target_user_id = kwargs.get(user_id_param)
            current_user_id = current_user.get("user_id")

            if target_user_id and target_user_id == current_user_id:
                # User is accessing their own resource, allow
                return await func(*args, **kwargs)

            # User is accessing someone else's resource, check permissions
            user_permissions = current_user.get("permissions")
            if not user_permissions or not user_permissions.has_permission(resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {action} on {resource} (or must be your own resource)",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    """
    Decorator to apply rate limiting to an endpoint.

    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # In a real implementation, you'd use Redis or another distributed cache
            # For now, this is a placeholder that doesn't actually limit
            logger.warning(f"Rate limiting not implemented for {func.__name__}")
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_system_admin():
    """
    Decorator to require system administrator privileges.
    """
    return require_role("admin", allow_admin=False)


def require_user_manager():
    """
    Decorator to require user management privileges.
    """
    return require_any_permission("user", ["read", "write", "manage"])


def require_policy_manager():
    """
    Decorator to require policy management privileges.
    """
    return require_any_permission("policy", ["read", "write", "manage"])


def require_invoice_manager():
    """
    Decorator to require invoice management privileges.
    """
    return require_any_permission("invoice", ["read", "write", "delete"])


def require_approval_manager():
    """
    Decorator to require approval management privileges.
    """
    return require_any_permission("approval", ["read", "write", "approve", "manage"])


# Conditional authentication for development
def conditional_auth(
    require_auth: bool = True,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    role: Optional[str] = None
):
    """
    Decorator that conditionally requires authentication based on environment.

    Args:
        require_auth: Whether authentication is required
        resource: Resource type for permission check (if require_auth=True)
        action: Action for permission check (if require_auth=True)
        role: Required role (if require_auth=True)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from app.core.config import settings

            if not require_auth or settings.ENVIRONMENT.lower() in ["development", "dev"]:
                # Development mode, use dev user
                if 'current_user' not in kwargs:
                    dev_user = await get_dev_user_with_permissions()
                    kwargs['current_user'] = dev_user
                return await func(*args, **kwargs)

            # Production mode, require authentication and check permissions
            if 'current_user' not in kwargs:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            current_user = kwargs['current_user']
            user_permissions = current_user.get("permissions")

            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found for user",
                )

            # Check role if specified
            if role and role not in user_permissions.roles and "admin" not in user_permissions.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role}",
                )

            # Check permissions if specified
            if resource and action and not user_permissions.has_permission(resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {action} on {resource}",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Permission checking utilities
def check_user_permission(user_permissions: UserPermissions, resource: str, action: str) -> bool:
    """
    Check if a user has permission for a specific resource and action.

    Args:
        user_permissions: The user's permissions object
        resource: The resource type
        action: The action required

    Returns:
        True if user has permission, False otherwise
    """
    return user_permissions.has_permission(resource, action)


def check_user_role(user_permissions: UserPermissions, role: str, allow_admin: bool = True) -> bool:
    """
    Check if a user has a specific role.

    Args:
        user_permissions: The user's permissions object
        role: The role to check
        allow_admin: Whether admin users automatically pass

    Returns:
        True if user has role (or admin if allowed), False otherwise
    """
    if role in user_permissions.roles:
        return True
    if allow_admin and "admin" in user_permissions.roles:
        return True
    return False


def can_user_approve(user_permissions: UserPermissions, level: int = 1) -> bool:
    """
    Check if a user can approve at the specified level.

    Args:
        user_permissions: The user's permissions object
        level: The approval level required

    Returns:
        True if user can approve at level, False otherwise
    """
    return user_permissions.can_approve(level)


def get_user_effective_permissions(user_permissions: UserPermissions) -> Dict[str, List[str]]:
    """
    Get the effective permissions for a user.

    Args:
        user_permissions: The user's permissions object

    Returns:
        Dictionary of resource -> list of permissions
    """
    return user_permissions.permissions.copy()