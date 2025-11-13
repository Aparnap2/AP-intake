"""
Working Capital Analytics data models.

This module defines comprehensive data models for working capital analytics,
including cash flow projections, payment optimization, early payment discounts,
collection metrics, and working capital scoring.
"""

import enum
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    Integer,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class ProjectionPeriod(str, enum.Enum):
    """Projection period types for cash flow forecasting."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ScenarioType(str, enum.Enum):
    """Scenario types for cash flow analysis."""

    REALISTIC = "realistic"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    STRESS_TEST = "stress_test"


class DiscountStatus(str, enum.Enum):
    """Status of early payment discounts."""

    AVAILABLE = "available"
    UTILIZED = "utilized"
    EXPIRED = "expired"
    PENDING = "pending"


class PriorityLevel(str, enum.Enum):
    """Priority levels for recommendations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CashFlowProjection(Base, UUIDMixin, TimestampMixin):
    """Cash flow projection model for forecasting future cash flows."""

    __tablename__ = "cash_flow_projections"

    # Projection metadata
    projection_date = Column(DateTime(timezone=True), nullable=False, index=True)
    projection_period = Column(Enum(ProjectionPeriod), nullable=False, index=True)
    scenario_type = Column(Enum(ScenarioType), nullable=False, default=ScenarioType.REALISTIC)

    # Projection values
    projected_inflow = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    projected_outflow = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    net_cash_flow = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))

    # Confidence and accuracy
    confidence_score = Column(Numeric(5, 2), nullable=True)  # 0-100 confidence level
    accuracy_score = Column(Numeric(5, 2), nullable=True)   # Historical accuracy
    variance_percentage = Column(Numeric(5, 2), nullable=True)

    # Breakdown data
    inflow_breakdown = Column(JSON, nullable=True)  # Detailed inflow sources
    outflow_breakdown = Column(JSON, nullable=True)  # Detailed outflow categories
    assumptions = Column(JSON, nullable=True)  # Projection assumptions

    # Metadata
    projection_model_version = Column(String(20), nullable=True)
    data_quality_score = Column(Numeric(5, 2), nullable=True)
    generated_by = Column(String(100), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_projection_date_period', 'projection_date', 'projection_period'),
        Index('idx_projection_scenario', 'scenario_type', 'projection_date'),
        Index('idx_projection_confidence', 'confidence_score', 'projection_date'),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name='check_confidence_range'),
        CheckConstraint("accuracy_score >= 0 AND accuracy_score <= 100", name='check_accuracy_range'),
    )

    def __repr__(self):
        return f"<CashFlowProjection(date={self.projection_date}, net_flow={self.net_cash_flow}, scenario={self.scenario_type})>"

    def calculate_variance(self, actual_inflow: Optional[Decimal] = None, actual_outflow: Optional[Decimal] = None):
        """Calculate variance between projected and actual values."""
        if actual_inflow is not None:
            if self.projected_inflow != 0:
                inflow_variance = ((actual_inflow - self.projected_inflow) / self.projected_inflow) * 100
                self.variance_percentage = abs(inflow_variance)
            else:
                self.variance_percentage = Decimal('100.00') if actual_inflow != 0 else Decimal('0.00')

    @classmethod
    async def generate_projections(cls, db: AsyncSession, start_date: date, end_date: date,
                                 scenario: ScenarioType = ScenarioType.REALISTIC) -> List['CashFlowProjection']:
        """Generate cash flow projections for a given date range."""
        # Implementation would call analytics service
        projections = []
        current_date = start_date

        while current_date <= end_date:
            projection = cls(
                projection_date=datetime.combine(current_date, datetime.min.time()),
                projection_period=ProjectionPeriod.DAILY,
                scenario_type=scenario,
                # Analytics calculations would populate these values
            )
            projections.append(projection)
            current_date += timedelta(days=1)

        return projections


