"""
Role-Based Access Control (RBAC) models for the AP Intake & Validation system.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class PermissionType(str, enum.Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    APPROVE = "approve"
    MANAGE = "manage"
    ADMIN = "admin"


class ResourceType(str, enum.Enum):
    """Resource types that can be protected."""
    INVOICE = "invoice"
    VENDOR = "vendor"
    USER = "user"
    APPROVAL = "approval"
    POLICY = "policy"
    REPORT = "report"
    SYSTEM = "system"
    EXPORT = "export"
    EXCEPTION = "exception"


class Role(Base, UUIDMixin, TimestampMixin):
    """Role definitions for RBAC system."""

    __tablename__ = "roles"

    # Role details
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Role hierarchy
    level = Column(Integer, nullable=False, default=0)  # Higher number = higher privilege
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)

    # Role configuration
    is_system_role = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    permissions = Column(JSON, nullable=False, default=dict)  # Legacy permissions field

    # Metadata
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_role_level_active', 'level', 'is_active'),
        Index('idx_role_name_active', 'name', 'is_active'),
        UniqueConstraint('name', name='uq_role_name'),
    )

    # Relationships
    parent_role = relationship("Role", remote_side="Role.id", backref="child_roles")
    permissions_detail = relationship("Permission", back_populates="role", cascade="all, delete-orphan")
    user_assignments = relationship("UserRole", back_populates="role")
    policy_gates = relationship("PolicyGate", back_populates="required_role_obj")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', level={self.level})>"


class Permission(Base, UUIDMixin, TimestampMixin):
    """Granular permissions for roles."""

    __tablename__ = "permissions"

    # Permission details
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    resource_type = Column(String(50), nullable=False, index=True)
    permission_type = Column(String(20), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True, index=True)  # For specific resource permissions

    # Permission configuration
    conditions = Column(JSON, nullable=True)  # Conditions for when permission applies
    is_granted = Column(Boolean, default=True, nullable=False)  # Grant vs deny
    priority = Column(Integer, default=0, nullable=False)  # Higher priority overrides lower

    # Metadata
    granted_by = Column(String(255), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_permission_role_resource', 'role_id', 'resource_type', 'permission_type'),
        Index('idx_permission_resource_id', 'resource_type', 'resource_id'),
        UniqueConstraint('role_id', 'resource_type', 'permission_type', 'resource_id',
                        name='uq_permission_role_resource'),
    )

    # Relationships
    role = relationship("Role", back_populates="permissions_detail")

    def __repr__(self):
        return f"<Permission(role={self.role_id}, resource={self.resource_type}, action={self.permission_type})>"


class UserRole(Base, UUIDMixin, TimestampMixin):
    """User role assignments with optional expiration."""

    __tablename__ = "user_roles"

    # Assignment details
    user_id = Column(String(255), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)

    # Assignment configuration
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_by = Column(String(255), nullable=True)
    assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Assignment context
    context = Column(JSON, nullable=True)  # Additional context for the assignment
    notes = Column(Text, nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_user_role_user_active', 'user_id', 'is_active'),
        Index('idx_user_role_role_active', 'role_id', 'is_active'),
        Index('idx_user_role_expires', 'expires_at'),
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
    )

    # Relationships
    role = relationship("Role", back_populates="user_assignments")

    def __repr__(self):
        return f"<UserRole(user={self.user_id}, role={self.role_id}, active={self.is_active})>"


class PolicyGateType(str, enum.Enum):
    """Policy gate types."""
    CURRENCY_THRESHOLD = "currency_threshold"
    VENDOR_LIMIT = "vendor_limit"
    NEW_VENDOR = "new_vendor"
    NEGATIVE_AMOUNTS = "negative_amounts"
    DUPLICATE_INVOICE = "duplicate_invoice"
    UNUSUAL_VARIANCE = "unusual_variance"
    EXCEPTION_LIMIT = "exception_limit"
    PAYMENT_TERMS = "payment_terms"
    APPROVAL_CHAIN = "approval_chain"
    CUSTOM_RULE = "custom_rule"


class PolicyAction(str, enum.Enum):
    """Policy gate actions."""
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"
    ESCALATE = "escalate"
    FLAG = "flag"
    ALLOW = "allow"
    LOG = "log"


class PolicyGate(Base, UUIDMixin, TimestampMixin):
    """Policy gates for invoice processing control."""

    __tablename__ = "policy_gates"

    # Gate details
    name = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    gate_type = Column(String(50), nullable=False, index=True)

    # Gate configuration
    conditions = Column(JSON, nullable=False, default=dict)
    threshold_value = Column(String(100), nullable=True)  # Can be currency, percentage, etc.
    threshold_type = Column(String(20), nullable=True)  # currency, percentage, count, etc.

    # Action configuration
    action = Column(String(20), default=PolicyAction.REQUIRE_APPROVAL, nullable=False)
    required_role = Column(String(50), nullable=True, index=True)
    approval_level = Column(Integer, default=1, nullable=False)

    # Gate settings
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=10, nullable=False)  # Higher priority gates evaluated first
    timeout_hours = Column(Integer, default=72, nullable=False)

    # Gate metadata
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_policy_gate_type_active', 'gate_type', 'is_active'),
        Index('idx_policy_gate_priority_active', 'priority', 'is_active'),
        Index('idx_policy_gate_required_role', 'required_role', 'is_active'),
        UniqueConstraint('name', name='uq_policy_gate_name'),
    )

    # Relationships
    required_role_obj = relationship("Role", back_populates="policy_gates")
    evaluations = relationship("PolicyEvaluation", back_populates="gate")
    audit_logs = relationship("PolicyAuditLog", back_populates="gate")

    def __repr__(self):
        return f"<PolicyGate(id={self.id}, name='{self.name}', action={self.action})>"


class PolicyEvaluation(Base, UUIDMixin, TimestampMixin):
    """Policy gate evaluation results."""

    __tablename__ = "policy_evaluations"

    # Evaluation details
    gate_id = Column(UUID(as_uuid=True), ForeignKey("policy_gates.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Evaluation results
    triggered = Column(Boolean, nullable=False, index=True)
    result = Column(String(20), nullable=False, index=True)  # passed, failed, blocked, etc.
    evaluation_details = Column(JSON, nullable=False, default=dict)

    # Timing information
    evaluation_time = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    evaluation_duration_ms = Column(Integer, nullable=False)

    # Context information
    context_data = Column(JSON, nullable=True)  # Invoice data at time of evaluation

    # Indexes
    __table_args__ = (
        Index('idx_evaluation_gate_triggered', 'gate_id', 'triggered'),
        Index('idx_evaluation_invoice_time', 'invoice_id', 'evaluation_time'),
        Index('idx_evaluation_result_time', 'result', 'evaluation_time'),
    )

    # Relationships
    gate = relationship("PolicyGate", back_populates="evaluations")
    audit_logs = relationship("PolicyAuditLog", back_populates="evaluation")

    def __repr__(self):
        return f"<PolicyEvaluation(gate={self.gate_id}, triggered={self.triggered}, result={self.result})>"


class PolicyAuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit log for policy gate evaluations and decisions."""

    __tablename__ = "policy_audit_logs"

    # Event details
    gate_id = Column(UUID(as_uuid=True), ForeignKey("policy_gates.id"), nullable=True)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("policy_evaluations.id"), nullable=True)
    invoice_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=False, default=dict)

    # Decision information
    decision = Column(String(50), nullable=True, index=True)
    decision_reason = Column(Text, nullable=True)

    # User tracking
    user_id = Column(String(255), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # System information
    session_id = Column(String(255), nullable=True)
    correlation_id = Column(String(100), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_policy_audit_gate_time', 'gate_id', 'created_at'),
        Index('idx_policy_audit_invoice_time', 'invoice_id', 'created_at'),
        Index('idx_policy_audit_event_time', 'event_type', 'created_at'),
        Index('idx_policy_audit_decision_time', 'decision', 'created_at'),
        Index('idx_policy_audit_user_time', 'user_id', 'created_at'),
    )

    # Relationships
    gate = relationship("PolicyGate", back_populates="audit_logs")
    evaluation = relationship("PolicyEvaluation", back_populates="audit_logs")

    def __repr__(self):
        return f"<PolicyAuditLog(id={self.id}, event_type={self.event_type}, decision={self.decision})>"


class RolePermissionCache(Base, UUIDMixin, TimestampMixin):
    """Cache for user role permissions to improve performance."""

    __tablename__ = "role_permission_cache"

    # Cache key details
    user_id = Column(String(255), nullable=False, index=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)

    # Cached data
    permissions = Column(JSON, nullable=False, default=dict)
    roles = Column(JSON, nullable=False, default=list)

    # Cache metadata
    expires_at = Column(DateTime(timezone=True), nullable=False)
    hit_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_cache_user_expires', 'user_id', 'expires_at'),
        Index('idx_cache_key_expires', 'cache_key', 'expires_at'),
        Index('idx_cache_expires_hit_count', 'expires_at', 'hit_count'),
    )

    def __repr__(self):
        return f"<RolePermissionCache(user={self.user_id}, key={self.cache_key})>"


