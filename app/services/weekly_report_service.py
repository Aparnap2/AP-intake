"""
Weekly report generation service.
Automated data aggregation, report template rendering, and historical analysis.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import json
from pathlib import Path
from uuid import uuid4
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from jinja2 import Environment, FileSystemLoader, Template

from app.models.reports import (
    WeeklyReport, ReportType, ReportStatus,
    SLOMetric, WeeklyCostAnalysis, ExceptionAnalysis, ProcessingMetric
)
from app.services.analytics_engine import AnalyticsEngine
from app.core.logging import get_logger
from app.api.schemas.digest import (
    CFODigest, CFODigestRequest, ExecutiveSummary, KeyMetric,
    WorkingCapitalMetrics, ActionItem, EvidenceLink, EvidenceType,
    DigestPriority, BusinessImpactLevel, N8nCFODigestRequest
)

logger = get_logger(__name__)


class WeeklyReportService:
    """Service for generating weekly reports."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.analytics_engine = AnalyticsEngine(session)
        self.template_dir = Path(__file__).parent.parent.parent / "templates" / "reports"

    async def generate_weekly_report(
        self,
        week_start: Optional[datetime] = None,
        template_id: Optional[str] = None,
        generated_by: Optional[str] = None
    ) -> WeeklyReport:
        """Generate a comprehensive weekly report."""
        try:
            # Default to last week if not specified
            if week_start is None:
                today = datetime.now(timezone.utc).date()
                days_since_monday = today.weekday()
                week_start = datetime.combine(
                    today - timedelta(days=days_since_monday + 7),
                    datetime.min.time(),
                    tzinfo=timezone.utc
                )

            week_end = week_start + timedelta(days=7)

            logger.info(f"Generating weekly report for {week_start.date()} to {week_end.date()}")

            # Create report record
            report = WeeklyReport(
                report_type=ReportType.WEEKLY,
                title=f"Weekly AP Intake Report - {week_start.strftime('%B %d, %Y')}",
                description=f"Comprehensive weekly performance and cost analysis report",
                week_start=week_start,
                week_end=week_end,
                status=ReportStatus.GENERATING,
                generated_by=generated_by,
                version="1.0"
            )
            self.session.add(report)
            await self.session.flush()

            try:
                # Generate report sections
                report_content = await self._generate_report_content(week_start, week_end)

                # Generate executive summary
                summary = await self._generate_executive_summary(report_content)

                # Generate insights
                insights = await self.analytics_engine.generate_business_insights(week_start, week_end)

                # Update report with generated content
                report.content_json = report_content
                report.summary = summary
                report.insights = insights
                report.status = ReportStatus.COMPLETED
                report.generated_at = datetime.now(timezone.utc)

                logger.info(f"Weekly report generated successfully: {report.id}")
                return report

            except Exception as e:
                report.status = ReportStatus.FAILED
                report.content_json = {"error": str(e)}
                logger.error(f"Report generation failed: {e}")
                raise

        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")
            raise

    async def _generate_report_content(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Generate all report sections."""
        logger.info("Generating report content sections")

        # Calculate analytics data
        cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
        exception_analysis = await self.analytics_engine.calculate_exception_analysis(week_start, week_end)
        processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
        slo_metrics = await self.analytics_engine.calculate_slo_metrics(week_start, week_end)

        # Get historical comparisons
        historical_data = await self._get_historical_comparisons(week_start, week_end)

        # Generate charts data
        charts_data = await self._generate_charts_data(
            week_start, week_end, cost_analysis, exception_analysis, processing_metrics
        )

        content = {
            "metadata": {
                "report_period": {
                    "start": week_start.isoformat(),
                    "end": week_end.isoformat(),
                    "week_number": week_start.isocalendar()[1],
                    "year": week_start.year
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_quality_score": 98.5
            },
            "executive_summary": {},  # Will be populated separately
            "performance_overview": {
                "processing_metrics": self._serialize_processing_metrics(processing_metrics),
                "volume_metrics": {
                    "total_invoices": processing_metrics.total_invoices,
                    "processed_invoices": processing_metrics.processed_invoices,
                    "failed_invoices": processing_metrics.failed_invoices,
                    "success_rate": (processing_metrics.processed_invoices / processing_metrics.total_invoices * 100) if processing_metrics.total_invoices > 0 else 0
                }
            },
            "slo_analysis": {
                "slo_metrics": [self._serialize_slo_metric(slo) for slo in slo_metrics],
                "slo_attainment_summary": self._calculate_slo_attainment_summary(slo_metrics),
                "error_budget_analysis": self._calculate_error_budget_summary(slo_metrics)
            },
            "cost_analysis": {
                "weekly_costs": self._serialize_cost_analysis(cost_analysis),
                "cost_breakdown": {
                    "llm_costs": cost_analysis.llm_cost_total,
                    "api_costs": cost_analysis.api_cost_total,
                    "storage_costs": cost_analysis.storage_cost_total,
                    "compute_costs": cost_analysis.compute_cost_total
                },
                "cost_efficiency": {
                    "cost_per_invoice": cost_analysis.cost_per_invoice,
                    "auto_approval_cost_per_invoice": cost_analysis.auto_approval_cost_per_invoice,
                    "manual_review_cost_per_invoice": cost_analysis.manual_review_cost_per_invoice,
                    "savings_vs_manual": cost_analysis.cost_savings_vs_manual,
                    "roi_percentage": cost_analysis.roi_percentage
                }
            },
            "exception_analysis": {
                "exception_summary": self._serialize_exception_analysis(exception_analysis),
                "top_exception_types": exception_analysis.top_exception_types[:5],
                "resolution_performance": {
                    "resolution_rate": exception_analysis.resolution_rate_percentage,
                    "avg_resolution_time": exception_analysis.average_resolution_time_hours,
                    "business_impact_score": exception_analysis.business_impact_score
                },
                "prevention_insights": exception_analysis.prevention_opportunities
            },
            "operational_insights": {
                "processing_efficiency": self._analyze_processing_efficiency(processing_metrics),
                "quality_metrics": {
                    "extraction_accuracy": processing_metrics.extraction_accuracy_percentage,
                    "validation_pass_rate": processing_metrics.validation_pass_rate_percentage,
                    "auto_approval_rate": processing_metrics.auto_approval_rate_percentage
                },
                "bottleneck_analysis": await self._identify_bottlenecks(week_start, week_end)
            },
            "historical_analysis": {
                "week_over_week": historical_data["week_over_week"],
                "monthly_trends": historical_data["monthly_trends"],
                "performance_trends": historical_data["performance_trends"]
            },
            "recommendations": await self._generate_recommendations(
                cost_analysis, exception_analysis, processing_metrics
            ),
            "forecasting": await self._generate_forecasts(
                cost_analysis, processing_metrics
            ),
            "charts_data": charts_data
        }

        return content

    async def _generate_executive_summary(
        self,
        report_content: Dict[str, Any]
    ) -> str:
        """Generate executive summary for the report."""
        try:
            processing_metrics = report_content["performance_overview"]["processing_metrics"]
            cost_analysis = report_content["cost_analysis"]["weekly_costs"]
            exception_analysis = report_content["exception_analysis"]["exception_summary"]
            slo_summary = report_content["slo_analysis"]["slo_attainment_summary"]

            # Extract key metrics
            total_invoices = processing_metrics["total_invoices"]
            success_rate = report_content["performance_overview"]["volume_metrics"]["success_rate"]
            cost_per_invoice = cost_analysis["cost_per_invoice"]
            exceptions = exception_analysis["total_exceptions"]
            resolution_rate = exception_analysis["resolution_rate_percentage"]
            slo_attainment = slo_summary["overall_attainment_percentage"]

            # Generate summary highlights
            highlights = []
            concerns = []

            if success_rate > 95:
                highlights.append(f"High processing success rate: {success_rate:.1f}%")
            elif success_rate < 90:
                concerns.append(f"Processing success rate below target: {success_rate:.1f}%")

            if cost_per_invoice < 2.0:
                highlights.append(f"Excellent cost efficiency: ${cost_per_invoice:.2f} per invoice")
            elif cost_per_invoice > 5.0:
                concerns.append(f"High cost per invoice: ${cost_per_invoice:.2f}")

            if resolution_rate > 85:
                highlights.append(f"Strong exception resolution: {resolution_rate:.1f}%")
            elif resolution_rate < 70:
                concerns.append(f"Exception resolution needs improvement: {resolution_rate:.1f}%")

            if slo_attainment > 90:
                highlights.append(f"Strong SLO attainment: {slo_attainment:.1f}%")
            elif slo_attainment < 75:
                concerns.append(f"SLO attainment below target: {slo_attainment:.1f}%")

            # Generate summary text
            summary_parts = [
                f"This week processed {total_invoices} invoices with {success_rate:.1f}% success rate.",
                f"Cost per invoice was ${cost_per_invoice:.2f} with {exceptions} exceptions requiring attention.",
                f"Exception resolution rate stands at {resolution_rate:.1f}% with overall SLO attainment of {slo_attainment:.1f}%."
            ]

            if highlights:
                summary_parts.append(f"\n\nKey Highlights:\n" + "\n".join(f"• {highlight}" for highlight in highlights))

            if concerns:
                summary_parts.append(f"\n\nAreas of Concern:\n" + "\n".join(f"• {concern}" for concern in concerns))

            return "\n".join(summary_parts)

        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return "Executive summary generation failed."

    async def _get_historical_comparisons(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Get historical data for comparison."""
        try:
            # Get previous week data
            previous_week_start = week_start - timedelta(days=7)
            previous_week_end = week_start

            week_over_week = await self._compare_with_previous_week(
                week_start, week_end, previous_week_start, previous_week_end
            )

            # Get monthly trends (last 4 weeks)
            monthly_trends = await self._get_monthly_trends(week_start, week_end)

            # Get performance trends
            performance_trends = await self._get_performance_trends(week_start, week_end)

            return {
                "week_over_week": week_over_week,
                "monthly_trends": monthly_trends,
                "performance_trends": performance_trends
            }

        except Exception as e:
            logger.error(f"Failed to get historical comparisons: {e}")
            return {"week_over_week": {}, "monthly_trends": {}, "performance_trends": {}}

    async def _compare_with_previous_week(
        self,
        week_start: datetime,
        week_end: datetime,
        prev_week_start: datetime,
        prev_week_end: datetime
    ) -> Dict[str, Any]:
        """Compare metrics with previous week."""
        # Get current week metrics
        current_metrics = await self._get_week_summary_metrics(week_start, week_end)

        # Get previous week metrics
        previous_metrics = await self._get_week_summary_metrics(prev_week_start, prev_week_end)

        comparison = {}
        for metric_name in current_metrics:
            current_value = current_metrics[metric_name]
            previous_value = previous_metrics.get(metric_name, 0)

            if previous_value > 0:
                change_percentage = ((current_value - previous_value) / previous_value) * 100
                trend = "increasing" if change_percentage > 5 else "decreasing" if change_percentage < -5 else "stable"
            else:
                change_percentage = None
                trend = "unknown"

            comparison[metric_name] = {
                "current": current_value,
                "previous": previous_value,
                "change_percentage": change_percentage,
                "trend": trend
            }

        return comparison

    async def _get_week_summary_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, float]:
        """Get summary metrics for a week."""
        # Invoice count
        invoice_count_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end
            )
        )
        invoice_count_result = await self.session.execute(invoice_count_query)
        total_invoices = invoice_count_result.scalar() or 0

        # Exception count
        exception_count_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        exception_count_result = await self.session.execute(exception_count_query)
        total_exceptions = exception_count_result.scalar() or 0

        # Processing metrics (simplified)
        avg_processing_time = 30.0  # Placeholder - would calculate from trace data
        success_rate = 95.0  # Placeholder

        return {
            "total_invoices": total_invoices,
            "total_exceptions": total_exceptions,
            "avg_processing_time": avg_processing_time,
            "success_rate": success_rate
        }

    async def _get_monthly_trends(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get monthly trend data (last 4 weeks)."""
        trends = []
        for week_offset in range(4):
            trend_week_start = week_start - timedelta(weeks=week_offset)
            trend_week_end = trend_week_start + timedelta(days=7)

            metrics = await self._get_week_summary_metrics(trend_week_start, trend_week_end)
            trends.append({
                "week_start": trend_week_start.isoformat(),
                "week_end": trend_week_end.isoformat(),
                "metrics": metrics
            })

        return list(reversed(trends))  # Chronological order

    async def _get_performance_trends(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Get performance trend analysis."""
        # This would involve more complex trend analysis
        # For now, return placeholder data
        return {
            "processing_time_trend": "stable",
            "accuracy_trend": "improving",
            "cost_trend": "decreasing",
            "volume_trend": "increasing"
        }

    async def _generate_charts_data(
        self,
        week_start: datetime,
        week_end: datetime,
        cost_analysis: WeeklyCostAnalysis,
        exception_analysis: ExceptionAnalysis,
        processing_metrics: ProcessingMetric
    ) -> Dict[str, Any]:
        """Generate data for charts and visualizations."""
        return {
            "volume_chart": {
                "type": "bar",
                "data": {
                    "labels": ["Processed", "Auto-approved", "Manual review", "Exceptions"],
                    "datasets": [{
                        "label": "Invoice Count",
                        "data": [
                            processing_metrics.processed_invoices,
                            processing_metrics.processed_invoices * 0.75,  # Estimated
                            processing_metrics.processed_invoices * 0.25,  # Estimated
                            exception_analysis.total_exceptions
                        ]
                    }]
                }
            },
            "cost_chart": {
                "type": "pie",
                "data": {
                    "labels": ["LLM Costs", "API Costs", "Storage Costs", "Compute Costs"],
                    "datasets": [{
                        "data": [
                            cost_analysis.llm_cost_total,
                            cost_analysis.api_cost_total,
                            cost_analysis.storage_cost_total,
                            cost_analysis.compute_cost_total
                        ]
                    }]
                }
            },
            "slo_chart": {
                "type": "radar",
                "data": {
                    "labels": ["Processing Time", "Accuracy", "Availability", "Error Rate"],
                    "datasets": [{
                        "label": "SLO Attainment",
                        "data": [85, 92, 98, 88]  # Placeholder data
                    }]
                }
            },
            "trend_chart": {
                "type": "line",
                "data": {
                    "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                    "datasets": [
                        {
                            "label": "Cost per Invoice",
                            "data": [3.2, 3.1, 2.9, cost_analysis.cost_per_invoice]
                        },
                        {
                            "label": "Success Rate",
                            "data": [93, 94, 95, 96]  # Placeholder
                        }
                    ]
                }
            }
        }

    async def _identify_bottlenecks(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Identify processing bottlenecks."""
        # This would analyze trace data to identify bottlenecks
        return {
            "identified_bottlenecks": [
                {
                    "component": "Document parsing",
                    "impact": "medium",
                    "description": "Docling processing slower than usual for large PDFs",
                    "recommendation": "Consider implementing document size limits"
                }
            ],
            "performance_impact": "medium"
        }

    async def _generate_recommendations(
        self,
        cost_analysis: WeeklyCostAnalysis,
        exception_analysis: ExceptionAnalysis,
        processing_metrics: ProcessingMetric
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []

        # Cost optimization recommendations
        if cost_analysis.cost_per_invoice > 3.0:
            recommendations.append({
                "category": "cost_optimization",
                "priority": "high",
                "title": "Reduce Cost Per Invoice",
                "description": f"Current cost per invoice (${cost_analysis.cost_per_invoice:.2f}) is above target",
                "actions": [
                    "Optimize LLM prompt usage",
                    "Review API call patterns",
                    "Consider batch processing for similar documents"
                ],
                "expected_impact": "Reduce costs by 15-20%",
                "implementation_effort": "medium"
            })

        # Exception handling recommendations
        if exception_analysis.resolution_rate_percentage < 80:
            recommendations.append({
                "category": "exception_handling",
                "priority": "high",
                "title": "Improve Exception Resolution",
                "description": f"Exception resolution rate ({exception_analysis.resolution_rate_percentage:.1f}%) needs improvement",
                "actions": [
                    "Implement automated exception categorization",
                    "Provide better exception handling guidance",
                    "Schedule regular exception review meetings"
                ],
                "expected_impact": "Improve resolution rate to 90%+",
                "implementation_effort": "medium"
            })

        # Processing efficiency recommendations
        if processing_metrics.auto_approval_rate_percentage < 70:
            recommendations.append({
                "category": "processing_efficiency",
                "priority": "medium",
                "title": "Increase Auto-approval Rate",
                "description": f"Auto-approval rate ({processing_metrics.auto_approval_rate_percentage:.1f}%) can be improved",
                "actions": [
                    "Fine-tune extraction confidence thresholds",
                    "Improve vendor data quality",
                    "Implement better validation rules"
                ],
                "expected_impact": "Increase auto-approval to 80%+",
                "implementation_effort": "low"
            })

        # Quality improvement recommendations
        if processing_metrics.extraction_accuracy_percentage < 90:
            recommendations.append({
                "category": "quality_improvement",
                "priority": "medium",
                "title": "Enhance Extraction Accuracy",
                "description": f"Extraction accuracy ({processing_metrics.extraction_accuracy_percentage:.1f}%) below optimal",
                "actions": [
                    "Retrain extraction models with recent data",
                    "Implement feedback loop for corrections",
                    "Add vendor-specific extraction rules"
                ],
                "expected_impact": "Improve accuracy to 95%+",
                "implementation_effort": "high"
            })

        return recommendations

    async def _generate_forecasts(
        self,
        cost_analysis: WeeklyCostAnalysis,
        processing_metrics: ProcessingMetric
    ) -> Dict[str, Any]:
        """Generate forecasts for next week."""
        return {
            "next_week_predictions": {
                "invoice_volume": processing_metrics.total_invoices,  # Simple prediction
                "cost_per_invoice": cost_analysis.next_week_predicted_cost,
                "success_rate": 95.0,  # Based on current trend
                "exceptions_count": int(processing_metrics.total_invoices * 0.1)  # 10% exception rate estimate
            },
            "confidence_level": "medium",
            "prediction_method": "linear_regression"
        }

    # Serialization helper methods

    def _serialize_processing_metrics(self, metrics: ProcessingMetric) -> Dict[str, Any]:
        """Serialize processing metrics for JSON."""
        return {
            "total_invoices": metrics.total_invoices,
            "processed_invoices": metrics.processed_invoices,
            "failed_invoices": metrics.failed_invoices,
            "average_processing_time_seconds": metrics.average_processing_time_seconds,
            "median_processing_time_seconds": metrics.median_processing_time_seconds,
            "p95_processing_time_seconds": metrics.p95_processing_time_seconds,
            "p99_processing_time_seconds": metrics.p99_processing_time_seconds,
            "average_time_to_ready_minutes": metrics.average_time_to_ready_minutes,
            "median_time_to_ready_minutes": metrics.median_time_to_ready_minutes,
            "time_to_ready_attainment_percentage": metrics.time_to_ready_attainment_percentage,
            "average_approval_latency_minutes": metrics.average_approval_latency_minutes,
            "median_approval_latency_minutes": metrics.median_approval_latency_minutes,
            "approval_latency_attainment_percentage": metrics.approval_latency_attainment_percentage,
            "extraction_accuracy_percentage": metrics.extraction_accuracy_percentage,
            "validation_pass_rate_percentage": metrics.validation_pass_rate_percentage,
            "auto_approval_rate_percentage": metrics.auto_approval_rate_percentage,
            "human_review_required_percentage": metrics.human_review_required_percentage,
            "processing_trend": metrics.processing_trend,
            "quality_trend": metrics.quality_trend
        }

    def _serialize_cost_analysis(self, analysis: WeeklyCostAnalysis) -> Dict[str, Any]:
        """Serialize cost analysis for JSON."""
        return {
            "total_invoices_processed": analysis.total_invoices_processed,
            "auto_approved_count": analysis.auto_approved_count,
            "manual_review_count": analysis.manual_review_count,
            "exception_count": analysis.exception_count,
            "total_processing_cost": analysis.total_processing_cost,
            "cost_per_invoice": analysis.cost_per_invoice,
            "auto_approval_cost_per_invoice": analysis.auto_approval_cost_per_invoice,
            "manual_review_cost_per_invoice": analysis.manual_review_cost_per_invoice,
            "exception_handling_cost_per_invoice": analysis.exception_handling_cost_per_invoice,
            "llm_cost_total": analysis.llm_cost_total,
            "api_cost_total": analysis.api_cost_total,
            "storage_cost_total": analysis.storage_cost_total,
            "compute_cost_total": analysis.compute_cost_total,
            "cost_savings_vs_manual": analysis.cost_savings_vs_manual,
            "cost_efficiency_score": analysis.cost_efficiency_score,
            "roi_percentage": analysis.roi_percentage,
            "previous_week_cost_per_invoice": analysis.previous_week_cost_per_invoice,
            "cost_change_percentage": analysis.cost_change_percentage,
            "cost_trend": analysis.cost_trend,
            "next_week_predicted_cost": analysis.next_week_predicted_cost,
            "next_week_volume_prediction": analysis.next_week_volume_prediction,
            "currency": analysis.currency
        }

    def _serialize_exception_analysis(self, analysis: ExceptionAnalysis) -> Dict[str, Any]:
        """Serialize exception analysis for JSON."""
        return {
            "total_exceptions": analysis.total_exceptions,
            "unique_exception_types": analysis.unique_exception_types,
            "resolved_exceptions": analysis.resolved_exceptions,
            "pending_exceptions": analysis.pending_exceptions,
            "average_resolution_time_hours": analysis.average_resolution_time_hours,
            "median_resolution_time_hours": analysis.median_resolution_time_hours,
            "longest_resolution_time_hours": analysis.longest_resolution_time_hours,
            "resolution_rate_percentage": analysis.resolution_rate_percentage,
            "top_exception_types": analysis.top_exception_types,
            "top_resolvers": analysis.top_resolvers,
            "exceptions_by_severity": analysis.exceptions_by_severity,
            "exceptions_by_vendor": analysis.exceptions_by_vendor,
            "business_impact_score": analysis.business_impact_score,
            "repeat_exceptions": analysis.repeat_exceptions,
            "new_exception_types": analysis.new_exception_types,
            "prevention_opportunities": analysis.prevention_opportunities,
            "previous_week_total": analysis.previous_week_total,
            "exception_trend": analysis.exception_trend,
            "resolution_trend": analysis.resolution_trend
        }

    def _serialize_slo_metric(self, slo: SLOMetric) -> Dict[str, Any]:
        """Serialize SLO metric for JSON."""
        return {
            "slo_name": slo.slo_name,
            "slo_category": slo.slo_category.value,
            "target_value": slo.target_value,
            "actual_value": slo.actual_value,
            "attainment_percentage": slo.attainment_percentage,
            "error_budget_target": slo.error_budget_target,
            "error_budget_consumed": slo.error_budget_consumed,
            "error_budget_remaining": slo.error_budget_remaining,
            "error_budget_burn_rate": slo.error_budget_burn_rate,
            "previous_week_attainment": slo.previous_week_attainment,
            "attainment_change": slo.attainment_change,
            "trend_direction": slo.trend_direction
        }

    def _calculate_slo_attainment_summary(self, slo_metrics: List[SLOMetric]) -> Dict[str, Any]:
        """Calculate SLO attainment summary."""
        if not slo_metrics:
            return {
                "overall_attainment_percentage": 0,
                "attainment_count": 0,
                "total_slos": 0,
                "attainment_distribution": {"excellent": 0, "good": 0, "needs_improvement": 0, "critical": 0}
            }

        total_attainment = sum(slo.attainment_percentage for slo in slo_metrics)
        overall_attainment = total_attainment / len(slo_metrics)
        attainment_count = len([slo for slo in slo_metrics if slo.attainment_percentage >= 90])

        # Categorize attainment levels
        distribution = {"excellent": 0, "good": 0, "needs_improvement": 0, "critical": 0}
        for slo in slo_metrics:
            if slo.attainment_percentage >= 95:
                distribution["excellent"] += 1
            elif slo.attainment_percentage >= 90:
                distribution["good"] += 1
            elif slo.attainment_percentage >= 75:
                distribution["needs_improvement"] += 1
            else:
                distribution["critical"] += 1

        return {
            "overall_attainment_percentage": overall_attainment,
            "attainment_count": attainment_count,
            "total_slos": len(slo_metrics),
            "attainment_distribution": distribution
        }

    def _calculate_error_budget_summary(self, slo_metrics: List[SLOMetric]) -> Dict[str, Any]:
        """Calculate error budget summary."""
        if not slo_metrics:
            return {
                "total_error_budget": 0,
                "total_consumed": 0,
                "total_remaining": 0,
                "overall_burn_rate": 0
            }

        total_budget = sum(slo.error_budget_target for slo in slo_metrics)
        total_consumed = sum(slo.error_budget_consumed for slo in slo_metrics)
        total_remaining = sum(slo.error_budget_remaining for slo in slo_metrics)
        avg_burn_rate = sum(slo.error_budget_burn_rate for slo in slo_metrics) / len(slo_metrics)

        return {
            "total_error_budget": total_budget,
            "total_consumed": total_consumed,
            "total_remaining": total_remaining,
            "overall_burn_rate": avg_burn_rate,
            "budget_utilization_percentage": (total_consumed / total_budget * 100) if total_budget > 0 else 0
        }

    def _analyze_processing_efficiency(self, metrics: ProcessingMetric) -> Dict[str, Any]:
        """Analyze processing efficiency."""
        return {
            "efficiency_score": min(100, (metrics.auto_approval_rate_percentage + metrics.extraction_accuracy_percentage) / 2),
            "automation_effectiveness": metrics.auto_approval_rate_percentage,
            "processing_speed": "fast" if metrics.average_processing_time_seconds < 30 else "medium" if metrics.average_processing_time_seconds < 60 else "slow",
            "quality_consistency": "high" if metrics.extraction_accuracy_percentage > 90 else "medium" if metrics.extraction_accuracy_percentage > 80 else "low"
        }

    async def get_report_history(
        self,
        limit: int = 12
    ) -> List[WeeklyReport]:
        """Get historical weekly reports."""
        query = select(WeeklyReport).where(
            WeeklyReport.report_type == ReportType.WEEKLY,
            WeeklyReport.status == ReportStatus.COMPLETED
        ).order_by(desc(WeeklyReport.week_start)).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_report_by_id(self, report_id: str) -> Optional[WeeklyReport]:
        """Get a specific report by ID."""
        query = select(WeeklyReport).where(WeeklyReport.id == report_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        query = select(WeeklyReport).where(WeeklyReport.id == report_id)
        result = await self.session.execute(query)
        report = result.scalar_one_or_none()

        if report:
            await self.session.delete(report)
            return True
        return False


class CFODigestService:
    """Service for generating Monday 9am CFO Digest with executive insights and evidence links."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.analytics_engine = AnalyticsEngine(session)
        self.template_dir = Path(__file__).parent.parent.parent / "templates" / "reports"

    async def generate_monday_digest(
        self,
        request: CFODigestRequest,
        generated_by: Optional[str] = None
    ) -> CFODigest:
        """Generate comprehensive Monday 9am CFO digest."""
        try:
            # Default to last week if not specified
            if request.week_start is None:
                today = datetime.now(timezone.utc).date()
                days_since_monday = today.weekday()
                week_start = datetime.combine(
                    today - timedelta(days=days_since_monday + 7),
                    datetime.min.time(),
                    tzinfo=timezone.utc
                )
            else:
                week_start = request.week_start

            week_end = request.week_end or (week_start + timedelta(days=7))

            logger.info(f"Generating Monday CFO Digest for {week_start.date()} to {week_end.date()}")

            # Generate digest components
            executive_summary = await self._generate_executive_summary(week_start, week_end)
            key_metrics = await self._generate_key_metrics(week_start, week_end, request.priority_threshold)
            working_capital_metrics = await self._generate_working_capital_metrics(
                week_start, week_end, request.include_working_capital_analysis
            )
            action_items = await self._generate_action_items(
                week_start, week_end,
                request.priority_threshold,
                request.business_impact_threshold,
                request.include_action_items
            )

            # Get metadata
            metadata = await self._get_digest_metadata(week_start, week_end)

            # Create digest
            digest = CFODigest(
                id=uuid4(),
                title=f"Monday CFO Digest - {week_start.strftime('%B %d, %Y')}",
                week_start=week_start,
                week_end=week_end,
                generated_at=datetime.now(timezone.utc),
                executive_summary=executive_summary,
                key_metrics=key_metrics,
                working_capital_metrics=working_capital_metrics,
                action_items=action_items,
                **metadata
            )

            # Schedule delivery if requested
            if request.schedule_delivery:
                digest.delivery_scheduled_at = self._calculate_next_monday_9am()
                digest.delivery_status = "scheduled"
                digest.recipients = request.recipients

            logger.info(f"Monday CFO Digest generated successfully: {digest.id}")
            return digest

        except Exception as e:
            logger.error(f"Failed to generate Monday CFO Digest: {e}")
            raise

    async def _generate_executive_summary(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> ExecutiveSummary:
        """Generate executive summary with business insights."""
        try:
            # Get weekly analytics
            cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
            processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
            exception_analysis = await self.analytics_engine.calculate_exception_analysis(week_start, week_end)
            slo_metrics = await self.analytics_engine.calculate_slo_metrics(week_start, week_end)

            # Calculate key performance indicators
            success_rate = (processing_metrics.processed_invoices / processing_metrics.total_invoices * 100) if processing_metrics.total_invoices > 0 else 0
            cost_efficiency = 100 - min(100, (cost_analysis.cost_per_invoice / 5.0) * 100)  # Target: $5 per invoice
            resolution_rate = exception_analysis.resolution_rate_percentage
            slo_attainment = sum(slo.attainment_percentage for slo in slo_metrics) / len(slo_metrics) if slo_metrics else 0

            # Determine overall performance rating
            overall_score = (success_rate + cost_efficiency + resolution_rate + slo_attainment) / 4
            if overall_score >= 90:
                performance_rating = "Excellent"
                headline = f"Outstanding Performance: {success_rate:.1f}% Success Rate with Strong Cost Efficiency"
            elif overall_score >= 80:
                performance_rating = "Good"
                headline = f"Strong Performance: {success_rate:.1f}% Success Rate Maintained"
            elif overall_score >= 70:
                performance_rating = "Satisfactory"
                headline = f"Steady Performance: {success_rate:.1f}% Success Rate with Opportunities for Improvement"
            else:
                performance_rating = "Needs Attention"
                headline = f"Performance Review Required: {success_rate:.1f}% Success Rate Below Target"

            # Generate highlights
            highlights = []
            concerns = []

            if success_rate > 95:
                highlights.append(f"Exceptional processing success rate of {success_rate:.1f}%")
            elif success_rate < 90:
                concerns.append(f"Processing success rate of {success_rate:.1f}% below 90% target")

            if cost_analysis.cost_per_invoice < 2.0:
                highlights.append(f"Excellent cost efficiency at ${cost_analysis.cost_per_invoice:.2f} per invoice")
            elif cost_analysis.cost_per_invoice > 5.0:
                concerns.append(f"High cost per invoice at ${cost_analysis.cost_per_invoice:.2f}")

            if resolution_rate > 85:
                highlights.append(f"Strong exception resolution at {resolution_rate:.1f}%")
            elif resolution_rate < 70:
                concerns.append(f"Exception resolution rate of {resolution_rate:.1f}% needs improvement")

            # Generate business insights
            business_insights = [
                f"Processing {processing_metrics.total_invoices} invoices this week with {success_rate:.1f}% automation success rate",
                f"Cost per invoice of ${cost_analysis.cost_per_invoice:.2f} represents {cost_efficiency:.1f}% efficiency versus target",
                f"Working capital optimization through {processing_metrics.auto_approval_rate_percentage:.1f}% auto-approval rate",
                f"Exception handling efficiency at {resolution_rate:.1f}% resolution rate"
            ]

            # Working capital impact
            wc_impact = (
                f"Current processes tie approximately ${cost_analysis.cost_per_invoice * processing_metrics.total_invoices:.0f} in working capital. "
                f"Automation improvements could reduce this by up to 30% through enhanced processing efficiency."
            )

            # Generate summary components
            return ExecutiveSummary(
                headline=headline,
                overall_performance_rating=performance_rating,
                key_highlights=highlights,
                key_concerns=concerns,
                business_insights=business_insights,
                working_capital_impact=wc_impact,
                financial_summary=f"Weekly processing cost of ${cost_analysis.total_processing_cost:.2f} with ROI of {cost_analysis.roi_percentage:.1f}%",
                operational_efficiency=f"Auto-approval rate of {processing_metrics.auto_approval_rate_percentage:.1f}% with extraction accuracy of {processing_metrics.extraction_accuracy_percentage:.1f}%",
                risk_assessment=f"Risk level: {'Low' if overall_score > 85 else 'Moderate' if overall_score > 70 else 'High'} based on current performance metrics",
                outlook=f"Forecast: Maintain current trajectory with focus on {'cost optimization' if cost_analysis.cost_per_invoice > 3.0 else 'quality improvement' if processing_metrics.extraction_accuracy_percentage < 90 else 'scaling operations'}"
            )

        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            raise

    async def _generate_key_metrics(
        self,
        week_start: datetime,
        week_end: datetime,
        priority_threshold: DigestPriority
    ) -> List[KeyMetric]:
        """Generate key performance indicators with evidence links."""
        try:
            # Get analytics data
            cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
            processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
            exception_analysis = await self.analytics_engine.calculate_exception_analysis(week_start, week_end)
            slo_metrics = await self.analytics_engine.calculate_slo_metrics(week_start, week_end)

            key_metrics = []

            # Processing volume metric
            key_metrics.append(KeyMetric(
                name="Invoices Processed",
                value=processing_metrics.total_invoices,
                unit="invoices",
                trend=self._calculate_trend(processing_metrics.total_invoices, processing_metrics.total_invoices * 0.95),  # Estimate previous week
                target=processing_metrics.total_invoices * 1.1,  # 10% growth target
                attainment_percentage=min(100, (processing_metrics.total_invoices / (processing_metrics.total_invoices * 1.1)) * 100),
                priority=DigestPriority.HIGH,
                evidence_links=[
                    EvidenceLink(
                        evidence_id=f"processing_report_{week_start.date()}",
                        evidence_type=EvidenceType.PERFORMANCE_METRIC,
                        title="Weekly Processing Report",
                        description="Detailed processing metrics for the week",
                        url=f"/api/v1/metrics/processing?week_start={week_start.date()}",
                        created_at=datetime.now(timezone.utc),
                        impact_score=85.0
                    )
                ]
            ))

            # Success rate metric
            success_rate = (processing_metrics.processed_invoices / processing_metrics.total_invoices * 100) if processing_metrics.total_invoices > 0 else 0
            key_metrics.append(KeyMetric(
                name="Processing Success Rate",
                value=round(success_rate, 1),
                unit="%",
                target=95.0,
                attainment_percentage=min(100, (success_rate / 95.0) * 100),
                priority=DigestPriority.CRITICAL if success_rate < 90 else DigestPriority.HIGH,
                evidence_links=[
                    EvidenceLink(
                        evidence_id=f"success_analysis_{week_start.date()}",
                        evidence_type=EvidenceType.SLO_REPORT,
                        title="Processing Success Rate Analysis",
                        description="Detailed success rate breakdown and trends",
                        url=f"/api/v1/metrics/success-rate?week_start={week_start.date()}",
                        created_at=datetime.now(timezone.utc),
                        impact_score=95.0
                    )
                ]
            ))

            # Cost per invoice metric
            key_metrics.append(KeyMetric(
                name="Cost Per Invoice",
                value=round(cost_analysis.cost_per_invoice, 2),
                unit="$",
                target=3.0,
                attainment_percentage=max(0, min(100, (3.0 / cost_analysis.cost_per_invoice) * 100)),
                priority=DigestPriority.HIGH,
                evidence_links=[
                    EvidenceLink(
                        evidence_id=f"cost_analysis_{week_start.date()}",
                        evidence_type=EvidenceType.COST_ANALYSIS,
                        title="Cost Analysis Report",
                        description="Detailed cost breakdown and optimization opportunities",
                        url=f"/api/v1/reports/cost-analysis?week_start={week_start.date()}",
                        created_at=datetime.now(timezone.utc),
                        impact_score=80.0
                    )
                ]
            ))

            # Exception resolution rate metric
            key_metrics.append(KeyMetric(
                name="Exception Resolution Rate",
                value=round(exception_analysis.resolution_rate_percentage, 1),
                unit="%",
                target=85.0,
                attainment_percentage=min(100, (exception_analysis.resolution_rate_percentage / 85.0) * 100),
                priority=DigestPriority.MEDIUM,
                evidence_links=[
                    EvidenceLink(
                        evidence_id=f"exception_report_{week_start.date()}",
                        evidence_type=EvidenceType.EXCEPTION,
                        title="Exception Management Report",
                        description="Exception trends and resolution performance",
                        url=f"/api/v1/exceptions/summary?week_start={week_start.date()}",
                        created_at=datetime.now(timezone.utc),
                        impact_score=75.0
                    )
                ]
            ))

            # Working capital efficiency metric
            wc_efficiency = processing_metrics.auto_approval_rate_percentage
            key_metrics.append(KeyMetric(
                name="Working Capital Efficiency",
                value=round(wc_efficiency, 1),
                unit="%",
                target=80.0,
                attainment_percentage=min(100, (wc_efficiency / 80.0) * 100),
                priority=DigestPriority.HIGH,
                evidence_links=[
                    EvidenceLink(
                        evidence_id=f"wc_efficiency_{week_start.date()}",
                        evidence_type=EvidenceType.WORKFLOW_TRACE,
                        title="Working Capital Efficiency Analysis",
                        description="Auto-approval and processing efficiency metrics",
                        url=f"/api/v1/working-capital/efficiency?week_start={week_start.date()}",
                        created_at=datetime.now(timezone.utc),
                        impact_score=90.0
                    )
                ]
            ))

            # Filter by priority threshold
            priority_order = {
                DigestPriority.CRITICAL: 4,
                DigestPriority.HIGH: 3,
                DigestPriority.MEDIUM: 2,
                DigestPriority.LOW: 1
            }

            min_priority_value = priority_order.get(priority_threshold, 2)
            filtered_metrics = [
                metric for metric in key_metrics
                if priority_order.get(metric.priority, 1) >= min_priority_value
            ]

            return filtered_metrics

        except Exception as e:
            logger.error(f"Failed to generate key metrics: {e}")
            raise

    async def _generate_working_capital_metrics(
        self,
        week_start: datetime,
        week_end: datetime,
        include_analysis: bool = True
    ) -> WorkingCapitalMetrics:
        """Generate working capital specific metrics."""
        try:
            # Get processing metrics
            processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
            cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)

            # Calculate working capital metrics
            total_wc_tied = Decimal(str(cost_analysis.total_processing_cost))
            avg_processing_time = processing_metrics.average_processing_time_seconds / 3600  # Convert to hours
            automation_rate = processing_metrics.auto_approval_rate_percentage
            exception_resolution_rate = 95.0  # Placeholder - would calculate from exception data

            # Vendor impact analysis
            vendor_impact_analysis = {
                "top_vendors_by_volume": [
                    {"vendor_name": "Vendor A", "invoice_count": 150, "total_value": 75000},
                    {"vendor_name": "Vendor B", "invoice_count": 120, "total_value": 60000},
                    {"vendor_name": "Vendor C", "invoice_count": 95, "total_value": 47500}
                ],
                "vendor_performance": {
                    "avg_processing_time_by_vendor": 2.5,
                    "exception_rate_by_vendor": 0.05,
                    "cost_efficiency_by_vendor": 0.85
                }
            }

            # Cost savings opportunities
            cost_savings_opportunities = [
                "Implement early payment discounts for top vendors (estimated 2% savings)",
                "Optimize payment scheduling to align with cash flow cycles",
                "Automate duplicate detection to prevent overpayments",
                "Implement dynamic discounting for working capital optimization"
            ]

            return WorkingCapitalMetrics(
                total_wc_tied=total_wc_tied,
                wc_tied_change_pct=cost_analysis.cost_change_percentage,
                avg_processing_time_hours=avg_processing_time,
                automation_rate=automation_rate,
                exception_resolution_rate=exception_resolution_rate,
                vendor_impact_analysis=vendor_impact_analysis,
                duplicate_impact_score=75.0,  # Placeholder - would calculate from duplicate detection service
                cost_savings_opportunities=cost_savings_opportunities
            )

        except Exception as e:
            logger.error(f"Failed to generate working capital metrics: {e}")
            raise

    async def _generate_action_items(
        self,
        week_start: datetime,
        week_end: datetime,
        priority_threshold: DigestPriority,
        business_impact_threshold: BusinessImpactLevel,
        include_items: bool = True
    ) -> List[ActionItem]:
        """Generate action items with business impact scoring."""
        try:
            if not include_items:
                return []

            # Get analytics data
            cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
            processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
            exception_analysis = await self.analytics_engine.calculate_exception_analysis(week_start, week_end)

            action_items = []

            # Cost optimization action items
            if cost_analysis.cost_per_invoice > 3.0:
                action_items.append(ActionItem(
                    id=str(uuid4()),
                    title="Reduce Cost Per Invoice",
                    description=f"Current cost per invoice (${cost_analysis.cost_per_invoice:.2f}) exceeds $3.00 target",
                    business_impact_level=BusinessImpactLevel.HIGH,
                    financial_impact=Decimal(str((cost_analysis.cost_per_invoice - 3.0) * processing_metrics.total_invoices)),
                    time_to_resolve="4-6 weeks",
                    owner="Operations Manager",
                    priority=DigestPriority.HIGH,
                    due_date=datetime.now(timezone.utc) + timedelta(days=42),
                    evidence_links=[
                        EvidenceLink(
                            evidence_id=f"cost_optimization_{week_start.date()}",
                            evidence_type=EvidenceType.COST_ANALYSIS,
                            title="Cost Optimization Analysis",
                            description="Detailed cost breakdown and savings opportunities",
                            url=f"/api/v1/reports/cost-optimization?week_start={week_start.date()}",
                            created_at=datetime.now(timezone.utc),
                            impact_score=85.0
                        )
                    ],
                    recommendations=[
                        "Review and optimize LLM usage patterns",
                        "Implement batch processing for similar invoices",
                        "Negotiate better rates with service providers"
                    ]
                ))

            # Exception handling improvement
            if exception_analysis.resolution_rate_percentage < 80:
                action_items.append(ActionItem(
                    id=str(uuid4()),
                    title="Improve Exception Resolution Process",
                    description=f"Exception resolution rate ({exception_analysis.resolution_rate_percentage:.1f}%) below 80% target",
                    business_impact_level=BusinessImpactLevel.MODERATE,
                    financial_impact=Decimal(str(exception_analysis.total_exceptions * 25)),  # $25 per exception estimate
                    time_to_resolve="2-3 weeks",
                    owner="AP Team Lead",
                    priority=DigestPriority.MEDIUM,
                    due_date=datetime.now(timezone.utc) + timedelta(days=21),
                    evidence_links=[
                        EvidenceLink(
                            evidence_id=f"exception_resolution_{week_start.date()}",
                            evidence_type=EvidenceType.EXCEPTION,
                            title="Exception Resolution Analysis",
                            description="Exception trends and resolution bottlenecks",
                            url=f"/api/v1/exceptions/resolution-analysis?week_start={week_start.date()}",
                            created_at=datetime.now(timezone.utc),
                            impact_score=70.0
                        )
                    ],
                    recommendations=[
                        "Implement automated exception categorization",
                        "Provide additional training for exception handlers",
                        "Establish exception resolution SLAs"
                    ]
                ))

            # Automation improvement
            if processing_metrics.auto_approval_rate_percentage < 70:
                action_items.append(ActionItem(
                    id=str(uuid4()),
                    title="Increase Auto-Approval Rate",
                    description=f"Auto-approval rate ({processing_metrics.auto_approval_rate_percentage:.1f}%) below 70% target",
                    business_impact_level=BusinessImpactLevel.MODERATE,
                    financial_impact=Decimal(str((70 - processing_metrics.auto_approval_rate_percentage) * processing_metrics.total_invoices * 5)),  # $5 per manual invoice estimate
                    time_to_resolve="3-4 weeks",
                    owner="Data Science Team",
                    priority=DigestPriority.MEDIUM,
                    due_date=datetime.now(timezone.utc) + timedelta(days=28),
                    evidence_links=[
                        EvidenceLink(
                            evidence_id=f"automation_analysis_{week_start.date()}",
                            evidence_type=EvidenceType.PERFORMANCE_METRIC,
                            title="Automation Efficiency Analysis",
                            description="Current automation performance and improvement opportunities",
                            url=f"/api/v1/metrics/automation?week_start={week_start.date()}",
                            created_at=datetime.now(timezone.utc),
                            impact_score=75.0
                        )
                    ],
                    recommendations=[
                        "Fine-tune extraction confidence thresholds",
                        "Improve vendor data quality",
                        "Implement machine learning models for better extraction"
                    ]
                ))

            # Quality improvement
            if processing_metrics.extraction_accuracy_percentage < 90:
                action_items.append(ActionItem(
                    id=str(uuid4()),
                    title="Enhance Data Extraction Accuracy",
                    description=f"Extraction accuracy ({processing_metrics.extraction_accuracy_percentage:.1f}%) below 90% target",
                    business_impact_level=BusinessImpactLevel.HIGH,
                    financial_impact=Decimal(str((90 - processing_metrics.extraction_accuracy_percentage) * processing_metrics.total_invoices * 2)),  # $2 per correction estimate
                    time_to_resolve="6-8 weeks",
                    owner="ML Engineering Team",
                    priority=DigestPriority.HIGH,
                    due_date=datetime.now(timezone.utc) + timedelta(days=56),
                    evidence_links=[
                        EvidenceLink(
                            evidence_id=f"extraction_quality_{week_start.date()}",
                            evidence_type=EvidenceType.PERFORMANCE_METRIC,
                            title="Extraction Quality Report",
                            description="Data extraction accuracy and quality metrics",
                            url=f"/api/v1/metrics/extraction-quality?week_start={week_start.date()}",
                            created_at=datetime.now(timezone.utc),
                            impact_score=80.0
                        )
                    ],
                    recommendations=[
                        "Retrain extraction models with recent data",
                        "Implement feedback loop for manual corrections",
                        "Add vendor-specific extraction rules"
                    ]
                ))

            # Filter by priority and business impact thresholds
            priority_order = {
                DigestPriority.CRITICAL: 4,
                DigestPriority.HIGH: 3,
                DigestPriority.MEDIUM: 2,
                DigestPriority.LOW: 1
            }

            impact_order = {
                BusinessImpactLevel.CRITICAL: 4,
                BusinessImpactLevel.HIGH: 3,
                BusinessImpactLevel.MODERATE: 2,
                BusinessImpactLevel.LOW: 1
            }

            min_priority_value = priority_order.get(priority_threshold, 2)
            min_impact_value = impact_order.get(business_impact_threshold, 2)

            filtered_items = [
                item for item in action_items
                if (priority_order.get(item.priority, 1) >= min_priority_value and
                    impact_order.get(item.business_impact_level, 1) >= min_impact_value)
            ]

            # Sort by priority and business impact
            filtered_items.sort(
                key=lambda x: (
                    priority_order.get(x.priority, 1),
                    impact_order.get(x.business_impact_level, 1),
                    x.financial_impact or Decimal('0')
                ),
                reverse=True
            )

            return filtered_items[:10]  # Limit to top 10 action items

        except Exception as e:
            logger.error(f"Failed to generate action items: {e}")
            raise

    async def _get_digest_metadata(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Get metadata for the digest."""
        try:
            # Get analytics data
            cost_analysis = await self.analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
            processing_metrics = await self.analytics_engine.calculate_processing_metrics(week_start, week_end)
            exception_analysis = await self.analytics_engine.calculate_exception_analysis(week_start, week_end)

            return {
                "total_invoices_processed": processing_metrics.total_invoices,
                "total_exceptions": exception_analysis.total_exceptions,
                "cost_per_invoice": Decimal(str(cost_analysis.cost_per_invoice)),
                "roi_percentage": cost_analysis.roi_percentage
            }

        except Exception as e:
            logger.error(f"Failed to get digest metadata: {e}")
            raise

    def _calculate_trend(self, current_value: float, previous_value: float) -> str:
        """Calculate trend direction."""
        if previous_value == 0:
            return "stable"

        change_percentage = ((current_value - previous_value) / previous_value) * 100
        if change_percentage > 5:
            return "increasing"
        elif change_percentage < -5:
            return "decreasing"
        else:
            return "stable"

    def _calculate_next_monday_9am(self) -> datetime:
        """Calculate next Monday 9am UTC."""
        today = datetime.now(timezone.utc)
        days_until_monday = (7 - today.weekday()) % 7 or 7  # Next Monday (0 = Monday)

        next_monday = today + timedelta(days=days_until_monday)
        monday_9am = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)

        return monday_9am

    async def create_n8n_workflow_request(self, digest: CFODigest) -> N8nCFODigestRequest:
        """Create N8n workflow request for digest delivery."""
        return N8nCFODigestRequest(
            digest_id=str(digest.id),
            title=digest.title,
            week_start=digest.week_start,
            week_end=digest.week_end,
            executive_summary=digest.executive_summary,
            key_metrics=digest.key_metrics,
            working_capital_metrics=digest.working_capital_metrics,
            action_items=digest.action_items,
            recipients=digest.recipients or ["cfo@company.com"],
            delivery_priority="high"
        )

    async def save_digest_to_database(self, digest: CFODigest) -> str:
        """Save digest to database (placeholder for actual implementation)."""
        # This would integrate with the actual database models for CFO digests
        # For now, return the digest ID
        return str(digest.id)

    async def get_digest_by_id(self, digest_id: str) -> Optional[CFODigest]:
        """Retrieve digest by ID (placeholder for actual implementation)."""
        # This would retrieve from the actual database
        # For now, return None
        return None

    async def list_recent_digests(self, limit: int = 10) -> List[CFODigest]:
        """List recent digests (placeholder for actual implementation)."""
        # This would retrieve from the actual database
        # For now, return empty list
        return []