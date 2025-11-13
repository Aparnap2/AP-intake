"""
Exception Management API schemas and data models.

This module provides comprehensive schemas for exception management,
including classification, resolution workflows, notifications, and metrics.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ExceptionSeverity(str, Enum):
    """Exception severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ExceptionStatus(str, Enum):
    """Exception status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ExceptionCategory(str, Enum):
    """Exception categories for classification."""
    MATH = "math"
    DUPLICATE = "duplicate"
    MATCHING = "matching"
    VENDOR_POLICY = "vendor_policy"
    DATA_QUALITY = "data_quality"
    SYSTEM = "system"


class ExceptionAction(str, Enum):
    """Available exception resolution actions."""
    AUTO_APPROVE = "auto_approve"
    MANUAL_ADJUST = "manual_adjust"
    RECALCULATE = "recalculate"
    DATA_CORRECTION = "data_correction"
    UPDATE_PO = "update_po"
    ACCEPT_VARIANCE = "accept_variance"
    MANUAL_REVIEW = "manual_review"
    REJECT_DUPLICATE = "reject_duplicate"
    ESCALATE = "escalate"
    MANUAL_APPROVAL = "manual_approval"
    SYSTEM_RETRY = "system_retry"


class ExceptionReasonCode(str, Enum):
    """Standardized exception reason codes."""

    # Math exceptions
    SUBTOTAL_MISMATCH = "SUBTOTAL_MISMATCH"
    TOTAL_MISMATCH = "TOTAL_MISMATCH"
    LINE_MATH_MISMATCH = "LINE_MATH_MISMATCH"
    INVALID_AMOUNT = "INVALID_AMOUNT"

    # Duplicate exceptions
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"

    # Matching exceptions
    PO_NOT_FOUND = "PO_NOT_FOUND"
    PO_MISMATCH = "PO_MISMATCH"
    PO_AMOUNT_MISMATCH = "PO_AMOUNT_MISMATCH"
    PO_QUANTITY_MISMATCH = "PO_QUANTITY_MISMATCH"
    GRN_NOT_FOUND = "GRN_NOT_FOUND"
    GRN_MISMATCH = "GRN_MISMATCH"
    GRN_QUANTITY_MISMATCH = "GRN_QUANTITY_MISMATCH"

    # Vendor policy exceptions
    INACTIVE_VENDOR = "INACTIVE_VENDOR"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    INVALID_TAX_ID = "INVALID_TAX_ID"
    SPEND_LIMIT_EXCEEDED = "SPEND_LIMIT_EXCEEDED"
    PAYMENT_TERMS_VIOLATION = "PAYMENT_TERMS_VIOLATION"

    # Data quality exceptions
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_FORMAT = "INVALID_FIELD_FORMAT"
    INVALID_DATA_STRUCTURE = "INVALID_DATA_STRUCTURE"
    NO_LINE_ITEMS = "NO_LINE_ITEMS"

    # System exceptions
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


class ExceptionCreate(BaseModel):
    """Exception creation data."""
    reason_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    auto_resolution_possible: bool = False
    suggested_actions: List[ExceptionAction] = Field(default_factory=list)


class ExceptionUpdate(BaseModel):
    """Exception update data."""
    status: Optional[ExceptionStatus] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    auto_resolution_possible: Optional[bool] = None
    suggested_actions: Optional[List[ExceptionAction]] = None


class ExceptionResolutionRequest(BaseModel):
    """Exception resolution request."""
    action: ExceptionAction
    resolved_by: str
    notes: Optional[str] = None
    resolution_data: Optional[Dict[str, Any]] = None
    auto_approve_invoice: bool = False


class ExceptionBatchUpdate(BaseModel):
    """Batch exception update request."""
    exception_ids: List[str]
    action: ExceptionAction
    resolved_by: str
    notes: Optional[str] = None
    resolution_data: Optional[Dict[str, Any]] = None
    auto_approve_invoices: bool = False


class ExceptionResponse(BaseModel):
    """Exception response model."""
    id: str
    invoice_id: str
    reason_code: str
    category: ExceptionCategory
    severity: ExceptionSeverity
    status: ExceptionStatus
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    auto_resolution_possible: bool = False
    suggested_actions: List[ExceptionAction] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None


class ExceptionListResponse(BaseModel):
    """Exception list response with pagination."""
    exceptions: List[ExceptionResponse]
    total: int
    limit: int
    offset: int


class ExceptionMetrics(BaseModel):
    """Exception metrics for reporting."""
    total_exceptions: int
    resolved_exceptions: int
    open_exceptions: int
    resolution_rate: float  # Percentage
    avg_resolution_hours: float
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
    top_reason_codes: Dict[str, int]
    period_days: int
    generated_at: datetime


class ExceptionNotification(BaseModel):
    """Exception notification data."""
    exception_id: str
    invoice_id: str
    severity: ExceptionSeverity
    message: str
    category: ExceptionCategory
    reason_code: str
    created_at: datetime
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None


class ExceptionFilter(BaseModel):
    """Exception filtering parameters."""
    invoice_id: Optional[str] = None
    status: Optional[ExceptionStatus] = None
    severity: Optional[ExceptionSeverity] = None
    category: Optional[ExceptionCategory] = None
    reason_code: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    resolved_after: Optional[datetime] = None
    resolved_before: Optional[datetime] = None
    resolved_by: Optional[str] = None
    auto_resolution_possible: Optional[bool] = None


class ExceptionSummary(BaseModel):
    """Exception summary for dashboard."""
    total_exceptions: int
    new_exceptions_today: int
    critical_exceptions: int
    awaiting_review: int
    avg_resolution_time_hours: float
    resolution_trend: str  # "improving", "stable", "declining"
    top_exception_types: List[Dict[str, Any]]
    recent_exceptions: List[ExceptionResponse]


class ExceptionAuditLog(BaseModel):
    """Exception audit log entry."""
    exception_id: str
    action: str
    performed_by: str
    timestamp: datetime
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ExceptionWorkflow(BaseModel):
    """Exception workflow configuration."""
    category: ExceptionCategory
    auto_resolution_enabled: bool
    escalation_rules: List[Dict[str, Any]]
    approval_requirements: Dict[str, Any]
    notification_settings: Dict[str, Any]


class ExceptionResolutionTemplate(BaseModel):
    """Template for common exception resolutions."""
    reason_code: str
    template_name: str
    action: ExceptionAction
    resolution_data_template: Dict[str, Any]
    approval_required: bool = False
    auto_approve_conditions: List[Dict[str, Any]] = Field(default_factory=list)


class ExceptionTrend(BaseModel):
    """Exception trend data."""
    period_start: datetime
    period_end: datetime
    total_exceptions: int
    resolved_exceptions: int
    new_exceptions: int
    avg_resolution_time_hours: float
    by_category: Dict[str, int]
    by_severity: Dict[str, int]


class ExceptionDashboard(BaseModel):
    """Complete exception dashboard data."""
    summary: ExceptionSummary
    metrics: ExceptionMetrics
    trends: List[ExceptionTrend]
    recent_exceptions: List[ExceptionResponse]
    pending_escalations: List[ExceptionResponse]
    auto_resolution_candidates: List[ExceptionResponse]


class ExceptionExport(BaseModel):
    """Exception data export format."""
    exception_id: str
    invoice_id: str
    invoice_number: str
    vendor_name: str
    reason_code: str
    category: str
    severity: str
    status: str
    message: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_time_hours: Optional[float] = None
    auto_resolved: bool = False


class ExceptionStatistics(BaseModel):
    """Detailed exception statistics."""
    period_days: int
    total_exceptions: int
    exceptions_by_day: List[Dict[str, Any]]
    exceptions_by_hour: List[Dict[str, Any]]
    resolution_time_distribution: Dict[str, int]
    exception_age_distribution: Dict[str, int]
    resolver_performance: List[Dict[str, Any]]
    vendor_exception_rates: List[Dict[str, Any]]


class ExceptionAlert(BaseModel):
    """Exception alert configuration."""
    alert_type: str
    conditions: Dict[str, Any]
    recipients: List[str]
    enabled: bool = True
    last_triggered: Optional[datetime] = None


class ExceptionSearch(BaseModel):
    """Exception search parameters."""
    query: Optional[str] = None
    filters: ExceptionFilter = Field(default_factory=ExceptionFilter)
    sort_by: str = "created_at"
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0


class ExceptionSearchResponse(BaseModel):
    """Exception search response."""
    results: List[ExceptionResponse]
    total: int
    query: str
    filters: ExceptionFilter
    sort_by: str
    sort_order: str
    limit: int
    offset: int


# Request/Response models for API endpoints

class ExceptionListRequest(BaseModel):
    """Request for listing exceptions."""
    filter: Optional[ExceptionFilter] = None
    search: Optional[ExceptionSearch] = None
    include_details: bool = False


class ExceptionResolutionResponse(BaseModel):
    """Response for exception resolution."""
    success: bool
    exception: ExceptionResponse
    message: str
    invoice_auto_approved: bool = False


class ExceptionBatchResolutionResponse(BaseModel):
    """Response for batch exception resolution."""
    success_count: int
    error_count: int
    resolved_exceptions: List[ExceptionResponse]
    errors: List[Dict[str, Any]]
    invoices_auto_approved: List[str]


class ExceptionMetricsRequest(BaseModel):
    """Request for exception metrics."""
    period_days: int = 30
    include_trends: bool = False
    include_details: bool = False
    group_by: Optional[str] = None  # "category", "severity", "reason_code", "day"


# CFO Grade Enums and Classes

class CFOGrade(str, Enum):
    """CFO grade levels for executive prioritization."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BusinessPriority(str, Enum):
    """Business priority levels for resource allocation."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FinancialMateriality(str, Enum):
    """Financial materiality levels."""
    MATERIAL = "material"
    MODERATE = "moderate"
    LOW = "low"


class WorkingCapitalImpact(str, Enum):
    """Working capital impact levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, Enum):
    """Business risk levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImpactTimeframe(str, Enum):
    """Impact timeframe for business effects."""
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class ActionUrgency(str, Enum):
    """Action urgency levels."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# CFO Grade Enhanced Schemas