# Default roles for the system
DEFAULT_ROLES = [
    {
        "name": "admin",
        "display_name": "System Administrator",
        "description": "Full system access with all permissions",
        "level": 100,
        "is_system_role": True,
        "permissions": {
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
    },
    {
        "name": "manager",
        "display_name": "AP Manager",
        "description": "AP team manager with approval and oversight capabilities",
        "level": 80,
        "is_system_role": True,
        "permissions": {
            "invoice": ["read", "write", "approve"],
            "vendor": ["read", "write", "approve"],
            "approval": ["read", "write", "approve"],
            "report": ["read", "write"],
            "export": ["read", "write"],
            "exception": ["read", "write", "approve"],
            "user": ["read"]  # Can view team members
        }
    },
    {
        "name": "ap_clerk",
        "display_name": "AP Clerk",
        "description": "Accounts payable clerk with basic processing capabilities",
        "level": 50,
        "is_system_role": True,
        "permissions": {
            "invoice": ["read", "write"],
            "vendor": ["read", "write"],
            "approval": ["read"],
            "report": ["read"],
            "export": ["read", "write"],
            "exception": ["read", "write"]
        }
    },
    {
        "name": "viewer",
        "display_name": "Viewer",
        "description": "Read-only access for reporting and monitoring",
        "level": 20,
        "is_system_role": True,
        "permissions": {
            "invoice": ["read"],
            "vendor": ["read"],
            "approval": ["read"],
            "report": ["read"],
            "export": ["read"]
        }
    },
    {
        "name": "vendor",
        "display_name": "Vendor",
        "description": "Limited access for vendors to view their own invoices",
        "level": 10,
        "is_system_role": True,
        "permissions": {
            "invoice": ["read"],  # Limited to their own invoices
            "vendor": ["read"]    # Limited to their own profile
        }
    }
]

# Default policy gates for invoice processing
DEFAULT_POLICY_GATES = [
    {
        "name": "high_value_invoice_approval",
        "display_name": "High Value Invoice Approval",
        "description": "Invoices above $10,000 require manager approval",
        "gate_type": PolicyGateType.CURRENCY_THRESHOLD,
        "conditions": {
            "field": "total_amount",
            "operator": ">",
            "value": 10000,
            "currency": "USD"
        },
        "threshold_value": "10000",
        "threshold_type": "currency",
        "action": PolicyAction.REQUIRE_APPROVAL,
        "required_role": "manager",
        "approval_level": 1,
        "priority": 90
    },
    {
        "name": "new_vendor_approval",
        "display_name": "New Vendor Approval",
        "description": "First-time vendors require admin approval",
        "gate_type": PolicyGateType.NEW_VENDOR,
        "conditions": {
            "field": "vendor.is_new",
            "operator": "==",
            "value": True
        },
        "action": PolicyAction.REQUIRE_APPROVAL,
        "required_role": "admin",
        "approval_level": 1,
        "priority": 95
    },
    {
        "name": "negative_amount_blocking",
        "display_name": "Negative Amount Blocking",
        "description": "Block invoices with negative line items",
        "gate_type": PolicyGateType.NEGATIVE_AMOUNTS,
        "conditions": {
            "field": "line_items.amount",
            "operator": "<",
            "value": 0
        },
        "action": PolicyAction.BLOCK,
        "priority": 100
    },
    {
        "name": "duplicate_invoice_detection",
        "display_name": "Duplicate Invoice Detection",
        "description": "Flag potential duplicate invoices for review",
        "gate_type": PolicyGateType.DUPLICATE_INVOICE,
        "conditions": {
            "field": "invoice_number",
            "operator": "duplicate_check",
            "vendor_match": True,
            "amount_match": True,
            "date_range_days": 30
        },
        "action": PolicyAction.FLAG,
        "required_role": "ap_clerk",
        "priority": 85
    },
    {
        "name": "unusual_variance_flagging",
        "display_name": "Unusual Variance Flagging",
        "description": "Flag invoices with unusual amounts for vendor",
        "gate_type": PolicyGateType.UNUSUAL_VARIANCE,
        "conditions": {
            "field": "total_amount",
            "operator": "variance_check",
            "vendor_history_months": 12,
            "variance_threshold": 0.5,  # 50% variance
            "min_invoices": 3
        },
        "action": PolicyAction.FLAG,
        "required_role": "manager",
        "priority": 70
    },
    {
        "name": "exception_limit_approval",
        "display_name": "Exception Limit Approval",
        "description": "Invoices with many exceptions require higher approval",
        "gate_type": PolicyGateType.EXCEPTION_LIMIT,
        "conditions": {
            "field": "exception_count",
            "operator": ">",
            "value": 3
        },
        "action": PolicyAction.ESCALATE,
        "required_role": "manager",
        "approval_level": 2,
        "priority": 75
    }
]