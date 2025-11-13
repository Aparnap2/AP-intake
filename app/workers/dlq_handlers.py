"""
Celery error handlers for capturing task failures in DLQ.

This module provides comprehensive error handling for Celery tasks including:
- Automatic DLQ entry creation on task failure
- Task metadata extraction and preservation
- Error categorization and analysis
- Integration with DLQ service
- Background monitoring and alerting
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery.signals import task_failure, task_prerun, task_postrun, task_revoked, task_unknown
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.dlq import DLQCategory, DLQPriority
from app.services.dlq_service import DLQService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DLQErrorHandler:
    """
    Error handler for capturing Celery task failures in DLQ.

    This class handles the automatic creation of DLQ entries when
    Celery tasks fail, preserving all relevant context and metadata.
    """

    def __init__(self):
        self.service_cache = {}

    def get_dlq_service(self) -> DLQService:
        """Get DLQ service instance with connection pooling."""
        db = SessionLocal()
        return DLQService(db)

    @staticmethod
    def extract_task_metadata(request) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from Celery task request.

        Args:
            request: Celery task request

        Returns:
            Dictionary with task metadata
        """
        metadata = {
            "task_id": request.id,
            "task_name": request.task,
            "args": request.args,
            "kwargs": request.kwargs,
            "retries": request.retries,
            "eta": request.eta,
            "expires": request.expires,
            "utc": request.utc,
            "headers": request.headers,
            "reply_to": request.reply_to,
            "correlation_id": request.correlation_id,
            "origin": request.origin,
            "content_type": request.content_type,
            "content_encoding": request.content_encoding,
            "root_id": request.root_id,
            "parent_id": request.parent_id,
            "group": request.group,
            "group_index": request.group_index,
            "chain": request.chain,
            "chord": request.chord,
            "callback": request.callback,
            "errback": request.errback,
            "shadow": request.shadow,
            "timelimit": request.timelimit,
            "ignore_result": request.ignore_result,
            "store_errors_even_if_ignored": request.store_errors_even_if_ignored,
            "hostname": request.hostname,
            "delivery_info": request.delivery_info,
        }

        # Extract worker and queue information
        if hasattr(request, 'hostname'):
            metadata["worker_name"] = request.hostname

        if hasattr(request, 'delivery_info') and request.delivery_info:
            metadata["queue_name"] = request.delivery_info.get('exchange', '')

        # Extract timing information
        metadata["received_at"] = datetime.now(timezone.utc).isoformat()

        return metadata

    @staticmethod
    def extract_invoice_context(args: tuple, kwargs: dict) -> Optional[str]:
        """
        Extract invoice ID from task arguments.

        Args:
            args: Task positional arguments
            kwargs: Task keyword arguments

        Returns:
            Invoice ID as string or None
        """
        # Check kwargs first
        if 'invoice_id' in kwargs:
            return str(kwargs['invoice_id'])
        if 'invoice' in kwargs and hasattr(kwargs['invoice'], 'id'):
            return str(kwargs['invoice'].id)

        # Check args
        for arg in args:
            if hasattr(arg, 'id'):
                # Could be an invoice object
                return str(arg.id)
            elif isinstance(arg, str) and len(arg) == 36:
                # Could be a UUID string
                return arg

        return None

    @staticmethod
    def determine_task_priority(task_name: str, error_category: DLQCategory) -> DLQPriority:
        """
        Determine task priority based on task name and error category.

        Args:
            task_name: Name of the failed task
            error_category: Category of the error

        Returns:
            DLQ priority
        """
        # Critical tasks
        critical_tasks = ['process_invoice', 'validate_invoice', 'export_invoice']
        if any(task in task_name.lower() for task in critical_tasks):
            if error_category in [DLQCategory.SYSTEM_ERROR, DLQCategory.DATABASE_ERROR]:
                return DLQPriority.CRITICAL
            return DLQPriority.HIGH

        # High priority tasks
        high_priority_tasks = ['send_email', 'generate_report', 'ingestion']
        if any(task in task_name.lower() for task in high_priority_tasks):
            return DLQPriority.HIGH

        # Low priority tasks
        low_priority_tasks = ['cleanup', 'maintenance', 'health_check']
        if any(task in task_name.lower() for task in low_priority_tasks):
            return DLQPriority.LOW

        return DLQPriority.NORMAL

    def create_dlq_entry_on_failure(self, sender, task_id: str, error: Exception, traceback_str: str, request, **kwargs):
        """
        Create DLQ entry when a task fails.

        This is the main error handler that gets called when any Celery task fails.

        Args:
            sender: Task sender
            task_id: Task ID
            error: Exception that caused the failure
            traceback_str: Full traceback string
            request: Task request
            **kwargs: Additional keyword arguments
        """
        try:
            # Skip certain task types that shouldn't go to DLQ
            if self._should_skip_dlq(sender.name):
                logger.debug(f"Skipping DLQ creation for task {sender.name} (task_id: {task_id})")
                return

            # Extract task metadata
            metadata = self.extract_task_metadata(request)

            # Extract invoice context
            invoice_id = self.extract_invoice_context(request.args, request.kwargs)

            # Get DLQ service
            dlq_service = self.get_dlq_service()

            # Create DLQ entry
            dlq_service.create_dlq_entry(
                task_id=task_id,
                task_name=sender.name,
                error_type=type(error).__name__,
                error_message=str(error),
                error_stack_trace=traceback_str,
                task_args=list(request.args) if request.args else None,
                task_kwargs=dict(request.kwargs) if request.kwargs else None,
                original_task_data=metadata,
                idempotency_key=request.headers.get('idempotency-key') if request.headers else None,
                invoice_id=invoice_id,
                worker_name=request.hostname,
                queue_name=metadata.get('queue_name'),
                execution_time=getattr(request, 'execution_time', None),
                max_retries=getattr(sender, 'max_retries', 3),
                priority=self.determine_task_priority(sender.name, dlq_service._categorize_error(type(error).__name__, str(error)))
            )

            logger.info(f"Created DLQ entry for failed task {sender.name} (task_id: {task_id})")

            # Clean up service
            dlq_service.db.close()

        except Exception as e:
            logger.error(f"Failed to create DLQ entry for task {task_id}: {e}")
            # Don't raise here to avoid interfering with the original task failure

    def _should_skip_dlq(self, task_name: str) -> bool:
        """
        Determine if a task should be skipped for DLQ creation.

        Args:
            task_name: Name of the task

        Returns:
            True if task should be skipped
        """
        # Skip internal and monitoring tasks
        skip_tasks = [
            'celery.',
            'app.workers.maintenance_tasks.',
            'app.workers.health_check',
            'dlq.',
            'redrive.'
        ]

        return any(task_name.startswith(skip_task) for skip_task in skip_tasks)


