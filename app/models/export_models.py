"""
Export-related database models.
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


class ExportFormat(str, enum.Enum):
    """Export format options."""
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    EXCEL = "excel"
    PDF = "pdf"


class ExportStatus(str, enum.Enum):
    """Export processing status."""
    PENDING = "pending"
    PREPARING = "preparing"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportDestination(str, enum.Enum):
    """Export destination options."""
    DOWNLOAD = "download"
    FILE_STORAGE = "file_storage"
    API_ENDPOINT = "api_endpoint"
    EMAIL = "email"
    FTP = "ftp"


class ExportTemplate(Base, UUIDMixin, TimestampMixin):
    """Export template configuration."""

    __tablename__ = "export_templates"

    # Template details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    format = Column(Enum(ExportFormat), nullable=False)

    # Template configuration
    field_mappings = Column(JSON, nullable=False)
    header_config = Column(JSON, nullable=True)
    footer_config = Column(JSON, nullable=True)

    # Processing options
    compression = Column(Boolean, default=False, nullable=False)
    encryption = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_template_name_format', 'name', 'format'),
        Index('idx_template_active_updated', 'is_active', 'updated_at'),
        UniqueConstraint('name', 'format', name='uq_template_name_format'),
    )

    # Relationships
    export_jobs = relationship("ExportJob", back_populates="template")

    def __repr__(self):
        return f"<ExportTemplate(id={self.id}, name={self.name}, format={self.format})>"


class ExportJob(Base, UUIDMixin, TimestampMixin):
    """Export job tracking."""

    __tablename__ = "export_jobs"

    # Job details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("export_templates.id"), nullable=False)

    # Job configuration
    format = Column(Enum(ExportFormat), nullable=False)
    destination = Column(Enum(ExportDestination), nullable=False)
    destination_config = Column(JSON, nullable=False)

    # Filtering criteria
    filters = Column(JSON, nullable=True)
    invoice_ids = Column(JSON, nullable=True)  # List of specific invoice IDs

    # Job status and progress
    status = Column(Enum(ExportStatus), default=ExportStatus.PENDING, nullable=False, index=True)
    total_records = Column(Integer, nullable=True)
    processed_records = Column(Integer, default=0, nullable=False)
    failed_records = Column(Integer, default=0, nullable=False)

    # Timing information
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_completion = Column(DateTime(timezone=True), nullable=True)

    # Results
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    record_count = Column(Integer, nullable=True)

    # Error information
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Job configuration
    priority = Column(Integer, default=5, nullable=False)
    batch_size = Column(Integer, default=1000, nullable=False)
    notify_on_completion = Column(Boolean, default=False, nullable=False)
    notification_config = Column(JSON, nullable=True)

    # User tracking
    created_by = Column(String(255), nullable=True)
    user_id = Column(String(255), nullable=True, index=True)

    # Indexes and constraints
    __table_args__ = (
        Index('idx_job_status_created', 'status', 'created_at'),
        Index('idx_job_user_status', 'user_id', 'status'),
        Index('idx_job_template_status', 'template_id', 'status'),
        Index('idx_job_priority_status', 'priority', 'status'),
        Index('idx_job_created_at', 'created_at'),
        Index('idx_job_started_at', 'started_at'),
        Index('idx_job_completed_at', 'completed_at'),
    )

    # Relationships
    template = relationship("ExportTemplate", back_populates="export_jobs")
    audit_logs = relationship("ExportAuditLog", back_populates="export_job", cascade="all, delete-orphan")
    metrics = relationship("ExportMetrics", back_populates="export_job", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExportJob(id={self.id}, name={self.name}, status={self.status})>"


class ExportAuditLog(Base, UUIDMixin, TimestampMixin):
    """Export audit log entries."""

    __tablename__ = "export_audit_logs"

    # Job reference
    export_job_id = Column(UUID(as_uuid=True), ForeignKey("export_jobs.id"), nullable=False)

    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)

    # User tracking
    user_id = Column(String(255), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # Support IPv6

    # Performance tracking
    processing_time_ms = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_audit_job_timestamp', 'export_job_id', 'created_at'),
        Index('idx_audit_event_type', 'event_type', 'created_at'),
        Index('idx_audit_user_timestamp', 'user_id', 'created_at'),
    )

    # Relationships
    export_job = relationship("ExportJob", back_populates="audit_logs")

    def __repr__(self):
        return f"<ExportAuditLog(id={self.id}, job_id={self.export_job_id}, event={self.event_type})>"


class ExportMetrics(Base, UUIDMixin, TimestampMixin):
    """Export performance metrics."""

    __tablename__ = "export_metrics"

    # Job reference
    export_job_id = Column(UUID(as_uuid=True), ForeignKey("export_jobs.id"), nullable=False, unique=True)

    # Processing metrics
    total_records = Column(Integer, nullable=False)
    successful_records = Column(Integer, nullable=False)
    failed_records = Column(Integer, nullable=False)
    skipped_records = Column(Integer, default=0, nullable=False)

    # Timing metrics
    processing_time_seconds = Column(Integer, nullable=False)
    validation_time_seconds = Column(Integer, nullable=True)
    transformation_time_seconds = Column(Integer, nullable=True)
    upload_time_seconds = Column(Integer, nullable=True)

    # File metrics
    file_size_bytes = Column(Integer, nullable=False)
    compressed_size_bytes = Column(Integer, nullable=True)
    compression_ratio = Column(Integer, nullable=True)  # Percentage

    # Performance metrics
    records_per_second = Column(Integer, nullable=False)
    peak_memory_usage_mb = Column(Integer, nullable=True)
    average_record_size_bytes = Column(Integer, nullable=True)

    # Error metrics
    validation_errors = Column(Integer, default=0, nullable=False)
    transformation_errors = Column(Integer, default=0, nullable=False)
    upload_errors = Column(Integer, default=0, nullable=False)

    # System metrics
    cpu_usage_percent = Column(Integer, nullable=True)
    disk_io_mb = Column(Integer, nullable=True)
    network_io_mb = Column(Integer, nullable=True)

    # Relationships
    export_job = relationship("ExportJob", back_populates="metrics")

    def __repr__(self):
        return f"<ExportMetrics(id={self.id}, job_id={self.export_job_id}, records={self.total_records})>"


class ExportValidationRule(Base, UUIDMixin, TimestampMixin):
    """Export validation rules."""

    __tablename__ = "export_validation_rules"

    # Rule details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("export_templates.id"), nullable=True)

    # Rule configuration
    field_path = Column(String(500), nullable=False)
    rule_type = Column(String(100), nullable=False)
    rule_config = Column(JSON, nullable=False)
    error_message = Column(String(500), nullable=False)
    severity = Column(String(20), default="error", nullable=False)

    # Rule status
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_validation_template', 'template_id', 'is_active'),
        Index('idx_validation_field_type', 'field_path', 'rule_type'),
        UniqueConstraint('name', 'template_id', name='uq_validation_rule_name_template'),
    )

    def __repr__(self):
        return f"<ExportValidationRule(id={self.id}, name={self.name}, type={self.rule_type})>"


class ExportSchedule(Base, UUIDMixin, TimestampMixin):
    """Scheduled export jobs."""

    __tablename__ = "export_schedules"

    # Schedule details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("export_templates.id"), nullable=False)

    # Schedule configuration
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)

    # Export configuration
    filters = Column(JSON, nullable=True)
    destination_config = Column(JSON, nullable=False)
    notification_config = Column(JSON, nullable=True)

    # Schedule status
    is_active = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    # Execution tracking
    total_runs = Column(Integer, default=0, nullable=False)
    successful_runs = Column(Integer, default=0, nullable=False)
    failed_runs = Column(Integer, default=0, nullable=False)

    # User tracking
    created_by = Column(String(255), nullable=True)

    # Relationships
    template = relationship("ExportTemplate")

    # Indexes
    __table_args__ = (
        Index('idx_schedule_next_run', 'next_run_at', 'is_active'),
        Index('idx_schedule_template', 'template_id', 'is_active'),
        UniqueConstraint('name', name='uq_schedule_name'),
    )

    def __repr__(self):
        return f"<ExportSchedule(id={self.id}, name={self.name}, next_run={self.next_run_at})>"