class PaymentOptimization(Base, UUIDMixin, TimestampMixin):
    """Payment optimization recommendations for working capital management."""

    __tablename__ = "payment_optimizations"

    # Related invoice
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False, index=True)

    # Optimization details
    optimization_type = Column(String(50), nullable=False, index=True)  # early_payment, timing, etc.
    recommended_payment_date = Column(DateTime(timezone=True), nullable=False)

    # Financial impact
    potential_savings = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    working_capital_impact = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    roi_percentage = Column(Numeric(5, 2), nullable=True)

    # Priority and timing
    priority_level = Column(Enum(PriorityLevel), nullable=False, default=PriorityLevel.MEDIUM)
    urgency_score = Column(Numeric(5, 2), nullable=True)  # 0-100 urgency score

    # Optimization details
    optimization_logic = Column(JSON, nullable=True)  # How recommendation was calculated
    assumptions = Column(JSON, nullable=True)  # Key assumptions made
    risk_factors = Column(JSON, nullable=True)  # Associated risks

    # Status tracking
    status = Column(String(20), nullable=False, default="pending")  # pending, accepted, rejected, expired
    implemented_at = Column(DateTime(timezone=True), nullable=True)
    actual_savings = Column(Numeric(15, 2), nullable=True)
    feedback_score = Column(Numeric(3, 1), nullable=True)  # 1-5 feedback rating

    # Performance indexes
    __table_args__ = (
        Index('idx_optimization_invoice', 'invoice_id', 'priority_level'),
        Index('idx_optimization_date', 'recommended_payment_date', 'status'),
        Index('idx_optimization_priority', 'priority_level', 'urgency_score'),
        Index('idx_optimization_savings', 'potential_savings', 'status'),
        CheckConstraint("roi_percentage >= -1000", name='check_roi_range'),  # Allow negative ROI
        CheckConstraint("urgency_score >= 0 AND urgency_score <= 100", name='check_urgency_range'),
        CheckConstraint("feedback_score >= 1 AND feedback_score <= 5", name='check_feedback_range'),
    )

    # Relationships
    invoice = relationship("ARInvoice", backref="payment_optimizations")

    def __repr__(self):
        return f"<PaymentOptimization(invoice={self.invoice_id}, type={self.optimization_type}, savings={self.potential_savings})>"

    def calculate_roi(self, cost_of_implementation: Decimal) -> Decimal:
        """Calculate ROI for the optimization recommendation."""
        if cost_of_implementation <= 0:
            return Decimal('0.00')

        roi = ((self.potential_savings - cost_of_implementation) / cost_of_implementation) * 100
        self.roi_percentage = roi
        return roi

    def update_status(self, new_status: str, actual_savings: Optional[Decimal] = None,
                     feedback: Optional[int] = None):
        """Update the status of the optimization recommendation."""
        self.status = new_status
        if new_status == "implemented":
            self.implemented_at = datetime.utcnow()
            if actual_savings is not None:
                self.actual_savings = actual_savings
        if feedback is not None:
            self.feedback_score = feedback


class EarlyPaymentDiscount(Base, UUIDMixin, TimestampMixin):
    """Early payment discount opportunities and tracking."""

    __tablename__ = "early_payment_discounts"

    # Related invoice
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False, index=True)

    # Discount terms
    discount_percent = Column(Numeric(5, 2), nullable=False)
    discount_days = Column(Integer, nullable=False)  # Days from invoice date
    discount_deadline = Column(DateTime(timezone=True), nullable=False)

    # Financial calculations
    discount_amount = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    annualized_return = Column(Numeric(8, 2), nullable=True)  # Annualized return percentage
    break_even_days = Column(Integer, nullable=True)  # Days at which discount breaks even

    # Status tracking
    status = Column(Enum(DiscountStatus), nullable=False, default=DiscountStatus.AVAILABLE)
    utilized_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    # Risk and analysis
    utilization_probability = Column(Numeric(5, 2), nullable=True)  # 0-100 probability
    risk_score = Column(Numeric(5, 2), nullable=True)  # 0-100 risk assessment
    alternative_options = Column(JSON, nullable=True)  # Alternative payment strategies

    # Tracking data
    days_remaining = Column(Integer, nullable=True)  # Days until deadline
    utilization_history = Column(JSON, nullable=True)  # Historical utilization patterns
    competitive_analysis = Column(JSON, nullable=True)  # Market comparison

    # Performance indexes
    __table_args__ = (
        Index('idx_discount_invoice', 'invoice_id', 'status'),
        Index('idx_discount_deadline', 'discount_deadline', 'status'),
        Index('idx_discount_return', 'annualized_return', 'discount_percent'),
        Index('idx_discount_probability', 'utilization_probability', 'risk_score'),
        CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name='check_discount_percent_range'),
        CheckConstraint("discount_days > 0", name='check_discount_days_positive'),
        CheckConstraint("utilization_probability >= 0 AND utilization_probability <= 100", name='check_utilization_probability_range'),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name='check_risk_score_range'),
    )

    # Relationships
    invoice = relationship("ARInvoice", backref="early_payment_discounts")

    def __repr__(self):
        return f"<EarlyPaymentDiscount(invoice={self.invoice_id}, percent={self.discount_percent}%, status={self.status})>"

    def calculate_annualized_return(self, payment_terms_days: int) -> Decimal:
        """Calculate the annualized return of taking the discount."""
        if payment_terms_days <= self.discount_days:
            return Decimal('0.00')

        days_saved = payment_terms_days - self.discount_days
        if days_saved <= 0:
            return Decimal('0.00')

        # Annualized return = (Discount % / (1 - Discount %)) * (365 / Days Saved)
        discount_rate = self.discount_percent / Decimal('100')
        annualized_return = (discount_rate / (1 - discount_rate)) * (Decimal('365') / days_saved) * 100
        self.annualized_return = annualized_return
        return annualized_return

    def calculate_break_even_days(self, cost_of_capital: Decimal) -> int:
        """Calculate the break-even point in days for taking the discount."""
        if cost_of_capital <= 0 or self.discount_percent <= 0:
            return 0

        # Break-even days = (Discount % / Cost of Capital %) * 365
        break_even = (self.discount_percent / cost_of_capital) * 365
        self.break_even_days = int(break_even)
        return int(break_even)

    def update_days_remaining(self):
        """Update the days remaining until discount deadline."""
        now = datetime.utcnow()
        if self.discount_deadline > now:
            self.days_remaining = (self.discount_deadline - now).days
        else:
            self.days_remaining = 0
            if self.status == DiscountStatus.AVAILABLE:
                self.status = DiscountStatus.EXPIRED
                self.expired_at = now

    def mark_utilized(self):
        """Mark the discount as utilized."""
        self.status = DiscountStatus.UTILIZED
        self.utilized_at = datetime.utcnow()


