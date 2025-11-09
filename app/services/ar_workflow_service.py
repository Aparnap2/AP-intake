"""
AR (Accounts Receivable) workflow service orchestration.

This service provides high-level orchestration for AR invoice processing,
including workflow management, state persistence, and integration
with external systems.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.core.config import settings
from app.core.exceptions import WorkflowException, ValidationException
from app.models.workflow_states import (
    WorkflowStatePersistence, ARWorkflowStateModel,
    InvoiceType, WorkflowStatus, WorkflowStep
)
from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus, CollectionPriority
from app.workflows.enhanced_ar_invoice_processor import EnhancedARInvoiceProcessor
from app.services.storage_service import StorageService
from app.services.metrics_service import metrics_service
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ARWorkflowService:
    """
    High-level service for AR workflow orchestration.

    Provides a clean interface for AR invoice processing, workflow management,
    and integration with external systems like ERP and customer management.
    """

    def __init__(self):
        """Initialize AR workflow service."""
        self.ar_processor = EnhancedARInvoiceProcessor()
        self.storage_service = StorageService()

    async def process_ar_invoice(
        self,
        invoice_id: str,
        file_path: str,
        customer_id: Optional[str] = None,
        priority: str = "normal",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process an AR invoice through the complete workflow.

        Args:
            invoice_id: Unique invoice identifier
            file_path: Path to invoice file
            customer_id: Optional customer identifier
            priority: Processing priority (normal, high, urgent)
            **kwargs: Additional processing parameters

        Returns:
            Processing results with complete workflow state
        """
        try:
            logger.info(f"Starting AR invoice processing service for invoice {invoice_id}")

            # Validate inputs
            await self._validate_processing_inputs(invoice_id, file_path, customer_id)

            # Save initial workflow state
            workflow_id = str(uuid.uuid4())
            await self._save_workflow_state(workflow_id, invoice_id, {
                "status": WorkflowStatus.PROCESSING.value,
                "step": WorkflowStep.INITIALIZED.value,
                "priority": priority,
                "customer_id": customer_id
            })

            # Process invoice through AR workflow
            result = await self.ar_processor.process_ar_invoice(
                invoice_id=invoice_id,
                file_path=file_path,
                customer_id=customer_id,
                **kwargs
            )

            # Update final workflow state
            await self._update_workflow_state(workflow_id, {
                "status": result.get("status"),
                "step": result.get("current_step"),
                "completed_at": datetime.utcnow().isoformat(),
                "total_processing_time_ms": result.get("performance_metrics", {}).get("total_processing_time_ms"),
                "confidence_score": result.get("enhanced_confidence"),
                "working_capital_score": result.get("working_capital_score"),
                "error_count": len(result.get("exceptions", [])),
                "requires_human_review": result.get("requires_human_review", False)
            })

            # Create AR invoice record if processing was successful
            if result.get("status") in [WorkflowStatus.COMPLETED.value, WorkflowStatus.READY.value]:
                await self._create_ar_invoice_record(invoice_id, result)

            # Record service-level metrics
            await self._record_service_metrics(invoice_id, result, priority)

            logger.info(f"AR invoice processing service completed for invoice {invoice_id}: {result['status']}")
            return result

        except Exception as e:
            logger.error(f"AR invoice processing service failed for invoice {invoice_id}: {e}")

            # Update workflow state with error
            if 'workflow_id' in locals():
                await self._update_workflow_state(workflow_id, {
                    "status": WorkflowStatus.FAILED.value,
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                })

            raise WorkflowException(f"AR workflow service failed: {str(e)}")

    async def process_ar_invoice_batch(
        self,
        invoice_batch: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process multiple AR invoices concurrently.

        Args:
            invoice_batch: List of invoice processing parameters
            max_concurrent: Maximum number of concurrent processes

        Returns:
            List of processing results
        """
        logger.info(f"Processing AR invoice batch of {len(invoice_batch)} invoices")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_invoice(invoice_params: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.process_ar_invoice(**invoice_params)
                    return {"success": True, "result": result, "invoice_id": invoice_params.get("invoice_id")}
                except Exception as e:
                    logger.error(f"Failed to process invoice {invoice_params.get('invoice_id')}: {e}")
                    return {"success": False, "error": str(e), "invoice_id": invoice_params.get("invoice_id")}

        # Process all invoices concurrently
        results = await asyncio.gather(
            *[process_single_invoice(params) for params in invoice_batch],
            return_exceptions=True
        )

        # Handle exceptions and return results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing error: {result}")
                processed_results.append({"success": False, "error": str(result)})
            else:
                processed_results.append(result)

        # Log batch processing summary
        successful = len([r for r in processed_results if r.get("success")])
        failed = len(processed_results) - successful
        logger.info(f"AR invoice batch processing completed: {successful} successful, {failed} failed")

        return processed_results

    async def resume_workflow(
        self,
        workflow_id: str,
        human_decision: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume a workflow that requires human intervention.

        Args:
            workflow_id: Workflow identifier
            human_decision: Human decision data
            user_id: Optional user identifier making the decision

        Returns:
            Updated processing results
        """
        try:
            logger.info(f"Resuming AR workflow {workflow_id} with human decision")

            # Validate human decision
            await self._validate_human_decision(human_decision)

            # Update workflow state with human intervention
            await self._update_workflow_state(workflow_id, {
                "status": WorkflowStatus.PROCESSING.value,
                "human_intervention": {
                    "user_id": user_id,
                    "decision": human_decision,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            # Resume workflow in processor
            result = await self.ar_processor.resume_ar_workflow(workflow_id, human_decision)

            # Update final workflow state
            await self._update_workflow_state(workflow_id, {
                "status": result.get("status"),
                "step": result.get("current_step"),
                "completed_at": datetime.utcnow().isoformat(),
                "human_intervention_completed": True
            })

            # Create AR invoice record if processing was successful
            if result.get("status") in [WorkflowStatus.COMPLETED.value, WorkflowStatus.READY.value]:
                await self._create_ar_invoice_record(result.get("invoice_id"), result)

            logger.info(f"AR workflow {workflow_id} resumed successfully: {result['status']}")
            return result

        except Exception as e:
            logger.error(f"Failed to resume AR workflow {workflow_id}: {e}")

            # Update workflow state with error
            await self._update_workflow_state(workflow_id, {
                "status": WorkflowStatus.FAILED.value,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            })

            raise WorkflowException(f"AR workflow resume failed: {str(e)}")

    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Current workflow status and state
        """
        try:
            # Get workflow state from processor
            processor_state = self.ar_processor.get_ar_workflow_state(workflow_id)

            # Get persisted state from database
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WorkflowStatePersistence).where(
                        WorkflowStatePersistence.workflow_id == workflow_id
                    )
                )
                persisted_state = result.scalar_one_or_none()

            if not processor_state and not persisted_state:
                return None

            # Combine states
            combined_state = {
                "workflow_id": workflow_id,
                "processor_state": processor_state,
                "persisted_state": persisted_state.state_data if persisted_state else None,
                "current_status": persisted_state.status if persisted_state else "unknown",
                "current_step": persisted_state.current_step if persisted_state else "unknown",
                "updated_at": persisted_state.updated_at.isoformat() if persisted_state else None,
                "processing_time_ms": persisted_state.total_processing_time_ms if persisted_state else None,
                "confidence_score": persisted_state.confidence_score if persisted_state else None
            }

            return combined_state

        except Exception as e:
            logger.error(f"Failed to get workflow status for {workflow_id}: {e}")
            return None

    async def get_active_workflows(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of active workflows.

        Args:
            limit: Maximum number of workflows to return

        Returns:
            List of active workflow information
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WorkflowStatePersistence)
                    .where(
                        and_(
                            WorkflowStatePersistence.invoice_type == InvoiceType.AR.value,
                            WorkflowStatePersistence.status.in_([
                                WorkflowStatus.PROCESSING.value,
                                WorkflowStatus.HUMAN_REVIEW.value
                            ])
                        )
                    )
                    .order_by(WorkflowStatePersistence.updated_at.desc())
                    .limit(limit)
                )
                workflows = result.scalars().all()

            return [
                {
                    "workflow_id": wf.workflow_id,
                    "invoice_id": wf.invoice_id,
                    "status": wf.status,
                    "current_step": wf.current_step,
                    "created_at": wf.created_at.isoformat(),
                    "updated_at": wf.updated_at.isoformat(),
                    "processing_time_ms": wf.total_processing_time_ms,
                    "confidence_score": wf.confidence_score,
                    "error_count": wf.error_count
                }
                for wf in workflows
            ]

        except Exception as e:
            logger.error(f"Failed to get active workflows: {e}")
            return []

    async def get_workflow_metrics(
        self,
        days: int = 30,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AR workflow performance metrics.

        Args:
            days: Number of days to look back
            customer_id: Optional customer filter

        Returns:
            Workflow performance metrics
        """
        try:
            # Get metrics from processor
            processor_metrics = await self.ar_processor.get_ar_workflow_metrics(days)

            # Get database metrics
            async with AsyncSessionLocal() as session:
                since_date = datetime.utcnow() - timedelta(days=days)

                # Base query
                base_query = select(WorkflowStatePersistence).where(
                    and_(
                        WorkflowStatePersistence.invoice_type == InvoiceType.AR.value,
                        WorkflowStatePersistence.created_at >= since_date
                    )
                )

                # Add customer filter if provided
                if customer_id:
                    # Note: This would require parsing state_data to filter by customer_id
                    # For now, we'll skip customer-specific filtering in this example
                    pass

                result = await session.execute(base_query)
                workflows = result.scalars().all()

            # Calculate metrics from database
            total_workflows = len(workflows)
            completed_workflows = len([w for w in workflows if w.status == WorkflowStatus.COMPLETED.value])
            failed_workflows = len([w for w in workflows if w.status == WorkflowStatus.FAILED.value])
            human_review_workflows = len([w for w in workflows if w.status == WorkflowStatus.HUMAN_REVIEW.value])

            success_rate = (completed_workflows / total_workflows * 100) if total_workflows > 0 else 0

            # Calculate average processing time
            completed_with_time = [w for w in workflows if w.total_processing_time_ms is not None]
            avg_processing_time = (
                sum(w.total_processing_time_ms for w in completed_with_time) / len(completed_with_time)
                if completed_with_time else 0
            )

            # Calculate average confidence score
            with_confidence = [w for w in workflows if w.confidence_score is not None]
            avg_confidence = (
                sum(w.confidence_score for w in with_confidence) / len(with_confidence)
                if with_confidence else 0
            )

            return {
                "period_days": days,
                "total_workflows": total_workflows,
                "completed_workflows": completed_workflows,
                "failed_workflows": failed_workflows,
                "human_review_workflows": human_review_workflows,
                "success_rate": round(success_rate, 2),
                "average_processing_time_ms": round(avg_processing_time, 2),
                "average_confidence_score": round(avg_confidence, 3),
                "generated_at": datetime.utcnow().isoformat(),
                **processor_metrics
            }

        except Exception as e:
            logger.error(f"Failed to get workflow metrics: {e}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }

    async def cancel_workflow(self, workflow_id: str, reason: str) -> bool:
        """
        Cancel an active workflow.

        Args:
            workflow_id: Workflow identifier
            reason: Cancellation reason

        Returns:
            True if cancelled successfully
        """
        try:
            logger.info(f"Cancelling AR workflow {workflow_id}: {reason}")

            # Update workflow state
            await self._update_workflow_state(workflow_id, {
                "status": WorkflowStatus.CANCELLED.value,
                "cancellation_reason": reason,
                "cancelled_at": datetime.utcnow().isoformat()
            })

            # Note: In a real implementation, you might want to
            # signal the running workflow to stop gracefully
            # This could involve setting a cancellation flag in the state

            logger.info(f"AR workflow {workflow_id} cancelled successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel AR workflow {workflow_id}: {e}")
            return False

    async def retry_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Retry a failed workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            New processing results
        """
        try:
            logger.info(f"Retrying AR workflow {workflow_id}")

            # Get current workflow state
            workflow_status = await self.get_workflow_status(workflow_id)
            if not workflow_status:
                raise WorkflowException(f"Workflow {workflow_id} not found")

            # Extract original processing parameters
            # This would require storing original parameters or reconstructing them
            # For now, we'll demonstrate the concept

            # Update workflow state for retry
            await self._update_workflow_state(workflow_id, {
                "status": WorkflowStatus.PROCESSING.value,
                "retry_attempt": workflow_status.get("persisted_state", {}).get("retry_count", 0) + 1,
                "retry_at": datetime.utcnow().isoformat()
            })

            # In a real implementation, you would restart the workflow
            # from the appropriate step based on where it failed

            logger.info(f"AR workflow {workflow_id} retry initiated")
            return {"workflow_id": workflow_id, "status": "retry_initiated"}

        except Exception as e:
            logger.error(f"Failed to retry AR workflow {workflow_id}: {e}")
            raise WorkflowException(f"AR workflow retry failed: {str(e)}")

    # Private helper methods
    async def _validate_processing_inputs(
        self, invoice_id: str, file_path: str, customer_id: Optional[str]
    ) -> None:
        """Validate inputs for AR invoice processing."""
        if not invoice_id:
            raise ValidationException("Invoice ID is required")

        if not file_path:
            raise ValidationException("File path is required")

        # Check if file exists
        if not await self.storage_service.file_exists(file_path):
            raise ValidationException(f"File not found: {file_path}")

        # Check if invoice is already being processed
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(WorkflowStatePersistence).where(
                    and_(
                        WorkflowStatePersistence.invoice_id == invoice_id,
                        WorkflowStatePersistence.invoice_type == InvoiceType.AR.value,
                        WorkflowStatePersistence.status.in_([
                            WorkflowStatus.PROCESSING.value,
                            WorkflowStatus.HUMAN_REVIEW.value
                        ])
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationException(f"Invoice {invoice_id} is already being processed")

    async def _save_workflow_state(self, workflow_id: str, invoice_id: str, state_data: Dict[str, Any]) -> None:
        """Save initial workflow state to database."""
        try:
            async with AsyncSessionLocal() as session:
                workflow_state = WorkflowStatePersistence(
                    workflow_id=workflow_id,
                    invoice_id=invoice_id,
                    invoice_type=InvoiceType.AR.value,
                    current_step=state_data.get("step", WorkflowStep.INITIALIZED.value),
                    status=state_data.get("status", WorkflowStatus.PROCESSING.value),
                    state_data=state_data
                )
                session.add(workflow_state)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")
            # Don't fail the workflow if state saving fails

    async def _update_workflow_state(self, workflow_id: str, updates: Dict[str, Any]) -> None:
        """Update workflow state in database."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WorkflowStatePersistence).where(
                        WorkflowStatePersistence.workflow_id == workflow_id
                    )
                )
                workflow_state = result.scalar_one_or_none()

                if workflow_state:
                    # Update state data
                    current_state = workflow_state.state_data or {}
                    current_state.update(updates)
                    workflow_state.state_data = current_state

                    # Update direct fields
                    if "status" in updates:
                        workflow_state.status = updates["status"]
                    if "step" in updates:
                        workflow_state.current_step = updates["step"]
                    if "total_processing_time_ms" in updates:
                        workflow_state.total_processing_time_ms = updates["total_processing_time_ms"]
                    if "confidence_score" in updates:
                        workflow_state.confidence_score = updates["confidence_score"]
                    if "error" in updates:
                        workflow_state.last_error = updates["error"][:500]  # Limit length
                        workflow_state.error_count = (workflow_state.error_count or 0) + 1

                    workflow_state.updated_at = datetime.utcnow()
                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update workflow state: {e}")
            # Don't fail the workflow if state update fails

    async def _create_ar_invoice_record(self, invoice_id: str, processing_result: Dict[str, Any]) -> None:
        """Create AR invoice record from processing results."""
        try:
            async with AsyncSessionLocal() as session:
                # Check if invoice already exists
                existing = await session.execute(
                    select(ARInvoice).where(ARInvoice.invoice_number == invoice_id)
                )
                if existing.scalar_one_or_none():
                    logger.warning(f"AR invoice {invoice_id} already exists, skipping creation")
                    return

                # Extract data from processing results
                extraction_result = processing_result.get("extraction_result", {})
                header = extraction_result.get("header", {})
                customer_data = processing_result.get("customer_data", {})

                # Create AR invoice record
                ar_invoice = ARInvoice(
                    customer_id=uuid.UUID(customer_data["id"]) if customer_data and "id" in customer_data else None,
                    invoice_number=invoice_id,
                    invoice_date=datetime.fromisoformat(
                        header.get("invoice_date", datetime.utcnow().isoformat()).replace('Z', '+00:00')
                    ),
                    due_date=datetime.fromisoformat(
                        processing_result.get("due_date", datetime.utcnow().isoformat()).replace('Z', '+00:00')
                    ) if processing_result.get("due_date") else datetime.utcnow() + timedelta(days=30),
                    currency=header.get("currency", "USD"),
                    subtotal=Decimal(str(header.get("subtotal", 0))),
                    tax_amount=Decimal(str(header.get("tax_amount", 0))),
                    total_amount=Decimal(str(header.get("total_amount", 0))),
                    outstanding_amount=Decimal(str(header.get("total_amount", 0))),
                    status=PaymentStatus.PENDING,
                    collection_priority=CollectionPriority(processing_result.get("collection_priority", "medium")),
                    early_payment_discount_percent=Decimal(str(processing_result.get("early_payment_discount", 0))) if processing_result.get("early_payment_discount") else None
                )

                session.add(ar_invoice)
                await session.commit()
                logger.info(f"Created AR invoice record for {invoice_id}")

        except Exception as e:
            logger.error(f"Failed to create AR invoice record for {invoice_id}: {e}")
            # Don't fail the workflow if record creation fails

    async def _validate_human_decision(self, human_decision: Dict[str, Any]) -> None:
        """Validate human decision data."""
        if not human_decision:
            raise ValidationException("Human decision data is required")

        action = human_decision.get("action")
        if not action:
            raise ValidationException("Human decision action is required")

        valid_actions = ["approve", "reject", "retry", "escalate", "continue"]
        if action not in valid_actions:
            raise ValidationException(f"Invalid action: {action}. Must be one of {valid_actions}")

    async def _record_service_metrics(
        self, invoice_id: str, result: Dict[str, Any], priority: str
    ) -> None:
        """Record service-level metrics."""
        try:
            await metrics_service.record_ar_workflow_metric(
                invoice_id=invoice_id,
                workflow_result=result,
                priority=priority,
                service_metadata={
                    "service_name": "ARWorkflowService",
                    "processing_mode": "async",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to record service metrics for {invoice_id}: {e}")
            # Don't fail the workflow if metrics recording fails

    # Integration methods for external systems
    async def integrate_with_erp(self, invoice_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integrate processed AR invoice with ERP system.

        Args:
            invoice_id: Invoice identifier
            result: Processing results

        Returns:
            Integration results
        """
        try:
            logger.info(f"Integrating AR invoice {invoice_id} with ERP system")

            # This would integrate with your specific ERP system
            # For now, we'll simulate the integration

            integration_result = {
                "invoice_id": invoice_id,
                "erp_system": "mock_erp",
                "integration_status": "success",
                "erp_invoice_id": f"ERP_{invoice_id}",
                "integrated_at": datetime.utcnow().isoformat(),
                "customer_id": result.get("customer_data", {}).get("id"),
                "total_amount": result.get("extraction_result", {}).get("header", {}).get("total_amount"),
                "due_date": result.get("due_date")
            }

            logger.info(f"ERP integration completed for invoice {invoice_id}")
            return integration_result

        except Exception as e:
            logger.error(f"ERP integration failed for invoice {invoice_id}: {e}")
            return {
                "invoice_id": invoice_id,
                "erp_system": "mock_erp",
                "integration_status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }

    async def send_customer_notifications(self, invoice_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send customer notifications for processed AR invoice.

        Args:
            invoice_id: Invoice identifier
            result: Processing results

        Returns:
            Notification results
        """
        try:
            logger.info(f"Sending customer notifications for AR invoice {invoice_id}")

            communication_result = result.get("communication_result", {})
            if not communication_result.get("sent", False):
                logger.warning(f"No communication was sent for invoice {invoice_id}")
                return {"invoice_id": invoice_id, "notification_status": "not_sent"}

            notification_result = {
                "invoice_id": invoice_id,
                "notification_status": "sent",
                "communication_id": communication_result.get("communication_id"),
                "notification_type": communication_result.get("type"),
                "recipient": communication_result.get("recipient"),
                "channels": communication_result.get("channels", []),
                "sent_at": communication_result.get("timestamp")
            }

            logger.info(f"Customer notifications sent for invoice {invoice_id}")
            return notification_result

        except Exception as e:
            logger.error(f"Failed to send customer notifications for invoice {invoice_id}: {e}")
            return {
                "invoice_id": invoice_id,
                "notification_status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }

    async def get_customer_ar_summary(self, customer_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get AR processing summary for a specific customer.

        Args:
            customer_id: Customer identifier
            days: Number of days to look back

        Returns:
            Customer AR processing summary
        """
        try:
            async with AsyncSessionLocal() as session:
                since_date = datetime.utcnow() - timedelta(days=days)

                # Get AR invoices for customer
                result = await session.execute(
                    select(ARInvoice).where(
                        and_(
                            ARInvoice.customer_id == uuid.UUID(customer_id),
                            ARInvoice.created_at >= since_date
                        )
                    )
                )
                invoices = result.scalars().all()

            # Calculate summary metrics
            total_invoices = len(invoices)
            total_amount = sum(inv.total_amount for inv in invoices)
            outstanding_amount = sum(inv.outstanding_amount for inv in invoices if inv.status != PaymentStatus.PAID)
            overdue_invoices = len([inv for inv in invoices if inv.is_overdue()])

            # Collection efficiency
            paid_invoices = [inv for inv in invoices if inv.status == PaymentStatus.PAID and inv.paid_at]
            avg_days_to_pay = 0
            if paid_invoices:
                days_to_pay = [(inv.paid_at - inv.invoice_date).days for inv in paid_invoices]
                avg_days_to_pay = sum(days_to_pay) / len(days_to_pay)

            return {
                "customer_id": customer_id,
                "period_days": days,
                "total_invoices": total_invoices,
                "total_amount": float(total_amount),
                "outstanding_amount": float(outstanding_amount),
                "overdue_invoices": overdue_invoices,
                "paid_invoices": len(paid_invoices),
                "average_days_to_pay": round(avg_days_to_pay, 2),
                "collection_rate": round((len(paid_invoices) / total_invoices * 100) if total_invoices > 0 else 0, 2),
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get customer AR summary for {customer_id}: {e}")
            return {
                "customer_id": customer_id,
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }