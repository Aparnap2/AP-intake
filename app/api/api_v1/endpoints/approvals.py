"""
Approval workflow API endpoints.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.api_v1.deps import get_current_user
from app.db.session import get_db
from app.models.approval_models import (
    ApprovalWorkflow, ApprovalRequest, ApprovalDecision, ApprovalStatus,
    WorkflowType
)
from app.schemas.approval_schemas import (
    ApprovalWorkflowCreate, ApprovalWorkflowUpdate, ApprovalWorkflowResponse,
    ApprovalRequestCreate, ApprovalRequestResponse, ApprovalDecisionCreate,
    ApprovalDecisionResponse, ApprovalStatusResponse, ApprovalFilter,
    StagedExportCreate, StagedExportResponse, ExportApprovalRequest,
    DiffComparisonResponse, BulkApprovalRequest, BulkApprovalResponse,
    ApprovalStatisticsResponse
)
from app.services.approval_service import ApprovalService
from app.services.diff_service import DiffService
from app.services.erp_adapter_service import ERPAdapterService

logger = logging.getLogger(__name__)
router = APIRouter()


# Workflow Management Endpoints
@router.post("/workflows", response_model=ApprovalWorkflowResponse)
async def create_approval_workflow(
    workflow_data: ApprovalWorkflowCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new approval workflow."""
    try:
        approval_service = ApprovalService(db=db)
        workflow = await approval_service.workflow_engine.create_workflow(
            workflow_data,
            current_user.get("sub")
        )
        return workflow

    except Exception as e:
        logger.error(f"Failed to create approval workflow: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflows", response_model=List[ApprovalWorkflowResponse])
