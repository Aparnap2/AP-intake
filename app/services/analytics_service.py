"""
Analytics service for calculating KPIs and metrics for the AP Intake system.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, cast, Date, extract, func, text
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceExtraction, InvoiceStatus, Validation, Exception, StagedExport
from app.models.reference import Vendor

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for calculating and providing analytics data."""

    def __init__(self, db: Session):
        self.db = db

    # Accuracy Metrics
    def get_extraction_accuracy_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate document extraction accuracy metrics."""
        try:
            # Get extractions in date range
            extractions = self.db.query(InvoiceExtraction).join(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).all()

            if not extractions:
                return {
                    "total_extractions": 0,
                    "average_confidence": 0,
                    "high_confidence_rate": 0,
                    "medium_confidence_rate": 0,
                    "low_confidence_rate": 0,
                    "confidence_distribution": {}
                }

            # Calculate confidence metrics
            confidence_scores = []
            confidence_distribution = {"high": 0, "medium": 0, "low": 0}

            for extraction in extractions:
                if extraction.confidence_json:
                    # Parse confidence scores from JSON
                    if isinstance(extraction.confidence_json, dict):
                        # Average confidence across all fields
                        field_confidences = [
                            float(v) for v in extraction.confidence_json.values()
                            if isinstance(v, (int, float)) and v > 0
                        ]
                        if field_confidences:
                            avg_confidence = sum(field_confidences) / len(field_confidences)
                            confidence_scores.append(avg_confidence)

                            # Categorize confidence
                            if avg_confidence >= 0.9:
                                confidence_distribution["high"] += 1
                            elif avg_confidence >= 0.7:
                                confidence_distribution["medium"] += 1
                            else:
                                confidence_distribution["low"] += 1

            total_extractions = len(extractions)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

            return {
                "total_extractions": total_extractions,
                "average_confidence": round(avg_confidence, 4),
                "high_confidence_rate": round(confidence_distribution["high"] / total_extractions * 100, 2),
                "medium_confidence_rate": round(confidence_distribution["medium"] / total_extractions * 100, 2),
                "low_confidence_rate": round(confidence_distribution["low"] / total_extractions * 100, 2),
                "confidence_distribution": confidence_distribution
            }
        except Exception as e:
            logger.error(f"Error calculating extraction accuracy metrics: {e}")
            return {"error": str(e)}

    def get_validation_pass_rates(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate validation pass/fail rates."""
        try:
            validations = self.db.query(Validation).join(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).all()

            if not validations:
                return {
                    "total_validations": 0,
                    "pass_rate": 0,
                    "fail_rate": 0,
                    "validation_trend": []
                }

            passed = sum(1 for v in validations if v.passed)
            failed = len(validations) - passed

            # Daily trend data
            daily_stats = {}
            for validation in validations:
                day = validation.created_at.date()
                if day not in daily_stats:
                    daily_stats[day] = {"passed": 0, "failed": 0, "total": 0}

                if validation.passed:
                    daily_stats[day]["passed"] += 1
                else:
                    daily_stats[day]["failed"] += 1
                daily_stats[day]["total"] += 1

            # Convert to trend data
            validation_trend = []
            for day, stats in sorted(daily_stats.items()):
                validation_trend.append({
                    "date": day.isoformat(),
                    "pass_rate": round(stats["passed"] / stats["total"] * 100, 2),
                    "total": stats["total"],
                    "passed": stats["passed"],
                    "failed": stats["failed"]
                })

            return {
                "total_validations": len(validations),
                "pass_rate": round(passed / len(validations) * 100, 2),
                "fail_rate": round(failed / len(validations) * 100, 2),
                "validation_trend": validation_trend
            }
        except Exception as e:
            logger.error(f"Error calculating validation pass rates: {e}")
            return {"error": str(e)}

    # Exception Analysis
    def get_exception_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze exception rates and breakdown by reason codes."""
        try:
            exceptions = self.db.query(Exception).join(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).all()

            total_invoices = self.db.query(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).count()

            if not exceptions:
                return {
                    "total_exceptions": 0,
                    "exception_rate": 0,
                    "resolved_exceptions": 0,
                    "resolution_rate": 0,
                    "reason_code_breakdown": {},
                    "resolution_trend": []
                }

            # Exception rate
            exception_rate = len(exceptions) / total_invoices * 100 if total_invoices > 0 else 0

            # Resolution metrics
            resolved_exceptions = [e for e in exceptions if e.resolved_at]
            resolution_rate = len(resolved_exceptions) / len(exceptions) * 100 if exceptions else 0

            # Reason code breakdown
            reason_code_breakdown = {}
            for exception in exceptions:
                reason = exception.reason_code
                if reason not in reason_code_breakdown:
                    reason_code_breakdown[reason] = {
                        "count": 0,
                        "resolved": 0,
                        "average_resolution_time_hours": 0,
                        "resolution_times": []
                    }

                reason_code_breakdown[reason]["count"] += 1

                if exception.resolved_at:
                    reason_code_breakdown[reason]["resolved"] += 1
                    resolution_time = exception.resolved_at - exception.created_at
                    resolution_hours = resolution_time.total_seconds() / 3600
                    reason_code_breakdown[reason]["resolution_times"].append(resolution_hours)

            # Calculate average resolution times
            for reason, data in reason_code_breakdown.items():
                if data["resolution_times"]:
                    data["average_resolution_time_hours"] = round(
                        sum(data["resolution_times"]) / len(data["resolution_times"]), 2
                    )
                del data["resolution_times"]  # Remove raw times from output

            # Resolution trend (daily)
            resolution_trend = {}
            for exception in exceptions:
                day = exception.created_at.date()
                if day not in resolution_trend:
                    resolution_trend[day] = {"created": 0, "resolved": 0}

                resolution_trend[day]["created"] += 1
                if exception.resolved_at and exception.resolved_at.date() == day:
                    resolution_trend[day]["resolved"] += 1

            trend_data = [
                {
                    "date": day.isoformat(),
                    "created": stats["created"],
                    "resolved": stats["resolved"]
                }
                for day, stats in sorted(resolution_trend.items())
            ]

            return {
                "total_exceptions": len(exceptions),
                "exception_rate": round(exception_rate, 2),
                "resolved_exceptions": len(resolved_exceptions),
                "resolution_rate": round(resolution_rate, 2),
                "reason_code_breakdown": reason_code_breakdown,
                "resolution_trend": trend_data
            }
        except Exception as e:
            logger.error(f"Error analyzing exceptions: {e}")
            return {"error": str(e)}

    # Cycle Time Metrics
    def get_cycle_time_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate processing cycle times."""
        try:
            invoices = self.db.query(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).all()

            if not invoices:
                return {
                    "total_invoices": 0,
                    "average_processing_time_hours": 0,
                    "processing_time_distribution": {},
                    "stage_performance": {}
                }

            processing_times = []
            stage_performance = {
                "received_to_parsed": [],
                "parsed_to_validated": [],
                "validated_to_staged": [],
                "staged_to_done": []
            }

            for invoice in invoices:
                # Calculate total processing time
                if invoice.status == InvoiceStatus.DONE and invoice.updated_at:
                    total_time = invoice.updated_at - invoice.created_at
                    total_hours = total_time.total_seconds() / 3600
                    processing_times.append(total_hours)

                # Stage-specific times from workflow_data
                if invoice.workflow_data and isinstance(invoice.workflow_data, dict):
                    timestamps = invoice.workflow_data.get("timestamps", {})
                    if timestamps:
                        # Extract stage completion times
                        stages = [
                            ("received_to_parsed", "parsed"),
                            ("parsed_to_validated", "validated"),
                            ("validated_to_staged", "staged"),
                            ("staged_to_done", "done")
                        ]

                        for stage_key, stage_name in stages:
                            if stage_name in timestamps:
                                stage_time = timestamps[stage_name] - invoice.created_at
                                stage_hours = stage_time.total_seconds() / 3600
                                stage_performance[stage_key].append(stage_hours)

            # Calculate metrics
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

            # Processing time distribution
            distribution = {
                "under_1_hour": sum(1 for t in processing_times if t < 1),
                "1_to_4_hours": sum(1 for t in processing_times if 1 <= t < 4),
                "4_to_24_hours": sum(1 for t in processing_times if 4 <= t < 24),
                "over_24_hours": sum(1 for t in processing_times if t >= 24)
            }

            # Stage performance averages
            stage_averages = {}
            for stage, times in stage_performance.items():
                if times:
                    stage_averages[stage] = round(sum(times) / len(times), 2)
                else:
                    stage_averages[stage] = 0

            return {
                "total_invoices": len(invoices),
                "average_processing_time_hours": round(avg_processing_time, 2),
                "processing_time_distribution": distribution,
                "stage_performance": stage_averages
            }
        except Exception as e:
            logger.error(f"Error calculating cycle time metrics: {e}")
            return {"error": str(e)}

    # Productivity Metrics
    def get_productivity_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate productivity metrics for reviewers and the system."""
        try:
            # System productivity
            total_invoices = self.db.query(Invoice).filter(
                Invoice.created_at.between(start_date, end_date)
            ).count()

            processed_invoices = self.db.query(Invoice).filter(
                and_(
                    Invoice.created_at.between(start_date, end_date),
                    Invoice.status.in_([InvoiceStatus.DONE, InvoiceStatus.STAGED])
                )
            ).count()

            # Exception resolution productivity
            resolved_exceptions = self.db.query(Exception).filter(
                and_(
                    Exception.resolved_at.between(start_date, end_date),
                    Exception.resolved_at.isnot(None)
                )
            ).all()

            # Export productivity
            exports = self.db.query(StagedExport).filter(
                StagedExport.created_at.between(start_date, end_date)
            ).all()

            successful_exports = [e for e in exports if e.status.value == "sent"]

            # Calculate metrics
            processing_efficiency = processed_invoices / total_invoices * 100 if total_invoices > 0 else 0
            export_success_rate = len(successful_exports) / len(exports) * 100 if exports else 0

            # Daily productivity trend
            daily_productivity = {}
            current_date = start_date.date()
            end_date_only = end_date.date()

            while current_date <= end_date_only:
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())

                day_invoices = self.db.query(Invoice).filter(
                    Invoice.created_at.between(day_start, day_end)
                ).count()

                day_processed = self.db.query(Invoice).filter(
                    and_(
                        Invoice.created_at.between(day_start, day_end),
                        Invoice.status.in_([InvoiceStatus.DONE, InvoiceStatus.STAGED])
                    )
                ).count()

                daily_productivity[current_date.isoformat()] = {
                    "received": day_invoices,
                    "processed": day_processed,
                    "efficiency": day_processed / day_invoices * 100 if day_invoices > 0 else 0
                }

                current_date += timedelta(days=1)

            return {
                "total_invoices_received": total_invoices,
                "total_invoices_processed": processed_invoices,
                "processing_efficiency": round(processing_efficiency, 2),
                "total_exceptions_resolved": len(resolved_exceptions),
                "total_exports_attempted": len(exports),
                "total_exports_successful": len(successful_exports),
                "export_success_rate": round(export_success_rate, 2),
                "daily_productivity": daily_productivity
            }
        except Exception as e:
            logger.error(f"Error calculating productivity metrics: {e}")
            return {"error": str(e)}

    # Reviewer Performance
    def get_reviewer_performance(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate performance metrics for individual reviewers."""
        try:
            # Get exceptions resolved by reviewers
            resolved_exceptions = self.db.query(Exception).filter(
                and_(
                    Exception.resolved_at.between(start_date, end_date),
                    Exception.resolved_at.isnot(None),
                    Exception.resolved_by.isnot(None)
                )
            ).all()

            # Group by reviewer
            reviewer_stats = {}
            for exception in resolved_exceptions:
                reviewer = exception.resolved_by
                if reviewer not in reviewer_stats:
                    reviewer_stats[reviewer] = {
                        "resolved_count": 0,
                        "resolution_times": [],
                        "reason_codes": {}
                    }

                reviewer_stats[reviewer]["resolved_count"] += 1

                # Calculate resolution time
                resolution_time = exception.resolved_at - exception.created_at
                resolution_hours = resolution_time.total_seconds() / 3600
                reviewer_stats[reviewer]["resolution_times"].append(resolution_hours)

                # Track reason codes
                reason = exception.reason_code
                if reason not in reviewer_stats[reviewer]["reason_codes"]:
                    reviewer_stats[reviewer]["reason_codes"][reason] = 0
                reviewer_stats[reviewer]["reason_codes"][reason] += 1

            # Calculate averages and clean up data
            reviewer_performance = {}
            for reviewer, stats in reviewer_stats.items():
                avg_resolution_time = (
                    sum(stats["resolution_times"]) / len(stats["resolution_times"])
                    if stats["resolution_times"] else 0
                )

                reviewer_performance[reviewer] = {
                    "resolved_count": stats["resolved_count"],
                    "average_resolution_time_hours": round(avg_resolution_time, 2),
                    "top_reason_codes": dict(
                        sorted(stats["reason_codes"].items(), key=lambda x: x[1], reverse=True)[:5]
                    )
                }

            # Calculate rankings
            if reviewer_performance:
                ranked_reviewers = sorted(
                    reviewer_performance.items(),
                    key=lambda x: x[1]["resolved_count"],
                    reverse=True
                )

                # Add rankings
                for i, (reviewer, _) in enumerate(ranked_reviewers, 1):
                    reviewer_performance[reviewer]["rank"] = i

            return {
                "total_reviewers": len(reviewer_performance),
                "reviewer_performance": reviewer_performance,
                "total_resolved_exceptions": len(resolved_exceptions)
            }
        except Exception as e:
            logger.error(f"Error calculating reviewer performance: {e}")
            return {"error": str(e)}

    # Trend Analysis
    def get_trend_analysis(self, start_date: datetime, end_date: datetime, metric: str = "all") -> Dict[str, Any]:
        """Provide trend analysis for various metrics over time."""
        try:
            trends = {}

            if metric in ["all", "volume"]:
                # Invoice volume trend
                volume_query = self.db.query(
                    func.date(Invoice.created_at).label('date'),
                    func.count(Invoice.id).label('count')
                ).filter(
                    Invoice.created_at.between(start_date, end_date)
                ).group_by(func.date(Invoice.created_at)).all()

                trends["volume"] = [
                    {"date": str(row.date), "count": row.count}
                    for row in volume_query
                ]

            if metric in ["all", "accuracy"]:
                # Accuracy trend
                accuracy_query = self.db.query(
                    func.date(InvoiceExtraction.created_at).label('date'),
                    func.avg(cast(func.json_extract(InvoiceExtraction.confidence_json, '$.overall'), float)).label('avg_confidence')
                ).join(Invoice).filter(
                    Invoice.created_at.between(start_date, end_date)
                ).group_by(func.date(InvoiceExtraction.created_at)).all()

                trends["accuracy"] = [
                    {"date": str(row.date), "confidence": round(row.avg_confidence or 0, 4)}
                    for row in accuracy_query
                ]

            if metric in ["all", "exceptions"]:
                # Exception trend
                exception_query = self.db.query(
                    func.date(Exception.created_at).label('date'),
                    func.count(Exception.id).label('count')
                ).join(Invoice).filter(
                    Invoice.created_at.between(start_date, end_date)
                ).group_by(func.date(Exception.created_at)).all()

                trends["exceptions"] = [
                    {"date": str(row.date), "count": row.count}
                    for row in exception_query
                ]

            return {
                "trends": trends,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error generating trend analysis: {e}")
            return {"error": str(e)}

    # Executive Summary
    def get_executive_summary(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Provide executive summary KPIs."""
        try:
            # Get all metrics
            accuracy_metrics = self.get_extraction_accuracy_metrics(start_date, end_date)
            validation_metrics = self.get_validation_pass_rates(start_date, end_date)
            exception_metrics = self.get_exception_analysis(start_date, end_date)
            cycle_metrics = self.get_cycle_time_metrics(start_date, end_date)
            productivity_metrics = self.get_productivity_metrics(start_date, end_date)

            # Calculate overall health score
            health_score = 0
            factors = 0

            # Accuracy factor (30%)
            if "average_confidence" in accuracy_metrics:
                health_score += accuracy_metrics["average_confidence"] * 30
                factors += 30

            # Validation factor (25%)
            if "pass_rate" in validation_metrics:
                health_score += (validation_metrics["pass_rate"] / 100) * 25
                factors += 25

            # Exception factor (25%)
            if "exception_rate" in exception_metrics:
                # Lower exception rate is better
                exception_score = max(0, (100 - exception_metrics["exception_rate"]) / 100)
                health_score += exception_score * 25
                factors += 25

            # Efficiency factor (20%)
            if "processing_efficiency" in productivity_metrics:
                health_score += (productivity_metrics["processing_efficiency"] / 100) * 20
                factors += 20

            overall_health = round(health_score / factors * 100, 2) if factors > 0 else 0

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "overall_health_score": overall_health,
                "key_metrics": {
                    "total_invoices": productivity_metrics.get("total_invoices_received", 0),
                    "processing_efficiency": productivity_metrics.get("processing_efficiency", 0),
                    "extraction_accuracy": round(accuracy_metrics.get("average_confidence", 0) * 100, 2),
                    "validation_pass_rate": validation_metrics.get("pass_rate", 0),
                    "exception_rate": exception_metrics.get("exception_rate", 0),
                    "avg_processing_time_hours": cycle_metrics.get("average_processing_time_hours", 0)
                },
                "trends": {
                    "invoice_volume_trend": "stable",  # Would calculate from historical data
                    "accuracy_trend": "improving",
                    "exception_trend": "decreasing"
                },
                "recommendations": self._generate_recommendations(
                    accuracy_metrics, validation_metrics, exception_metrics,
                    cycle_metrics, productivity_metrics
                )
            }
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return {"error": str(e)}

    def _generate_recommendations(self, accuracy_metrics: Dict, validation_metrics: Dict,
                                exception_metrics: Dict, cycle_metrics: Dict,
                                productivity_metrics: Dict) -> List[str]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []

        # Accuracy recommendations
        if accuracy_metrics.get("average_confidence", 0) < 0.8:
            recommendations.append("Consider implementing additional training data for document extraction to improve confidence scores")

        if accuracy_metrics.get("low_confidence_rate", 0) > 20:
            recommendations.append("High number of low-confidence extractions detected. Review document quality thresholds")

        # Validation recommendations
        if validation_metrics.get("pass_rate", 0) < 90:
            recommendations.append("Validation pass rate below target. Review and update validation rules")

        # Exception recommendations
        if exception_metrics.get("exception_rate", 0) > 15:
            recommendations.append("Exception rate above target. Analyze top reason codes for process improvements")

        if exception_metrics.get("resolution_rate", 0) < 80:
            recommendations.append("Exception resolution rate needs improvement. Consider reviewer training or workload balancing")

        # Processing time recommendations
        if cycle_metrics.get("average_processing_time_hours", 0) > 24:
            recommendations.append("Processing time exceeds 24 hours. Identify bottlenecks in the workflow")

        # Productivity recommendations
        if productivity_metrics.get("processing_efficiency", 0) < 85:
            recommendations.append("Processing efficiency below target. Review resource allocation and workflow optimization")

        if not recommendations:
            recommendations.append("All metrics are within target ranges. Continue current operations")

        return recommendations