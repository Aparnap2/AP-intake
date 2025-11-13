"""
Database models for weekly reporting system.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey,
    Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class ReportType(str, Enum):
    """Report type enumeration."""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    AD_HOC = "ad_hoc"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class DeliveryStatus(str, Enum):
    """Email delivery status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class SLOCategory(str, Enum):
    """SLO categories for reporting."""
    PROCESSING_TIME = "processing_time"
    ACCURACY = "accuracy"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    COST_EFFICIENCY = "cost_efficiency"
    CUSTOMER_SATISFACTION = "customer_satisfaction"


class WeeklyReport(Base, UUIDMixin, TimestampMixin):
    """Weekly report generation records."""

    __tablename__ = "weekly_reports"

    # Report metadata
    report_type = Column(SQLEnum(ReportType), default=ReportType.WEEKLY, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Time period
    week_start = Column(DateTime(timezone=True), nullable=False, index=True)
    week_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Generation status
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    generation_duration_seconds = Column(Integer, nullable=True)

    # Report content
    content_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    insights = Column(JSON, nullable=True)

    # File attachments
    pdf_file_path = Column(String(500), nullable=True)
    pdf_file_size = Column(Integer, nullable=True)
    html_content = Column(Text, nullable=True)

    # Metadata
    generated_by = Column(String(255), nullable=True)
    version = Column(String(50), nullable=False, default="1.0")
    tags = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_weekly_reports_week_start', 'week_start'),
        Index('idx_weekly_reports_status', 'status'),
        Index('idx_weekly_reports_type_status', 'report_type', 'status'),
        Index('idx_weekly_reports_generated_at', 'generated_at'),
        CheckConstraint("week_start < week_end", name='check_week_start_before_end'),
        CheckConstraint("title <> ''", name='check_report_title_not_empty'),
    )

    # Relationships
    deliveries = relationship("ReportDelivery", back_populates="report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WeeklyReport(id={self.id}, week_start={self.week_start}, status={self.status})>"


class ReportDelivery(Base, UUIDMixin, TimestampMixin):
    """Report delivery tracking."""

    __tablename__ = "report_deliveries"

    # Relationships
    report_id = Column(PostgresUUID(as_uuid=True), ForeignKey('weekly_reports.id'), nullable=False)

    # Delivery details
    recipient_email = Column(String(255), nullable=False)
    recipient_group = Column(String(100), nullable=False)  # executive, operations, finance, etc.
    delivery_method = Column(String(50), default="email", nullable=False)

    # Delivery status
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivery_attempts = Column(Integer, default=0, nullable=False)

    # Error tracking
    error_message = Column(Text, nullable=True)
    bounce_reason = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)

    # Engagement tracking
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    delivery_provider = Column(String(100), nullable=True)  # gmail, sendgrid, etc.
    external_id = Column(String(255), nullable=True)  # external message ID

    # Performance indexes
    __table_args__ = (
        Index('idx_report_deliveries_report_id', 'report_id'),
        Index('idx_report_deliveries_status', 'status'),
        Index('idx_report_deliveries_recipient', 'recipient_email'),
        Index('idx_report_deliveries_group', 'recipient_group'),
        Index('idx_report_deliveries_sent_at', 'sent_at'),
        CheckConstraint("recipient_email <> ''", name='check_recipient_email_not_empty'),
        CheckConstraint("recipient_group <> ''", name='check_recipient_group_not_empty'),
    )

    # Relationships
    report = relationship("WeeklyReport", back_populates="deliveries")

    def __repr__(self):
        return f"<ReportDelivery(id={self.id}, report_id={self.report_id}, status={self.status})>"


