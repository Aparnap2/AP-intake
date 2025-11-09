"""
Background tasks for scheduled report generation and delivery.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.db.session import get_async_session
from app.services.weekly_report_service import WeeklyReportService
from app.services.email_report_service import EmailReportService
from app.models.reports import WeeklyReport, ReportType, ReportStatus, ReportSubscription
from app.core.logging import get_logger

logger = get_logger(__name__)

# Initialize Celery
celery_app = Celery('report_tasks')


@celery_app.task(bind=True, max_retries=3)
def generate_weekly_report_task(
    self,
    week_start_iso: str,
    template_id: str = None,
    generated_by: str = None
) -> Dict[str, Any]:
    """Generate weekly report in background."""
    try:
        logger.info(f"Starting weekly report generation for week {week_start_iso}")

        # Parse date
        week_start = datetime.fromisoformat(week_start_iso.replace('Z', '+00:00'))
        if week_start.tzinfo is None:
            week_start = week_start.replace(tzinfo=timezone.utc)

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_generate_report_async(
            week_start, template_id, generated_by
        ))

        logger.info(f"Weekly report generation completed: {result.get('report_id')}")
        return result

    except Exception as exc:
        logger.error(f"Weekly report generation failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _generate_report_async(
    week_start: datetime,
    template_id: str = None,
    generated_by: str = None
) -> Dict[str, Any]:
    """Async helper for report generation."""
    async with get_async_session() as session:
        try:
            report_service = WeeklyReportService(session)
            report = await report_service.generate_weekly_report(
                week_start=week_start,
                template_id=template_id,
                generated_by=generated_by
            )

            return {
                "report_id": str(report.id),
                "status": report.status.value,
                "week_start": week_start.isoformat(),
                "message": "Report generated successfully"
            }

        except Exception as e:
            logger.error(f"Async report generation failed: {e}")
            raise


@celery_app.task(bind=True, max_retries=3)
def send_scheduled_reports_task(self) -> Dict[str, Any]:
    """Send scheduled reports to subscribers."""
    try:
        logger.info("Starting scheduled report delivery")

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_send_scheduled_reports_async())

        logger.info(f"Scheduled report delivery completed: {result.get('deliveries_sent', 0)} deliveries")
        return result

    except Exception as exc:
        logger.error(f"Scheduled report delivery failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _send_scheduled_reports_async() -> Dict[str, Any]:
    """Async helper for scheduled report delivery."""
    async with get_async_session() as session:
        try:
            email_service = EmailReportService(session)
            deliveries = await email_service.send_scheduled_reports()

            return {
                "deliveries_sent": len(deliveries),
                "delivery_ids": [str(d.id) for d in deliveries],
                "message": "Scheduled reports sent successfully"
            }

        except Exception as e:
            logger.error(f"Async scheduled report delivery failed: {e}")
            raise


@celery_app.task(bind=True, max_retries=3)
def generate_and_send_weekly_report_task(
    self,
    week_start_iso: str = None,
    send_email: bool = True,
    recipient_groups: list = None
) -> Dict[str, Any]:
    """Generate and send weekly report in one task."""
    try:
        logger.info("Starting generate and send weekly report task")

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_generate_and_send_async(
            week_start_iso, send_email, recipient_groups
        ))

        logger.info(f"Generate and send task completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Generate and send task failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _generate_and_send_async(
    week_start_iso: str = None,
    send_email: bool = True,
    recipient_groups: list = None
) -> Dict[str, Any]:
    """Async helper for generate and send task."""
    async with get_async_session() as session:
        try:
            # Generate report
            if week_start_iso:
                week_start = datetime.fromisoformat(week_start_iso.replace('Z', '+00:00'))
                if week_start.tzinfo is None:
                    week_start = week_start.replace(tzinfo=timezone.utc)
            else:
                # Default to last week
                today = datetime.now(timezone.utc).date()
                days_since_monday = today.weekday()
                week_start = datetime.combine(
                    today - timedelta(days=days_since_monday + 7),
                    datetime.min.time(),
                    tzinfo=timezone.utc
                )

            report_service = WeeklyReportService(session)
            report = await report_service.generate_weekly_report(
                week_start=week_start,
                generated_by="system"
            )

            result = {
                "report_id": str(report.id),
                "report_status": report.status.value,
                "week_start": week_start.isoformat()
            }

            # Send email if requested
            if send_email and report.status == ReportStatus.COMPLETED:
                email_service = EmailReportService(session)
                deliveries = await email_service.send_weekly_report(
                    report_id=str(report.id),
                    recipient_groups=recipient_groups or ["executive", "operations", "finance"]
                )

                result.update({
                    "email_sent": True,
                    "deliveries_count": len(deliveries),
                    "delivery_ids": [str(d.id) for d in deliveries]
                })
            else:
                result.update({
                    "email_sent": False,
                    "reason": "send_email=False or report not completed"
                })

            return result

        except Exception as e:
            logger.error(f"Async generate and send task failed: {e}")
            raise


@celery_app.task
def cleanup_old_reports_task(days_to_keep: int = 90) -> Dict[str, Any]:
    """Clean up old reports and delivery records."""
    try:
        logger.info(f"Starting cleanup of reports older than {days_to_keep} days")

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_cleanup_old_reports_async(days_to_keep))

        logger.info(f"Cleanup completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Report cleanup failed: {exc}")
        raise


async def _cleanup_old_reports_async(days_to_keep: int) -> Dict[str, Any]:
    """Async helper for report cleanup."""
    async with get_async_session() as session:
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            # Count old reports
            count_query = select(WeeklyReport).where(
                WeeklyReport.created_at < cutoff_date
            )
            count_result = await session.execute(count_query)
            old_reports = count_result.scalars().all()

            reports_deleted = 0
            deliveries_deleted = 0

            for report in old_reports:
                # Delete associated deliveries
                for delivery in report.deliveries:
                    await session.delete(delivery)
                    deliveries_deleted += 1

                # Delete report
                await session.delete(report)
                reports_deleted += 1

            await session.commit()

            return {
                "reports_deleted": reports_deleted,
                "deliveries_deleted": deliveries_deleted,
                "cutoff_date": cutoff_date.isoformat(),
                "message": f"Cleaned up {reports_deleted} old reports and {deliveries_deleted} deliveries"
            }

        except Exception as e:
            logger.error(f"Async report cleanup failed: {e}")
            await session.rollback()
            raise


@celery_app.task
def generate_cost_analysis_task(
    week_start_iso: str,
    week_end_iso: str
) -> Dict[str, Any]:
    """Generate cost analysis for a specific week."""
    try:
        logger.info(f"Starting cost analysis for week {week_start_iso} to {week_end_iso}")

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_generate_cost_analysis_async(
            week_start_iso, week_end_iso
        ))

        logger.info(f"Cost analysis completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Cost analysis failed: {exc}")
        raise


async def _generate_cost_analysis_async(
    week_start_iso: str,
    week_end_iso: str
) -> Dict[str, Any]:
    """Async helper for cost analysis."""
    async with get_async_session() as session:
        try:
            from app.services.analytics_engine import AnalyticsEngine

            week_start = datetime.fromisoformat(week_start_iso.replace('Z', '+00:00'))
            if week_start.tzinfo is None:
                week_start = week_start.replace(tzinfo=timezone.utc)

            week_end = datetime.fromisoformat(week_end_iso.replace('Z', '+00:00'))
            if week_end.tzinfo is None:
                week_end = week_end.replace(tzinfo=timezone.utc)

            analytics_engine = AnalyticsEngine(session)
            cost_analysis = await analytics_engine.calculate_weekly_cost_analysis(
                week_start, week_end
            )

            return {
                "week_start": week_start_iso,
                "week_end": week_end_iso,
                "cost_per_invoice": cost_analysis.cost_per_invoice,
                "total_cost": cost_analysis.total_processing_cost,
                "total_invoices": cost_analysis.total_invoices_processed,
                "efficiency_score": cost_analysis.cost_efficiency_score,
                "roi_percentage": cost_analysis.roi_percentage,
                "message": "Cost analysis generated successfully"
            }

        except Exception as e:
            logger.error(f"Async cost analysis failed: {e}")
            raise


@celery_app.task
def retry_failed_deliveries_task() -> Dict[str, Any]:
    """Retry failed report deliveries."""
    try:
        logger.info("Starting retry of failed deliveries")

        # Run async task in sync context
        import asyncio
        result = asyncio.run(_retry_failed_deliveries_async())

        logger.info(f"Retry task completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Retry failed deliveries task failed: {exc}")
        raise


async def _retry_failed_deliveries_async() -> Dict[str, Any]:
    """Async helper for retrying failed deliveries."""
    async with get_async_session() as session:
        try:
            email_service = EmailReportService(session)

            # Get reports with failed deliveries from the last 24 hours
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            reports_query = select(WeeklyReport).where(
                and_(
                    WeeklyReport.created_at >= yesterday,
                    WeeklyReport.status == ReportStatus.COMPLETED
                )
            )
            reports_result = await session.execute(reports_query)
            recent_reports = reports_result.scalars().all()

            total_retried = 0
            for report in recent_reports:
                retried = await email_service.retry_failed_deliveries(str(report.id))
                total_retried += len(retried)

            return {
                "deliveries_retried": total_retried,
                "reports_checked": len(recent_reports),
                "message": f"Retried {total_retried} failed deliveries"
            }

        except Exception as e:
            logger.error(f"Async retry failed deliveries task failed: {e}")
            raise


# Schedule configuration
from celery.schedules import crontab

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    # Generate weekly report every Monday at 8 AM UTC
    'generate-weekly-report': {
        'task': 'app.workers.report_tasks.generate_and_send_weekly_report_task',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),
        'args': ()
    },

    # Send scheduled reports every weekday at 9 AM UTC
    'send-scheduled-reports': {
        'task': 'app.workers.report_tasks.send_scheduled_reports_task',
        'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),
        'args': ()
    },

    # Retry failed deliveries every 2 hours
    'retry-failed-deliveries': {
        'task': 'app.workers.report_tasks.retry_failed_deliveries_task',
        'schedule': crontab(minute=0, hour='*/2'),
        'args': ()
    },

    # Cleanup old reports weekly on Sunday at 2 AM UTC
    'cleanup-old-reports': {
        'task': 'app.workers.report_tasks.cleanup_old_reports_task',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
        'args': (90,)  # Keep 90 days
    },

    # Generate cost analysis every Friday at 5 PM UTC
    'generate-cost-analysis': {
        'task': 'app.workers.report_tasks.generate_cost_analysis_task',
        'schedule': crontab(hour=17, minute=0, day_of_week=5),
        'args': ()  # Will be calculated dynamically
    }
}

# Celery configuration
celery_app.conf.timezone = 'UTC'
celery_app.conf.enable_utc = True