async def list_approval_workflows(
    workflow_type: Optional[WorkflowType] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List approval workflows."""
    query = db.query(ApprovalWorkflow)

    if workflow_type:
        query = query.filter(ApprovalWorkflow.workflow_type == workflow_type)
    if is_active is not None:
        query = query.filter(ApprovalWorkflow.is_active == is_active)

    workflows = query.order_by(ApprovalWorkflow.name).offset(offset).limit(limit).all()
    return workflows


@router.get("/workflows/{workflow_id}", response_model=ApprovalWorkflowResponse)
async def get_approval_workflow(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific approval workflow."""
    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")
    return workflow


@router.put("/workflows/{workflow_id}", response_model=ApprovalWorkflowResponse)
async def update_approval_workflow(
    workflow_id: str,
    workflow_data: ApprovalWorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an approval workflow."""
    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")

    # Update fields
    update_data = workflow_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workflow, field, value)

    workflow.updated_by = current_user.get("sub")
    workflow.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workflow)

    return workflow


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_approval_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete an approval workflow."""
    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")

    # Check if workflow has active requests
    active_requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.workflow_id == workflow_id,
        ApprovalRequest.status.in_(['pending', 'in_review'])
    ).count()

    if active_requests > 0:
        raise HTTPException(status_code=400, detail="Cannot delete workflow with active requests")

    db.delete(workflow)
    db.commit()


# Request Management Endpoints
@router.post("/requests", response_model=ApprovalRequestResponse)
async def create_approval_request(
    request_data: ApprovalRequestCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new approval request."""
    try:
        approval_service = ApprovalService(db=db)
        request = await approval_service.workflow_engine.initiate_approval_request(
            request_data,
            current_user.get("sub")
        )
        return request

    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests", response_model=List[ApprovalRequestResponse])
async def list_approval_requests(
    status: Optional[List[ApprovalStatus]] = Query(None),
    entity_type: Optional[str] = None,
    priority: Optional[List[int]] = Query(None),
    requested_by: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List approval requests."""
    query = db.query(ApprovalRequest)

    # Filter by user unless admin
    if current_user.get("role") != "admin":
        query = query.filter(ApprovalRequest.requested_by == current_user.get("sub"))

    if status:
        query = query.filter(ApprovalRequest.status.in_(status))
    if entity_type:
        query = query.filter(ApprovalRequest.entity_type == entity_type)
    if priority:
        query = query.filter(ApprovalRequest.priority.in_(priority))
    if requested_by:
        query = query.filter(ApprovalRequest.requested_by == requested_by)

    requests = query.order_by(ApprovalRequest.created_at.desc()).offset(offset).limit(limit).all()
    return requests


@router.get("/requests/{request_id}", response_model=ApprovalStatusResponse)
async def get_approval_request_status(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed approval request status."""
    try:
        approval_service = ApprovalService(db=db)
        status_data = await approval_service.workflow_engine.get_approval_request_status(request_id)
        return status_data

    except Exception as e:
        logger.error(f"Failed to get approval request status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Decision Management Endpoints
@router.post("/decisions", response_model=ApprovalDecisionResponse)
async def submit_approval_decision(
    decision_data: ApprovalDecisionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit an approval decision."""
    try:
        approval_service = ApprovalService(db=db)
        decision = await approval_service.workflow_engine.submit_approval_decision(
            decision_data,
            current_user.get("sub")
        )
        return decision

    except Exception as e:
        logger.error(f"Failed to submit approval decision: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-approvals", response_model=List[ApprovalRequestResponse])
async def get_my_pending_approvals(
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get pending approval requests for current user."""
    try:
        approval_service = ApprovalService(db=db)
        requests = approval_service.workflow_engine.get_pending_approvals(current_user.get("sub"))
        return requests[:limit]

    except Exception as e:
        logger.error(f"Failed to get pending approvals: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-approval-history", response_model=List[ApprovalRequestResponse])
async def get_my_approval_history(
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get approval history for current user."""
    try:
        approval_service = ApprovalService(db=db)
        requests = approval_service.workflow_engine.get_approval_history(current_user.get("sub"), limit)
        return requests

    except Exception as e:
        logger.error(f"Failed to get approval history: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Staged Export Approval Endpoints
@router.post("/staged-exports", response_model=StagedExportResponse)
async def stage_export_for_approval(
    export_data: StagedExportCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Stage an export for approval."""
    try:
        approval_service = ApprovalService(db=db)
        staged_export = await approval_service.stage_export_for_approval(
            str(export_data.invoice_id),
            export_data.export_format,
            export_data.export_data,
            str(export_data.workflow_id),
            current_user.get("sub")
        )
        return staged_export

    except Exception as e:
        logger.error(f"Failed to stage export for approval: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/exports/approve", response_model=ApprovalRequestResponse)
async def create_export_approval_request(
    approval_data: ExportApprovalRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create approval request for staged export."""
    try:
        approval_service = ApprovalService(db=db)

        # Get staged export data
        from app.models.invoice import StagedExport
        staged_export = db.query(StagedExport).filter(
            StagedExport.id == approval_data.staged_export_id
        ).first()

        if not staged_export:
            raise HTTPException(status_code=404, detail="Staged export not found")

        # Create approval request
        request_data = ApprovalRequestCreate(
            workflow_id=approval_data.workflow_id,
            title=approval_data.title or f"Export Approval - {staged_export.id}",
            description=approval_data.description or f"Review and approve export of invoice {staged_export.invoice_id}",
            entity_type="staged_export",
            entity_id=staged_export.id,
            priority=approval_data.priority,
            context_data=approval_data.context_data
        )

        request = await approval_service.workflow_engine.initiate_approval_request(
            request_data,
            current_user.get("sub")
        )

        return request

    except Exception as e:
        logger.error(f"Failed to create export approval request: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exports/{staged_export_id}/diff", response_model=DiffComparisonResponse)
async def get_export_approval_diff(
    staged_export_id: str,
    db: Session = Depends(get_db)
):
    """Get diff comparison for staged export approval."""
    try:
        approval_service = ApprovalService(db=db)
        diff_data = await approval_service.get_approval_diff(staged_export_id)
        return diff_data

    except Exception as e:
        logger.error(f"Failed to get export approval diff: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Bulk Approval Endpoints
@router.post("/bulk-approvals", response_model=BulkApprovalResponse)
async def submit_bulk_approvals(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit approval decisions for multiple requests."""
    try:
        approval_service = ApprovalService(db=db)

        successful_approvals = []
        failed_approvals = []

        for request_id in bulk_data.approval_request_ids:
            try:
                decision_data = ApprovalDecisionCreate(
                    approval_request_id=request_id,
                    action=bulk_data.action,
                    comments=bulk_data.comments,
                    decision_data=bulk_data.decision_data
                )

                decision = await approval_service.workflow_engine.submit_approval_decision(
                    decision_data,
                    current_user.get("sub")
                )
                successful_approvals.append(request_id)

            except Exception as e:
                failed_approvals.append({
                    "request_id": request_id,
                    "error": str(e)
                })

        return BulkApprovalResponse(
            successful_approvals=successful_approvals,
            failed_approvals=failed_approvals,
            total_processed=len(bulk_data.approval_request_ids),
            success_count=len(successful_approvals),
            failure_count=len(failed_approvals)
        )

    except Exception as e:
        logger.error(f"Failed to submit bulk approvals: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ERP Integration Endpoints
@router.post("/erp/test-connection")
async def test_erp_connection(
    system_type: str,
    environment: str = "sandbox",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Test connection to ERP system."""
    try:
        from app.services.erp_adapter_service import ERPSystemType, ERPEnvironment
        erp_service = ERPAdapterService(db=db)

        result = await erp_service.test_erp_connection(
            ERPSystemType(system_type),
            ERPEnvironment(environment)
        )

        return result

    except Exception as e:
        logger.error(f"Failed to test ERP connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/erp/export")
async def export_to_erp(
    invoice_data: dict,
    system_type: str,
    environment: str = "sandbox",
    action: str = "create_vendor_bill",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Export invoice data to ERP system."""
    try:
        from app.services.erp_adapter_service import ERPSystemType, ERPEnvironment, ERPAction
        erp_service = ERPAdapterService(db=db)

        result = await erp_service.export_invoice_to_erp(
            invoice_data,
            ERPSystemType(system_type),
            ERPEnvironment(environment),
            ERPAction(action)
        )

        return result

    except Exception as e:
        logger.error(f"Failed to export to ERP: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/erp/systems")
async def get_available_erp_systems(
    db: Session = Depends(get_db)
):
    """Get list of available ERP systems."""
    try:
        erp_service = ERPAdapterService(db=db)
        systems = erp_service.get_available_erps()
        return {"systems": systems}

    except Exception as e:
        logger.error(f"Failed to get available ERP systems: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/erp/sync-accounts")
async def sync_chart_of_accounts(
    system_type: str,
    environment: str = "sandbox",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Sync chart of accounts from ERP system."""
    try:
        from app.services.erp_adapter_service import ERPSystemType, ERPEnvironment
        erp_service = ERPAdapterService(db=db)

        result = await erp_service.sync_chart_of_accounts(
            ERPSystemType(system_type),
            ERPEnvironment(environment)
        )

        return result

    except Exception as e:
        logger.error(f"Failed to sync chart of accounts: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Statistics and Analytics Endpoints
@router.get("/statistics", response_model=ApprovalStatisticsResponse)
async def get_approval_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get approval statistics."""
    try:
        # Build base query
        query = db.query(ApprovalRequest)

        # Apply date filters
        if date_from:
            query = query.filter(ApprovalRequest.created_at >= date_from)
        if date_to:
            query = query.filter(ApprovalRequest.created_at <= date_to)

        # Get counts by status
        total_requests = query.count()
        pending_requests = query.filter(ApprovalRequest.status == ApprovalStatus.PENDING).count()
        approved_requests = query.filter(ApprovalRequest.status == ApprovalStatus.APPROVED).count()
        rejected_requests = query.filter(ApprovalRequest.status == ApprovalStatus.REJECTED).count()
        expired_requests = query.filter(ApprovalRequest.status == ApprovalStatus.EXPIRED).count()

        # Calculate approval rate
        approval_rate = (approved_requests / total_requests * 100) if total_requests > 0 else 0

        # Get average approval time
        completed_requests = query.filter(ApprovalRequest.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])).all()
        approval_times = []
        for req in completed_requests:
            if req.completed_at and req.created_at:
                time_diff = (req.completed_at - req.created_at).total_seconds() / 3600  # hours
                approval_times.append(time_diff)

        avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0

        # Get requests by type
        requests_by_type = {}
        for req in query.all():
            entity_type = req.entity_type
            requests_by_type[entity_type] = requests_by_type.get(entity_type, 0) + 1

        # Get requests by priority
        requests_by_priority = {}
        for req in query.all():
            priority = req.priority
            requests_by_priority[priority] = requests_by_priority.get(priority, 0) + 1

        return ApprovalStatisticsResponse(
            total_requests=total_requests,
            pending_requests=pending_requests,
            approved_requests=approved_requests,
            rejected_requests=rejected_requests,
            expired_requests=expired_requests,
            average_approval_time_hours=avg_approval_time,
            approval_rate_percentage=approval_rate,
            requests_by_type=requests_by_type,
            requests_by_priority=requests_by_priority
        )

    except Exception as e:
        logger.error(f"Failed to get approval statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Diff and Comparison Endpoints
@router.post("/diff/generate")
async def generate_diff_comparison(
    original_data: dict,
    modified_data: dict,
    comparison_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate diff comparison between two datasets."""
    try:
        diff_service = DiffService(db=db)
        diff_data = await diff_service.generate_export_diff(
            original_data,
            modified_data,
            comparison_name
        )
        return diff_data

    except Exception as e:
        logger.error(f"Failed to generate diff comparison: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/diff/validate")
async def validate_export_changes(
    diff_data: dict,
    db: Session = Depends(get_db)
):
    """Validate if export changes are acceptable."""
    try:
        diff_service = DiffService(db=db)
        validation_result = diff_service.validate_export_changes(diff_data)
        return validation_result

    except Exception as e:
        logger.error(f"Failed to validate export changes: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/diff/summary")
async def get_diff_summary(
    diff_data: dict,
    db: Session = Depends(get_db)
):
    """Get summary of diff comparison."""
    try:
        diff_service = DiffService(db=db)
        summary = diff_service.get_diff_summary(diff_data)
        return summary

    except Exception as e:
        logger.error(f"Failed to get diff summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))