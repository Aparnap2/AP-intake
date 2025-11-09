"""
Working Capital Analytics data validation schemas.

This module provides Pydantic schemas for validating and serializing
working capital analytics data including cash flow projections,
payment optimization, collection metrics, and scoring.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator, root_validator


# Base schemas
class BaseAnalyticsSchema(BaseModel):
    """Base schema for analytics data."""

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None,
            datetime: lambda v: v.isoformat() if v is not None else None,
            date: lambda v: v.isoformat() if v is not None else None,
            UUID: lambda v: str(v) if v is not None else None
        }


# ================================
# CASH FLOW SCHEMAS
# ================================

class CashFlowProjectionBase(BaseAnalyticsSchema):
    """Base schema for cash flow projection data."""

    projection_date: datetime
    projection_period: str
    scenario_type: str
    projected_inflow: Decimal = Field(ge=0, description="Projected cash inflow")
    projected_outflow: Decimal = Field(ge=0, description="Projected cash outflow")
    net_cash_flow: Decimal = Field(description="Net cash flow (inflow - outflow)")
    confidence_score: Optional[float] = Field(None, ge=0, le=100, description="Confidence score 0-100")
    accuracy_score: Optional[float] = Field(None, ge=0, le=100, description="Historical accuracy score")
    variance_percentage: Optional[float] = Field(None, description="Variance percentage")
    assumptions: Optional[Dict[str, Any]] = Field(None, description="Projection assumptions")


class CashFlowProjectionCreate(CashFlowProjectionBase):
    """Schema for creating cash flow projections."""
    pass


class CashFlowProjectionUpdate(BaseAnalyticsSchema):
    """Schema for updating cash flow projections."""

    projected_inflow: Optional[Decimal] = Field(None, ge=0)
    projected_outflow: Optional[Decimal] = Field(None, ge=0)
    confidence_score: Optional[float] = Field(None, ge=0, le=100)
    accuracy_score: Optional[float] = Field(None, ge=0, le=100)
    variance_percentage: Optional[float] = None


class CashFlowProjectionResponse(CashFlowProjectionBase):
    """Schema for cash flow projection response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    inflow_breakdown: Optional[Dict[str, Any]] = None
    outflow_breakdown: Optional[Dict[str, Any]] = None
    projection_model_version: Optional[str] = None
    data_quality_score: Optional[float] = None
    generated_by: Optional[str] = None


class CashFlowProjectionRequest(BaseAnalyticsSchema):
    """Schema for cash flow projection requests."""

    days: int = Field(30, ge=1, le=365, description="Number of days to project")
    scenario: str = Field("realistic", description="Scenario type")
    customer_id: Optional[UUID] = None
    start_date: Optional[date] = None


class ScenarioAnalysisRequest(BaseAnalyticsSchema):
    """Schema for scenario analysis requests."""

    scenarios: Optional[List[str]] = Field(None, description="Scenarios to analyze")
    days: int = Field(90, ge=1, le=365, description="Projection period")
    customer_id: Optional[UUID] = None


# ================================
# PAYMENT OPTIMIZATION SCHEMAS
# ================================

class PaymentOptimizationBase(BaseAnalyticsSchema):
    """Base schema for payment optimization data."""

    invoice_id: UUID
    optimization_type: str = Field(..., description="Type of optimization")
    recommended_payment_date: datetime
    potential_savings: Decimal = Field(ge=0, description="Potential savings amount")
    working_capital_impact: Decimal = Field(description="Working capital impact")
    roi_percentage: Optional[float] = Field(None, description="ROI percentage")
    priority_level: str = Field("medium", description="Priority level")
    urgency_score: Optional[float] = Field(None, ge=0, le=100, description="Urgency score 0-100")
    optimization_logic: Optional[Dict[str, Any]] = None
    assumptions: Optional[Dict[str, Any]] = None
    risk_factors: Optional[List[str]] = None


class PaymentOptimizationCreate(PaymentOptimizationBase):
    """Schema for creating payment optimization records."""
    pass


class PaymentOptimizationUpdate(BaseAnalyticsSchema):
    """Schema for updating payment optimization records."""

    status: Optional[str] = None
    implemented_at: Optional[datetime] = None
    actual_savings: Optional[Decimal] = Field(None, ge=0)
    feedback_score: Optional[float] = Field(None, ge=1, le=5)