# Global error handler instance
error_handler = DLQErrorHandler()


# Celery signal handlers
@task_failure.connect
def task_failure_handler(sender, task_id, exception, traceback, einfo, **kwargs):
    """
    Handle task failure signals.

    This signal is sent when a task fails.
    """
    try:
        logger.error(f"Task {sender.name} failed (ID: {task_id}): {exception}")

        # Create DLQ entry
        error_handler.create_dlq_entry_on_failure(
            sender=sender,
            task_id=task_id,
            error=exception,
            traceback_str=traceback,
            request=einfo.request if hasattr(einfo, 'request') else None,
            **kwargs
        )

    except Exception as e:
        logger.error(f"Error in task_failure_handler: {e}")


@task_prerun.connect
def task_prerun_handler(sender, task_id, task, args, kwargs, **kwds):
    """
    Handle task pre-run signals.

    This signal is sent just before a task is executed.
    """
    try:
        logger.debug(f"Task {sender.name} starting (ID: {task_id})")

        # Store start time for execution time calculation
        if hasattr(task, 'request'):
            task.request.start_time = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Error in task_prerun_handler: {e}")


@task_postrun.connect
def task_postrun_handler(sender, task_id, task, args, kwargs, retval, state, **kwds):
    """
    Handle task post-run signals.

    This signal is sent after a task has been executed.
    """
    try:
        logger.debug(f"Task {sender.name} completed (ID: {task_id}, state: {state})")

        # Calculate execution time
        if hasattr(task, 'request') and hasattr(task.request, 'start_time'):
            execution_time = (datetime.now(timezone.utc) - task.request.start_time).total_seconds()
            logger.debug(f"Task {sender.name} execution time: {execution_time:.2f}s")

    except Exception as e:
        logger.error(f"Error in task_postrun_handler: {e}")


@task_revoked.connect
def task_revoked_handler(sender, request, terminated, signum, expired, **kwargs):
    """
    Handle task revoked signals.

    This signal is sent when a task is revoked.
    """
    try:
        logger.warning(f"Task {sender.name} revoked (ID: {request.id})")

        # Create DLQ entry for revoked tasks
        if not terminated:  # Only create DLQ for non-termination revokes
            error_message = f"Task revoked (terminated={terminated}, signum={signum}, expired={expired})"

            error_handler.create_dlq_entry_on_failure(
                sender=sender,
                task_id=request.id,
                error=Exception(error_message),
                traceback_str="",  # No traceback for revokes
                request=request,
                **kwargs
            )

    except Exception as e:
        logger.error(f"Error in task_revoked_handler: {e}")


