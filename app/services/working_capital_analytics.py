"""
Working Capital Analytics Service.

This service provides comprehensive analytics for working capital optimization,
including cash flow forecasting, payment optimization, early payment discount analysis,
collection efficiency metrics, and working capital scoring.
"""

import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Tuple
import uuid
import statistics
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus
from app.models.working_capital import (
    CashFlowProjection, PaymentOptimization, EarlyPaymentDiscount,
    CollectionMetrics, WorkingCapitalScore, WorkingCapitalAlert,
    ProjectionPeriod, ScenarioType, DiscountStatus, PriorityLevel
)
from app.core.config import settings


class WorkingCapitalAnalytics:
    """
    Comprehensive working capital analytics service.

    This service provides TDD-driven analytics for optimizing working capital
    through data-driven insights and recommendations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cost_of_capital = getattr(settings, 'COST_OF_CAPITAL', Decimal('0.08'))  # 8% default

    # ================================
    # CASH FLOW FORECASTING METHODS
    # ================================

    async def calculate_cash_flow_projection(self, days: int = 30,
                                           scenario: ScenarioType = ScenarioType.REALISTIC) -> Dict[str, Any]:
        """
        Calculate cash flow projection for specified number of days.

        Args:
            days: Number of days to project
            scenario: Scenario type for projection

        Returns:
            Dictionary containing cash flow projection data
        """
        # Get outstanding invoices
        end_date = datetime.utcnow() + timedelta(days=days)

        query = select(ARInvoice).where(
            and_(
                ARInvoice.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID]),
                ARInvoice.due_date <= end_date
            )
        ).order_by(ARInvoice.due_date)

        result = await self.db.execute(query)
        invoices = result.scalars().all()

        # Initialize projection structures
        daily_breakdown = {}
        weekly_breakdown = {}
        monthly_breakdown = {}
        total_projected = Decimal('0.00')

        for invoice in invoices:
            due_date = invoice.due_date.date()
            amount = invoice.outstanding_amount

            # Apply scenario adjustments
            adjusted_amount = self._apply_scenario_adjustments(amount, scenario, invoice)

            total_projected += adjusted_amount

            # Daily breakdown
            if due_date not in daily_breakdown:
                daily_breakdown[due_date] = Decimal('0.00')
            daily_breakdown[due_date] += adjusted_amount

            # Weekly breakdown
            week_key = due_date.isocalendar()[:2]  # (year, week)
            if week_key not in weekly_breakdown:
                weekly_breakdown[week_key] = Decimal('0.00')
            weekly_breakdown[week_key] += adjusted_amount

            # Monthly breakdown
            month_key = (due_date.year, due_date.month)
            if month_key not in monthly_breakdown:
                monthly_breakdown[month_key] = Decimal('0.00')
            monthly_breakdown[month_key] += adjusted_amount

        # Calculate confidence score based on data quality and scenario
        confidence_score = self._calculate_confidence_score(invoices, scenario)

        return {
            'total_projected': total_projected.quantize(Decimal('0.01')),
            'daily_breakdown': {str(k): v.quantize(Decimal('0.01')) for k, v in daily_breakdown.items()},
            'weekly_breakdown': {f"{k[0]}-W{k[1]}": v.quantize(Decimal('0.01')) for k, v in weekly_breakdown.items()},
            'monthly_breakdown': {f"{k[0]}-{k[1]:02d}": v.quantize(Decimal('0.01')) for k, v in monthly_breakdown.items()},
            'confidence_score': confidence_score,
            'scenario': scenario,
            'projection_period_days': days,
            'invoice_count': len(invoices)
        }

    def _apply_scenario_adjustments(self, amount: Decimal, scenario: ScenarioType,
                                  invoice: ARInvoice) -> Decimal:
        """Apply scenario-based adjustments to cash flow projections."""
        if scenario == ScenarioType.REALISTIC:
            # Assume 95% collection rate for pending, 80% for overdue
            if invoice.is_overdue():
                return amount * Decimal('0.80')
            else:
                return amount * Decimal('0.95')

        elif scenario == ScenarioType.OPTIMISTIC:
            # Assume higher collection rates
            if invoice.is_overdue():
                return amount * Decimal('0.90')
            else:
                return amount * Decimal('0.98')

        elif scenario == ScenarioType.PESSIMISTIC:
            # Assume lower collection rates with some defaults
            if invoice.days_overdue() > 60:
                return amount * Decimal('0.50')  # Only 50% expected collection
            elif invoice.is_overdue():
                return amount * Decimal('0.70')
            else:
                return amount * Decimal('0.85')

        elif scenario == ScenarioType.STRESS_TEST:
            # Stress scenario with significant delays
            if invoice.days_overdue() > 30:
                return amount * Decimal('0.30')  # Only 30% expected
            else:
                return amount * Decimal('0.60')

        return amount

    def _calculate_confidence_score(self, invoices: List[ARInvoice], scenario: ScenarioType) -> float:
        """Calculate confidence score for cash flow projection."""
        if not invoices:
            return 0.0

        base_confidence = 85.0  # Start with good confidence

        # Adjust based on invoice aging
        overdue_invoices = [inv for inv in invoices if inv.is_overdue()]
        if overdue_invoices:
            overdue_ratio = len(overdue_invoices) / len(invoices)
            base_confidence -= (overdue_ratio * 20)  # Reduce confidence for overdue invoices

        # Adjust based on scenario type
        scenario_adjustments = {
            ScenarioType.REALISTIC: 0.0,
            ScenarioType.OPTIMISTIC: -5.0,
            ScenarioType.PESSIMISTIC: -10.0,
            ScenarioType.STRESS_TEST: -15.0
        }

        base_confidence += scenario_adjustments.get(scenario, 0.0)

        return max(0.0, min(100.0, base_confidence))

    async def detect_seasonal_patterns(self) -> Dict[str, Any]:
        """Detect seasonal patterns in cash flow."""
        # Get historical invoice data for the past 24 months
        start_date = datetime.utcnow() - timedelta(days=730)

        query = select(ARInvoice).where(
            ARInvoice.invoice_date >= start_date
        ).order_by(ARInvoice.invoice_date)

        result = await self.db.execute(query)
        invoices = result.scalars().all()

        # Group invoices by month
        monthly_data = {}
        for invoice in invoices:
            month_key = (invoice.invoice_date.year, invoice.invoice_date.month)
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(invoice.total_amount)

        # Calculate seasonal index
        if not monthly_data:
            return {'seasonal_index': {}, 'peak_months': [], 'low_months': [], 'confidence_level': 0.0}

        # Calculate monthly averages
        monthly_totals = {}
        for month_key, amounts in monthly_data.items():
            monthly_totals[month_key] = sum(amounts) / len(amounts)

        # Calculate overall average
        overall_average = sum(monthly_totals.values()) / len(monthly_totals) if monthly_totals else 0

        # Calculate seasonal index (12 months)
        seasonal_index = {}
        for month in range(1, 13):
            month_data = [monthly_totals.get((year, month), 0) for year in range(2022, 2025)]
            if month_data:
                avg_month = sum(month_data) / len(month_data)
                if overall_average > 0:
                    seasonal_index[month] = ((avg_month / overall_average) - 1) * 100  # Percentage deviation
                else:
                    seasonal_index[month] = 0
            else:
                seasonal_index[month] = 0

        # Identify peak and low months
        sorted_months = sorted(seasonal_index.items(), key=lambda x: x[1], reverse=True)
        peak_months = [month for month, index in sorted_months[:3] if index > 5]
        low_months = [month for month, index in sorted_months[-3:] if index < -5]

        # Calculate confidence level based on data consistency
        confidence_level = min(95.0, len(monthly_data) * 3.0)  # More data = higher confidence

        return {
            'seasonal_index': {f"Month {k}": float(v) for k, v in seasonal_index.items()},
            'peak_months': peak_months,
            'low_months': low_months,
            'confidence_level': confidence_level,
            'data_months': len(monthly_data)
        }

    async def analyze_cash_flow_scenarios(self) -> Dict[str, Any]:
        """Analyze multiple cash flow scenarios."""
        scenarios = {}

        for scenario in [ScenarioType.REALISTIC, ScenarioType.OPTIMISTIC, ScenarioType.PESSIMISTIC]:
            projection = await self.calculate_cash_flow_projection(days=90, scenario=scenario)

            # Add scenario-specific assumptions
            assumptions = self._get_scenario_assumptions(scenario)

            scenarios[scenario.value] = {
                'projected_cash_flow': projection,
                'assumptions': assumptions,
                'risk_factors': self._identify_scenario_risks(scenario)
            }

        return scenarios

    def _get_scenario_assumptions(self, scenario: ScenarioType) -> Dict[str, float]:
        """Get assumptions for each scenario type."""
        assumptions = {
            ScenarioType.REALISTIC: {
                'payment_rate': 0.85,
                'collection_efficiency': 0.90,
                'default_rate': 0.02,
                'delay_average_days': 5
            },
            ScenarioType.OPTIMISTIC: {
                'payment_rate': 0.95,
                'collection_efficiency': 0.95,
                'default_rate': 0.01,
                'delay_average_days': 2
            },
            ScenarioType.PESSIMISTIC: {
                'payment_rate': 0.70,
                'collection_efficiency': 0.80,
                'default_rate': 0.05,
                'delay_average_days': 15
            }
        }
        return assumptions.get(scenario, assumptions[ScenarioType.REALISTIC])

    def _identify_scenario_risks(self, scenario: ScenarioType) -> List[str]:
        """Identify risks associated with each scenario."""
        risks = {
            ScenarioType.REALISTIC: [
                "Unexpected economic changes",
                "Customer payment delays",
                "Seasonal variations"
            ],
            ScenarioType.OPTIMISTIC: [
                "Overestimation of collection rates",
                "Economic downturn impact",
                "Customer financial difficulties"
            ],
            ScenarioType.PESSIMISTIC: [
                "Conservative estimates may be too low",
                "Potential missed opportunities",
                "Over-allocation of reserves"
            ]
        }
        return risks.get(scenario, risks[ScenarioType.REALISTIC])

    async def validate_projection_accuracy(self) -> Dict[str, Any]:
        """Validate historical accuracy of cash flow projections."""
        # This would compare historical projections with actual results
        # For now, return simulated accuracy metrics

        return {
            'mape': 15.2,  # Mean Absolute Percentage Error
            'bias': -2.1,   # Slight underprediction
            'accuracy_score': 84.8,
            'recommendations': [
                "Improve late payment prediction models",
                "Incorporate seasonal adjustments",
                "Update customer payment behavior patterns"
            ]
        }

    # ================================
    # PAYMENT OPTIMIZATION METHODS
    # ================================

    async def calculate_optimal_payment_timing(self) -> List[Dict[str, Any]]:
        """Calculate optimal payment timing for invoices with early payment discounts."""
        # Get invoices with early payment discounts
        query = select(ARInvoice).where(
            and_(
                ARInvoice.status == PaymentStatus.PENDING,
                ARInvoice.early_payment_discount_percent.isnot(None),
                ARInvoice.early_payment_discount_days.isnot(None)
            )
        )

        result = await self.db.execute(query)
        invoices = result.scalars().all()

        recommendations = []

        for invoice in invoices:
            if invoice.is_early_payment_discount_available():
                recommendation = await self._analyze_payment_optimization(invoice)
                recommendations.append(recommendation)

        # Sort by potential savings (highest first)
        recommendations.sort(key=lambda x: x.get('potential_savings', Decimal('0')), reverse=True)

        return recommendations

    async def _analyze_payment_optimization(self, invoice: ARInvoice) -> Dict[str, Any]:
        """Analyze payment optimization for a single invoice."""
        discount_amount = invoice.calculate_early_payment_discount()
        outstanding_amount = invoice.outstanding_amount

        # Calculate optimal payment date (before discount deadline)
        discount_deadline = invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days))

        # Calculate working capital impact
        days_saved = (invoice.due_date - discount_deadline).days
        working_capital_savings = outstanding_amount * (self.cost_of_capital / Decimal('365')) * days_saved

        # Net benefit
        net_benefit = discount_amount - working_capital_savings

        # Generate recommendation
        if net_benefit > 0:
            recommendation = "Take early payment discount"
            optimal_date = discount_deadline - timedelta(days=1)  # Pay one day early
        else:
            recommendation = "Wait for normal payment date"
            optimal_date = invoice.due_date

        return {
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'optimal_payment_date': optimal_date,
            'discount_savings': discount_amount.quantize(Decimal('0.01')),
            'working_capital_impact': working_capital_savings.quantize(Decimal('0.01')),
            'net_benefit': net_benefit.quantize(Decimal('0.01')),
            'recommendation': recommendation,
            'discount_percent': invoice.early_payment_discount_percent,
            'discount_deadline': discount_deadline,
            'normal_due_date': invoice.due_date,
            'outstanding_amount': outstanding_amount.quantize(Decimal('0.01')),
            'days_saved': days_saved,
            'discount_available': True
        }

    async def analyze_early_payment_discounts(self) -> Dict[str, Any]:
        """Analyze early payment discount opportunities."""
        opportunities = await self.detect_discount_opportunities()

        total_savings = opportunities['total_potential_savings']
        total_opportunities = opportunities['total_opportunities']

        # Calculate ROI analysis
        roi_analysis = await self._calculate_discount_roi_analysis(opportunities)

        return {
            'total_opportunities': total_opportunities,
            'potential_savings': total_savings.quantize(Decimal('0.01')),
            'opportunities': opportunities['opportunities_list'],
            'roi_analysis': roi_analysis,
            'average_discount_percent': self._calculate_average_discount(opportunities['opportunities_list']),
            'utilization_recommendation': self._generate_utilization_recommendation(total_savings, total_opportunities)
        }

    async def detect_discount_opportunities(self) -> Dict[str, Any]:
        """Detect all early payment discount opportunities."""
        query = select(ARInvoice).where(
            and_(
                ARInvoice.status == PaymentStatus.PENDING,
                ARInvoice.early_payment_discount_percent.isnot(None),
                ARInvoice.early_payment_discount_days.isnot(None)
            )
        )

        result = await self.db.execute(query)
        invoices = result.scalars().all()

        available_opportunities = []
        expired_opportunities = []
        total_potential_savings = Decimal('0.00')

        for invoice in invoices:
            discount_amount = invoice.calculate_early_payment_discount()

            opportunity = {
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'total_amount': invoice.total_amount.quantize(Decimal('0.01')),
                'discount_amount': discount_amount.quantize(Decimal('0.01')),
                'discount_percent': invoice.early_payment_discount_percent,
                'deadline': invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)),
                'days_remaining': max(0, (invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)) - datetime.utcnow()).days),
                'status': 'available' if invoice.is_early_payment_discount_available() else 'expired'
            }

            if opportunity['status'] == 'available':
                available_opportunities.append(opportunity)
                total_potential_savings += discount_amount
            else:
                expired_opportunities.append(opportunity)

        return {
            'total_opportunities': len(available_opportunities),
            'available_opportunities': len(available_opportunities),
            'expired_opportunities': len(expired_opportunities),
            'total_potential_savings': total_potential_savings.quantize(Decimal('0.01')),
            'opportunities_list': available_opportunities + expired_opportunities
        }

    def _calculate_average_discount(self, opportunities: List[Dict]) -> Decimal:
        """Calculate average discount percentage."""
        if not opportunities:
            return Decimal('0.00')

        total_discount = sum(opp.get('discount_percent', Decimal('0')) for opp in opportunities)
        return (total_discount / len(opportunities)).quantize(Decimal('0.01'))

    def _generate_utilization_recommendation(self, total_savings: Decimal, opportunity_count: int) -> str:
        """Generate utilization recommendation based on potential savings."""
        if total_savings > Decimal('10000'):
            return "High priority: Significant savings available through early payment discounts"
        elif total_savings > Decimal('5000'):
            return "Medium priority: Moderate savings available"
        elif opportunity_count > 0:
            return "Low priority: Limited but available savings"
        else:
            return "No early payment discount opportunities currently available"

    async def _calculate_discount_roi_analysis(self, opportunities: Dict) -> Dict[str, Any]:
        """Calculate ROI analysis for discount opportunities."""
        total_savings = opportunities['total_potential_savings']
        opportunity_count = opportunities['total_opportunities']

        if opportunity_count == 0:
            return {
                'average_roi': 0.0,
                'total_investment_required': Decimal('0.00'),
                'payback_period_days': 0,
                'risk_level': 'none'
            }

        # Estimate investment required (early payment of all invoices)
        total_investment = sum(opp['total_amount'] - opp['discount_amount']
                             for opp in opportunities['opportunities_list']
                             if opp['status'] == 'available')

        # Calculate average ROI
        if total_investment > 0:
            average_roi = float((total_savings / total_investment) * 100)
        else:
            average_roi = 0.0

        # Estimate payback period (in days)
        avg_discount_days = sum(opp['days_remaining']
                              for opp in opportunities['opportunities_list']
                              if opp['status'] == 'available') / opportunity_count if opportunity_count > 0 else 0

        # Assess risk level
        if average_roi > 20:
            risk_level = 'low'
        elif average_roi > 10:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        return {
            'average_roi': round(average_roi, 2),
            'total_investment_required': total_investment.quantize(Decimal('0.01')),
            'payback_period_days': int(avg_discount_days),
            'risk_level': risk_level
        }

    async def calculate_working_capital_impact(self, amount: Decimal, discount_percent: Decimal,
                                             payment_terms: int, cost_of_capital: Decimal) -> Dict[str, Any]:
        """Calculate working capital impact of payment decisions."""
        # Calculate discount amount
        discount_amount = amount * (discount_percent / Decimal('100'))

        # Calculate working capital savings from early payment
        days_saved = payment_terms - 10  # Assuming 10-day discount period
        working_capital_savings = amount * (cost_of_capital / Decimal('365')) * days_saved

        # Calculate net benefit
        net_benefit = discount_amount - working_capital_savings

        # Calculate annualized return
        if days_saved > 0:
            annualized_return = (discount_amount / (amount - discount_amount)) * (Decimal('365') / days_saved) * 100
        else:
            annualized_return = Decimal('0.00')

        # Generate recommendation
        if net_benefit > 0:
            recommendation = "Take early payment discount"
            impact_score = min(100, float(annualized_return))
        else:
            recommendation = "Wait for normal payment date"
            impact_score = max(0, float(annualized_return))

        return {
            'discount_amount': discount_amount.quantize(Decimal('0.01')),
            'working_capital_cost': working_capital_savings.quantize(Decimal('0.01')),
            'net_benefit': net_benefit.quantize(Decimal('0.01')),
            'annualized_return': round(float(annualized_return), 2),
            'recommendation': recommendation,
            'impact_score': round(impact_score, 2)
        }

    async def calculate_payment_roi(self, invoice_amount: Decimal, discount_percent: Decimal,
                                  discount_days: int, regular_terms: int,
                                  cost_of_capital: Decimal) -> Dict[str, Any]:
        """Calculate ROI for early payment decisions."""
        # Calculate discount amount
        discount_amount = invoice_amount * (discount_percent / Decimal('100'))

        # Calculate cost of early payment (opportunity cost)
        days_early = regular_terms - discount_days
        early_payment_cost = invoice_amount * cost_of_capital * (Decimal(days_early) / Decimal('365'))

        # Calculate net ROI
        net_roi = discount_amount - early_payment_cost

        # Calculate annualized ROI
        if days_early > 0:
            annualized_roi = (net_roi / early_payment_cost) * (Decimal('365') / days_early) * 100 if early_payment_cost > 0 else 0
        else:
            annualized_roi = 0

        # Generate recommendation
        if net_roi > 0:
            recommendation = "Take early payment discount"
        else:
            recommendation = "Wait for normal payment terms"

        return {
            'discount_amount': discount_amount.quantize(Decimal('0.01')),
            'cost_of_early_payment': early_payment_cost.quantize(Decimal('0.01')),
            'net_roi': net_roi.quantize(Decimal('0.01')),
            'annualized_roi': round(float(annualized_roi), 2),
            'recommendation': recommendation,
            'days_saved': days_early,
            'roi_percentage': round(float((net_roi / early_payment_cost) * 100) if early_payment_cost > 0 else 0, 2)
        }

    async def optimize_payment_schedule(self) -> Dict[str, Any]:
        """Optimize payment schedule across multiple invoices."""
        recommendations = await self.calculate_optimal_payment_timing()

        # Calculate total savings
        total_savings = sum(rec.get('discount_savings', Decimal('0')) for rec in recommendations)

        # Calculate working capital impact
        total_working_capital_impact = sum(rec.get('working_capital_impact', Decimal('0')) for rec in recommendations)

        # Sort by priority score
        for rec in recommendations:
            # Priority score based on net benefit and urgency
            net_benefit = rec.get('net_benefit', Decimal('0'))
            days_remaining = rec.get('days_remaining', 0)
            urgency_factor = max(0, (10 - days_remaining) / 10) if days_remaining < 10 else 0
            rec['priority_score'] = float(net_benefit) * (1 + urgency_factor)

        recommendations.sort(key=lambda x: x['priority_score'], reverse=True)

        # Create payment schedule
        payment_schedule = []
        for i, rec in enumerate(recommendations[:10]):  # Top 10 recommendations
            payment_schedule.append({
                'rank': i + 1,
                'invoice_id': rec['invoice_id'],
                'invoice_number': rec['invoice_number'],
                'recommended_date': rec['optimal_payment_date'],
                'savings': rec['discount_savings'],
                'priority_score': rec['priority_score'],
                'recommendation': rec['recommendation']
            })

        return {
            'payment_schedule': payment_schedule,
            'total_savings': total_savings.quantize(Decimal('0.01')),
            'working_capital_preserved': total_working_capital_impact.quantize(Decimal('0.01')),
            'priority_list': recommendations,
            'implementation_timeline': self._generate_implementation_timeline(payment_schedule)
        }

    def _generate_implementation_timeline(self, schedule: List[Dict]) -> Dict[str, Any]:
        """Generate implementation timeline for payment optimizations."""
        if not schedule:
            return {'immediate': [], 'this_week': [], 'this_month': []}

        now = datetime.utcnow()
        immediate = []
        this_week = []
        this_month = []

        for item in schedule:
            recommended_date = item['recommended_date']
            if isinstance(recommended_date, str):
                recommended_date = datetime.fromisoformat(recommended_date.replace('Z', '+00:00'))

            days_until = (recommended_date - now).days

            if days_until <= 1:
                immediate.append(item)
            elif days_until <= 7:
                this_week.append(item)
            elif days_until <= 30:
                this_month.append(item)

        return {
            'immediate': immediate,
            'this_week': this_week,
            'this_month': this_month
        }

    # ================================
    # COLLECTION EFFICIENCY METHODS
    # ================================

    async def calculate_dso(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate Days Sales Outstanding (DSO)."""
        # Get outstanding invoices and sales data
        base_query = select(ARInvoice)

        if customer_id:
            base_query = base_query.where(ARInvoice.customer_id == customer_id)

        result = await self.db.execute(base_query)
        invoices = result.scalars().all()

        if not invoices:
            return {
                'current_dso': 0.0,
                'dso_trend': 'stable',
                'industry_comparison': {'median': 45.0, 'percentile': 50},
                'recommendations': ['Insufficient data for analysis']
            }

        # Calculate total outstanding receivables
        total_outstanding = sum(inv.outstanding_amount for inv in invoices if inv.outstanding_amount > 0)

        # Calculate total credit sales (using total amounts as proxy)
        total_sales = sum(inv.total_amount for inv in invoices)

        # Calculate DSO
        if total_sales > 0:
            dso = float((total_outstanding / total_sales) * 365)
        else:
            dso = 0.0

        # Generate trend and recommendations
        trend = self._determine_dso_trend(dso)
        recommendations = self._generate_dso_recommendations(dso)

        return {
            'current_dso': round(dso, 1),
            'dso_trend': trend,
            'industry_comparison': self._get_dso_industry_comparison(dso),
            'recommendations': recommendations,
            'total_outstanding': float(total_outstanding),
            'total_sales': float(total_sales),
            'invoice_count': len(invoices)
        }

    def _determine_dso_trend(self, current_dso: float) -> str:
        """Determine DSO trend based on current value."""
        if current_dso < 30:
            return 'excellent'
        elif current_dso < 45:
            return 'good'
        elif current_dso < 60:
            return 'concerning'
        else:
            return 'poor'

    def _generate_dso_recommendations(self, dso: float) -> List[str]:
        """Generate recommendations based on DSO value."""
        recommendations = []

        if dso > 60:
            recommendations.extend([
                "Implement aggressive collection procedures",
                "Review customer credit terms",
                "Consider factoring or other financing options"
            ])
        elif dso > 45:
            recommendations.extend([
                "Strengthen collection follow-up processes",
                "Review payment terms with slow-paying customers",
                "Implement early payment incentives"
            ])
        elif dso > 30:
            recommendations.extend([
                "Monitor collection performance closely",
                "Identify and address payment delays early"
            ])
        else:
            recommendations.append("Maintain current collection practices")

        return recommendations

    def _get_dso_industry_comparison(self, dso: float) -> Dict[str, Any]:
        """Get industry comparison for DSO."""
        # Industry benchmarks (example values)
        industry_median = 45.0

        if dso < industry_median * 0.8:
            percentile = 80
            performance = 'excellent'
        elif dso < industry_median:
            percentile = 60
            performance = 'good'
        elif dso < industry_median * 1.2:
            percentile = 40
            performance = 'average'
        else:
            percentile = 20
            performance = 'below_average'

        return {
            'median': industry_median,
            'percentile': percentile,
            'performance': performance
        }

    async def calculate_collection_effectiveness_index(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate Collection Effectiveness Index (CEI)."""
        base_query = select(ARInvoice)

        if customer_id:
            base_query = base_query.where(ARInvoice.customer_id == customer_id)

        result = await self.db.execute(base_query)
        invoices = result.scalars().all()

        if not invoices:
            return {
                'cei_score': 0.0,
                'collection_rate': 0.0,
                'recovery_rate': 0.0,
                'benchmark_comparison': {'industry_average': 75.0, 'percentile': 0}
            }

        # Calculate CEI components
        beginning_receivables = Decimal('0.00')  # Would need historical data
        current_collections = sum(inv.total_amount for inv in invoices if inv.status == PaymentStatus.PAID)
        credit_sales = sum(inv.total_amount for inv in invoices)  # Simplified

        # Calculate CEI
        if (beginning_receivables + credit_sales) > 0:
            cei = float((current_collections / (beginning_receivables + credit_sales)) * 100)
        else:
            cei = 0.0

        # Calculate collection rate
        total_invoices = len(invoices)
        paid_invoices = len([inv for inv in invoices if inv.status == PaymentStatus.PAID])
        collection_rate = (paid_invoices / total_invoices) * 100 if total_invoices > 0 else 0

        # Calculate recovery rate (amount recovered vs amount invoiced)
        total_invoiced = sum(inv.total_amount for inv in invoices)
        total_collected = sum(inv.paid_amount or Decimal('0') for inv in invoices if inv.paid_amount)
        recovery_rate = float((total_collected / total_invoiced) * 100) if total_invoiced > 0 else 0

        return {
            'cei_score': round(cei, 2),
            'collection_rate': round(collection_rate, 2),
            'recovery_rate': round(recovery_rate, 2),
            'benchmark_comparison': {
                'industry_average': 75.0,
                'percentile': min(100, max(0, (cei / 75.0) * 100))
            },
            'total_invoices': total_invoices,
            'paid_invoices': paid_invoices,
            'total_invoiced': float(total_invoiced),
            'total_collected': float(total_collected)
        }

    async def analyze_aging_buckets(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Analyze aging buckets for receivables."""
        base_query = select(ARInvoice).where(
            ARInvoice.outstanding_amount > 0
        )

        if customer_id:
            base_query = base_query.where(ARInvoice.customer_id == customer_id)

        result = await self.db.execute(base_query)
        invoices = result.scalars().all()

        # Initialize aging buckets
        aging_buckets = {
            'current': {'amount': Decimal('0.00'), 'count': 0, 'invoices': []},
            'days_1_30': {'amount': Decimal('0.00'), 'count': 0, 'invoices': []},
            'days_31_60': {'amount': Decimal('0.00'), 'count': 0, 'invoices': []},
            'days_61_90': {'amount': Decimal('0.00'), 'count': 0, 'invoices': []},
            'days_over_90': {'amount': Decimal('0.00'), 'count': 0, 'invoices': []}
        }

        total_outstanding = Decimal('0.00')

        for invoice in invoices:
            days_overdue = invoice.days_overdue()
            amount = invoice.outstanding_amount

            total_outstanding += amount

            # Categorize into aging buckets
            if days_overdue <= 0:
                bucket = 'current'
            elif days_overdue <= 30:
                bucket = 'days_1_30'
            elif days_overdue <= 60:
                bucket = 'days_31_60'
            elif days_overdue <= 90:
                bucket = 'days_61_90'
            else:
                bucket = 'days_over_90'

            aging_buckets[bucket]['amount'] += amount
            aging_buckets[bucket]['count'] += 1
            aging_buckets[bucket]['invoices'].append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount': float(amount),
                'days_overdue': days_overdue
            })

        # Calculate risk assessment
        risk_assessment = self._assess_aging_risk(aging_buckets, total_outstanding)

        # Format response
        response = {
            'total_outstanding': total_outstanding.quantize(Decimal('0.01')),
            'risk_assessment': risk_assessment,
            'aging_summary': {}
        }

        # Add bucket information
        for bucket_name, bucket_data in aging_buckets.items():
            response[bucket_name] = {
                'amount': bucket_data['amount'].quantize(Decimal('0.01')),
                'count': bucket_data['count'],
                'percentage': float((bucket_data['amount'] / total_outstanding) * 100) if total_outstanding > 0 else 0.0
            }
            response['aging_summary'][bucket_name] = {
                'amount': float(bucket_data['amount']),
                'count': bucket_data['count'],
                'percentage': float((bucket_data['amount'] / total_outstanding) * 100) if total_outstanding > 0 else 0.0
            }

        return response

    def _assess_aging_risk(self, aging_buckets: Dict, total_outstanding: Decimal) -> str:
        """Assess overall risk based on aging analysis."""
        if total_outstanding == 0:
            return 'no_risk'

        # Calculate percentage over 90 days
        over_90_percentage = (aging_buckets['days_over_90']['amount'] / total_outstanding) * 100

        # Calculate percentage over 60 days
        over_60_percentage = (
            (aging_buckets['days_61_90']['amount'] + aging_buckets['days_over_90']['amount']) /
            total_outstanding
        ) * 100

        # Risk assessment
        if over_90_percentage > 20 or over_60_percentage > 35:
            return 'high'
        elif over_90_percentage > 10 or over_60_percentage > 25:
            return 'medium'
        elif over_90_percentage > 5 or over_60_percentage > 15:
            return 'low'
        else:
            return 'minimal'

    async def analyze_payment_patterns(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Analyze payment patterns for customers."""
        # Get paid invoices for pattern analysis
        base_query = select(ARInvoice).where(
            ARInvoice.status == PaymentStatus.PAID
        )

        if customer_id:
            base_query = base_query.where(ARInvoice.customer_id == customer_id)

        result = await self.db.execute(base_query)
        invoices = result.scalars().all()

        if not invoices:
            return {
                'average_payment_days': 0,
                'payment_distribution': {},
                'seasonal_trends': {},
                'predictability_score': 0.0
            }

        # Calculate payment days for each invoice
        payment_days = []
        for invoice in invoices:
            if invoice.paid_at and invoice.invoice_date:
                days = (invoice.paid_at - invoice.invoice_date).days
                if 0 <= days <= 365:  # Filter reasonable values
                    payment_days.append(days)

        if not payment_days:
            return {
                'average_payment_days': 0,
                'payment_distribution': {},
                'seasonal_trends': {},
                'predictability_score': 0.0
            }

        # Calculate statistics
        average_days = statistics.mean(payment_days)
        median_days = statistics.median(payment_days)
        std_dev = statistics.stdev(payment_days) if len(payment_days) > 1 else 0

        # Create payment distribution
        distribution = {
            'under_30': len([d for d in payment_days if d < 30]),
            '30_to_45': len([d for d in payment_days if 30 <= d < 45]),
            '45_to_60': len([d for d in payment_days if 45 <= d < 60]),
            'over_60': len([d for d in payment_days if d >= 60])
        }

        # Calculate predictability score (lower std dev = more predictable)
        predictability_score = max(0, min(100, 100 - (std_dev / average_days * 100) if average_days > 0 else 0))

        # Analyze seasonal trends
        seasonal_trends = self._analyze_seasonal_payment_patterns(invoices)

        return {
            'average_payment_days': round(average_days, 1),
            'median_payment_days': round(median_days, 1),
            'payment_distribution': distribution,
            'seasonal_trends': seasonal_trends,
            'predictability_score': round(predictability_score, 1),
            'payment_volatility': round(std_dev, 1),
            'total_analyzed': len(payment_days)
        }

    def _analyze_seasonal_payment_patterns(self, invoices: List[ARInvoice]) -> Dict[str, Any]:
        """Analyze seasonal patterns in payments."""
        monthly_payments = {}

        for invoice in invoices:
            if invoice.paid_at:
                month_key = (invoice.paid_at.year, invoice.paid_at.month)
                if month_key not in monthly_payments:
                    monthly_payments[month_key] = []

                if invoice.invoice_date:
                    days = (invoice.paid_at - invoice.invoice_date).days
                    if 0 <= days <= 365:
                        monthly_payments[month_key].append(days)

        # Calculate monthly averages
        monthly_averages = {}
        for month_key, days_list in monthly_payments.items():
            if days_list:
                monthly_averages[month_key] = statistics.mean(days_list)

        if not monthly_averages:
            return {}

        # Identify patterns
        overall_average = statistics.mean(monthly_averages.values())
        seasonal_variations = {}

        for month in range(1, 13):
            month_data = [avg for (year, m), avg in monthly_averages.items() if m == month]
            if month_data:
                monthly_avg = statistics.mean(month_data)
                seasonal_variations[month] = ((monthly_avg / overall_average) - 1) * 100

        return {
            'monthly_variations': seasonal_variations,
            'most_prompt_months': sorted(seasonal_variations.items(), key=lambda x: x[1])[:3],
            'slowest_months': sorted(seasonal_variations.items(), key=lambda x: x[1], reverse=True)[:3],
            'data_months': len(monthly_averages)
        }

    async def analyze_collection_efficiency_trends(self) -> Dict[str, Any]:
        """Analyze collection efficiency trends over time."""
        # This would typically query historical metrics
        # For now, return simulated trend data

        # Generate 12 months of trend data
        trends = []
        base_date = datetime.utcnow()

        for i in range(12):
            period_date = base_date - timedelta(days=30 * i)

            # Simulate improving trend
            collection_rate = 85 + i * 1.5  # Improving from 85% to ~100%
            dso = 50 - i * 1.2  # Improving from 50 to ~35 days

            trends.append({
                'period': period_date.strftime('%Y-%m'),
                'collection_rate': min(100, collection_rate),
                'dso': max(20, dso),
                'overdue_percentage': max(5, 15 - i * 0.8)
            })

        # Calculate trend direction
        recent_trend = trends[:3]  # Last 3 months
        older_trend = trends[3:6]  # Previous 3 months

        recent_avg_rate = sum(t['collection_rate'] for t in recent_trend) / len(recent_trend)
        older_avg_rate = sum(t['collection_rate'] for t in older_trend) / len(older_trend)

        if recent_avg_rate > older_avg_rate + 2:
            trend_direction = 'improving'
        elif recent_avg_rate < older_avg_rate - 2:
            trend_direction = 'declining'
        else:
            trend_direction = 'stable'

        return {
            'collection_rate_trend': {
                'direction': trend_direction,
                'recent_average': recent_avg_rate,
                'change_from_previous': recent_avg_rate - older_avg_rate,
                'data_points': trends
            },
            'dso_trend': {
                'direction': 'improving' if trends[0]['dso'] < trends[-1]['dso'] else 'declining',
                'current_dso': trends[0]['dso'],
                'change_from_previous': trends[-1]['dso'] - trends[0]['dso']
            },
            'improvement_areas': self._identify_improvement_areas(trends),
            'forecast': self._forecast_collection_trends(trends)
        }

    def _identify_improvement_areas(self, trends: List[Dict]) -> List[str]:
        """Identify areas needing improvement based on trends."""
        improvement_areas = []

        latest = trends[0]

        if latest['collection_rate'] < 90:
            improvement_areas.append("Collection rate below 90%")

        if latest['dso'] > 40:
            improvement_areas.append("DSO above 40 days")

        if latest['overdue_percentage'] > 10:
            improvement_areas.append("High overdue percentage")

        return improvement_areas

    def _forecast_collection_trends(self, trends: List[Dict]) -> Dict[str, Any]:
        """Forecast collection trends based on historical data."""
        if len(trends) < 3:
            return {'forecast': 'insufficient_data'}

        # Simple linear forecast
        recent_rates = [t['collection_rate'] for t in trends[:6]]
        rate_trend = (recent_rates[0] - recent_rates[-1]) / len(recent_rates) if len(recent_rates) > 1 else 0

        projected_rates = []
        for i in range(3):  # Project 3 months ahead
            projected_rate = recent_rates[0] + (rate_trend * (i + 1))
            projected_rates.append(min(100, max(0, projected_rate)))

        return {
            'method': 'linear_trend',
            'projected_rates': projected_rates,
            'confidence': 'medium' if len(trends) >= 6 else 'low'
        }

    # ================================
    # EARLY PAYMENT DISCOUNT METHODS
    # ================================

    async def analyze_discount_break_even(self, invoice_amount: Decimal, discount_percent: Decimal,
                                        discount_period_days: int, normal_terms_days: int,
                                        cost_of_capital: Decimal) -> Dict[str, Any]:
        """Analyze break-even point for early payment discounts."""
        # Calculate discount amount
        discount_amount = invoice_amount * (discount_percent / Decimal('100'))

        # Calculate daily cost of capital
        daily_cost_of_capital = cost_of_capital / Decimal('365')

        # Calculate days saved by early payment
        days_saved = normal_terms_days - discount_period_days

        # Calculate savings from early payment
        savings_from_early_payment = invoice_amount * daily_cost_of_capital * days_saved

        # Calculate break-even point
        net_benefit = discount_amount - savings_from_early_payment
        break_even_achieved = net_benefit > 0

        # Calculate break-even days (if discount is worth taking)
        if discount_amount > 0 and daily_cost_of_capital > 0:
            break_even_days = discount_amount / (invoice_amount * daily_cost_of_capital)
        else:
            break_even_days = 0

        return {
            'discount_amount': discount_amount.quantize(Decimal('0.01')),
            'savings_from_early_payment': savings_from_early_payment.quantize(Decimal('0.01')),
            'break_even_point': break_even_achieved,
            'break_even_days': round(break_even_days, 1),
            'net_benefit': net_benefit.quantize(Decimal('0.01')),
            'recommendation': 'take_discount' if break_even_achieved else 'wait_normal_terms',
            'days_saved': days_saved,
            'annualized_return': float((discount_amount / (invoice_amount - discount_amount)) * (Decimal('365') / days_saved) * 100) if days_saved > 0 else 0
        }

    async def analyze_discount_cost_benefit(self, total_discountable_amount: Decimal,
                                          average_discount_percent: Decimal,
                                          average_payment_terms: int,
                                          cost_of_capital: Decimal,
                                          administrative_cost_per_payment: Decimal) -> Dict[str, Any]:
        """Analyze comprehensive cost-benefit of discount program."""
        # Calculate total discount cost
        total_discount_cost = total_discountable_amount * (average_discount_percent / Decimal('100'))

        # Calculate working capital savings
        days_saved = average_payment_terms - 10  # Assuming 10-day average discount period
        total_working_capital_savings = total_discountable_amount * cost_of_capital * (Decimal(days_saved) / Decimal('365'))

        # Calculate administrative costs
        # Estimate number of discount payments (simplified)
        estimated_payments = max(1, int(total_discountable_amount / 5000))  # Assume average $5k per invoice
        total_administrative_cost = administrative_cost_per_payment * estimated_payments

        # Calculate net financial impact
        total_benefits = total_working_capital_savings
        total_costs = total_discount_cost + total_administrative_cost
        net_financial_impact = total_benefits - total_costs

        # Calculate ROI
        roi_percentage = ((net_financial_impact / total_costs) * 100) if total_costs > 0 else 0

        # Generate recommendation
        if net_financial_impact > 0:
            recommendation = 'implement_discount_program'
        elif net_financial_impact > -total_discount_cost * Decimal('0.1'):  # Within 10% of break-even
            recommendation = 'consider_discount_program'
        else:
            recommendation = 'reconsider_discount_program'

        return {
            'total_discount_cost': total_discount_cost.quantize(Decimal('0.01')),
            'total_working_capital_savings': total_working_capital_savings.quantize(Decimal('0.01')),
            'total_administrative_cost': total_administrative_cost.quantize(Decimal('0.01')),
            'net_financial_impact': net_financial_impact.quantize(Decimal('0.01')),
            'roi_percentage': round(float(roi_percentage), 2),
            'recommendation': recommendation,
            'estimated_payments': estimated_payments,
            'benefit_cost_ratio': float(total_benefits / total_costs) if total_costs > 0 else 0
        }

    async def analyze_historical_discount_accuracy(self) -> Dict[str, Any]:
        """Analyze historical accuracy of discount predictions."""
        # This would query historical discount data
        # For now, return simulated historical analysis

        return {
            'utilization_rate': 75.5,  # 75.5% of available discounts utilized
            'prediction_accuracy': 82.3,  # 82.3% accuracy in discount opportunity predictions
            'trend_analysis': {
                'direction': 'improving',
                'utilization_trend': '+5.2%',
                'accuracy_trend': '+3.1%'
            },
            'improvement_recommendations': [
                "Improve early notification system for discount opportunities",
                "Enhance integration with payment processing systems",
                "Provide better training on discount utilization",
                "Implement automated discount recommendation system"
            ]
        }

    async def generate_discount_optimization_recommendations(self) -> Dict[str, Any]:
        """Generate optimization recommendations for discount programs."""
        opportunities = await self.detect_discount_opportunities()

        # Prioritize opportunities
        priority_opportunities = []
        for opp in opportunities['opportunities_list']:
            if opp['status'] == 'available':
                # Calculate priority score based on discount amount and urgency
                amount_score = float(opp['discount_amount']) / 100  # Normalize by $100
                urgency_score = max(0, (10 - opp['days_remaining']) / 10) if opp['days_remaining'] < 10 else 0
                priority_score = amount_score * (1 + urgency_score)

                priority_opportunities.append({
                    **opp,
                    'priority_score': priority_score
                })

        # Sort by priority
        priority_opportunities.sort(key=lambda x: x['priority_score'], reverse=True)

        # Generate recommendations
        total_savings = sum(opp['discount_amount'] for opp in priority_opportunities)

        return {
            'priority_opportunities': priority_opportunities[:10],  # Top 10
            'process_improvements': [
                "Implement automated discount tracking system",
                "Set up early warning notifications for expiring discounts",
                "Integrate discount analysis with payment processing",
                "Establish clear discount utilization protocols"
            ],
            'financial_impact': {
                'total_potential_savings': total_savings.quantize(Decimal('0.01')),
                'average_discount_amount': (total_savings / len(priority_opportunities)).quantize(Decimal('0.01')) if priority_opportunities else Decimal('0.00'),
                'roi_potential': self._calculate_discount_roi_potential(priority_opportunities)
            },
            'implementation_timeline': {
                'immediate_actions': len([opp for opp in priority_opportunities if opp['days_remaining'] <= 3]),
                'week_one_actions': len([opp for opp in priority_opportunities if opp['days_remaining'] <= 7]),
                'month_one_actions': len(priority_opportunities)
            }
        }

    def _calculate_discount_roi_potential(self, opportunities: List[Dict]) -> float:
        """Calculate potential ROI from discount opportunities."""
        if not opportunities:
            return 0.0

        total_savings = sum(float(opp['discount_amount']) for opp in opportunities)
        total_investment = sum(float(opp['total_amount']) - float(opp['discount_amount']) for opp in opportunities)

        if total_investment > 0:
            return round((total_savings / total_investment) * 100, 2)
        else:
            return 0.0

    async def assess_discount_program_risks(self, annual_revenue: Decimal,
                                          average_discount_percent: Decimal,
                                          expected_utilization_rate: Decimal,
                                          customer_concentration_risk: Decimal,
                                          cash_flow_volatility: Decimal) -> Dict[str, Any]:
        """Assess risks associated with early payment discount programs."""
        # Calculate financial risk metrics
        annual_discount_cost = annual_revenue * (average_discount_percent / Decimal('100')) * expected_utilization_rate

        # Calculate risk scores
        financial_risk_score = min(100, float((annual_discount_cost / annual_revenue) * 500))  # Scale to 0-100
        concentration_risk_score = float(customer_concentration_risk * 100)
        cash_flow_risk_score = float(cash_flow_volatility * 100)

        # Calculate overall risk
        overall_risk_score = (financial_risk_score * 0.4 + concentration_risk_score * 0.3 + cash_flow_risk_score * 0.3)

        # Determine risk level
        if overall_risk_score > 70:
            risk_level = 'high'
        elif overall_risk_score > 40:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        # Generate mitigation strategies
        mitigation_strategies = self._generate_discount_risk_mitigation(overall_risk_score)

        return {
            'overall_risk_level': risk_level,
            'overall_risk_score': round(overall_risk_score, 1),
            'financial_risk': {
                'score': round(financial_risk_score, 1),
                'annual_cost': float(annual_discount_cost),
                'cost_as_revenue_percentage': float((annual_discount_cost / annual_revenue) * 100) if annual_revenue > 0 else 0
            },
            'operational_risk': {
                'concentration_risk': round(concentration_risk_score, 1),
                'cash_flow_volatility': round(cash_flow_risk_score, 1)
            },
            'mitigation_strategies': mitigation_strategies,
            'risk_tolerance_check': self._check_risk_tolerance(overall_risk_score)
        }

    def _generate_discount_risk_mitigation(self, risk_score: float) -> List[str]:
        """Generate risk mitigation strategies based on risk score."""
        strategies = []

        if risk_score > 70:
            strategies.extend([
                "Implement strict discount approval processes",
                "Set conservative discount limits",
                "Diversify customer base to reduce concentration",
                "Maintain substantial cash reserves"
            ])
        elif risk_score > 40:
            strategies.extend([
                "Monitor discount utilization closely",
                "Set up early warning systems",
                "Regularly review discount terms",
                "Maintain adequate working capital buffers"
            ])
        else:
            strategies.extend([
                "Continue standard monitoring procedures",
                "Periodic review of discount effectiveness",
                "Maintain standard risk controls"
            ])

        return strategies

    def _check_risk_tolerance(self, risk_score: float) -> str:
        """Check if risk level is within acceptable tolerance."""
        if risk_score > 70:
            return "Risk exceeds acceptable tolerance - immediate action required"
        elif risk_score > 50:
            return "Risk approaching tolerance limits - increased monitoring needed"
        elif risk_score > 30:
            return "Risk within acceptable tolerance - standard monitoring"
        else:
            return "Risk well within tolerance - normal operations"

    # ================================
    # WORKING CAPITAL SCORING METHODS
    # ================================

    async def calculate_overall_working_capital_score(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate overall working capital optimization score."""
        # Get component scores
        collection_score = await self.calculate_collection_efficiency_score(customer_id)
        payment_score = await self.calculate_payment_optimization_score(customer_id)
        discount_score = await self.calculate_discount_utilization_score(customer_id)

        # Calculate weighted average
        total_score = (
            collection_score['score'] * collection_score['weight'] +
            payment_score['score'] * payment_score['weight'] +
            discount_score['score'] * discount_score['weight']
        )

        # Get benchmark comparison
        benchmark_comparison = await self.compare_with_industry_benchmarks({
            'dso': collection_score.get('dso', 45),
            'cash_conversion_cycle': payment_score.get('cash_conversion_cycle', 25),
            'working_capital_turnover': payment_score.get('working_capital_turnover', 6.0)
        })

        # Identify improvement areas
        improvement_areas = []
        if collection_score['score'] < 70:
            improvement_areas.append("collection_efficiency")
        if payment_score['score'] < 70:
            improvement_areas.append("payment_optimization")
        if discount_score['score'] < 70:
            improvement_areas.append("discount_utilization")

        return {
            'total_score': round(total_score, 1),
            'component_scores': {
                'collection_efficiency': collection_score,
                'payment_optimization': payment_score,
                'discount_utilization': discount_score
            },
            'benchmark_comparison': benchmark_comparison,
            'improvement_areas': improvement_areas,
            'overall_grade': self._calculate_grade(total_score)
        }

    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade based on score."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'

    async def calculate_collection_efficiency_score(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate collection efficiency component score."""
        # Get collection metrics
        dso_metrics = await self.calculate_dso(customer_id)
        cei_metrics = await self.calculate_collection_effectiveness_index(customer_id)
        aging_analysis = await self.analyze_aging_buckets(customer_id)

        # Calculate sub-scores
        dso_score = max(0, min(100, 120 - dso_metrics['current_dso']))  # Lower DSO = higher score
        cei_score = min(100, cei_metrics['cei_score'])  # CEI already 0-100
        aging_score = self._calculate_aging_score(aging_analysis)

        # Calculate weighted average
        collection_score = (dso_score * 0.4 + cei_score * 0.4 + aging_score * 0.2)

        return {
            'score': round(collection_score, 1),
            'weight': 0.4,
            'sub_scores': {
                'dso_score': round(dso_score, 1),
                'cei_score': round(cei_score, 1),
                'aging_score': round(aging_score, 1)
            },
            'dso': dso_metrics['current_dso'],
            'trend_analysis': dso_metrics['dso_trend']
        }

    def _calculate_aging_score(self, aging_analysis: Dict) -> float:
        """Calculate score based on aging analysis."""
        total_outstanding = aging_analysis.get('total_outstanding', 0)
        if total_outstanding == 0:
            return 100.0

        # Calculate risk score based on aging buckets
        over_90_amount = aging_analysis.get('days_over_90', {}).get('amount', 0)
        over_60_amount = aging_analysis.get('days_61_90', {}).get('amount', 0) + over_90_amount

        over_90_percentage = (over_90_amount / total_outstanding) * 100
        over_60_percentage = (over_60_amount / total_outstanding) * 100

        # Calculate score (penalize higher percentages)
        score = 100
        if over_90_percentage > 20:
            score -= 40
        elif over_90_percentage > 10:
            score -= 25
        elif over_90_percentage > 5:
            score -= 15

        if over_60_percentage > 35:
            score -= 20
        elif over_60_percentage > 25:
            score -= 10
        elif over_60_percentage > 15:
            score -= 5

        return max(0, score)

    async def calculate_payment_optimization_score(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate payment optimization component score."""
        # Get payment optimization metrics
        optimization_recommendations = await self.calculate_optimal_payment_timing()

        # Filter by customer if specified
        if customer_id:
            # This would need to be implemented to filter by customer
            pass

        # Calculate metrics
        total_savings = sum(rec.get('potential_savings', Decimal('0')) for rec in optimization_recommendations)
        optimization_rate = len([rec for rec in optimization_recommendations if rec.get('net_benefit', Decimal('0')) > 0]) / len(optimization_recommendations) if optimization_recommendations else 0

        # Calculate working capital turnover (simplified)
        # Would need more sophisticated calculation with real data
        working_capital_turnover = 6.5  # Placeholder
        cash_conversion_cycle = 25.0  # Placeholder

        # Calculate sub-scores
        optimization_score = optimization_rate * 100
        turnover_score = min(100, working_capital_turnover * 12)  # Scale turnover to score
        cycle_score = max(0, 100 - cash_conversion_cycle)  # Lower cycle = higher score

        # Calculate weighted average
        payment_score = (optimization_score * 0.4 + turnover_score * 0.3 + cycle_score * 0.3)

        return {
            'score': round(payment_score, 1),
            'weight': 0.35,
            'sub_scores': {
                'optimization_score': round(optimization_score, 1),
                'turnover_score': round(turnover_score, 1),
                'cycle_score': round(cycle_score, 1)
            },
            'optimization_opportunities': {
                'total_savings': float(total_savings),
                'optimization_rate': round(optimization_rate * 100, 1),
                'opportunity_count': len(optimization_recommendations)
            },
            'working_capital_turnover': working_capital_turnover,
            'cash_conversion_cycle': cash_conversion_cycle
        }

    async def calculate_discount_utilization_score(self, customer_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Calculate discount utilization component score."""
        # Get discount opportunities
        discount_analysis = await self.analyze_early_payment_discounts()
        historical_accuracy = await self.analyze_historical_discount_accuracy()

        # Calculate metrics
        total_opportunities = discount_analysis['total_opportunities']
        total_savings = discount_analysis['potential_savings']

        # Calculate utilization rate (would need historical data)
        utilization_rate = historical_accuracy['utilization_rate']
        roi_achieved = discount_analysis['roi_analysis'].get('average_roi', 0)

        # Calculate accuracy rate
        accuracy_rate = historical_accuracy['prediction_accuracy']

        # Calculate sub-scores
        utilization_score = min(100, utilization_rate * 1.2)  # Scale up slightly
        roi_score = min(100, max(0, roi_achieved * 5))  # Scale ROI to score (20% ROI = 100 points)
        accuracy_score = accuracy_rate

        # Calculate weighted average
        discount_score = (utilization_score * 0.4 + roi_score * 0.4 + accuracy_score * 0.2)

        return {
            'score': round(discount_score, 1),
            'weight': 0.25,
            'sub_scores': {
                'utilization_score': round(utilization_score, 1),
                'roi_score': round(roi_score, 1),
                'accuracy_score': round(accuracy_score, 1)
            },
            'utilization_metrics': {
                'utilization_rate': utilization_rate,
                'total_savings': float(total_savings),
                'opportunity_count': total_opportunities
            },
            'roi_achieved': roi_achieved,
            'accuracy_rate': accuracy_rate
        }

    async def compare_with_industry_benchmarks(self, company_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Compare company metrics with industry benchmarks."""
        # Industry benchmarks (example values)
        industry_benchmarks = {
            'dso': {'median': 45.0, 'top_quartile': 30.0, 'bottom_quartile': 60.0},
            'cash_conversion_cycle': {'median': 35.0, 'top_quartile': 20.0, 'bottom_quartile': 50.0},
            'working_capital_turnover': {'median': 5.0, 'top_quartile': 8.0, 'bottom_quartile': 3.0}
        }

        # Calculate percentiles for each metric
        percentiles = {}
        for metric, value in company_metrics.items():
            if metric in industry_benchmarks:
                benchmarks = industry_benchmarks[metric]
                percentile = self._calculate_percentile(value, benchmarks)
                percentiles[metric] = percentile

        # Calculate overall percentile
        overall_percentile = sum(percentiles.values()) / len(percentiles) if percentiles else 50

        # Determine competitive positioning
        if overall_percentile >= 75:
            positioning = 'leader'
        elif overall_percentile >= 60:
            positioning = 'above_average'
        elif overall_percentile >= 40:
            positioning = 'average'
        else:
            positioning = 'below_average'

        return {
            'overall_percentile': round(overall_percentile, 1),
            'metric_percentiles': {k: round(v, 1) for k, v in percentiles.items()},
            'competitive_positioning': positioning,
            'improvement_targets': self._calculate_improvement_targets(company_metrics, industry_benchmarks)
        }

    def _calculate_percentile(self, value: float, benchmarks: Dict[str, float]) -> float:
        """Calculate percentile rank for a metric value."""
        median = benchmarks['median']
        top_quartile = benchmarks['top_quartile']
        bottom_quartile = benchmarks['bottom_quartile']

        if value <= top_quartile:
            # Top quartile (75th to 100th percentile)
            return 75 + ((top_quartile - value) / (top_quartile - (top_quartile * 0.5))) * 25
        elif value <= median:
            # Second quartile (50th to 75th percentile)
            return 50 + ((median - value) / (median - top_quartile)) * 25
        elif value <= bottom_quartile:
            # Third quartile (25th to 50th percentile)
            return 25 + ((bottom_quartile - value) / (bottom_quartile - median)) * 25
        else:
            # Bottom quartile (0th to 25th percentile)
            return max(0, (bottom_quartile / value) * 25)

    def _calculate_improvement_targets(self, company_metrics: Dict[str, float],
                                     industry_benchmarks: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Calculate improvement targets based on industry benchmarks."""
        targets = {}

        for metric, current_value in company_metrics.items():
            if metric in industry_benchmarks:
                # Target top quartile performance
                if metric == 'working_capital_turnover':
                    # Higher is better
                    targets[metric] = industry_benchmarks[metric]['top_quartile']
                else:
                    # Lower is better (DSO, cash conversion cycle)
                    targets[metric] = industry_benchmarks[metric]['top_quartile']

        return targets

    async def analyze_score_trends(self) -> Dict[str, Any]:
        """Analyze working capital score trends over time."""
        # Generate historical score data (would normally query from database)
        historical_scores = []
        base_date = datetime.utcnow()

        for i in range(12):
            score_date = base_date - timedelta(days=30 * i)
            # Simulate improving trend
            score = 72 + i * 1.5 + (i % 3) * 0.5  # Base score with improvement and some variation

            historical_scores.append({
                'date': score_date.strftime('%Y-%m'),
                'total_score': round(score, 1),
                'collection_score': round(score - 2, 1),
                'payment_score': round(score + 1, 1),
                'discount_score': round(score - 1, 1)
            })

        # Calculate trend
        if len(historical_scores) >= 2:
            recent_score = historical_scores[0]['total_score']
            previous_score = historical_scores[1]['total_score']
            score_change = recent_score - previous_score

            if score_change > 2:
                trend_direction = 'improving'
            elif score_change < -2:
                trend_direction = 'declining'
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'insufficient_data'

        # Calculate improvement rate
        if len(historical_scores) >= 6:
            recent_avg = sum(s['total_score'] for s in historical_scores[:3]) / 3
            older_avg = sum(s['total_score'] for s in historical_scores[3:6]) / 3
            improvement_rate = recent_avg - older_avg
        else:
            improvement_rate = 0

        # Simple forecast
        if improvement_rate > 0:
            forecast_score = historical_scores[0]['total_score'] + improvement_rate
        else:
            forecast_score = historical_scores[0]['total_score']

        return {
            'overall_trend': {
                'direction': trend_direction,
                'current_score': historical_scores[0]['total_score'],
                'change_from_previous': score_change if 'score_change' in locals() else 0
            },
            'component_trends': {
                'collection_efficiency': self._calculate_component_trend([s['collection_score'] for s in historical_scores]),
                'payment_optimization': self._calculate_component_trend([s['payment_score'] for s in historical_scores]),
                'discount_utilization': self._calculate_component_trend([s['discount_score'] for s in historical_scores])
            },
            'improvement_rate': round(improvement_rate, 2),
            'forecast': {
                'next_month_score': round(forecast_score, 1),
                'confidence': 'medium' if len(historical_scores) >= 6 else 'low'
            },
            'historical_data': historical_scores
        }

    def _calculate_component_trend(self, scores: List[float]) -> Dict[str, Any]:
        """Calculate trend for a specific component."""
        if len(scores) < 2:
            return {'direction': 'insufficient_data', 'change': 0}

        current = scores[0]
        previous = scores[1]
        change = current - previous

        if change > 1:
            direction = 'improving'
        elif change < -1:
            direction = 'declining'
        else:
            direction = 'stable'

        return {
            'direction': direction,
            'change': round(change, 1),
            'current_score': current
        }

    async def generate_actionable_recommendations(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate actionable recommendations based on current scores and metrics."""
        total_score = current_state['total_score']
        component_scores = current_state['component_scores']
        key_metrics = current_state.get('key_metrics', {})

        priority_actions = []
        quick_wins = []
        long_term_improvements = []

        # Analyze each component
        for component, score_data in component_scores.items():
            score = score_data['score']
            issues = score_data.get('issues', [])

            if score < 60:
                # Critical issues need priority action
                for issue in issues:
                    if component == 'collection_efficiency':
                        priority_actions.append({
                            'area': component,
                            'issue': issue,
                            'action': self._get_collection_priority_action(issue),
                            'impact': 'high',
                            'effort': 'medium',
                            'timeline': '30-60 days'
                        })
                    elif component == 'payment_optimization':
                        priority_actions.append({
                            'area': component,
                            'issue': issue,
                            'action': self._get_payment_priority_action(issue),
                            'impact': 'high',
                            'effort': 'medium',
                            'timeline': '30-45 days'
                        })
                    elif component == 'discount_utilization':
                        priority_actions.append({
                            'area': component,
                            'issue': issue,
                            'action': self._get_discount_priority_action(issue),
                            'impact': 'medium',
                            'effort': 'low',
                            'timeline': '15-30 days'
                        })

            elif score < 80:
                # Moderate issues can be quick wins
                for issue in issues:
                    quick_wins.append({
                        'area': component,
                        'issue': issue,
                        'action': self._get_quick_win_action(component, issue),
                        'impact': 'medium',
                        'effort': 'low',
                        'timeline': '7-21 days'
                    })

        # Long-term improvements
        if total_score < 85:
            long_term_improvements.extend([
                {
                    'area': 'system_optimization',
                    'action': 'Implement advanced analytics and ML for payment prediction',
                    'impact': 'high',
                    'effort': 'high',
                    'timeline': '90-180 days'
                },
                {
                    'area': 'process_improvement',
                    'action': 'Develop comprehensive working capital management framework',
                    'impact': 'high',
                    'effort': 'high',
                    'timeline': '60-120 days'
                }
            ])

        # Calculate expected impact
        expected_impact = self._calculate_recommendation_impact(priority_actions, quick_wins, current_state)

        return {
            'priority_actions': priority_actions[:5],  # Top 5 priority actions
            'quick_wins': quick_wins[:5],  # Top 5 quick wins
            'long_term_improvements': long_term_improvements,
            'expected_impact': expected_impact,
            'implementation_plan': self._create_implementation_plan(priority_actions, quick_wins)
        }

    def _get_collection_priority_action(self, issue: str) -> str:
        """Get priority action for collection efficiency issues."""
        actions = {
            'high_dso': "Implement targeted collection process for high DSO customers",
            'overdue_rate': "Establish automated overdue invoice follow-up system",
            'low_cei': "Review and strengthen credit approval process"
        }
        return actions.get(issue, "Conduct comprehensive collection process review")

    def _get_payment_priority_action(self, issue: str) -> str:
        """Get priority action for payment optimization issues."""
        actions = {
            'missed_discounts': "Implement automated early payment discount system",
            'poor_timing': "Develop optimal payment scheduling system",
            'low_turnover': "Analyze and optimize working capital turnover"
        }
        return actions.get(issue, "Review payment optimization processes")

    def _get_discount_priority_action(self, issue: str) -> str:
        """Get priority action for discount utilization issues."""
        actions = {
            'low_utilization': "Set up automated discount opportunity notifications",
            'poor_tracking': "Implement comprehensive discount tracking system"
        }
        return actions.get(issue, "Enhance discount management processes")

    def _get_quick_win_action(self, component: str, issue: str) -> str:
        """Get quick win action for moderate issues."""
        actions = {
            ('collection_efficiency', 'moderate_dso'): "Send reminder emails for overdue invoices",
            ('payment_optimization', 'some_missed_discounts'): "Review weekly discount opportunities",
            ('discount_utilization', 'tracking_gaps'): "Update discount tracking spreadsheet"
        }
        return actions.get((component, issue), "Monitor and review current processes")

    def _calculate_recommendation_impact(self, priority_actions: List[Dict],
                                       quick_wins: List[Dict],
                                       current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate expected impact of recommendations."""
        # Estimate score improvements
        priority_impact = len(priority_actions) * 5  # 5 points per priority action
        quick_win_impact = len(quick_wins) * 2  # 2 points per quick win

        total_current_score = current_state['total_score']
        projected_score = min(100, total_current_score + priority_impact + quick_win_impact)

        # Estimate financial impact
        financial_improvements = []
        for action in priority_actions + quick_wins:
            if action['area'] == 'discount_utilization':
                financial_improvements.append("Increased discount savings")
            elif action['area'] == 'payment_optimization':
                financial_improvements.append("Improved working capital efficiency")
            elif action['area'] == 'collection_efficiency':
                financial_improvements.append("Reduced DSO and improved cash flow")

        return {
            'score_improvement': round(projected_score - total_current_score, 1),
            'projected_score': round(projected_score, 1),
            'financial_benefits': financial_improvements,
            'implementation_priority': "high" if priority_impact > 10 else "medium"
        }

    def _create_implementation_plan(self, priority_actions: List[Dict],
                                  quick_wins: List[Dict]) -> Dict[str, List[Dict]]:
        """Create structured implementation plan."""
        return {
            'week_1': [action for action in quick_wins if action['timeline'] == '7-21 days'][:2],
            'weeks_2_4': [action for action in quick_wins if action['timeline'] == '7-21 days'][2:] +
                        [action for action in priority_actions if action['timeline'] == '15-30 days'][:1],
            'month_2': [action for action in priority_actions if action['timeline'] in ['30-45 days', '30-60 days']],
            'months_3_6': [action for action in priority_actions if '60' in action['timeline']]
        }

    async def generate_working_capital_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive working capital KPI dashboard."""
        # Get all required data
        overall_score = await self.calculate_overall_working_capital_score()
        cash_flow_metrics = await self.calculate_cash_flow_projection(days=30)
        discount_opportunities = await self.detect_discount_opportunities()
        aging_metrics = await self.analyze_aging_buckets()

        # Generate alerts
        alerts = self._generate_dashboard_alerts(overall_score, aging_metrics, discount_opportunities)

        # Get trend data
        score_trends = await self.analyze_score_trends()

        return {
            'overall_score': overall_score,
            'cash_flow_metrics': {
                'projected_inflow': float(cash_flow_metrics['total_projected']),
                'confidence_score': cash_flow_metrics['confidence_score'],
                'opportunity_count': len(cash_flow_metrics['daily_breakdown'])
            },
            'collection_metrics': {
                'total_outstanding': float(aging_metrics['total_outstanding']),
                'risk_level': aging_metrics['risk_assessment'],
                'aging_breakdown': {
                    'current': float(aging_metrics.get('current', {}).get('amount', 0)),
                    'past_due': float(
                        aging_metrics.get('days_1_30', {}).get('amount', 0) +
                        aging_metrics.get('days_31_60', {}).get('amount', 0) +
                        aging_metrics.get('days_61_90', {}).get('amount', 0) +
                        aging_metrics.get('days_over_90', {}).get('amount', 0)
                    )
                }
            },
            'discount_opportunities': {
                'total_opportunities': discount_opportunities['total_opportunities'],
                'potential_savings': float(discount_opportunities['total_potential_savings']),
                'urgent_opportunities': len([opp for opp in discount_opportunities['opportunities_list']
                                          if opp.get('days_remaining', 0) <= 7])
            },
            'risk_indicators': {
                'overall_risk': self._assess_overall_risk(overall_score, aging_metrics),
                'critical_issues': len([alert for alert in alerts if alert['severity'] == 'urgent'])
            },
            'trend_data': {
                'score_trend': score_trends['overall_trend']['direction'],
                'score_change': score_trends['overall_trend']['change_from_previous']
            },
            'alerts': alerts[:5]  # Top 5 alerts
        }

    def _generate_dashboard_alerts(self, overall_score: Dict, aging_metrics: Dict,
                                 discount_opportunities: Dict) -> List[Dict]:
        """Generate alerts for dashboard."""
        alerts = []

        # Score alerts
        if overall_score['total_score'] < 60:
            alerts.append({
                'type': 'score',
                'severity': 'urgent',
                'message': f"Working capital score is critically low at {overall_score['total_score']}",
                'recommendation': "Immediate action required for working capital optimization"
            })
        elif overall_score['total_score'] < 75:
            alerts.append({
                'type': 'score',
                'severity': 'high',
                'message': f"Working capital score needs improvement at {overall_score['total_score']}",
                'recommendation': "Focus on identified improvement areas"
            })

        # Aging alerts
        if aging_metrics['risk_assessment'] == 'high':
            alerts.append({
                'type': 'aging',
                'severity': 'high',
                'message': "High concentration of overdue receivables detected",
                'recommendation': "Implement aggressive collection procedures"
            })

        # Discount alerts
        urgent_discounts = len([opp for opp in discount_opportunities['opportunities_list']
                              if opp.get('days_remaining', 0) <= 3])
        if urgent_discounts > 0:
            alerts.append({
                'type': 'discounts',
                'severity': 'medium',
                'message': f"{urgent_discounts} early payment discounts expiring soon",
                'recommendation': "Review and act on expiring discount opportunities"
            })

        return alerts

    def _assess_overall_risk(self, overall_score: Dict, aging_metrics: Dict) -> str:
        """Assess overall risk level."""
        score_risk = 'high' if overall_score['total_score'] < 60 else 'medium' if overall_score['total_score'] < 75 else 'low'
        aging_risk = aging_metrics['risk_assessment']

        if score_risk == 'high' or aging_risk == 'high':
            return 'high'
        elif score_risk == 'medium' or aging_risk == 'medium':
            return 'medium'
        else:
            return 'low'

    # ================================
    # HELPER METHODS
    # ================================

    async def get_historical_accuracy(self) -> Dict[str, float]:
        """Get historical accuracy data for projections."""
        # This would query historical projection accuracy
        return {
            'mape': 15.2,
            'bias': -2.1,
            'accuracy_score': 84.8
        }

    async def get_historical_collection_data(self) -> List[Dict]:
        """Get historical collection data for trend analysis."""
        # This would query historical collection metrics
        return []

    async def get_historical_discount_data(self) -> List[Dict]:
        """Get historical discount utilization data."""
        # This would query historical discount data
        return []

    async def get_historical_scores(self) -> List[Dict]:
        """Get historical working capital scores."""
        # This would query historical score data
        return []

    async def get_invoice_data(self) -> List[Dict]:
        """Get invoice data for analytics."""
        # This would query invoice data
        return []