class PaymentOptimizationResponse(PaymentOptimizationBase):
    """Schema for payment optimization response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    status: str = Field(..., description="Current status")
    implemented_at: Optional[datetime] = None
    actual_savings: Optional[Decimal] = None
    feedback_score: Optional[float] = None


class PaymentOptimizationScenario(BaseAnalyticsSchema):
    """Schema for individual payment optimization scenario."""

    scenario_id: str
    scenario_name: str
    invoice_amount: Decimal = Field(gt=0)
    discount_percent: Decimal = Field(ge=0, le=100)
    discount_days: int = Field(gt=0)
    regular_terms: int = Field(gt=0)
    cost_of_capital: Decimal = Field(ge=0, le=1)


class PaymentOptimizationRequest(BaseAnalyticsSchema):
    """Schema for payment optimization analysis requests."""

    scenarios: List[PaymentOptimizationScenario]
    analysis_type: str = Field("roi", description="Type of analysis to perform")


# ================================
# EARLY PAYMENT DISCOUNT SCHEMAS
# ================================

class EarlyPaymentDiscountBase(BaseAnalyticsSchema):
    """Base schema for early payment discount data."""

    invoice_id: UUID
    discount_percent: Decimal = Field(gt=0, le=100, description="Discount percentage")
    discount_days: int = Field(gt=0, description="Discount period in days")
    discount_deadline: datetime
    discount_amount: Decimal = Field(ge=0, description="Discount amount")
    annualized_return: Optional[float] = Field(None, description="Annualized return percentage")
    break_even_days: Optional[int] = Field(None, ge=0, description="Break-even point in days")
    utilization_probability: Optional[float] = Field(None, ge=0, le=100, description="Utilization probability")
    risk_score: Optional[float] = Field(None, ge=0, le=100, description="Risk assessment score")
    alternative_options: Optional[Dict[str, Any]] = None


class EarlyPaymentDiscountCreate(EarlyPaymentDiscountBase):
    """Schema for creating early payment discount records."""
    pass


class EarlyPaymentDiscountUpdate(BaseAnalyticsSchema):
    """Schema for updating early payment discount records."""

    status: Optional[str] = None
    utilized_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    days_remaining: Optional[int] = Field(None, ge=0)


class EarlyPaymentDiscountResponse(EarlyPaymentDiscountBase):
    """Schema for early payment discount response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    status: str = Field(..., description="Current status")
    utilized_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    utilization_history: Optional[Dict[str, Any]] = None
    competitive_analysis: Optional[Dict[str, Any]] = None


class DiscountBreakEvenRequest(BaseAnalyticsSchema):
    """Schema for discount break-even analysis requests."""

    invoice_amount: Decimal = Field(gt=0)
    discount_percent: Decimal = Field(gt=0, le=100)
    discount_period_days: int = Field(gt=0)
    normal_terms_days: int = Field(gt=0)
    cost_of_capital: Optional[Decimal] = Field(None, ge=0, le=1)


class DiscountRiskAssessmentRequest(BaseAnalyticsSchema):
    """Schema for discount risk assessment requests."""

    annual_revenue: Optional[Decimal] = Field(None, gt=0)
    average_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    expected_utilization_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    customer_concentration_risk: Optional[Decimal] = Field(None, ge=0, le=1)
    cash_flow_volatility: Optional[Decimal] = Field(None, ge=0, le=1)


# ================================
# COLLECTION METRICS SCHEMAS
# ================================

class CollectionMetricsBase(BaseAnalyticsSchema):
    """Base schema for collection metrics data."""

    metric_date: datetime
    metric_period: str = Field(..., description="Metric period")
    dso: Optional[float] = Field(None, ge=0, description="Days Sales Outstanding")
    collection_rate: Optional[float] = Field(None, ge=0, le=100, description="Collection rate percentage")
    cei: Optional[float] = Field(None, ge=0, le=100, description="Collection Effectiveness Index")
    average_days_to_pay: Optional[float] = Field(None, ge=0, description="Average days to pay")
    current_receivables: Decimal = Field(0, ge=0, description="Current receivables amount")
    days_1_30: Decimal = Field(0, ge=0, description="1-30 days overdue")
    days_31_60: Decimal = Field(0, ge=0, description="31-60 days overdue")
    days_61_90: Decimal = Field(0, ge=0, description="61-90 days overdue")
    days_over_90: Decimal = Field(0, ge=0, description="Over 90 days overdue")
    total_invoices: int = Field(0, ge=0, description="Total invoice count")
    paid_invoices: int = Field(0, ge=0, description="Paid invoice count")
    overdue_invoices: int = Field(0, ge=0, description="Overdue invoice count")
    write_off_amount: Decimal = Field(0, ge=0, description="Write-off amount")


class CollectionMetricsCreate(CollectionMetricsBase):
    """Schema for creating collection metrics records."""
    pass


