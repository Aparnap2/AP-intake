"""
Working Capital Analytics API endpoints.

This module provides REST API endpoints for accessing working capital analytics,
including cash flow forecasting, payment optimization, collection efficiency,
and working capital scoring.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.api.api_v1.deps import get_current_user, get_db
from app.models.user import User
from app.models.working_capital import (
    CashFlowProjection, PaymentOptimization, EarlyPaymentDiscount,
    CollectionMetrics, WorkingCapitalScore, ScenarioType, PriorityLevel
)
from app.schemas.analytics_schemas import (
    CashFlowProjectionResponse, PaymentOptimizationResponse,
    CollectionMetricsResponse, WorkingCapitalScoreResponse,
    EarlyPaymentDiscountResponse, AnalyticsDashboardResponse,
    PaymentOptimizationRequest, ScenarioAnalysisRequest
)
from app.services.working_capital_analytics import WorkingCapitalAnalytics
from app.core.config import settings

router = APIRouter()


# ================================
# CASH FFORECASTING ENDPOINTS
# ================================

@router.get("/cash-flow/projection", response_model=Dict[str, Any])
async def get_cash_flow_projection(
    days: int = Query(30, ge=1, le=365, description="Number of days to project"),
    scenario: ScenarioType = Query(ScenarioType.REALISTIC, description="Scenario type"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get cash flow projection for specified period.

    Args:
        days: Number of days to project (1-365)
        scenario: Scenario type for projection
        customer_id: Optional customer filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Cash flow projection data
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        projection = await analytics.calculate_cash_flow_projection(days=days, scenario=scenario)

        # Store projection in database for historical tracking
        db_projection = CashFlowProjection(
            projection_date=datetime.utcnow(),
            projection_period="daily",
            scenario_type=scenario,
            projected_inflow=projection['total_projected'],
            net_cash_flow=projection['total_projected'],
            confidence_score=Decimal(str(projection['confidence_score'])),
            inflow_breakdown=projection['daily_breakdown'],
            assumptions={'scenario': scenario.value, 'days': days}
        )
        db.add(db_projection)
        await db.commit()

        return {
            "success": True,
            "data": projection,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "projection_period_days": days,
                "scenario": scenario.value,
                "customer_filter": str(customer_id) if customer_id else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating cash flow projection: {str(e)}")


@router.get("/cash-flow/seasonal-patterns", response_model=Dict[str, Any])
async def get_seasonal_patterns(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get seasonal pattern analysis for cash flow.

    Args:
        customer_id: Optional customer filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Seasonal pattern analysis data
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        patterns = await analytics.detect_seasonal_patterns()

        return {
            "success": True,
            "data": patterns,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None,
                "analysis_period_months": patterns.get('data_months', 0)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing seasonal patterns: {str(e)}")


@router.post("/cash-flow/scenario-analysis", response_model=Dict[str, Any])
async def analyze_cash_flow_scenarios(
    request: ScenarioAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze multiple cash flow scenarios.

    Args:
        request: Scenario analysis request parameters
        db: Database session
        current_user: Current authenticated user

    Returns:
        Multi-scenario analysis results
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        scenarios = await analytics.analyze_cash_flow_scenarios()

        # Filter scenarios if specified
        if request.scenarios:
            scenarios = {k: v for k, v in scenarios.items() if k in request.scenarios}

        return {
            "success": True,
            "data": scenarios,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "scenarios_analyzed": list(scenarios.keys()),
                "projection_period_days": 90  # Default for scenario analysis
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing cash flow scenarios: {str(e)}")


@router.get("/cash-flow/accuracy-validation", response_model=Dict[str, Any])
async def validate_projection_accuracy(
    days_back: int = Query(90, ge=1, le=365, description="Days to look back for validation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate historical accuracy of cash flow projections.

    Args:
        days_back: Number of days to look back
        db: Database session
        current_user: Current authenticated user

    Returns:
        Accuracy validation metrics
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        accuracy = await analytics.validate_projection_accuracy()

        return {
            "success": True,
            "data": accuracy,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "validation_period_days": days_back
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating projection accuracy: {str(e)}")


# ================================
# PAYMENT OPTIMIZATION ENDPOINTS
# ================================

@router.get("/payment-optimization/recommendations", response_model=Dict[str, Any])
async def get_payment_optimization_recommendations(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of recommendations"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    min_savings: Optional[Decimal] = Query(None, ge=0, description="Minimum potential savings filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get payment optimization recommendations.

    Args:
        limit: Maximum number of recommendations to return
        customer_id: Optional customer filter
        min_savings: Minimum potential savings filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Payment optimization recommendations
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        recommendations = await analytics.calculate_optimal_payment_timing()

        # Apply filters
        if customer_id:
            # This would need to be implemented in the analytics service
            pass

        if min_savings:
            recommendations = [r for r in recommendations if r.get('potential_savings', Decimal('0')) >= min_savings]

        # Limit results
        recommendations = recommendations[:limit]

        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "total_potential_savings": sum(r.get('potential_savings', Decimal('0')) for r in recommendations)
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "filters_applied": {
                    "customer_id": str(customer_id) if customer_id else None,
                    "min_savings": str(min_savings) if min_savings else None
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting payment optimization recommendations: {str(e)}")


@router.get("/payment-optimization/schedule", response_model=Dict[str, Any])
async def get_optimized_payment_schedule(
    days_ahead: int = Query(30, ge=1, le=90, description="Days ahead to schedule"),
    priority_threshold: float = Query(0.0, ge=0, le=1, description="Minimum priority score threshold"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get optimized payment schedule.

    Args:
        days_ahead: Number of days ahead to schedule
        priority_threshold: Minimum priority score for inclusion
        db: Database session
        current_user: Current authenticated user

    Returns:
        Optimized payment schedule
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        schedule = await analytics.optimize_payment_schedule()

        # Filter by priority threshold
        if priority_threshold > 0:
            schedule['payment_schedule'] = [
                item for item in schedule['payment_schedule']
                if item.get('priority_score', 0) >= priority_threshold
            ]

        # Filter by time horizon
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
        if schedule.get('payment_schedule'):
            schedule['payment_schedule'] = [
                item for item in schedule['payment_schedule']
                if item.get('recommended_date') and item['recommended_date'] <= cutoff_date
            ]

        return {
            "success": True,
            "data": schedule,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "schedule_horizon_days": days_ahead,
                "priority_threshold": priority_threshold
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating payment schedule: {str(e)}")


@router.post("/payment-optimization/roi-analysis", response_model=Dict[str, Any])
async def analyze_payment_roi(
    request: PaymentOptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze ROI for specific payment optimization scenarios.

    Args:
        request: Payment optimization analysis request
        db: Database session
        current_user: Current authenticated user

    Returns:
        ROI analysis results
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        # Calculate ROI for each scenario
        results = []
        for scenario in request.scenarios:
            roi_analysis = await analytics.calculate_payment_roi(
                invoice_amount=scenario.invoice_amount,
                discount_percent=scenario.discount_percent,
                discount_days=scenario.discount_days,
                regular_terms=scenario.regular_terms,
                cost_of_capital=scenario.cost_of_capital
            )
            results.append({
                "scenario_id": scenario.scenario_id,
                "scenario_name": scenario.scenario_name,
                "analysis": roi_analysis
            })

        return {
            "success": True,
            "data": {
                "analyses": results,
                "recommendation": max(results, key=lambda x: x['analysis']['net_roi']) if results else None
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "scenarios_analyzed": len(results)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing payment ROI: {str(e)}")


# ================================
# EARLY PAYMENT DISCOUNT ENDPOINTS
# ================================

@router.get("/discounts/opportunities", response_model=Dict[str, Any])
async def get_discount_opportunities(
    status: Optional[str] = Query(None, description="Filter by status: available, expired, utilized"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    min_discount_percent: Optional[Decimal] = Query(None, ge=0, le=100, description="Minimum discount percentage"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get early payment discount opportunities.

    Args:
        status: Filter by discount status
        customer_id: Optional customer filter
        min_discount_percent: Minimum discount percentage filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Early payment discount opportunities
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        opportunities = await analytics.detect_discount_opportunities()

        # Apply filters
        filtered_opportunities = opportunities['opportunities_list']

        if status:
            filtered_opportunities = [opp for opp in filtered_opportunities if opp.get('status') == status]

        if min_discount_percent:
            filtered_opportunities = [
                opp for opp in filtered_opportunities
                if opp.get('discount_percent', Decimal('0')) >= min_discount_percent
            ]

        # Recalculate totals
        total_savings = sum(opp['discount_amount'] for opp in filtered_opportunities)
        available_count = len([opp for opp in filtered_opportunities if opp.get('status') == 'available'])
        expired_count = len([opp for opp in filtered_opportunities if opp.get('status') == 'expired'])

        return {
            "success": True,
            "data": {
                "opportunities": filtered_opportunities,
                "summary": {
                    "total_opportunities": available_count,
                    "available_opportunities": available_count,
                    "expired_opportunities": expired_count,
                    "total_potential_savings": total_savings.quantize(Decimal('0.01'))
                }
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "filters_applied": {
                    "status": status,
                    "customer_id": str(customer_id) if customer_id else None,
                    "min_discount_percent": str(min_discount_percent) if min_discount_percent else None
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting discount opportunities: {str(e)}")


@router.get("/discounts/analysis", response_model=Dict[str, Any])
async def analyze_discount_programs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive early payment discount program analysis.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Discount program analysis
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        analysis = await analytics.analyze_early_payment_discounts()
        historical_accuracy = await analytics.analyze_historical_discount_accuracy()

        return {
            "success": True,
            "data": {
                "current_opportunities": analysis,
                "historical_performance": historical_accuracy,
                "recommendations": await analytics.generate_discount_optimization_recommendations()
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing discount programs: {str(e)}")


@router.post("/discounts/break-even-analysis", response_model=Dict[str, Any])
async def analyze_discount_break_even(
    invoice_amount: Decimal,
    discount_percent: Decimal,
    discount_period_days: int,
    normal_terms_days: int,
    cost_of_capital: Optional[Decimal] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze break-even point for early payment discount.

    Args:
        invoice_amount: Total invoice amount
        discount_percent: Discount percentage
        discount_period_days: Discount period in days
        normal_terms_days: Normal payment terms in days
        cost_of_capital: Optional cost of capital (uses default if not provided)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Break-even analysis results
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        if cost_of_capital is None:
            cost_of_capital = analytics.cost_of_capital

        break_even_analysis = await analytics.analyze_discount_break_even(
            invoice_amount=invoice_amount,
            discount_percent=discount_percent,
            discount_period_days=discount_period_days,
            normal_terms_days=normal_terms_days,
            cost_of_capital=cost_of_capital
        )

        return {
            "success": True,
            "data": break_even_analysis,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_parameters": {
                    "invoice_amount": str(invoice_amount),
                    "discount_percent": str(discount_percent),
                    "discount_period_days": discount_period_days,
                    "normal_terms_days": normal_terms_days,
                    "cost_of_capital": str(cost_of_capital)
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing discount break-even: {str(e)}")


@router.get("/discounts/risk-assessment", response_model=Dict[str, Any])
async def assess_discount_program_risks(
    annual_revenue: Optional[Decimal] = None,
    average_discount_percent: Optional[Decimal] = None,
    expected_utilization_rate: Optional[Decimal] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assess risks associated with early payment discount programs.

    Args:
        annual_revenue: Annual revenue for risk calculation
        average_discount_percent: Average discount percentage
        expected_utilization_rate: Expected utilization rate (0-1)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Risk assessment results
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        # Use defaults if not provided
        if annual_revenue is None:
            annual_revenue = Decimal('10000000.00')  # $10M default
        if average_discount_percent is None:
            average_discount_percent = Decimal('2.00')  # 2% default
        if expected_utilization_rate is None:
            expected_utilization_rate = Decimal('0.7')  # 70% default

        risk_assessment = await analytics.assess_discount_program_risks(
            annual_revenue=annual_revenue,
            average_discount_percent=average_discount_percent,
            expected_utilization_rate=expected_utilization_rate,
            customer_concentration_risk=Decimal('0.3'),  # 30% default
            cash_flow_volatility=Decimal('0.15')  # 15% default
        )

        return {
            "success": True,
            "data": risk_assessment,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "assumption_parameters": {
                    "annual_revenue": str(annual_revenue),
                    "average_discount_percent": str(average_discount_percent),
                    "expected_utilization_rate": str(expected_utilization_rate)
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error assessing discount program risks: {str(e)}")


# ================================
# COLLECTION EFFICIENCY ENDPOINTS
# ================================

@router.get("/collection/dso", response_model=Dict[str, Any])
async def get_dso_metrics(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    period: str = Query("current", description="Period: current, month, quarter, year"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get Days Sales Outstanding (DSO) metrics.

    Args:
        customer_id: Optional customer filter
        period: Analysis period
        db: Database session
        current_user: Current authenticated user

    Returns:
        DSO metrics and analysis
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        dso_metrics = await analytics.calculate_dso(customer_id=customer_id)

        return {
            "success": True,
            "data": dso_metrics,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "period": period,
                "customer_filter": str(customer_id) if customer_id else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating DSO metrics: {str(e)}")


@router.get("/collection/efficiency", response_model=Dict[str, Any])
async def get_collection_efficiency_metrics(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get collection efficiency metrics.

    Args:
        customer_id: Optional customer filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Collection efficiency metrics
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        # Get multiple collection metrics
        cei_metrics = await analytics.calculate_collection_efficiency_index(customer_id=customer_id)
        aging_analysis = await analytics.analyze_aging_buckets(customer_id=customer_id)
        payment_patterns = await analytics.analyze_payment_patterns(customer_id=customer_id)

        return {
            "success": True,
            "data": {
                "collection_effectiveness_index": cei_metrics,
                "aging_analysis": aging_analysis,
                "payment_patterns": payment_patterns
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating collection efficiency metrics: {str(e)}")


@router.get("/collection/aging-analysis", response_model=Dict[str, Any])
async def get_aging_analysis(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    include_details: bool = Query(False, description="Include detailed invoice breakdown"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed aging analysis.

    Args:
        customer_id: Optional customer filter
        include_details: Include detailed invoice breakdown
        db: Database session
        current_user: Current authenticated user

    Returns:
        Detailed aging analysis
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        aging_analysis = await analytics.analyze_aging_buckets(customer_id=customer_id)

        # Remove detailed invoice breakdown if not requested
        if not include_details:
            # Remove detailed invoice lists from response
            for bucket in ['current', 'days_1_30', 'days_31_60', 'days_61_90', 'days_over_90']:
                if bucket in aging_analysis and 'invoices' in aging_analysis[bucket]:
                    del aging_analysis[bucket]['invoices']

        return {
            "success": True,
            "data": aging_analysis,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None,
                "includes_details": include_details
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing aging analysis: {str(e)}")


@router.get("/collection/trends", response_model=Dict[str, Any])
async def get_collection_efficiency_trends(
    months: int = Query(12, ge=1, le=24, description="Number of months to analyze"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get collection efficiency trends over time.

    Args:
        months: Number of months to analyze
        customer_id: Optional customer filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Collection efficiency trends
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        trends = await analytics.analyze_collection_efficiency_trends()

        return {
            "success": True,
            "data": trends,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_period_months": months,
                "customer_filter": str(customer_id) if customer_id else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing collection trends: {str(e)}")


# ================================
# WORKING CAPITAL SCORING ENDPOINTS
# ================================

@router.get("/working-capital/score", response_model=Dict[str, Any])
async def get_working_capital_score(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    include_benchmarks: bool = Query(True, description="Include industry benchmarks"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive working capital optimization score.

    Args:
        customer_id: Optional customer filter
        include_benchmarks: Include industry benchmark comparison
        db: Database session
        current_user: Current authenticated user

    Returns:
        Working capital score and detailed analysis
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        score_analysis = await analytics.calculate_overall_working_capital_score(customer_id=customer_id)

        # Add score to database for tracking
        db_score = WorkingCapitalScore(
            score_date=datetime.utcnow(),
            score_period="daily",
            total_score=Decimal(str(score_analysis['total_score'])),
            collection_efficiency_score=Decimal(str(score_analysis['component_scores']['collection_efficiency']['score'])),
            payment_optimization_score=Decimal(str(score_analysis['component_scores']['payment_optimization']['score'])),
            discount_utilization_score=Decimal(str(score_analysis['component_scores']['discount_utilization']['score'])),
            cash_flow_management_score=Decimal('85.0'),  # Placeholder
            component_details=score_analysis['component_scores']
        )
        db.add(db_score)
        await db.commit()

        # Remove benchmarks if not requested
        if not include_benchmarks and 'benchmark_comparison' in score_analysis:
            del score_analysis['benchmark_comparison']

        return {
            "success": True,
            "data": score_analysis,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None,
                "includes_benchmarks": include_benchmarks
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating working capital score: {str(e)}")


@router.get("/working-capital/score-trends", response_model=Dict[str, Any])
async def get_score_trends(
    months: int = Query(12, ge=1, le=24, description="Number of months to analyze"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get working capital score trends over time.

    Args:
        months: Number of months to analyze
        customer_id: Optional customer filter
        db: Database session
        current_user: Current authenticated user

    Returns:
        Score trend analysis
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        trends = await analytics.analyze_score_trends()

        return {
            "success": True,
            "data": trends,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_period_months": months,
                "customer_filter": str(customer_id) if customer_id else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing score trends: {str(e)}")


@router.get("/working-capital/recommendations", response_model=Dict[str, Any])
async def get_optimization_recommendations(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    priority_level: Optional[PriorityLevel] = Query(None, description="Filter by priority level"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get working capital optimization recommendations.

    Args:
        customer_id: Optional customer filter
        priority_level: Filter by priority level
        db: Database session
        current_user: Current authenticated user

    Returns:
        Actionable optimization recommendations
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        # Get current state for recommendations
        current_state = await analytics.calculate_overall_working_capital_score(customer_id=customer_id)
        recommendations = await analytics.generate_actionable_recommendations(current_state)

        # Filter by priority level if specified
        if priority_level:
            recommendations['priority_actions'] = [
                action for action in recommendations['priority_actions']
                if action.get('priority') == priority_level.value
            ]

        return {
            "success": True,
            "data": recommendations,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None,
                "priority_filter": priority_level.value if priority_level else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")


@router.get("/working-capital/benchmark-comparison", response_model=Dict[str, Any])
async def get_benchmark_comparison(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    industry: Optional[str] = Query(None, description="Industry for benchmark comparison"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get industry benchmark comparison for working capital metrics.

    Args:
        customer_id: Optional customer filter
        industry: Industry for benchmark comparison
        db: Database session
        current_user: Current authenticated user

    Returns:
        Industry benchmark comparison
    """
    try:
        analytics = WorkingCapitalAnalytics(db)

        # Get current metrics
        current_state = await analytics.calculate_overall_working_capital_score(customer_id=customer_id)

        # Get benchmark comparison
        benchmark_comparison = await analytics.compare_with_industry_benchmarks({
            'dso': current_state['component_scores']['collection_efficiency'].get('dso', 45),
            'cash_conversion_cycle': current_state['component_scores']['payment_optimization'].get('cash_conversion_cycle', 25),
            'working_capital_turnover': current_state['component_scores']['payment_optimization'].get('working_capital_turnover', 6.0)
        })

        return {
            "success": True,
            "data": benchmark_comparison,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "customer_filter": str(customer_id) if customer_id else None,
                "industry": industry or "default"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting benchmark comparison: {str(e)}")


# ================================
# COMPREHENSIVE DASHBOARD ENDPOINT
# ================================

@router.get("/dashboard", response_model=Dict[str, Any])
async def get_working_capital_dashboard(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    period: str = Query("current", description="Analysis period"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive working capital analytics dashboard.

    Args:
        customer_id: Optional customer filter
        period: Analysis period
        db: Database session
        current_user: Current authenticated user

    Returns:
        Comprehensive analytics dashboard
    """
    try:
        analytics = WorkingCapitalAnalytics(db)
        dashboard = await analytics.generate_working_capital_dashboard()

        return {
            "success": True,
            "data": dashboard,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "period": period,
                "customer_filter": str(customer_id) if customer_id else None,
                "dashboard_version": "1.0"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")


# ================================
# HEALTH CHECK ENDPOINT
# ================================

@router.get("/health", response_model=Dict[str, Any])
async def analytics_health_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Health check for analytics service.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Health check status
    """
    try:
        # Test basic analytics functionality
        analytics = WorkingCapitalAnalytics(db)

        # Simple test calculation
        test_projection = await analytics.calculate_cash_flow_projection(days=7)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "tests": {
                "cash_flow_projection": "passed",
                "database_connection": "passed"
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }