"""
Comprehensive staging service for export workflow management with audit trails and approval chains.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, update, delete
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ValidationException, ConflictException
from app.models.staging import (
    StagedExport,
    StagingApprovalChain,
    StagingAuditTrail,
    StagingBatch,
    StagingStatus,
    ExportFormat,
)
from app.models.invoice import Invoice
from app.models.idempotency import IdempotencyOperationType

logger = logging.getLogger(__name__)


class StagingService:
    """Service for managing export staging workflows."""

    def __init__(self):
        """Initialize the staging service."""
        self.default_quality_threshold = getattr(settings, 'STAGING_QUALITY_THRESHOLD', 70)
        self.approval_timeout_hours = getattr(settings, 'STAGING_APPROVAL_TIMEOUT_HOURS', 72)

    async def stage_export(
        self,
        db: AsyncSession,
        invoice_id: str,
        export_data: Dict[str, Any],
        export_format: ExportFormat,
        destination_system: str,
        prepared_by: str,
        batch_id: Optional[str] = None,
        priority: int = 5,
        business_unit: Optional[str] = None,
        cost_center: Optional[str] = None,
        compliance_flags: Optional[List[str]] = None,
    ) -> StagedExport:
        """
        Stage an export for review and approval.

        Args:
            db: Database session
            invoice_id: Invoice ID to export
            export_data: Export data payload
            export_format: Export format
            destination_system: Target system
            prepared_by: User ID who prepared the export
            batch_id: Optional batch ID
            priority: Priority level (1-10)
            business_unit: Business unit
            cost_center: Cost center
            compliance_flags: Compliance flags

        Returns:
            Created staged export record
        """
        try:
            # Validate invoice exists
            invoice = await self._get_invoice(db, invoice_id)
            if not invoice:
                raise ValidationException(f"Invoice {invoice_id} not found")

            # Check for existing staged export
            existing_export = await self._get_existing_staged_export(db, invoice_id, destination_system)
            if existing_export and existing_export.can_approve():
                raise ConflictException(f"Export for invoice {invoice_id} to {destination_system} is already staged")

            # Get original invoice data for diff tracking
            original_data = await self._extract_invoice_data(invoice)

            # Validate export data quality
            quality_score = await self._calculate_quality_score(export_data, original_data)
            validation_errors = await self._validate_export_data(export_data, export_format)

            # Create staged export
            staged_export = StagedExport(
                invoice_id=uuid.UUID(invoice_id),
                staging_status=StagingStatus.PREPARED,
                export_format=export_format,
                destination_system=destination_system,
                prepared_data=export_data,
                original_data=original_data,
                prepared_by=uuid.UUID(prepared_by),
                quality_score=quality_score,
                batch_id=uuid.UUID(batch_id) if batch_id else None,
                priority=priority,
                business_unit=business_unit,
                cost_center=cost_center,
                compliance_flags=compliance_flags,
                validation_errors=validation_errors if validation_errors else None,
            )

            db.add(staged_export)
            await db.commit()
            await db.refresh(staged_export)

            # Create audit trail entry
            await self._create_audit_trail(
                db=db,
                staged_export_id=staged_export.id,
                action="created",
                action_by=uuid.UUID(prepared_by),
                previous_state=None,
                new_state={"status": "prepared", "quality_score": quality_score},
                data_snapshot=export_data,
                business_event="export_staged",
            )

            # Update batch progress if part of a batch
            if batch_id:
                await self._update_batch_progress(db, batch_id)

            logger.info(f"Staged export {staged_export.id} for invoice {invoice_id}")
            return staged_export

        except Exception as e:
            await db.rollback()
            logger.error(f"Error staging export: {e}")
            raise

    async def approve_staged_export(
        self,
        db: AsyncSession,
        staged_export_id: str,
        approved_by: str,
        approved_data: Optional[Dict[str, Any]] = None,
        change_reason: Optional[str] = None,
        approval_comments: Optional[str] = None,
    ) -> StagedExport:
        """
        Approve a staged export with optional data modifications.

        Args:
            db: Database session
            staged_export_id: Staged export ID
            approved_by: User ID approving the export
            approved_data: Modified export data (if any changes)
            change_reason: Business reason for changes
            approval_comments: Approval comments

        Returns:
            Updated staged export record
        """
        try:
            # Get staged export
            staged_export = await self._get_staged_export(db, staged_export_id)
            if not staged_export:
                raise ValidationException(f"Staged export {staged_export_id} not found")

            if not staged_export.can_approve():
                raise ValidationException(f"Staged export {staged_export_id} cannot be approved in status {staged_export.staging_status}")

            # Calculate field changes if data was modified
            field_changes = None
            if approved_data:
                field_changes = await self._calculate_field_changes(staged_export.prepared_data, approved_data)
                # Re-validate modified data
                validation_errors = await self._validate_export_data(approved_data, staged_export.export_format)
                if validation_errors:
                    raise ValidationException(f"Modified export data has validation errors: {validation_errors}")
            else:
                approved_data = staged_export.prepared_data

            # Store previous state for audit
            previous_state = {
                "status": staged_export.staging_status.value,
                "quality_score": staged_export.quality_score,
            }

            # Update staged export
            staged_export.mark_approved(
                approved_by_uuid=uuid.UUID(approved_by),
                approved_data=approved_data,
                change_reason=change_reason,
                field_changes=field_changes,
            )
            staged_export.approved_at = datetime.now(timezone.utc)
            staged_export.reviewer_comments = approval_comments

            await db.commit()

            # Create audit trail entry
            await self._create_audit_trail(
                db=db,
                staged_export_id=staged_export.id,
                action="approved",
                action_by=uuid.UUID(approved_by),
                previous_state=previous_state,
                new_state={"status": "approved", "changes": field_changes},
                data_snapshot=approved_data,
                business_event="export_approved",
                impact_assessment=await self._assess_change_impact(field_changes),
                action_reason=change_reason,
            )

            # Update batch progress if part of a batch
            if staged_export.batch_id:
                await self._update_batch_progress(db, str(staged_export.batch_id))

            logger.info(f"Approved staged export {staged_export_id} by {approved_by}")
            return staged_export

        except Exception as e:
            await db.rollback()
            logger.error(f"Error approving staged export: {e}")
            raise

    async def post_staged_export(
        self,
        db: AsyncSession,
        staged_export_id: str,
        posted_by: str,
        external_reference: Optional[str] = None,
        export_filename: Optional[str] = None,
        export_file_size: Optional[int] = None,
    ) -> StagedExport:
        """
        Post a staged export to the destination system.

        Args:
            db: Database session
            staged_export_id: Staged export ID
            posted_by: User ID posting the export
            external_reference: Reference in destination system
            export_filename: Generated export filename
            export_file_size: Export file size

        Returns:
            Updated staged export record
        """
        try:
            # Get staged export
            staged_export = await self._get_staged_export(db, staged_export_id)
            if not staged_export:
                raise ValidationException(f"Staged export {staged_export_id} not found")

            if not staged_export.can_post():
                raise ValidationException(f"Staged export {staged_export_id} cannot be posted in status {staged_export.staging_status}")

            # Store previous state for audit
            previous_state = {
                "status": staged_export.staging_status.value,
                "external_reference": staged_export.external_reference,
            }

            # Post to destination system (this would integrate with actual export systems)
            posted_data, export_job_id = await self._post_to_destination_system(
                staged_export.approved_data or staged_export.prepared_data,
                staged_export.destination_system,
                staged_export.export_format,
                external_reference
            )

            # Update staged export
            staged_export.mark_posted(
                posted_by_uuid=uuid.UUID(posted_by),
                posted_data=posted_data,
                external_reference=external_reference,
            )
            staged_export.export_job_id = export_job_id
            staged_export.export_filename = export_filename
            staged_export.export_file_size = export_file_size

            await db.commit()

            # Create audit trail entry
            await self._create_audit_trail(
                db=db,
                staged_export_id=staged_export.id,
                action="posted",
                action_by=uuid.UUID(posted_by),
                previous_state=previous_state,
                new_state={
                    "status": "posted",
                    "external_reference": external_reference,
                    "export_job_id": export_job_id,
                },
                data_snapshot=posted_data,
                business_event="export_posted",
                impact_assessment="high",
            )

            # Update batch progress if part of a batch
            if staged_export.batch_id:
                await self._update_batch_progress(db, str(staged_export.batch_id))

            logger.info(f"Posted staged export {staged_export_id} to {staged_export.destination_system}")
            return staged_export

        except Exception as e:
            await db.rollback()
            logger.error(f"Error posting staged export: {e}")
            raise

    async def reject_staged_export(
        self,
        db: AsyncSession,
        staged_export_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> StagedExport:
        """
        Reject a staged export.

        Args:
            db: Database session
            staged_export_id: Staged export ID
            rejected_by: User ID rejecting the export
            rejection_reason: Reason for rejection

        Returns:
            Updated staged export record
        """
        try:
            # Get staged export
            staged_export = await self._get_staged_export(db, staged_export_id)
            if not staged_export:
                raise ValidationException(f"Staged export {staged_export_id} not found")

            if not staged_export.can_approve():
                raise ValidationException(f"Staged export {staged_export_id} cannot be rejected in status {staged_export.staging_status}")

            # Store previous state for audit
            previous_state = {
                "status": staged_export.staging_status.value,
                "quality_score": staged_export.quality_score,
            }

            # Update staged export
            staged_export.mark_rejected(
                rejected_by_uuid=uuid.UUID(rejected_by),
                rejection_reason=rejection_reason,
            )

            await db.commit()

            # Create audit trail entry
            await self._create_audit_trail(
                db=db,
                staged_export_id=staged_export.id,
                action="rejected",
                action_by=uuid.UUID(rejected_by),
                previous_state=previous_state,
                new_state={"status": "rejected"},
                data_snapshot=staged_export.prepared_data,
                business_event="export_rejected",
                action_reason=rejection_reason,
            )

            # Update batch progress if part of a batch
            if staged_export.batch_id:
                await self._update_batch_progress(db, str(staged_export.batch_id))

            logger.info(f"Rejected staged export {staged_export_id} by {rejected_by}: {rejection_reason}")
            return staged_export

        except Exception as e:
            await db.rollback()
            logger.error(f"Error rejecting staged export: {e}")
            raise

    async def get_staged_export_diff(
        self,
        db: AsyncSession,
        staged_export_id: str,
    ) -> Dict[str, Any]:
        """
        Get the diff between original and staged export data.

        Args:
            db: Database session
            staged_export_id: Staged export ID

        Returns:
            Dictionary with diff information
        """
        try:
            staged_export = await self._get_staged_export(db, staged_export_id)
            if not staged_export:
                raise ValidationException(f"Staged export {staged_export_id} not found")

            # Calculate comprehensive diff
            original_to_prepared = await self._calculate_comprehensive_diff(
                staged_export.original_data or {},
                staged_export.prepared_data
            )

            prepared_to_approved = None
            if staged_export.approved_data and staged_export.approved_data != staged_export.prepared_data:
                prepared_to_approved = await self._calculate_comprehensive_diff(
                    staged_export.prepared_data,
                    staged_export.approved_data
                )

            return {
                "staged_export_id": staged_export_id,
                "invoice_id": str(staged_export.invoice_id),
                "destination_system": staged_export.destination_system,
                "export_format": staged_export.export_format.value,
                "original_to_prepared": original_to_prepared,
                "prepared_to_approved": prepared_to_approved,
                "field_changes": staged_export.field_changes,
                "change_reason": staged_export.change_reason,
                "quality_score": staged_export.quality_score,
                "validation_errors": staged_export.validation_errors,
                "audit_trail_count": len(staged_export.audit_trail) if hasattr(staged_export, 'audit_trail') else 0,
            }

        except Exception as e:
            logger.error(f"Error getting staged export diff: {e}")
            raise

    async def rollback_staged_export(
        self,
        db: AsyncSession,
        staged_export_id: str,
        rolled_back_by: str,
        rollback_reason: str,
    ) -> StagedExport:
        """
        Roll back a posted staged export.

        Args:
            db: Database session
            staged_export_id: Staged export ID
            rolled_back_by: User ID performing the rollback
            rollback_reason: Reason for rollback

        Returns:
            Updated staged export record
        """
        try:
            # Get staged export
            staged_export = await self._get_staged_export(db, staged_export_id)
            if not staged_export:
                raise ValidationException(f"Staged export {staged_export_id} not found")

            if not staged_export.can_rollback():
                raise ValidationException(f"Staged export {staged_export_id} cannot be rolled back in status {staged_export.staging_status}")

            # Perform actual rollback in destination system
            rollback_success = await self._rollback_from_destination_system(
                staged_export.destination_system,
                staged_export.external_reference,
                rollback_reason
            )

            if not rollback_success:
                raise ValidationException(f"Failed to rollback export from destination system {staged_export.destination_system}")

            # Store previous state for audit
            previous_state = {
                "status": staged_export.staging_status.value,
                "external_reference": staged_export.external_reference,
            }

            # Update staged export
            staged_export.staging_status = StagingStatus.ROLLED_BACK
            staged_export.external_reference = None  # Clear external reference
            staged_export.audit_notes = f"Rolled back: {rollback_reason}"

            await db.commit()

            # Create audit trail entry
            await self._create_audit_trail(
                db=db,
                staged_export_id=staged_export.id,
                action="rolled_back",
                action_by=uuid.UUID(rolled_back_by),
                previous_state=previous_state,
                new_state={"status": "rolled_back", "external_reference": None},
                data_snapshot=staged_export.posted_data,
                business_event="export_rolled_back",
                impact_assessment="high",
                action_reason=rollback_reason,
            )

            logger.info(f"Rolled back staged export {staged_export_id} by {rolled_back_by}")
            return staged_export

        except Exception as e:
            await db.rollback()
            logger.error(f"Error rolling back staged export: {e}")
            raise

    async def list_staged_exports(
        self,
        db: AsyncSession,
        status: Optional[StagingStatus] = None,
        destination_system: Optional[str] = None,
        batch_id: Optional[str] = None,
        business_unit: Optional[str] = None,
        prepared_by: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StagedExport], int]:
        """
        List staged exports with filtering.

        Args:
            db: Database session
            status: Optional status filter
            destination_system: Optional destination system filter
            batch_id: Optional batch ID filter
            business_unit: Optional business unit filter
            prepared_by: Optional prepared by filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (staged_exports, total_count)
        """
        try:
            # Build base query
            query = select(StagedExport).options(selectinload(StagedExport.audit_trail))
            conditions = []

            # Apply filters
            if status:
                conditions.append(StagedExport.staging_status == status)
            if destination_system:
                conditions.append(StagedExport.destination_system == destination_system)
            if batch_id:
                conditions.append(StagedExport.batch_id == uuid.UUID(batch_id))
            if business_unit:
                conditions.append(StagedExport.business_unit == business_unit)
            if prepared_by:
                conditions.append(StagedExport.prepared_by == uuid.UUID(prepared_by))

            # Apply conditions
            if conditions:
                query = query.where(and_(*conditions))

            # Get total count
            count_query = select(func.count(StagedExport.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))

            count_result = await db.execute(count_query)
            total = count_result.scalar()

            # Apply pagination and ordering
            query = query.order_by(desc(StagedExport.created_at)).offset(skip).limit(limit)
            result = await db.execute(query)
            staged_exports = result.scalars().all()

            return staged_exports, total

        except Exception as e:
            logger.error(f"Error listing staged exports: {e}")
            raise

    # Private helper methods

    async def _get_invoice(self, db: AsyncSession, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID."""
        try:
            stmt = select(Invoice).where(Invoice.id == uuid.UUID(invoice_id))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting invoice: {e}")
            return None

    async def _get_staged_export(self, db: AsyncSession, staged_export_id: str) -> Optional[StagedExport]:
        """Get staged export by ID."""
        try:
            stmt = select(StagedExport).where(StagedExport.id == uuid.UUID(staged_export_id))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting staged export: {e}")
            return None

    async def _get_existing_staged_export(
        self,
        db: AsyncSession,
        invoice_id: str,
        destination_system: str,
    ) -> Optional[StagedExport]:
        """Get existing staged export for invoice and destination."""
        try:
            stmt = select(StagedExport).where(
                and_(
                    StagedExport.invoice_id == uuid.UUID(invoice_id),
                    StagedExport.destination_system == destination_system,
                    StagedExport.staging_status.in_([StagingStatus.PREPARED, StagingStatus.UNDER_REVIEW])
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting existing staged export: {e}")
            return None

    async def _extract_invoice_data(self, invoice: Invoice) -> Dict[str, Any]:
        """Extract relevant invoice data for comparison."""
        # This would extract invoice data for comparison
        # For now, return a placeholder
        return {
            "invoice_id": str(invoice.id),
            "status": invoice.status.value,
            "created_at": invoice.created_at.isoformat(),
        }

    async def _calculate_quality_score(
        self,
        export_data: Dict[str, Any],
        original_data: Dict[str, Any],
    ) -> int:
        """Calculate quality score for export data."""
        # Simple quality score calculation
        # In production, this would be more sophisticated
        score = 100

        # Check for required fields
        required_fields = ["vendor_name", "invoice_number", "total_amount"]
        for field in required_fields:
            if field not in export_data or not export_data[field]:
                score -= 10

        # Check data consistency
        if original_data:
            consistency_score = await self._calculate_data_consistency(export_data, original_data)
            score = min(score, consistency_score)

        return max(0, score)

    async def _calculate_data_consistency(
        self,
        export_data: Dict[str, Any],
        original_data: Dict[str, Any],
    ) -> int:
        """Calculate data consistency score."""
        # Simple consistency calculation
        # In production, this would be more sophisticated
        return 85  # Placeholder

    async def _validate_export_data(
        self,
        export_data: Dict[str, Any],
        export_format: ExportFormat,
    ) -> Optional[List[str]]:
        """Validate export data against format requirements."""
        errors = []

        # Basic validation
        if not export_data:
            errors.append("Export data is empty")
            return errors

        # Format-specific validation
        if export_format == ExportFormat.CSV:
            # Validate CSV-specific requirements
            if "headers" not in export_data:
                errors.append("CSV headers are required")
        elif export_format == ExportFormat.JSON:
            # Validate JSON-specific requirements
            try:
                json.dumps(export_data)
            except (TypeError, ValueError):
                errors.append("Invalid JSON format")

        return errors if errors else None

    async def _calculate_field_changes(
        self,
        original_data: Dict[str, Any],
        modified_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate field-level changes between data versions."""
        changes = {}

        for key in set(original_data.keys()) | set(modified_data.keys()):
            original_value = original_data.get(key)
            modified_value = modified_data.get(key)

            if original_value != modified_value:
                changes[key] = {
                    "original": original_value,
                    "modified": modified_value,
                    "change_type": "added" if key not in original_data else "removed" if key not in modified_data else "modified"
                }

        return changes

    async def _calculate_comprehensive_diff(
        self,
        data1: Dict[str, Any],
        data2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate comprehensive diff between two data sets."""
        return {
            "added_fields": {k: v for k, v in data2.items() if k not in data1},
            "removed_fields": {k: v for k, v in data1.items() if k not in data2},
            "modified_fields": await self._calculate_field_changes(data1, data2),
            "summary": {
                "total_fields_in_data1": len(data1),
                "total_fields_in_data2": len(data2),
                "fields_added": len([k for k in data2 if k not in data1]),
                "fields_removed": len([k for k in data1 if k not in data2]),
                "fields_modified": len([k for k in data1 if k in data2 and data1[k] != data2[k]]),
            }
        }

    async def _assess_change_impact(self, field_changes: Optional[Dict[str, Any]]) -> str:
        """Assess the impact of changes."""
        if not field_changes:
            return "low"

        # Simple impact assessment based on number of changes
        change_count = len(field_changes)
        if change_count <= 2:
            return "low"
        elif change_count <= 5:
            return "medium"
        else:
            return "high"

    async def _post_to_destination_system(
        self,
        data: Dict[str, Any],
        destination_system: str,
        export_format: ExportFormat,
        external_reference: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Post data to destination system."""
        # This would integrate with actual destination systems
        # For now, return mock data
        export_job_id = f"job_{uuid.uuid4().hex[:8]}"
        posted_data = data.copy()  # In reality, this might be transformed by the destination system
        return posted_data, export_job_id

    async def _rollback_from_destination_system(
        self,
        destination_system: str,
        external_reference: str,
        rollback_reason: str,
    ) -> bool:
        """Roll back data from destination system."""
        # This would integrate with actual destination systems
        # For now, return True
        return True

    async def _create_audit_trail(
        self,
        db: AsyncSession,
        staged_export_id: uuid.UUID,
        action: str,
        action_by: uuid.UUID,
        previous_state: Optional[Dict[str, Any]],
        new_state: Optional[Dict[str, Any]],
        data_snapshot: Optional[Dict[str, Any]],
        business_event: Optional[str] = None,
        impact_assessment: Optional[str] = None,
        action_reason: Optional[str] = None,
    ) -> None:
        """Create audit trail entry."""
        try:
            audit_entry = StagingAuditTrail(
                staged_export_id=staged_export_id,
                action=action,
                action_by=action_by,
                action_reason=action_reason,
                previous_state=previous_state,
                new_state=new_state,
                data_snapshot=data_snapshot,
                business_event=business_event,
                impact_assessment=impact_assessment,
            )
            db.add(audit_entry)
            await db.commit()
        except Exception as e:
            logger.error(f"Error creating audit trail: {e}")

    async def _update_batch_progress(self, db: AsyncSession, batch_id: str) -> None:
        """Update batch progress metrics."""
        try:
            # Get batch and update progress
            stmt = select(StagingBatch).where(StagingBatch.id == uuid.UUID(batch_id))
            result = await db.execute(stmt)
            batch = result.scalar_one_or_none()

            if batch:
                batch.update_progress()
                await db.commit()
        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")