class CollectionMetrics(Base, UUIDMixin, TimestampMixin):
    """Collection efficiency metrics and tracking."""

    __tablename__ = "collection_metrics"

    # Metric period
    metric_date = Column(DateTime(timezone=True), nullable=False, index=True)
    metric_period = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly

    # Collection efficiency metrics
    dso = Column(Numeric(8, 2), nullable=True)  # Days Sales Outstanding
    collection_rate = Column(Numeric(5, 2), nullable=True)  # Collection rate percentage
    cei = Column(Numeric(5, 2), nullable=True)  # Collection Effectiveness Index
    average_days_to_pay = Column(Numeric(8, 2), nullable=True)

    # Aging metrics
    current_receivables = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    days_1_30 = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    days_31_60 = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    days_61_90 = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    days_over_90 = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))

    # Performance metrics
    total_invoices = Column(Integer, nullable=False, default=0)
    paid_invoices = Column(Integer, nullable=False, default=0)
    overdue_invoices = Column(Integer, nullable=False, default=0)
    write_off_amount = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))

    # Trend analysis
    dso_trend = Column(String(10), nullable=True)  # improving, declining, stable
    collection_trend = Column(String(10), nullable=True)
    efficiency_trend = Column(String(10), nullable=True)

    # Detailed breakdown
    customer_breakdown = Column(JSON, nullable=True)  # Metrics by customer
    industry_comparison = Column(JSON, nullable=True)  # Industry benchmark comparison
    predictive_metrics = Column(JSON, nullable=True)  # Predictive analytics data

    # Performance indexes
    __table_args__ = (
        Index('idx_metrics_date_period', 'metric_date', 'metric_period'),
        Index('idx_metrics_dso', 'dso', 'metric_date'),
        Index('idx_metrics_collection', 'collection_rate', 'metric_date'),
        Index('idx_metrics_aging', 'days_over_90', 'metric_date'),
        CheckConstraint("dso >= 0", name='check_dso_non_negative'),
        CheckConstraint("collection_rate >= 0 AND collection_rate <= 100", name='check_collection_rate_range'),
        CheckConstraint("cei >= 0 AND cei <= 100", name='check_cei_range'),
        CheckConstraint("average_days_to_pay >= 0", name='check_average_days_non_negative'),
        CheckConstraint("total_invoices >= 0", name='check_total_invoices_non_negative'),
        CheckConstraint("paid_invoices >= 0 AND paid_invoices <= total_invoices", name='check_paid_invoices_range'),
        CheckConstraint("overdue_invoices >= 0 AND overdue_invoices <= total_invoices", name='check_overdue_invoices_range'),
    )

    def __repr__(self):
        return f"<CollectionMetrics(date={self.metric_date}, dso={self.dso}, collection_rate={self.collection_rate}%)>"

    def calculate_total_outstanding(self) -> Decimal:
        """Calculate total outstanding receivables."""
        return (
            self.current_receivables + self.days_1_30 + self.days_31_60 +
            self.days_61_90 + self.days_over_90
        )

    def calculate_aging_percentage(self) -> Dict[str, Decimal]:
        """Calculate percentage breakdown by aging bucket."""
        total = self.calculate_total_outstanding()
        if total == 0:
            return {
                'current': Decimal('0.00'),
                'days_1_30': Decimal('0.00'),
                'days_31_60': Decimal('0.00'),
                'days_61_90': Decimal('0.00'),
                'days_over_90': Decimal('0.00')
            }

        return {
            'current': (self.current_receivables / total) * 100,
            'days_1_30': (self.days_1_30 / total) * 100,
            'days_31_60': (self.days_31_60 / total) * 100,
            'days_61_90': (self.days_61_90 / total) * 100,
            'days_over_90': (self.days_over_90 / total) * 100
        }

    def assess_risk_level(self) -> str:
        """Assess overall risk level based on metrics."""
        risk_score = 0

        # DSO risk assessment
        if self.dso and self.dso > 60:
            risk_score += 3
        elif self.dso and self.dso > 45:
            risk_score += 2
        elif self.dso and self.dso > 30:
            risk_score += 1

        # Collection rate risk
        if self.collection_rate and self.collection_rate < 80:
            risk_score += 3
        elif self.collection_rate and self.collection_rate < 90:
            risk_score += 2
        elif self.collection_rate and self.collection_rate < 95:
            risk_score += 1

        # Aging risk
        aging_pct = self.calculate_aging_percentage()
        if aging_pct['days_over_90'] > 20:
            risk_score += 3
        elif aging_pct['days_over_90'] > 10:
            risk_score += 2
        elif aging_pct['days_over_90'] > 5:
            risk_score += 1

        if risk_score >= 6:
            return "high"
        elif risk_score >= 4:
            return "medium"
        elif risk_score >= 2:
            return "low"
        else:
            return "minimal"


