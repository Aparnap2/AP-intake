"""
DLQ Metrics Service for comprehensive monitoring and alerting.

This service provides:
- Prometheus metrics collection for DLQ
- Custom metrics calculation and aggregation
- Alert rule evaluation and notification
- Performance monitoring and trend analysis
- Health score calculation
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Histogram, Gauge, Info
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dlq import DLQStatus, DLQCategory, DLQPriority
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class DLQMetricsService:
    """
    Service for collecting and managing DLQ metrics.

    This service integrates with Prometheus to provide comprehensive
    monitoring and alerting for the DLQ system.
    """

    def __init__(self, db: Session):
        self.db = db
        self.alert_service = AlertService(db) if hasattr(settings, 'ALERT_SERVICE_ENABLED') and settings.ALERT_SERVICE_ENABLED else None

        # Prometheus metrics
        self._init_prometheus_metrics()

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""
        # Counters
        self.dlq_entries_total = Counter(
            'dlq_entries_total',
            'Total number of DLQ entries',
            ['task_name', 'error_category', 'priority', 'status']
        )

        self.dlq_redrive_attempts_total = Counter(
            'dlq_redrive_attempts_total',
            'Total number of redrive attempts',
            ['task_name', 'success']
        )

        self.dlq_cleanup_operations_total = Counter(
            'dlq_cleanup_operations_total',
            'Total number of cleanup operations',
            ['operation_type']
        )

        # Histograms
        self.dlq_entry_age_hours = Histogram(
            'dlq_entry_age_hours',
            'Age of DLQ entries in hours',
            ['error_category', 'priority']
        )

        self.dlq_redrive_duration_seconds = Histogram(
            'dlq_redrive_duration_seconds',
            'Time taken to redrive DLQ entries',
            ['task_name']
        )

        # Gauges
        self.dlq_entries_by_status = Gauge(
            'dlq_entries_by_status',
            'Number of DLQ entries by status',
            ['status']
        )

        self.dlq_entries_by_category = Gauge(
            'dlq_entries_by_category',
            'Number of DLQ entries by error category',
            ['category']
        )

        self.dlq_entries_by_priority = Gauge(
            'dlq_entries_by_priority',
            'Number of DLQ entries by priority',
            ['priority']
        )

        self.dlq_health_score = Gauge(
            'dlq_health_score',
            'Overall DLQ system health score (0-100)',
            []
        )

        self.dlq_oldest_entry_age_hours = Gauge(
            'dlq_oldest_entry_age_hours',
            'Age of oldest DLQ entry in hours',
            []
        )

        self.dlq_pending_redrive_count = Gauge(
            'dlq_pending_redrive_count',
            'Number of entries pending redrive',
            []
        )

        # Info metrics
        self.dlq_system_info = Info(
            'dlq_system_info',
            'DLQ system information'
        )

    def record_dlq_entry_created(self, task_name: str, error_category: str, priority: str):
        """Record creation of a new DLQ entry."""
        self.dlq_entries_total.labels(
            task_name=task_name,
            error_category=error_category,
            priority=priority,
            status=DLQStatus.PENDING.value
        ).inc()

    def record_dlq_entry_updated(self, old_status: str, new_status: str, task_name: str, error_category: str, priority: str):
        """Record status change of a DLQ entry."""
        # Decrement old status counter
        self.dlq_entries_by_status.labels(status=old_status).dec()

        # Increment new status counter
        self.dlq_entries_by_status.labels(status=new_status).inc()

        # Update total counter with new status
        self.dlq_entries_total.labels(
            task_name=task_name,
            error_category=error_category,
            priority=priority,
            status=new_status
        ).inc()

    def record_redrive_attempt(self, task_name: str, success: bool, duration_seconds: float):
        """Record a redrive attempt."""
        self.dlq_redrive_attempts_total.labels(
            task_name=task_name,
            success=str(success).lower()
        ).inc()

        self.dlq_redrive_duration_seconds.labels(
            task_name=task_name
        ).observe(duration_seconds)

    def record_cleanup_operation(self, operation_type: str, entries_deleted: int):
        """Record a cleanup operation."""
        self.dlq_cleanup_operations_total.labels(
            operation_type=operation_type
        ).inc()

    def update_metrics_from_stats(self, stats: Dict[str, Any]):
        """Update Prometheus metrics from DLQ stats."""
        # Update by status
        self.dlq_entries_by_status.labels(status='pending').set(stats.get('pending_entries', 0))
        self.dlq_entries_by_status.labels(status='processing').set(stats.get('processing_entries', 0))
        self.dlq_entries_by_status.labels(status='completed').set(stats.get('completed_entries', 0))
        self.dlq_entries_by_status.labels(status='failed_permanently').set(stats.get('failed_permanently', 0))
        self.dlq_entries_by_status.labels(status='archived').set(stats.get('archived_entries', 0))

        # Update by category
        self.dlq_entries_by_category.labels(category='processing_error').set(stats.get('processing_errors', 0))
        self.dlq_entries_by_category.labels(category='validation_error').set(stats.get('validation_errors', 0))
        self.dlq_entries_by_category.labels(category='network_error').set(stats.get('network_errors', 0))
        self.dlq_entries_by_category.labels(category='database_error').set(stats.get('database_errors', 0))
        self.dlq_entries_by_category.labels(category='timeout_error').set(stats.get('timeout_errors', 0))
        self.dlq_entries_by_category.labels(category='business_rule_error').set(stats.get('business_rule_errors', 0))
        self.dlq_entries_by_category.labels(category='system_error').set(stats.get('system_errors', 0))
        self.dlq_entries_by_category.labels(category='unknown_error').set(stats.get('unknown_errors', 0))

        # Update by priority
        self.dlq_entries_by_priority.labels(priority='critical').set(stats.get('critical_entries', 0))
        self.dlq_entries_by_priority.labels(priority='high').set(stats.get('high_entries', 0))
        self.dlq_entries_by_priority.labels(priority='normal').set(stats.get('normal_entries', 0))
        self.dlq_entries_by_priority.labels(priority='low').set(stats.get('low_entries', 0))

        # Update age metrics
        self.dlq_oldest_entry_age_hours.set(stats.get('oldest_entry_age_hours', 0))
        self.dlq_pending_redrive_count.set(stats.get('pending_entries', 0))

        # Record entry ages as histogram
        if stats.get('avg_age_hours', 0) > 0:
            for category in ['processing_error', 'validation_error', 'network_error', 'database_error', 'timeout_error']:
                for priority in ['critical', 'high', 'normal', 'low']:
                    # Sample a few entries for histogram
                    self.dlq_entry_age_hours.labels(
                        error_category=category,
                        priority=priority
                    ).observe(stats.get('avg_age_hours', 0))

    def calculate_health_score(self, stats: Dict[str, Any]) -> float:
        """Calculate DLQ system health score (0-100)."""
        score = 100.0

        # Deduct points for issues
        total_entries = stats.get('total_entries', 0)

        if total_entries == 0:
            return 100.0  # Perfect health if no entries

        # High number of pending entries
        pending_ratio = stats.get('pending_entries', 0) / total_entries
        if pending_ratio > 0.5:
            score -= 20
        elif pending_ratio > 0.3:
            score -= 10
        elif pending_ratio > 0.1:
            score -= 5

        # High number of critical entries
        critical_ratio = stats.get('critical_entries', 0) / total_entries
        if critical_ratio > 0.1:
            score -= 30
        elif critical_ratio > 0.05:
            score -= 15
        elif critical_ratio > 0.01:
            score -= 5

        # High failure rate
        total_processed = stats.get('completed_entries', 0) + stats.get('failed_permanently', 0)
        if total_processed > 0:
            failure_rate = stats.get('failed_permanently', 0) / total_processed
            if failure_rate > 0.7:
                score -= 25
            elif failure_rate > 0.5:
                score -= 15
            elif failure_rate > 0.3:
                score -= 10

        # Old entries
        oldest_age = stats.get('oldest_entry_age_hours', 0)
        if oldest_age > 168:  # 1 week
            score -= 20
        elif oldest_age > 72:  # 3 days
            score -= 10
        elif oldest_age > 24:  # 1 day
            score -= 5

        # Error category issues
        system_errors = stats.get('system_errors', 0)
        database_errors = stats.get('database_errors', 0)
        if system_errors > 0:
            score -= 15
        if database_errors > 0:
            score -= 10

        return max(0.0, score)

    def evaluate_alert_rules(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate alert rules and return triggered alerts."""
        alerts = []

        # Alert rules configuration
        alert_rules = [
            {
                "name": "High DLQ Pending Count",
                "condition": stats.get('pending_entries', 0) > 100,
                "severity": "warning",
                "message": f"High number of pending DLQ entries: {stats.get('pending_entries', 0)}",
                "threshold": 100,
                "current_value": stats.get('pending_entries', 0),
            },
            {
                "name": "Critical DLQ Entries",
                "condition": stats.get('critical_entries', 0) > 10,
                "severity": "critical",
                "message": f"High number of critical DLQ entries: {stats.get('critical_entries', 0)}",
                "threshold": 10,
                "current_value": stats.get('critical_entries', 0),
            },
            {
                "name": "High DLQ Failure Rate",
                "condition": self._calculate_failure_rate(stats) > 0.5,
                "severity": "warning",
                "message": f"High DLQ failure rate: {self._calculate_failure_rate(stats):.1%}",
                "threshold": 0.5,
                "current_value": self._calculate_failure_rate(stats),
            },
            {
                "name": "Old DLQ Entries",
                "condition": stats.get('oldest_entry_age_hours', 0) > 24,
                "severity": "warning",
                "message": f"Old DLQ entries detected: {stats.get('oldest_entry_age_hours', 0):.1f} hours",
                "threshold": 24,
                "current_value": stats.get('oldest_entry_age_hours', 0),
            },
            {
                "name": "System Errors in DLQ",
                "condition": stats.get('system_errors', 0) > 0,
                "severity": "critical",
                "message": f"System errors detected in DLQ: {stats.get('system_errors', 0)}",
                "threshold": 0,
                "current_value": stats.get('system_errors', 0),
            },
            {
                "name": "DLQ Health Score Low",
                "condition": self.calculate_health_score(stats) < 70,
                "severity": "warning",
                "message": f"DLQ health score is low: {self.calculate_health_score(stats):.1f}",
                "threshold": 70,
                "current_value": self.calculate_health_score(stats),
            },
        ]

        # Evaluate rules
        for rule in alert_rules:
            if rule["condition"]:
                alerts.append({
                    "alert_type": "dlq_monitoring",
                    "severity": rule["severity"],
                    "title": rule["name"],
                    "message": rule["message"],
                    "metadata": {
                        "threshold": rule["threshold"],
                        "current_value": rule["current_value"],
                        "rule_name": rule["name"],
                    }
                })

        return alerts

    def _calculate_failure_rate(self, stats: Dict[str, Any]) -> float:
        """Calculate DLQ failure rate."""
        total_processed = stats.get('completed_entries', 0) + stats.get('failed_permanently', 0)
        if total_processed == 0:
            return 0.0
        return stats.get('failed_permanently', 0) / total_processed

    def update_system_info(self):
        """Update DLQ system information."""
        self.dlq_system_info.info({
            'version': '1.0.0',
            'environment': settings.ENVIRONMENT,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive DLQ metrics."""
        try:
            from app.services.dlq_service import DLQService
            dlq_service = DLQService(self.db)

            # Get stats
            stats = dlq_service.get_dlq_stats(days=1)
            stats_dict = stats.dict()

            # Update Prometheus metrics
            self.update_metrics_from_stats(stats_dict)

            # Calculate health score
            health_score = self.calculate_health_score(stats_dict)
            self.dlq_health_score.set(health_score)

            # Update system info
            self.update_system_info()

            # Evaluate alert rules
            alerts = self.evaluate_alert_rules(stats_dict)

            # Send alerts if service is available
            if self.alert_service and alerts:
                for alert in alerts:
                    try:
                        self.alert_service.create_alert(
                            alert_type=alert["alert_type"],
                            severity=alert["severity"],
                            message=alert["message"],
                            metadata=alert["metadata"]
                        )
                        logger.info(f"Created DLQ alert: {alert['title']}")
                    except Exception as e:
                        logger.error(f"Failed to create DLQ alert: {e}")

            return {
                "stats": stats_dict,
                "health_score": health_score,
                "alerts_triggered": len(alerts),
                "alerts": alerts,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to collect DLQ metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current DLQ metrics."""
        try:
            from app.services.dlq_service import DLQService
            dlq_service = DLQService(self.db)

            # Get stats for different time periods
            stats_1d = dlq_service.get_dlq_stats(days=1)
            stats_7d = dlq_service.get_dlq_stats(days=7)
            stats_30d = dlq_service.get_dlq_stats(days=30)

            # Calculate trends
            trend_1d_vs_7d = {
                "entries_growth": stats_1d.total_entries - stats_7d.total_entries,
                "pending_growth": stats_1d.pending_entries - stats_7d.pending_entries,
                "completion_rate_1d": (
                    stats_1d.completed_entries / max(stats_1d.total_entries, 1)
                ),
                "completion_rate_7d": (
                    stats_7d.completed_entries / max(stats_7d.total_entries, 1)
                ),
            }

            return {
                "current_health_score": self.calculate_health_score(stats_1d.dict()),
                "stats": {
                    "last_24_hours": stats_1d.dict(),
                    "last_7_days": stats_7d.dict(),
                    "last_30_days": stats_30d.dict(),
                },
                "trends": trend_1d_vs_7d,
                "top_error_categories": self._get_top_error_categories(stats_1d.dict()),
                "critical_entries": stats_1d.dict().get('critical_entries', 0),
                "urgent_attention": (
                    stats_1d.dict().get('critical_entries', 0) > 0 or
                    stats_1d.dict().get('system_errors', 0) > 0
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _get_top_error_categories(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get top error categories by count."""
        categories = [
            {"name": "Processing Errors", "count": stats.get('processing_errors', 0)},
            {"name": "Validation Errors", "count": stats.get('validation_errors', 0)},
            {"name": "Network Errors", "count": stats.get('network_errors', 0)},
            {"name": "Database Errors", "count": stats.get('database_errors', 0)},
            {"name": "Timeout Errors", "count": stats.get('timeout_errors', 0)},
            {"name": "Business Rule Errors", "count": stats.get('business_rule_errors', 0)},
            {"name": "System Errors", "count": stats.get('system_errors', 0)},
            {"name": "Unknown Errors", "count": stats.get('unknown_errors', 0)},
        ]

        # Sort by count and return top 5
        return sorted(categories, key=lambda x: x['count'], reverse=True)[:5]