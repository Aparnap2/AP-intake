"""
Approval workflow endpoints with RBAC integration.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.api_v1.deps import get_db
from app.services.auth_service import (
    AuthService,
    get_auth_service,
    get_current_user_with_permissions
)
from app.services.approval_service import (
    ApprovalWorkflowService,
    ApprovalWorkflowRequest
)
from app.services.policy_service import PolicyEvaluationEngine
from app.models.approval_models import (
    ApprovalAction,
    WorkflowType,
    ApprovalStatus
)
from app.decorators.rbac import (
    require_permission,
    require_approval_level,
    conditional_auth
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


# Pydantic models for requests/responses
class ApprovalRequestCreate(BaseModel):
    workflow_type: WorkflowType
    entity_type: str
    entity_id: str
    title: str
    description: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    workflow_name: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None
    approval_metadata: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class ApprovalDecisionRequest(BaseModel):
    action: ApprovalAction
    comments: Optional[str] = None
    decision_data: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    current_step: int
    priority: int
    requested_by: str
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]
    workflow: Dict[str, Any]
    steps: List[Dict[str, Any]]
    decisions: List[Dict[str, Any]]
    assignments: List[Dict[str, Any]]


class PendingApprovalResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    priority: int
    workflow_type: str
    current_step: int
    created_at: datetime
    expires_at: Optional[datetime]


# Approval workflow endpoints
@router.post("/request", response_model=Dict[str, Any])
@require_permission("approval", "write")
async def create_approval_request(
    request_data: ApprovalRequestCreate,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Create a new approval request."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        approval_service = ApprovalWorkflowService(db, auth_service)

        # Create approval request
        approval_request = ApprovalWorkflowRequest(
            workflow_type=request_data.workflow_type,
            entity_type=request_data.entity_type,
            entity_id=request_data.entity_id,
            title=request_data.title,
            description=request_data.description,
            priority=request_data.priority,
            requested_by=current_user["user_id"],
            context_data=request_data.context_data,
            workflow_name=request_data.workflow_name,
            approval_metadata=request_data.approval_metadata,
            expires_at=request_data.expires_at
        )

        created_request = await approval_service.create_approval_request(approval_request)

        return {
            "id": str(created_request.id),
            "message": "Approval request created successfully",
            "status": created_request.status.value,
            "current_step": created_request.current_step
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create approval request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create approval request"
        )


@router.get("/{approval_id}", response_model=ApprovalResponse)
@require_permission("approval", "read")
async def get_approval_details(
    approval_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about an approval request."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        approval_service = ApprovalWorkflowService(db, auth_service)

        # Get approval summary
        summary = await approval_service.get_approval_summary(approval_id)

        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )

        return ApprovalResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get approval details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval details"
        )


@router.post("/{approval_id}/decide", response_model=Dict[str, Any])
@require_approval_level(level=1)
async def submit_approval_decision(
    approval_id: str,
    decision_data: ApprovalDecisionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Submit a decision on an approval request."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        approval_service = ApprovalWorkflowService(db, auth_service)

        # Process decision
        result = await approval_service.process_approval_decision(
            approval_request_id=approval_id,
            approver_id=current_user["user_id"],
            action=decision_data.action,
            comments=decision_data.comments,
            decision_data=decision_data.decision_data
        )

        return {
            "success": result.success,
            "message": result.message,
            "is_complete": result.is_complete,
            "requires_escalation": result.requires_escalation
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Submit approval decision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit approval decision"
        )


@router.get("/pending/my-approvals", response_model[List[PendingApprovalResponse]])
@require_approval_level(level=1)
async def get_my_pending_approvals(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get pending approvals for the current user."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        approval_service = ApprovalWorkflowService(db, auth_service)

        # Get pending approvals
        pending_approvals = await approval_service.get_user_pending_approvals(
            user_id=current_user["user_id"],
            limit=limit
        )

        return [PendingApprovalResponse(**approval) for approval in pending_approvals]

    except Exception as e:
        logger.error(f"Get pending approvals error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending approvals"
        )


@router.get("/statistics", response_model=Dict[str, Any])
@require_permission("approval", "read")
async def get_approval_statistics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get approval workflow statistics."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        approval_service = ApprovalWorkflowService(db, auth_service)

        # Get statistics
        stats = await approval_service.get_approval_statistics(days=days)

        return stats

    except Exception as e:
        logger.error(f"Get approval statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval statistics"
        )


# Policy evaluation endpoints
@router.post("/policies/evaluate/{invoice_id}", response_model=Dict[str, Any])
@require_permission("policy", "read")
async def evaluate_invoice_policies(
    invoice_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Evaluate policy gates for an invoice."""
    try:
        # Initialize policy engine
        policy_engine = PolicyEvaluationEngine(db)

        # Get invoice (this would typically come from database)
        # For now, we'll create a mock invoice
        from app.models.invoice import Invoice, Vendor
        from app.models.vendor import Vendor
        import uuid

        # Mock invoice for demonstration
        invoice = Invoice(
            id=uuid.UUID(invoice_id) if invoice_id != "demo" else uuid.uuid4(),
            invoice_number="INV-2024-001",
            total_amount=15000.00,
            currency="USD",
            vendor_id=uuid.uuid4()
        )

        # Mock vendor
        vendor = Vendor(
            id=invoice.vendor_id,
            name="Sample Vendor",
            vendor_number="VEND-001"
        )

        # Evaluate policies
        results = await policy_engine.evaluate_invoice(invoice, vendor)

        return {
            "invoice_id": str(invoice.id),
            "evaluation_summary": {
                "total_gates": len(results),
                "triggered_gates": len([r for r in results if r.triggered]),
                "blocked_gates": len([r for r in results if r.result == "blocked"]),
                "requires_approval": len([r for r in results if r.result == "requires_approval"])
            },
            "evaluations": [result.to_dict() for result in results]
        }

    except Exception as e:
        logger.error(f"Evaluate invoice policies error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate invoice policies"
        )


@router.get("/policies/summary/{invoice_id}", response_model=Dict[str, Any])
@require_permission("policy", "read")
async def get_policy_evaluation_summary(
    invoice_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get a summary of policy evaluations for an invoice."""
    try:
        # Initialize policy engine
        policy_engine = PolicyEvaluationEngine(db)

        # Get summary
        summary = await policy_engine.get_policy_evaluation_summary(invoice_id)

        return summary

    except Exception as e:
        logger.error(f"Get policy evaluation summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get policy evaluation summary"
        )


@router.get("/policies/statistics", response_model=Dict[str, Any])
@require_permission("policy", "read")
async def get_policy_statistics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get policy gate statistics."""
    try:
        # Initialize policy engine
        policy_engine = PolicyEvaluationEngine(db)

        # Get statistics
        stats = await policy_engine.get_policy_gate_statistics(days=days)

        return stats

    except Exception as e:
        logger.error(f"Get policy statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get policy statistics"
        )


# System management endpoints (admin only)
@router.post("/initialize-system")
@require_permission("system", "admin")
async def initialize_approval_system(
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Initialize the approval system with default data."""
    try:
        # Initialize services
        auth_service = AuthService(db)
        policy_engine = PolicyEvaluationEngine(db)

        # Initialize default roles and policies
        await auth_service.initialize_default_roles()
        await policy_engine.initialize_default_policy_gates()

        return {
            "message": "Approval system initialized successfully",
            "initialized_components": [
                "default_roles",
                "default_policy_gates"
            ]
        }

    except Exception as e:
        logger.error(f"Initialize approval system error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize approval system"
        )