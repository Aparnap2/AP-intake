"""
Idempotency management models for ensuring operation safety and preventing duplicates.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

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
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class IdempotencyOperationType(str, enum.Enum):
    """Types of operations that can be made idempotent."""

    INVOICE_UPLOAD = "invoice_upload"
    INVOICE_PROCESS = "invoice_process"
    EXPORT_STAGE = "export_stage"
    EXPORT_POST = "export_post"
    EXCEPTION_RESOLVE = "exception_resolve"
    BATCH_OPERATION = "batch_operation"


class IdempotencyStatus(str, enum.Enum):
    """Status of idempotency record."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IdempotencyRecord(Base, UUIDMixin, TimestampMixin):
    """Comprehensive idempotency tracking for operation safety."""

    __tablename__ = "idempotency_records"

    # Idempotency key information
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    operation_type = Column(Enum(IdempotencyOperationType), nullable=False, index=True)
    operation_status = Column(Enum(IdempotencyStatus), default=IdempotencyStatus.PENDING, nullable=False, index=True)

    # Resource tracking
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True)
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=True, index=True)

    # Operation data
    operation_data = Column(JSONB, nullable=False)  # Original request data
    result_data = Column(JSONB, nullable=True)     # Operation result
    error_data = Column(JSONB, nullable=True)      # Error details if failed

    # Execution tracking
    execution_count = Column(Integer, nullable=False, default=0)
    max_executions = Column(Integer, nullable=False, default=1)  # Max retry attempts
    first_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Expiration and cleanup
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ttl_seconds = Column(Integer, nullable=True)  # Time to live in seconds

    # Security and ownership
    user_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True)
    client_ip = Column(String(45), nullable=True)  # IPv6 compatible

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_idempotency_key_status', 'idempotency_key', 'operation_status'),
        Index('idx_idempotency_operation_created', 'operation_type', 'created_at'),
        Index('idx_idempotency_expires_status', 'expires_at', 'operation_status'),
        Index('idx_idempotency_user_operation', 'user_id', 'operation_type'),
        Index('idx_idempotency_invoice_status', 'invoice_id', 'operation_status'),
        Index('idx_idempotency_execution_tracking', 'execution_count', 'last_attempt_at'),
        # Unique constraints
        UniqueConstraint('idempotency_key', name='uq_idempotency_key'),
        # Check constraints
        CheckConstraint("idempotency_key <> ''", name='check_idempotency_key_not_empty'),
        CheckConstraint("execution_count >= 0", name='check_execution_count_non_negative'),
        CheckConstraint("max_executions >= 1", name='check_max_executions_positive'),
        CheckConstraint("ttl_seconds IS NULL OR ttl_seconds > 0", name='check_ttl_seconds_positive'),
    )

    # Relationships
    invoice = relationship("Invoice", back_populates="idempotency_records")
    ingestion_job = relationship("IngestionJob", back_populates="idempotency_records")

    def __repr__(self):
        return f"<IdempotencyRecord(id={self.id}, key={self.idempotency_key}, status={self.operation_status})>"

    def is_expired(self) -> bool:
        """Check if the idempotency record has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def can_execute(self) -> bool:
        """Check if the operation can be executed."""
        if self.is_expired():
            return False
        if self.operation_status == IdempotencyStatus.COMPLETED:
            return False
        if self.execution_count >= self.max_executions:
            return False
        return True

    def mark_attempt(self) -> None:
        """Mark an execution attempt."""
        self.execution_count += 1
        if not self.first_attempt_at:
            self.first_attempt_at = datetime.now(timezone.utc)
        self.last_attempt_at = datetime.now(timezone.utc)

    def mark_completed(self, result_data: Dict[str, Any]) -> None:
        """Mark operation as completed with result."""
        self.operation_status = IdempotencyStatus.COMPLETED
        self.result_data = result_data
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, error_data: Dict[str, Any]) -> None:
        """Mark operation as failed with error details."""
        self.operation_status = IdempotencyStatus.FAILED
        self.error_data = error_data

    def mark_in_progress(self) -> None:
        """Mark operation as in progress."""
        self.operation_status = IdempotencyStatus.IN_PROGRESS


class IdempotencyConflict(Base, UUIDMixin, TimestampMixin):
    """Records of idempotency conflicts and their resolutions."""

    __tablename__ = "idempotency_conflicts"

    # Conflict identification
    idempotency_record_id = Column(UUID(as_uuid=True), ForeignKey("idempotency_records.id"), nullable=False)
    conflict_key = Column(String(255), nullable=False, index=True)

    # Conflict details
    conflict_type = Column(String(50), nullable=False, index=True)  # duplicate, concurrent, expired
    conflict_reason = Column(Text, nullable=False)
    conflicting_operation_data = Column(JSONB, nullable=False)

    # Resolution tracking
    resolution_action = Column(String(50), nullable=True)  # reject, merge, retry, manual
    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_conflict_record_id', 'idempotency_record_id'),
        Index('idx_conflict_key_type', 'conflict_key', 'conflict_type'),
        Index('idx_conflict_resolved_at', 'resolved_at'),
        Index('idx_conflict_created_at', 'created_at'),
        # Check constraints
        CheckConstraint("conflict_key <> ''", name='check_conflict_key_not_empty'),
        CheckConstraint("conflict_reason IS NOT NULL", name='check_conflict_reason_not_null'),
    )

    # Relationships
    idempotency_record = relationship("IdempotencyRecord")

    def __repr__(self):
        return f"<IdempotencyConflict(id={self.id}, key={self.conflict_key}, type={self.conflict_type})>"


class IdempotencyMetric(Base, UUIDMixin, TimestampMixin):
    """Daily metrics for idempotency system performance."""

    __tablename__ = "idempotency_metrics"

    # Metric date and scope
    metric_date = Column(DateTime(timezone=True), nullable=False, index=True)
    operation_type = Column(Enum(IdempotencyOperationType), nullable=True, index=True)

    # Operation counts
    total_operations = Column(Integer, nullable=False, default=0)
    successful_operations = Column(Integer, nullable=False, default=0)
    failed_operations = Column(Integer, nullable=False, default=0)
    duplicate_prevented = Column(Integer, nullable=False, default=0)
    conflicts_detected = Column(Integer, nullable=False, default=0)

    # Performance metrics
    avg_execution_time_ms = Column(Integer, nullable=True)
    max_execution_time_ms = Column(Integer, nullable=True)
    cache_hit_rate = Column(Integer, nullable=True)  # Percentage

    # Error breakdown
    error_types = Column(JSONB, nullable=True)  # Error type counts

    # Performance indexes
    __table_args__ = (
        Index('idx_idempotency_metrics_date', 'metric_date'),
        Index('idx_idempotency_metrics_date_operation', 'metric_date', 'operation_type'),
        # Check constraints
        CheckConstraint("total_operations >= 0", name='check_total_operations_non_negative'),
        CheckConstraint("successful_operations >= 0", name='check_successful_operations_non_negative'),
        CheckConstraint("failed_operations >= 0", name='check_failed_operations_non_negative'),
        CheckConstraint("duplicate_prevented >= 0", name='check_duplicate_prevented_non_negative'),
        CheckConstraint("conflicts_detected >= 0", name='check_conflicts_detected_non_negative'),
        CheckConstraint("avg_execution_time_ms >= 0", name='check_avg_execution_time_non_negative'),
        CheckConstraint("max_execution_time_ms >= 0", name='check_max_execution_time_non_negative'),
        CheckConstraint("cache_hit_rate IS NULL OR (cache_hit_rate >= 0 AND cache_hit_rate <= 100)",
                       name='check_cache_hit_rate_range'),
    )

    def __repr__(self):
        return f"<IdempotencyMetric(id={self.id}, date={self.metric_date}, total={self.total_operations})>"