class WorkingCapitalScore(Base, UUIDMixin, TimestampMixin):
    """Working capital optimization scoring and tracking."""

    __tablename__ = "working_capital_scores"

    # Score period
    score_date = Column(DateTime(timezone=True), nullable=False, index=True)
    score_period = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly

    # Overall scores
    total_score = Column(Numeric(5, 2), nullable=False)  # 0-100 overall score
    previous_score = Column(Numeric(5, 2), nullable=True)  # Previous period score
    score_change = Column(Numeric(5, 2), nullable=True)  # Change from previous period

    # Component scores
    collection_efficiency_score = Column(Numeric(5, 2), nullable=False)
    payment_optimization_score = Column(Numeric(5, 2), nullable=False)
    discount_utilization_score = Column(Numeric(5, 2), nullable=False)
    cash_flow_management_score = Column(Numeric(5, 2), nullable=False)

    # Score weights
    collection_weight = Column(Numeric(3, 2), nullable=False, default=Decimal('0.40'))
    payment_weight = Column(Numeric(3, 2), nullable=False, default=Decimal('0.30'))
    discount_weight = Column(Numeric(3, 2), nullable=False, default=Decimal('0.20'))
    cash_flow_weight = Column(Numeric(3, 2), nullable=False, default=Decimal('0.10'))

    # Performance analysis
    percentile_rank = Column(Numeric(5, 2), nullable=True)  # Industry percentile
    benchmark_comparison = Column(JSON, nullable=True)  # Comparison with benchmarks
    improvement_areas = Column(ARRAY(String), nullable=True)  # Areas needing improvement
    strengths = Column(ARRAY(String), nullable=True)  # Strength areas

    # Trend analysis
    trend_direction = Column(String(10), nullable=True)  # improving, declining, stable
    trend_strength = Column(String(10), nullable=True)  # strong, moderate, weak
    volatility_index = Column(Numeric(5, 2), nullable=True)  # Score volatility

    # Detailed metrics
    component_details = Column(JSON, nullable=True)  # Detailed component analysis
    calculation_methodology = Column(JSON, nullable=True)  # How scores were calculated
    confidence_level = Column(Numeric(5, 2), nullable=True)  # Confidence in score accuracy

    # Performance indexes
    __table_args__ = (
        Index('idx_score_date_period', 'score_date', 'score_period'),
        Index('idx_score_total', 'total_score', 'score_date'),
        Index('idx_score_trend', 'trend_direction', 'score_date'),
        Index('idx_score_percentile', 'percentile_rank', 'score_date'),
        CheckConstraint("total_score >= 0 AND total_score <= 100", name='check_total_score_range'),
        CheckConstraint("collection_efficiency_score >= 0 AND collection_efficiency_score <= 100", name='check_collection_score_range'),
        CheckConstraint("payment_optimization_score >= 0 AND payment_optimization_score <= 100", name='check_payment_score_range'),
        CheckConstraint("discount_utilization_score >= 0 AND discount_utilization_score <= 100", name='check_discount_score_range'),
        CheckConstraint("cash_flow_management_score >= 0 AND cash_flow_management_score <= 100", name='check_cash_flow_score_range'),
        CheckConstraint("percentile_rank >= 0 AND percentile_rank <= 100", name='check_percentile_rank_range'),
        CheckConstraint("confidence_level >= 0 AND confidence_level <= 100", name='check_confidence_level_range'),
    )

    def __repr__(self):
        return f"<WorkingCapitalScore(date={self.score_date}, total={self.total_score}, trend={self.trend_direction})>"

    def calculate_weighted_score(self) -> Decimal:
        """Calculate total weighted score from components."""
        total = (
            self.collection_efficiency_score * self.collection_weight +
            self.payment_optimization_score * self.payment_weight +
            self.discount_utilization_score * self.discount_weight +
            self.cash_flow_management_score * self.cash_flow_weight
        )
        self.total_score = total
        return total

    def calculate_score_change(self, previous_total: Decimal):
        """Calculate change from previous period score."""
        self.previous_score = previous_total
        self.score_change = self.total_score - previous_total

        # Determine trend direction
        if self.score_change > 2:
            self.trend_direction = "improving"
        elif self.score_change < -2:
            self.trend_direction = "declining"
        else:
            self.trend_direction = "stable"

        # Determine trend strength
        if abs(self.score_change) > 10:
            self.trend_strength = "strong"
        elif abs(self.score_change) > 5:
            self.trend_strength = "moderate"
        else:
            self.trend_strength = "weak"

        return self.score_change

    def identify_improvement_areas(self, threshold: Decimal = Decimal('70.0')):
        """Identify areas needing improvement based on scores."""
        improvement_areas = []
        strengths = []

        if self.collection_efficiency_score < threshold:
            improvement_areas.append("collection_efficiency")
        else:
            strengths.append("collection_efficiency")

        if self.payment_optimization_score < threshold:
            improvement_areas.append("payment_optimization")
        else:
            strengths.append("payment_optimization")

        if self.discount_utilization_score < threshold:
            improvement_areas.append("discount_utilization")
        else:
            strengths.append("discount_utilization")

        if self.cash_flow_management_score < threshold:
            improvement_areas.append("cash_flow_management")
        else:
            strengths.append("cash_flow_management")

        self.improvement_areas = improvement_areas
        self.strengths = strengths

        return improvement_areas

    def calculate_confidence_level(self, data_quality: Decimal, sample_size: int) -> Decimal:
        """Calculate confidence level in the score accuracy."""
        # Base confidence on data quality and sample size
        base_confidence = data_quality

        # Adjust for sample size (higher sample size = higher confidence)
        if sample_size > 1000:
            size_adjustment = Decimal('0.0')
        elif sample_size > 500:
            size_adjustment = Decimal('5.0')
        elif sample_size > 100:
            size_adjustment = Decimal('10.0')
        else:
            size_adjustment = Decimal('20.0')

        confidence = base_confidence - size_adjustment
        self.confidence_level = max(Decimal('0.0'), min(Decimal('100.0'), confidence))

        return self.confidence_level


