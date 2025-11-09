"""
Business intelligence analytics engine for weekly reporting.
Calculates business insights, cost analysis, and performance metrics.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice, InvoiceStatus, Exception
from app.models.observability import PerformanceMetric, TraceSpan
from app.models.reports import (
    SLOMetric, WeeklyCostAnalysis, ExceptionAnalysis, ProcessingMetric,
    SLOCategory
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsEngine:
    """Business intelligence analytics engine."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.cost_per_llm_token = 0.000002  # $2 per 1M tokens (adjust based on actual rates)
        self.cost_per_api_call = 0.001  # $0.001 per API call
        self.cost_per_gb_storage = 0.023  # $0.023 per GB/month
        self.cost_per_compute_hour = 0.05  # $0.05 per compute hour

    async def calculate_weekly_cost_analysis(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> WeeklyCostAnalysis:
        """Calculate comprehensive cost analysis for the week."""
        try:
            logger.info(f"Calculating cost analysis for week {week_start.date()} to {week_end.date()}")

            # Get invoice volume metrics
            volume_metrics = await self._calculate_volume_metrics(week_start, week_end)

            # Get processing costs
            processing_costs = await self._calculate_processing_costs(week_start, week_end)

            # Calculate cost breakdowns
            cost_per_invoice = processing_costs['total_cost'] / max(volume_metrics['total'], 1)

            # Calculate efficiency metrics
            efficiency_metrics = await self._calculate_efficiency_metrics(
                volume_metrics, processing_costs
            )

            # Get trend analysis
            trend_analysis = await self._get_cost_trend_analysis(week_start, cost_per_invoice)

            # Generate predictions
            predictions = await self._generate_cost_predictions(week_start, week_end)

            # Create cost analysis record
            cost_analysis = WeeklyCostAnalysis(
                week_start=week_start,
                week_end=week_end,
                total_invoices_processed=volume_metrics['total'],
                auto_approved_count=volume_metrics['auto_approved'],
                manual_review_count=volume_metrics['manual_review'],
                exception_count=volume_metrics['exceptions'],
                total_processing_cost=processing_costs['total_cost'],
                cost_per_invoice=cost_per_invoice,
                auto_approval_cost_per_invoice=processing_costs['auto_approval_cost'] / max(volume_metrics['auto_approved'], 1),
                manual_review_cost_per_invoice=processing_costs['manual_review_cost'] / max(volume_metrics['manual_review'], 1),
                exception_handling_cost_per_invoice=processing_costs['exception_cost'] / max(volume_metrics['exceptions'], 1),
                llm_cost_total=processing_costs['llm_cost'],
                api_cost_total=processing_costs['api_cost'],
                storage_cost_total=processing_costs['storage_cost'],
                compute_cost_total=processing_costs['compute_cost'],
                cost_savings_vs_manual=efficiency_metrics['savings_vs_manual'],
                cost_efficiency_score=efficiency_metrics['efficiency_score'],
                roi_percentage=efficiency_metrics['roi_percentage'],
                previous_week_cost_per_invoice=trend_analysis['previous_week_cost'],
                cost_change_percentage=trend_analysis['change_percentage'],
                cost_trend=trend_analysis['trend'],
                next_week_predicted_cost=predictions['predicted_cost'],
                next_week_volume_prediction=predictions['predicted_volume'],
                currency="USD",
                data_quality_score=95.0,  # Could be calculated based on data completeness
                notes="Automated cost analysis by analytics engine"
            )

            logger.info(f"Cost analysis completed: ${cost_per_invoice:.2f} per invoice")
            return cost_analysis

        except Exception as e:
            logger.error(f"Failed to calculate cost analysis: {e}")
            raise

    async def calculate_exception_analysis(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> ExceptionAnalysis:
        """Calculate comprehensive exception analysis for the week."""
        try:
            logger.info(f"Calculating exception analysis for week {week_start.date()} to {week_end.date()}")

            # Get exception metrics
            exception_metrics = await self._get_exception_metrics(week_start, week_end)

            # Calculate resolution metrics
            resolution_metrics = await self._calculate_resolution_metrics(week_start, week_end)

            # Analyze top exception categories
            top_exceptions = await self._analyze_top_exceptions(week_start, week_end)

            # Calculate exception impact
            impact_analysis = await self._calculate_exception_impact(week_start, week_end)

            # Generate prevention insights
            prevention_insights = await self._generate_prevention_insights(week_start, week_end)

            # Get trend analysis
            trend_analysis = await self._get_exception_trends(week_start, week_end)

            # Create exception analysis record
            exception_analysis = ExceptionAnalysis(
                week_start=week_start,
                week_end=week_end,
                total_exceptions=exception_metrics['total'],
                unique_exception_types=exception_metrics['unique_types'],
                resolved_exceptions=resolution_metrics['resolved'],
                pending_exceptions=resolution_metrics['pending'],
                average_resolution_time_hours=resolution_metrics['avg_resolution_time'],
                median_resolution_time_hours=resolution_metrics['median_resolution_time'],
                longest_resolution_time_hours=resolution_metrics['longest_resolution_time'],
                resolution_rate_percentage=resolution_metrics['resolution_rate'],
                top_exception_types=top_exceptions['types'],
                top_resolvers=top_exceptions['resolvers'],
                exceptions_by_severity=impact_analysis['by_severity'],
                exceptions_by_vendor=impact_analysis['by_vendor'],
                business_impact_score=impact_analysis['impact_score'],
                repeat_exceptions=prevention_insights['repeat_exceptions'],
                new_exception_types=prevention_insights['new_types'],
                prevention_opportunities=prevention_insights['opportunities'],
                previous_week_total=trend_analysis['previous_week_total'],
                exception_trend=trend_analysis['exception_trend'],
                resolution_trend=trend_analysis['resolution_trend'],
                analysis_version="1.0",
                confidence_score=92.0,
                notes="Automated exception analysis by analytics engine"
            )

            logger.info(f"Exception analysis completed: {exception_metrics['total']} exceptions, {resolution_metrics['resolution_rate']:.1f}% resolution rate")
            return exception_analysis

        except Exception as e:
            logger.error(f"Failed to calculate exception analysis: {e}")
            raise

    async def calculate_processing_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> ProcessingMetric:
        """Calculate processing performance metrics for the week."""
        try:
            logger.info(f"Calculating processing metrics for week {week_start.date()} to {week_end.date()}")

            # Get volume and timing metrics
            volume_metrics = await self._get_processing_volume_metrics(week_start, week_end)
            timing_metrics = await self._calculate_timing_metrics(week_start, week_end)

            # Calculate time-to-ready metrics
            time_to_ready_metrics = await self._calculate_time_to_ready_metrics(week_start, week_end)

            # Calculate approval latency metrics
            approval_metrics = await self._calculate_approval_latency_metrics(week_start, week_end)

            # Calculate quality metrics
            quality_metrics = await self._calculate_quality_metrics(week_start, week_end)

            # Analyze performance by dimensions
            performance_breakdown = await self._analyze_performance_by_dimensions(week_start, week_end)

            # Get trend analysis
            trend_analysis = await self._get_processing_trends(week_start, week_end)

            # Create processing metrics record
            processing_metric = ProcessingMetric(
                week_start=week_start,
                week_end=week_end,
                total_invoices=volume_metrics['total'],
                processed_invoices=volume_metrics['processed'],
                failed_invoices=volume_metrics['failed'],
                average_processing_time_seconds=timing_metrics['avg_processing_time'],
                median_processing_time_seconds=timing_metrics['median_processing_time'],
                p95_processing_time_seconds=timing_metrics['p95_processing_time'],
                p99_processing_time_seconds=timing_metrics['p99_processing_time'],
                average_time_to_ready_minutes=time_to_ready_metrics['avg_minutes'],
                median_time_to_ready_minutes=time_to_ready_metrics['median_minutes'],
                time_to_ready_target_minutes=30.0,  # 30 minutes target
                time_to_ready_attainment_percentage=time_to_ready_metrics['attainment_percentage'],
                average_approval_latency_minutes=approval_metrics['avg_minutes'],
                median_approval_latency_minutes=approval_metrics['median_minutes'],
                approval_latency_target_minutes=15.0,  # 15 minutes target
                approval_latency_attainment_percentage=approval_metrics['attainment_percentage'],
                extraction_accuracy_percentage=quality_metrics['extraction_accuracy'],
                validation_pass_rate_percentage=quality_metrics['validation_pass_rate'],
                auto_approval_rate_percentage=quality_metrics['auto_approval_rate'],
                human_review_required_percentage=quality_metrics['human_review_rate'],
                performance_by_vendor=performance_breakdown['by_vendor'],
                performance_by_file_size=performance_breakdown['by_file_size'],
                performance_by_page_count=performance_breakdown['by_page_count'],
                processing_trend=trend_analysis['processing_trend'],
                quality_trend=trend_analysis['quality_trend'],
                metric_version="1.0",
                data_completeness_percentage=98.0,
                notes="Automated processing metrics by analytics engine"
            )

            logger.info(f"Processing metrics completed: {volume_metrics['total']} invoices, {timing_metrics['avg_processing_time']:.1f}s avg processing time")
            return processing_metric

        except Exception as e:
            logger.error(f"Failed to calculate processing metrics: {e}")
            raise

    async def calculate_slo_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> List[SLOMetric]:
        """Calculate SLO metrics for all defined SLOs."""
        try:
            logger.info(f"Calculating SLO metrics for week {week_start.date()} to {week_end.date()}")

            slo_metrics = []

            # Define SLO configurations
            slo_configs = await self._get_slo_configurations()

            for slo_config in slo_configs:
                slo_metric = await self._calculate_single_slo_metric(
                    slo_config, week_start, week_end
                )
                if slo_metric:
                    slo_metrics.append(slo_metric)

            logger.info(f"SLO metrics completed: {len(slo_metrics)} SLOs calculated")
            return slo_metrics

        except Exception as e:
            logger.error(f"Failed to calculate SLO metrics: {e}")
            raise

    async def generate_business_insights(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Generate actionable business insights from weekly data."""
        try:
            logger.info(f"Generating business insights for week {week_start.date()} to {week_end.date()}")

            insights = {
                "key_highlights": [],
                "concerns": [],
                "opportunities": [],
                "recommendations": [],
                "predictions": {},
                "financial_impact": {}
            }

            # Get current week metrics
            cost_analysis = await self.calculate_weekly_cost_analysis(week_start, week_end)
            exception_analysis = await self.calculate_exception_analysis(week_start, week_end)
            processing_metrics = await self.calculate_processing_metrics(week_start, week_end)

            # Generate cost insights
            await self._generate_cost_insights(cost_analysis, insights)

            # Generate performance insights
            await self._generate_performance_insights(processing_metrics, insights)

            # Generate exception insights
            await self._generate_exception_insights(exception_analysis, insights)

            # Generate business impact analysis
            await self._generate_business_impact_analysis(
                cost_analysis, exception_analysis, processing_metrics, insights
            )

            # Generate predictions and recommendations
            await self._generate_predictions_and_recommendations(
                cost_analysis, exception_analysis, processing_metrics, insights
            )

            logger.info(f"Business insights generated: {len(insights['recommendations'])} recommendations")
            return insights

        except Exception as e:
            logger.error(f"Failed to generate business insights: {e}")
            raise

    # Private helper methods

    async def _calculate_volume_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, int]:
        """Calculate invoice volume metrics."""
        total_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end
            )
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        auto_approved_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end,
                Invoice.status == InvoiceStatus.READY,
                Invoice.requires_human_review == False
            )
        )
        auto_approved_result = await self.session.execute(auto_approved_query)
        auto_approved = auto_approved_result.scalar() or 0

        manual_review_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end,
                Invoice.requires_human_review == True
            )
        )
        manual_review_result = await self.session.execute(manual_review_query)
        manual_review = manual_review_result.scalar() or 0

        exception_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        exception_result = await self.session.execute(exception_query)
        exceptions = exception_result.scalar() or 0

        return {
            "total": total,
            "auto_approved": auto_approved,
            "manual_review": manual_review,
            "exceptions": exceptions
        }

    async def _calculate_processing_costs(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, float]:
        """Calculate processing costs breakdown."""
        # Get trace spans for cost calculation
        trace_query = select(TraceSpan).where(
            and_(
                TraceSpan.start_time >= week_start,
                TraceSpan.start_time < week_end,
                TraceSpan.llm_cost.isnot(None)
            )
        )
        trace_result = await self.session.execute(trace_query)
        traces = trace_result.scalars().all()

        total_llm_cost = sum(trace.llm_cost or 0 for trace in traces)
        total_llm_tokens = sum(trace.llm_tokens_used or 0 for trace in traces)

        # Calculate API costs
        api_calls_query = select(func.count(TraceSpan.id)).where(
            and_(
                TraceSpan.start_time >= week_start,
                TraceSpan.start_time < week_end,
                TraceSpan.operation_name.like('%api%')
            )
        )
        api_calls_result = await self.session.execute(api_calls_query)
        api_calls = api_calls_result.scalar() or 0

        # Get file sizes for storage calculation
        invoice_query = select(Invoice.file_size).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end
            )
        )
        invoice_result = await self.session.execute(invoice_query)
        file_sizes = invoice_result.scalars().all()

        # Convert human-readable sizes to bytes (simplified)
        total_storage_gb = sum(
            self._parse_file_size(size) for size in file_sizes
        ) / (1024 * 1024 * 1024)

        # Calculate compute costs (processing time)
        total_processing_seconds = sum(trace.duration_ms or 0 for trace in traces) / 1000
        compute_hours = total_processing_seconds / 3600

        # Calculate costs
        llm_cost = total_llm_cost + (total_llm_tokens * self.cost_per_llm_token)
        api_cost = api_calls * self.cost_per_api_call
        storage_cost = total_storage_gb * self.cost_per_gb_storage / 4  # Weekly cost
        compute_cost = compute_hours * self.cost_per_compute_hour

        total_cost = llm_cost + api_cost + storage_cost + compute_cost

        # Estimate cost breakdown by processing type
        auto_approval_cost = total_cost * 0.3  # Lower cost for automated
        manual_review_cost = total_cost * 0.5  # Higher cost for manual review
        exception_cost = total_cost * 0.2  # Medium cost for exceptions

        return {
            "total_cost": total_cost,
            "llm_cost": llm_cost,
            "api_cost": api_cost,
            "storage_cost": storage_cost,
            "compute_cost": compute_cost,
            "auto_approval_cost": auto_approval_cost,
            "manual_review_cost": manual_review_cost,
            "exception_cost": exception_cost
        }

    def _parse_file_size(self, size_str: str) -> int:
        """Parse human-readable file size to bytes."""
        if not size_str:
            return 0

        size_str = size_str.upper().strip()
        if 'KB' in size_str:
            return float(size_str.replace('KB', '')) * 1024
        elif 'MB' in size_str:
            return float(size_str.replace('MB', '')) * 1024 * 1024
        elif 'GB' in size_str:
            return float(size_str.replace('GB', '')) * 1024 * 1024 * 1024
        else:
            # Assume bytes if no unit
            try:
                return float(size_str)
            except:
                return 0

    async def _calculate_efficiency_metrics(
        self,
        volume_metrics: Dict[str, int],
        processing_costs: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate efficiency and ROI metrics."""
        # Estimate manual processing cost (what it would cost without automation)
        manual_cost_per_invoice = 5.0  # $5 per invoice for manual processing
        total_manual_cost = volume_metrics['total'] * manual_cost_per_invoice

        # Calculate savings
        savings_vs_manual = total_manual_cost - processing_costs['total_cost']
        roi_percentage = (savings_vs_manual / processing_costs['total_cost']) * 100 if processing_costs['total_cost'] > 0 else 0

        # Calculate efficiency score (0-100)
        efficiency_score = min(100, (savings_vs_manual / total_manual_cost) * 100) if total_manual_cost > 0 else 0

        return {
            "savings_vs_manual": savings_vs_manual,
            "roi_percentage": roi_percentage,
            "efficiency_score": efficiency_score
        }

    async def _get_cost_trend_analysis(
        self,
        week_start: datetime,
        current_cost_per_invoice: float
    ) -> Dict[str, Any]:
        """Get cost trend analysis compared to previous week."""
        previous_week_start = week_start - timedelta(days=7)
        previous_week_end = week_start

        # Get previous week's cost analysis
        previous_cost_query = select(WeeklyCostAnalysis).where(
            and_(
                WeeklyCostAnalysis.week_start == previous_week_start,
                WeeklyCostAnalysis.week_end == previous_week_end
            )
        )
        previous_cost_result = await self.session.execute(previous_cost_query)
        previous_cost = previous_cost_result.scalar_one_or_none()

        if previous_cost:
            previous_week_cost = previous_cost.cost_per_invoice
            change_percentage = ((current_cost_per_invoice - previous_week_cost) / previous_week_cost) * 100

            if change_percentage > 5:
                trend = "increasing"
            elif change_percentage < -5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            previous_week_cost = None
            change_percentage = None
            trend = "unknown"

        return {
            "previous_week_cost": previous_week_cost,
            "change_percentage": change_percentage,
            "trend": trend
        }

    async def _generate_cost_predictions(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Generate cost predictions for next week."""
        # Simple linear prediction based on recent trends
        recent_weeks = 4  # Look at last 4 weeks

        historical_query = select(WeeklyCostAnalysis).where(
            WeeklyCostAnalysis.week_start >= (week_start - timedelta(weeks=recent_weeks))
        ).order_by(desc(WeeklyCostAnalysis.week_start)).limit(recent_weeks)

        historical_result = await self.session.execute(historical_query)
        historical_data = historical_result.scalars().all()

        if len(historical_data) >= 2:
            # Calculate trend
            costs = [record.cost_per_invoice for record in historical_data]
            volumes = [record.total_invoices_processed for record in historical_data]

            # Simple linear regression for prediction
            cost_trend = (costs[0] - costs[-1]) / len(costs) if costs[0] != costs[-1] else 0
            volume_trend = (volumes[0] - volumes[-1]) / len(volumes) if volumes[0] != volumes[-1] else 0

            predicted_cost = costs[0] + cost_trend
            predicted_volume = max(0, volumes[0] + volume_trend)
        else:
            # Not enough data for prediction
            predicted_cost = None
            predicted_volume = None

        return {
            "predicted_cost": predicted_cost,
            "predicted_volume": predicted_volume
        }

    async def _get_exception_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Get exception volume and type metrics."""
        total_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        unique_types_query = select(func.count(func.distinct(Exception.reason_code))).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        unique_types_result = await self.session.execute(unique_types_query)
        unique_types = unique_types_result.scalar() or 0

        return {
            "total": total,
            "unique_types": unique_types
        }

    async def _calculate_resolution_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Calculate exception resolution metrics."""
        # Get resolved exceptions for the week
        resolved_query = select(
            Exception.resolved_at,
            Exception.created_at
        ).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end,
                Exception.resolved_at.isnot(None)
            )
        )
        resolved_result = await self.session.execute(resolved_query)
        resolved_exceptions = resolved_result.all()

        # Get pending exceptions
        pending_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end,
                Exception.resolved_at.is_(None)
            )
        )
        pending_result = await self.session.execute(pending_query)
        pending = pending_result.scalar() or 0

        # Calculate resolution times
        resolution_times = []
        for resolved in resolved_exceptions:
            resolution_time = (resolved[0] - resolved[1]).total_seconds() / 3600  # Convert to hours
            resolution_times.append(resolution_time)

        if resolution_times:
            avg_resolution_time = statistics.mean(resolution_times)
            median_resolution_time = statistics.median(resolution_times)
            longest_resolution_time = max(resolution_times)
        else:
            avg_resolution_time = 0
            median_resolution_time = 0
            longest_resolution_time = 0

        total_exceptions = len(resolved_exceptions) + pending
        resolution_rate = (len(resolved_exceptions) / total_exceptions * 100) if total_exceptions > 0 else 0

        return {
            "resolved": len(resolved_exceptions),
            "pending": pending,
            "avg_resolution_time": avg_resolution_time,
            "median_resolution_time": median_resolution_time,
            "longest_resolution_time": longest_resolution_time,
            "resolution_rate": resolution_rate
        }

    async def _analyze_top_exceptions(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze top exception types and resolvers."""
        # Top exception types
        exception_types_query = select(
            Exception.reason_code,
            func.count(Exception.id).label('count')
        ).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        ).group_by(Exception.reason_code).order_by(desc('count')).limit(10)

        exception_types_result = await self.session.execute(exception_types_query)
        exception_types = exception_types_result.all()

        total_exceptions = sum(count for _, count in exception_types)
        top_types = [
            {
                "type": reason_code,
                "count": count,
                "percentage": (count / total_exceptions * 100) if total_exceptions > 0 else 0
            }
            for reason_code, count in exception_types
        ]

        # Top resolvers
        resolvers_query = select(
            Exception.resolved_by,
            func.count(Exception.id).label('count'),
            func.avg(
                func.extract('epoch', Exception.resolved_at - Exception.created_at) / 3600
            ).label('avg_resolution_time')
        ).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end,
                Exception.resolved_at.isnot(None),
                Exception.resolved_by.isnot(None)
            )
        ).group_by(Exception.resolved_by).order_by(desc('count')).limit(10)

        resolvers_result = await self.session.execute(resolvers_query)
        resolvers = resolvers_result.all()

        top_resolvers = [
            {
                "resolver": resolver,
                "count": count,
                "avg_resolution_time": float(avg_time) if avg_time else 0
            }
            for resolver, count, avg_time in resolvers
        ]

        return {
            "types": top_types,
            "resolvers": top_resolvers
        }

    async def _calculate_exception_impact(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Calculate exception impact analysis."""
        # Get exceptions by severity (simplified - using reason_code patterns)
        severity_query = select(Exception.reason_code, func.count(Exception.id).label('count')).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        ).group_by(Exception.reason_code)

        severity_result = await self.session.execute(severity_query)
        exceptions = severity_result.all()

        # Categorize by severity (simplified logic)
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for reason_code, count in exceptions:
            if any(keyword in reason_code.lower() for keyword in ['critical', 'urgent', 'payment']):
                by_severity["critical"] += count
            elif any(keyword in reason_code.lower() for keyword in ['validation', 'format', 'missing']):
                by_severity["high"] += count
            elif any(keyword in reason_code.lower() for keyword in ['warning', 'quality']):
                by_severity["medium"] += count
            else:
                by_severity["low"] += count

        # Get exceptions by vendor
        vendor_query = select(
            Invoice.vendor_id,
            func.count(Exception.id).label('count')
        ).join(Exception, Invoice.id == Exception.invoice_id).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        ).group_by(Invoice.vendor_id).order_by(desc('count')).limit(10)

        vendor_result = await self.session.execute(vendor_query)
        vendor_exceptions = vendor_result.all()

        total_exceptions = sum(count for _, count in vendor_exceptions)
        by_vendor = [
            {
                "vendor_id": str(vendor_id) if vendor_id else "unknown",
                "count": count,
                "percentage": (count / total_exceptions * 100) if total_exceptions > 0 else 0
            }
            for vendor_id, count in vendor_exceptions
        ]

        # Calculate business impact score (0-100)
        critical_weight = 4
        high_weight = 3
        medium_weight = 2
        low_weight = 1

        weighted_score = (
            by_severity["critical"] * critical_weight +
            by_severity["high"] * high_weight +
            by_severity["medium"] * medium_weight +
            by_severity["low"] * low_weight
        )

        max_possible_score = sum(by_severity.values()) * critical_weight
        impact_score = 100 - (weighted_score / max_possible_score * 100) if max_possible_score > 0 else 100

        return {
            "by_severity": by_severity,
            "by_vendor": by_vendor,
            "impact_score": impact_score
        }

    async def _generate_prevention_insights(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Generate exception prevention insights."""
        # Get current week exception types
        current_types_query = select(func.distinct(Exception.reason_code)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        current_types_result = await self.session.execute(current_types_query)
        current_types = set(row[0] for row in current_types_result.all())

        # Get previous week exception types
        previous_week_start = week_start - timedelta(days=7)
        previous_types_query = select(func.distinct(Exception.reason_code)).where(
            and_(
                Exception.created_at >= previous_week_start,
                Exception.created_at < week_start
            )
        )
        previous_types_result = await self.session.execute(previous_types_query)
        previous_types = set(row[0] for row in previous_types_result.all())

        # Calculate repeats and new types
        repeat_exceptions = len(current_types.intersection(previous_types))
        new_exception_types = len(current_types - previous_types)

        # Generate prevention opportunities (simplified)
        opportunities = []
        if repeat_exceptions > 0:
            opportunities.append({
                "type": "repeat_patterns",
                "description": f"Focus on {repeat_exceptions} recurring exception types",
                "potential_impact": "high",
                "effort": "medium"
            })

        if new_exception_types > 0:
            opportunities.append({
                "type": "new_patterns",
                "description": f"Analyze {new_exception_types} new exception types",
                "potential_impact": "medium",
                "effort": "low"
            })

        return {
            "repeat_exceptions": repeat_exceptions,
            "new_types": new_exception_types,
            "opportunities": opportunities
        }

    async def _get_exception_trends(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """Get exception trend analysis."""
        previous_week_start = week_start - timedelta(days=7)

        # Get current week total
        current_total_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= week_start,
                Exception.created_at < week_end
            )
        )
        current_total_result = await self.session.execute(current_total_query)
        current_total = current_total_result.scalar() or 0

        # Get previous week total
        previous_total_query = select(func.count(Exception.id)).where(
            and_(
                Exception.created_at >= previous_week_start,
                Exception.created_at < week_start
            )
        )
        previous_total_result = await self.session.execute(previous_total_query)
        previous_total = previous_total_result.scalar() or 0

        # Calculate trends
        if previous_total > 0:
            change_percentage = ((current_total - previous_total) / previous_total) * 100
            if change_percentage > 10:
                exception_trend = "increasing"
            elif change_percentage < -10:
                exception_trend = "decreasing"
            else:
                exception_trend = "stable"
        else:
            exception_trend = "unknown"

        # Resolution trend would require more complex calculation of resolution rates
        resolution_trend = "stable"  # Placeholder

        return {
            "previous_week_total": previous_total,
            "exception_trend": exception_trend,
            "resolution_trend": resolution_trend
        }

    # Additional helper methods would be implemented here for processing metrics,
    # SLO calculations, and business insights generation...

    async def _get_processing_volume_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, int]:
        """Get processing volume metrics."""
        total_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end
            )
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        processed_query = select(func.count(Invoice.id)).where(
            and_(
                Invoice.created_at >= week_start,
                Invoice.created_at < week_end,
                Invoice.status.in_([InvoiceStatus.PARSED, InvoiceStatus.VALIDATED, InvoiceStatus.READY, InvoiceStatus.DONE])
            )
        )
        processed_result = await self.session.execute(processed_query)
        processed = processed_result.scalar() or 0

        failed = total - processed

        return {
            "total": total,
            "processed": processed,
            "failed": failed
        }

    async def _calculate_timing_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, float]:
        """Calculate timing metrics from trace data."""
        timing_query = select(TraceSpan.duration_ms).where(
            and_(
                TraceSpan.start_time >= week_start,
                TraceSpan.start_time < week_end,
                TraceSpan.operation_name == "process_invoice",
                TraceSpan.duration_ms.isnot(None)
            )
        )
        timing_result = await self.session.execute(timing_query)
        durations = [row[0] / 1000 for row in timing_result.all()]  # Convert to seconds

        if not durations:
            return {
                "avg_processing_time": 0,
                "median_processing_time": 0,
                "p95_processing_time": 0,
                "p99_processing_time": 0
            }

        durations.sort()
        length = len(durations)

        return {
            "avg_processing_time": statistics.mean(durations),
            "median_processing_time": statistics.median(durations),
            "p95_processing_time": durations[int(length * 0.95)],
            "p99_processing_time": durations[int(length * 0.99)]
        }

    # Placeholder methods for remaining functionality
    async def _calculate_time_to_ready_metrics(self, week_start, week_end):
        return {"avg_minutes": 25.0, "median_minutes": 20.0, "attainment_percentage": 85.0}

    async def _calculate_approval_latency_metrics(self, week_start, week_end):
        return {"avg_minutes": 10.0, "median_minutes": 8.0, "attainment_percentage": 90.0}

    async def _calculate_quality_metrics(self, week_start, week_end):
        return {
            "extraction_accuracy": 94.0,
            "validation_pass_rate": 88.0,
            "auto_approval_rate": 75.0,
            "human_review_rate": 25.0
        }

    async def _analyze_performance_by_dimensions(self, week_start, week_end):
        return {
            "by_vendor": [],
            "by_file_size": [],
            "by_page_count": []
        }

    async def _get_processing_trends(self, week_start, week_end):
        return {"processing_trend": "stable", "quality_trend": "improving"}

    async def _get_slo_configurations(self):
        return [
            {
                "name": "Processing Time",
                "category": SLOCategory.PROCESSING_TIME,
                "target": 30.0,
                "error_budget": 5.0
            },
            {
                "name": "Extraction Accuracy",
                "category": SLOCategory.ACCURACY,
                "target": 95.0,
                "error_budget": 2.0
            }
        ]

    async def _calculate_single_slo_metric(self, slo_config, week_start, week_end):
        return None  # Placeholder

    async def _generate_cost_insights(self, cost_analysis, insights):
        insights["key_highlights"].append(f"Cost per invoice: ${cost_analysis.cost_per_invoice:.2f}")
        if cost_analysis.cost_savings_vs_manual > 0:
            insights["key_highlights"].append(f"Cost savings: ${cost_analysis.cost_savings_vs_manual:.2f} vs manual processing")

    async def _generate_performance_insights(self, processing_metrics, insights):
        insights["key_highlights"].append(f"Processed {processing_metrics.total_invoices} invoices")
        insights["key_highlights"].append(f"Auto-approval rate: {processing_metrics.auto_approval_rate_percentage:.1f}%")

    async def _generate_exception_insights(self, exception_analysis, insights):
        if exception_analysis.resolution_rate_percentage < 80:
            insights["concerns"].append(f"Exception resolution rate is {exception_analysis.resolution_rate_percentage:.1f}%")

    async def _generate_business_impact_analysis(self, cost_analysis, exception_analysis, processing_metrics, insights):
        insights["financial_impact"] = {
            "weekly_cost": cost_analysis.total_processing_cost,
            "cost_per_invoice": cost_analysis.cost_per_invoice,
            "efficiency_score": cost_analysis.cost_efficiency_score
        }

    async def _generate_predictions_and_recommendations(self, cost_analysis, exception_analysis, processing_metrics, insights):
        insights["predictions"] = {
            "next_week_cost": cost_analysis.next_week_predicted_cost,
            "next_week_volume": cost_analysis.next_week_volume_prediction
        }

        insights["recommendations"].append("Monitor cost trends and optimize automation")
        if exception_analysis.total_exceptions > 10:
            insights["recommendations"].append("Focus on reducing exception volume")