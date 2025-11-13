"""
Exception Explainability Service for CFO-level exception insights.

This service provides AI-powered exception explanations, financial impact assessment,
cash flow implications analysis, executive summary generation, and recommended actions
with business impact for CFO-level decision making.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.api.schemas.validation import ValidationIssue, ValidationSeverity
from app.api.schemas.exception import (
    ExceptionCategory,
    ExceptionSeverity,
    ExceptionResponse,
    CFOGrade,
    BusinessPriority,
    FinancialMateriality,
    WorkingCapitalImpact
)
from app.models.invoice import Invoice, Exception as ExceptionModel
from app.models.reference import Vendor
from app.services.working_capital_analytics import WorkingCapitalAnalytics
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk assessment levels for exceptions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImpactTimeframe(str, Enum):
    """Timeframe for impact assessment."""
    IMMEDIATE = "immediate"  # 0-7 days
    SHORT_TERM = "short_term"  # 8-30 days
    MEDIUM_TERM = "medium_term"  # 31-90 days
    LONG_TERM = "long_term"  # 90+ days


class ActionUrgency(str, Enum):
    """Action urgency levels."""
    URGENT = "urgent"  # Action required within 24 hours
    HIGH = "high"  # Action required within 3 days
    MEDIUM = "medium"  # Action required within 7 days
    LOW = "low"  # Action required within 30 days


class ExceptionExplainabilityService:
    """
    AI-powered exception explainability service for CFO-level insights.

    This service translates technical exceptions into business impacts and
    provides actionable recommendations for executive decision making.
    """

    def __init__(self):
        """Initialize the exception explainability service."""
        self.cost_of_capital = Decimal('0.08')  # 8% annual cost of capital
        self.working_capital_analytics = None

    async def generate_exception_insight(
        self,
        exception_id: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive CFO-level exception insights.

        This method provides executive-level analysis including financial impact,
        working capital implications, risk assessment, and actionable recommendations.
        """
        logger.info(f"Generating CFO-level insights for exception {exception_id}")

        if session is None:
            async with AsyncSessionLocal() as session:
                return await self._generate_comprehensive_insight(exception_id, session)
        else:
            return await self._generate_comprehensive_insight(exception_id, session)

    async def _generate_comprehensive_insight(
        self,
        exception_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Generate comprehensive exception insight."""
        # Get exception details
        query = select(ExceptionModel).where(ExceptionModel.id == uuid.UUID(exception_id))
        result = await session.execute(query)
        exception = result.scalar_one_or_none()

        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        # Get invoice details
        invoice_query = select(Invoice).where(Invoice.id == exception.invoice_id)
        invoice_result = await session.execute(invoice_query)
        invoice = invoice_result.scalar_one_or_none()

        # Parse exception details
        exception_details = exception.details_json or {}
        category = ExceptionCategory(exception_details.get('category', 'DATA_QUALITY'))
        severity = ExceptionSeverity(exception_details.get('severity', 'ERROR'))

        # Generate comprehensive analysis
        insight = {
            "exception_summary": await self._generate_exception_summary(exception, invoice, category, severity),
            "executive_summary": await self._generate_executive_summary(exception, invoice, category, severity),
            "financial_impact_assessment": await self._assess_financial_impact(exception, invoice, category, severity),
            "working_capital_implications": await self._analyze_working_capital_impact(exception, invoice, category, severity),
            "cash_flow_analysis": await self._analyze_cash_flow_impact(exception, invoice, category, severity),
            "risk_assessment": await self._assess_business_risk(exception, invoice, category, severity),
            "operational_impact": await self._assess_operational_impact(exception, invoice, category, severity),
            "recommended_actions": await self._generate_executive_recommendations(exception, invoice, category, severity),
            "business_metrics": await self._calculate_business_metrics(exception, invoice, category, severity),
            "investment_justification": await self._generate_investment_justification(exception, invoice, category, severity),
            "cfo_grade_details": await self._generate_cfo_grade_details(exception, invoice, category, severity)
        }

        return insight

    async def _generate_exception_summary(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate high-level exception summary for executives."""
        return {
            "exception_id": str(exception.id),
            "exception_type": category.value,
            "severity_level": severity.value,
            "business_impact_level": self._determine_business_impact_level(category, severity),
            "invoice_details": {
                "invoice_id": str(exception.invoice_id),
                "invoice_amount": float(invoice.total_amount) if invoice else 0,
                "vendor_name": "Unknown Vendor",  # Would get from vendor relationship
                "invoice_date": invoice.invoice_date.isoformat() if invoice else None,
                "days_open": (datetime.utcnow() - exception.created_at).days
            },
            "key_takeaway": self._generate_key_takeaway(category, severity),
            "attention_required": self._determine_attention_level(category, severity)
        }

    async def _generate_executive_summary(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate executive summary for CFO consumption."""
        invoice_amount = Decimal(str(invoice.total_amount)) if invoice else Decimal('0')

        return {
            "one_line_summary": self._create_one_line_summary(category, severity, invoice_amount),
            "financial_exposure": self._assess_financial_exposure(category, severity, invoice_amount),
            "strategic_implications": self._assess_strategic_implications(category, severity),
            "immediate_action_required": self._determine_immediate_action_requirement(category, severity),
            "board_level_visibility": self._assess_board_visibility(category, severity),
            "confidence_level": self._calculate_confidence_level(category, severity),
            "executive_briefing": self._create_executive_briefing(category, severity, invoice_amount)
        }

    async def _assess_financial_impact(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Assess comprehensive financial impact."""
        invoice_amount = Decimal(str(invoice.total_amount)) if invoice else Decimal('0')

        # Calculate direct financial impacts
        potential_loss = await self._calculate_potential_financial_loss(category, severity, invoice_amount)
        working_capital_cost = await self._calculate_working_capital_cost(category, severity, invoice_amount)
        resolution_cost = await self._estimate_resolution_cost(category, severity)

        # Calculate indirect impacts
        operational_disruption_cost = await self._estimate_operational_disruption_cost(category, severity)
        customer_relationship_impact = await self._assess_customer_relationship_impact(category, severity)
        compliance_risk_cost = await self._assess_compliance_risk_cost(category, severity)

        total_financial_impact = (
            potential_loss + working_capital_cost + resolution_cost +
            operational_disruption_cost + customer_relationship_impact + compliance_risk_cost
        )

        return {
            "total_estimated_impact": float(total_financial_impact),
            "direct_impacts": {
                "potential_loss": float(potential_loss),
                "working_capital_cost": float(working_capital_cost),
                "resolution_cost": float(resolution_cost)
            },
            "indirect_impacts": {
                "operational_disruption": float(operational_disruption_cost),
                "customer_relationship": float(customer_relationship_impact),
                "compliance_risk": float(compliance_risk_cost)
            },
            "impact_breakdown_percentage": self._calculate_impact_percentages(
                potential_loss, working_capital_cost, resolution_cost,
                operational_disruption_cost, customer_relationship_impact, compliance_risk_cost
            ),
            "financial_materiality": self._assess_financial_materiality(total_financial_impact),
            "budget_impact": self._assess_budget_impact(total_financial_impact),
            "earnings_impact": self._assess_earnings_impact(total_financial_impact)
        }

    async def _analyze_working_capital_impact(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Analyze working capital implications."""
        invoice_amount = Decimal(str(invoice.total_amount)) if invoice else Decimal('0')

        # Calculate working capital metrics
        cash_flow_impact = await self._calculate_cash_flow_impact(category, severity, invoice_amount)
        days_payable_impact = await self._calculate_days_payable_impact(category, severity)
        inventory_impact = await self._calculate_inventory_impact(category, severity)
        receivables_impact = await self._calculate_receivables_impact(category, severity, invoice_amount)

        # Calculate efficiency metrics
        working_capital_turnover_impact = await self._assess_turnover_impact(category, severity)
        cash_conversion_cycle_impact = await self._assess_conversion_cycle_impact(category, severity)

        return {
            "overall_wc_impact": self._assess_overall_wc_impact(category, severity),
            "cash_flow_effects": {
                "immediate_impact": float(cash_flow_impact),
                "30_day_impact": float(cash_flow_impact * 1.2),
                "90_day_impact": float(cash_flow_impact * 1.5)
            },
            "efficiency_metrics": {
                "days_payable_impact": days_payable_impact,
                "inventory_turnover_impact": inventory_impact,
                "receivables_turnover_impact": receivables_impact,
                "working_capital_turnover_impact": working_capital_turnover_impact,
                "cash_conversion_cycle_impact": cash_conversion_cycle_impact
            },
            "capital_allocation": {
                "additional_capital_required": float(cash_flow_impact),
                "opportunity_cost": float(cash_flow_impact * Decimal('0.08') / Decimal('365') * Decimal('30')),
                "cost_of_capital_impact": float(cash_flow_impact * self.cost_of_capital / Decimal('365') * Decimal('30'))
            },
            "optimization_opportunities": self._identify_wc_optimization_opportunities(category, severity)
        }

    async def _analyze_cash_flow_impact(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Analyze cash flow implications."""
        invoice_amount = Decimal(str(invoice.total_amount)) if invoice else Decimal('0')

        # Calculate cash flow timing impacts
        payment_delay_days = await self._estimate_payment_delay(category, severity)
        delayed_amount = await self._calculate_delayed_amount(category, severity, invoice_amount)

        # Calculate forecast accuracy impact
        forecast_variance = await self._calculate_forecast_variance(category, severity, invoice_amount)

        # Calculate liquidity impact
        liquidity_impact = await self._assess_liquidity_impact(category, severity, delayed_amount)

        return {
            "immediate_cash_flow_impact": float(delayed_amount),
            "timing_analysis": {
                "estimated_delay_days": payment_delay_days,
                "delayed_receipt_amount": float(delayed_amount),
                "daily_cash_flow_impact": float(delayed_amount / max(1, payment_delay_days))
            },
            "forecast_impact": {
                "forecast_variance": float(forecast_variance),
                "forecast_confidence_reduction": self._assess_forecast_confidence_reduction(category, severity),
                "reforecast_required": self._determine_reforecast_requirement(category, severity)
            },
            "liquidity_analysis": {
                "liquidity_impact_score": liquidity_impact,
                "covenant_compliance_risk": self._assess_covenant_compliance_risk(category, severity),
                "buffer_utilization": self._assess_buffer_utilization(category, severity, delayed_amount)
            },
            "cash_flow_planning": {
                "short_term_adjustment_required": float(delayed_amount),
                "medium_term_reprojection_needed": payment_delay_days > 30,
                "capital_allocation_impact": self._assess_capital_allocation_impact(category, severity)
            }
        }

    async def _assess_business_risk(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Assess comprehensive business risk."""
        return {
            "overall_risk_level": self._determine_overall_risk_level(category, severity),
            "risk_categories": {
                "financial_risk": await self._assess_financial_risk(category, severity),
                "operational_risk": await self._assess_operational_risk(category, severity),
                "compliance_risk": await self._assess_compliance_risk(category, severity),
                "reputational_risk": await self._assess_reputational_risk(category, severity),
                "strategic_risk": await self._assess_strategic_risk_category(category, severity)
            },
            "risk_mitigation": {
                "immediate_actions": self._identify_immediate_risk_mitigation(category, severity),
                "monitoring_requirements": self._identify_monitoring_requirements(category, severity),
                "escalation_triggers": self._define_escalation_triggers(category, severity)
            },
            "risk_timeline": {
                "immediate_risks": self._identify_immediate_risks(category, severity),
                "emerging_risks": self._identify_emerging_risks(category, severity),
                "long_term_risks": self._identify_long_term_risks(category, severity)
            },
            "risk_tolerance_assessment": {
                "current_risk_vs_tolerance": self._assess_risk_tolerance(category, severity),
                "risk_appetite_impact": self._assess_risk_appetite_impact(category, severity),
                "board_reporting_required": self._determine_board_reporting_requirement(category, severity)
            }
        }

    async def _assess_operational_impact(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Assess operational impact of exception."""
        return {
            "departmental_impact": {
                "accounts_payable": self._assess_ap_impact(category, severity),
                "procurement": self._assess_procurement_impact(category, severity),
                "finance": self._assess_finance_impact(category, severity),
                "operations": self._assess_operations_impact(category, severity),
                "legal_compliance": self._assess_legal_impact(category, severity)
            },
            "process_impact": {
                "workflow_disruption": self._assess_workflow_disruption(category, severity),
                "approval_process_impact": self._assess_approval_process_impact(category, severity),
                "system_integration_impact": self._assess_system_integration_impact(category, severity),
                "reporting_timeline_impact": self._assess_reporting_impact(category, severity)
            },
            "resource_impact": {
                "staff_time_required": await self._estimate_staff_time_impact(category, severity),
                "management_attention_required": self._assess_management_attention_impact(category, severity),
                "external_consultant_needed": self._assess_consultant_need(category, severity),
                "training_requirements": self._identify_training_requirements(category, severity)
            },
            "performance_metrics": {
                "kpi_impact": self._assess_kpi_impact(category, severity),
                "sla_compliance_impact": self._assess_sla_impact(category, severity),
                "productivity_impact": self._assess_productivity_impact(category, severity)
            }
        }

    async def _generate_executive_recommendations(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate executive-level recommendations."""
        return {
            "immediate_actions": {
                "urgency_level": self._determine_action_urgency(category, severity),
                "required_actions": await self._identify_immediate_actions(category, severity),
                "responsible_parties": self._assign_responsibility(category, severity),
                "timeline": self._establish_immediate_timeline(category, severity),
                "resource_requirements": self._identify_resource_requirements(category, severity)
            },
            "strategic_initiatives": {
                "short_term_initiatives": await self._identify_short_term_initiatives(category, severity),
                "medium_term_initiatives": await self._identify_medium_term_initiatives(category, severity),
                "long_term_initiatives": await self._identify_long_term_initiatives(category, severity),
                "investment_priorities": self._prioritize_investments(category, severity),
                "expected_roi": await self._calculate_initiative_roi(category, severity)
            },
            "process_improvements": {
                "quick_wins": self._identify_quick_wins(category, severity),
                "system_enhancements": self._identify_system_enhancements(category, severity),
                "policy_updates": self._identify_required_policy_updates(category, severity),
                "control_improvements": self._identify_control_improvements(category, severity)
            },
            "monitoring_and_reporting": {
                "key_metrics_to_monitor": self._identify_monitoring_metrics(category, severity),
                "reporting_frequency": self._establish_reporting_frequency(category, severity),
                "escalation_criteria": self._define_escalation_criteria(category, severity),
                "success_metrics": self._define_success_metrics(category, severity)
            }
        }

    async def _calculate_business_metrics(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Calculate relevant business metrics."""
        return {
            "financial_metrics": {
                "roi_on_resolution": await self._calculate_resolution_roi(category, severity),
                "cost_benefit_ratio": await self._calculate_cost_benefit_ratio(category, severity),
                "payback_period": await self._calculate_payback_period(category, severity),
                "npv_impact": await self._calculate_npv_impact(category, severity)
            },
            "operational_metrics": {
                "efficiency_loss": await self._calculate_efficiency_loss(category, severity),
                "productivity_impact": await self._calculate_productivity_impact(category, severity),
                "quality_impact": await self._calculate_quality_impact(category, severity),
                "cycle_time_impact": await self._calculate_cycle_time_impact(category, severity)
            },
            "risk_metrics": {
                "risk_adjusted_return": await self._calculate_risk_adjusted_return(category, severity),
                "var_impact": await self._calculate_var_impact(category, severity),
                "compliance_score_impact": await self._calculate_compliance_score_impact(category, severity),
                "audit_risk_increase": await self._calculate_audit_risk_increase(category, severity)
            },
            "benchmark_comparison": {
                "industry_benchmark": await self._get_industry_benchmark(category),
                "company_performance": await self._assess_company_performance(category, severity),
                "competitive_position": await self._assess_competitive_position(category, severity),
                "improvement_potential": await self._calculate_improvement_potential(category, severity)
            }
        }

    async def _generate_investment_justification(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate investment justification for addressing exceptions."""
        return {
            "financial_justification": {
                "total_investment_required": await self._calculate_total_investment(category, severity),
                "expected_annual_savings": await self._calculate_annual_savings(category, severity),
                "roi_percentage": await self._calculate_roi_percentage(category, severity),
                "payback_period_months": await self._calculate_payback_months(category, severity),
                "irr": await self._calculate_internal_rate_of_return(category, severity)
            },
            "business_case": {
                "strategic_alignment": self._assess_strategic_alignment(category, severity),
                "competitive_advantage": self._assess_competitive_advantage(category, severity),
                "risk_mitigation_value": self._assess_risk_mitigation_value(category, severity),
                "operational_excellence": self._assess_operational_excellence_value(category, severity)
            },
            "implementation_plan": {
                "phased_approach": self._design_phased_approach(category, severity),
                "critical_success_factors": self._identify_critical_success_factors(category, severity),
                "risk_mitigation_plan": self._create_risk_mitigation_plan(category, severity),
                "resource_allocation": self._plan_resource_allocation(category, severity)
            },
            "alternative_analysis": {
                "do_nothing_scenario": await self._analyze_do_nothing_scenario(category, severity),
                "minimal_intervention": await self._analyze_minimal_intervention(category, severity),
                "comprehensive_solution": await self._analyze_comprehensive_solution(category, severity),
                "recommended_approach": self._recommend_approach(category, severity)
            }
        }

    async def _generate_cfo_grade_details(
        self,
        exception: ExceptionModel,
        invoice: Optional[Invoice],
        category: ExceptionCategory,
        severity: ExceptionSeverity
    ) -> Dict[str, Any]:
        """Generate detailed CFO grading information."""
        return {
            "cfo_grade": self._assign_cfo_grade(category, severity),
            "grade_justification": self._justify_cfo_grade(category, severity),
            "business_priority": self._assign_business_priority(category, severity),
            "financial_materiality": self._assess_financial_materiality_level(category, severity),
            "working_capital_impact": self._assess_working_capital_impact_level(category, severity),
            "escalation_requirements": self._define_escalation_requirements(category, severity),
            "board_reporting": self._determine_board_reporting_needs(category, severity),
            "investor_communication": self._assess_investor_communication_needs(category, severity)
        }

    # Helper methods for generating insights

    def _determine_business_impact_level(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Determine business impact level."""
        impact_matrix = {
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.ERROR): "critical",
            (ExceptionCategory.DUPLICATE, ExceptionSeverity.WARNING): "high",
            (ExceptionCategory.MATH, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.MATH, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.MATCHING, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.MATCHING, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.ERROR): "high",
            (ExceptionCategory.VENDOR_POLICY, ExceptionSeverity.WARNING): "medium",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.ERROR): "medium",
            (ExceptionCategory.DATA_QUALITY, ExceptionSeverity.WARNING): "low",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.ERROR): "medium",
            (ExceptionCategory.SYSTEM, ExceptionSeverity.WARNING): "low",
        }
        return impact_matrix.get((category, severity), "low")

    def _generate_key_takeaway(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Generate key takeaway for executives."""
        takeaways = {
            ExceptionCategory.DUPLICATE: "Potential duplicate payment requiring immediate investigation",
            ExceptionCategory.MATH: "Calculation discrepancy that may lead to overpayment",
            ExceptionCategory.MATCHING: "Document matching issue affecting payment timing",
            ExceptionCategory.VENDOR_POLICY: "Policy compliance violation requiring review",
            ExceptionCategory.DATA_QUALITY: "Data quality issue impacting processing efficiency",
            ExceptionCategory.SYSTEM: "System error requiring technical intervention"
        }
        base_takeaway = takeaways.get(category, "Exception requiring attention and resolution")

        if severity == ExceptionSeverity.ERROR:
            return f"CRITICAL: {base_takeaway}"
        else:
            return base_takeaway

    def _determine_attention_level(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Determine attention level required."""
        if severity == ExceptionSeverity.ERROR:
            if category in [ExceptionCategory.DUPLICATE, ExceptionCategory.MATCHING]:
                return "Immediate executive attention required"
            else:
                return "Senior management attention required"
        else:
            return "Operational management attention required"

    def _create_one_line_summary(self, category: ExceptionCategory, severity: ExceptionSeverity, amount: Decimal) -> str:
        """Create one-line executive summary."""
        category_labels = {
            ExceptionCategory.DUPLICATE: "duplicate payment risk",
            ExceptionCategory.MATH: "calculation error",
            ExceptionCategory.MATCHING: "document matching failure",
            ExceptionCategory.VENDOR_POLICY: "policy violation",
            ExceptionCategory.DATA_QUALITY: "data quality issue",
            ExceptionCategory.SYSTEM: "system processing error"
        }

        issue = category_labels.get(category, "exception")
        amount_str = f" ${float(amount):,.2f}" if amount > 0 else ""

        return f"{severity.value.title()} {issue}{amount_str} requiring immediate attention and resolution"

    async def _assess_financial_exposure(self, category: ExceptionCategory, severity: ExceptionSeverity, amount: Decimal) -> Dict[str, Any]:
        """Assess financial exposure."""
        exposure_percentages = {
            ExceptionCategory.DUPLICATE: 1.0,  # 100% exposure
            ExceptionCategory.MATH: 0.15,      # 15% exposure
            ExceptionCategory.MATCHING: 0.08,  # 8% exposure
            ExceptionCategory.VENDOR_POLICY: 0.05,  # 5% exposure
            ExceptionCategory.DATA_QUALITY: 0.02,   # 2% exposure
            ExceptionCategory.SYSTEM: 0.03,    # 3% exposure
        }

        base_percentage = exposure_percentages.get(category, 0.02)
        severity_multiplier = 1.5 if severity == ExceptionSeverity.ERROR else 1.0

        estimated_exposure = amount * Decimal(str(base_percentage)) * Decimal(str(severity_multiplier))

        return {
            "estimated_exposure_amount": float(estimated_exposure),
            "exposure_as_percentage_of_invoice": float(base_percentage * 100 * severity_multiplier),
            "confidence_level": "high" if category == ExceptionCategory.DUPLICATE else "medium",
            "time_horizon": "immediate" if category == ExceptionCategory.DUPLICATE else "short_term"
        }

    def _assess_strategic_implications(self, category: ExceptionCategory, severity: ExceptionSeverity) -> List[str]:
        """Assess strategic implications."""
        implications = {
            ExceptionCategory.DUPLICATE: [
                "Internal control weakness requiring immediate attention",
                "Potential for systemic duplicate payment issues",
                "Vendor relationship impact possible",
                "Audit and compliance scrutiny likely"
            ],
            ExceptionCategory.MATH: [
                "Process validation weaknesses identified",
                "Training needs for staff potentially required",
                "System validation rules may need enhancement"
            ],
            ExceptionCategory.MATCHING: [
                "Procurement-to-pay process gaps identified",
                "System integration issues may exist",
                "Vendor payment terms may need review"
            ],
            ExceptionCategory.VENDOR_POLICY: [
                "Vendor management process weaknesses",
                "Compliance framework gaps identified",
                "Policy enforcement mechanisms need review"
            ],
            ExceptionCategory.DATA_QUALITY: [
                "Data governance issues identified",
                "Automation maturity may be insufficient",
                "Quality control processes need enhancement"
            ],
            ExceptionCategory.SYSTEM: [
                "Technology infrastructure limitations",
                "System reliability concerns raised",
                "Business continuity planning needed"
            ]
        }

        return implications.get(category, ["Operational impact requiring attention"])

    def _determine_immediate_action_requirement(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Dict[str, Any]:
        """Determine immediate action requirements."""
        if category == ExceptionCategory.DUPLICATE and severity == ExceptionSeverity.ERROR:
            return {
                "action_required": True,
                "urgency": "immediate",
                "deadline_hours": 24,
                "escalation_level": "executive",
                "justification": "Prevent potential duplicate payment"
            }
        elif severity == ExceptionSeverity.ERROR:
            return {
                "action_required": True,
                "urgency": "high",
                "deadline_hours": 72,
                "escalation_level": "management",
                "justification": "Prevent financial and operational impact"
            }
        else:
            return {
                "action_required": True,
                "urgency": "medium",
                "deadline_hours": 168,  # 1 week
                "escalation_level": "operational",
                "justification": "Maintain operational efficiency"
            }

    def _assess_board_visibility(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Dict[str, Any]:
        """Assess board-level visibility requirements."""
        if category == ExceptionCategory.DUPLICATE and severity == ExceptionSeverity.ERROR:
            return {
                "board_reporting_required": True,
                "visibility_level": "high",
                "reporting_frequency": "immediate",
                "agenda_item": "Financial Control Review"
            }
        elif severity == ExceptionSeverity.ERROR and category in [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]:
            return {
                "board_reporting_required": True,
                "visibility_level": "medium",
                "reporting_frequency": "quarterly",
                "agenda_item": "Risk Management Update"
            }
        else:
            return {
                "board_reporting_required": False,
                "visibility_level": "low",
                "reporting_frequency": None,
                "agenda_item": None
            }

    def _calculate_confidence_level(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Calculate confidence level in assessment."""
        high_confidence_categories = [ExceptionCategory.DUPLICATE, ExceptionCategory.MATH]
        medium_confidence_categories = [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]

        if category in high_confidence_categories:
            return "high"
        elif category in medium_confidence_categories:
            return "medium"
        else:
            return "moderate"

    def _create_executive_briefing(self, category: ExceptionCategory, severity: ExceptionSeverity, amount: Decimal) -> str:
        """Create executive briefing text."""
        briefing_templates = {
            ExceptionCategory.DUPLICATE: (
                "A duplicate invoice exception has been identified requiring immediate investigation "
                "to prevent potential duplicate payment. This exception indicates a weakness in our "
                "duplicate detection controls and may have systemic implications."
            ),
            ExceptionCategory.MATH: (
                "A mathematical discrepancy has been detected in invoice calculations. While the "
                "financial impact appears contained, this exception suggests validation control "
                "weaknesses that require attention."
            ),
            ExceptionCategory.MATCHING: (
                "Document matching failures are impacting our payment processing efficiency. "
                "This exception highlights gaps in our procurement-to-pay integration that may "
                "affect vendor relationships and cash flow timing."
            ),
            ExceptionCategory.VENDOR_POLICY: (
                "Vendor policy compliance issues have been identified that require review. "
                "This exception suggests potential weaknesses in our vendor management and "
                "compliance frameworks."
            ),
            ExceptionCategory.DATA_QUALITY: (
                "Data quality issues are affecting our processing efficiency. This exception "
                "highlights the need for enhanced data validation and quality control measures."
            ),
            ExceptionCategory.SYSTEM: (
                "System processing errors have been identified that require technical intervention. "
                "This exception may indicate broader system reliability concerns that need addressing."
            )
        }

        base_briefing = briefing_templates.get(category, "An exception has been identified requiring attention.")

        if amount > Decimal('10000'):
            return f"HIGH IMPACT: {base_briefing} The financial exposure exceeds $10,000."
        elif amount > Decimal('1000'):
            return f"MODERATE IMPACT: {base_briefing} The financial exposure exceeds $1,000."
        else:
            return base_briefing

    # Additional helper methods would be implemented here...
    # For brevity, I'll include key calculation methods

    async def _calculate_potential_financial_loss(self, category: ExceptionCategory, severity: ExceptionSeverity, amount: Decimal) -> Decimal:
        """Calculate potential financial loss."""
        loss_percentages = {
            ExceptionCategory.DUPLICATE: Decimal('1.0'),   # 100%
            ExceptionCategory.MATH: Decimal('0.15'),      # 15%
            ExceptionCategory.MATCHING: Decimal('0.08'),  # 8%
            ExceptionCategory.VENDOR_POLICY: Decimal('0.05'),  # 5%
            ExceptionCategory.DATA_QUALITY: Decimal('0.02'),   # 2%
            ExceptionCategory.SYSTEM: Decimal('0.03'),    # 3%
        }

        base_percentage = loss_percentages.get(category, Decimal('0.02'))
        severity_multiplier = Decimal('1.5') if severity == ExceptionSeverity.ERROR else Decimal('1.0')

        return amount * base_percentage * severity_multiplier

    async def _calculate_working_capital_cost(self, category: ExceptionCategory, severity: ExceptionSeverity, amount: Decimal) -> Decimal:
        """Calculate working capital cost impact."""
        # Estimate days of working capital impact
        impact_days = {
            ExceptionCategory.DUPLICATE: 45,
            ExceptionCategory.MATH: 2,
            ExceptionCategory.MATCHING: 14,
            ExceptionCategory.VENDOR_POLICY: 7,
            ExceptionCategory.DATA_QUALITY: 1,
            ExceptionCategory.SYSTEM: 3,
        }

        days = impact_days.get(category, 5)
        daily_cost_of_capital = self.cost_of_capital / Decimal('365')

        return amount * daily_cost_of_capital * Decimal(days)

    async def _estimate_resolution_cost(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Decimal:
        """Estimate cost to resolve exception."""
        base_costs = {
            ExceptionCategory.DUPLICATE: Decimal('250'),
            ExceptionCategory.MATH: Decimal('50'),
            ExceptionCategory.MATCHING: Decimal('150'),
            ExceptionCategory.VENDOR_POLICY: Decimal('100'),
            ExceptionCategory.DATA_QUALITY: Decimal('25'),
            ExceptionCategory.SYSTEM: Decimal('75'),
        }

        base_cost = base_costs.get(category, Decimal('50'))
        severity_multiplier = Decimal('1.5') if severity == ExceptionSeverity.ERROR else Decimal('1.0')

        return base_cost * severity_multiplier

    async def _estimate_operational_disruption_cost(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Decimal:
        """Estimate operational disruption cost."""
        disruption_hours = {
            ExceptionCategory.DUPLICATE: 16,
            ExceptionCategory.MATH: 4,
            ExceptionCategory.MATCHING: 12,
            ExceptionCategory.VENDOR_POLICY: 8,
            ExceptionCategory.DATA_QUALITY: 2,
            ExceptionCategory.SYSTEM: 6,
        }

        hours = disruption_hours.get(category, 4)
        hourly_rate = Decimal('75')  # Average blended rate

        return Decimal(hours) * hourly_rate

    async def _assess_customer_relationship_impact(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Decimal:
        """Assess customer relationship impact cost."""
        if category in [ExceptionCategory.DUPLICATE, ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]:
            return Decimal('500') if severity == ExceptionSeverity.ERROR else Decimal('200')
        else:
            return Decimal('0')

    async def _assess_compliance_risk_cost(self, category: ExceptionCategory, severity: ExceptionSeverity) -> Decimal:
        """Assess compliance risk cost."""
        if category in [ExceptionCategory.VENDOR_POLICY, ExceptionCategory.DUPLICATE]:
            return Decimal('1000') if severity == ExceptionSeverity.ERROR else Decimal('400')
        else:
            return Decimal('100')

    def _calculate_impact_percentages(self, *impacts) -> Dict[str, float]:
        """Calculate impact as percentages of total."""
        total = sum(impacts)
        if total == 0:
            return {}

        impact_names = ['potential_loss', 'working_capital_cost', 'resolution_cost',
                       'operational_disruption', 'customer_relationship', 'compliance_risk']

        return {
            name: float((impact / total) * 100)
            for name, impact in zip(impact_names, impacts) if impact > 0
        }

    def _assess_financial_materiality(self, total_impact: Decimal) -> str:
        """Assess financial materiality level."""
        if total_impact > Decimal('100000'):
            return "material"
        elif total_impact > Decimal('10000'):
            return "moderate"
        else:
            return "immaterial"

    def _assess_budget_impact(self, total_impact: Decimal) -> str:
        """Assess budget impact."""
        if total_impact > Decimal('50000'):
            return "significant"
        elif total_impact > Decimal('5000'):
            return "moderate"
        else:
            return "minimal"

    def _assess_earnings_impact(self, total_impact: Decimal) -> str:
        """Assess earnings impact."""
        if total_impact > Decimal('100000'):
            return "material_to_earnings"
        elif total_impact > Decimal('10000'):
            return "could_impact_earnings"
        else:
            return "unlikely_to_impact_earnings"

    def _assign_cfo_grade(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Assign CFO grade."""
        if category == ExceptionCategory.DUPLICATE and severity == ExceptionSeverity.ERROR:
            return CFOGrade.CRITICAL
        elif severity == ExceptionSeverity.ERROR:
            return CFOGrade.HIGH
        elif category in [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]:
            return CFOGrade.MEDIUM
        else:
            return CFOGrade.LOW

    def _justify_cfo_grade(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Provide justification for CFO grade."""
        justifications = {
            CFOGrade.CRITICAL: "Immediate financial risk requiring executive intervention",
            CFOGrade.HIGH: "Significant operational or financial impact requiring management attention",
            CFOGrade.MEDIUM: "Moderate impact requiring process improvement",
            CFOGrade.LOW: "Minimal impact with standard resolution procedures"
        }
        grade = self._assign_cfo_grade(category, severity)
        return justifications.get(grade, "Standard exception requiring resolution")

    def _assign_business_priority(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Assign business priority."""
        if category == ExceptionCategory.DUPLICATE and severity == ExceptionSeverity.ERROR:
            return BusinessPriority.CRITICAL
        elif severity == ExceptionSeverity.ERROR:
            return BusinessPriority.HIGH
        elif category in [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]:
            return BusinessPriority.MEDIUM
        else:
            return BusinessPriority.LOW

    def _assess_financial_materiality_level(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Assess financial materiality level."""
        if category == ExceptionCategory.DUPLICATE:
            return FinancialMateriality.MATERIAL
        elif severity == ExceptionSeverity.ERROR:
            return FinancialMateriality.MODERATE
        else:
            return FinancialMateriality.LOW

    def _assess_working_capital_impact_level(self, category: ExceptionCategory, severity: ExceptionSeverity) -> str:
        """Assess working capital impact level."""
        if category == ExceptionCategory.DUPLICATE:
            return WorkingCapitalImpact.HIGH
        elif category in [ExceptionCategory.MATCHING, ExceptionCategory.VENDOR_POLICY]:
            return WorkingCapitalImpact.MEDIUM
        else:
            return WorkingCapitalImpact.LOW

    # Additional helper methods would be implemented for complete functionality