class WorkingCapitalAlert(Base, UUIDMixin, TimestampMixin):
    """Alerts and notifications for working capital optimization."""

    __tablename__ = "working_capital_alerts"

    # Alert identification
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(Enum(PriorityLevel), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    # Alert data
    alert_data = Column(JSON, nullable=False)  # Detailed alert information
    threshold_value = Column(Numeric(15, 2), nullable=True)  # Threshold that triggered alert
    actual_value = Column(Numeric(15, 2), nullable=True)  # Actual value that triggered alert
    deviation_percentage = Column(Numeric(5, 2), nullable=True)

    # Context
    related_entity_type = Column(String(50), nullable=True)  # invoice, customer, etc.
    related_entity_id = Column(UUID(as_uuid=True), nullable=True)
    time_period = Column(String(20), nullable=True)  # Daily, weekly, monthly

    # Alert lifecycle
    status = Column(String(20), nullable=False, default="active")  # active, acknowledged, resolved
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Notification tracking
    notification_sent = Column(Boolean, nullable=False, default=False)
    notification_channels = Column(ARRAY(String), nullable=True)  # Email, SMS, Slack, etc.
    notification_attempts = Column(Integer, nullable=False, default=0)
    last_notification_at = Column(DateTime(timezone=True), nullable=True)

    # Impact assessment
    financial_impact = Column(Numeric(15, 2), nullable=True)
    operational_impact = Column(String(20), nullable=True)  # low, medium, high
    recommended_actions = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_alert_type_severity', 'alert_type', 'severity'),
        Index('idx_alert_status_created', 'status', 'created_at'),
        Index('idx_alert_entity', 'related_entity_type', 'related_entity_id'),
        Index('idx_alert_impact', 'financial_impact', 'operational_impact'),
        CheckConstraint("notification_attempts >= 0", name='check_notification_attempts_non_negative'),
    )

    def __repr__(self):
        return f"<WorkingCapitalAlert(type={self.alert_type}, severity={self.severity}, status={self.status})>"

    def calculate_deviation(self):
        """Calculate deviation percentage from threshold."""
        if self.threshold_value and self.threshold_value != 0 and self.actual_value is not None:
            self.deviation_percentage = ((self.actual_value - self.threshold_value) / self.threshold_value) * 100
        return self.deviation_percentage

    def acknowledge(self, acknowledged_by: str):
        """Acknowledge the alert."""
        self.status = "acknowledged"
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = acknowledged_by

    def resolve(self, resolution_notes: str):
        """Resolve the alert."""
        self.status = "resolved"
        self.resolved_at = datetime.utcnow()
        self.resolution_notes = resolution_notes

    def escalate(self, new_severity: PriorityLevel):
        """Escalate alert to higher severity."""
        self.severity = new_severity
        # Could trigger additional notifications here