class SLOMetric(Base, UUIDMixin, TimestampMixin):
    """SLO metrics for weekly tracking."""

    __tablename__ = "slo_metrics"

    # Metric identification
    slo_name = Column(String(255), nullable=False, index=True)
    slo_category = Column(SQLEnum(SLOCategory), nullable=False, index=True)

    # Time period
    week_start = Column(DateTime(timezone=True), nullable=False, index=True)
    week_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # SLO values
    target_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    attainment_percentage = Column(Float, nullable=False)

    # Error budget calculations
    error_budget_target = Column(Float, nullable=False)
    error_budget_consumed = Column(Float, nullable=False)
    error_budget_remaining = Column(Float, nullable=False)
    error_budget_burn_rate = Column(Float, nullable=False)

    # Trend data
    previous_week_attainment = Column(Float, nullable=True)
    attainment_change = Column(Float, nullable=True)
    trend_direction = Column(String(20), nullable=True)  # improving, degrading, stable

    # Metadata
    data_source = Column(String(100), nullable=False, default="automated")
    confidence_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_slo_metrics_slo_name', 'slo_name'),
        Index('idx_slo_metrics_category', 'slo_category'),
        Index('idx_slo_metrics_week_start', 'week_start'),
        Index('idx_slo_metrics_attainment', 'attainment_percentage'),
        Index('idx_slo_metrics_category_week', 'slo_category', 'week_start'),
        CheckConstraint("target_value > 0", name='check_slo_target_positive'),
        CheckConstraint("actual_value >= 0", name='check_slo_actual_non_negative'),
        CheckConstraint("attainment_percentage >= 0 AND attainment_percentage <= 100", name='check_attainment_percentage_range'),
    )

    def __repr__(self):
        return f"<SLOMetric(id={self.id}, slo_name={self.slo_name}, attainment={self.attainment_percentage}%)"


class WeeklyCostAnalysis(Base, UUIDMixin, TimestampMixin):
    """Weekly cost analysis data."""

    __tablename__ = "weekly_cost_analysis"

    # Time period
    week_start = Column(DateTime(timezone=True), nullable=False, index=True)
    week_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Volume metrics
    total_invoices_processed = Column(Integer, nullable=False)
    auto_approved_count = Column(Integer, nullable=False)
    manual_review_count = Column(Integer, nullable=False)
    exception_count = Column(Integer, nullable=False)

    # Cost breakdowns
    total_processing_cost = Column(Float, nullable=False)
    cost_per_invoice = Column(Float, nullable=False)
    auto_approval_cost_per_invoice = Column(Float, nullable=False)
    manual_review_cost_per_invoice = Column(Float, nullable=False)
    exception_handling_cost_per_invoice = Column(Float, nullable=False)

    # Cost components
    llm_cost_total = Column(Float, nullable=False)
    api_cost_total = Column(Float, nullable=False)
    storage_cost_total = Column(Float, nullable=False)
    compute_cost_total = Column(Float, nullable=False)

    # Efficiency metrics
    cost_savings_vs_manual = Column(Float, nullable=False)
    cost_efficiency_score = Column(Float, nullable=False)  # 0-100 scale
    roi_percentage = Column(Float, nullable=False)

    # Trend analysis
    previous_week_cost_per_invoice = Column(Float, nullable=True)
    cost_change_percentage = Column(Float, nullable=True)
    cost_trend = Column(String(20), nullable=True)  # decreasing, increasing, stable

    # Predictions
    next_week_predicted_cost = Column(Float, nullable=True)
    next_week_volume_prediction = Column(Integer, nullable=True)

    # Metadata
    currency = Column(String(10), default="USD", nullable=False)
    data_quality_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_weekly_cost_analysis_week_start', 'week_start'),
        Index('idx_weekly_cost_analysis_cost_per_invoice', 'cost_per_invoice'),
        Index('idx_weekly_cost_analysis_efficiency_score', 'cost_efficiency_score'),
        CheckConstraint("total_invoices_processed >= 0", name='check_invoice_count_non_negative'),
        CheckConstraint("total_processing_cost >= 0", name='check_total_cost_non_negative'),
        CheckConstraint("cost_per_invoice >= 0", name='check_cost_per_invoice_non_negative'),
    )

    def __repr__(self):
        return f"<WeeklyCostAnalysis(id={self.id}, week_start={self.week_start}, cost_per_invoice=${self.cost_per_invoice})>"


