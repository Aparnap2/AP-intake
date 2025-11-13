"""
Metrics and SLO-related database models for AP Intake & Validation system.
"""

import enum
import uuid
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Date as SQLDate,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    Integer,
    Float,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class SLIType(str, enum.Enum):
    """Service Level Indicator types."""

    TIME_TO_READY = "time_to_ready"
    VALIDATION_PASS_RATE = "validation_pass_rate"
    DUPLICATE_RECALL = "duplicate_recall"
    APPROVAL_LATENCY = "approval_latency"
    PROCESSING_SUCCESS_RATE = "processing_success_rate"
    EXTRACTION_ACCURACY = "extraction_accuracy"
    EXCEPTION_RESOLUTION_TIME = "exception_resolution_time"


class SLOPeriod(str, enum.Enum):
    """SLO measurement periods."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SLODefinition(Base, UUIDMixin, TimestampMixin):
    """SLO definitions with targets and error budget policies."""

    __tablename__ = "slo_definitions"

    # SLO identification
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    sli_type = Column(Enum(SLIType), nullable=False, index=True)

    # Target configuration
    target_percentage = Column(Numeric(5, 2), nullable=False)  # e.g., 95.00
    target_value = Column(Numeric(10, 2), nullable=True)  # e.g., 5.0 (minutes)
    target_unit = Column(String(20), nullable=True)  # e.g., "minutes", "percentage"

    # Error budget configuration
    error_budget_percentage = Column(Numeric(5, 2), nullable=False, default=5.0)
    alerting_threshold_percentage = Column(Numeric(5, 2), nullable=False, default=80.0)

    # Measurement configuration
    measurement_period = Column(Enum(SLOPeriod), nullable=False, default=SLOPeriod.DAILY)
    burn_rate_alert_threshold = Column(Numeric(5, 2), nullable=False, default=2.0)

    # Status and configuration
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    slos_owner = Column(String(100), nullable=True)
    notification_channels = Column(JSON, nullable=True)  # List of channel configs

    # Performance indexes
    __table_args__ = (
        Index('idx_slo_type_active', 'sli_type', 'is_active'),
        Index('idx_slo_period_active', 'measurement_period', 'is_active'),
        CheckConstraint("target_percentage > 0 AND target_percentage <= 100", name='check_target_percentage_range'),
        CheckConstraint("error_budget_percentage >= 0 AND error_budget_percentage <= 100", name='check_error_budget_range'),
        CheckConstraint("alerting_threshold_percentage >= 0 AND alerting_threshold_percentage <= 100", name='check_alert_threshold_range'),
    )

    # Relationships
    measurements = relationship("SLIMeasurement", back_populates="slo_definition", cascade="all, delete-orphan")
    alerts = relationship("SLOAlert", back_populates="slo_definition", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SLODefinition(name={self.name}, sli_type={self.sli_type}, target={self.target_percentage}%>"


class SLIMeasurement(Base, UUIDMixin, TimestampMixin):
    """Individual SLI measurements over time."""

    __tablename__ = "sli_measurements"

    # Measurement identification
    slo_definition_id = Column(UUID(as_uuid=True), ForeignKey("slo_definitions.id"), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    measurement_period = Column(Enum(SLOPeriod), nullable=False, index=True)

    # Measurement values
    actual_value = Column(Numeric(10, 2), nullable=False)
    target_value = Column(Numeric(10, 2), nullable=False)
    achieved_percentage = Column(Numeric(5, 2), nullable=False)  # How well we met the target
    good_events_count = Column(Integer, nullable=False, default=0)
    total_events_count = Column(Integer, nullable=False, default=1)  # Avoid division by zero
    error_budget_consumed = Column(Numeric(5, 2), nullable=False, default=0.0)

    # Additional metadata
    measurement_metadata = Column(JSON, nullable=True)  # Additional context
    data_quality_score = Column(Numeric(5, 2), nullable=True)  # Confidence in measurement

    # Performance indexes
    __table_args__ = (
        Index('idx_measurement_slo_period', 'slo_definition_id', 'period_start', 'period_end'),
        Index('idx_measurement_timeline', 'period_start', 'period_end'),
        Index('idx_measurement_period_type', 'measurement_period', 'period_start'),
        CheckConstraint("achieved_percentage >= 0 AND achieved_percentage <= 100", name='check_achieved_percentage_range'),
        CheckConstraint("error_budget_consumed >= 0 AND error_budget_consumed <= 100", name='check_error_budget_consumed_range'),
        CheckConstraint("total_events_count > 0", name='check_total_events_positive'),
    )

    # Relationships
    slo_definition = relationship("SLODefinition", back_populates="measurements")

    def __repr__(self):
        return f"<SLIMeasurement(slo={self.slo_definition_id}, achieved={self.achieved_percentage}%>"


class SLOAlert(Base, UUIDMixin, TimestampMixin):
    """SLO alerts and notifications."""

    __tablename__ = "slo_alerts"

    # Alert identification
    slo_definition_id = Column(UUID(as_uuid=True), ForeignKey("slo_definitions.id"), nullable=False, index=True)
    measurement_id = Column(UUID(as_uuid=True), ForeignKey("sli_measurements.id"), nullable=True, index=True)

    # Alert details
    alert_type = Column(String(50), nullable=False, index=True)  # burn_rate, error_budget_exhausted, etc.
    severity = Column(Enum(AlertSeverity), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # Alert data
    current_value = Column(Numeric(10, 2), nullable=False)
    target_value = Column(Numeric(10, 2), nullable=False)
    threshold_breached_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Alert lifecycle
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Notification tracking
    notification_sent = Column(Boolean, nullable=False, default=False)
    notification_attempts = Column(Integer, nullable=False, default=0)
    last_notification_at = Column(DateTime(timezone=True), nullable=True)
    notification_metadata = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_alert_slo_severity', 'slo_definition_id', 'severity'),
        Index('idx_alert_type_created', 'alert_type', 'created_at'),
        Index('idx_alert_resolved', 'resolved_at', 'severity'),
        CheckConstraint("notification_attempts >= 0", name='check_notification_attempts_non_negative'),
    )

    # Relationships
    slo_definition = relationship("SLODefinition", back_populates="alerts")
    measurement = relationship("SLIMeasurement")

    def __repr__(self):
        return f"<SLOAlert(type={self.alert_type}, severity={self.severity}, resolved={self.resolved_at})>"


class InvoiceMetric(Base, UUIDMixin, TimestampMixin):
    """Raw invoice-level metrics for KPI calculation."""

    __tablename__ = "invoice_metrics"

    # Invoice identification
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    # Timing metrics
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    parsing_completed_at = Column(DateTime(timezone=True), nullable=True)
    validation_completed_at = Column(DateTime(timezone=True), nullable=True)
    ready_for_approval_at = Column(DateTime(timezone=True), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Processing duration metrics (in seconds)
    time_to_ready_seconds = Column(Float, nullable=True, index=True)
    approval_latency_seconds = Column(Float, nullable=True, index=True)
    total_processing_time_seconds = Column(Float, nullable=True)

    # Quality metrics
    extraction_confidence = Column(Float, nullable=True)
    validation_passed = Column(Boolean, nullable=True, index=True)
    exception_count = Column(Integer, nullable=False, default=0, index=True)
    duplicate_detected = Column(Boolean, nullable=False, default=False, index=True)
    requires_human_review = Column(Boolean, nullable=False, default=False, index=True)

    # Technical metrics
    processing_step_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    file_size_bytes = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Additional metadata
    workflow_id = Column(String(100), nullable=True, index=True)
    processing_metadata = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_metrics_invoice_timeline', 'invoice_id', 'received_at'),
        Index('idx_metrics_ready_time', 'ready_for_approval_at', 'time_to_ready_seconds'),
        Index('idx_metrics_approval_time', 'approved_at', 'approval_latency_seconds'),
        Index('idx_metrics_validation_status', 'validation_passed', 'exception_count'),
        Index('idx_metrics_duplicate_detection', 'duplicate_detected', 'received_at'),
        Index('idx_metrics_processing_efficiency', 'processing_step_count', 'total_processing_time_seconds'),
        CheckConstraint("time_to_ready_seconds >= 0", name='check_time_to_ready_non_negative'),
        CheckConstraint("approval_latency_seconds >= 0", name='check_approval_latency_non_negative'),
        CheckConstraint("total_processing_time_seconds >= 0", name='check_total_processing_time_non_negative'),
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1", name='check_confidence_range'),
        CheckConstraint("processing_step_count >= 0", name='check_step_count_non_negative'),
        CheckConstraint("retry_count >= 0", name='check_retry_count_non_negative'),
        CheckConstraint("file_size_bytes >= 0", name='check_file_size_non_negative'),
        CheckConstraint("page_count >= 0", name='check_page_count_non_negative'),
    )

    # Relationships
    invoice = relationship("Invoice", backref="metrics")

    def __repr__(self):
        return f"<InvoiceMetric(invoice={self.invoice_id}, time_to_ready={self.time_to_ready_seconds}s)>"


class SystemMetric(Base, UUIDMixin, TimestampMixin):
    """System-level operational metrics."""

    __tablename__ = "system_metrics"

    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_category = Column(String(50), nullable=False, index=True)  # performance, quality, volume

    # Measurement details
    measurement_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    value = Column(Numeric(15, 4), nullable=False)
    unit = Column(String(20), nullable=True)  # count, percentage, seconds, etc.

    # Additional context
    dimensions = Column(JSON, nullable=True)  # Key-value pairs for slicing/dicing
    tags = Column(JSON, nullable=True)  # Simple list of tags
    metric_metadata = Column(JSON, nullable=True)  # Additional context

    # Data quality
    data_source = Column(String(50), nullable=False)  # workflow, database, external
    confidence_score = Column(Numeric(5, 2), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_system_metric_name_time', 'metric_name', 'measurement_timestamp'),
        Index('idx_system_metric_category_time', 'metric_category', 'measurement_timestamp'),
        Index('idx_system_metric_source', 'data_source', 'measurement_timestamp'),
    )

    def __repr__(self):
        return f"<SystemMetric(name={self.metric_name}, value={self.value}, category={self.metric_category})>"


class MetricsConfiguration(Base, UUIDMixin, TimestampMixin):
    """Configuration for metrics collection and processing."""

    __tablename__ = "metrics_configuration"

    # Configuration identification
    config_key = Column(String(100), nullable=False, unique=True, index=True)
    config_category = Column(String(50), nullable=False, index=True)

    # Configuration data
    config_value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)

    # Configuration management
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(String(100), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_metrics_config_category_active', 'config_category', 'is_active'),
        CheckConstraint("version > 0", name='check_version_positive'),
    )

    def __repr__(self):
        return f"<MetricsConfiguration(key={self.config_key}, category={self.config_category}, active={self.is_active})>"


class WeeklyMetric(Base, UUIDMixin, TimestampMixin):
    """Weekly aggregated metrics for executive reporting and trend analysis."""

    __tablename__ = "weekly_metrics"

    # Week identification
    week_start_date = Column(SQLDate, nullable=False, unique=True, index=True)
    week_end_date = Column(SQLDate, nullable=False, index=True)

    # Processing volume metrics
    invoices_processed = Column(Integer, nullable=False, default=0)
    auto_processed = Column(Integer, nullable=False, default=0)
    manual_processed = Column(Integer, nullable=False, default=0)
    exceptions_created = Column(Integer, nullable=False, default=0)
    exceptions_resolved = Column(Integer, nullable=False, default=0)
    duplicates_detected = Column(Integer, nullable=False, default=0)

    # Performance timing metrics
    avg_processing_time_hours = Column(Numeric(10, 2), nullable=False)
    p50_time_to_ready_minutes = Column(Numeric(10, 2), nullable=True)
    p95_time_to_ready_minutes = Column(Numeric(10, 2), nullable=True)
    p99_time_to_ready_minutes = Column(Numeric(10, 2), nullable=True)
    exception_resolution_time_p50_hours = Column(Numeric(10, 2), nullable=True)
    api_response_time_p95_ms = Column(Numeric(10, 2), nullable=True)
    system_availability_percentage = Column(Numeric(5, 2), nullable=True)

    # Quality metrics
    auto_processing_rate = Column(Numeric(5, 2), nullable=False, default=0)
    pass_rate_structural = Column(Numeric(5, 2), nullable=False, default=0)
    pass_rate_math = Column(Numeric(5, 2), nullable=False, default=0)
    duplicate_recall_percentage = Column(Numeric(5, 2), nullable=True)

    # Financial metrics
    total_invoice_amount = Column(Numeric(15, 2), nullable=False, default=0)
    cost_per_invoice = Column(Numeric(10, 2), nullable=False, default=0)
    total_cost = Column(Numeric(15, 2), nullable=False, default=0)
    roi_percentage = Column(Numeric(5, 2), nullable=False, default=0)

    # Additional analysis data
    working_capital_optimization = Column(JSON, nullable=True)
    performance_summary = Column(Text, nullable=True)
    quality_metrics = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_weekly_metrics_week_start', 'week_start_date'),
        Index('idx_weekly_metrics_created_at', 'created_at'),
        Index('idx_weekly_metrics_auto_processing_rate', 'auto_processing_rate'),
        Index('idx_weekly_metrics_cost_per_invoice', 'cost_per_invoice'),
        CheckConstraint('invoices_processed >= 0', name='check_invoices_processed_non_negative'),
        CheckConstraint('auto_processed >= 0', name='check_auto_processed_non_negative'),
        CheckConstraint('manual_processed >= 0', name='check_manual_processed_non_negative'),
        CheckConstraint('exceptions_created >= 0', name='check_exceptions_created_non_negative'),
        CheckConstraint('exceptions_resolved >= 0', name='check_exceptions_resolved_non_negative'),
        CheckConstraint('duplicates_detected >= 0', name='check_duplicates_detected_non_negative'),
        CheckConstraint('avg_processing_time_hours >= 0', name='check_avg_processing_time_non_negative'),
        CheckConstraint('auto_processing_rate >= 0 AND auto_processing_rate <= 100', name='check_auto_processing_rate_range'),
        CheckConstraint('pass_rate_structural >= 0 AND pass_rate_structural <= 100', name='check_pass_rate_structural_range'),
        CheckConstraint('pass_rate_math >= 0 AND pass_rate_math <= 100', name='check_pass_rate_math_range'),
        CheckConstraint('cost_per_invoice >= 0', name='check_cost_per_invoice_non_negative'),
        CheckConstraint('total_cost >= 0', name='check_total_cost_non_negative'),
        CheckConstraint('roi_percentage >= 0', name='check_roi_percentage_non_negative'),
    )

    def __repr__(self):
        return f"<WeeklyMetric(week={self.week_start_date}, invoices={self.invoices_processed}, auto_rate={self.auto_processing_rate}%>)>"