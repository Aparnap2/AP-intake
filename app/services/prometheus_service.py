"""
Prometheus metrics exposition service for AP Intake & Validation system.
"""

import logging
import time
from typing import Dict, Any, List
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
from fastapi import Response

logger = logging.getLogger(__name__)


class PrometheusService:
    """Service for managing Prometheus metrics collection and exposition."""

    def __init__(self):
        """Initialize the Prometheus service with custom metrics."""
        self.registry = CollectorRegistry()

        # Business metrics
        self.invoices_processed_total = Counter(
            'ap_intake_invoices_processed_total',
            'Total number of invoices processed',
            ['status', 'vendor'],
            registry=self.registry
        )

        self.processing_duration_seconds = Histogram(
            'ap_intake_processing_duration_seconds',
            'Time spent processing invoices',
            ['step', 'status'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 300.0],
            registry=self.registry
        )

        self.extraction_confidence = Histogram(
            'ap_intake_extraction_confidence',
            'Document extraction confidence scores',
            ['parser_version'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0],
            registry=self.registry
        )

        self.validation_results_total = Counter(
            'ap_intake_validation_results_total',
            'Total number of validation results',
            ['result', 'validation_errors'],
            registry=self.registry
        )

        self.exception_count_total = Counter(
            'ap_intake_exceptions_total',
            'Total number of processing exceptions',
            ['exception_type', 'severity'],
            registry=self.registry
        )

        # System metrics
        self.active_workflows = Gauge(
            'ap_intake_active_workflows',
            'Number of currently active workflows',
            registry=self.registry
        )

        self.queue_size = Gauge(
            'ap_intake_queue_size',
            'Number of items in processing queue',
            ['queue_name'],
            registry=self.registry
        )

        self.database_connections = Gauge(
            'ap_intake_database_connections',
            'Number of active database connections',
            ['pool'],
            registry=self.registry
        )

        # SLO metrics
        self.slo_achieved_percentage = Gauge(
            'ap_intake_slo_achieved_percentage',
            'SLO achieved percentage',
            ['slo_name', 'sli_type', 'period'],
            registry=self.registry
        )

        self.error_budget_consumed = Gauge(
            'ap_intake_error_budget_consumed',
            'Error budget consumed percentage',
            ['slo_name', 'sli_type'],
            registry=self.registry
        )

        self.slo_alerts_total = Counter(
            'ap_intake_slo_alerts_total',
            'Total number of SLO alerts',
            ['slo_name', 'alert_type', 'severity'],
            registry=self.registry
        )

        # Performance metrics
        self.api_requests_total = Counter(
            'ap_intake_api_requests_total',
            'Total number of API requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )

        self.api_request_duration_seconds = Histogram(
            'ap_intake_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )

        # Resource metrics
        self.memory_usage_bytes = Gauge(
            'ap_intake_memory_usage_bytes',
            'Memory usage in bytes',
            ['component'],
            registry=self.registry
        )

        self.cpu_usage_percent = Gauge(
            'ap_intake_cpu_usage_percent',
            'CPU usage percentage',
            ['component'],
            registry=self.registry
        )

        logger.info("Prometheus metrics service initialized")

    def record_invoice_processed(self, status: str, vendor: str = "unknown") -> None:
        """Record a processed invoice."""
        self.invoices_processed_total.labels(status=status, vendor=vendor).inc()

    def record_processing_step(self, step: str, duration_seconds: float, status: str = "success") -> None:
        """Record a processing step duration."""
        self.processing_duration_seconds.labels(step=step, status=status).observe(duration_seconds)

    def record_extraction_confidence(self, confidence: float, parser_version: str = "unknown") -> None:
        """Record extraction confidence score."""
        self.extraction_confidence.labels(parser_version=parser_version).observe(confidence)

    def record_validation_result(self, result: str, validation_errors: int = 0) -> None:
        """Record validation result."""
        error_bucket = "0" if validation_errors == 0 else "1" if validation_errors <= 3 else "3+"
        self.validation_results_total.labels(result=result, validation_errors=error_bucket).inc()

    def record_exception(self, exception_type: str, severity: str = "error") -> None:
        """Record a processing exception."""
        self.exception_count_total.labels(exception_type=exception_type, severity=severity).inc()

    def set_active_workflows(self, count: int) -> None:
        """Set the number of active workflows."""
        self.active_workflows.set(count)

    def set_queue_size(self, queue_name: str, size: int) -> None:
        """Set queue size."""
        self.queue_size.labels(queue_name=queue_name).set(size)

    def set_database_connections(self, pool: str, connections: int) -> None:
        """Set database connection count."""
        self.database_connections.labels(pool=pool).set(connections)

    def update_slo_metrics(self, slo_name: str, sli_type: str, achieved_percentage: float,
                          error_budget_consumed: float, period: str = "daily") -> None:
        """Update SLO metrics."""
        self.slo_achieved_percentage.labels(
            slo_name=slo_name,
            sli_type=sli_type,
            period=period
        ).set(achieved_percentage)

        self.error_budget_consumed.labels(
            slo_name=slo_name,
            sli_type=sli_type
        ).set(error_budget_consumed)

    def record_slo_alert(self, slo_name: str, alert_type: str, severity: str) -> None:
        """Record an SLO alert."""
        self.slo_alerts_total.labels(
            slo_name=slo_name,
            alert_type=alert_type,
            severity=severity
        ).inc()

    def record_api_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
        """Record an API request."""
        status_group = str(status_code)[0] + "xx"  # e.g., "2xx", "4xx", "5xx"

        self.api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status_group
        ).inc()

        self.api_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration_seconds)

    def set_memory_usage(self, component: str, bytes_used: int) -> None:
        """Set memory usage for a component."""
        self.memory_usage_bytes.labels(component=component).set(bytes_used)

    def set_cpu_usage(self, component: str, percent_used: float) -> None:
        """Set CPU usage for a component."""
        self.cpu_usage_percent.labels(component=component).set(percent_used)

    def get_metrics_response(self) -> Response:
        """Get Prometheus metrics as HTTP response."""
        try:
            metrics_data = generate_latest(self.registry)
            return Response(
                content=metrics_data,
                media_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            logger.error(f"Failed to generate Prometheus metrics: {e}")
            return Response(
                content=f"Error generating metrics: {str(e)}",
                status_code=500
            )

    async def update_system_metrics(self) -> None:
        """Update system-level metrics."""
        try:
            import psutil
            import os

            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            self.set_memory_usage("api_server", memory_info.rss)

            # Get CPU usage
            cpu_percent = process.cpu_percent()
            self.set_cpu_usage("api_server", cpu_percent)

            # Log system metrics
            logger.debug(f"Updated system metrics - Memory: {memory_info.rss / 1024 / 1024:.1f}MB, CPU: {cpu_percent}%")

        except ImportError:
            logger.warning("psutil not available, system metrics not updated")
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")

    async def update_from_database(self) -> None:
        """Update metrics from database data."""
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.metrics import SLODefinition, SLIMeasurement
            from sqlalchemy import select, func
            from datetime import datetime, timedelta

            async with AsyncSessionLocal() as session:
                # Get latest SLO measurements
                now = datetime.utcnow()
                day_ago = now - timedelta(days=1)

                # Get all active SLOs
                slo_query = select(SLODefinition).where(SLODefinition.is_active == True)
                slo_result = await session.execute(slo_query)
                slos = slo_result.scalars().all()

                for slo in slos:
                    # Get latest measurement for each SLO
                    measurement_query = select(SLIMeasurement).where(
                        SLIMeasurement.slo_definition_id == slo.id,
                        SLIMeasurement.period_start >= day_ago
                    ).order_by(SLIMeasurement.period_start.desc()).limit(1)

                    measurement_result = await session.execute(measurement_query)
                    measurement = measurement_result.scalar_one_or_none()

                    if measurement:
                        self.update_slo_metrics(
                            slo_name=slo.name,
                            sli_type=slo.sli_type.value,
                            achieved_percentage=float(measurement.achieved_percentage),
                            error_budget_consumed=float(measurement.error_budget_consumed),
                            period=measurement.measurement_period.value
                        )

                logger.debug(f"Updated metrics for {len(slos)} SLOs from database")

        except Exception as e:
            logger.error(f"Failed to update metrics from database: {e}")


# Singleton instance
prometheus_service = PrometheusService()