class ExceptionAnalysis(Base, UUIDMixin, TimestampMixin):
    """Weekly exception analysis data."""

    __tablename__ = "exception_analysis"

    # Time period
    week_start = Column(DateTime(timezone=True), nullable=False, index=True)
    week_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Exception summary
    total_exceptions = Column(Integer, nullable=False)
    unique_exception_types = Column(Integer, nullable=False)
    resolved_exceptions = Column(Integer, nullable=False)
    pending_exceptions = Column(Integer, nullable=False)

    # Resolution metrics
    average_resolution_time_hours = Column(Float, nullable=True)
    median_resolution_time_hours = Column(Float, nullable=True)
    longest_resolution_time_hours = Column(Float, nullable=True)
    resolution_rate_percentage = Column(Float, nullable=False)

    # Top exception categories
    top_exception_types = Column(JSON, nullable=False)  # List of {type, count, percentage}
    top_resolvers = Column(JSON, nullable=False)  # List of {resolver, count, avg_time}

    # Exception impact analysis
    exceptions_by_severity = Column(JSON, nullable=False)  # {critical: count, high: count, etc.}
    exceptions_by_vendor = Column(JSON, nullable=False)  # {vendor_id: count, percentage}
    business_impact_score = Column(Float, nullable=False)  # 0-100 scale

    # Prevention insights
    repeat_exceptions = Column(Integer, nullable=False)  # Exceptions seen before
    new_exception_types = Column(Integer, nullable=False)  # First time exceptions
    prevention_opportunities = Column(JSON, nullable=False)  # Actionable prevention recommendations

    # Trend analysis
    previous_week_total = Column(Integer, nullable=True)
    exception_trend = Column(String(20), nullable=True)  # increasing, decreasing, stable
    resolution_trend = Column(String(20), nullable=True)  # improving, degrading, stable

    # Metadata
    analysis_version = Column(String(50), default="1.0", nullable=False)
    confidence_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_exception_analysis_week_start', 'week_start'),
        Index('idx_exception_analysis_total_exceptions', 'total_exceptions'),
        Index('idx_exception_analysis_resolution_rate', 'resolution_rate_percentage'),
        CheckConstraint("total_exceptions >= 0", name='check_total_exceptions_non_negative'),
        CheckConstraint("resolved_exceptions >= 0 AND resolved_exceptions <= total_exceptions", name='check_resolved_exceptions_valid'),
        CheckConstraint("resolution_rate_percentage >= 0 AND resolution_rate_percentage <= 100", name='check_resolution_rate_range'),
    )

    def __repr__(self):
        return f"<ExceptionAnalysis(id={self.id}, week_start={self.week_start}, total_exceptions={self.total_exceptions})>"


class ProcessingMetric(Base, UUIDMixin, TimestampMixin):
    """Weekly processing performance metrics."""

    __tablename__ = "processing_metrics"

    # Time period
    week_start = Column(DateTime(timezone=True), nullable=False, index=True)
    week_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Volume metrics
    total_invoices = Column(Integer, nullable=False)
    processed_invoices = Column(Integer, nullable=False)
    failed_invoices = Column(Integer, nullable=False)

    # Timing metrics
    average_processing_time_seconds = Column(Float, nullable=False)
    median_processing_time_seconds = Column(Float, nullable=False)
    p95_processing_time_seconds = Column(Float, nullable=False)
    p99_processing_time_seconds = Column(Float, nullable=False)

    # Time-to-ready metrics (received to ready for export)
    average_time_to_ready_minutes = Column(Float, nullable=False)
    median_time_to_ready_minutes = Column(Float, nullable=False)
    time_to_ready_target_minutes = Column(Float, nullable=False)
    time_to_ready_attainment_percentage = Column(Float, nullable=False)

    # Approval latency metrics
    average_approval_latency_minutes = Column(Float, nullable=False)
    median_approval_latency_minutes = Column(Float, nullable=False)
    approval_latency_target_minutes = Column(Float, nullable=False)
    approval_latency_attainment_percentage = Column(Float, nullable=False)

    # Quality metrics
    extraction_accuracy_percentage = Column(Float, nullable=False)
    validation_pass_rate_percentage = Column(Float, nullable=False)
    auto_approval_rate_percentage = Column(Float, nullable=False)
    human_review_required_percentage = Column(Float, nullable=False)

    # Performance by vendor/size
    performance_by_vendor = Column(JSON, nullable=True)
    performance_by_file_size = Column(JSON, nullable=True)
    performance_by_page_count = Column(JSON, nullable=True)

    # Trend analysis
    processing_trend = Column(String(20), nullable=True)  # improving, degrading, stable
    quality_trend = Column(String(20), nullable=True)  # improving, degrading, stable

    # Metadata
    metric_version = Column(String(50), default="1.0", nullable=False)
    data_completeness_percentage = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_processing_metrics_week_start', 'week_start'),
        Index('idx_processing_metrics_total_invoices', 'total_invoices'),
        Index('idx_processing_metrics_avg_processing_time', 'average_processing_time_seconds'),
        CheckConstraint("total_invoices >= 0", name='check_total_invoices_non_negative'),
        CheckConstraint("processed_invoices >= 0 AND processed_invoices <= total_invoices", name='check_processed_invoices_valid'),
        CheckConstraint("extraction_accuracy_percentage >= 0 AND extraction_accuracy_percentage <= 100", name='check_accuracy_percentage_range'),
    )

    def __repr__(self):
        return f"<ProcessingMetric(id={self.id}, week_start={self.week_start}, total_invoices={self.total_invoices})>"


