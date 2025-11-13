"""
Staging API endpoints for export workflow management with comprehensive audit trails.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.api.schemas import (
    StagedExportResponse,
    StagedExportListResponse,
    StagedExportDiffResponse,
    StagingApprovalRequest,
    StagingRejectionRequest,
    StagingPostRequest,
    StagingRollbackRequest,
)
from app.core.config import settings
from app.core.exceptions import ValidationException, ConflictException
from app.db.session import get_db
from app.models.staging import (
    StagedExport,
    StagingStatus,
    ExportFormat,
)
from app.models.invoice import Invoice
from app.services.staging_service import StagingService
from app.services.idempotency_service import IdempotencyService, IdempotencyOperationType

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
staging_service = StagingService()
idempotency_service = IdempotencyService()


@router.post("/stage", response_model=StagedExportResponse)
async def stage_export(
    invoice_id: str = Query(..., description="Invoice ID to stage for export"),
    export_format: ExportFormat = Query(..., description="Export format"),
    destination_system: str = Query(..., description="Destination system"),
    export_data: Dict[str, Any] = Query(..., description="Export data payload"),
    prepared_by: str = Query(..., description="User ID preparing the export"),
    batch_id: Optional[str] = Query(None, description="Optional batch ID"),
    priority: int = Query(5, ge=1, le=10, description="Priority level (1-10)"),
    business_unit: Optional[str] = Query(None, description="Business unit"),
    cost_center: Optional[str] = Query(None, description="Cost center"),
    compliance_flags: Optional[List[str]] = Query(None, description="Compliance flags"),
    db: AsyncSession = Depends(get_db),
):
    """
    Stage an export for review and approval.

    This endpoint creates a staged export record that must be approved before posting.
    The staging process includes:
    - Data quality validation
    - Field-level change tracking
    - Audit trail creation
    - Compliance checking
    """
    logger.info(f"Staging export for invoice {invoice_id} to {destination_system}")

    try:
        # Generate idempotency key for staging operation
        idempotency_key = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            invoice_id=invoice_id,
            destination_system=destination_system,
            export_format=export_format.value,
            user_id=prepared_by,
        )

        # Check for existing idempotency record
        existing_record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            operation_data={
                "invoice_id": invoice_id,
                "export_format": export_format.value,
                "destination_system": destination_system,
                "prepared_by": prepared_by,
            },
            invoice_id=invoice_id,
            user_id=prepared_by,
        )

        if not is_new:
            # Return existing operation result
            if existing_record.operation_status.value == "completed":
                return StagedExportResponse(**existing_record.result_data)
            else:
                raise ConflictException(f"Export staging for invoice {invoice_id} is already in progress")

        # Mark operation as started
        await idempotency_service.mark_operation_started(db, idempotency_key)

        # Stage the export
        staged_export = await staging_service.stage_export(
            db=db,
            invoice_id=invoice_id,
            export_data=export_data,
            export_format=export_format,
            destination_system=destination_system,
            prepared_by=prepared_by,
            batch_id=batch_id,
            priority=priority,
            business_unit=business_unit,
            cost_center=cost_center,
            compliance_flags=compliance_flags,
        )

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": invoice_id,
            "export_format": export_format.value,
            "destination_system": destination_system,
            "staging_status": staged_export.staging_status.value,
            "prepared_at": staged_export.prepared_at,
            "prepared_by": prepared_by,
            "quality_score": staged_export.quality_score,
            "validation_errors": staged_export.validation_errors,
            "batch_id": str(staged_export.batch_id) if staged_export.batch_id else None,
            "priority": staged_export.priority,
            "business_unit": staged_export.business_unit,
            "cost_center": staged_export.cost_center,
            "compliance_flags": staged_export.compliance_flags,
        }

        # Mark operation as completed
        await idempotency_service.mark_operation_completed(db, idempotency_key, response_data)

        logger.info(f"Successfully staged export {staged_export.id}")
        return StagedExportResponse(**response_data)

    except (ValidationException, ConflictException) as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        logger.error(f"Error staging export for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{staged_export_id}/approve", response_model=StagedExportResponse)
async def approve_staged_export(
    staged_export_id: str,
    approval_request: StagingApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a staged export with optional data modifications.

    This endpoint approves a staged export and optionally modifies the export data.
    All modifications are tracked in the audit trail with before/after diffs.
    """
    logger.info(f"Approving staged export {staged_export_id}")

    try:
        # Generate idempotency key for approval operation
        idempotency_key = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            staged_export_id=staged_export_id,
            user_id=approval_request.approved_by,
            action="approve",
        )

        # Check for existing idempotency record
        existing_record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.EXPORT_STAGE,
            operation_data={
                "staged_export_id": staged_export_id,
                "approved_by": approval_request.approved_by,
                "action": "approve",
            },
            user_id=approval_request.approved_by,
        )

        if not is_new:
            # Return existing operation result
            if existing_record.operation_status.value == "completed":
                return StagedExportResponse(**existing_record.result_data)
            else:
                raise ConflictException(f"Export approval for {staged_export_id} is already in progress")

        # Mark operation as started
        await idempotency_service.mark_operation_started(db, idempotency_key)

        # Approve the staged export
        staged_export = await staging_service.approve_staged_export(
            db=db,
            staged_export_id=staged_export_id,
            approved_by=approval_request.approved_by,
            approved_data=approval_request.approved_data,
            change_reason=approval_request.change_reason,
            approval_comments=approval_request.approval_comments,
        )

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": str(staged_export.invoice_id),
            "export_format": staged_export.export_format.value,
            "destination_system": staged_export.destination_system,
            "staging_status": staged_export.staging_status.value,
            "prepared_at": staged_export.prepared_at,
            "approved_at": staged_export.approved_at,
            "approved_by": approval_request.approved_by,
            "quality_score": staged_export.quality_score,
            "field_changes": staged_export.field_changes,
            "change_reason": staged_export.change_reason,
            "reviewer_comments": staged_export.reviewer_comments,
        }

        # Mark operation as completed
        await idempotency_service.mark_operation_completed(db, idempotency_key, response_data)

        logger.info(f"Successfully approved staged export {staged_export_id}")
        return StagedExportResponse(**response_data)

    except (ValidationException, ConflictException) as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        logger.error(f"Error approving staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{staged_export_id}/post", response_model=StagedExportResponse)
