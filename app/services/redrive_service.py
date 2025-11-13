"""
Redrive Service for retrying failed Celery tasks from DLQ.

This service provides comprehensive redrive functionality including:
- Exponential backoff retry logic
- Circuit breaker pattern for preventing cascading failures
- Task reconstruction and execution
- Intelligent retry decision making
- Batch redrive operations
"""

import logging
import math
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dlq import (
    DeadLetterQueue, DLQStatus, DLQCategory, DLQPriority,
    RedriveRequest, RedriveResponse
)
from app.services.dlq_service import DLQService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, stop trying
    HALF_OPEN = "half_open"  # Testing if failures are resolved


class CircuitBreaker:
    """
    Circuit breaker implementation for preventing cascading failures.

    This implements the circuit breaker pattern to stop retrying tasks
    when a certain failure threshold is reached.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def __call__(self, func):
        """Decorator for circuit breaker functionality."""
        def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class RedriveService:
    """
    Service for redriving failed tasks from DLQ.

    This service handles the retry logic for failed tasks, including
    exponential backoff, circuit breaker pattern, and intelligent
    retry decision making.
    """

    def __init__(self, db: Session):
        self.db = db
        self.dlq_service = DLQService(db)

        # Initialize circuit breakers for different task types
        self.circuit_breakers = {
            "processing": CircuitBreaker(failure_threshold=3, recovery_timeout=300),
            "validation": CircuitBreaker(failure_threshold=5, recovery_timeout=180),
            "export": CircuitBreaker(failure_threshold=3, recovery_timeout=600),
            "email": CircuitBreaker(failure_threshold=5, recovery_timeout=120),
            "default": CircuitBreaker(failure_threshold=5, recovery_timeout=300),
        }

    def redrive_single_entry(
        self,
        dlq_id: UUID,
        force: bool = False,
        modify_args: Optional[Dict[str, Any]] = None,
        priority_override: Optional[DLQPriority] = None
    ) -> Tuple[bool, str]:
        """
        Redrive a single DLQ entry.

        Args:
            dlq_id: DLQ entry ID
            force: Force redrive even if max retries exceeded
            modify_args: Optional argument modifications
            priority_override: Optional priority override

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get DLQ entry
            dlq_entry = self.dlq_service.get_dlq_entry(dlq_id)
            if not dlq_entry:
                return False, f"DLQ entry {dlq_id} not found"

            # Check if redrive is allowed
            if not force and dlq_entry.retry_count >= dlq_entry.max_retries:
                return False, f"Max retries exceeded ({dlq_entry.max_retries})"

            if dlq_entry.dlq_status not in [DLQStatus.PENDING, DLQStatus.FAILED_PERMANENTLY]:
                return False, f"DLQ entry status is {dlq_entry.dlq_status}, cannot redrive"

            # Get circuit breaker for this task type
            task_type = self._get_task_type(dlq_entry.task_name)
            circuit_breaker = self.circuit_breakers.get(task_type, self.circuit_breakers["default"])

            # Check circuit breaker state
            if circuit_breaker.state == CircuitBreakerState.OPEN:
                return False, f"Circuit breaker is OPEN for task type: {task_type}"

            # Update status to processing
            dlq_entry.dlq_status = DLQStatus.PROCESSING
            dlq_entry.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            # Prepare task arguments
            task_args = dlq_entry.task_args or []
            task_kwargs = dlq_entry.task_kwargs or {}

            # Apply modifications if provided
            if modify_args:
                task_kwargs.update(modify_args)

            # Apply priority override if provided
            if priority_override:
                dlq_entry.priority = priority_override

            try:
                # Redrive the task
                result = self._execute_redrive(dlq_entry, task_args, task_kwargs)

                # Record successful redrive
                dlq_entry.add_redrive_attempt(success=True)
                self.db.commit()

                logger.info(f"Successfully redrove DLQ entry {dlq_id} (task: {dlq_entry.task_name})")
                return True, f"Successfully redrove task {dlq_entry.task_name}"

            except Exception as e:
                # Record failed redrive
                error_message = str(e)
                dlq_entry.add_redrive_attempt(success=False, error_message=error_message)

                # Update circuit breaker
                circuit_breaker._on_failure()

                self.db.commit()

                logger.error(f"Failed to redrive DLQ entry {dlq_id}: {error_message}")
                return False, f"Redrive failed: {error_message}"

        except Exception as e:
            logger.error(f"Error redriving DLQ entry {dlq_id}: {e}")
            return False, f"Redrive error: {str(e)}"

    def redrive_bulk_entries(self, request: RedriveRequest) -> RedriveResponse:
        """
        Redrive multiple DLQ entries in bulk.

        Args:
            request: Redrive request with entry IDs and options

        Returns:
            Redrive response with results
        """
        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0

        logger.info(f"Starting bulk redrive of {len(request.dlq_ids)} entries")

        for dlq_id in request.dlq_ids:
            try:
                success, message = self.redrive_single_entry(
                    dlq_id=dlq_id,
                    force=request.force,
                    modify_args=request.modify_args,
                    priority_override=request.priority
                )

                result = {
                    "dlq_id": str(dlq_id),
                    "success": success,
                    "message": message
                }
                results.append(result)

                if success:
                    success_count += 1
                else:
                    if "not found" in message or "status is" in message:
                        skipped_count += 1
                    else:
                        failed_count += 1

            except Exception as e:
                result = {
                    "dlq_id": str(dlq_id),
                    "success": False,
                    "message": f"Unexpected error: {str(e)}"
                }
                results.append(result)
                failed_count += 1

        logger.info(f"Bulk redrive completed: {success_count} success, {failed_count} failed, {skipped_count} skipped")

        return RedriveResponse(
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            results=results
        )

    def auto_redrive_pending_entries(self, batch_size: int = 50) -> Dict[str, int]:
        """
        Automatically redrive entries that are ready for retry.

        Args:
            batch_size: Maximum number of entries to process

        Returns:
            Dictionary with redrive statistics
        """
        try:
            # Get entries ready for retry
            entries = self.dlq_service.get_entries_ready_for_retry(batch_size)

            stats = {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0
            }

            logger.info(f"Auto-redriving {len(entries)} DLQ entries")

            for entry in entries:
                try:
                    success, message = self.redrive_single_entry(entry.id)
                    stats["processed"] += 1

                    if success:
                        stats["successful"] += 1
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(f"Error auto-redriving entry {entry.id}: {e}")
                    stats["failed"] += 1

            logger.info(f"Auto-redrive completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error in auto-redrive: {e}")
            return {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}

    def should_redrive_entry(self, dlq_entry: DeadLetterQueue) -> bool:
        """
        Determine if a DLQ entry should be redriven.

        Args:
            dlq_entry: DLQ entry to evaluate

        Returns:
            True if entry should be redriven
        """
        # Check retry count
        if dlq_entry.retry_count >= dlq_entry.max_retries:
            return False

        # Check if enough time has passed for exponential backoff
        if dlq_entry.last_retry_at:
            # Calculate delay based on retry count (exponential backoff)
            delay = min(3600, math.pow(2, dlq_entry.retry_count) * 60)  # Max 1 hour
            next_allowed_time = dlq_entry.last_retry_at + timedelta(seconds=delay)

            if datetime.now(timezone.utc) < next_allowed_time:
                return False

        # Check error category for redrive eligibility
        non_redrivable_categories = [
            DLQCategory.BUSINESS_RULE_ERROR,
            DLQCategory.VALIDATION_ERROR
        ]

        if dlq_entry.error_category in non_redrivable_categories:
            # Don't auto-redrive validation and business rule errors
            # These typically require manual intervention
            return False

        # Check circuit breaker state
        task_type = self._get_task_type(dlq_entry.task_name)
        circuit_breaker = self.circuit_breakers.get(task_type, self.circuit_breakers["default"])

        if circuit_breaker.state == CircuitBreakerState.OPEN:
            return False

        return True

    def get_redrive_recommendations(self, dlq_entry: DeadLetterQueue) -> Dict[str, Any]:
        """
        Get recommendations for redriving a DLQ entry.

        Args:
            dlq_entry: DLQ entry to analyze

        Returns:
            Dictionary with redrive recommendations
        """
        recommendations = {
            "should_redrive": False,
            "reason": "",
            "suggested_action": "",
            "estimated_success_rate": 0.0,
            "recommended_modifications": {}
        }

        # Analyze error category
        if dlq_entry.error_category == DLQCategory.NETWORK_ERROR:
            recommendations["should_redrive"] = True
            recommendations["reason"] = "Network errors are often transient"
            recommendations["suggested_action"] = "Redrive with exponential backoff"
            recommendations["estimated_success_rate"] = 0.8

        elif dlq_entry.error_category == DLQCategory.TIMEOUT_ERROR:
            recommendations["should_redrive"] = True
            recommendations["reason"] = "Timeouts can be resolved with retry"
            recommendations["suggested_action"] = "Redrive with increased timeout"
            recommendations["estimated_success_rate"] = 0.7
            recommendations["recommended_modifications"] = {"timeout": 300}

        elif dlq_entry.error_category == DLQCategory.DATABASE_ERROR:
            if "connection" in dlq_entry.error_message.lower():
                recommendations["should_redrive"] = True
                recommendations["reason"] = "Database connection issues are often transient"
                recommendations["suggested_action"] = "Redrive after connection recovery"
                recommendations["estimated_success_rate"] = 0.6
            else:
                recommendations["should_redrive"] = False
                recommendations["reason"] = "Database constraint errors require manual intervention"
                recommendations["suggested_action"] = "Review data and manual correction"

        elif dlq_entry.error_category == DLQCategory.PROCESSING_ERROR:
            if dlq_entry.retry_count < 2:
                recommendations["should_redrive"] = True
                recommendations["reason"] = "Processing errors may resolve with retry"
                recommendations["suggested_action"] = "Redrive with caution"
                recommendations["estimated_success_rate"] = 0.5
            else:
                recommendations["should_redrive"] = False
                recommendations["reason"] = "Multiple processing failures indicate persistent issues"
                recommendations["suggested_action"] = "Manual review required"

        elif dlq_entry.error_category in [DLQCategory.VALIDATION_ERROR, DLQCategory.BUSINESS_RULE_ERROR]:
            recommendations["should_redrive"] = False
            recommendations["reason"] = "Validation and business rule errors require data correction"
            recommendations["suggested_action"] = "Manual data correction before redrive"
            recommendations["estimated_success_rate"] = 0.1

        else:
            recommendations["should_redrive"] = True
            recommendations["reason"] = "Unknown errors worth attempting retry"
            recommendations["suggested_action"] = "Redrive with monitoring"
            recommendations["estimated_success_rate"] = 0.4

        return recommendations

    def _execute_redrive(
        self,
        dlq_entry: DeadLetterQueue,
        task_args: List[Any],
        task_kwargs: Dict[str, Any]
    ) -> Any:
        """
        Execute the redrive of a task.

        Args:
            dlq_entry: DLQ entry
            task_args: Task arguments
            task_kwargs: Task keyword arguments

        Returns:
            Task result
        """
        try:
            # Get the task from Celery
            task = celery_app.tasks.get(dlq_entry.task_name)
            if not task:
                raise ValueError(f"Task {dlq_entry.task_name} not found")

            # Execute the task with apply_async for better control
            result = task.apply_async(
                args=task_args,
                kwargs=task_kwargs,
                queue=dlq_entry.queue_name or "default",
                priority=self._get_celery_priority(dlq_entry.priority),
                expires=3600,  # 1 hour expiry
                retry=False,  # We handle retry logic ourselves
            )

            return result

        except Exception as e:
            logger.error(f"Failed to execute redrive for task {dlq_entry.task_name}: {e}")
            raise

    def _get_task_type(self, task_name: str) -> str:
        """
        Get task type for circuit breaker selection.

        Args:
            task_name: Name of the task

        Returns:
            Task type string
        """
        task_name_lower = task_name.lower()

        if "process" in task_name_lower:
            return "processing"
        elif "valid" in task_name_lower:
            return "validation"
        elif "export" in task_name_lower:
            return "export"
        elif "email" in task_name_lower:
            return "email"
        else:
            return "default"

    def _get_celery_priority(self, dlq_priority: DLQPriority) -> int:
        """
        Convert DLQ priority to Celery priority.

        Args:
            dlq_priority: DLQ priority

        Returns:
            Celery priority (0-9, higher is more important)
        """
        priority_map = {
            DLQPriority.CRITICAL: 9,
            DLQPriority.HIGH: 7,
            DLQPriority.NORMAL: 5,
            DLQPriority.LOW: 2,
        }
        return priority_map.get(dlq_priority, 5)

    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the status of all circuit breakers.

        Returns:
            Dictionary with circuit breaker statuses
        """
        status = {}

        for task_type, breaker in self.circuit_breakers.items():
            status[task_type] = {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "failure_threshold": breaker.failure_threshold,
                "recovery_timeout": breaker.recovery_timeout,
                "last_failure_time": breaker.last_failure_time,
                "is_open": breaker.state == CircuitBreakerState.OPEN,
                "should_attempt_reset": breaker._should_attempt_reset() if breaker.state == CircuitBreakerState.OPEN else False,
            }

        return status