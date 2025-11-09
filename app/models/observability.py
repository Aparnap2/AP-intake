"""
Database models for observability data including metrics, traces, and alerts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey,
    Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TraceSpan(Base):
    """Trace span data for distributed tracing."""
    __tablename__ = "trace_spans"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    trace_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(16), nullable=False)
    parent_span_id = Column(String(16), nullable=True)
    operation_name = Column(String(255), nullable=False)
    component = Column(String(100), nullable=False)
    service_name = Column(String(100), nullable=False)

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Status
    status_code = Column(String(20), nullable=False, default="ok")
    status_message = Column(Text, nullable=True)

    # Attributes and tags
    tags = Column(JSON, nullable=True)
    attributes = Column(JSON, nullable=True)
    resource_attributes = Column(JSON, nullable=True)

    # Events
    events = Column(JSON, nullable=True)
    links = Column(JSON, nullable=True)

    # Cost tracking
    operation_cost = Column(Float, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    llm_cost = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_trace_spans_trace_id', 'trace_id'),
        Index('idx_trace_spans_component', 'component'),
        Index('idx_trace_spans_operation_name', 'operation_name'),
        Index('idx_trace_spans_start_time', 'start_time'),
        Index('idx_trace_spans_duration_ms', 'duration_ms'),
        Index('idx_trace_spans_service_name', 'service_name'),
        UniqueConstraint('trace_id', 'span_id', name='uq_trace_span'),
    )


class AlertRule(Base):
    """Alert rule definitions."""
    __tablename__ = "alert_rules"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Rule configuration
    severity = Column(String(20), nullable=False)  # info, warning, error, critical
    condition = Column(Text, nullable=False)
    threshold = Column(Float, nullable=False)
    operator = Column(String(10), nullable=False)  # >, <, >=, <=, ==, !=

    # Evaluation settings
    evaluation_window_seconds = Column(Integer, default=300)
    consecutive_breaches = Column(Integer, default=1)
    cooldown_period_seconds = Column(Integer, default=300)

    # Notification settings
    notification_channels = Column(JSON, nullable=True)  # List of channels
    escalation_policy_id = Column(String(100), nullable=True)

    # State
    enabled = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Alert(Base):
    """Alert instances."""
    __tablename__ = "alerts"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(PostgresUUID(as_uuid=True), ForeignKey('alert_rules.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Alert state
    severity = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active, acknowledged, resolved, suppressed, escalated

    # Evaluation data
    current_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=False)

    # Resolution data
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(255), nullable=True)
    resolution_note = Column(Text, nullable=True)

    # Acknowledgment data
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    acknowledgment_note = Column(Text, nullable=True)

    # Escalation data
    escalation_level = Column(Integer, default=0)
    escalated_at = Column(DateTime(timezone=True), nullable=True)

    # Notification tracking
    last_notification_at = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0)

    # Context and metadata
    context = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    rule = relationship("AlertRule", backref="alerts")

    # Indexes
    __table_args__ = (
        Index('idx_alerts_rule_id', 'rule_id'),
        Index('idx_alerts_severity', 'severity'),
        Index('idx_alerts_status', 'status'),
        Index('idx_alerts_evaluated_at', 'evaluated_at'),
        Index('idx_alerts_created_at', 'created_at'),
    )


class RunbookExecution(Base):
    """Runbook execution records."""
    __tablename__ = "runbook_executions"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    runbook_id = Column(String(100), nullable=False)
    runbook_name = Column(String(255), nullable=False)

    # Execution state
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled, paused
    current_step = Column(String(100), nullable=True)

    # Progress tracking
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Execution context
    trigger_context = Column(JSON, nullable=True)
    execution_context = Column(JSON, nullable=True)
    step_results = Column(JSON, nullable=True)

    # Approval and authorization
    requires_approval = Column(Boolean, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(255), nullable=True)
    approval_note = Column(Text, nullable=True)

    # Metadata
    triggered_by = Column(String(255), nullable=True)
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_runbook_executions_runbook_id', 'runbook_id'),
        Index('idx_runbook_executions_status', 'status'),
        Index('idx_runbook_executions_started_at', 'started_at'),
        Index('idx_runbook_executions_triggered_by', 'triggered_by'),
    )


class RunbookStepExecution(Base):
    """Individual runbook step execution records."""
    __tablename__ = "runbook_step_executions"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_id = Column(PostgresUUID(as_uuid=True), ForeignKey('runbook_executions.id'), nullable=False)
    step_id = Column(String(100), nullable=False)
    step_name = Column(String(255), nullable=False)

    # Execution state
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, skipped
    action_type = Column(String(50), nullable=False)  # command, api_call, script, manual

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Execution details
    command = Column(Text, nullable=True)
    api_endpoint = Column(String(500), nullable=True)
    script_path = Column(String(500), nullable=True)

    # Results
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Retry tracking
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=0)

    # Dependencies
    dependencies = Column(JSON, nullable=True)  # List of step IDs
    parallel = Column(Boolean, default=False)

    # Metadata
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    execution = relationship("RunbookExecution", backref="step_executions")

    # Indexes
    __table_args__ = (
        Index('idx_runbook_step_executions_execution_id', 'execution_id'),
        Index('idx_runbook_step_executions_step_id', 'step_id'),
        Index('idx_runbook_step_executions_status', 'status'),
        Index('idx_runbook_step_executions_started_at', 'started_at'),
    )


class SystemHealthCheck(Base):
    """System health check records."""
    __tablename__ = "system_health_checks"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    check_name = Column(String(255), nullable=False)
    component = Column(String(100), nullable=False)

    # Check results
    status = Column(String(20), nullable=False)  # healthy, degraded, unhealthy, unknown
    response_time_ms = Column(Integer, nullable=True)

    # Check details
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)

    # Thresholds
    warning_threshold_ms = Column(Integer, nullable=True)
    critical_threshold_ms = Column(Integer, nullable=True)

    # Metadata
    check_type = Column(String(50), nullable=False)  # http, tcp, database, custom
    endpoint_url = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)

    # Timestamps
    checked_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_system_health_checks_component', 'component'),
        Index('idx_system_health_checks_status', 'status'),
        Index('idx_system_health_checks_checked_at', 'checked_at'),
        Index('idx_system_health_checks_check_name', 'check_name'),
    )


class PerformanceMetric(Base):
    """Performance metrics data."""
    __tablename__ = "performance_metrics"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    metric_name = Column(String(255), nullable=False)
    metric_category = Column(String(100), nullable=False)

    # Value and unit
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)

    # Dimensions for aggregation
    dimensions = Column(JSON, nullable=True)  # e.g., {"endpoint": "/api/v1/invoices", "method": "POST"}
    tags = Column(JSON, nullable=True)

    # Measurement timestamp
    measurement_timestamp = Column(DateTime(timezone=True), nullable=False)

    # Data source and quality
    data_source = Column(String(100), nullable=False, default="manual")
    confidence_score = Column(Float, nullable=True)

    # Additional metadata
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_performance_metrics_metric_name', 'metric_name'),
        Index('idx_performance_metrics_category', 'metric_category'),
        Index('idx_performance_metrics_timestamp', 'measurement_timestamp'),
        Index('idx_performance_metrics_data_source', 'data_source'),
    )


class AnomalyDetection(Base):
    """Anomaly detection results."""
    __tablename__ = "anomaly_detection"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    metric_name = Column(String(255), nullable=False)

    # Anomaly details
    anomaly_type = Column(String(50), nullable=False)  # spike, drop, trend, pattern
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    confidence_score = Column(Float, nullable=False)  # 0.0 to 1.0

    # Detection data
    expected_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    deviation_percentage = Column(Float, nullable=False)

    # Time window
    detected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)

    # Detection method
    detection_method = Column(String(100), nullable=False)  # statistical, ml, threshold
    model_version = Column(String(50), nullable=True)

    # Context and impact
    context = Column(JSON, nullable=True)
    impact_assessment = Column(JSON, nullable=True)
    recommended_actions = Column(JSON, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="active")  # active, acknowledged, resolved, false_positive
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_anomaly_detection_metric_name', 'metric_name'),
        Index('idx_anomaly_detection_severity', 'severity'),
        Index('idx_anomaly_detection_detected_at', 'detected_at'),
        Index('idx_anomaly_detection_status', 'status'),
    )


class AlertSuppression(Base):
    """Alert suppression rules."""
    __tablename__ = "alert_suppressions"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(String(100), nullable=False)

    # Suppression details
    reason = Column(Text, nullable=False)
    suppressed_by = Column(String(255), nullable=False)

    # Timing
    suppressed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    duration_minutes = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Scope
    scope = Column(JSON, nullable=True)  # Additional filter criteria

    # Status
    active = Column(Boolean, default=True)

    # Metadata
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_alert_suppressions_rule_id', 'rule_id'),
        Index('idx_alert_suppressions_expires_at', 'expires_at'),
        Index('idx_alert_suppressions_active', 'active'),
    )


class DashboardConfiguration(Base):
    """Custom dashboard configurations."""
    __tablename__ = "dashboard_configurations"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Dashboard layout and configuration
    layout = Column(JSON, nullable=False)  # Grid layout configuration
    widgets = Column(JSON, nullable=False)  # Widget definitions

    # Data sources and refresh settings
    refresh_interval_seconds = Column(Integer, default=60)
    time_range_hours = Column(Integer, default=24)

    # Access control
    owner = Column(String(255), nullable=False)
    viewers = Column(JSON, nullable=True)  # List of users/roles
    is_public = Column(Boolean, default=False)

    # Status
    active = Column(Boolean, default=True)

    # Metadata
    tags = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_dashboard_configurations_owner', 'owner'),
        Index('idx_dashboard_configurations_active', 'active'),
        Index('idx_dashboard_configurations_is_public', 'is_public'),
    )