class CFOGradeAssessment(BaseModel):
    """CFO grade assessment for exceptions."""
    cfo_grade: CFOGrade
    business_priority: BusinessPriority
    financial_materiality: FinancialMateriality
    working_capital_impact: WorkingCapitalImpact
    business_risk_level: RiskLevel
    impact_timeframe: ImpactTimeframe
    action_urgency: ActionUrgency
    justification: str


class FinancialImpact(BaseModel):
    """Financial impact assessment."""
    potential_loss: float
    loss_percentage: float
    confidence_level: str
    impact_description: str
    materiality: FinancialMateriality
    working_capital_cost: float
    resolution_cost_estimate: float


class WorkingCapitalAnalysis(BaseModel):
    """Working capital impact analysis."""
    level: WorkingCapitalImpact
    days_impacted: int
    capital_tied_up: float
    daily_wc_cost: float
    total_wc_cost: float
    impact_description: str


class BusinessRiskAssessment(BaseModel):
    """Business risk assessment."""
    overall_risk_level: RiskLevel
    financial_risk: str
    operational_risk: str
    compliance_risk: str
    reputational_risk: str
    strategic_risk: str


class ExecutiveSummary(BaseModel):
    """Executive summary for CFO review."""
    one_line_summary: str
    financial_exposure: Dict[str, Any]
    strategic_implications: List[str]
    immediate_action_required: Dict[str, Any]
    board_level_visibility: Dict[str, Any]
    confidence_level: str


