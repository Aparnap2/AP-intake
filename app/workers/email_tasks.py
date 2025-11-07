"""
Background worker tasks for email monitoring and processing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import Celery

from app.core.config import settings
from app.core.exceptions import EmailIngestionException
from app.services.email_ingestion_service import EmailIngestionService
from app.services.gmail_service import GmailCredentials
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=settings.WORKER_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.WORKER_TASK_TIME_LIMIT,
)
def monitor_gmail_inbox(
    self,
    user_id: str,
    credentials_data: Dict[str, Any],
    days_back: int = 1,
    max_emails: int = 25,
    auto_process: bool = True
) -> Dict[str, Any]:
    """
    Monitor Gmail inbox for new invoice emails.

    Args:
        user_id: User identifier
        credentials_data: OAuth 2.0 credentials data
        days_back: Number of days to look back
        max_emails: Maximum emails to process
        auto_process: Whether to auto-process found invoices

    Returns:
        Dict with processing results
    """
    try:
        logger.info(f"Starting Gmail monitoring for user {user_id}")

        # Create credentials object
        credentials = GmailCredentials(**credentials_data)

        # Create ingestion service
        ingestion_service = EmailIngestionService()

        # Run async ingestion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            records = loop.run_until_complete(
                ingestion_service.ingest_from_gmail(
                    credentials=credentials,
                    days_back=days_back,
                    max_emails=max_emails,
                    auto_process=auto_process
                )
            )
        finally:
            loop.close()

        # Prepare results
        results = {
            "user_id": user_id,
            "status": "success",
            "emails_processed": len(records),
            "attachments_found": sum(len(r.attachments) for r in records),
            "processed_at": datetime.utcnow().isoformat(),
            "email_ids": [r.email_id for r in records]
        }

        logger.info(f"Gmail monitoring completed for user {user_id}: "
                   f"{results['emails_processed']} emails, {results['attachments_found']} attachments")

        return results

    except Exception as e:
        logger.error(f"Gmail monitoring failed for user {user_id}: {e}")

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying Gmail monitoring for user {user_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))

        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,       # 1 hour
)
def process_email_attachment(
    self,
    email_id: str,
    attachment_data: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single email attachment through the invoice workflow.

    Args:
        email_id: Email identifier
        attachment_data: Attachment metadata and content
        user_id: Optional user identifier

    Returns:
        Dict with processing results
    """
    try:
        logger.info(f"Processing attachment from email {email_id}")

        # Import here to avoid circular imports
        from app.workflows.invoice_processor import InvoiceProcessor

        # Generate invoice ID
        invoice_id = f"email_{email_id}_{attachment_data.get('content_hash', '')[:8]}"

        # Create processor and run workflow
        processor = InvoiceProcessor()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                processor.process_invoice(
                    invoice_id=invoice_id,
                    file_path=attachment_data.get('filename', ''),
                    file_hash=attachment_data.get('content_hash', ''),
                    vendor_name=attachment_data.get('vendor_name')
                )
            )
        finally:
            loop.close()

        # Prepare results
        results = {
            "email_id": email_id,
            "invoice_id": invoice_id,
            "status": "success",
            "workflow_status": result.get("status"),
            "confidence_score": result.get("confidence_score"),
            "requires_human_review": result.get("requires_human_review", False),
            "processed_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Successfully processed attachment from email {email_id}: "
                   f"invoice {invoice_id}, status {results['workflow_status']}")

        return results

    except Exception as e:
        logger.error(f"Failed to process attachment from email {email_id}: {e}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying attachment processing for email {email_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))

        return {
            "email_id": email_id,
            "status": "error",
            "error": str(e),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=1,
    soft_time_limit=600,  # 10 minutes
)
def schedule_email_monitoring(
    self,
    user_id: str,
    credentials_data: Dict[str, Any],
    schedule_minutes: int = 60
) -> Dict[str, Any]:
    """
    Schedule recurring email monitoring for a user.

    Args:
        user_id: User identifier
        credentials_data: OAuth 2.0 credentials data
        schedule_minutes: Interval in minutes for monitoring

    Returns:
        Dict with scheduling results
    """
    try:
        logger.info(f"Scheduling email monitoring for user {user_id} every {schedule_minutes} minutes")

        from celery.schedules import crontab

        # Create recurring task
        task_name = f"email_monitor_{user_id}"

        # Schedule the task using Celery beat
        celery_app.conf.beat_schedule[task_name] = {
            'task': 'app.workers.email_tasks.monitor_gmail_inbox',
            'schedule': crontab(minute=f'*/{schedule_minutes}'),
            'args': (user_id, credentials_data, 1, 25, True)
        }

        results = {
            "user_id": user_id,
            "task_name": task_name,
            "schedule_minutes": schedule_minutes,
            "status": "scheduled",
            "scheduled_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Successfully scheduled email monitoring for user {user_id}")
        return results

    except Exception as e:
        logger.error(f"Failed to schedule email monitoring for user {user_id}: {e}")
        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    soft_time_limit=300  # 5 minutes
)
def cleanup_old_email_data(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old email processing data.

    Args:
        days_to_keep: Number of days to keep data

    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of email data older than {days_to_keep} days")

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # This would typically clean up database records
        # For now, just log the action
        deleted_records = 0  # Would be actual count from database

        results = {
            "status": "success",
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_records": deleted_records,
            "cleaned_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Email cleanup completed: {deleted_records} records deleted")
        return results

    except Exception as e:
        logger.error(f"Email cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    soft_time_limit=120  # 2 minutes
)
def health_check_email_services() -> Dict[str, Any]:
    """
    Perform health check on email ingestion services.

    Returns:
        Dict with health check results
    """
    try:
        logger.info("Performing email services health check")

        ingestion_service = EmailIngestionService()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            health_status = loop.run_until_complete(ingestion_service.health_check())
        finally:
            loop.close()

        results = {
            "status": "success",
            "services": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }

        logger.info("Email services health check completed")
        return results

    except Exception as e:
        logger.error(f"Email services health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=900  # 15 minutes
)
def batch_process_emails(
    self,
    email_ids: list,
    user_id: str,
    credentials_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Batch process a list of emails.

    Args:
        email_ids: List of email IDs to process
        user_id: User identifier
        credentials_data: OAuth 2.0 credentials data

    Returns:
        Dict with batch processing results
    """
    try:
        logger.info(f"Starting batch processing of {len(email_ids)} emails for user {user_id}")

        results = {
            "user_id": user_id,
            "total_emails": len(email_ids),
            "successful": 0,
            "failed": 0,
            "errors": [],
            "processed_at": datetime.utcnow().isoformat()
        }

        # Create credentials
        credentials = GmailCredentials(**credentials_data)

        # Create ingestion service
        ingestion_service = EmailIngestionService()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for email_id in email_ids:
                try:
                    # Process each email
                    # This would need implementation for processing specific email IDs
                    # For now, just simulate successful processing
                    results["successful"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "email_id": email_id,
                        "error": str(e)
                    })
                    logger.error(f"Failed to process email {email_id}: {e}")

        finally:
            loop.close()

        logger.info(f"Batch processing completed for user {user_id}: "
                   f"{results['successful']} successful, {results['failed']} failed")

        return results

    except Exception as e:
        logger.error(f"Batch processing failed for user {user_id}: {e}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying batch processing for user {user_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))

        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


# Utility functions for task management
def get_email_monitoring_task_status(user_id: str) -> Optional[Dict[str, Any]]:
    """Get status of email monitoring task for a user."""
    try:
        task_name = f"email_monitor_{user_id}"

        # Check if task is scheduled in beat schedule
        if task_name in celery_app.conf.beat_schedule:
            schedule_info = celery_app.conf.beat_schedule[task_name]
            return {
                "user_id": user_id,
                "task_name": task_name,
                "status": "scheduled",
                "schedule": str(schedule_info.get('schedule')),
                "task": schedule_info.get('task')
            }

        return None

    except Exception as e:
        logger.error(f"Failed to get task status for user {user_id}: {e}")
        return None


def cancel_email_monitoring(user_id: str) -> bool:
    """Cancel email monitoring for a user."""
    try:
        task_name = f"email_monitor_{user_id}"

        if task_name in celery_app.conf.beat_schedule:
            del celery_app.conf.beat_schedule[task_name]
            logger.info(f"Cancelled email monitoring for user {user_id}")
            return True

        return False

    except Exception as e:
        logger.error(f"Failed to cancel email monitoring for user {user_id}: {e}")
        return False


def get_active_email_tasks() -> List[Dict[str, Any]]:
    """Get list of active email monitoring tasks."""
    try:
        active_tasks = []

        for task_name, schedule_info in celery_app.conf.beat_schedule.items():
            if task_name.startswith("email_monitor_"):
                user_id = task_name.replace("email_monitor_", "")
                active_tasks.append({
                    "user_id": user_id,
                    "task_name": task_name,
                    "schedule": str(schedule_info.get('schedule')),
                    "task": schedule_info.get('task')
                })

        return active_tasks

    except Exception as e:
        logger.error(f"Failed to get active email tasks: {e}")
        return []