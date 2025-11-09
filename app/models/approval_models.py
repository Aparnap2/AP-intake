"""
Approval workflow related database models.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
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


class ApprovalStatus(str, enum.Enum):
    """Approval status options."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalAction(str, enum.Enum):
    """Approval action types."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"
    ESCALATE = "escalate"


class ApprovalRole(str, enum.Enum):
    """Approval role types."""
    AP_CLERK = "ap_clerk"
    AP_MANAGER = "ap_manager"
    CONTROLLER = "controller"
    CFO = "cfo"
    FINANCE_DIRECTOR = "finance_director"
    AUDITOR = "auditor"
    SYSTEM_ADMIN = "system_admin"


class WorkflowType(str, enum.Enum):
    """Workflow types."""
    INVOICE_EXPORT = "invoice_export"
    BULK_EXPORT = "bulk_export"
    PAYMENT_APPROVAL = "payment_approval"
    VENDOR_APPROVAL = "vendor_approval"
    EXCEPTION_APPROVAL = "exception_approval"
    SYSTEM_CONFIG = "system_config"


class ApprovalWorkflow(Base, UUIDMixin, TimestampMixin):
    """Approval workflow definitions."""

    __tablename__ = "approval_workflows"

    # Workflow details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    workflow_type = Column(Enum(WorkflowType), nullable=False)

    # Workflow configuration
    configuration = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timeout settings
    default_timeout_hours = Column(Integer, default=72, nullable=False)

    # User tracking
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_workflow_type_active', 'workflow_type', 'is_active'),
        Index('idx_workflow_created_by', 'created_by'),
        UniqueConstraint('name', 'workflow_type', name='uq_workflow_name_type'),
    )

    # Relationships
    steps = relationship("ApprovalStep", back_populates="workflow", cascade="all, delete-orphan")
    requests = relationship("ApprovalRequest", back_populates="workflow")
    audit_logs = relationship("ApprovalAuditLog", back_populates="workflow")

    def __repr__(self):
        return f"<ApprovalWorkflow(id={self.id}, name={self.name}, type={self.workflow_type})>"


class ApprovalStep(Base, UUIDMixin, TimestampMixin):
    """Individual steps in an approval workflow."""

    __tablename__ = "approval_steps"

    # Step details
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("approval_workflows.id"), nullable=False)
    step_name = Column(String(255), nullable=False)
    step_order = Column(Integer, nullable=False)

    # Approval configuration
    approval_role = Column(Enum(ApprovalRole), nullable=False)
    required_approvers = Column(Integer, default=1, nullable=False)
    is_parallel = Column(Boolean, default=False, nullable=False)

    # Timeout and conditions
    timeout_hours = Column(Integer, nullable=True)
    auto_approve_conditions = Column(JSON, nullable=True)
    reject_conditions = Column(JSON, nullable=True)

    # Step configuration
    configuration = Column(JSON, nullable=False, default=dict)

    # Step metadata
    description = Column(Text, nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_step_workflow_order', 'workflow_id', 'step_order'),
        Index('idx_step_role', 'approval_role'),
        UniqueConstraint('workflow_id', 'step_order', name='uq_step_workflow_order'),
    )

    # Relationships
    workflow = relationship("ApprovalWorkflow", back_populates="steps")
    decisions = relationship("ApprovalDecision", back_populates="step")
    assignments = relationship("ApproverAssignment", back_populates="step")

    def __repr__(self):
        return f"<ApprovalStep(id={self.id}, workflow_id={self.workflow_id}, order={self.step_order})>"


class ApprovalRequest(Base, UUIDMixin, TimestampMixin):
    """Individual approval requests."""

    __tablename__ = "approval_requests"

    # Request details
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("approval_workflows.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Entity information
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Priority and status
    priority = Column(Integer, default=5, nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True)
    current_step = Column(Integer, default=1, nullable=False)

    # User tracking
    requested_by = Column(String(255), nullable=False, index=True)

    # Timing
    expires_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Request data
    context_data = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_request_status_priority', 'status', 'priority'),
        Index('idx_request_entity', 'entity_type', 'entity_id'),
        Index('idx_request_requested_by', 'requested_by', 'created_at'),
        Index('idx_request_expires_at', 'expires_at'),
        Index('idx_request_workflow_status', 'workflow_id', 'status'),
    )

    # Relationships
    workflow = relationship("ApprovalWorkflow", back_populates="requests")
    decisions = relationship("ApprovalDecision", back_populates="request", cascade="all, delete-orphan")
    assignments = relationship("ApproverAssignment", back_populates="request", cascade="all, delete-orphan")
    audit_logs = relationship("ApprovalAuditLog", back_populates="request")

    def __repr__(self):
        return f"<ApprovalRequest(id={self.id}, title={self.title}, status={self.status})>"


class ApprovalDecision(Base, UUIDMixin, TimestampMixin):
    """Decisions made by approvers."""

    __tablename__ = "approval_decisions"

    # Decision details
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False)
    step_id = Column(UUID(as_uuid=True), ForeignKey("approval_steps.id"), nullable=False)

    # Decision data
    approver_id = Column(String(255), nullable=False, index=True)
    action = Column(Enum(ApprovalAction), nullable=False)
    comments = Column(Text, nullable=True)
    decision_data = Column(JSON, nullable=True)

    # Timing
    decision_time = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_decision_request_approver', 'approval_request_id', 'approver_id'),
        Index('idx_decision_step_action', 'step_id', 'action'),
        Index('idx_decision_approver_time', 'approver_id', 'decision_time'),
    )

    # Relationships
    request = relationship("ApprovalRequest", back_populates="decisions")
    step = relationship("ApprovalStep", back_populates="decisions")

    def __repr__(self):
        return f"<ApprovalDecision(id={self.id}, request_id={self.approval_request_id}, action={self.action})>"


class ApproverAssignment(Base, UUIDMixin, TimestampMixin):
    """Assignments of approvers to workflow steps."""

    __tablename__ = "approver_assignments"

    # Assignment details
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False)
    step_id = Column(UUID(as_uuid=True), ForeignKey("approval_steps.id"), nullable=False)
    user_id = Column(String(255), nullable=False, index=True)

    # Assignment status
    status = Column(String(50), default="pending", nullable=False, index=True)
    delegated_to = Column(String(255), nullable=True)

    # Assignment metadata
    assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Assignment configuration
    assignment_data = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_assignment_user_status', 'user_id', 'status'),
        Index('idx_assignment_step_user', 'step_id', 'user_id'),
        Index('idx_assignment_request_step', 'approval_request_id', 'step_id'),
        UniqueConstraint('approval_request_id', 'step_id', 'user_id', name='uq_assignment_request_step_user'),
    )

    # Relationships
    request = relationship("ApprovalRequest", back_populates="assignments")
    step = relationship("ApprovalStep", back_populates="assignments")

    def __repr__(self):
        return f"<ApproverAssignment(id={self.id}, user_id={self.user_id}, status={self.status})>"


class ApprovalAuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit log for approval workflow events."""

    __tablename__ = "approval_audit_logs"

    # Event details
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("approval_workflows.id"), nullable=True)
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=True)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)

    # User tracking
    user_id = Column(String(255), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # System information
    session_id = Column(String(255), nullable=True)
    correlation_id = Column(String(100), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_audit_workflow_timestamp', 'workflow_id', 'created_at'),
        Index('idx_audit_request_timestamp', 'approval_request_id', 'created_at'),
        Index('idx_audit_event_type', 'event_type', 'created_at'),
        Index('idx_audit_user_timestamp', 'user_id', 'created_at'),
    )

    # Relationships
    workflow = relationship("ApprovalWorkflow", back_populates="audit_logs")
    request = relationship("ApprovalRequest", back_populates="audit_logs")

    def __repr__(self):
        return f"<ApprovalAuditLog(id={self.id}, event_type={self.event_type})>"


class ApprovalTemplate(Base, UUIDMixin, TimestampMixin):
    """Templates for common approval workflows."""

    __tablename__ = "approval_templates"

    # Template details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)

    # Template configuration
    workflow_config = Column(JSON, nullable=False)
    steps_config = Column(JSON, nullable=False)

    # Template metadata
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # User tracking
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_template_category_active', 'category', 'is_active'),
        Index('idx_template_public_active', 'is_public', 'is_active'),
        UniqueConstraint('name', 'category', name='uq_template_name_category'),
    )

    def __repr__(self):
        return f"<ApprovalTemplate(id={self.id}, name={self.name}, category={self.category})>"


class ApprovalNotification(Base, UUIDMixin, TimestampMixin):
    """Notifications sent for approval events."""

    __tablename__ = "approval_notifications"

    # Notification details
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False)
    user_id = Column(String(255), nullable=False, index=True)

    # Notification content
    notification_type = Column(String(100), nullable=False)
    subject = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)

    # Delivery information
    delivery_method = Column(String(50), nullable=False)  # email, sms, push, etc.
    recipient_address = Column(String(255), nullable=False)

    # Status tracking
    status = Column(String(50), default="pending", nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_notification_user_status', 'user_id', 'status'),
        Index('idx_notification_request_type', 'approval_request_id', 'notification_type'),
        Index('idx_notification_delivery_method', 'delivery_method', 'status'),
    )

    def __repr__(self):
        return f"<ApprovalNotification(id={self.id}, type={self.notification_type}, status={self.status})>"