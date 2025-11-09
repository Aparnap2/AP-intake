"""
Background tasks for metrics collection and SLO calculations.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.metrics_service import metrics_service
from app.models.metrics import SLOPeriod

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "metrics_tasks",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="calculate_sli_measurements")
def calculate_sli_measurements_task(
    self,
    period: str = "daily",
    hours_back: int = 24,
    force_recalculate: bool = False,
) -> Dict[str, Any]:
    """
    Calculate SLI measurements for a given period.

    Args:
        period: Measurement period (hourly, daily, weekly, monthly)
        hours_back: How many hours back to calculate
        force_recalculate: Whether to recalculate existing measurements

    Returns:
        Dict with calculation results
    """
    try:
        logger.info(f"Starting SLI measurement calculation for {period} period, {hours_back} hours back")

        # Convert period string to enum
        try:
            slo_period = SLOPeriod(period)
        except ValueError:
            logger.error(f"Invalid period: {period}")
            return {"success": False, "error": f"Invalid period: {period}"}

        # Calculate time boundaries
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=hours_back)

        # Run async calculation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            measurements = loop.run_until_complete(
                metrics_service.calculate_sli_measurements(
                    period=slo_period,
                    period_start=start_date,
                    period_end=end_date
                )
            )

            # Check for alerts and create them
            alert_count = 0
            for measurement in measurements:
                alerts = loop.run_until_complete(
                    metrics_service.check_and_create_alerts(measurement)
                )
                alert_count += len(alerts)

            result = {
                "success": True,
                "period": period,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "measurements_created": len(measurements),
                "alerts_created": alert_count,
                "calculated_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Successfully calculated {len(measurements)} measurements and {alert_count} alerts")
            return result

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to calculate SLI measurements: {e}")
        return {
            "success": False,
            "error": str(e),
            "period": period,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }


@celery_app.task(bind=True, name="initialize_default_slos")
def initialize_default_slos_task(self) -> Dict[str, Any]:
    """
    Initialize default SLO definitions for the system.

    Returns:
        Dict with initialization results
    """
    try:
        logger.info("Starting default SLO initialization")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(metrics_service.initialize_default_slos())

            result = {
                "success": True,
                "message": "Default SLOs initialized successfully",
                "initialized_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("Successfully initialized default SLOs")
            return result

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to initialize default SLOs: {e}")
        return {
            "success": False,
            "error": str(e),
            "initialized_at": datetime.now(timezone.utc).isoformat(),
        }


@celery_app.task(bind=True, name="cleanup_old_metrics")
def cleanup_old_metrics_task(
    self,
    retention_days: int = 90,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Clean up old metrics data based on retention policy.

    Args:
        retention_days: Number of days to retain metrics
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting metrics cleanup for data older than {retention_days} days")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            async with AsyncSessionLocal() as session:
                from app.models.metrics import SLIMeasurement, SLOAlert, InvoiceMetric
                from sqlalchemy import select, delete

                # Count measurements to delete
                measurement_query = select(SLIMeasurement).where(
                    SLIMeasurement.created_at < cutoff_date
                )
                measurement_result = await session.execute(measurement_query)
                measurements_to_delete = len(measurement_result.scalars().all())

                # Count alerts to delete (resolved and older than cutoff)
                alert_query = select(SLOAlert).where(
                    SLOAlert.created_at < cutoff_date
                )
                alert_result = await session.execute(alert_query)
                alerts_to_delete = len(alert_result.scalars().all())

                # Count invoice metrics to delete
                invoice_metric_query = select(InvoiceMetric).where(
                    InvoiceMetric.created_at < cutoff_date
                )
                invoice_metric_result = await session.execute(invoice_metric_query)
                invoice_metrics_to_delete = len(invoice_metric_result.scalars().all())

                if not dry_run:
                    # Delete old measurements
                    await session.execute(
                        delete(SLIMeasurement).where(SLIMeasurement.created_at < cutoff_date)
                    )

                    # Delete old alerts
                    await session.execute(
                        delete(SLOAlert).where(SLOAlert.created_at < cutoff_date)
                    )

                    # Delete old invoice metrics
                    await session.execute(
                        delete(InvoiceMetric).where(InvoiceMetric.created_at < cutoff_date)
                    )

                    await session.commit()

                result = {
                    "success": True,
                    "retention_days": retention_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "measurements_deleted": measurements_to_delete,
                    "alerts_deleted": alerts_to_delete,
                    "invoice_metrics_deleted": invoice_metrics_to_delete,
                    "dry_run": dry_run,
                    "cleaned_at": datetime.now(timezone.utc).isoformat(),
                }

                logger.info(f"Cleanup completed: {measurements_to_delete} measurements, "
                           f"{alerts_to_delete} alerts, {invoice_metrics_to_delete} invoice metrics "
                           f"{'(dry run)' if dry_run else '(deleted)'}")

                return result

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to cleanup old metrics: {e}")
        return {
            "success": False,
            "error": str(e),
            "retention_days": retention_days,
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        }


@celery_app.task(bind=True, name="generate_slo_report")
def generate_slo_report_task(
    self,
    report_type: str = "daily",
    days: int = 1,
    send_email: bool = False,
    recipients: list = None,
) -> Dict[str, Any]:
    """
    Generate SLO performance report.

    Args:
        report_type: Type of report (daily, weekly, monthly)
        days: Number of days to include in report
        send_email: Whether to send report via email
        recipients: List of email recipients

    Returns:
        Dict with report generation results
    """
    try:
        logger.info(f"Generating {report_type} SLO report for {days} days")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Get dashboard data
            dashboard_data = loop.run_until_complete(
                metrics_service.get_slo_dashboard_data(time_range_days=days)
            )

            # Get KPI summary
            kpi_summary = loop.run_until_complete(
                metrics_service.get_kpi_summary(days=days)
            )

            # Generate report
            report = {
                "report_type": report_type,
                "period": {
                    "start_date": dashboard_data["time_range"]["start_date"],
                    "end_date": dashboard_data["time_range"]["end_date"],
                    "days": days,
                },
                "slo_summary": dashboard_data["summary"],
                "slos": dashboard_data["slos"],
                "alerts": dashboard_data["alerts"],
                "kpi_summary": kpi_summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = {
                "success": True,
                "report": report,
                "report_type": report_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            # TODO: Implement email sending if requested
            if send_email and recipients:
                logger.info(f"Report would be sent to {recipients} (email sending not implemented)")

            logger.info(f"Successfully generated {report_type} SLO report")
            return result

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to generate SLO report: {e}")
        return {
            "success": False,
            "error": str(e),
            "report_type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Calculate daily SLI measurements
    "calculate-daily-sli": {
        "task": "calculate_sli_measurements",
        "schedule": crontab(hour=1, minute=5),  # 1:05 AM UTC
        "args": ("daily", 24),
    },

    # Calculate hourly SLI measurements for critical SLOs
    "calculate-hourly-sli": {
        "task": "calculate_sli_measurements",
        "schedule": crontab(minute=5),  # Every hour at 5 minutes past
        "args": ("hourly", 1),
    },

    # Calculate weekly SLI measurements
    "calculate-weekly-sli": {
        "task": "calculate_sli_measurements",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Monday 2:00 AM UTC
        "args": ("weekly", 168),  # 7 days = 168 hours
    },

    # Generate daily report
    "generate-daily-report": {
        "task": "generate_slo_report",
        "schedule": crontab(hour=8, minute=0),  # 8:00 AM UTC
        "args": ("daily", 1),
    },

    # Generate weekly report
    "generate-weekly-report": {
        "task": "generate_slo_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday 9:00 AM UTC
        "args": ("weekly", 7),
    },

    # Cleanup old metrics (monthly)
    "cleanup-old-metrics": {
        "task": "cleanup_old_metrics_task",
        "schedule": crontab(hour=3, minute=0, day=1),  # 1st of month 3:00 AM UTC
        "args": (90, False),  # 90 days retention, not dry run
    },
}