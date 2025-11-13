"""
Enhanced approval workflow service with RBAC integration for managing multi-step approval chains.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.select import select, and_, or_, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.approval_models import (
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalRequest,
    ApprovalDecision,
    ApproverAssignment,
    ApprovalStatus,
    ApprovalAction,
    ApprovalRole,
    WorkflowType,
    ApprovalAuditLog,
    ApprovalNotification
)
from app.models.rbac import PolicyEvaluation
from app.models.invoice import Invoice
from app.models.user import User
from app.services.auth_service import AuthService, UserPermissions

logger = logging.getLogger(__name__)


class ApprovalWorkflowRequest:
    """Request data for creating an approval workflow."""

    def __init__(
        self,
        workflow_type: WorkflowType,
        entity_type: str,
        entity_id: str,
        title: str,
        description: Optional[str] = None,
        priority: int = 5,
        requested_by: str,
        context_data: Optional[Dict[str, Any]] = None,
        workflow_name: Optional[str] = None,
        approval_metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ):
        self.workflow_type = workflow_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.title = title
        self.description = description
        self.priority = priority
        self.requested_by = requested_by
        self.context_data = context_data or {}
        self.workflow_name = workflow_name
        self.approval_metadata = approval_metadata or {}
        self.expires_at = expires_at


class ApprovalDecisionResult:
    """Result of an approval decision."""

    def __init__(
        self,
        success: bool,
        message: str,
        next_step: Optional[ApprovalStep] = None,
        is_complete: bool = False,
        requires_escalation: bool = False
    ):
        self.success = success
        self.message = message
        self.next_step = next_step
        self.is_complete = is_complete
        self.requires_escalation = requires_escalation


class ApprovalWorkflowService:
    """Service for managing approval workflows with RBAC integration."""

    def __init__(self, db: AsyncSession, auth_service: AuthService):
        self.db = db
        self.auth_service = auth_service

    async def create_approval_request(
        self,
        request: ApprovalWorkflowRequest
    ) -> ApprovalRequest:
        """
        Create a new approval request and start the workflow.

        Args:
            request: The approval workflow request

        Returns:
            The created approval request
        """
        try:
            # Find the appropriate workflow
            workflow = await self._find_workflow(
                request.workflow_type,
                request.workflow_name
            )

            if not workflow:
                raise ValueError(f"No workflow found for type: {request.workflow_type}")

            # Create the approval request
            approval_request = ApprovalRequest(
                workflow_id=workflow.id,
                title=request.title,
                description=request.description,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                priority=request.priority,
                status=ApprovalStatus.PENDING,
                current_step=1,
                requested_by=request.requested_by,
                context_data=request.context_data,
                approval_metadata=request.approval_metadata,
                expires_at=request.expires_at or (
                    datetime.utcnow() + timedelta(hours=workflow.default_timeout_hours)
                )
            )
            self.db.add(approval_request)
            await self.db.flush()  # Get the ID

            # Initialize the first step
            await self._initialize_workflow_step(approval_request, workflow)

            # Log the creation
            await self._log_approval_event(
                approval_request.id,
                "approval_request_created",
                {
                    "workflow_id": str(workflow.id),
                    "workflow_type": workflow.workflow_type,
                    "requested_by": request.requested_by
                },
                user_id=request.requested_by
            )

            await self.db.commit()
            await self.db.refresh(approval_request)

            return approval_request

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating approval request: {e}")
            raise

    async def _find_workflow(
        self,
        workflow_type: WorkflowType,
        workflow_name: Optional[str] = None
    ) -> Optional[ApprovalWorkflow]:
        """Find the appropriate workflow for the given type and name."""
        if workflow_name:
            # Look for specific workflow by name
            stmt = (
                select(ApprovalWorkflow)
                .where(
                    ApprovalWorkflow.workflow_type == workflow_type,
                    ApprovalWorkflow.name == workflow_name,
                    ApprovalWorkflow.is_active == True
                )
                .options(selectinload(ApprovalWorkflow.steps))
            )
        else:
            # Look for default workflow for type
            stmt = (
                select(ApprovalWorkflow)
                .where(
                    ApprovalWorkflow.workflow_type == workflow_type,
                    ApprovalWorkflow.is_active == True
                )
                .order_by(ApprovalWorkflow.name.asc())  # Get the first one
                .options(selectinload(ApprovalWorkflow.steps))
            )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _initialize_workflow_step(
        self,
        approval_request: ApprovalRequest,
        workflow: ApprovalWorkflow
    ):
        """Initialize the first step of the workflow."""
        # Get the first step
        first_step = await self._get_workflow_step(workflow.id, 1)
        if not first_step:
            raise ValueError(f"No step 1 found for workflow {workflow.id}")

        # Find approvers for this step
        approvers = await self._find_approvers_for_step(
            first_step,
            approval_request
        )

        # Create assignments
        assignments = []
        for approver in approvers:
            assignment = ApproverAssignment(
                approval_request_id=approval_request.id,
                step_id=first_step.id,
                user_id=approver["user_id"],
                status="pending",
                assigned_at=datetime.utcnow(),
                assignment_data=approver.get("assignment_data", {})
            )
            assignments.append(assignment)
            self.db.add(assignment)

        # Update request status
        approval_request.status = ApprovalStatus.PENDING
        approval_request.current_step = 1

        # Send notifications
        await self._send_step_notifications(approval_request, first_step, assignments)

    async def _get_workflow_step(
        self,
        workflow_id: str,
        step_order: int
    ) -> Optional[ApprovalStep]:
        """Get a specific step in a workflow."""
        stmt = (
            select(ApprovalStep)
            .where(
                ApprovalStep.workflow_id == workflow_id,
                ApprovalStep.step_order == step_order
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_approvers_for_step(
        self,
        step: ApprovalStep,
        approval_request: ApprovalRequest
    ) -> List[Dict[str, Any]]:
        """Find approvers for a workflow step."""
        approvers = []

        # Get users with the required role
        user_permissions = await self.auth_service.get_user_permissions(approval_request.requested_by)

        # For now, we'll use a simple approach - in a real system,
        # this would be more sophisticated with role-based routing
        if step.approval_role == ApprovalRole.AP_MANAGER:
            # Get users with manager role
            approvers.extend(await self._get_users_by_role("manager"))
        elif step.approval_role == ApprovalRole.CONTROLLER:
            approvers.extend(await self._get_users_by_role("manager"))  # Use manager as controller
        elif step.approval_role == ApprovalRole.CFO:
            approvers.extend(await self._get_users_by_role("admin"))  # Use admin as CFO
        elif step.approval_role == ApprovalRole.AP_CLERK:
            approvers.extend(await self._get_users_by_role("ap_clerk"))
        elif step.approval_role == ApprovalRole.SYSTEM_ADMIN:
            approvers.extend(await self._get_users_by_role("admin"))

        # Filter by required count
        if step.required_approvers > 0 and len(approvers) > step.required_approvers:
            approvers = approvers[:step.required_approvers]

        return [{"user_id": approver} for approver in approvers]

    async def _get_users_by_role(self, role_name: str) -> List[str]:
        """Get user IDs by role name."""
        # This is a simplified implementation
        # In a real system, you'd query the user_roles table
        if role_name == "admin":
            return ["admin-user"]
        elif role_name == "manager":
            return ["manager-user"]
        elif role_name == "ap_clerk":
            return ["clerk-user"]
        else:
            return []

    async def _send_step_notifications(
        self,
        approval_request: ApprovalRequest,
        step: ApprovalStep,
        assignments: List[ApproverAssignment]
    ):
        """Send notifications for a workflow step."""
        for assignment in assignments:
            notification = ApprovalNotification(
                approval_request_id=approval_request.id,
                user_id=assignment.user_id,
                notification_type="approval_required",
                subject=f"Approval Required: {approval_request.title}",
                message=f"Your approval is required for {approval_request.title}",
                delivery_method="email",
                recipient_address=f"{assignment.user_id}@company.com",
                status="pending"
            )
            self.db.add(notification)

    async def process_approval_decision(
        self,
        approval_request_id: str,
        approver_id: str,
        action: ApprovalAction,
        comments: Optional[str] = None,
        decision_data: Optional[Dict[str, Any]] = None
    ) -> ApprovalDecisionResult:
        """
        Process an approval decision.

        Args:
            approval_request_id: The ID of the approval request
            approver_id: The ID of the approver
            action: The approval action
            comments: Optional comments
            decision_data: Additional decision data

        Returns:
            The result of the decision
        """
        try:
            # Get the approval request
            approval_request = await self._get_approval_request(approval_request_id)
            if not approval_request:
                raise ValueError(f"Approval request not found: {approval_request_id}")

            # Get the current step
            current_step = await self._get_workflow_step(
                approval_request.workflow_id,
                approval_request.current_step
            )
            if not current_step:
                raise ValueError(f"Current step not found: {approval_request.current_step}")

            # Check if approver is assigned to this step
            assignment = await self._get_approver_assignment(
                approval_request_id,
                current_step.id,
                approver_id
            )
            if not assignment:
                raise ValueError(f"Approver not assigned to this step: {approver_id}")

            # Create the decision
            decision = ApprovalDecision(
                approval_request_id=approval_request_id,
                step_id=current_step.id,
                approver_id=approver_id,
                action=action,
                comments=comments,
                decision_data=decision_data or {},
                decision_time=datetime.utcnow()
            )
            self.db.add(decision)

            # Update assignment status
            assignment.status = action.value
            assignment.acknowledged_at = datetime.utcnow()

            # Process the decision
            result = await self._process_decision_outcome(
                approval_request,
                current_step,
                decision
            )

            # Log the decision
            await self._log_approval_event(
                approval_request_id,
                "approval_decision",
                {
                    "approver_id": approver_id,
                    "action": action.value,
                    "step_order": current_step.step_order,
                    "comments": comments
                },
                user_id=approver_id
            )

            await self.db.commit()
            return result

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error processing approval decision: {e}")
            raise

    async def _get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .options(selectinload(ApprovalRequest.workflow))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_approver_assignment(
        self,
        approval_request_id: str,
        step_id: str,
        approver_id: str
    ) -> Optional[ApproverAssignment]:
        """Get an approver assignment."""
        stmt = (
            select(ApproverAssignment)
            .where(
                ApproverAssignment.approval_request_id == approval_request_id,
                ApproverAssignment.step_id == step_id,
                ApproverAssignment.user_id == approver_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _process_decision_outcome(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process the outcome of an approval decision."""
        if decision.action == ApprovalAction.APPROVE:
            return await self._process_approval(approval_request, current_step, decision)
        elif decision.action == ApprovalAction.REJECT:
            return await self._process_rejection(approval_request, current_step, decision)
        elif decision.action == ApprovalAction.REQUEST_CHANGES:
            return await self._process_change_request(approval_request, current_step, decision)
        elif decision.action == ApprovalAction.DELEGATE:
            return await self._process_delegation(approval_request, current_step, decision)
        elif decision.action == ApprovalAction.ESCALATE:
            return await self._process_escalation(approval_request, current_step, decision)
        else:
            raise ValueError(f"Unknown approval action: {decision.action}")

    async def _process_approval(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process an approval decision."""
        # Check if we have enough approvals for this step
        step_approvals = await self._count_step_approvals(
            approval_request.id,
            current_step.id,
            ApprovalAction.APPROVE
        )

        if step_approvals >= current_step.required_approvers:
            # Step is complete, move to next step
            next_step = await self._get_workflow_step(
                approval_request.workflow_id,
                current_step.step_order + 1
            )

            if next_step:
                # Move to next step
                approval_request.current_step = next_step.step_order
                await self._initialize_workflow_step(approval_request, approval_request.workflow)

                return ApprovalDecisionResult(
                    success=True,
                    message=f"Approved. Moving to step {next_step.step_order}",
                    next_step=next_step,
                    is_complete=False
                )
            else:
                # Workflow is complete
                approval_request.status = ApprovalStatus.APPROVED
                approval_request.completed_at = datetime.utcnow()

                return ApprovalDecisionResult(
                    success=True,
                    message="Workflow completed successfully",
                    is_complete=True
                )
        else:
            # Still waiting for more approvals
            remaining = current_step.required_approvers - step_approvals
            return ApprovalDecisionResult(
                success=True,
                message=f"Approved. {remaining} more approval(s) needed",
                is_complete=False
            )

    async def _process_rejection(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process a rejection decision."""
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.completed_at = datetime.utcnow()

        return ApprovalDecisionResult(
            success=True,
            message="Request rejected",
            is_complete=True
        )

    async def _process_change_request(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process a change request decision."""
        approval_request.status = ApprovalStatus.IN_REVIEW

        return ApprovalDecisionResult(
            success=True,
            message="Changes requested",
            is_complete=False,
            requires_escalation=True
        )

    async def _process_delegation(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process a delegation decision."""
        # In a real implementation, this would delegate to another user
        return ApprovalDecisionResult(
            success=True,
            message="Approval delegated",
            is_complete=False
        )

    async def _process_escalation(
        self,
        approval_request: ApprovalRequest,
        current_step: ApprovalStep,
        decision: ApprovalDecision
    ) -> ApprovalDecisionResult:
        """Process an escalation decision."""
        # In a real implementation, this would escalate to a higher level
        return ApprovalDecisionResult(
            success=True,
            message="Request escalated",
            is_complete=False,
            requires_escalation=True
        )

    async def _count_step_approvals(
        self,
        approval_request_id: str,
        step_id: str,
        action: ApprovalAction
    ) -> int:
        """Count approvals for a step."""
        stmt = (
            select(func.count(ApprovalDecision.id))
            .where(
                ApprovalDecision.approval_request_id == approval_request_id,
                ApprovalDecision.step_id == step_id,
                ApprovalDecision.action == action
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _log_approval_event(
        self,
        approval_request_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log an approval workflow event."""
        audit_log = ApprovalAuditLog(
            approval_request_id=approval_request_id,
            event_type=event_type,
            event_data=event_data,
            user_id=user_id
        )
        self.db.add(audit_log)

    async def get_approval_summary(
        self,
        approval_request_id: str
    ) -> Dict[str, Any]:
        """Get a summary of an approval request."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == approval_request_id)
            .options(
                selectinload(ApprovalRequest.workflow).selectinload(ApprovalWorkflow.steps),
                selectinload(ApprovalRequest.decisions),
                selectinload(ApprovalRequest.assignments)
            )
        )
        result = await self.db.execute(stmt)
        approval_request = result.scalar_one_or_none()

        if not approval_request:
            return {"error": "Approval request not found"}

        # Build summary
        summary = {
            "id": str(approval_request.id),
            "title": approval_request.title,
            "description": approval_request.description,
            "status": approval_request.status.value,
            "current_step": approval_request.current_step,
            "priority": approval_request.priority,
            "requested_by": approval_request.requested_by,
            "created_at": approval_request.created_at.isoformat(),
            "completed_at": approval_request.completed_at.isoformat() if approval_request.completed_at else None,
            "expires_at": approval_request.expires_at.isoformat() if approval_request.expires_at else None,
            "workflow": {
                "name": approval_request.workflow.name,
                "type": approval_request.workflow.workflow_type.value
            },
            "steps": [],
            "decisions": [],
            "assignments": []
        }

        # Add steps information
        for step in approval_request.workflow.steps:
            step_approvals = await self._count_step_approvals(
                approval_request_id,
                step.id,
                ApprovalAction.APPROVE
            )

            step_info = {
                "step_order": step.step_order,
                "step_name": step.step_name,
                "approval_role": step.approval_role.value,
                "required_approvers": step.required_approvers,
                "current_approvals": step_approvals,
                "is_current_step": step.step_order == approval_request.current_step
            }
            summary["steps"].append(step_info)

        # Add decisions
        for decision in approval_request.decisions:
            summary["decisions"].append({
                "approver_id": decision.approver_id,
                "action": decision.action.value,
                "comments": decision.comments,
                "decision_time": decision.decision_time.isoformat()
            })

        # Add assignments
        for assignment in approval_request.assignments:
            summary["assignments"].append({
                "user_id": assignment.user_id,
                "status": assignment.status,
                "assigned_at": assignment.assigned_at.isoformat(),
                "acknowledged_at": assignment.acknowledged_at.isoformat() if assignment.acknowledged_at else None
            })

        return summary

    async def get_user_pending_approvals(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get pending approvals for a user."""
        stmt = (
            select(ApprovalRequest)
            .join(ApproverAssignment, ApprovalRequest.id == ApproverAssignment.approval_request_id)
            .where(
                ApproverAssignment.user_id == user_id,
                ApproverAssignment.status == "pending",
                ApprovalRequest.status == ApprovalStatus.PENDING
            )
            .order_by(ApprovalRequest.priority.desc(), ApprovalRequest.created_at.asc())
            .limit(limit)
            .options(selectinload(ApprovalRequest.workflow))
        )
        result = await self.db.execute(stmt)
        requests = result.scalars().all()

        approvals = []
        for request in requests:
            approvals.append({
                "id": str(request.id),
                "title": request.title,
                "description": request.description,
                "priority": request.priority,
                "workflow_type": request.workflow.workflow_type.value,
                "current_step": request.current_step,
                "created_at": request.created_at.isoformat(),
                "expires_at": request.expires_at.isoformat() if request.expires_at else None
            })

        return approvals

    async def get_approval_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get approval workflow statistics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get completed requests
        completed_stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.completed_at >= cutoff_date,
                ApprovalRequest.completed_at.isnot(None)
            )
        )
        completed_result = await self.db.execute(completed_stmt)
        completed_requests = completed_result.scalars().all()

        # Get pending requests
        pending_stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.status.in_([
                    ApprovalStatus.PENDING,
                    ApprovalStatus.IN_REVIEW
                ]),
                ApprovalRequest.created_at >= cutoff_date
            )
        )
        pending_result = await self.db.execute(pending_stmt)
        pending_requests = pending_result.scalars().all()

        # Calculate statistics
        total_completed = len(completed_requests)
        total_pending = len(pending_requests)

        approved_count = len([r for r in completed_requests if r.status == ApprovalStatus.APPROVED])
        rejected_count = len([r for r in completed_requests if r.status == ApprovalStatus.REJECTED])

        # Calculate average completion time
        if completed_requests:
            completion_times = [
                (r.completed_at - r.created_at).total_seconds() / 3600  # hours
                for r in completed_requests
            ]
            avg_completion_hours = sum(completion_times) / len(completion_times)
        else:
            avg_completion_hours = 0

        stats = {
            "period_days": days,
            "total_requests": total_completed + total_pending,
            "completed_requests": total_completed,
            "pending_requests": total_pending,
            "approved_requests": approved_count,
            "rejected_requests": rejected_count,
            "approval_rate": (approved_count / total_completed * 100) if total_completed > 0 else 0,
            "average_completion_hours": avg_completion_hours,
            "workflow_types": {},
            "step_performance": {}
        }

        # Break down by workflow type
        for request in completed_requests + pending_requests:
            workflow_type = request.workflow.workflow_type.value
            if workflow_type not in stats["workflow_types"]:
                stats["workflow_types"][workflow_type] = {
                    "total": 0,
                    "completed": 0,
                    "pending": 0
                }
            stats["workflow_types"][workflow_type]["total"] += 1
            if request.completed_at:
                stats["workflow_types"][workflow_type]["completed"] += 1
            else:
                stats["workflow_types"][workflow_type]["pending"] += 1

        return stats