async def post_staged_export(
    staged_export_id: str,
    post_request: StagingPostRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Post a staged export to the destination system.

    This endpoint posts an approved staged export to the target system.
    The posting process includes:
    - Integration with destination system
    - External reference tracking
    - Comprehensive audit logging
    """
    logger.info(f"Posting staged export {staged_export_id}")

    try:
        # Generate idempotency key for posting operation
        idempotency_key = idempotency_service.generate_idempotency_key(
            operation_type=IdempotencyOperationType.EXPORT_POST,
            staged_export_id=staged_export_id,
            user_id=post_request.posted_by,
            action="post",
        )

        # Check for existing idempotency record
        existing_record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.EXPORT_POST,
            operation_data={
                "staged_export_id": staged_export_id,
                "posted_by": post_request.posted_by,
                "action": "post",
            },
            user_id=post_request.posted_by,
        )

        if not is_new:
            # Return existing operation result
            if existing_record.operation_status.value == "completed":
                return StagedExportResponse(**existing_record.result_data)
            else:
                raise ConflictException(f"Export posting for {staged_export_id} is already in progress")

        # Mark operation as started
        await idempotency_service.mark_operation_started(db, idempotency_key)

        # Post the staged export
        staged_export = await staging_service.post_staged_export(
            db=db,
            staged_export_id=staged_export_id,
            posted_by=post_request.posted_by,
            external_reference=post_request.external_reference,
            export_filename=post_request.export_filename,
            export_file_size=post_request.export_file_size,
        )

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": str(staged_export.invoice_id),
            "export_format": staged_export.export_format.value,
            "destination_system": staged_export.destination_system,
            "staging_status": staged_export.staging_status.value,
            "posted_at": staged_export.posted_at,
            "posted_by": post_request.posted_by,
            "external_reference": staged_export.external_reference,
            "export_job_id": staged_export.export_job_id,
            "export_filename": staged_export.export_filename,
            "export_file_size": staged_export.export_file_size,
        }

        # Mark operation as completed
        await idempotency_service.mark_operation_completed(db, idempotency_key, response_data)

        logger.info(f"Successfully posted staged export {staged_export_id}")
        return StagedExportResponse(**response_data)

    except (ValidationException, ConflictException) as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        logger.error(f"Error posting staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{staged_export_id}/reject", response_model=StagedExportResponse)
async def reject_staged_export(
    staged_export_id: str,
    rejection_request: StagingRejectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a staged export.

    This endpoint rejects a staged export, preventing it from being posted.
    The rejection is tracked in the audit trail with business reason.
    """
    logger.info(f"Rejecting staged export {staged_export_id}")

    try:
        # Reject the staged export
        staged_export = await staging_service.reject_staged_export(
            db=db,
            staged_export_id=staged_export_id,
            rejected_by=rejection_request.rejected_by,
            rejection_reason=rejection_request.rejection_reason,
        )

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": str(staged_export.invoice_id),
            "export_format": staged_export.export_format.value,
            "destination_system": staged_export.destination_system,
            "staging_status": staged_export.staging_status.value,
            "rejected_at": staged_export.rejected_at,
            "rejected_by": rejection_request.rejected_by,
            "audit_notes": staged_export.audit_notes,
        }

        logger.info(f"Successfully rejected staged export {staged_export_id}")
        return StagedExportResponse(**response_data)

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rejecting staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{staged_export_id}/rollback", response_model=StagedExportResponse)
async def rollback_staged_export(
    staged_export_id: str,
    rollback_request: StagingRollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Roll back a posted staged export.

    This endpoint rolls back an export that has already been posted to the destination system.
    The rollback process includes:
    - Integration with destination system for reversal
    - Comprehensive audit logging
    - Impact assessment
    """
    logger.info(f"Rolling back staged export {staged_export_id}")

    try:
        # Roll back the staged export
        staged_export = await staging_service.rollback_staged_export(
            db=db,
            staged_export_id=staged_export_id,
            rolled_back_by=rollback_request.rolled_back_by,
            rollback_reason=rollback_request.rollback_reason,
        )

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": str(staged_export.invoice_id),
            "export_format": staged_export.export_format.value,
            "destination_system": staged_export.destination_system,
            "staging_status": staged_export.staging_status.value,
            "rolled_back_at": staged_export.updated_at,
            "audit_notes": staged_export.audit_notes,
        }

        logger.info(f"Successfully rolled back staged export {staged_export_id}")
        return StagedExportResponse(**response_data)

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rolling back staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{staged_export_id}/diff", response_model=StagedExportDiffResponse)
async def get_staged_export_diff(
    staged_export_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the diff between original and staged export data.

    This endpoint returns comprehensive diff information showing:
    - Changes from original invoice data to prepared export
    - Changes from prepared export to approved export (if any)
    - Field-level change tracking
    - Business reasons for changes
    """
    logger.info(f"Getting diff for staged export {staged_export_id}")

    try:
        diff_data = await staging_service.get_staged_export_diff(db, staged_export_id)
        return StagedExportDiffResponse(**diff_data)

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting diff for staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=StagedExportListResponse)
async def list_staged_exports(
    status: Optional[StagingStatus] = Query(None, description="Filter by status"),
    destination_system: Optional[str] = Query(None, description="Filter by destination system"),
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    business_unit: Optional[str] = Query(None, description="Filter by business unit"),
    prepared_by: Optional[str] = Query(None, description="Filter by prepared by user"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    List staged exports with comprehensive filtering.

    This endpoint returns a paginated list of staged exports with optional filtering.
    Useful for monitoring export workflows and finding exports requiring action.
    """
    logger.info(f"Listing staged exports with filters: status={status}, destination={destination_system}")

    try:
        staged_exports, total = await staging_service.list_staged_exports(
            db=db,
            status=status,
            destination_system=destination_system,
            batch_id=batch_id,
            business_unit=business_unit,
            prepared_by=prepared_by,
            skip=skip,
            limit=limit,
        )

        # Transform to response format
        export_responses = []
        for export in staged_exports:
            export_data = {
                "id": str(export.id),
                "invoice_id": str(export.invoice_id),
                "export_format": export.export_format.value,
                "destination_system": export.destination_system,
                "staging_status": export.staging_status.value,
                "prepared_at": export.prepared_at,
                "prepared_by": str(export.prepared_by) if export.prepared_by else None,
                "approved_at": export.approved_at,
                "approved_by": str(export.approved_by) if export.approved_by else None,
                "posted_at": export.posted_at,
                "posted_by": str(export.posted_by) if export.posted_by else None,
                "quality_score": export.quality_score,
                "validation_errors": export.validation_errors,
                "batch_id": str(export.batch_id) if export.batch_id else None,
                "priority": export.priority,
                "business_unit": export.business_unit,
                "cost_center": export.cost_center,
                "compliance_flags": export.compliance_flags,
                "audit_trail_count": len(export.audit_trail) if hasattr(export, 'audit_trail') else 0,
            }
            export_responses.append(export_data)

        return StagedExportListResponse(
            staged_exports=export_responses,
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Error listing staged exports: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{staged_export_id}", response_model=StagedExportResponse)
async def get_staged_export(
    staged_export_id: str,
    include_audit_trail: bool = Query(False, description="Include audit trail"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific staged export.

    This endpoint returns comprehensive information about a staged export,
    including audit trail if requested.
    """
    logger.info(f"Getting staged export {staged_export_id}")

    try:
        # Get staged export with optional audit trail
        stmt = select(StagedExport)
        if include_audit_trail:
            from sqlalchemy.orm import selectinload
            stmt = stmt.options(selectinload(StagedExport.audit_trail))

        stmt = stmt.where(StagedExport.id == uuid.UUID(staged_export_id))
        result = await db.execute(stmt)
        staged_export = result.scalar_one_or_none()

        if not staged_export:
            raise HTTPException(status_code=404, detail="Staged export not found")

        # Create response
        response_data = {
            "id": str(staged_export.id),
            "invoice_id": str(staged_export.invoice_id),
            "export_format": staged_export.export_format.value,
            "destination_system": staged_export.destination_system,
            "staging_status": staged_export.staging_status.value,
            "prepared_at": staged_export.prepared_at,
            "approved_at": staged_export.approved_at,
            "posted_at": staged_export.posted_at,
            "rejected_at": staged_export.rejected_at,
            "prepared_by": str(staged_export.prepared_by) if staged_export.prepared_by else None,
            "approved_by": str(staged_export.approved_by) if staged_export.approved_by else None,
            "posted_by": str(staged_export.posted_by) if staged_export.posted_by else None,
            "rejected_by": str(staged_export.rejected_by) if staged_export.rejected_by else None,
            "quality_score": staged_export.quality_score,
            "validation_errors": staged_export.validation_errors,
            "field_changes": staged_export.field_changes,
            "change_reason": staged_export.change_reason,
            "reviewer_comments": staged_export.reviewer_comments,
            "external_reference": staged_export.external_reference,
            "export_job_id": staged_export.export_job_id,
            "export_filename": staged_export.export_filename,
            "export_file_size": staged_export.export_file_size,
            "batch_id": str(staged_export.batch_id) if staged_export.batch_id else None,
            "priority": staged_export.priority,
            "business_unit": staged_export.business_unit,
            "cost_center": staged_export.cost_center,
            "compliance_flags": staged_export.compliance_flags,
            "audit_notes": staged_export.audit_notes,
        }

        # Add audit trail if requested
        if include_audit_trail and hasattr(staged_export, 'audit_trail'):
            response_data["audit_trail"] = [
                {
                    "id": str(audit.id),
                    "action": audit.action,
                    "action_by": str(audit.action_by),
                    "created_at": audit.created_at,
                    "action_reason": audit.action_reason,
                    "business_event": audit.business_event,
                    "impact_assessment": audit.impact_assessment,
                }
                for audit in staged_export.audit_trail
            ]

        return StagedExportResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting staged export {staged_export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")