class DuplicateType(str, enum.Enum):
    """Types of duplicates for evidence harness."""

    EXACT = "exact"
    AMOUNT_SHIFT = "amount_shift"
    DATE_SHIFT = "date_shift"
    FORMAT_CHANGE = "format_change"
    VENDOR_VARIATION = "vendor_variation"
    INVOICE_NUMBER_VARIATION = "invoice_number_variation"


class ExceptionScenarioType(str, enum.Enum):
    """Types of exception scenarios for evidence harness."""

    MATH_ERROR = "math_error"
    DUPLICATE_PAYMENT = "duplicate_payment"
    MATCHING_FAILURE = "matching_failure"
    VENDOR_POLICY_VIOLATION = "vendor_policy_violation"
    DATA_QUALITY = "data_quality"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FORMAT = "invalid_format"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"


class SeedDuplicateRecord(Base, UUIDMixin, TimestampMixin):
    """Seed duplicate records for training and testing."""

    __tablename__ = "seed_duplicate_records"

    # Base invoice reference
    base_invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False, index=True)
    duplicate_invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False, index=True)

    # Duplicate classification
    duplicate_type = Column(Enum(DuplicateType), nullable=False, index=True)
    confidence_score = Column(Numeric(5, 2), nullable=True)  # 0-100 confidence

    # Duplicate variations
    variation_details = Column(JSON, nullable=True)  # Specific changes made
    similarity_score = Column(Numeric(5, 2), nullable=True)  # 0-100 similarity
    working_capital_impact = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))

    # Detection metadata
    detection_method = Column(String(50), nullable=True)  # hash, fuzzy, business_rules, etc.
    detection_confidence = Column(Numeric(5, 2), nullable=True)
    false_positive_risk = Column(Numeric(5, 2), nullable=True)

    # Training data quality
    is_labeled = Column(Boolean, nullable=False, default=False)
    labeled_by = Column(String(100), nullable=True)
    labeled_at = Column(DateTime(timezone=True), nullable=True)
    validation_status = Column(String(20), nullable=False, default="pending")  # pending, validated, rejected

    # Scenario metadata
    scenario_name = Column(String(200), nullable=True)
    scenario_description = Column(Text, nullable=True)
    difficulty_level = Column(String(20), nullable=True)  # easy, medium, hard
    business_context = Column(JSON, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_seed_duplicate_base', 'base_invoice_id', 'duplicate_type'),
        Index('idx_seed_duplicate_confidence', 'confidence_score', 'duplicate_type'),
        Index('idx_seed_duplicate_impact', 'working_capital_impact', 'duplicate_type'),
        Index('idx_seed_duplicate_validation', 'validation_status', 'is_labeled'),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name='check_duplicate_confidence_range'),
        CheckConstraint("similarity_score >= 0 AND similarity_score <= 100", name='check_similarity_range'),
        CheckConstraint("detection_confidence >= 0 AND detection_confidence <= 100", name='check_detection_confidence_range'),
        CheckConstraint("false_positive_risk >= 0 AND false_positive_risk <= 100", name='check_false_positive_risk_range'),
    )

    # Relationships
    base_invoice = relationship("ARInvoice", foreign_keys=[base_invoice_id], backref="base_duplicates")
    duplicate_invoice = relationship("ARInvoice", foreign_keys=[duplicate_invoice_id], backref="duplicate_instances")

    def __repr__(self):
        return f"<SeedDuplicateRecord(base={self.base_invoice_id}, type={self.duplicate_type}, impact=${self.working_capital_impact})>"

    def calculate_working_capital_impact(self, base_amount: Decimal, duplicate_amount: Decimal):
        """Calculate working capital impact of potential duplicate payment."""
        impact = abs(duplicate_amount - base_amount)
        self.working_capital_impact = impact
        return impact

    def validate_duplicate(self, validator: str, is_valid_duplicate: bool, notes: str = None):
        """Validate duplicate record."""
        self.is_labeled = True
        self.labeled_by = validator
        self.labeled_at = datetime.utcnow()
        self.validation_status = "validated" if is_valid_duplicate else "rejected"

        if notes:
            if not self.business_context:
                self.business_context = {}
            self.business_context['validation_notes'] = notes


