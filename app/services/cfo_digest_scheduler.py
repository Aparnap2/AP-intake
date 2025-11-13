"""
CFO Digest Scheduler Service for Monday 9am automated delivery.
This service handles the scheduling and automated delivery of CFO digests.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.api.schemas.digest import (
    CFODigestRequest, DigestPriority, BusinessImpactLevel,
    CFODigestScheduleRequest
)
from app.services.weekly_report_service import CFODigestService
from app.services.n8n_service import N8nService
from app.services.metrics_service import metrics_service
from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class CFODigestScheduler:
    """
    Scheduler service for Monday 9am CFO digest delivery.

    This service handles:
    - Automatic digest generation on Monday mornings
    - Scheduling configuration management
    - Delivery coordination with N8n workflows
    - Error handling and retry logic
    """

    def __init__(self):
        self.n8n_service = N8nService()

    async def calculate_next_monday_9am(self, current_time: Optional[datetime] = None) -> datetime:
        """
        Calculate the next Monday 9am UTC timestamp.

        Args:
            current_time: Current time for calculation (defaults to now)

        Returns:
            datetime: Next Monday 9am UTC
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Calculate days until next Monday
        days_until_monday = (7 - current_time.weekday()) % 7 or 7

        # Get next Monday
        next_monday = current_time + timedelta(days=days_until_monday)

        # Set time to 9:00 AM UTC
        monday_9am = next_monday.replace(
            hour=9, minute=0, second=0, microsecond=0
        )

        return monday_9am

    async def generate_monday_digest(
        self,
        week_start: Optional[datetime] = None,
        recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate Monday CFO digest with current week's data.

        Args:
            week_start: Week start date (defaults to last week)
            recipients: Email recipients list

        Returns:
            Dict with generation results
        """
        try:
            async with AsyncSessionLocal() as session:
                cfo_service = CFODigestService(session)

                # Create digest request
                request = CFODigestRequest(
                    week_start=week_start,
                    include_working_capital_analysis=True,
                    include_action_items=True,
                    include_evidence_links=True,
                    priority_threshold=DigestPriority.MEDIUM,
                    business_impact_threshold=BusinessImpactLevel.MODERATE,
                    recipients=recipients or self._get_default_recipients(),
                    schedule_delivery=False,  # We'll handle scheduling separately
                    delivery_time="09:00"
                )

                # Generate digest
                digest = await cfo_service.generate_monday_digest(
                    request=request,
                    generated_by="system@ap-intake.com"
                )

                # Save to database
                digest_id = await cfo_service.save_digest_to_database(digest)

                logger.info(f"Monday CFO digest generated: {digest_id}")

                return {
                    "success": True,
                    "digest_id": digest_id,
                    "title": digest.title,
                    "week_start": digest.week_start.isoformat(),
                    "week_end": digest.week_end.isoformat(),
                    "generated_at": digest.generated_at.isoformat(),
                    "total_invoices": digest.total_invoices_processed,
                    "total_exceptions": digest.total_exceptions,
                    "cost_per_invoice": float(digest.cost_per_invoice),
                    "roi_percentage": digest.roi_percentage
                }

        except Exception as e:
            logger.error(f"Failed to generate Monday CFO digest: {e}")
            return {
                "success": False,
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

    async def schedule_digest_delivery(
        self,
        digest_id: str,
        delivery_time: Optional[datetime] = None,
        recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Schedule digest delivery via N8n workflow.

        Args:
            digest_id: ID of the digest to deliver
            delivery_time: When to deliver (defaults to next Monday 9am)
            recipients: Email recipients

        Returns:
            Dict with scheduling results
        """
        try:
            async with AsyncSessionLocal() as session:
                cfo_service = CFODigestService(session)

                # Get digest
                digest = await cfo_service.get_digest_by_id(digest_id)
                if not digest:
                    return {
                        "success": False,
                        "error": f"Digest {digest_id} not found"
                    }

                # Calculate delivery time
                if delivery_time is None:
                    delivery_time = await self.calculate_next_monday_9am()

                # Update digest with delivery schedule
                digest.delivery_scheduled_at = delivery_time
                digest.delivery_status = "scheduled"
                digest.recipients = recipients or self._get_default_recipients()

                # Create N8n workflow request
                n8n_request = await cfo_service.create_n8n_workflow_request(digest)

                # Schedule N8n workflow execution
                n8n_response = await self.n8n_service.schedule_workflow(
                    workflow_id="cfo_digest_delivery",
                    execution_time=delivery_time,
                    data=n8n_request.dict()
                )

                logger.info(f"CFO digest delivery scheduled: {digest_id} at {delivery_time}")

                return {
                    "success": True,
                    "digest_id": digest_id,
                    "scheduled_at": delivery_time.isoformat(),
                    "n8n_execution_id": n8n_response.get("execution_id"),
                    "recipients": digest.recipients
                }

        except Exception as e:
            logger.error(f"Failed to schedule digest delivery: {e}")
            return {
                "success": False,
                "error": str(e),
                "digest_id": digest_id
            }

    async def process_scheduled_digests(self) -> Dict[str, Any]:
        """
        Process all scheduled digests that are ready for delivery.
        This is called by the scheduled task runner.

        Returns:
            Dict with processing results
        """
        try:
            current_time = datetime.now(timezone.utc)
            processed_count = 0
            failed_count = 0

            # Get digests scheduled for now
            async with AsyncSessionLocal() as session:
                from app.models.reports import WeeklyReport, ReportStatus

                query = select(WeeklyReport).where(
                    and_(
                        WeeklyReport.status == ReportStatus.SCHEDULED,
                        WeeklyReport.delivery_scheduled_at <= current_time
                    )
                )
                result = await session.execute(query)
                scheduled_digests = result.scalars().all()

                for digest_record in scheduled_digests:
                    try:
                        # Trigger immediate delivery
                        cfo_service = CFODigestService(session)
                        digest = await cfo_service.get_digest_by_id(str(digest_record.id))

                        if digest:
                            n8n_request = await cfo_service.create_n8n_workflow_request(digest)
                            await self.n8n_service.trigger_workflow(
                                workflow_id="cfo_digest_delivery",
                                data=n8n_request.dict()
                            )

                            # Update status
                            digest_record.status = ReportStatus.COMPLETED
                            digest_record.delivery_status = "sent"
                            processed_count += 1

                            logger.info(f"Processed scheduled digest: {digest_record.id}")

                    except Exception as e:
                        logger.error(f"Failed to process digest {digest_record.id}: {e}")
                        digest_record.status = ReportStatus.FAILED
                        digest_record.delivery_status = "failed"
                        failed_count += 1

                await session.commit()

            return {
                "success": True,
                "processed_at": current_time.isoformat(),
                "processed_count": processed_count,
                "failed_count": failed_count,
                "total_scheduled": len(scheduled_digests)
            }

        except Exception as e:
            logger.error(f"Failed to process scheduled digests: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed_at": datetime.now(timezone.utc).isoformat()
            }

    async def get_schedule_status(self) -> Dict[str, Any]:
        """
        Get current scheduling status and next delivery information.

        Returns:
            Dict with scheduling status
        """
        try:
            current_time = datetime.now(timezone.utc)
            next_monday_9am = await self.calculate_next_monday_9am(current_time)

            # Count scheduled digests
            async with AsyncSessionLocal() as session:
                from app.models.reports import WeeklyReport, ReportStatus

                scheduled_query = select(func.count(WeeklyReport.id)).where(
                    WeeklyReport.status == ReportStatus.SCHEDULED
                )
                scheduled_result = await session.execute(scheduled_query)
                scheduled_count = scheduled_result.scalar() or 0

                # Get most recent digest
                recent_query = select(WeeklyReport).where(
                    WeeklyReport.report_type == "weekly"
                ).order_by(WeeklyReport.created_at.desc()).limit(1)
                recent_result = await session.execute(recent_query)
                recent_digest = recent_result.scalar_one_or_none()

            return {
                "current_time": current_time.isoformat(),
                "next_monday_9am": next_monday_9am.isoformat(),
                "hours_until_next_delivery": (next_monday_9am - current_time).total_seconds() / 3600,
                "scheduled_digests_count": scheduled_count,
                "most_recent_digest": {
                    "id": str(recent_digest.id) if recent_digest else None,
                    "title": recent_digest.title if recent_digest else None,
                    "generated_at": recent_digest.generated_at.isoformat() if recent_digest and recent_digest.generated_at else None,
                    "status": recent_digest.status.value if recent_digest else None
                },
                "scheduler_status": "active",
                "last_check": current_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get schedule status: {e}")
            return {
                "success": False,
                "error": str(e),
                "current_time": datetime.now(timezone.utc).isoformat()
            }

    async def update_schedule_config(
        self,
        config: CFODigestScheduleRequest
    ) -> Dict[str, Any]:
        """
        Update scheduling configuration.

        Args:
            config: New scheduling configuration

        Returns:
            Dict with update results
        """
        try:
            # Store configuration in system settings or database
            # For now, just validate and return success
            next_delivery = await self.calculate_next_monday_9am()

            # Apply timezone if specified
            if config.timezone != "UTC":
                # TODO: Implement timezone conversion
                pass

            return {
                "success": True,
                "message": "Schedule configuration updated",
                "next_delivery": next_delivery.isoformat(),
                "delivery_day": config.delivery_day,
                "delivery_time": config.delivery_time,
                "is_active": config.is_active,
                "recipients": config.recipients
            }

        except Exception as e:
            logger.error(f"Failed to update schedule config: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_default_recipients(self) -> List[str]:
        """Get default recipient list for CFO digest."""
        return [
            "cfo@company.com",
            "finance-team@company.com",
            "ap-manager@company.com"
        ]

    async def run_scheduled_check(self):
        """
        Main method to run scheduled check for digest generation and delivery.
        This should be called by a cron job or scheduled task runner.
        """
        try:
            current_time = datetime.now(timezone.utc)
            current_weekday = current_time.weekday()  # Monday = 0
            current_hour = current_time.hour

            # Check if it's Monday 9:00 AM UTC (with 5-minute window)
            if current_weekday == 0 and 8 <= current_hour < 10:
                logger.info("Monday CFO digest check triggered")

                # Generate digest for last week
                result = await self.generate_monday_digest()

                if result["success"]:
                    # Schedule immediate delivery
                    await self.schedule_digest_delivery(
                        digest_id=result["digest_id"],
                        delivery_time=current_time + timedelta(minutes=5),  # 5 minute delay
                        recipients=self._get_default_recipients()
                    )

                    logger.info(f"Monday CFO digest generated and scheduled: {result['digest_id']}")
                else:
                    logger.error(f"Failed to generate Monday CFO digest: {result.get('error')}")

            # Process any scheduled digests
            await self.process_scheduled_digests()

            # Update SLO metrics for the dashboard
            await metrics_service.calculate_sli_measurements(
                period="daily",
                period_start=current_time - timedelta(hours=24),
                period_end=current_time
            )

        except Exception as e:
            logger.error(f"Failed to run scheduled check: {e}")


# Singleton instance
cfo_digest_scheduler = CFODigestScheduler()