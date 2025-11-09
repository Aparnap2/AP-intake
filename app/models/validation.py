"""
Enhanced validation models with reason taxonomy and rule versioning.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class ValidationRule(Base):
    """Validation rule with versioning and configuration."""
    __tablename__ = "validation_rules"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # ERROR, WARNING, INFO
    enabled = Column(Boolean, default=True)
    version = Column(String(20), nullable=False)

    # Rule configuration
    parameters = Column(JSON, nullable=True)
    condition = Column(Text, nullable=True)  # Condition expression

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    # Usage statistics
    execution_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_executed = Column(DateTime, nullable=True)


class ValidationRuleExecution(Base):
    """Track execution of validation rules."""
    __tablename__ = "validation_rule_executions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(PG_UUID(as_uuid=True), ForeignKey("validation_rules.id"), nullable=False)
    invoice_id = Column(PG_UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Execution details
    executed_at = Column(DateTime, default=datetime.utcnow)
    execution_time_ms = Column(Integer, nullable=False)
    passed = Column(Boolean, nullable=False)

    # Results
    reason_taxonomy = Column(String(50), nullable=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)

    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)


class ValidationSession(Base):
    """Complete validation session for an invoice."""
    __tablename__ = "validation_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(PG_UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Session metadata
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # Configuration
    rules_version = Column(String(20), nullable=False)
    validator_version = Column(String(20), nullable=False)
    strict_mode = Column(Boolean, default=False)
    custom_rules = Column(JSON, nullable=True)

    # Results summary
    total_rules_executed = Column(Integer, default=0)
    rules_passed = Column(Integer, default=0)
    rules_failed = Column(Integer, default=0)
    overall_passed = Column(Boolean, nullable=False)
    confidence_score = Column(Float, nullable=True)

    # Issue breakdown
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    info_count = Column(Integer, default=0)

    # Categorized results
    structural_passed = Column(Boolean, default=True)
    mathematical_passed = Column(Boolean, default=True)
    business_rules_passed = Column(Boolean, default=True)

    # Processing metadata
    extraction_confidence = Column(Float, nullable=True)
    enhancement_applied = Column(Boolean, default=False)

    # Relationships
    rule_executions = relationship("ValidationRuleExecution", backref="validation_session")


class ValidationIssue(Base):
    """Detailed validation issue with reason taxonomy."""
    __tablename__ = "validation_issues"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("validation_sessions.id"), nullable=False)
    rule_id = Column(PG_UUID(as_uuid=True), ForeignKey("validation_rules.id"), nullable=True)

    # Issue classification
    reason_taxonomy = Column(String(50), nullable=False)
    validation_code = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)

    # Issue details
    message = Column(Text, nullable=False)
    field_name = Column(String(100), nullable=True)
    line_number = Column(Integer, nullable=True)
    expected_value = Column(Text, nullable=True)
    actual_value = Column(Text, nullable=True)

    # Extended information
    details = Column(JSON, nullable=True)
    suggested_actions = Column(JSON, nullable=True)  # List of suggested actions
    related_documentation = Column(JSON, nullable=True)  # Links to documentation

    # Resolution tracking
    auto_resolvable = Column(Boolean, default=False)
    resolution_status = Column(String(20), default="open")  # open, resolved, ignored
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)

    # Impact assessment
    business_impact = Column(String(20), default="medium")  # low, medium, high, critical
    processing_blocker = Column(Boolean, default=False)
    requires_human_review = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RuleVersion(Base):
    """Versioning for validation rules."""
    __tablename__ = "rule_versions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)

    # Rule definition at this version
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    parameters = Column(JSON, nullable=True)
    condition = Column(Text, nullable=True)

    # Version metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    change_log = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # Compatibility
    backwards_compatible = Column(Boolean, default=True)
    migration_notes = Column(Text, nullable=True)


class ValidationMetrics(Base):
    """Aggregated validation metrics."""
    __tablename__ = "validation_metrics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # hourly, daily, weekly, monthly

    # Volume metrics
    total_invoices = Column(Integer, default=0)
    passed_invoices = Column(Integer, default=0)
    failed_invoices = Column(Integer, default=0)
    auto_approved = Column(Integer, default=0)
    human_review_required = Column(Integer, default=0)

    # Quality metrics
    average_confidence = Column(Float, default=0.0)
    average_processing_time_ms = Column(Float, default=0.0)
    average_rules_executed = Column(Float, default=0.0)

    # Issue breakdown
    total_issues = Column(Integer, default=0)
    error_issues = Column(Integer, default=0)
    warning_issues = Column(Integer, default=0)
    info_issues = Column(Integer, default=0)

    # Category performance
    structural_pass_rate = Column(Float, default=0.0)
    mathematical_pass_rate = Column(Float, default=0.0)
    business_rules_pass_rate = Column(Float, default=0.0)

    # Top issues
    top_reason_taxonomies = Column(JSON, nullable=True)  # List of most common reasons
    top_failed_rules = Column(JSON, nullable=True)  # List of most failed rules

    # Performance metrics
    average_execution_time_ms = Column(Float, default=0.0)
    peak_execution_time_ms = Column(Float, default=0.0)

    # Enhancement metrics
    llm_patch_usage_rate = Column(Float, default=0.0)
    bbox_detection_rate = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic models for API
class ValidationRuleModel(BaseModel):
    """Pydantic model for validation rule."""
    name: str
    category: str
    description: str
    severity: str
    enabled: bool = True
    version: str = "1.0.0"
    parameters: Dict[str, Any] = {}
    condition: Optional[str] = None

    class Config:
        from_attributes = True


class ValidationIssueModel(BaseModel):
    """Pydantic model for validation issue."""
    reason_taxonomy: str
    validation_code: str
    severity: str
    category: str
    message: str
    field_name: Optional[str] = None
    line_number: Optional[int] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    details: Dict[str, Any] = {}
    suggested_actions: List[str] = []
    business_impact: str = "medium"
    auto_resolvable: bool = False
    requires_human_review: bool = True

    class Config:
        from_attributes = True


class ValidationSessionModel(BaseModel):
    """Pydantic model for validation session."""
    session_id: str
    invoice_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    rules_version: str
    validator_version: str
    strict_mode: bool = False
    total_rules_executed: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    overall_passed: bool
    confidence_score: Optional[float] = None
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    structural_passed: bool = True
    mathematical_passed: bool = True
    business_rules_passed: bool = True

    class Config:
        from_attributes = True


class ValidationSummaryModel(BaseModel):
    """Summary model for validation results."""
    period_start: datetime
    period_end: datetime

    # Volume metrics
    total_invoices: int
    passed_invoices: int
    failed_invoices: int
    auto_approved: int
    human_review_required: int

    # Quality metrics
    average_confidence: float
    average_processing_time_ms: float
    pass_rate: float

    # Issue analysis
    top_issues: List[Dict[str, Any]]
    issue_categories: Dict[str, int]
    reason_taxonomy_distribution: Dict[str, int]

    # Performance metrics
    rule_performance: Dict[str, Dict[str, float]]
    enhancement_effectiveness: Dict[str, float]

    class Config:
        from_attributes = True


class RulePerformanceModel(BaseModel):
    """Model for individual rule performance."""
    rule_name: str
    category: str
    execution_count: int
    success_count: int
    failure_count: int
    pass_rate: float
    average_execution_time_ms: float
    last_failure: Optional[datetime] = None
    common_failure_reasons: List[str] = []
    performance_trend: str  # improving, stable, degrading

    class Config:
        from_attributes = True


class ValidationRecommendationModel(BaseModel):
    """Model for validation recommendations."""
    invoice_id: str
    session_id: str

    # Primary recommendation
    recommendation_type: str  # approve, reject, review, patch
    confidence: float
    reasoning: str

    # Actionable items
    suggested_actions: List[str]
    auto_fixable_issues: List[str]
    manual_review_issues: List[str]

    # Processing guidance
    processing_priority: str  # low, medium, high, urgent
    estimated_review_time_minutes: int
    required_skills: List[str]  # skills needed for review

    # Cost impact
    potential_cost_impact: Optional[float] = None
    processing_cost_estimate: float = 0.0

    class Config:
        from_attributes = True


class ValidationTrendModel(BaseModel):
    """Model for validation trends over time."""
    period: str  # daily, weekly, monthly
    data_points: List[Dict[str, Any]]

    # Trend metrics
    volume_trend: str  # increasing, stable, decreasing
    quality_trend: str  # improving, stable, degrading
    efficiency_trend: str  # improving, stable, degrading

    # Key insights
    insights: List[str]
    recommendations: List[str]

    # Forecasting
    predicted_volume_next_period: Optional[int] = None
    predicted_quality_score: Optional[float] = None

    class Config:
        from_attributes = True