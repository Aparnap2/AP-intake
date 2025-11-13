"""
Dead Letter Queue models for handling failed Celery tasks.

This module provides comprehensive DLQ functionality including:
- Task failure capture with full context
- Redrive tracking with retry history
- Error categorization and analysis
- Circuit breaker pattern integration
"""

import enum
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON,
    Index, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class DLQStatus(str, enum.Enum):
    """DLQ entry status."""
    PENDING = "pending"
    PROCESSING = "processing"
    REDRIVING = "redriving"
    COMPLETED = "completed"
    FAILED_PERMANENTLY = "failed_permanently"
    ARCHIVED = "archived"


class DLQCategory(str, enum.Enum):
    """DLQ entry categories for error classification."""
    PROCESSING_ERROR = "processing_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    TIMEOUT_ERROR = "timeout_error"
    BUSINESS_RULE_ERROR = "business_rule_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN_ERROR = "unknown_error"


class DLQPriority(str, enum.Enum):
    """DLQ entry priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeadLetterQueue(Base):
    """
    Dead Letter Queue entry for failed Celery tasks.

    This model captures comprehensive information about failed tasks
    including original task data, error details, and retry history.
    """
    __tablename__ = "dead_letter_queue"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    task_id = Column(String(255), unique=True, nullable=False, index=True)
    task_name = Column(String(255), nullable=False, index=True)

    # Task data
    task_args = Column(JSON, nullable=True)
    task_kwargs = Column(JSON, nullable=True)
    original_task_data = Column(JSON, nullable=True)

    # Error information
    error_type = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    error_stack_trace = Column(Text, nullable=True)
    error_category = Column(
        Enum(DLQCategory),
        default=DLQCategory.UNKNOWN_ERROR,
        nullable=False,
        index=True
    )

    # Retry information
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Classification and priority
    dlq_status = Column(
        Enum(DLQStatus),
        default=DLQStatus.PENDING,
        nullable=False,
        index=True
    )
    priority = Column(
        Enum(DLQPriority),
        default=DLQPriority.NORMAL,
        nullable=False,
        index=True
    )

    # Relationships and linking
    idempotency_key = Column(String(255), nullable=True, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True)

    # Metadata
    worker_name = Column(String(255), nullable=True)
    queue_name = Column(String(100), nullable=True, index=True)
    execution_time = Column(Integer, nullable=True)  # Time in seconds

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Redrive history
    redrive_history = Column(JSON, nullable=True)  # List of redrive attempts
    manual_intervention = Column(Boolean, default=False, nullable=False)
    intervention_reason = Column(Text, nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="dlq_entries")

    # Indexes for performance
    __table_args__ = (
        Index('idx_dlq_status_priority', 'dlq_status', 'priority'),
        Index('idx_dlq_created_at', 'created_at'),
        Index('idx_dlq_next_retry', 'next_retry_at'),
        Index('idx_dlq_task_name_status', 'task_name', 'dlq_status'),
        Index('idx_dlq_category_status', 'error_category', 'dlq_status'),
    )

    def __repr__(self) -> str:
        return (
            f"<DeadLetterQueue(id={self.id}, task_id={self.task_id}, "
            f"task_name={self.task_name}, status={self.dlq_status})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert DLQ entry to dictionary."""
        return {
            "id": str(self.id),
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_args": self.task_args,
            "task_kwargs": self.task_kwargs,
            "original_task_data": self.original_task_data,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
            "error_category": self.error_category.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "dlq_status": self.dlq_status.value,
            "priority": self.priority.value,
            "idempotency_key": self.idempotency_key,
            "invoice_id": str(self.invoice_id) if self.invoice_id else None,
            "worker_name": self.worker_name,
            "queue_name": self.queue_name,
            "execution_time": self.execution_time,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "redrive_history": self.redrive_history,
            "manual_intervention": self.manual_intervention,
            "intervention_reason": self.intervention_reason,
        }

    def add_redrive_attempt(self, success: bool, error_message: Optional[str] = None):
        """Add a redrive attempt to the history."""
        if not self.redrive_history:
            self.redrive_history = []

        attempt = {
            "attempt_number": len(self.redrive_history) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "error_message": error_message,
        }

        self.redrive_history.append(attempt)
        self.retry_count += 1
        self.last_retry_at = datetime.now(timezone.utc)

        if success:
            self.dlq_status = DLQStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)
        elif self.retry_count >= self.max_retries:
            self.dlq_status = DLQStatus.FAILED_PERMANENTLY
        else:
            # Calculate next retry time with exponential backoff
            import math
            delay = min(300, math.pow(2, self.retry_count) * 60)  # Max 5 minutes
            self.next_retry_at = datetime.now(timezone.utc).timestamp() + delay
            self.dlq_status = DLQStatus.PENDING