class SeedExceptionRecord(Base, UUIDMixin, TimestampMixin):
    """Seed exception records for training and testing."""

    __tablename__ = "seed_exception_records"

    # Invoice reference
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False, index=True)

    # Exception classification
    exception_type = Column(Enum(ExceptionScenarioType), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical

    # Exception details
    exception_details = Column(JSON, nullable=False)  # Detailed exception information
    detection_rules = Column(JSON, nullable=True)  # Rules that triggered detection
    business_impact = Column(JSON, nullable=True)  # Business impact assessment

    # Working capital impact
    financial_impact = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    resolution_cost = Column(Numeric(15, 2), nullable=True)
    opportunity_cost = Column(Numeric(15, 2), nullable=True)

    # CFO-relevant insights
    cfo_insights = Column(JSON, nullable=True)  # Executive-level insights
    risk_assessment = Column(JSON, nullable=True)  # Financial risk assessment
    working_capital_implications = Column(JSON, nullable=True)  # WC implications

    # Training data quality
    is_labeled = Column(Boolean, nullable=False, default=False)
    labeled_by = Column(String(100), nullable=True)
    labeled_at = Column(DateTime(timezone=True), nullable=True)
    validation_status = Column(String(20), nullable=False, default="pending")  # pending, validated, rejected

    # Scenario metadata
    scenario_name = Column(String(200), nullable=True)
    scenario_description = Column(Text, nullable=True)
    occurrence_frequency = Column(String(20), nullable=True)  # rare, occasional, frequent
    resolution_complexity = Column(String(20), nullable=True)  # simple, moderate, complex

    # Performance tracking
    resolution_time_hours = Column(Integer, nullable=True)
    resolution_success_rate = Column(Numeric(5, 2), nullable=True)  # 0-100 success rate
    repeat_occurrence = Column(Boolean, nullable=False, default=False)

    # Performance indexes
    __table_args__ = (
        Index('idx_seed_exception_invoice', 'invoice_id', 'exception_type'),
        Index('idx_seed_exception_severity', 'severity', 'validation_status'),
        Index('idx_seed_exception_impact', 'financial_impact', 'exception_type'),
        Index('idx_seed_exception_frequency', 'occurrence_frequency', 'resolution_complexity'),
        CheckConstraint("financial_impact >= -1000000", name='check_financial_impact_range'),
        CheckConstraint("resolution_cost >= 0", name='check_resolution_cost_positive'),
        CheckConstraint("opportunity_cost >= 0", name='check_opportunity_cost_positive'),
        CheckConstraint("resolution_time_hours >= 0", name='check_resolution_time_positive'),
        CheckConstraint("resolution_success_rate >= 0 AND resolution_success_rate <= 100", name='check_success_rate_range'),
    )

    # Relationships
    invoice = relationship("ARInvoice", backref="seed_exceptions")

    def __repr__(self):
        return f"<SeedExceptionRecord(invoice={self.invoice_id}, type={self.exception_type}, impact=${self.financial_impact})>"

    def calculate_total_impact(self) -> Decimal:
        """Calculate total financial impact including resolution and opportunity costs."""
        total = abs(self.financial_impact)
        if self.resolution_cost:
            total += self.resolution_cost
        if self.opportunity_cost:
            total += self.opportunity_cost
        return total

    def generate_cfo_insights(self):
        """Generate CFO-relevant insights for the exception."""
        insights = {
            'financial_summary': {
                'direct_impact': float(abs(self.financial_impact)),
                'total_cost': float(self.calculate_total_impact()),
                'working_capital_tied_up': float(abs(self.financial_impact))
            },
            'risk_assessment': {
                'severity': self.severity,
                'frequency': self.occurrence_frequency,
                'complexity': self.resolution_complexity,
                'repeat_issue': self.repeat_occurrence
            },
            'operational_impact': {
                'resolution_time_hours': self.resolution_time_hours,
                'success_rate': float(self.resolution_success_rate) if self.resolution_success_rate else None,
                'department_responsibility': self._get_responsible_department()
            },
            'strategic_recommendations': self._generate_strategic_recommendations()
        }

        self.cfo_insights = insights
        return insights

    def _get_responsible_department(self) -> str:
        """Determine responsible department based on exception type."""
        department_mapping = {
            ExceptionScenarioType.MATH_ERROR: "Finance",
            ExceptionScenarioType.DUPLICATE_PAYMENT: "AP Operations",
            ExceptionScenarioType.MATCHING_FAILURE: "Procurement",
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: "Vendor Management",
            ExceptionScenarioType.DATA_QUALITY: "Data Management",
            ExceptionScenarioType.MISSING_REQUIRED_FIELD: "AP Operations",
            ExceptionScenarioType.INVALID_FORMAT: "Technical Support",
            ExceptionScenarioType.BUSINESS_RULE_VIOLATION: "Compliance"
        }
        return department_mapping.get(self.exception_type, "Unknown")

    def _generate_strategic_recommendations(self) -> List[str]:
        """Generate strategic recommendations based on exception type."""
        recommendations = {
            ExceptionScenarioType.MATH_ERROR: [
                "Implement automated calculation validation",
                "Add pre-processing verification checks",
                "Train staff on calculation verification"
            ],
            ExceptionScenarioType.DUPLICATE_PAYMENT: [
                "Enhance duplicate detection algorithms",
                "Implement real-time duplicate checking",
                "Establish vendor portal for duplicate verification"
            ],
            ExceptionScenarioType.MATCHING_FAILURE: [
                "Improve PO matching logic",
                "Implement three-way matching automation",
                "Establish vendor communication protocols"
            ],
            ExceptionScenarioType.VENDOR_POLICY_VIOLATION: [
                "Update vendor onboarding procedures",
                "Implement policy compliance checks",
                "Regular vendor policy reviews"
            ],
            ExceptionScenarioType.DATA_QUALITY: [
                "Implement data quality monitoring",
                "Add data validation rules",
                "Regular data cleansing procedures"
            ]
        }
        return recommendations.get(self.exception_type, ["Review and improve current processes"])

    def validate_exception(self, validator: str, is_valid_exception: bool, resolution_cost: Decimal = None, notes: str = None):
        """Validate exception record."""
        self.is_labeled = True
        self.labeled_by = validator
        self.labeled_at = datetime.utcnow()
        self.validation_status = "validated" if is_valid_exception else "rejected"

        if resolution_cost:
            self.resolution_cost = resolution_cost

        if notes:
            if not self.business_impact:
                self.business_impact = {}
            self.business_impact['validation_notes'] = notes

        # Regenerate CFO insights with updated information
        self.generate_cfo_insights()


class EvidenceHarnessJob(Base, UUIDMixin, TimestampMixin):
    """Evidence harness generation job tracking."""

    __tablename__ = "evidence_harness_jobs"

    # Job information
    job_name = Column(String(200), nullable=False)
    job_type = Column(String(50), nullable=False, index=True)  # duplicate_generation, exception_generation
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, running, completed, failed

    # Job parameters
    target_count = Column(Integer, nullable=False)
    parameters = Column(JSON, nullable=True)  # Generation parameters

    # Job results
    generated_count = Column(Integer, nullable=False, default=0)
    validated_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)

    # Quality metrics
    average_quality_score = Column(Numeric(5, 2), nullable=True)  # 0-100 average quality
    diversity_score = Column(Numeric(5, 2), nullable=True)  # Scenario diversity measure
    coverage_score = Column(Numeric(5, 2), nullable=True)  # Coverage of scenario types

    # Execution tracking
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_harness_job_type_status', 'job_type', 'status'),
        Index('idx_harness_job_quality', 'average_quality_score', 'status'),
        Index('idx_harness_job_coverage', 'coverage_score', 'job_type'),
        CheckConstraint("target_count >= 0", name='check_target_count_positive'),
        CheckConstraint("generated_count >= 0", name='check_generated_count_positive'),
        CheckConstraint("validated_count >= 0", name='check_validated_count_positive'),
        CheckConstraint("failed_count >= 0", name='check_failed_count_positive'),
        CheckConstraint("average_quality_score >= 0 AND average_quality_score <= 100", name='check_avg_quality_range'),
        CheckConstraint("diversity_score >= 0 AND diversity_score <= 100", name='check_diversity_range'),
        CheckConstraint("coverage_score >= 0 AND coverage_score <= 100", name='check_coverage_range'),
        CheckConstraint("execution_time_seconds >= 0", name='check_execution_time_positive'),
    )

    def __repr__(self):
        return f"<EvidenceHarnessJob(name={self.job_name}, type={self.job_type}, status={self.status})>"

    def start_job(self):
        """Mark job as started."""
        self.status = "running"
        self.started_at = datetime.utcnow()

    def complete_job(self, success: bool = True, error_message: str = None):
        """Mark job as completed."""
        self.status = "completed" if success else "failed"
        self.completed_at = datetime.utcnow()

        if self.started_at:
            self.execution_time_seconds = int((self.completed_at - self.started_at).total_seconds())

        if error_message:
            self.error_message = error_message

    def update_progress(self, generated: int = None, validated: int = None, failed: int = None):
        """Update job progress."""
        if generated is not None:
            self.generated_count = generated
        if validated is not None:
            self.validated_count = validated
        if failed is not None:
            self.failed_count = failed

    def calculate_completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.target_count == 0:
            return 0.0
        return min(100.0, (self.generated_count / self.target_count) * 100)