class CollectionMetricsUpdate(BaseAnalyticsSchema):
    """Schema for updating collection metrics records."""

    dso: Optional[float] = Field(None, ge=0)
    collection_rate: Optional[float] = Field(None, ge=0, le=100)
    cei: Optional[float] = Field(None, ge=0, le=100)
    average_days_to_pay: Optional[float] = Field(None, ge=0)
    total_invoices: Optional[int] = Field(None, ge=0)
    paid_invoices: Optional[int] = Field(None, ge=0)
    overdue_invoices: Optional[int] = Field(None, ge=0)


class CollectionMetricsResponse(CollectionMetricsBase):
    """Schema for collection metrics response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    dso_trend: Optional[str] = None
    collection_trend: Optional[str] = None
    efficiency_trend: Optional[str] = None
    customer_breakdown: Optional[Dict[str, Any]] = None
    industry_comparison: Optional[Dict[str, Any]] = None
    predictive_metrics: Optional[Dict[str, Any]] = None


class AgingBucketRequest(BaseAnalyticsSchema):
    """Schema for aging bucket analysis requests."""

    customer_id: Optional[UUID] = None
    include_details: bool = Field(False, description="Include detailed invoice breakdown")
    as_of_date: Optional[date] = None


class DSOMetricsRequest(BaseAnalyticsSchema):
    """Schema for DSO metrics requests."""

    customer_id: Optional[UUID] = None
    period: str = Field("current", description="Analysis period")
    end_date: Optional[date] = None


# ================================
# WORKING CAPITAL SCORE SCHEMAS
# ================================

class WorkingCapitalScoreBase(BaseAnalyticsSchema):
    """Base schema for working capital score data."""

    score_date: datetime
    score_period: str = Field(..., description="Score period")
    total_score: float = Field(ge=0, le=100, description="Total working capital score")
    previous_score: Optional[float] = Field(None, ge=0, le=100)
    score_change: Optional[float] = None
    collection_efficiency_score: float = Field(ge=0, le=100)
    payment_optimization_score: float = Field(ge=0, le=100)
    discount_utilization_score: float = Field(ge=0, le=100)
    cash_flow_management_score: float = Field(ge=0, le=100)
    collection_weight: Decimal = Field(0.40, ge=0, le=1, description="Collection efficiency weight")
    payment_weight: Decimal = Field(0.30, ge=0, le=1, description="Payment optimization weight")
    discount_weight: Decimal = Field(0.20, ge=0, le=1, description="Discount utilization weight")
    cash_flow_weight: Decimal = Field(0.10, ge=0, le=1, description="Cash flow management weight")


class WorkingCapitalScoreCreate(WorkingCapitalScoreBase):
    """Schema for creating working capital score records."""
    pass


class WorkingCapitalScoreUpdate(BaseAnalyticsSchema):
    """Schema for updating working capital score records."""

    total_score: Optional[float] = Field(None, ge=0, le=100)
    collection_efficiency_score: Optional[float] = Field(None, ge=0, le=100)
    payment_optimization_score: Optional[float] = Field(None, ge=0, le=100)
    discount_utilization_score: Optional[float] = Field(None, ge=0, le=100)
    cash_flow_management_score: Optional[float] = Field(None, ge=0, le=100)


class WorkingCapitalScoreResponse(WorkingCapitalScoreBase):
    """Schema for working capital score response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    percentile_rank: Optional[float] = Field(None, ge=0, le=100)
    benchmark_comparison: Optional[Dict[str, Any]] = None
    improvement_areas: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    trend_direction: Optional[str] = None
    trend_strength: Optional[str] = None
    volatility_index: Optional[float] = Field(None, ge=0, le=100)
    component_details: Optional[Dict[str, Any]] = None
    calculation_methodology: Optional[Dict[str, Any]] = None
    confidence_level: Optional[float] = Field(None, ge=0, le=100)


class WorkingCapitalScoreRequest(BaseAnalyticsSchema):
    """Schema for working capital score requests."""

    customer_id: Optional[UUID] = None
    include_benchmarks: bool = Field(True, description="Include industry benchmarks")
    period: str = Field("current", description="Analysis period")
    score_date: Optional[date] = None


class OptimizationRecommendationRequest(BaseAnalyticsSchema):
    """Schema for optimization recommendations requests."""

    customer_id: Optional[UUID] = None
    priority_level: Optional[str] = None
    category: Optional[str] = None
    limit: int = Field(20, ge=1, le=100, description="Maximum number of recommendations")


# ================================
# ALERT SCHEMAS
# ================================

class WorkingCapitalAlertBase(BaseAnalyticsSchema):
    """Base schema for working capital alerts."""

    alert_type: str = Field(..., description="Type of alert")
    severity: str = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    alert_data: Dict[str, Any] = Field(..., description="Alert-specific data")
    threshold_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    deviation_percentage: Optional[float] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    time_period: Optional[str] = None
    financial_impact: Optional[Decimal] = Field(None, ge=0)
    operational_impact: Optional[str] = None
    recommended_actions: Optional[List[str]] = None


