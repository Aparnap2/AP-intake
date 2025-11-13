"""
Staging table models for export workflow management with comprehensive audit trails.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Integer,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class StagingStatus(str, enum.Enum):
    """Staging workflow statuses."""

    PREPARED = "prepared"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ExportFormat(str, enum.Enum):
    """Export format options."""

    CSV = "csv"
    JSON = "json"
    XML = "xml"
    EDI = "edi"
    X12 = "x12"


class StagedExport(Base, UUIDMixin, TimestampMixin):
    """Enhanced staging table for export workflow management."""

    __tablename__ = "staged_exports"

    # Core relationship
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    # Staging workflow
    staging_status = Column(Enum(StagingStatus), default=StagingStatus.PREPARED, nullable=False, index=True)
    export_format = Column(Enum(ExportFormat), nullable=False, index=True)
    destination_system = Column(String(255), nullable=False, index=True)  # ERP system name

    # Data snapshots for audit trail
    prepared_data = Column(JSONB, nullable=False)  # Data when first staged
    approved_data = Column(JSONB, nullable=True)   # Data after approval
    posted_data = Column(JSONB, nullable=True)     # Data as actually posted
    original_data = Column(JSONB, nullable=True)   # Original invoice data for diff

    # Approval workflow tracking
    prepared_by = Column(UUID(as_uuid=True), nullable=True, index=True)
    approved_by = Column(UUID(as_uuid=True), nullable=True, index=True)
    posted_by = Column(UUID(as_uuid=True), nullable=True, index=True)
    rejected_by = Column(UUID(as_uuid=True), nullable=True, index=True)

    prepared_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    approved_at = Column(DateTime(timezone=True), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    # Change tracking and diffs
    diff_summary = Column(JSONB, nullable=True)  # Summary of changes made during review
    change_reason = Column(Text, nullable=True)  # Business reason for changes
    field_changes = Column(JSONB, nullable=True)  # Detailed field-by-field changes

    # Export metadata
    export_job_id = Column(String(100), nullable=True, index=True)  # External job ID
    external_reference = Column(String(255), nullable=True)  # Reference in destination system
    export_filename = Column(String(255), nullable=True)
    export_file_path = Column(Text, nullable=True)
    export_file_size = Column(Integer, nullable=True)

    # Quality and validation
    validation_errors = Column(JSONB, nullable=True)  # Validation errors found
    validation_warnings = Column(JSONB, nullable=True)  # Validation warnings
    quality_score = Column(Integer, nullable=True)  # 0-100 quality score

    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Business context
    batch_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # For batch operations
    priority = Column(Integer, nullable=False, default=5)  # 1-10 priority
    business_unit = Column(String(100), nullable=True, index=True)
    cost_center = Column(String(50), nullable=True, index=True)

    # Compliance and audit
    compliance_flags = Column(ARRAY(String), nullable=True)  # SOX, GDPR, etc.
    audit_notes = Column(Text, nullable=True)
    reviewer_comments = Column(Text, nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_staging_status_priority', 'staging_status', 'priority'),
        Index('idx_staging_invoice_status', 'invoice_id', 'staging_status'),
        Index('idx_staging_destination_status', 'destination_system', 'staging_status'),
        Index('idx_staging_prepared_at', 'prepared_at'),
        Index('idx_staging_approved_at', 'approved_at'),
        Index('idx_staging_batch_status', 'batch_id', 'staging_status'),
        Index('idx_staging_export_job', 'export_job_id'),
        Index('idx_staging_quality_score', 'quality_score', 'staging_status'),
        Index('idx_staging_business_unit', 'business_unit', 'staging_status'),
        Index('idx_staging_cost_center', 'cost_center', 'staging_status'),
        Index('idx_staging_external_ref', 'external_reference'),
        # Check constraints
        CheckConstraint("destination_system <> ''", name='check_destination_system_not_empty'),
        CheckConstraint("priority >= 1 AND priority <= 10", name='check_priority_range'),
        CheckConstraint("retry_count >= 0", name='check_retry_count_non_negative'),
        CheckConstraint("max_retries >= 0", name='check_max_retries_non_negative'),
        CheckConstraint("export_file_size >= 0", name='check_export_file_size_non_negative'),
        CheckConstraint("quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)",
                       name='check_quality_score_range'),
    )

    # Relationships
    invoice = relationship("Invoice", back_populates="staged_exports")
    approval_chain = relationship("StagingApprovalChain", back_populates="staged_export", cascade="all, delete-orphan")
    audit_trail = relationship("StagingAuditTrail", back_populates="staged_export", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StagedExport(id={self.id}, invoice_id={self.invoice_id}, status={self.staging_status})>"

    def can_approve(self) -> bool:
        """Check if the staged export can be approved."""
        return self.staging_status in [StagingStatus.PREPARED, StagingStatus.UNDER_REVIEW]

    def can_post(self) -> bool:
        """Check if the staged export can be posted."""
        return self.staging_status == StagingStatus.APPROVED

    def can_rollback(self) -> bool:
        """Check if the staged export can be rolled back."""
        return self.staging_status == StagingStatus.POSTED

    def mark_approved(self, approved_by_uuid: uuid.UUID, approved_data: Dict[str, Any],
                     change_reason: Optional[str] = None, field_changes: Optional[Dict] = None) -> None:
        """Mark the staged export as approved."""
        self.staging_status = StagingStatus.APPROVED
        self.approved_by = approved_by_uuid
        self.approved_at = datetime.now(timezone.utc)
        self.approved_data = approved_data
        self.change_reason = change_reason
        self.field_changes = field_changes

    def mark_posted(self, posted_by_uuid: uuid.UUID, posted_data: Dict[str, Any],
                   external_reference: Optional[str] = None) -> None:
        """Mark the staged export as posted."""
        self.staging_status = StagingStatus.POSTED
        self.posted_by = posted_by_uuid
        self.posted_at = datetime.now(timezone.utc)
        self.posted_data = posted_data
        self.external_reference = external_reference

    def mark_rejected(self, rejected_by_uuid: uuid.UUID, rejection_reason: str) -> None:
        """Mark the staged export as rejected."""
        self.staging_status = StagingStatus.REJECTED
        self.rejected_by = rejected_by_uuid
        self.rejected_at = datetime.now(timezone.utc)
        self.audit_notes = rejection_reason

    def mark_failed(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Mark the staged export as failed."""
        self.staging_status = StagingStatus.FAILED
        self.error_message = error_message
        self.error_code = error_code
        self.retry_count += 1