# Pydantic schemas for API
class DLQEntryBase(BaseModel):
    """Base DLQ entry schema."""
    task_id: str = Field(..., description="Unique task identifier")
    task_name: str = Field(..., description="Name of the failed task")
    task_args: Optional[List[Any]] = Field(None, description="Task arguments")
    task_kwargs: Optional[Dict[str, Any]] = Field(None, description="Task keyword arguments")
    error_type: str = Field(..., description="Type of error that occurred")
    error_message: str = Field(..., description="Detailed error message")
    error_stack_trace: Optional[str] = Field(None, description="Full error stack trace")
    error_category: DLQCategory = Field(DLQCategory.UNKNOWN_ERROR, description="Error category")
    priority: DLQPriority = Field(DLQPriority.NORMAL, description="Entry priority")
    idempotency_key: Optional[str] = Field(None, description="Task idempotency key")
    invoice_id: Optional[uuid.UUID] = Field(None, description="Related invoice ID")
    worker_name: Optional[str] = Field(None, description="Worker that processed the task")
    queue_name: Optional[str] = Field(None, description="Queue the task was in")
    execution_time: Optional[int] = Field(None, description="Task execution time in seconds")


class DLQEntryCreate(DLQEntryBase):
    """Schema for creating DLQ entries."""
    original_task_data: Optional[Dict[str, Any]] = Field(None, description="Original task metadata")
    max_retries: int = Field(3, description="Maximum number of retries")


class DLQEntryUpdate(BaseModel):
    """Schema for updating DLQ entries."""
    dlq_status: Optional[DLQStatus] = Field(None, description="Update DLQ status")
    priority: Optional[DLQPriority] = Field(None, description="Update priority")
    manual_intervention: Optional[bool] = Field(None, description="Mark for manual intervention")
    intervention_reason: Optional[str] = Field(None, description="Reason for manual intervention")


class DLQEntry(DLQEntryBase):
    """Schema for DLQ entry responses."""
    id: uuid.UUID = Field(..., description="DLQ entry ID")
    retry_count: int = Field(..., description="Current retry count")
    max_retries: int = Field(..., description="Maximum retries allowed")
    last_retry_at: Optional[datetime] = Field(None, description="Last retry timestamp")
    next_retry_at: Optional[datetime] = Field(None, description="Next scheduled retry")
    dlq_status: DLQStatus = Field(..., description="Current DLQ status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    redrive_history: Optional[List[Dict[str, Any]]] = Field(None, description="Redrive attempt history")

    class Config:
        from_attributes = True


class DLQStats(BaseModel):
    """DLQ statistics schema."""
    total_entries: int = Field(..., description="Total DLQ entries")
    pending_entries: int = Field(..., description="Entries pending redrive")
    processing_entries: int = Field(..., description="Entries currently processing")
    completed_entries: int = Field(..., description="Successfully completed entries")
    failed_permanently: int = Field(..., description="Permanently failed entries")
    archived_entries: int = Field(..., description="Archived entries")

    # By category
    processing_errors: int = Field(..., description="Processing error count")
    validation_errors: int = Field(..., description="Validation error count")
    network_errors: int = Field(..., description="Network error count")
    database_errors: int = Field(..., description="Database error count")
    timeout_errors: int = Field(..., description="Timeout error count")
    business_rule_errors: int = Field(..., description="Business rule error count")
    system_errors: int = Field(..., description="System error count")
    unknown_errors: int = Field(..., description="Unknown error count")

    # By priority
    critical_entries: int = Field(..., description="Critical priority entries")
    high_entries: int = Field(..., description="High priority entries")
    normal_entries: int = Field(..., description="Normal priority entries")
    low_entries: int = Field(..., description="Low priority entries")

    # Aging
    avg_age_hours: float = Field(..., description="Average age of entries in hours")
    oldest_entry_age_hours: float = Field(..., description="Age of oldest entry in hours")


class RedriveRequest(BaseModel):
    """Schema for redrive requests."""
    dlq_ids: List[uuid.UUID] = Field(..., description="List of DLQ entry IDs to redrive")
    force: bool = Field(False, description="Force redrive even if max retries exceeded")
    modify_args: Optional[Dict[str, Any]] = Field(None, description="Optional argument modifications")
    priority: Optional[DLQPriority] = Field(None, description="Optional priority override")


class RedriveResponse(BaseModel):
    """Schema for redrive responses."""
    success_count: int = Field(..., description="Number of successful redrives")
    failed_count: int = Field(..., description="Number of failed redrives")
    skipped_count: int = Field(..., description="Number of skipped entries")
    results: List[Dict[str, Any]] = Field(..., description="Detailed results for each entry")

    class Config:
        from_attributes = True