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