class WorkingCapitalAlertCreate(WorkingCapitalAlertBase):
    """Schema for creating working capital alerts."""
    pass


class WorkingCapitalAlertUpdate(BaseAnalyticsSchema):
    """Schema for updating working capital alerts."""

    status: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    notification_sent: Optional[bool] = None
    notification_attempts: Optional[int] = Field(None, ge=0)


class WorkingCapitalAlertResponse(WorkingCapitalAlertBase):
    """Schema for working capital alert response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    status: str = Field(..., description="Current alert status")
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    notification_sent: bool = Field(default=False)
    notification_channels: Optional[List[str]] = None
    notification_attempts: int = Field(default=0)
    last_notification_at: Optional[datetime] = None


# ================================
# DASHBOARD SCHEMAS
# ================================

class AnalyticsDashboardRequest(BaseAnalyticsSchema):
    """Schema for analytics dashboard requests."""

    customer_id: Optional[UUID] = None
    period: str = Field("current", description="Analysis period")
    include_forecasts: bool = Field(True, description="Include forecast data")
    include_recommendations: bool = Field(True, description="Include recommendations")
    refresh_cache: bool = Field(False, description="Force cache refresh")


class AnalyticsDashboardResponse(BaseAnalyticsSchema):
    """Schema for analytics dashboard response."""

    overall_score: Dict[str, Any]
    cash_flow_metrics: Dict[str, Any]
    collection_metrics: Dict[str, Any]
    discount_opportunities: Dict[str, Any]
    risk_indicators: Dict[str, Any]
    trend_data: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    recommendations: Optional[List[Dict[str, Any]]] = None
    forecasts: Optional[Dict[str, Any]] = None
    benchmark_comparison: Optional[Dict[str, Any]] = None


# ================================
# VALIDATION SCHEMAS
# ================================

class ValidationError(BaseAnalyticsSchema):
    """Schema for validation errors."""

    field: str = Field(..., description="Field with validation error")
    message: str = Field(..., description="Error message")
    value: Any = Field(None, description="Invalid value")
    constraint: Optional[str] = None


class ValidationResult(BaseAnalyticsSchema):
    """Schema for validation results."""

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")
    warnings: List[ValidationError] = Field(default_factory=list, description="Validation warnings")


# ================================
# RESPONSE WRAPPER SCHEMAS
# ================================

class AnalyticsResponse(BaseAnalyticsSchema):
    """Generic analytics response wrapper."""

    success: bool = Field(..., description="Whether request was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Response message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")
    validation: Optional[ValidationResult] = Field(None, description="Validation results")


class ErrorResponse(BaseAnalyticsSchema):
    """Schema for error responses."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")


# ================================
# VALIDATORS
# ================================

def validate_discount_percent(value: Decimal) -> Decimal:
    """Validate discount percentage is within reasonable bounds."""
    if value < 0 or value > 100:
        raise ValueError("Discount percentage must be between 0 and 100")
    return value


def validate_roi_percentage(value: Optional[float]) -> Optional[float]:
    """Validate ROI percentage."""
    if value is not None and abs(value) > 1000:  # Allow for very high ROI but cap at 1000%
        raise ValueError("ROI percentage seems unrealistic (over 1000%)")
    return value


def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Validate date range makes sense."""
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date")


def validate_working_capital_score(value: float) -> float:
    """Validate working capital score is within valid range."""
    if not (0 <= value <= 100):
        raise ValueError("Working capital score must be between 0 and 100")
    return value


def validate_payment_terms(days: int) -> int:
    """Validate payment terms are reasonable."""
    if not (1 <= days <= 365):
        raise ValueError("Payment terms must be between 1 and 365 days")
    return days


# ================================
# CUSTOM VALIDATOR DECORATORS
# ================================

def validate_positive_amount(field_name: str):
    """Decorator to validate positive decimal amounts."""
    def validator(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"{field_name} must be non-negative")
        return v
    return validator


def validate_percentage_range(field_name: str, min_val: float = 0, max_val: float = 100):
    """Decorator to validate percentage ranges."""
    def validator(cls, v):
        if v is not None and not (min_val <= v <= max_val):
            raise ValueError(f"{field_name} must be between {min_val} and {max_val}")
        return v
    return validator


def validate_date_not_future(field_name: str):
    """Decorator to validate dates are not in the future."""
    def validator(cls, v):
        if v and v > datetime.utcnow():
            raise ValueError(f"{field_name} cannot be in the future")
        return v
    return validator