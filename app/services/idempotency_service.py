"""
Comprehensive idempotency service for preventing duplicate operations and ensuring data integrity.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, update, delete
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.exceptions import ValidationException, ConflictException
from app.models.idempotency import (
    IdempotencyRecord,
    IdempotencyConflict,
    IdempotencyMetric,
    IdempotencyOperationType,
    IdempotencyStatus,
)
from app.models.invoice import Invoice
from app.models.ingestion import IngestionJob

logger = logging.getLogger(__name__)


class IdempotencyService:
    """Service for managing idempotency across all operations."""

    def __init__(self):
        """Initialize the idempotency service."""
        self.default_ttl_seconds = getattr(settings, 'IDEMPOTENCY_TTL_SECONDS', 24 * 3600)  # 24 hours
        self.max_execution_attempts = getattr(settings, 'IDEMPOTENCY_MAX_EXECUTIONS', 3)
        self.cleanup_interval_hours = getattr(settings, 'IDEMPOTENCY_CLEANUP_HOURS', 1)

    def generate_idempotency_key(
        self,
        operation_type: IdempotencyOperationType,
        invoice_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        file_hash: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a deterministic idempotency key for an operation.

        Args:
            operation_type: Type of operation
            invoice_id: Optional invoice ID
            vendor_id: Optional vendor ID
            file_hash: Optional file hash for upload operations
            user_id: Optional user ID
            additional_context: Additional context for key generation

        Returns:
            Unique idempotency key
        """
        # Build key components based on operation type
        key_components = [operation_type.value]

        if operation_type == IdempotencyOperationType.INVOICE_UPLOAD:
            # For uploads, use vendor_id + file_hash
            if vendor_id and file_hash:
                key_components.extend([vendor_id, file_hash])
            else:
                # Fallback to provided context
                key_components.append(str(additional_context or {}))
        elif operation_type == IdempotencyOperationType.INVOICE_PROCESS:
            # For processing, use invoice_id
            if invoice_id:
                key_components.append(invoice_id)
        elif operation_type in [IdempotencyOperationType.EXPORT_STAGE, IdempotencyOperationType.EXPORT_POST]:
            # For exports, use invoice_id + operation type
            if invoice_id:
                key_components.extend([invoice_id, operation_type.value])
        elif operation_type == IdempotencyOperationType.BATCH_OPERATION:
            # For batch operations, use all context
            context_str = json.dumps(additional_context or {}, sort_keys=True)
            key_components.append(context_str)

        # Add user_id if provided for user-specific idempotency
        if user_id:
            key_components.append(f"user:{user_id}")

        # Generate hash of components
        key_string = "|".join(key_components)
        return hashlib.sha256(key_string.encode()).hexdigest()

    async def check_and_create_idempotency_record(
        self,
        db: AsyncSession,
        idempotency_key: str,
        operation_type: IdempotencyOperationType,
        operation_data: Dict[str, Any],
        invoice_id: Optional[str] = None,
        ingestion_job_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        max_executions: Optional[int] = None,
        client_ip: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[IdempotencyRecord, bool]:
        """
        Check for existing idempotency record and create if not exists.

        Args:
            db: Database session
            idempotency_key: Unique idempotency key
            operation_type: Type of operation
            operation_data: Operation request data
            invoice_id: Optional invoice ID
            ingestion_job_id: Optional ingestion job ID
            user_id: Optional user ID
            ttl_seconds: Time to live in seconds
            max_executions: Maximum execution attempts
            client_ip: Client IP address
            session_id: Session ID

        Returns:
            Tuple of (idempotency_record, is_new_record)
        """
        try:
            # Set defaults
            ttl_seconds = ttl_seconds or self.default_ttl_seconds
            max_executions = max_executions or self.max_execution_attempts
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

            # First, try to find existing record
            existing_record = await self._get_idempotency_record(db, idempotency_key)

            if existing_record:
                # Check if existing record can be used
                if existing_record.operation_status == IdempotencyStatus.COMPLETED:
                    logger.info(f"Returning completed operation for key: {idempotency_key}")
                    return existing_record, False

                elif existing_record.operation_status == IdempotencyStatus.IN_PROGRESS:
                    # Another instance is processing this operation
                    if existing_record.is_expired():
                        # Mark as expired and allow new execution
                        await self._mark_record_expired(db, existing_record)
                        logger.warning(f"Expired in-progress operation for key: {idempotency_key}")
                    else:
                        # Still in progress, create conflict record
                        await self._create_conflict_record(
                            db, existing_record, operation_data, "concurrent_execution"
                        )
                        raise ConflictException(
                            f"Operation with idempotency key '{idempotency_key}' is already in progress"
                        )

                elif existing_record.operation_status == IdempotencyStatus.FAILED:
                    # Check if we can retry
                    if existing_record.execution_count >= existing_record.max_executions:
                        raise ConflictException(
                            f"Operation with idempotency key '{idempotency_key}' has exceeded maximum execution attempts"
                        )
                    # We can retry this failed operation
                    await self._mark_record_retry(db, existing_record)
                    logger.info(f"Retrying failed operation for key: {idempotency_key}")

                else:
                    # Other status, create conflict
                    await self._create_conflict_record(
                        db, existing_record, operation_data, "status_conflict"
                    )
                    raise ConflictException(
                        f"Operation with idempotency key '{idempotency_key}' has conflicting status: {existing_record.operation_status}"
                    )

            # Create new idempotency record
            new_record = IdempotencyRecord(
                idempotency_key=idempotency_key,
                operation_type=operation_type,
                operation_status=IdempotencyStatus.PENDING,
                operation_data=operation_data,
                invoice_id=uuid.UUID(invoice_id) if invoice_id else None,
                ingestion_job_id=uuid.UUID(ingestion_job_id) if ingestion_job_id else None,
                expires_at=expires_at,
                ttl_seconds=ttl_seconds,
                max_executions=max_executions,
                user_id=user_id,
                client_ip=client_ip,
                session_id=session_id,
            )

            db.add(new_record)
            await db.commit()
            await db.refresh(new_record)

            logger.info(f"Created new idempotency record for key: {idempotency_key}")
            return new_record, True

        except Exception as e:
            await db.rollback()
            logger.error(f"Error in check_and_create_idempotency_record: {e}")
            raise

    async def mark_operation_started(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> bool:
        """
        Mark an operation as started/in progress.

        Args:
            db: Database session
            idempotency_key: Idempotency key

        Returns:
            True if successfully marked as started
        """
        try:
            stmt = (
                update(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == idempotency_key)
                .where(IdempotencyRecord.can_execute())
                .values(
                    operation_status=IdempotencyStatus.IN_PROGRESS,
                    updated_at=datetime.now(timezone.utc)
                )
                .returning(IdempotencyRecord)
            )

            result = await db.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                record.mark_attempt()
                await db.commit()
                logger.info(f"Marked operation as started for key: {idempotency_key}")
                return True
            else:
                logger.warning(f"Could not mark operation as started for key: {idempotency_key}")
                return False

        except Exception as e:
            await db.rollback()
            logger.error(f"Error marking operation as started: {e}")
            return False

    async def mark_operation_completed(
        self,
        db: AsyncSession,
        idempotency_key: str,
        result_data: Dict[str, Any],
    ) -> bool:
        """
        Mark an operation as completed with result data.

        Args:
            db: Database session
            idempotency_key: Idempotency key
            result_data: Operation result data

        Returns:
            True if successfully marked as completed
        """
        try:
            stmt = (
                update(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == idempotency_key)
                .where(IdempotencyRecord.operation_status == IdempotencyStatus.IN_PROGRESS)
                .values(
                    operation_status=IdempotencyStatus.COMPLETED,
                    result_data=result_data,
                    completed_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                .returning(IdempotencyRecord)
            )

            result = await db.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                await db.commit()
                await self._update_metrics(db, record.operation_type, "completed")
                logger.info(f"Marked operation as completed for key: {idempotency_key}")
                return True
            else:
                logger.warning(f"Could not mark operation as completed for key: {idempotency_key}")
                return False

        except Exception as e:
            await db.rollback()
            logger.error(f"Error marking operation as completed: {e}")
            return False

    async def mark_operation_failed(
        self,
        db: AsyncSession,
        idempotency_key: str,
        error_data: Dict[str, Any],
        error_code: Optional[str] = None,
    ) -> bool:
        """
        Mark an operation as failed with error details.

        Args:
            db: Database session
            idempotency_key: Idempotency key
            error_data: Error details
            error_code: Optional error code

        Returns:
            True if successfully marked as failed
        """
        try:
            stmt = (
                update(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == idempotency_key)
                .where(IdempotencyRecord.operation_status == IdempotencyStatus.IN_PROGRESS)
                .values(
                    operation_status=IdempotencyStatus.FAILED,
                    error_data=error_data,
                    updated_at=datetime.now(timezone.utc)
                )
                .returning(IdempotencyRecord)
            )

            result = await db.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                await db.commit()
                await self._update_metrics(db, record.operation_type, "failed")
                logger.info(f"Marked operation as failed for key: {idempotency_key}")
                return True
            else:
                logger.warning(f"Could not mark operation as failed for key: {idempotency_key}")
                return False

        except Exception as e:
            await db.rollback()
            logger.error(f"Error marking operation as failed: {e}")
            return False

    async def get_operation_result(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the result of a completed operation.

        Args:
            db: Database session
            idempotency_key: Idempotency key

        Returns:
            Result data if operation is completed, None otherwise
        """
        try:
            record = await self._get_idempotency_record(db, idempotency_key)

            if record and record.operation_status == IdempotencyStatus.COMPLETED:
                return record.result_data

            return None

        except Exception as e:
            logger.error(f"Error getting operation result: {e}")
            return None

    async def cleanup_expired_records(
        self,
        db: AsyncSession,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """
        Clean up expired idempotency records.

        Args:
            db: Database session
            dry_run: If True, only count records without deleting

        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Count expired records
            count_stmt = select(func.count(IdempotencyRecord.id)).where(
                and_(
                    IdempotencyRecord.expires_at < datetime.now(timezone.utc),
                    IdempotencyRecord.operation_status.in_([
                        IdempotencyStatus.COMPLETED,
                        IdempotencyStatus.FAILED,
                        IdempotencyStatus.CANCELLED
                    ])
                )
            )
            count_result = await db.execute(count_stmt)
            expired_count = count_result.scalar()

            cleanup_stats = {
                "expired_records_found": expired_count,
                "records_deleted": 0,
                "conflicts_deleted": 0,
            }

            if not dry_run and expired_count > 0:
                # Delete expired records
                delete_stmt = delete(IdempotencyRecord).where(
                    and_(
                        IdempotencyRecord.expires_at < datetime.now(timezone.utc),
                        IdempotencyRecord.operation_status.in_([
                            IdempotencyStatus.COMPLETED,
                            IdempotencyStatus.FAILED,
                            IdempotencyStatus.CANCELLED
                        ])
                    )
                )
                delete_result = await db.execute(delete_stmt)
                cleanup_stats["records_deleted"] = delete_result.rowcount

                # Delete related conflicts
                conflict_delete_stmt = delete(IdempotencyConflict).where(
                    IdempotencyConflict.idempotency_record_id.in_(
                        select(IdempotencyRecord.id).where(
                            and_(
                                IdempotencyRecord.expires_at < datetime.now(timezone.utc),
                                IdempotencyRecord.operation_status.in_([
                                    IdempotencyStatus.COMPLETED,
                                    IdempotencyStatus.FAILED,
                                    IdempotencyStatus.CANCELLED
                                ])
                            )
                        )
                    )
                )
                conflict_result = await db.execute(conflict_delete_stmt)
                cleanup_stats["conflicts_deleted"] = conflict_result.rowcount

                await db.commit()

            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            await db.rollback()
            logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}

    async def get_idempotency_metrics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        operation_type: Optional[IdempotencyOperationType] = None,
    ) -> Dict[str, Any]:
        """
        Get idempotency metrics for the specified date range.

        Args:
            db: Database session
            start_date: Start date for metrics
            end_date: End date for metrics
            operation_type: Optional operation type filter

        Returns:
            Dictionary with idempotency metrics
        """
        try:
            # Build base query
            conditions = [
                IdempotencyRecord.created_at >= start_date,
                IdempotencyRecord.created_at <= end_date,
            ]

            if operation_type:
                conditions.append(IdempotencyRecord.operation_type == operation_type)

            # Get total operations
            total_query = select(func.count(IdempotencyRecord.id)).where(and_(*conditions))
            total_result = await db.execute(total_query)
            total_operations = total_result.scalar()

            # Get status breakdown
            status_query = (
                select(IdempotencyRecord.operation_status, func.count(IdempotencyRecord.id))
                .where(and_(*conditions))
                .group_by(IdempotencyRecord.operation_status)
            )
            status_result = await db.execute(status_query)
            status_breakdown = {status.value: count for status, count in status_result}

            # Get conflict count
            conflict_query = (
                select(func.count(IdempotencyConflict.id))
                .join(IdempotencyRecord, IdempotencyConflict.idempotency_record_id == IdempotencyRecord.id)
                .where(and_(*conditions))
            )
            conflict_result = await db.execute(conflict_query)
            conflicts_detected = conflict_result.scalar()

            # Get average execution time (would need to track this)
            avg_execution_time = 0  # Placeholder

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "total_operations": total_operations,
                "status_breakdown": status_breakdown,
                "conflicts_detected": conflicts_detected,
                "avg_execution_time_ms": avg_execution_time,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting idempotency metrics: {e}")
            raise

    # Private helper methods

    async def _get_idempotency_record(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> Optional[IdempotencyRecord]:
        """Get idempotency record by key."""
        try:
            stmt = select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == idempotency_key
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting idempotency record: {e}")
            return None

    async def _create_conflict_record(
        self,
        db: AsyncSession,
        existing_record: IdempotencyRecord,
        conflicting_data: Dict[str, Any],
        conflict_reason: str,
    ) -> None:
        """Create a conflict record."""
        try:
            conflict = IdempotencyConflict(
                idempotency_record_id=existing_record.id,
                conflict_key=existing_record.idempotency_key,
                conflict_type="data_mismatch",
                conflict_reason=conflict_reason,
                conflicting_operation_data=conflicting_data,
            )
            db.add(conflict)
            await db.commit()
        except Exception as e:
            logger.error(f"Error creating conflict record: {e}")

    async def _mark_record_expired(
        self,
        db: AsyncSession,
        record: IdempotencyRecord,
    ) -> None:
        """Mark a record as expired."""
        try:
            record.operation_status = IdempotencyStatus.FAILED
            record.error_data = {"error": "operation_expired", "message": "Operation expired before completion"}
            await db.commit()
        except Exception as e:
            logger.error(f"Error marking record as expired: {e}")

    async def _mark_record_retry(
        self,
        db: AsyncSession,
        record: IdempotencyRecord,
    ) -> None:
        """Mark a record for retry."""
        try:
            record.mark_attempt()
            record.operation_status = IdempotencyStatus.PENDING
            await db.commit()
        except Exception as e:
            logger.error(f"Error marking record for retry: {e}")

    async def _update_metrics(
        self,
        db: AsyncSession,
        operation_type: IdempotencyOperationType,
        status: str,
    ) -> None:
        """Update operation metrics."""
        try:
            # This would update daily metrics
            # For now, just log the metric
            logger.info(f"Metric update: {operation_type.value} -> {status}")
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")