"""
Approval workflow service for managing staged exports and approval processes.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import ApprovalException, ValidationException
from app.models.invoice import Invoice, StagedExport
from app.models.approval_models import (
    ApprovalWorkflow, ApprovalStep, ApprovalRequest, ApprovalDecision,
    ApprovalRole, ApprovalStatus, ApprovalAction
)
from app.schemas.approval_schemas import (
    ApprovalWorkflowCreate, ApprovalRequestCreate, ApprovalDecisionCreate,
    ApprovalStepResponse, ApprovalWorkflowResponse
)
from app.services.notification_service import NotificationService
from app.services.diff_service import DiffService

logger = logging.getLogger(__name__)


class ApprovalWorkflowEngine:
    """Engine for managing approval workflows."""

    def __init__(self, db: Session):
        """Initialize the approval workflow engine."""
        self.db = db
        self.notification_service = NotificationService()
        self.diff_service = DiffService()

    async def create_workflow(self, workflow_data: ApprovalWorkflowCreate, creator_id: str) -> ApprovalWorkflow:
        """Create a new approval workflow."""
        logger.info(f"Creating approval workflow: {workflow_data.name}")

        try:
            # Create workflow
            workflow = ApprovalWorkflow(
                name=workflow_data.name,
                description=workflow_data.description,
                workflow_type=workflow_data.workflow_type,
                configuration=workflow_data.configuration,
                is_active=workflow_data.is_active,
                created_by=creator_id
            )

            self.db.add(workflow)
            self.db.commit()
            self.db.refresh(workflow)

            # Create workflow steps
            for i, step_data in enumerate(workflow_data.steps):
                step = ApprovalStep(
                    workflow_id=workflow.id,
                    step_name=step_data.step_name,
                    step_order=i + 1,
                    approval_role=step_data.approval_role,
                    required_approvers=step_data.required_approvers,
                    timeout_hours=step_data.timeout_hours,
                    is_parallel=step_data.is_parallel,
                    auto_approve_conditions=step_data.auto_approve_conditions,
                    reject_conditions=step_data.reject_conditions,
                    configuration=step_data.configuration
                )

                self.db.add(step)

            self.db.commit()

            # Log workflow creation
            await self._log_workflow_event(
                workflow.id,
                "workflow_created",
                {"creator_id": creator_id, "steps": len(workflow_data.steps)},
                creator_id
            )

            logger.info(f"Approval workflow created: {workflow.id}")
            return workflow

        except Exception as e:
            logger.error(f"Failed to create approval workflow: {e}")
            self.db.rollback()
            raise ApprovalException(f"Failed to create approval workflow: {str(e)}")

    async def initiate_approval_request(
        self,
        request_data: ApprovalRequestCreate,
        initiator_id: str
    ) -> ApprovalRequest:
        """Initiate a new approval request."""
        logger.info(f"Initiating approval request for export: {request_data.export_id}")

        try:
            # Get workflow
            workflow = self.db.query(ApprovalWorkflow).filter(
                ApprovalWorkflow.id == request_data.workflow_id,
                ApprovalWorkflow.is_active == True
            ).first()

            if not workflow:
                raise ApprovalException(f"Active workflow not found: {request_data.workflow_id}")

            # Create approval request
            approval_request = ApprovalRequest(
                workflow_id=workflow.id,
                title=request_data.title,
                description=request_data.description,
                entity_type=request_data.entity_type,
                entity_id=request_data.entity_id,
                priority=request_data.priority,
                requested_by=initiator_id,
                current_step=1,
                status=ApprovalStatus.PENDING,
                context_data=request_data.context_data,
                expires_at=datetime.now(timezone.utc) + workflow.configuration.get('default_timeout_hours', 72)
            )

            self.db.add(approval_request)
            self.db.commit()
            self.db.refresh(approval_request)

            # Get first step
            first_step = self.db.query(ApprovalStep).filter(
                ApprovalStep.workflow_id == workflow.id,
                ApprovalStep.step_order == 1
            ).first()

            if first_step:
                # Initialize step approvers
                await self._initialize_step_approvers(approval_request.id, first_step)

                # Send notifications to approvers
                await self._send_step_notifications(approval_request, first_step, "step_initiated")

            # Log request initiation
            await self._log_request_event(
                approval_request.id,
                "request_initiated",
                {"initiator_id": initiator_id, "workflow_id": workflow.id},
                initiator_id
            )

            logger.info(f"Approval request initiated: {approval_request.id}")
            return approval_request

        except Exception as e:
            logger.error(f"Failed to initiate approval request: {e}")
            self.db.rollback()
            raise ApprovalException(f"Failed to initiate approval request: {str(e)}")

    async def submit_approval_decision(
        self,
        decision_data: ApprovalDecisionCreate,
        approver_id: str
    ) -> ApprovalDecision:
        """Submit an approval decision."""
        logger.info(f"Submitting approval decision for request: {decision_data.approval_request_id}")

        try:
            # Get approval request
            request = self.db.query(ApprovalRequest).filter(
                ApprovalRequest.id == decision_data.approval_request_id
            ).first()

            if not request:
                raise ApprovalException(f"Approval request not found: {decision_data.approval_request_id}")

            # Check if request is still active
            if request.status not in [ApprovalStatus.PENDING, ApprovalStatus.IN_REVIEW]:
                raise ApprovalException(f"Cannot submit decision for request in {request.status} status")

            # Get current step
            current_step = self.db.query(ApprovalStep).filter(
                ApprovalStep.workflow_id == request.workflow_id,
                ApprovalStep.step_order == request.current_step
            ).first()

            if not current_step:
                raise ApprovalException(f"Current step not found: {request.current_step}")

            # Create decision
            decision = ApprovalDecision(
                approval_request_id=request.id,
                step_id=current_step.id,
                approver_id=approver_id,
                action=decision_data.action,
                comments=decision_data.comments,
                decision_data=decision_data.decision_data
            )

            self.db.add(decision)
            self.db.commit()
            self.db.refresh(decision)

            # Update request status
            await self._update_request_status(request, decision)

            # Send notifications
            await self._send_decision_notifications(request, decision)

            # Log decision
            await self._log_request_event(
                request.id,
                "decision_submitted",
                {
                    "approver_id": approver_id,
                    "action": decision_data.action.value,
                    "step": current_step.step_name
                },
                approver_id
            )

            logger.info(f"Approval decision submitted: {decision.id}")
            return decision

        except Exception as e:
            logger.error(f"Failed to submit approval decision: {e}")
            self.db.rollback()
            raise ApprovalException(f"Failed to submit approval decision: {str(e)}")

    async def get_approval_request_status(self, request_id: str) -> Dict[str, Any]:
        """Get detailed status of an approval request."""
        request = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.id == request_id
        ).first()

        if not request:
            raise ApprovalException(f"Approval request not found: {request_id}")

        # Get workflow and steps
        workflow = self.db.query(ApprovalWorkflow).filter(
            ApprovalWorkflow.id == request.workflow_id
        ).first()

        steps = self.db.query(ApprovalStep).filter(
            ApprovalStep.workflow_id == workflow.id
        ).order_by(ApprovalStep.step_order).all()

        # Get decisions for each step
        step_decisions = {}
        for step in steps:
            decisions = self.db.query(ApprovalDecision).filter(
                ApprovalDecision.approval_request_id == request.id,
                ApprovalDecision.step_id == step.id
            ).all()

            step_decisions[step.id] = {
                "step": step,
                "decisions": decisions,
                "is_completed": len(decisions) >= step.required_approvers,
                "is_approved": sum(1 for d in decisions if d.action == ApprovalAction.APPROVE) >= step.required_approvers,
                "is_rejected": any(d.action == ApprovalAction.REJECT for d in decisions)
            }

        return {
            "request": request,
            "workflow": workflow,
            "steps": steps,
            "step_decisions": step_decisions,
            "current_step": next((s for s in steps if s.step_order == request.current_step), None),
            "progress": self._calculate_approval_progress(step_decisions, request.current_step)
        }

    async def _initialize_step_approvers(self, request_id: str, step: ApprovalStep) -> None:
        """Initialize approvers for a workflow step."""
        # Get users with required approval role
        from app.models.user import User
        from app.models.role import Role

        approvers = self.db.query(User).join(Role).filter(
            Role.name == step.approval_role,
            User.is_active == True
        ).all()

        # Create approver assignments
        for approver in approvers:
            from app.models.approval_models import ApproverAssignment
            assignment = ApproverAssignment(
                approval_request_id=request_id,
                step_id=step.id,
                user_id=approver.id,
                status="pending"
            )
            self.db.add(assignment)

        self.db.commit()

    async def _update_request_status(self, request: ApprovalRequest, decision: ApprovalDecision) -> None:
        """Update approval request status based on decision."""
        current_step = self.db.query(ApprovalStep).filter(
            ApprovalStep.id == decision.step_id
        ).first()

        # Get all decisions for current step
        step_decisions = self.db.query(ApprovalDecision).filter(
            ApprovalDecision.approval_request_id == request.id,
            ApprovalDecision.step_id == decision.step_id
        ).all()

        # Check if step is complete
        if len(step_decisions) >= current_step.required_approvers:
            approvals = sum(1 for d in step_decisions if d.action == ApprovalAction.APPROVE)
            rejections = sum(1 for d in step_decisions if d.action == ApprovalAction.REJECT)

            if rejections > 0:
                # Step rejected
                request.status = ApprovalStatus.REJECTED
                request.completed_at = datetime.now(timezone.utc)
            elif approvals >= current_step.required_approvers:
                # Step approved, move to next step
                next_step = self.db.query(ApprovalStep).filter(
                    ApprovalStep.workflow_id == request.workflow_id,
                    ApprovalStep.step_order == request.current_step + 1
                ).first()

                if next_step:
                    # Move to next step
                    request.current_step = next_step.step_order
                    await self._initialize_step_approvers(request.id, next_step)
                    await self._send_step_notifications(request, next_step, "step_initiated")
                else:
                    # Workflow completed
                    request.status = ApprovalStatus.APPROVED
                    request.completed_at = datetime.now(timezone.utc)
                    await self._finalize_approval(request)
            else:
                # Still waiting for more decisions
                request.status = ApprovalStatus.IN_REVIEW

        self.db.commit()

    async def _finalize_approval(self, request: ApprovalRequest) -> None:
        """Finalize an approved request."""
        # Update entity based on approval
        if request.entity_type == "staged_export":
            staged_export = self.db.query(StagedExport).filter(
                StagedExport.id == request.entity_id
            ).first()

            if staged_export:
                from app.models.invoice import ExportStatus
                staged_export.status = ExportStatus.SENT

                # Generate export file
                await self._generate_export_file(staged_export)

                self.db.commit()

        # Send completion notifications
        await self._send_completion_notifications(request)

    async def _generate_export_file(self, staged_export: StagedExport) -> None:
        """Generate export file for approved staged export."""
        from app.services.export_service import ExportService

        export_service = ExportService(db=self.db)

        # Get invoice data
        invoice = self.db.query(Invoice).filter(
            Invoice.id == staged_export.invoice_id
        ).first()

        if invoice:
            from app.models.invoice import InvoiceExtraction
            extraction = self.db.query(InvoiceExtraction).filter(
                InvoiceExtraction.invoice_id == invoice.id
            ).order_by(InvoiceExtraction.created_at.desc()).first()

            if extraction:
                invoice_data = {
                    "header": extraction.header_json,
                    "lines": extraction.lines_json,
                    "metadata": {
                        "invoice_id": str(invoice.id),
                        "export_id": str(staged_export.id),
                        "approved_at": datetime.now(timezone.utc).isoformat()
                    }
                }

                # Generate export file
                if staged_export.format == "csv":
                    content = await export_service.export_to_csv(invoice_data)
                    filename = f"export_{staged_export.id}.csv"
                else:
                    content = await export_service.export_to_json(invoice_data)
                    filename = f"export_{staged_export.id}.json"

                # Save file
                from app.services.storage_service import StorageService
                storage_service = StorageService()
                file_path = f"exports/approved/{filename}"
                await storage_service.upload_file(file_path, content.encode('utf-8'))

                staged_export.file_name = file_path

    async def _send_step_notifications(self, request: ApprovalRequest, step: ApprovalStep, event_type: str) -> None:
        """Send notifications for workflow step events."""
        # Get approvers for this step
        from app.models.approval_models import ApproverAssignment
        from app.models.user import User

        assignments = self.db.query(ApproverAssignment).filter(
            ApproverAssignment.approval_request_id == request.id,
            ApproverAssignment.step_id == step.id
        ).all()

        for assignment in assignments:
            user = self.db.query(User).filter(User.id == assignment.user_id).first()
            if user:
                await self.notification_service.send_approval_notification(
                    user=user,
                    request=request,
                    step=step,
                    event_type=event_type
                )

    async def _send_decision_notifications(self, request: ApprovalRequest, decision: ApprovalDecision) -> None:
        """Send notifications about approval decisions."""
        # Notify request initiator
        from app.models.user import User
        initiator = self.db.query(User).filter(User.id == request.requested_by).first()

        if initiator:
            await self.notification_service.send_decision_notification(
                user=initiator,
                request=request,
                decision=decision
            )

        # Notify other approvers in the same step if parallel
        current_step = self.db.query(ApprovalStep).filter(
            ApprovalStep.id == decision.step_id
        ).first()

        if current_step.is_parallel:
            assignments = self.db.query(ApproverAssignment).filter(
                ApproverAssignment.approval_request_id == request.id,
                ApproverAssignment.step_id == decision.step_id,
                ApproverAssignment.user_id != decision.approver_id
            ).all()

            for assignment in assignments:
                user = self.db.query(User).filter(User.id == assignment.user_id).first()
                if user:
                    await self.notification_service.send_step_decision_notification(
                        user=user,
                        request=request,
                        decision=decision
                    )

    async def _send_completion_notifications(self, request: ApprovalRequest) -> None:
        """Send notifications when approval workflow is completed."""
        from app.models.user import User

        # Notify initiator
        initiator = self.db.query(User).filter(User.id == request.requested_by).first()
        if initiator:
            await self.notification_service.send_approval_completion_notification(
                user=initiator,
                request=request
            )

        # Notify all approvers
        from app.models.approval_models import ApproverAssignment
        assignments = self.db.query(ApproverAssignment).filter(
            ApproverAssignment.approval_request_id == request.id
        ).all()

        for assignment in assignments:
            user = self.db.query(User).filter(User.id == assignment.user_id).first()
            if user:
                await self.notification_service.send_approval_completion_notification(
                    user=user,
                    request=request
                )

    def _calculate_approval_progress(self, step_decisions: Dict, current_step_order: int) -> Dict[str, Any]:
        """Calculate approval progress."""
        total_steps = len(step_decisions)
        completed_steps = sum(1 for step_info in step_decisions.values() if step_info["is_completed"])

        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "current_step": current_step_order,
            "progress_percentage": (completed_steps / total_steps) * 100 if total_steps > 0 else 0,
            "status": "in_progress" if completed_steps < total_steps else "completed"
        }

    async def _log_workflow_event(self, workflow_id: str, event_type: str, event_data: Dict, user_id: str) -> None:
        """Log workflow-related events."""
        from app.models.approval_models import ApprovalAuditLog

        audit_log = ApprovalAuditLog(
            workflow_id=workflow_id,
            event_type=event_type,
            event_data=event_data,
            user_id=user_id
        )

        self.db.add(audit_log)
        self.db.commit()

    async def _log_request_event(self, request_id: str, event_type: str, event_data: Dict, user_id: str) -> None:
        """Log request-related events."""
        from app.models.approval_models import ApprovalAuditLog

        audit_log = ApprovalAuditLog(
            approval_request_id=request_id,
            event_type=event_type,
            event_data=event_data,
            user_id=user_id
        )

        self.db.add(audit_log)
        self.db.commit()

    def get_pending_approvals(self, user_id: str) -> List[ApprovalRequest]:
        """Get pending approval requests for a user."""
        from app.models.approval_models import ApproverAssignment

        assignments = self.db.query(ApproverAssignment).filter(
            ApproverAssignment.user_id == user_id,
            ApproverAssignment.status == "pending"
        ).all()

        request_ids = [a.approval_request_id for a in assignments]

        return self.db.query(ApprovalRequest).filter(
            ApprovalRequest.id.in_(request_ids),
            ApprovalRequest.status.in_([ApprovalStatus.PENDING, ApprovalStatus.IN_REVIEW])
        ).all()

    def get_approval_history(self, user_id: str, limit: int = 50) -> List[ApprovalRequest]:
        """Get approval history for a user."""
        from app.models.approval_models import ApproverAssignment

        assignments = self.db.query(ApproverAssignment).filter(
            ApproverAssignment.user_id == user_id
        ).all()

        request_ids = [a.approval_request_id for a in assignments]

        return self.db.query(ApprovalRequest).filter(
            ApprovalRequest.id.in_(request_ids)
        ).order_by(ApprovalRequest.created_at.desc()).limit(limit).all()


class ApprovalService:
    """Main approval service for managing staged exports and approvals."""

    def __init__(self, db: Session):
        """Initialize the approval service."""
        self.db = db
        self.workflow_engine = ApprovalWorkflowEngine(db)
        self.diff_service = DiffService()

    async def stage_export_for_approval(
        self,
        invoice_id: str,
        export_format: str,
        export_data: Dict[str, Any],
        workflow_id: str,
        initiator_id: str
    ) -> StagedExport:
        """Stage an export for approval."""
        logger.info(f"Staging export for approval: invoice {invoice_id}")

        try:
            # Create staged export
            staged_export = StagedExport(
                invoice_id=uuid.UUID(invoice_id),
                payload_json=export_data,
                format=export_format,
                status="pending_approval",
                destination="approval_workflow"
            )

            self.db.add(staged_export)
            self.db.commit()
            self.db.refresh(staged_export)

            # Create approval request
            approval_request_data = ApprovalRequestCreate(
                workflow_id=uuid.UUID(workflow_id),
                title=f"Export Approval - Invoice {invoice_id}",
                description=f"Review and approve export of invoice {invoice_id} in {export_format} format",
                entity_type="staged_export",
                entity_id=staged_export.id,
                context_data={
                    "invoice_id": invoice_id,
                    "export_format": export_format,
                    "export_data_preview": self._create_export_preview(export_data)
                }
            )

            await self.workflow_engine.initiate_approval_request(
                approval_request_data,
                initiator_id
            )

            logger.info(f"Export staged for approval: {staged_export.id}")
            return staged_export

        except Exception as e:
            logger.error(f"Failed to stage export for approval: {e}")
            self.db.rollback()
            raise ApprovalException(f"Failed to stage export for approval: {str(e)}")

    async def get_approval_diff(self, staged_export_id: str) -> Dict[str, Any]:
        """Get diff comparison for staged export."""
        staged_export = self.db.query(StagedExport).filter(
            StagedExport.id == staged_export_id
        ).first()

        if not staged_export:
            raise ApprovalException(f"Staged export not found: {staged_export_id}")

        # Get original invoice data
        invoice = self.db.query(Invoice).filter(
            Invoice.id == staged_export.invoice_id
        ).first()

        if not invoice:
            raise ApprovalException(f"Invoice not found: {staged_export.invoice_id}")

        from app.models.invoice import InvoiceExtraction
        extraction = self.db.query(InvoiceExtraction).filter(
            InvoiceExtraction.invoice_id == invoice.id
        ).order_by(InvoiceExtraction.created_at.desc()).first()

        if not extraction:
            raise ApprovalException(f"No extraction found for invoice: {invoice.id}")

        original_data = {
            "header": extraction.header_json,
            "lines": extraction.lines_json
        }

        # Generate diff
        return await self.diff_service.generate_diff(
            original_data,
            staged_export.payload_json,
            f"Invoice {invoice.id} Export Diff"
        )

    def _create_export_preview(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a preview of export data for approval context."""
        return {
            "header_fields": len(export_data.get("header", {})),
            "line_items": len(export_data.get("lines", [])),
            "total_amount": export_data.get("header", {}).get("total"),
            "vendor": export_data.get("header", {}).get("vendor_name"),
            "invoice_number": export_data.get("header", {}).get("invoice_no")
        }