class ReportSubscription(Base, UUIDMixin, TimestampMixin):
    """User subscriptions to weekly reports."""

    __tablename__ = "report_subscriptions"

    # User identification
    user_id = Column(PostgresUUID(as_uuid=True), nullable=False, index=True)
    user_email = Column(String(255), nullable=False, index=True)

    # Subscription preferences
    report_type = Column(SQLEnum(ReportType), default=ReportType.WEEKLY, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Delivery preferences
    delivery_methods = Column(JSON, nullable=False)  # ["email", "slack", "teams"]
    recipient_groups = Column(JSON, nullable=False)  # ["executive", "operations", "finance"]

    # Content preferences
    include_pdf_attachment = Column(Boolean, default=True, nullable=False)
    include_raw_data = Column(Boolean, default=False, nullable=False)
    custom_sections = Column(JSON, nullable=True)  # Additional sections to include

    # Scheduling preferences
    preferred_day_of_week = Column(Integer, default=1, nullable=False)  # 1=Monday, 7=Sunday
    preferred_time = Column(String(10), default="09:00", nullable=False)  # HH:MM format
    timezone = Column(String(50), default="UTC", nullable=False)

    # Last delivery tracking
    last_delivered_at = Column(DateTime(timezone=True), nullable=True)
    delivery_count = Column(Integer, default=0, nullable=False)
    failed_delivery_count = Column(Integer, default=0, nullable=False)

    # Metadata
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)
    unsubscribe_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_report_subscriptions_user_id', 'user_id'),
        Index('idx_report_subscriptions_email', 'user_email'),
        Index('idx_report_subscriptions_active', 'is_active'),
        Index('idx_report_subscriptions_report_type', 'report_type'),
        CheckConstraint("user_email <> ''", name='check_user_email_not_empty'),
        CheckConstraint("preferred_day_of_week >= 1 AND preferred_day_of_week <= 7", name='check_day_of_week_range'),
    )

    def __repr__(self):
        return f"<ReportSubscription(id={self.id}, user_email={self.user_email}, active={self.is_active})>"


class ReportTemplate(Base, UUIDMixin, TimestampMixin):
    """Custom report templates."""

    __tablename__ = "report_templates"

    # Template identification
    name = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template configuration
    template_type = Column(SQLEnum(ReportType), nullable=False)
    layout_json = Column(JSON, nullable=False)  # Template layout structure
    sections_json = Column(JSON, nullable=False)  # Section configurations
    styling_json = Column(JSON, nullable=True)  # Custom styling

    # Content configuration
    included_metrics = Column(JSON, nullable=False)  # List of metric types to include
    time_ranges = Column(JSON, nullable=False)  # Time range configurations
    filters = Column(JSON, nullable=True)  # Data filters

    # Template metadata
    version = Column(String(50), default="1.0", nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Ownership
    created_by = Column(String(255), nullable=False)
    owner_team = Column(String(100), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_report_templates_type', 'template_type'),
        Index('idx_report_templates_active', 'is_active'),
        Index('idx_report_templates_default', 'is_default'),
        CheckConstraint("name <> ''", name='check_template_name_not_empty'),
        CheckConstraint("title <> ''", name='check_template_title_not_empty'),
    )

    def __repr__(self):
        return f"<ReportTemplate(id={self.id}, name={self.name}, type={self.template_type})>"