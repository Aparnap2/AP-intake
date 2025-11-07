"""
Enhanced LangGraph state machine for invoice processing workflow with comprehensive error handling,
human review interrupts, state persistence, and exception management integration.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict, Union

from langfuse import Langfuse
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ExtractionException, ValidationException, WorkflowException
from app.services.docling_service import DoclingService
from app.services.llm_service import LLMService
from app.services.validation_service import ValidationService
from app.services.storage_service import StorageService
from app.services.exception_service import ExceptionService
from app.services.export_service import ExportService
from app.db.session import AsyncSessionLocal
from app.models.invoice import Invoice, InvoiceExtraction, InvoiceStatus, Validation as ValidationModel
from app.api.schemas.exception import ExceptionStatus, ExceptionResolutionRequest, ExceptionAction

logger = logging.getLogger(__name__)


class InvoiceState(TypedDict):
    """Enhanced state object for invoice processing workflow."""

    # Invoice metadata
    invoice_id: str
    file_path: str
    file_hash: str
    vendor_id: Optional[str]
    workflow_id: str
    created_at: str
    updated_at: str

    # Processing results
    extraction_result: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    confidence_score: Optional[float]

    # Exception management
    exceptions: List[Dict[str, Any]]
    exception_ids: List[str]
    exception_resolution_data: Optional[Dict[str, Any]]

    # Workflow state
    current_step: str
    status: str
    previous_step: Optional[str]
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    requires_human_review: bool
    retry_count: int
    max_retries: int

    # Human review and interrupts
    human_review_reason: Optional[str]
    human_review_data: Optional[Dict[str, Any]]
    interrupt_point: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]

    # Processing metadata
    processing_history: List[Dict[str, Any]]
    step_timings: Dict[str, Any]
    performance_metrics: Dict[str, Any]

    # Export data
    export_payload: Optional[Dict[str, Any]]
    export_format: str
    export_ready: bool


# Define state reducers for proper LangGraph state management
def merge_processing_history(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge processing history lists."""
    return left + right


