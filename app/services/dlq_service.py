"""
Dead Letter Queue Service for managing failed Celery tasks.

This service provides comprehensive DLQ management including:
- Creating and storing DLQ entries
- Querying and filtering DLQ entries
- DLQ statistics and monitoring
- Error categorization and analysis
- Automatic aging and cleanup
"""

import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.dlq import (
    DeadLetterQueue, DLQStatus, DLQCategory, DLQPriority,
    DLQEntry, DLQStats, DLQEntryCreate, DLQEntryUpdate
)
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


class DLQService:
    """
    Service for managing Dead Letter Queue entries.

    This service handles all DLQ operations including creation, querying,
    updating, and statistics generation.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_dlq_entry(
        self,
        task_id: str,
        task_name: str,
        error_type: str,
        error_message: str,
        error_stack_trace: Optional[str] = None,
        task_args: Optional[List[Any]] = None,
        task_kwargs: Optional[Dict[str, Any]] = None,
        original_task_data: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        invoice_id: Optional[UUID] = None,
        worker_name: Optional[str] = None,
        queue_name: Optional[str] = None,
        execution_time: Optional[int] = None,
        max_retries: int = 3,
        priority: DLQPriority = DLQPriority.NORMAL
    ) -> DeadLetterQueue:
        """
        Create a new DLQ entry for a failed task.

        Args:
            task_id: Unique task identifier
            task_name: Name of the failed task
            error_type: Type of error that occurred
            error_message: Detailed error message
            error_stack_trace: Full error stack trace
            task_args: Task arguments
            task_kwargs: Task keyword arguments
            original_task_data: Original task metadata
            idempotency_key: Task idempotency key
            invoice_id: Related invoice ID
            worker_name: Worker that processed the task
            queue_name: Queue the task was in
            execution_time: Task execution time in seconds
            max_retries: Maximum number of retries
            priority: Entry priority

        Returns:
            Created DLQ entry
        """
        try:
            # Categorize the error
            error_category = self._categorize_error(error_type, error_message)

            # Determine priority based on error type and context
            if priority == DLQPriority.NORMAL:
                priority = self._determine_priority(error_category, task_name, invoice_id)

            dlq_entry = DeadLetterQueue(
                task_id=task_id,
                task_name=task_name,
                task_args=task_args,
                task_kwargs=task_kwargs,
                original_task_data=original_task_data,
                error_type=error_type,
                error_message=error_message,
                error_stack_trace=error_stack_trace,
                error_category=error_category,
                max_retries=max_retries,
                priority=priority,
                idempotency_key=idempotency_key,
                invoice_id=invoice_id,
                worker_name=worker_name,
                queue_name=queue_name,
                execution_time=execution_time,
            )

            self.db.add(dlq_entry)
            self.db.commit()
            self.db.refresh(dlq_entry)

            logger.info(f"Created DLQ entry for task {task_id} ({task_name})")
            return dlq_entry

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create DLQ entry for task {task_id}: {e}")
            raise

    def get_dlq_entry(self, dlq_id: UUID) -> Optional[DeadLetterQueue]:
        """
        Get a DLQ entry by ID.

        Args:
            dlq_id: DLQ entry ID

        Returns:
            DLQ entry or None if not found
        """
        try:
            return (
                self.db.query(DeadLetterQueue)
                .options(joinedload(DeadLetterQueue.invoice))
                .filter(DeadLetterQueue.id == dlq_id)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Failed to get DLQ entry {dlq_id}: {e}")
            raise

    def get_dlq_entry_by_task_id(self, task_id: str) -> Optional[DeadLetterQueue]:
        """
        Get a DLQ entry by task ID.

        Args:
            task_id: Task identifier

        Returns:
            DLQ entry or None if not found
        """
        try:
            return (
                self.db.query(DeadLetterQueue)
                .options(joinedload(DeadLetterQueue.invoice))
                .filter(DeadLetterQueue.task_id == task_id)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Failed to get DLQ entry for task {task_id}: {e}")
            raise

    def list_dlq_entries(
        self,
        status: Optional[DLQStatus] = None,
        category: Optional[DLQCategory] = None,
        priority: Optional[DLQPriority] = None,
        task_name: Optional[str] = None,
        invoice_id: Optional[UUID] = None,
        queue_name: Optional[str] = None,
        worker_name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[DeadLetterQueue], int]:
        """
        List DLQ entries with filtering and pagination.

        Args:
            status: Filter by DLQ status
            category: Filter by error category
            priority: Filter by priority
            task_name: Filter by task name
            invoice_id: Filter by invoice ID
            queue_name: Filter by queue name
            worker_name: Filter by worker name
            idempotency_key: Filter by idempotency key
            created_after: Filter entries created after this date
            created_before: Filter entries created before this date
            page: Page number
            page_size: Number of entries per page
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            Tuple of (DLQ entries, total count)
        """
        try:
            query = (
                self.db.query(DeadLetterQueue)
                .options(joinedload(DeadLetterQueue.invoice))
            )

            # Apply filters
            if status:
                query = query.filter(DeadLetterQueue.dlq_status == status)
            if category:
                query = query.filter(DeadLetterQueue.error_category == category)
            if priority:
                query = query.filter(DeadLetterQueue.priority == priority)
            if task_name:
                query = query.filter(DeadLetterQueue.task_name.ilike(f"%{task_name}%"))
            if invoice_id:
                query = query.filter(DeadLetterQueue.invoice_id == invoice_id)
            if queue_name:
                query = query.filter(DeadLetterQueue.queue_name == queue_name)
            if worker_name:
                query = query.filter(DeadLetterQueue.worker_name == worker_name)
            if idempotency_key:
                query = query.filter(DeadLetterQueue.idempotency_key == idempotency_key)
            if created_after:
                query = query.filter(DeadLetterQueue.created_at >= created_after)
            if created_before:
                query = query.filter(DeadLetterQueue.created_at <= created_before)

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = getattr(DeadLetterQueue, sort_by, DeadLetterQueue.created_at)
            if sort_order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())

            # Apply pagination
            offset = (page - 1) * page_size
            entries = query.offset(offset).limit(page_size).all()

            return entries, total

        except SQLAlchemyError as e:
            logger.error(f"Failed to list DLQ entries: {e}")
            raise

    def update_dlq_entry(self, dlq_id: UUID, update_data: DLQEntryUpdate) -> Optional[DeadLetterQueue]:
        """
        Update a DLQ entry.

        Args:
            dlq_id: DLQ entry ID
            update_data: Update data

        Returns:
            Updated DLQ entry or None if not found
        """
        try:
            dlq_entry = self.get_dlq_entry(dlq_id)
            if not dlq_entry:
                return None

            # Update fields
            update_dict = update_data.dict(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(dlq_entry, field, value)

            dlq_entry.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(dlq_entry)

            logger.info(f"Updated DLQ entry {dlq_id}")
            return dlq_entry

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update DLQ entry {dlq_id}: {e}")
            raise

    def delete_dlq_entry(self, dlq_id: UUID) -> bool:
        """
        Delete a DLQ entry.

        Args:
            dlq_id: DLQ entry ID

        Returns:
            True if deleted, False if not found
        """
        try:
            dlq_entry = self.get_dlq_entry(dlq_id)
            if not dlq_entry:
                return False

            self.db.delete(dlq_entry)
            self.db.commit()

            logger.info(f"Deleted DLQ entry {dlq_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to delete DLQ entry {dlq_id}: {e}")
            raise

    def get_dlq_stats(self, days: int = 30) -> DLQStats:
        """
        Get DLQ statistics.

        Args:
            days: Number of days to consider for stats

        Returns:
            DLQ statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Base query
            query = self.db.query(DeadLetterQueue).filter(
                DeadLetterQueue.created_at >= cutoff_date
            )

            # Total entries
            total_entries = query.count()

            # By status
            pending_entries = query.filter(DeadLetterQueue.dlq_status == DLQStatus.PENDING).count()
            processing_entries = query.filter(DeadLetterQueue.dlq_status == DLQStatus.PROCESSING).count()
            completed_entries = query.filter(DeadLetterQueue.dlq_status == DLQStatus.COMPLETED).count()
            failed_permanently = query.filter(DeadLetterQueue.dlq_status == DLQStatus.FAILED_PERMANENTLY).count()
            archived_entries = query.filter(DeadLetterQueue.dlq_status == DLQStatus.ARCHIVED).count()

            # By category
            processing_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.PROCESSING_ERROR).count()
            validation_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.VALIDATION_ERROR).count()
            network_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.NETWORK_ERROR).count()
            database_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.DATABASE_ERROR).count()
            timeout_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.TIMEOUT_ERROR).count()
            business_rule_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.BUSINESS_RULE_ERROR).count()
            system_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.SYSTEM_ERROR).count()
            unknown_errors = query.filter(DeadLetterQueue.error_category == DLQCategory.UNKNOWN_ERROR).count()

            # By priority
            critical_entries = query.filter(DeadLetterQueue.priority == DLQPriority.CRITICAL).count()
            high_entries = query.filter(DeadLetterQueue.priority == DLQPriority.HIGH).count()
            normal_entries = query.filter(DeadLetterQueue.priority == DLQPriority.NORMAL).count()
            low_entries = query.filter(DeadLetterQueue.priority == DLQPriority.LOW).count()

            # Aging calculations
            now = datetime.now(timezone.utc)
            entries_with_age = query.all()

            if entries_with_age:
                ages = [(now - entry.created_at).total_seconds() / 3600 for entry in entries_with_age]
                avg_age_hours = sum(ages) / len(ages)
                oldest_entry_age_hours = max(ages)
            else:
                avg_age_hours = 0.0
                oldest_entry_age_hours = 0.0

            return DLQStats(
                total_entries=total_entries,
                pending_entries=pending_entries,
                processing_entries=processing_entries,
                completed_entries=completed_entries,
                failed_permanently=failed_permanently,
                archived_entries=archived_entries,
                processing_errors=processing_errors,
                validation_errors=validation_errors,
                network_errors=network_errors,
                database_errors=database_errors,
                timeout_errors=timeout_errors,
                business_rule_errors=business_rule_errors,
                system_errors=system_errors,
                unknown_errors=unknown_errors,
                critical_entries=critical_entries,
                high_entries=high_entries,
                normal_entries=normal_entries,
                low_entries=low_entries,
                avg_age_hours=avg_age_hours,
                oldest_entry_age_hours=oldest_entry_age_hours,
            )

        except SQLAlchemyError as e:
            logger.error(f"Failed to get DLQ stats: {e}")
            raise

    def cleanup_old_entries(self, days: int = 90, status: Optional[DLQStatus] = None) -> int:
        """
        Clean up old DLQ entries.

        Args:
            days: Age in days to delete entries
            status: Optional status filter

        Returns:
            Number of entries deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            query = self.db.query(DeadLetterQueue).filter(
                DeadLetterQueue.created_at < cutoff_date
            )

            if status:
                query = query.filter(DeadLetterQueue.dlq_status == status)

            count = query.count()
            query.delete()
            self.db.commit()

            logger.info(f"Cleaned up {count} old DLQ entries")
            return count

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to cleanup old DLQ entries: {e}")
            raise

    def get_entries_ready_for_retry(self, batch_size: int = 100) -> List[DeadLetterQueue]:
        """
        Get DLQ entries that are ready for retry.

        Args:
            batch_size: Maximum number of entries to return

        Returns:
            List of DLQ entries ready for retry
        """
        try:
            now = datetime.now(timezone.utc)

            entries = (
                self.db.query(DeadLetterQueue)
                .filter(
                    DeadLetterQueue.dlq_status == DLQStatus.PENDING,
                    DeadLetterQueue.retry_count < DeadLetterQueue.max_retries,
                    sa.or_(
                        DeadLetterQueue.next_retry_at.is_(None),
                        DeadLetterQueue.next_retry_at <= now
                    )
                )
                .order_by(DeadLetterQueue.priority.desc(), DeadLetterQueue.created_at.asc())
                .limit(batch_size)
                .all()
            )

            return entries

        except SQLAlchemyError as e:
            logger.error(f"Failed to get entries ready for retry: {e}")
            raise

    def _categorize_error(self, error_type: str, error_message: str) -> DLQCategory:
        """
        Categorize an error based on type and message.

        Args:
            error_type: Error type
            error_message: Error message

        Returns:
            Error category
        """
        error_type_lower = error_type.lower()
        error_message_lower = error_message.lower()

        # Network errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['connection', 'network', 'timeout', 'unreachable']):
            if 'timeout' in error_type_lower or 'timeout' in error_message_lower:
                return DLQCategory.TIMEOUT_ERROR
            return DLQCategory.NETWORK_ERROR

        # Database errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['database', 'sql', 'integrity', 'constraint']):
            return DLQCategory.DATABASE_ERROR

        # Validation errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['validation', 'invalid', 'malformed', 'schema']):
            return DLQCategory.VALIDATION_ERROR

        # Business rule errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['business', 'rule', 'policy', 'permission']):
            return DLQCategory.BUSINESS_RULE_ERROR

        # System errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['memory', 'disk', 'system', 'resource']):
            return DLQCategory.SYSTEM_ERROR

        # Processing errors
        if any(term in error_type_lower or term in error_message_lower
               for term in ['processing', 'parse', 'extract', 'transform']):
            return DLQCategory.PROCESSING_ERROR

        return DLQCategory.UNKNOWN_ERROR

    def _determine_priority(
        self,
        error_category: DLQCategory,
        task_name: str,
        invoice_id: Optional[UUID]
    ) -> DLQPriority:
        """
        Determine the priority of a DLQ entry.

        Args:
            error_category: Error category
            task_name: Task name
            invoice_id: Related invoice ID

        Returns:
            DLQ priority
        """
        # Critical errors
        if error_category in [DLQCategory.SYSTEM_ERROR, DLQCategory.DATABASE_ERROR]:
            return DLQPriority.CRITICAL

        # High priority for invoice-related tasks
        if invoice_id and 'invoice' in task_name.lower():
            return DLQPriority.HIGH

        # High priority for network and timeout errors (likely transient)
        if error_category in [DLQCategory.NETWORK_ERROR, DLQCategory.TIMEOUT_ERROR]:
            return DLQPriority.HIGH

        # Normal priority for processing and validation errors
        if error_category in [DLQCategory.PROCESSING_ERROR, DLQCategory.VALIDATION_ERROR]:
            return DLQPriority.NORMAL

        # Low priority for business rule errors (require manual intervention)
        if error_category == DLQCategory.BUSINESS_RULE_ERROR:
            return DLQPriority.LOW

        return DLQPriority.NORMAL