class RecommendedAction(BaseModel):
    """Recommended action for exception resolution."""
    action: str
    urgency: ActionUrgency
    responsible_party: str
    timeline: str
    resource_requirements: List[str]
    expected_outcome: str


class CFOInsight(BaseModel):
    """Comprehensive CFO insight for exception."""
    executive_summary: ExecutiveSummary
    financial_impact: FinancialImpact
    working_capital_analysis: WorkingCapitalAnalysis
    risk_assessment: BusinessRiskAssessment
    recommended_actions: List[RecommendedAction]
    business_metrics: Dict[str, Any]
    investment_justification: Dict[str, Any]


# Enhanced Exception Schemas with CFO Fields

class ExceptionCreateRequest(BaseModel):
    """Request for manual exception creation."""
    invoice_id: str
    reason_code: ExceptionReasonCode
    category: ExceptionCategory
    severity: ExceptionSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    auto_resolution_possible: bool = False
    suggested_actions: List[ExceptionAction] = Field(default_factory=list)


class CFOGradeExceptionCreate(BaseModel):
    """Request for CFO-graded exception creation."""
    invoice_id: str
    reason_code: ExceptionReasonCode
    category: ExceptionCategory
    severity: ExceptionSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    auto_resolution_possible: bool = False
    suggested_actions: List[ExceptionAction] = Field(default_factory=list)
    invoice_data: Optional[Dict[str, Any]] = None  # Additional invoice data for CFO analysis