class StagingApprovalChain(Base, UUIDMixin, TimestampMixin):
    """Approval chain for staged exports with multi-level approval support."""

    __tablename__ = "staging_approval_chains"

    # Core relationships
    staged_export_id = Column(UUID(as_uuid=True), ForeignKey("staged_exports.id"), nullable=False)
    approver_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Approval details
    approval_level = Column(Integer, nullable=False, index=True)  # 1=first, 2=second, etc.
    approval_status = Column(String(20), nullable=False, default="pending", index=True)  # pending, approved, rejected
    approval_decision = Column(String(20), nullable=True)  # approve, reject, request_changes

    # Approval metadata
    approval_comments = Column(Text, nullable=True)
    business_justification = Column(Text, nullable=True)
    risk_assessment = Column(String(50), nullable=True)  # low, medium, high

    # Timestamps
    approved_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_approval_chain_export_level', 'staged_export_id', 'approval_level'),
        Index('idx_approval_chain_status', 'approval_status', 'expires_at'),
        Index('idx_approval_chain_approver', 'approver_id', 'approval_status'),
        Index('idx_approval_chain_risk', 'risk_assessment', 'approval_status'),
        # Check constraints
        CheckConstraint("approval_level >= 1", name='check_approval_level_positive'),
        CheckConstraint("approval_status IN ('pending', 'approved', 'rejected', 'expired')",
                       name='check_approval_status_valid'),
        CheckConstraint("approval_decision IN ('approve', 'reject', 'request_changes')",
                       name='check_approval_decision_valid'),
        CheckConstraint("risk_assessment IS NULL OR risk_assessment IN ('low', 'medium', 'high')",
                       name='check_risk_assessment_valid'),
    )

    # Relationships
    staged_export = relationship("StagedExport", back_populates="approval_chain")

    def __repr__(self):
        return f"<StagingApprovalChain(id={self.id}, export_id={self.staged_export_id}, level={self.approval_level})>"

    def is_expired(self) -> bool:
        """Check if the approval request has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def can_approve(self) -> bool:
        """Check if this approval can be granted."""
        return (self.approval_status == "pending" and
                not self.is_expired() and
                self.approval_decision is None)


class StagingAuditTrail(Base, UUIDMixin, TimestampMixin):
    """Comprehensive audit trail for all staging operations."""

    __tablename__ = "staging_audit_trails"

    # Core relationship
    staged_export_id = Column(UUID(as_uuid=True), ForeignKey("staged_exports.id"), nullable=False)

    # Audit information
    action = Column(String(50), nullable=False, index=True)  # created, approved, rejected, posted, rolled_back
    action_by = Column(UUID(as_uuid=True), nullable=False, index=True)
    action_reason = Column(Text, nullable=True)

    # State snapshots
    previous_state = Column(JSONB, nullable=True)
    new_state = Column(JSONB, nullable=True)
    data_snapshot = Column(JSONB, nullable=True)  # Complete data snapshot at time of action

    # System information
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True)

    # Business context
    business_event = Column(String(100), nullable=True, index=True)
    impact_assessment = Column(String(50), nullable=True)  # low, medium, high
    compliance_impact = Column(ARRAY(String), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_audit_trail_export_action', 'staged_export_id', 'action'),
        Index('idx_audit_trail_action_by_date', 'action_by', 'created_at'),
        Index('idx_audit_trail_business_event', 'business_event', 'created_at'),
        Index('idx_audit_trail_impact', 'impact_assessment', 'created_at'),
        Index('idx_audit_trail_created_at', 'created_at'),
        # Check constraints
        CheckConstraint("action <> ''", name='check_action_not_empty'),
        CheckConstraint("impact_assessment IS NULL OR impact_assessment IN ('low', 'medium', 'high')",
                       name='check_impact_assessment_valid'),
    )

    # Relationships
    staged_export = relationship("StagedExport", back_populates="audit_trail")

    def __repr__(self):
        return f"<StagingAuditTrail(id={self.id}, export_id={self.staged_export_id}, action={self.action})>"


class StagingBatch(Base, UUIDMixin, TimestampMixin):
    """Batch management for grouped staging operations."""

    __tablename__ = "staging_batches"

    # Batch identification
    batch_name = Column(String(255), nullable=False, index=True)
    batch_description = Column(Text, nullable=True)
    batch_type = Column(String(50), nullable=False, index=True)  # daily, weekly, monthly, ad_hoc

    # Batch workflow
    batch_status = Column(String(20), nullable=False, default="preparing", index=True)
    total_exports = Column(Integer, nullable=False, default=0)
    prepared_exports = Column(Integer, nullable=False, default=0)
    approved_exports = Column(Integer, nullable=False, default=0)
    posted_exports = Column(Integer, nullable=False, default=0)
    failed_exports = Column(Integer, nullable=False, default=0)

    # Batch processing
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_completion_at = Column(DateTime(timezone=True), nullable=True)

    # Quality metrics
    avg_quality_score = Column(Integer, nullable=True)
    total_validation_errors = Column(Integer, nullable=False, default=0)
    total_validation_warnings = Column(Integer, nullable=False, default=0)

    # Owner and approval
    created_by = Column(UUID(as_uuid=True), nullable=True, index=True)
    approved_by = Column(UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_staging_batch_status', 'batch_status', 'created_at'),
        Index('idx_staging_batch_type_status', 'batch_type', 'batch_status'),
        Index('idx_staging_batch_created_by', 'created_by', 'created_at'),
        Index('idx_staging_batch_completion', 'processing_completed_at'),
        # Check constraints
        CheckConstraint("batch_name <> ''", name='check_batch_name_not_empty'),
        CheckConstraint("total_exports >= 0", name='check_total_exports_non_negative'),
        CheckConstraint("prepared_exports >= 0", name='check_prepared_exports_non_negative'),
        CheckConstraint("approved_exports >= 0", name='check_approved_exports_non_negative'),
        CheckConstraint("posted_exports >= 0", name='check_posted_exports_non_negative'),
        CheckConstraint("failed_exports >= 0", name='check_failed_exports_non_negative'),
        CheckConstraint("avg_quality_score IS NULL OR (avg_quality_score >= 0 AND avg_quality_score <= 100)",
                       name='check_avg_quality_score_range'),
    )

    def __repr__(self):
        return f"<StagingBatch(id={self.id}, name={self.batch_name}, status={self.batch_status})>"

    def update_progress(self) -> None:
        """Update batch progress based on current counts."""
        if self.total_exports > 0:
            completion_rate = (self.posted_exports / self.total_exports) * 100
            if completion_rate == 100:
                self.batch_status = "completed"
            elif self.posted_exports > 0:
                self.batch_status = "in_progress"
        elif self.failed_exports > 0:
            self.batch_status = "failed"