@task_unknown.connect
def task_unknown_handler(sender, task_id, exc, **kwargs):
    """
    Handle task unknown signals.

    This signal is sent when a worker receives a message for an unregistered task.
    """
    try:
        logger.error(f"Unknown task {task_id}: {exc}")

        # This typically indicates a configuration issue
        # Could create an alert or notification here

    except Exception as e:
        logger.error(f"Error in task_unknown_handler: {e}")


# Background task for DLQ monitoring
@celery_app.task(name="app.workers.dlq_handlers.monitor_dlq_health")
def monitor_dlq_health():
    """
    Background task to monitor DLQ health and generate alerts.

    This task runs periodically to check DLQ health metrics and
    generate alerts if needed.
    """
    try:
        from app.services.alert_service import AlertService
        from app.core.config import settings

        db = SessionLocal()
        dlq_service = DLQService(db)

        # Get DLQ stats
        stats = dlq_service.get_dlq_stats(days=1)

        # Check for critical conditions
        alerts = []

        # High number of pending entries
        if stats.pending_entries > 100:
            alerts.append({
                "severity": "warning",
                "message": f"High number of pending DLQ entries: {stats.pending_entries}",
                "metric": "dlq_pending_count",
                "value": stats.pending_entries,
                "threshold": 100
            })

        # High number of critical entries
        if stats.critical_entries > 10:
            alerts.append({
                "severity": "critical",
                "message": f"High number of critical DLQ entries: {stats.critical_entries}",
                "metric": "dlq_critical_count",
                "value": stats.critical_entries,
                "threshold": 10
            })

        # High failure rate
        total_processed = stats.completed_entries + stats.failed_permanently
        if total_processed > 0:
            failure_rate = stats.failed_permanently / total_processed
            if failure_rate > 0.5:  # 50% failure rate
                alerts.append({
                    "severity": "warning",
                    "message": f"High DLQ failure rate: {failure_rate:.1%}",
                    "metric": "dlq_failure_rate",
                    "value": failure_rate,
                    "threshold": 0.5
                })

        # Old entries
        if stats.oldest_entry_age_hours > 24:
            alerts.append({
                "severity": "warning",
                "message": f"Old DLQ entries detected: {stats.oldest_entry_age_hours:.1f} hours",
                "metric": "dlq_oldest_entry_age",
                "value": stats.oldest_entry_age_hours,
                "threshold": 24
            })

        # Send alerts if any
        if alerts and hasattr(settings, 'ALERT_SERVICE_ENABLED') and settings.ALERT_SERVICE_ENABLED:
            alert_service = AlertService(db)
            for alert in alerts:
                alert_service.create_alert(
                    alert_type="dlq_health",
                    severity=alert["severity"],
                    message=alert["message"],
                    metadata=alert
                )

        db.close()

        logger.info(f"DLQ health monitoring completed: {len(alerts)} alerts generated")

    except Exception as e:
        logger.error(f"Error in DLQ health monitoring: {e}")


# Background task for automatic redrive
@celery_app.task(name="app.workers.dlq_handlers.auto_redrive")
def auto_redrive_tasks():
    """
    Background task for automatic redrive of DLQ entries.

    This task runs periodically to automatically redrive entries
    that are ready for retry.
    """
    try:
        db = SessionLocal()
        from app.services.redrive_service import RedriveService

        redrive_service = RedriveService(db)
        stats = redrive_service.auto_redrive_pending_entries(batch_size=100)

        db.close()

        logger.info(f"Auto-redrive completed: {stats}")

    except Exception as e:
        logger.error(f"Error in auto-redrive: {e}")


# Register the background tasks in Celery beat schedule
def register_dlq_monitoring_tasks():
    """Register DLQ monitoring tasks in Celery beat schedule."""

    # Add monitoring tasks to existing schedule
    celery_app.conf.beat_schedule.update({
        "dlq-health-monitor": {
            "task": "app.workers.dlq_handlers.monitor_dlq_health",
            "schedule": 300.0,  # Every 5 minutes
        },
        "auto-redrive-tasks": {
            "task": "app.workers.dlq_handlers.auto_redrive",
            "schedule": 60.0,   # Every minute
        },
    })


# Register monitoring tasks on module import
register_dlq_monitoring_tasks()