class ExceptionResponseWithCFO(ExceptionResponse):
    """Exception response enhanced with CFO-grade fields."""
    cfo_grade: Optional[CFOGrade] = None
    business_priority: Optional[BusinessPriority] = None
    financial_materiality: Optional[FinancialMateriality] = None
    working_capital_impact: Optional[WorkingCapitalImpact] = None
    business_risk_level: Optional[RiskLevel] = None
    executive_summary: Optional[str] = None
    financial_impact_assessment: Optional[Dict[str, Any]] = None
    recommended_actions: Optional[List[str]] = None
    cfo_justification: Optional[str] = None


class ExceptionExplainabilityRequest(BaseModel):
    """Request for exception explainability analysis."""
    exception_id: str
    include_financial_impact: bool = True
    include_working_capital_analysis: bool = True
    include_risk_assessment: bool = True
    include_recommendations: bool = True
    detail_level: str = Field(default="comprehensive", pattern="^(basic|detailed|comprehensive)$")


class ExceptionExplainabilityResponse(BaseModel):
    """Response for exception explainability analysis."""
    exception_id: str
    analysis_timestamp: datetime
    exception_summary: Dict[str, Any]
    executive_summary: ExecutiveSummary
    financial_impact_assessment: FinancialImpact
    working_capital_implications: WorkingCapitalAnalysis
    cash_flow_analysis: Dict[str, Any]
    risk_assessment: BusinessRiskAssessment
    operational_impact: Dict[str, Any]
    recommended_actions: List[RecommendedAction]
    business_metrics: Dict[str, Any]
    investment_justification: Dict[str, Any]
    cfo_grade_details: CFOGradeAssessment


class CFOGradeSummary(BaseModel):
    """CFO grade summary for dashboard."""
    total_exceptions: int
    grade_distribution: Dict[CFOGrade, int]
    priority_distribution: Dict[BusinessPriority, int]
    materiality_distribution: Dict[FinancialMateriality, int]
    risk_distribution: Dict[RiskLevel, int]
    financial_impact_summary: Dict[str, float]
    working_capital_impact_summary: Dict[str, float]
    critical_exceptions: List[ExceptionResponseWithCFO]
    high_priority_actions: List[RecommendedAction]
    trends: Dict[str, Any]
    recommendations: List[str]


class CFOGradeSummaryRequest(BaseModel):
    """Request for CFO grade summary."""
    time_period_days: int = 30
    include_resolved: bool = False
    grade_filter: Optional[List[CFOGrade]] = None
    priority_filter: Optional[List[BusinessPriority]] = None
    materiality_filter: Optional[List[FinancialMateriality]] = None
    include_financial_summary: bool = True
    include_trends: bool = True


class CFOGradeBatchUpdate(BaseModel):
    """Batch update request for CFO-graded exceptions."""
    exception_ids: List[str]
    cfo_grade_update: Optional[CFOGrade] = None
    business_priority_update: Optional[BusinessPriority] = None
    financial_materiality_update: Optional[FinancialMateriality] = None
    add_notes: Optional[str] = None
    escalation_required: bool = False
    escalation_reason: Optional[str] = None


class CFOExceptionMetrics(BaseModel):
    """CFO-specific exception metrics."""
    period_days: int
    total_exceptions: int
    cfo_grade_distribution: Dict[CFOGrade, int]
    financial_exposure_total: float
    working_capital_impact_total: float
    high_risk_exceptions_count: int
    board_reporting_required_count: int
    average_resolution_time_hours: float
    exceptions_by_category: Dict[str, Dict[CFOGrade, int]]
    trends: Dict[str, Any]
    top_financial_impacts: List[Dict[str, Any]]
    recommended_investments: List[Dict[str, Any]]


class ExceptionCreateRequest(BaseModel):
    """Request for manual exception creation."""
    invoice_id: str
    reason_code: ExceptionReasonCode
    category: ExceptionCategory
    severity: ExceptionSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    auto_resolution_possible: bool = False
    suggested_actions: List[ExceptionAction] = Field(default_factory=list)