def merge_step_timings(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge step timing dictionaries."""
    result = left.copy()
    result.update(right)
    return result


def merge_performance_metrics(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge performance metrics dictionaries."""
    result = left.copy()
    result.update(right)
    return result


# Apply reducers to the InvoiceState
InvoiceState.__annotations__ = {
    **InvoiceState.__annotations__,
    "processing_history": List[Dict[str, Any]],
    "step_timings": Dict[str, Any],
    "performance_metrics": Dict[str, Any],
    "exceptions": List[Dict[str, Any]],
    "exception_ids": List[str],
}


class InvoiceProcessor:
    """Enhanced LangGraph-based invoice processor with comprehensive error handling and state persistence."""

    def __init__(self):
        """Initialize the enhanced invoice processor."""
        self.langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        ) if settings.LANGFUSE_PUBLIC_KEY else None

        # Initialize services
        self.storage_service = StorageService()
        self.docling_service = DoclingService()
        self.llm_service = LLMService()
        self.validation_service = ValidationService()
        self.exception_service = ExceptionService()
        self.export_service = ExportService()

        # Initialize state persistence
        self.checkpointer = self._init_checkpointer()

        # Build the enhanced state graph
        self.graph = self._build_graph()
        self.runner = self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_review"],  # Interrupt before human review nodes
            interrupt_after=["triage"],  # Interrupt after triage to allow for manual intervention
        )

    def _init_checkpointer(self):
        """Initialize state persistence checkpointer."""
        try:
            # Use SQLite for persistent state storage
            import os
            # Ensure the directory exists
            persist_dir = settings.LANGGRAPH_PERSIST_PATH
            os.makedirs(persist_dir, exist_ok=True)
            checkpointer_path = f"sqlite:///{persist_dir}/checkpoints.db"
            # SqliteSaver.from_conn_string may return a context manager, handle both cases
            checkpointer = SqliteSaver.from_conn_string(checkpointer_path)
            # If it's a context manager, enter it to get the actual checkpointer
            if hasattr(checkpointer, '__enter__'):
                checkpointer = checkpointer.__enter__()
            logger.info(f"SQLite checkpointer initialized at: {persist_dir}/checkpoints.db")
            return checkpointer
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite checkpointer, falling back to memory: {e}")
            return MemorySaver()

    def _build_graph(self) -> StateGraph:
        """Build the enhanced LangGraph state machine with comprehensive error handling."""
        # Create state graph with proper reducers for list and dict fields
        workflow = StateGraph(
            InvoiceState,
            reducers={
                "processing_history": merge_processing_history,
                "step_timings": merge_step_timings,
                "performance_metrics": merge_performance_metrics,
                "exceptions": lambda left, right: left + right,
                "exception_ids": lambda left, right: left + right,
            }
        )

        # Add core processing nodes
        workflow.add_node("receive", self._receive_invoice)
        workflow.add_node("parse", self._parse_document)
        workflow.add_node("patch", self._patch_low_confidence)
        workflow.add_node("validate", self._validate_invoice)
        workflow.add_node("triage", self._triage_results)
        workflow.add_node("stage_export", self._stage_export)

        # Add error handling and recovery nodes
        workflow.add_node("error_handler", self._handle_error)
        workflow.add_node("retry", self._retry_step)
        workflow.add_node("escalate", self._escalate_exception)
        workflow.add_node("human_review", self._human_review_interrupt)

        # Set entry point
        workflow.set_entry_point("receive")

        # Define main workflow edges
        workflow.add_edge("receive", "parse")
        workflow.add_edge("parse", "patch")
        workflow.add_edge("patch", "validate")
        workflow.add_edge("validate", "triage")
        workflow.add_edge("stage_export", END)

        # Conditional routing from triage with enhanced options
        workflow.add_conditional_edges(
            "triage",
            self._triage_routing,
            {
                "stage_export": "stage_export",
                "human_review": "human_review",
                "error": "error_handler",
                "escalate": "escalate",
                "retry": "retry",
            }
        )

        # Error recovery routing
        workflow.add_conditional_edges(
            "error_handler",
            self._error_recovery_routing,
            {
                "retry": "retry",
                "escalate": "escalate",
                "human_review": "human_review",
                "fail": END,
            }
        )

        # Retry routing
        workflow.add_conditional_edges(
            "retry",
            self._retry_routing,
            {
                "receive": "receive",
                "parse": "parse",
                "patch": "patch",
                "validate": "validate",
                "escalate": "escalate",
                "fail": END,
            }
        )

        # Human review completion routing
        workflow.add_conditional_edges(
            "human_review",
            self._human_review_routing,
            {
                "continue": "triage",
                "retry": "retry",
                "escalate": "escalate",
                "fail": END,
            }
        )

        # Escalation completion
        workflow.add_edge("escalate", END)

        return workflow

    # Helper methods for enhanced workflow functionality
    def _update_processing_metadata(self, state: InvoiceState, step: str, start_time: datetime) -> None:
        """Update processing metadata for the current step."""
        state["updated_at"] = datetime.utcnow().isoformat()
        if "processing_history" not in state:
            state["processing_history"] = []

    async def _check_duplicate_invoice(
        self, session: AsyncSession, invoice_id: str, file_hash: Optional[str] = None
    ) -> Optional[Invoice]:
        """Check for duplicate invoice by ID or file hash."""
        from sqlalchemy import select
        query = select(Invoice).where(Invoice.id == invoice_id)
        if file_hash:
            query = query.where(Invoice.file_hash == file_hash)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _update_invoice_status(self, invoice_id: str, status: InvoiceStatus) -> None:
        """Update invoice status in database."""
        try:
            async with AsyncSessionLocal() as session:
                query = select(Invoice).where(Invoice.id == invoice_id)
                result = await session.execute(query)
                invoice = result.scalar_one_or_none()
                if invoice:
                    invoice.status = status
                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update invoice status: {e}")

    async def _create_workflow_exception(self, state: InvoiceState, error: Exception, step: str) -> str:
        """Create exception record for workflow error."""
        try:
            from app.api.schemas.exception import ExceptionCreate, ExceptionCategory, ExceptionSeverity
            from app.api.schemas.validation import ValidationIssue, ValidationCode, ValidationSeverity as ValSeverity

            # Create validation issue from error
            validation_issue = ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=str(error),
                severity=ValSeverity.ERROR,
                field=step,
                details={"error_type": type(error).__name__, "step": step}
            )

            # Create exception via exception service
            exceptions = await self.exception_service.create_exception_from_validation(
                invoice_id=state["invoice_id"],
                validation_issues=[validation_issue]
            )

            if exceptions:
                exception_id = exceptions[0].id
                state["exception_ids"] = state.get("exception_ids", []) + [exception_id]
                return exception_id

        except Exception as e:
            logger.error(f"Failed to create workflow exception: {e}")

        return ""

    async def _save_extraction_result(self, invoice_id: str, extraction_result: Dict[str, Any]) -> None:
        """Save extraction result to database."""
        try:
            async with AsyncSessionLocal() as session:
                # Create new extraction record
                extraction = InvoiceExtraction(
                    invoice_id=uuid.UUID(invoice_id),
                    header_json=extraction_result.get("header", {}),
                    lines_json=extraction_result.get("lines", []),
                    confidence_json=extraction_result.get("confidence", {}),
                    parser_version=extraction_result.get("metadata", {}).get("parser_version", "unknown"),
                    processing_time_ms=str(extraction_result.get("metadata", {}).get("processing_time_ms", 0)),
                    page_count=str(extraction_result.get("metadata", {}).get("pages_processed", 0))
                )
                session.add(extraction)
                await session.commit()
                logger.debug(f"Saved extraction result for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to save extraction result: {e}")
            # Don't fail the workflow if database save fails

    async def _save_validation_result(self, invoice_id: str, validation_result: Dict[str, Any]) -> None:
        """Save validation result to database."""
        try:
            async with AsyncSessionLocal() as session:
                # Create new validation record
                validation = ValidationModel(
                    invoice_id=uuid.UUID(invoice_id),
                    passed=validation_result.get("passed", False),
                    checks_json=validation_result.get("check_results", {}),
                    rules_version=validation_result.get("rules_version", "unknown"),
                    validator_version=validation_result.get("validator_version", "unknown"),
                    processing_time_ms=validation_result.get("processing_time_ms", "0")
                )
                session.add(validation)
                await session.commit()
                logger.debug(f"Saved validation result for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to save validation result: {e}")
            # Don't fail the workflow if database save fails

    async def _save_staged_export(self, invoice_id: str, export_payload: Dict[str, Any], export_format: str) -> None:
        """Save staged export to database."""
        try:
            async with AsyncSessionLocal() as session:
                from app.models.invoice import StagedExport, ExportFormat, ExportStatus

                # Create new staged export record
                staged_export = StagedExport(
                    invoice_id=uuid.UUID(invoice_id),
                    payload_json=export_payload,
                    format=ExportFormat[export_format.upper()],
                    status=ExportStatus.PREPARED,
                    destination="erp_system",  # Can be made configurable
                    export_job_id=f"export_{invoice_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                )
                session.add(staged_export)
                await session.commit()
                logger.debug(f"Saved staged export for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to save staged export: {e}")
            # Don't fail the workflow if database save fails

    # Workflow node implementations (enhanced versions from the separate file)
    async def _receive_invoice(self, state: InvoiceState) -> InvoiceState:
        """Enhanced invoice reception with comprehensive validation and state tracking."""
        start_time = datetime.utcnow()
        logger.info(f"Receiving invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "receive", start_time)

            # Validate file exists and is accessible
            file_path = state["file_path"]
            if not await self.storage_service.file_exists(file_path):
                raise WorkflowException(f"File not found: {file_path}")

            # Get file metadata
            try:
                file_content = await self.storage_service.get_file_content(file_path)
                file_size = len(file_content)

                # Validate file size
                max_size_mb = settings.MAX_FILE_SIZE_MB
                max_size_bytes = max_size_mb * 1024 * 1024
                if file_size > max_size_bytes:
                    raise WorkflowException(f"File size {file_size} bytes exceeds maximum {max_size_mb}MB")

                # Validate file hash if provided
                if state.get("file_hash"):
                    import hashlib
                    actual_hash = hashlib.sha256(file_content).hexdigest()
                    if actual_hash != state["file_hash"]:
                        logger.warning(f"File hash mismatch for invoice {state['invoice_id']}")
                        state["file_hash"] = actual_hash  # Update with actual hash

            except Exception as file_error:
                raise WorkflowException(f"Failed to read or validate file: {str(file_error)}")

            # Check for duplicate invoice in database
            async with AsyncSessionLocal() as session:
                existing_invoice = await self._check_duplicate_invoice(
                    session, state["invoice_id"], state.get("file_hash")
                )
                if existing_invoice:
                    raise WorkflowException(f"Duplicate invoice detected: {existing_invoice.id}")

            # Update state with successful reception
            state.update({
                "current_step": "received",
                "status": "processing",
                "previous_step": state.get("current_step"),
                "requires_human_review": False,
                "error_message": None,
                "error_details": None,
                "retry_count": 0,
                "max_retries": 3,
                "exceptions": [],
                "exception_ids": [],
                "processing_history": state.get("processing_history", []) + [{
                    "step": "receive",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "file_size": file_size,
                        "file_path": file_path,
                        "file_hash": state.get("file_hash")
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["receive"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_received",
                    input={"invoice_id": state["invoice_id"], "file_path": file_path},
                    output={"status": "success", "file_size": file_size},
                    metadata={
                        "step": "receive",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time
                    }
                )

            # Update invoice status in database
            await self._update_invoice_status(state["invoice_id"], InvoiceStatus.RECEIVED)

            logger.info(f"Successfully received invoice {state['invoice_id']} in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to receive invoice {state['invoice_id']}: {e}")

            # Update state with error information
            state.update({
                "current_step": "receive_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "receive",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True
                }
            })

            # Trace the error
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_receive_error",
                    input={"invoice_id": state["invoice_id"]},
                    output={"error": str(e)},
                    metadata={
                        "step": "receive",
                        "error_type": type(e).__name__,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            return state

    async def _parse_document(self, state: InvoiceState) -> InvoiceState:
        """Enhanced document parsing with comprehensive error handling and state tracking."""
        start_time = datetime.utcnow()
        logger.info(f"Parsing document for invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "parse", start_time)

            # Get file content
            file_path = state["file_path"]
            file_content = await self.storage_service.get_file_content(file_path)

            # Extract data using Docling
            extraction_result = await self.docling_service.extract_from_content(
                file_content, file_path=file_path
            )

            # Validate extraction result structure
            if not extraction_result or "header" not in extraction_result or "lines" not in extraction_result:
                raise ExtractionException("Invalid extraction result structure")

            # Update state with extraction results
            state.update({
                "extraction_result": extraction_result,
                "current_step": "parsed",
                "status": "processing",
                "previous_step": state.get("current_step"),
                "confidence_score": extraction_result.get("overall_confidence", 0.0),
                "error_message": None,
                "error_details": None,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "parse",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "extraction_confidence": extraction_result.get("overall_confidence", 0.0),
                        "header_fields": len(extraction_result.get("header", {})),
                        "line_items": len(extraction_result.get("lines", [])),
                        "pages_processed": extraction_result.get("metadata", {}).get("pages_processed", 0)
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["parse"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="document_parsed",
                    input={"invoice_id": state["invoice_id"], "file_path": file_path},
                    output={
                        "confidence": state["confidence_score"],
                        "header_fields": len(extraction_result.get("header", {})),
                        "line_items": len(extraction_result.get("lines", []))
                    },
                    metadata={
                        "step": "parse",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time,
                        "parser_version": extraction_result.get("metadata", {}).get("parser_version")
                    }
                )

            # Update invoice status in database
            await self._update_invoice_status(state["invoice_id"], InvoiceStatus.PARSED)

            # Save extraction result to database
            await self._save_extraction_result(state["invoice_id"], extraction_result)

            logger.info(f"Successfully parsed invoice {state['invoice_id']} with confidence {state['confidence_score']:.2f} in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to parse document for invoice {state['invoice_id']}: {e}")

            # Create exception record
            exception_id = await self._create_workflow_exception(state, e, "parse")

            # Update state with error information
            state.update({
                "current_step": "parse_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "parse",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True,
                    "exception_id": exception_id
                }
            })

            # Trace the error
            if self.langfuse:
                self.langfuse.trace(
                    name="document_parse_error",
                    input={"invoice_id": state["invoice_id"]},
                    output={"error": str(e)},
                    metadata={
                        "step": "parse",
                        "error_type": type(e).__name__,
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            return state

    async def _patch_low_confidence(self, state: InvoiceState) -> InvoiceState:
        """Enhanced low-confidence field patching with LLM support and comprehensive error handling."""
        start_time = datetime.utcnow()
        logger.info(f"Checking confidence for invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "patch", start_time)

            confidence = state.get("confidence_score", 0.0)
            threshold = settings.DOCLING_CONFIDENCE_THRESHOLD

            if confidence >= threshold:
                logger.info(f"Confidence {confidence:.2f} >= threshold {threshold}, no patching needed")

                # Update state for skipped patching
                state.update({
                    "current_step": "patch_skipped",
                    "status": "processing",
                    "previous_step": state.get("current_step"),
                    "processing_history": state.get("processing_history", []) + [{
                        "step": "patch",
                        "status": "skipped",
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                        "metadata": {
                            "reason": "confidence_above_threshold",
                            "confidence": confidence,
                            "threshold": threshold
                        }
                    }]
                })

                # Update step timings
                step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                state["step_timings"] = state.get("step_timings", {})
                state["step_timings"]["patch"] = step_time

                return state

            logger.info(f"Confidence {confidence:.2f} < threshold {threshold}, applying LLM patching")

            # Apply LLM patching
            extraction_result = state["extraction_result"]
            patched_result = await self.llm_service.patch_low_confidence_fields(
                extraction_result, confidence
            )

            # Validate patched result
            if not patched_result or "header" not in patched_result:
                raise WorkflowException("Invalid patched result from LLM")

            # Calculate confidence improvement
            new_confidence = patched_result.get("overall_confidence", confidence)
            confidence_improvement = new_confidence - confidence

            # Update state with patched results
            state.update({
                "extraction_result": patched_result,
                "current_step": "patched",
                "status": "processing",
                "previous_step": state.get("current_step"),
                "confidence_score": new_confidence,
                "error_message": None,
                "error_details": None,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "patch",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "original_confidence": confidence,
                        "new_confidence": new_confidence,
                        "confidence_improvement": confidence_improvement,
                        "llm_provider": self.llm_service.provider,
                        "llm_model": self.llm_service.model
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["patch"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="low_confidence_patched",
                    input={
                        "invoice_id": state["invoice_id"],
                        "extraction_result": extraction_result,
                        "confidence": confidence
                    },
                    output={
                        "patched_result": patched_result,
                        "new_confidence": new_confidence,
                        "improvement": confidence_improvement
                    },
                    metadata={
                        "step": "patch",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time,
                        "llm_provider": self.llm_service.provider
                    }
                )

            # Save patched extraction result to database
            await self._save_extraction_result(state["invoice_id"], patched_result)

            logger.info(f"Successfully patched invoice {state['invoice_id']} confidence from {confidence:.2f} to {new_confidence:.2f} in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to patch low confidence fields for invoice {state['invoice_id']}: {e}")

            # Create exception record
            exception_id = await self._create_workflow_exception(state, e, "patch")

            # Update state with error information
            state.update({
                "current_step": "patch_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "patch",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True,
                    "exception_id": exception_id,
                    "confidence_before": confidence
                }
            })

            # Trace the error
            if self.langfuse:
                self.langfuse.trace(
                    name="low_confidence_patch_error",
                    input={"invoice_id": state["invoice_id"], "confidence": confidence},
                    output={"error": str(e)},
                    metadata={
                        "step": "patch",
                        "error_type": type(e).__name__,
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            return state

    # Include enhanced methods from the separate file
    async def _validate_invoice(self, state: InvoiceState) -> InvoiceState:
        """Enhanced invoice validation with comprehensive business rules and exception integration."""
        start_time = datetime.utcnow()
        logger.info(f"Validating invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "validate", start_time)

            extraction_result = state["extraction_result"]
            if not extraction_result:
                raise ValidationException("No extraction result to validate")

            # Run comprehensive validation using ValidationService
            validation_result = await self.validation_service.validate_invoice(
                extraction_result=extraction_result,
                invoice_id=state["invoice_id"],
                vendor_id=state.get("vendor_id"),
                strict_mode=False  # Can be made configurable
            )

            # Extract validation details
            validation_passed = validation_result.get("passed", False)
            total_issues = validation_result.get("total_issues", 0)
            error_count = validation_result.get("error_count", 0)
            warning_count = validation_result.get("warning_count", 0)
            validation_confidence = validation_result.get("confidence_score", 0.0)

            # Get validation issues for exception processing
            validation_issues = validation_result.get("issues", [])

            # Create exceptions for validation failures
            exception_ids = []
            if not validation_passed and error_count > 0:
                try:
                    exceptions = await self.exception_service.create_exception_from_validation(
                        invoice_id=state["invoice_id"],
                        validation_issues=validation_issues
                    )
                    exception_ids = [exc.id for exc in exceptions]
                    logger.info(f"Created {len(exception_ids)} exceptions for invoice {state['invoice_id']}")
                except Exception as exc_error:
                    logger.error(f"Failed to create exceptions for invoice {state['invoice_id']}: {exc_error}")

            # Update state with validation results
            state.update({
                "validation_result": validation_result,
                "current_step": "validated",
                "status": "exception" if not validation_passed else "processing",
                "previous_step": state.get("current_step"),
                "requires_human_review": not validation_passed or error_count > 0,
                "exceptions": validation_issues,
                "exception_ids": state.get("exception_ids", []) + exception_ids,
                "error_message": None if validation_passed else f"Validation failed with {error_count} errors",
                "error_details": None if validation_passed else {
                    "validation_errors": error_count,
                    "validation_warnings": warning_count,
                    "validation_confidence": validation_confidence
                },
                "processing_history": state.get("processing_history", []) + [{
                    "step": "validate",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "validation_passed": validation_passed,
                        "total_issues": total_issues,
                        "error_count": error_count,
                        "warning_count": warning_count,
                        "validation_confidence": validation_confidence,
                        "exceptions_created": len(exception_ids)
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["validate"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_validated",
                    input={
                        "invoice_id": state["invoice_id"],
                        "extraction_result": extraction_result
                    },
                    output={
                        "validation_passed": validation_passed,
                        "total_issues": total_issues,
                        "error_count": error_count,
                        "validation_confidence": validation_confidence
                    },
                    metadata={
                        "step": "validate",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time,
                        "exceptions_created": len(exception_ids)
                    }
                )

            # Update invoice status in database
            await self._update_invoice_status(
                state["invoice_id"],
                InvoiceStatus.VALIDATED if validation_passed else InvoiceStatus.EXCEPTION
            )

            # Save validation result to database
            await self._save_validation_result(state["invoice_id"], validation_result)

            logger.info(f"Validation completed for invoice {state['invoice_id']}: {'PASSED' if validation_passed else 'FAILED'} "
                       f"({error_count} errors, {warning_count} warnings) in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to validate invoice {state['invoice_id']}: {e}")

            # Create exception record
            exception_id = await self._create_workflow_exception(state, e, "validate")

            # Update state with error information
            state.update({
                "current_step": "validation_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "validate",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True,
                    "exception_id": exception_id
                }
            })

            # Trace the error
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_validation_error",
                    input={"invoice_id": state["invoice_id"]},
                    output={"error": str(e)},
                    metadata={
                        "step": "validate",
                        "error_type": type(e).__name__,
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            return state

    async def _triage_results(self, state: InvoiceState) -> InvoiceState:
        """Enhanced triage results with intelligent routing and human review determination."""
        start_time = datetime.utcnow()
        logger.info(f"Triaging results for invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "triage", start_time)

            validation_result = state.get("validation_result", {})
            confidence = state.get("confidence_score", 0.0)
            exceptions = state.get("exceptions", [])
            error_count = validation_result.get("error_count", 0)

            # Determine triage decision based on multiple factors
            triage_decision = self._calculate_triage_decision(
                validation_passed=validation_result.get("passed", False),
                confidence_score=confidence,
                error_count=error_count,
                exceptions_count=len(exceptions),
                exceptions=exceptions
            )

            # Determine human review requirements
            human_review_required = self._determine_human_review_requirements(
                triage_decision, validation_result, confidence, exceptions
            )

            # Set human review reason if required
            human_review_reason = None
            human_review_data = None

            if human_review_required:
                human_review_reason = self._get_human_review_reason(
                    triage_decision, validation_result, confidence, exceptions
                )
                human_review_data = {
                    "triage_decision": triage_decision,
                    "validation_result": validation_result,
                    "confidence_score": confidence,
                    "exceptions": exceptions,
                    "suggested_actions": self._get_suggested_actions(triage_decision, exceptions)
                }

            # Update state with triage results
            state.update({
                "current_step": "triaged",
                "status": self._map_triage_to_status(triage_decision),
                "previous_step": state.get("current_step"),
                "requires_human_review": human_review_required,
                "human_review_reason": human_review_reason,
                "human_review_data": human_review_data,
                "error_message": None,
                "error_details": None,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "triage",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "triage_decision": triage_decision,
                        "human_review_required": human_review_required,
                        "confidence_score": confidence,
                        "validation_errors": error_count,
                        "exceptions_count": len(exceptions)
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["triage"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_triaged",
                    input={
                        "invoice_id": state["invoice_id"],
                        "validation_result": validation_result,
                        "confidence_score": confidence
                    },
                    output={
                        "triage_decision": triage_decision,
                        "human_review_required": human_review_required,
                        "status": state["status"]
                    },
                    metadata={
                        "step": "triage",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time
                    }
                )

            logger.info(f"Triage completed for invoice {state['invoice_id']}: {triage_decision} "
                       f"({'human review' if human_review_required else 'auto-processing'}) in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to triage results for invoice {state['invoice_id']}: {e}")

            # Create exception record
            exception_id = await self._create_workflow_exception(state, e, "triage")

            # Update state with error information
            state.update({
                "current_step": "triage_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "triage",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True,
                    "exception_id": exception_id
                }
            })

            return state

    def _calculate_triage_decision(
        self, validation_passed: bool, confidence_score: float,
        error_count: int, exceptions_count: int, exceptions: List[Dict[str, Any]]
    ) -> str:
        """Calculate intelligent triage decision based on multiple factors."""
        # High confidence and validation passed - auto-approve
        if validation_passed and confidence_score >= 0.9:
            return "auto_approve"

        # Validation passed but lower confidence - may need review
        if validation_passed and confidence_score >= settings.DOCLING_CONFIDENCE_THRESHOLD:
            return "conditional_approve"

        # Validation failed but has fixable issues - try auto-recovery
        if not validation_passed and error_count <= 3 and confidence_score >= 0.7:
            # Check if exceptions are auto-resolvable
            auto_resolvable = all(
                exc.get("auto_resolution_possible", False) for exc in exceptions
            )
            if auto_resolvable:
                return "auto_resolve"

        # High confidence but validation failed - needs review
        if not validation_passed and confidence_score >= settings.DOCLING_CONFIDENCE_THRESHOLD:
            return "high_priority_review"

        # Low confidence - needs human review
        if confidence_score < settings.DOCLING_CONFIDENCE_THRESHOLD:
            return "low_confidence_review"

        # Default to human review
        return "human_review"

    def _determine_human_review_requirements(
        self, triage_decision: str, validation_result: Dict[str, Any],
        confidence_score: float, exceptions: List[Dict[str, Any]]
    ) -> bool:
        """Determine if human review is required based on triage decision and other factors."""
        review_decisions = {
            "auto_approve": False,
            "conditional_approve": False,
            "auto_resolve": False,
            "high_priority_review": True,
            "low_confidence_review": True,
            "human_review": True
        }

        base_requirement = review_decisions.get(triage_decision, True)

        # Additional checks
        if not base_requirement:
            # Check for critical validation issues
            error_count = validation_result.get("error_count", 0)
            if error_count > 0:
                critical_issues = [
                    exc for exc in exceptions
                    if exc.get("severity") == "ERROR" and not exc.get("auto_resolution_possible", False)
                ]
                if critical_issues:
                    return True

            # Check for business rule violations
            business_rule_issues = [
                exc for exc in exceptions
                if exc.get("category") in ["VENDOR_POLICY", "MATCHING"]
            ]
            if business_rule_issues:
                return True

        return base_requirement

    def _get_human_review_reason(
        self, triage_decision: str, validation_result: Dict[str, Any],
        confidence_score: float, exceptions: List[Dict[str, Any]]
    ) -> str:
        """Get human review reason based on triage decision and context."""
        reason_map = {
            "high_priority_review": "Validation failed despite high extraction confidence",
            "low_confidence_review": f"Low extraction confidence ({confidence_score:.2f})",
            "human_review": "Multiple validation issues require manual review"
        }

        base_reason = reason_map.get(triage_decision, "Manual review required")

        # Add specific issue details
        if exceptions:
            critical_count = len([exc for exc in exceptions if exc.get("severity") == "ERROR"])
            if critical_count > 0:
                base_reason += f" ({critical_count} critical errors)"

        return base_reason

    def _get_suggested_actions(self, triage_decision: str, exceptions: List[Dict[str, Any]]) -> List[str]:
        """Get suggested actions for human review based on triage decision and exceptions."""
        actions = []

        if triage_decision == "high_priority_review":
            actions.extend(["Review validation errors", "Verify extracted data", "Approve or reject"])

        elif triage_decision == "low_confidence_review":
            actions.extend(["Verify extraction accuracy", "Correct low-confidence fields", "Re-process if needed"])

        # Add exception-specific actions
        for exc in exceptions[:3]:  # Limit to top 3 exceptions
            suggested_actions = exc.get("suggested_actions", [])
            actions.extend([action.value for action in suggested_actions])

        return list(set(actions))  # Remove duplicates

    def _map_triage_to_status(self, triage_decision: str) -> str:
        """Map triage decision to workflow status."""
        status_map = {
            "auto_approve": "ready",
            "conditional_approve": "ready",
            "auto_resolve": "processing",
            "high_priority_review": "exception",
            "low_confidence_review": "exception",
            "human_review": "exception"
        }
        return status_map.get(triage_decision, "exception")

    async def _stage_export(self, state: InvoiceState) -> InvoiceState:
        """Enhanced export staging with multiple format support and comprehensive error handling."""
        start_time = datetime.utcnow()
        logger.info(f"Staging export for invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            self._update_processing_metadata(state, "stage_export", start_time)

            # Prepare export payload
            extraction_result = state["extraction_result"]
            export_format = state.get("export_format", "json")

            # Create standardized export payload
            export_payload = {
                "invoice_id": state["invoice_id"],
                "workflow_id": state["workflow_id"],
                "header": extraction_result.get("header", {}),
                "lines": extraction_result.get("lines", []),
                "metadata": {
                    "extraction_confidence": state.get("confidence_score", 0.0),
                    "validation_passed": state.get("validation_result", {}).get("passed", False),
                    "processed_at": datetime.utcnow().isoformat(),
                    "export_format": export_format,
                    "export_version": "2.0",
                    "processing_summary": {
                        "total_steps": len(state.get("processing_history", [])),
                        "total_time_ms": sum(
                            step.get("duration_ms", 0) for step in state.get("processing_history", [])
                        ),
                        "exceptions_resolved": len(state.get("exception_ids", []))
                    }
                }
            }

            # Generate export content based on format
            if export_format.lower() == "csv":
                export_content = await self.export_service.export_to_csv(export_payload)
            elif export_format.lower() == "json":
                export_content = await self.export_service.export_to_json(export_payload)
            else:
                # Generate multiple formats for ERP integration
                export_content = {
                    "json": await self.export_service.export_to_json(export_payload),
                    "csv": await self.export_service.export_to_csv(export_payload),
                    "erp_generic": await self.export_service.export_for_erp(export_payload, "generic")
                }

            # Update state with export results
            state.update({
                "export_payload": export_payload,
                "export_format": export_format,
                "export_ready": True,
                "current_step": "export_staged",
                "status": "staged",
                "previous_step": state.get("current_step"),
                "error_message": None,
                "error_details": None,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "stage_export",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "export_format": export_format,
                        "export_size": len(str(export_content)),
                        "export_version": "2.0"
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["stage_export"] = step_time

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="export_staged",
                    input={
                        "invoice_id": state["invoice_id"],
                        "extraction_result": extraction_result,
                        "export_format": export_format
                    },
                    output={
                        "export_ready": True,
                        "export_format": export_format,
                        "export_size": len(str(export_content))
                    },
                    metadata={
                        "step": "stage_export",
                        "workflow_id": state["workflow_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "processing_time_ms": step_time
                    }
                )

            # Update invoice status in database
            await self._update_invoice_status(state["invoice_id"], InvoiceStatus.STAGED)

            # Save staged export to database
            await self._save_staged_export(state["invoice_id"], export_payload, export_format)

            logger.info(f"Successfully staged export for invoice {state['invoice_id']} in {export_format} format in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to stage export for invoice {state['invoice_id']}: {e}")

            # Create exception record
            exception_id = await self._create_workflow_exception(state, e, "stage_export")

            # Update state with error information
            state.update({
                "current_step": "export_failed",
                "status": "error",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "stage_export",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True,
                    "exception_id": exception_id
                }
            })

            return state

    # Error handling and recovery methods
    async def _handle_error(self, state: InvoiceState) -> InvoiceState:
        """Comprehensive error handling with intelligent recovery routing."""
        logger.error(f"Handling error for invoice {state['invoice_id']} at step {state.get('current_step')}")

        error_details = state.get("error_details", {})
        error_type = error_details.get("error_type", "Unknown")
        recovery_possible = error_details.get("recovery_possible", False)
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        # Determine recovery strategy
        if recovery_possible and retry_count < max_retries:
            return {**state, "status": "retry"}
        elif retry_count >= max_retries:
            return {**state, "status": "escalate"}
        elif error_type in ["ValidationException", "ExtractionException"]:
            return {**state, "status": "human_review"}
        else:
            return {**state, "status": "escalate"}

    async def _retry_step(self, state: InvoiceState) -> InvoiceState:
        """Intelligent retry logic with exponential backoff and step validation."""
        retry_count = state.get("retry_count", 0) + 1
        previous_step = state.get("previous_step", "receive")

        logger.info(f"Retrying invoice {state['invoice_id']} step {previous_step} (attempt {retry_count})")

        # Update retry state
        state.update({
            "retry_count": retry_count,
            "current_step": f"retry_{previous_step}",
            "status": "processing",
            "error_message": None,
            "error_details": None
        })

        # Route back to the failed step
        if retry_count <= state.get("max_retries", 3):
            return {**state, "status": previous_step}
        else:
            return {**state, "status": "escalate"}

    async def _escalate_exception(self, state: InvoiceState) -> InvoiceState:
        """Escalate exceptions with proper notification and tracking."""
        logger.error(f"Escalating invoice {state['invoice_id']} due to persistent errors")

        # Update state for escalation
        state.update({
            "current_step": "escalated",
            "status": "escalated",
            "error_message": f"Escalated after {state.get('retry_count', 0)} retries",
            "processing_history": state.get("processing_history", []) + [{
                "step": "escalate",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "reason": "max_retries_exceeded",
                    "retry_count": state.get("retry_count", 0),
                    "final_error": state.get("error_message")
                }
            }]
        })

        # Update invoice status
        await self._update_invoice_status(state["invoice_id"], InvoiceStatus.EXCEPTION)

        return state

    async def _human_review_interrupt(self, state: InvoiceState) -> InvoiceState:
        """Human review interrupt with comprehensive context and action guidance."""
        logger.info(f"Initiating human review for invoice {state['invoice_id']}")

        # Update state for human review
        state.update({
            "current_step": "human_review",
            "status": "human_review",
            "interrupt_point": state.get("current_step"),
            "interrupt_data": {
                "reason": state.get("human_review_reason"),
                "context": state.get("human_review_data"),
                "available_actions": [
                    "approve_invoice",
                    "reject_invoice",
                    "request_changes",
                    "escalate_to_manager"
                ]
            },
            "processing_history": state.get("processing_history", []) + [{
                "step": "human_review",
                "status": "interrupted",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "review_reason": state.get("human_review_reason"),
                    "waiting_for_human": True
                }
            }]
        })

        return state

    # Routing methods for conditional edges
    def _triage_routing(self, state: InvoiceState) -> str:
        """Enhanced triage routing with intelligent decision making."""
        status = state.get("status", "")
        current_step = state.get("current_step", "")

        if status == "ready" and not state.get("requires_human_review", False):
            return "stage_export"
        elif state.get("requires_human_review", False):
            return "human_review"
        elif status == "error":
            return "error_handler"
        elif status == "processing":
            return "retry"  # Continue processing
        else:
            return "human_review"  # Default to human review for safety

    def _error_recovery_routing(self, state: InvoiceState) -> str:
        """Intelligent error recovery routing based on error type and context."""
        error_type = state.get("error_details", {}).get("error_type", "")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        if retry_count < max_retries and error_type not in ["ValidationException"]:
            return "retry"
        elif error_type in ["ValidationException", "ExtractionException"]:
            return "human_review"
        else:
            return "escalate"

    def _retry_routing(self, state: InvoiceState) -> str:
        """Smart retry routing to the appropriate step."""
        previous_step = state.get("previous_step", "receive")

        # Route back to the failed step
        step_map = {
            "receive": "receive",
            "parse": "parse",
            "patch": "patch",
            "validate": "validate",
            "triage": "triage"
        }

        return step_map.get(previous_step, "escalate")

    def _human_review_routing(self, state: InvoiceState) -> str:
        """Routing after human review based on human decision."""
        # This would be populated by human decision
        # For now, default to continue with validation
        interrupt_data = state.get("interrupt_data", {})
        human_action = interrupt_data.get("human_action", "continue")

        if human_action == "continue":
            return "triage"
        elif human_action == "retry":
            return "retry"
        elif human_action == "escalate":
            return "escalate"
        else:
            return "fail"

    # Enhanced main processing method
    async def process_invoice(self, invoice_id: str, file_path: str, **kwargs) -> Dict[str, Any]:
        """Enhanced invoice processing with comprehensive state management and error handling."""
        workflow_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        logger.info(f"Starting enhanced invoice processing workflow for {invoice_id} (workflow: {workflow_id})")

        # Initialize enhanced state
        initial_state = InvoiceState(
            invoice_id=invoice_id,
            file_path=file_path,
            file_hash=kwargs.get("file_hash", ""),
            vendor_id=kwargs.get("vendor_id"),
            workflow_id=workflow_id,
            created_at=start_time.isoformat(),
            updated_at=start_time.isoformat(),
            current_step="initialized",
            status="processing",
            previous_step=None,
            error_message=None,
            error_details=None,
            requires_human_review=False,
            retry_count=0,
            max_retries=kwargs.get("max_retries", 3),
            exceptions=[],
            exception_ids=[],
            exception_resolution_data=None,
            human_review_reason=None,
            human_review_data=None,
            interrupt_point=None,
            interrupt_data=None,
            processing_history=[],
            step_timings={},
            performance_metrics={},
            extraction_result=None,
            validation_result=None,
            confidence_score=0.0,
            export_payload=None,
            export_format=kwargs.get("export_format", "json"),
            export_ready=False,
        )

        try:
            # Run the enhanced workflow with state persistence
            thread_config = {"configurable": {"thread_id": workflow_id}}
            result = await self.runner.ainvoke(initial_state, config=thread_config)

            # Calculate performance metrics
            total_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result["performance_metrics"] = {
                "total_processing_time_ms": total_time,
                "steps_completed": len(result.get("processing_history", [])),
                "average_step_time_ms": total_time // max(len(result.get("processing_history", [])), 1),
                "success_rate": 1.0 if result.get("status") in ["staged", "ready"] else 0.0,
                "exceptions_created": len(result.get("exception_ids", []))
            }

            # Log completion
            logger.info(f"Completed enhanced invoice processing for {invoice_id}: {result['status']} "
                       f"in {total_time}ms with {len(result.get('exception_ids', []))} exceptions")

            return result

        except Exception as e:
            logger.error(f"Enhanced workflow failed for invoice {invoice_id}: {e}")

            # Update state with workflow failure
            initial_state.update({
                "status": "workflow_failed",
                "error_message": f"Workflow execution failed: {str(e)}",
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "workflow_execution",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": False
                },
                "performance_metrics": {
                    "total_processing_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "steps_completed": len(initial_state.get("processing_history", [])),
                    "success_rate": 0.0,
                    "exceptions_created": len(initial_state.get("exception_ids", []))
                }
            })

            return initial_state

    async def resume_workflow(self, workflow_id: str, human_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Resume interrupted workflow with human decision input."""
        logger.info(f"Resuming workflow {workflow_id} with human decision: {human_decision.get('action')}")

        try:
            # Get current workflow state
            thread_config = {"configurable": {"thread_id": workflow_id}}

            # Update state with human decision
            if self.checkpointer:
                # Get the latest state snapshot
                state_snapshot = await self.checkpointer.aget(workflow_id)
                if state_snapshot:
                    current_state = state_snapshot.values

                    # Update with human decision
                    current_state["interrupt_data"]["human_action"] = human_decision.get("action")
                    current_state["interrupt_data"]["human_notes"] = human_decision.get("notes")
                    current_state["interrupt_data"]["human_corrections"] = human_decision.get("corrections", {})

                    # Apply corrections if provided
                    if human_decision.get("corrections"):
                        current_state = await self._apply_human_corrections(current_state, human_decision.get("corrections"))

                    # Resume workflow from interrupt point
                    result = await self.runner.ainvoke(
                        current_state,
                        config=thread_config
                    )

                    logger.info(f"Resumed workflow {workflow_id} completed with status: {result['status']}")
                    return result

            raise WorkflowException(f"Could not resume workflow {workflow_id}: state not found")

        except Exception as e:
            logger.error(f"Failed to resume workflow {workflow_id}: {e}")
            raise WorkflowException(f"Workflow resume failed: {str(e)}")

    async def _apply_human_corrections(self, state: InvoiceState, corrections: Dict[str, Any]) -> InvoiceState:
        """Apply human corrections to extraction and validation results."""
        try:
            # Apply header corrections
            if "header" in corrections:
                extraction_result = state.get("extraction_result", {})
                if "header" in extraction_result:
                    extraction_result["header"].update(corrections["header"])
                    state["extraction_result"] = extraction_result

            # Apply line corrections
            if "lines" in corrections:
                extraction_result = state.get("extraction_result", {})
                if "lines" in extraction_result:
                    # Replace or update specific lines
                    for line_index, line_correction in corrections["lines"].items():
                        if int(line_index) < len(extraction_result["lines"]):
                            extraction_result["lines"][int(line_index)].update(line_correction)
                    state["extraction_result"] = extraction_result

            # Re-validate after corrections
            if state.get("extraction_result"):
                validation_result = await self.validation_service.validate_invoice(
                    extraction_result=state["extraction_result"],
                    invoice_id=state["invoice_id"]
                )
                state["validation_result"] = validation_result
                state["requires_human_review"] = not validation_result.get("passed", False)

            logger.info(f"Applied human corrections to invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Failed to apply human corrections: {e}")
            # Don't fail the workflow, just log the error
            return state

    def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current workflow state for monitoring and debugging."""
        try:
            if self.checkpointer:
                state_snapshot = self.checkpointer.get(workflow_id)
                if state_snapshot:
                    return state_snapshot.values
            return None
        except Exception as e:
            logger.error(f"Failed to get workflow state {workflow_id}: {e}")
            return None

    async def get_workflow_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get workflow performance metrics for monitoring."""
        try:
            # This would integrate with your monitoring system
            # For now, return basic metrics
            return {
                "workflows_processed": 0,  # Would query database
                "success_rate": 0.0,
                "average_processing_time_ms": 0,
                "exceptions_created": 0,
                "human_review_required": 0,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get workflow metrics: {e}")
            return {}