"""
User management models for the AP Intake & Validation system.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserRole(str, enum.Enum):
    """User role types."""
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    CLERK = "clerk"
    VIEWER = "viewer"


class UserStatus(str, enum.Enum):
    """User status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(Base):
    """User management model."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)

    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # User information
    role = Column(String(20), nullable=False, default=UserRole.CLERK)
    status = Column(String(20), nullable=False, default=UserStatus.ACTIVE)
    department = Column(String(100), nullable=True)

    # OAuth providers
    google_id = Column(String(255), nullable=True, unique=True)
    quickbooks_id = Column(String(255), nullable=True, unique=True)

    # Preferences and settings
    preferences = Column(JSON, nullable=True)
    notification_settings = Column(JSON, nullable=True)

    # Metadata
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role={self.role})>"


class UserSession(Base):
    """User session tracking model."""
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Session information
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True)

    # Device and browser info
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    device_fingerprint = Column(String(255), nullable=True)

    # Session status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now())
    terminated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class ApiKey(Base):
    """API key management model."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # API key information
    key_name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(20), nullable=False)  # First few characters for identification

    # Permissions and restrictions
    permissions = Column(JSON, nullable=True)  # List of allowed endpoints/actions
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    allowed_ips = Column(JSON, nullable=True)  # List of allowed IP addresses

    # Status and lifecycle
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<ApiKey(id={self.id}, key_name='{self.key_name}', active={self.is_active})>"