"""
CFO Digest API schemas for executive reporting.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer
from enum import Enum


class DigestPriority(str, Enum):
    """Priority levels for digest items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BusinessImpactLevel(str, Enum):
    """Business impact levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class EvidenceType(str, Enum):
    """Types of evidence links."""
    INVOICE = "invoice"
    EXCEPTION = "exception"
    WORKFLOW_TRACE = "workflow_trace"
    COST_ANALYSIS = "cost_analysis"
    PERFORMANCE_METRIC = "performance_metric"
    SLO_REPORT = "slo_report"


class EvidenceLink(BaseModel):
    """Evidence link for digest items."""
    evidence_id: str = Field(..., description="Unique identifier for evidence")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    title: str = Field(..., description="Evidence title")
    description: str = Field(..., description="Evidence description")
    url: str = Field(..., description="Direct URL to evidence")
    created_at: datetime = Field(..., description="When evidence was created")
    impact_score: Optional[float] = Field(None, description="Impact score (0-100)")

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class KeyMetric(BaseModel):
    """Key performance indicator for CFO digest."""
    name: str = Field(..., description="Metric name")
    value: Union[float, int, str, Decimal] = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    change_percentage: Optional[float] = Field(None, description="Week-over-week change percentage")
    trend: Optional[str] = Field(None, description="Trend direction: increasing, decreasing, stable")
    target: Optional[Union[float, int, Decimal]] = Field(None, description="Target value")
    attainment_percentage: Optional[float] = Field(None, description="Percentage of target achieved")
    priority: DigestPriority = Field(DigestPriority.MEDIUM, description="Priority level")
    evidence_links: List[EvidenceLink] = Field(default_factory=list, description="Supporting evidence")


class ActionItem(BaseModel):
    """Action item with business impact scoring."""
    id: str = Field(..., description="Unique action item identifier")
    title: str = Field(..., description="Action item title")
    description: str = Field(..., description="Detailed description")
    business_impact_level: BusinessImpactLevel = Field(..., description="Business impact level")
    financial_impact: Optional[Decimal] = Field(None, description="Estimated financial impact")
    time_to_resolve: Optional[str] = Field(None, description="Estimated time to resolve")
    owner: Optional[str] = Field(None, description="Person/team responsible")
    priority: DigestPriority = Field(..., description="Priority level")
    due_date: Optional[datetime] = Field(None, description="Action item due date")
    status: str = Field("open", description="Current status")
    evidence_links: List[EvidenceLink] = Field(default_factory=list, description="Supporting evidence")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")

    @field_serializer('due_date')
    def serialize_due_date(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('financial_impact')
    def serialize_financial_impact(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value else None


class ExecutiveSummary(BaseModel):
    """Executive summary for CFO digest."""
    headline: str = Field(..., description="Main headline for the week")
    overall_performance_rating: str = Field(..., description="Overall performance rating")
    key_highlights: List[str] = Field(..., description="Key highlights for the week")
    key_concerns: List[str] = Field(default_factory=list, description="Key concerns to address")
    business_insights: List[str] = Field(..., description="Business insights and observations")
    working_capital_impact: str = Field(..., description="Working capital impact summary")
    financial_summary: str = Field(..., description="Financial performance summary")
    operational_efficiency: str = Field(..., description="Operational efficiency summary")
    risk_assessment: str = Field(..., description="Risk assessment summary")
    outlook: str = Field(..., description="Forward-looking outlook")


class WorkingCapitalMetrics(BaseModel):
    """Working capital specific metrics."""
    total_wc_tied: Decimal = Field(..., description="Total working capital tied up")
    wc_tied_change_pct: Optional[float] = Field(None, description="Week-over-week change percentage")
    avg_processing_time_hours: float = Field(..., description="Average processing time in hours")
    automation_rate: float = Field(..., description="Automation rate percentage")
    exception_resolution_rate: float = Field(..., description="Exception resolution rate percentage")
    vendor_impact_analysis: Dict[str, Any] = Field(default_factory=dict, description="Vendor-specific impact")
    duplicate_impact_score: Optional[float] = Field(None, description="Duplicate detection impact score")
    cost_savings_opportunities: List[str] = Field(default_factory=list, description="Identified cost savings opportunities")

    @field_serializer('total_wc_tied')
    def serialize_total_wc_tied(self, value: Decimal) -> float:
        return float(value)


class CFODigest(BaseModel):
    """Complete CFO Digest model."""
    id: Optional[UUID] = Field(None, description="Digest ID")
    title: str = Field(..., description="Digest title")
    week_start: datetime = Field(..., description="Week start date")
    week_end: datetime = Field(..., description="Week end date")
    generated_at: datetime = Field(..., description="When digest was generated")
    status: str = Field("draft", description="Digest status")

    # Core digest components
    executive_summary: ExecutiveSummary = Field(..., description="Executive summary")
    key_metrics: List[KeyMetric] = Field(..., description="Key performance indicators")
    working_capital_metrics: WorkingCapitalMetrics = Field(..., description="Working capital metrics")
    action_items: List[ActionItem] = Field(..., description="Action items with business impact")

    # Metadata
    total_invoices_processed: int = Field(..., description="Total invoices processed this week")
    total_exceptions: int = Field(..., description="Total exceptions this week")
    cost_per_invoice: Decimal = Field(..., description="Average cost per invoice")
    roi_percentage: float = Field(..., description="ROI percentage")

    # Delivery information
    delivery_scheduled_at: Optional[datetime] = Field(None, description="When digest is scheduled for delivery")
    delivery_status: str = Field("pending", description="Delivery status")
    recipients: List[str] = Field(default_factory=list, description="Delivery recipients")

    @field_serializer('id')
    def serialize_id(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None

    @field_serializer('week_start')
    def serialize_week_start(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('week_end')
    def serialize_week_end(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('generated_at')
    def serialize_generated_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('delivery_scheduled_at')
    def serialize_delivery_scheduled_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('cost_per_invoice')
    def serialize_cost_per_invoice(self, value: Decimal) -> float:
        return float(value)


class CFODigestRequest(BaseModel):
    """Request model for generating CFO digest."""
    week_start: Optional[datetime] = Field(None, description="Week start date (defaults to last week)")
    week_end: Optional[datetime] = Field(None, description="Week end date")
    include_working_capital_analysis: bool = Field(True, description="Include working capital analysis")
    include_action_items: bool = Field(True, description="Include action items")
    include_evidence_links: bool = Field(True, description="Include evidence links")
    priority_threshold: DigestPriority = Field(DigestPriority.MEDIUM, description="Minimum priority threshold")
    business_impact_threshold: BusinessImpactLevel = Field(BusinessImpactLevel.MODERATE, description="Minimum business impact threshold")
    recipients: List[str] = Field(default_factory=list, description="Additional recipients")
    schedule_delivery: bool = Field(False, description="Schedule automatic delivery")
    delivery_time: Optional[str] = Field("09:00", description="Delivery time (HH:MM format)")

    @field_serializer('week_start')
    def serialize_week_start(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('week_end')
    def serialize_week_end(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class CFODigestResponse(BaseModel):
    """Response model for CFO digest operations."""
    success: bool = Field(..., description="Operation success status")
    digest_id: Optional[str] = Field(None, description="Generated digest ID")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    errors: Optional[List[str]] = Field(None, description="Error messages if any")


class CFODigestListResponse(BaseModel):
    """Response model for listing CFO digests."""
    digests: List[CFODigest] = Field(..., description="List of CFO digests")
    total_count: int = Field(..., description="Total number of digests")
    page: int = Field(1, description="Current page")
    page_size: int = Field(10, description="Page size")
    has_more: bool = Field(False, description="Whether there are more pages")


class CFODigestScheduleRequest(BaseModel):
    """Request model for scheduling recurring CFO digest."""
    is_active: bool = Field(True, description="Whether scheduling is active")
    delivery_day: str = Field("monday", description="Delivery day of week")
    delivery_time: str = Field("09:00", description="Delivery time (HH:MM format)")
    recipients: List[str] = Field(..., description="Delivery recipients")
    priority_threshold: DigestPriority = Field(DigestPriority.MEDIUM, description="Minimum priority threshold")
    business_impact_threshold: BusinessImpactLevel = Field(BusinessImpactLevel.MODERATE, description="Minimum business impact threshold")
    include_working_capital_analysis: bool = Field(True, description="Include working capital analysis")
    include_action_items: bool = Field(True, description="Include action items")
    timezone: str = Field("UTC", description="Timezone for scheduling")


class CFODigestScheduleResponse(BaseModel):
    """Response model for scheduling operations."""
    success: bool = Field(..., description="Operation success status")
    schedule_id: Optional[str] = Field(None, description="Schedule ID")
    message: str = Field(..., description="Response message")
    next_delivery: Optional[str] = Field(None, description="Next scheduled delivery time")


# N8n Integration Models

class N8nCFODigestRequest(BaseModel):
    """N8n workflow request for CFO digest."""
    digest_id: str = Field(..., description="Digest ID")
    title: str = Field(..., description="Digest title")
    week_start: datetime = Field(..., description="Week start date")
    week_end: datetime = Field(..., description="Week end date")
    executive_summary: ExecutiveSummary = Field(..., description="Executive summary")
    key_metrics: List[KeyMetric] = Field(..., description="Key metrics")
    working_capital_metrics: WorkingCapitalMetrics = Field(..., description="Working capital metrics")
    action_items: List[ActionItem] = Field(..., description="Action items")
    recipients: List[str] = Field(..., description="Email recipients")
    delivery_priority: str = Field("high", description="Email delivery priority")

    @field_serializer('week_start')
    def serialize_week_start(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('week_end')
    def serialize_week_end(self, value: datetime) -> str:
        return value.isoformat()


# Email Template Models

class EmailTemplateData(BaseModel):
    """Data for email template rendering."""
    digest: CFODigest = Field(..., description="CFO digest data")
    company_name: str = Field("Your Company", description="Company name")
    logo_url: Optional[str] = Field(None, description="Company logo URL")
    brand_colors: Dict[str, str] = Field(default_factory=lambda: {
        "primary": "#2563eb",
        "secondary": "#64748b",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626"
    }, description="Brand colors for email template")
    footer_text: str = Field("This is an automated executive digest from AP Intake & Validation System", description="Email footer text")