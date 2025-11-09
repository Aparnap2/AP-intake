"""
Enhanced AR (Accounts Receivable) invoice processor with LangGraph state machine.

This module extends the existing invoice processing workflow to support AR invoices,
including customer validation, payment terms processing, collection management,
and working capital optimization.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.config import settings
from app.core.exceptions import ExtractionException, ValidationException, WorkflowException
from app.models.workflow_states import (
    ARWorkflowStateModel, InvoiceType, WorkflowStep, WorkflowStatus,
    create_ar_workflow_state, validate_state_transition
)
from app.services.enhanced_extraction_service import EnhancedExtractionService
from app.services.validation_engine import ValidationEngine
from app.services.llm_patch_service import LLMPatchService
from app.services.storage_service import StorageService
from app.services.exception_service import ExceptionService
from app.services.export_service import ExportService
from app.services.metrics_service import metrics_service
from app.workflows.ar_workflow_nodes import (
    ARWorkflowState,
    CustomerValidationNode,
    PaymentTermsNode,
    CollectionNode,
    WorkingCapitalNode,
    CustomerCommunicationNode
)
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EnhancedARInvoiceState(TypedDict):
    """Enhanced state for AR invoice processing workflow."""

    # Core metadata
    invoice_id: str
    file_path: str
    file_hash: str
    workflow_id: str
    created_at: str
    updated_at: str

    # AR-specific fields
    invoice_type: str  # Will be "ar"
    customer_id: Optional[str]
    customer_data: Optional[Dict[str, Any]]
    payment_terms: Optional[str]
    due_date: Optional[str]
    collection_priority: str
    working_capital_score: float
    early_payment_discount: Optional[float]

    # Processing results
    extraction_result: Optional[Dict[str, Any]]
    extraction_metadata: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    validation_issues: List[Dict[str, Any]]
    validation_rules_applied: List[str]

    # AR processing results
    customer_validation_result: Optional[Dict[str, Any]]
    payment_terms_result: Optional[Dict[str, Any]]
    collection_result: Optional[Dict[str, Any]]
    working_capital_result: Optional[Dict[str, Any]]
    communication_result: Optional[Dict[str, Any]]

    # Enhanced confidence tracking
    original_confidence: Optional[float]
    enhanced_confidence: Optional[float]
    llm_patched_fields: List[str]
    patch_metadata: Dict[str, Any]

    # Workflow state
    current_step: str
    status: str
    previous_step: Optional[str]
    ar_step: str
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    requires_human_review: bool
    retry_count: int
    max_retries: int

    # Processing metadata
    processing_history: List[Dict[str, Any]]
    ar_processing_history: List[Dict[str, Any]]
    step_timings: Dict[str, Any]
    performance_metrics: Dict[str, Any]

    # Enhancement tracking
    enhancement_applied: bool
    enhancement_cost: float
    enhancement_time_ms: int

    # Export data
    export_payload: Optional[Dict[str, Any]]
    export_format: str
    export_ready: bool

    # Quality metrics
    completeness_score: Optional[float]
    accuracy_score: Optional[float]
    processing_quality: str

    # Exception management
    exceptions: List[Dict[str, Any]]
    exception_ids: List[str]
    exception_resolution_data: Optional[Dict[str, Any]]

    # Human review
    human_review_reason: Optional[str]
    human_review_data: Optional[Dict[str, Any]]
    interrupt_point: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]


class EnhancedARInvoiceProcessor:
    """Enhanced AR invoice processor with customer-centric workflow."""

    def __init__(self):
        """Initialize the enhanced AR invoice processor."""
        # Initialize core services
        self.storage_service = StorageService()
        self.enhanced_extraction_service = EnhancedExtractionService()
        self.validation_engine = ValidationEngine()
        self.llm_patch_service = LLMPatchService()
        self.exception_service = ExceptionService()
        self.export_service = ExportService()

        # Initialize AR-specific nodes
        self.customer_validation_node = CustomerValidationNode()
        self.payment_terms_node = PaymentTermsNode()
        self.collection_node = CollectionNode()
        self.working_capital_node = WorkingCapitalNode()
        self.customer_communication_node = CustomerCommunicationNode()

        # Initialize state persistence
        self.checkpointer = self._init_checkpointer()

        # Build the enhanced AR state graph
        self.graph = self._build_ar_graph()
        self.runner = self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_review"],  # Interrupt before human review nodes
            interrupt_after=["ar_triage"],  # Interrupt after triage to allow for manual intervention
        )

    def _init_checkpointer(self):
        """Initialize state persistence checkpointer."""
        try:
            # Use SQLite for persistent state storage
            import os
            # Ensure the directory exists
            persist_dir = settings.LANGGRAPH_PERSIST_PATH
            os.makedirs(persist_dir, exist_ok=True)
            checkpointer_path = f"sqlite:///{persist_dir}/ar_checkpoints.db"

            # SqliteSaver.from_conn_string may return a context manager, handle both cases
            checkpointer = SqliteSaver.from_conn_string(checkpointer_path)
            # If it's a context manager, enter it to get the actual checkpointer
            if hasattr(checkpointer, '__enter__'):
                checkpointer = checkpointer.__enter__()

            logger.info(f"AR SQLite checkpointer initialized at: {persist_dir}/ar_checkpoints.db")
            return checkpointer
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite checkpointer for AR, falling back to memory: {e}")
            return MemorySaver()

    def _build_ar_graph(self) -> StateGraph:
        """Build the enhanced AR LangGraph state machine."""
        workflow = StateGraph(EnhancedARInvoiceState)

        # Add core processing nodes (shared with AP)
        workflow.add_node("receive", self._ar_receive_invoice)
        workflow.add_node("extract", self._ar_extract_document)
        workflow.add_node("enhance", self._ar_enhance_extraction)
        workflow.add_node("validate", self._ar_validate_invoice)

        # Add AR-specific processing nodes
        workflow.add_node("customer_validation", self._ar_customer_validation)
        workflow.add_node("payment_terms", self._ar_payment_terms)
        workflow.add_node("collection", self._ar_collection_processing)
        workflow.add_node("working_capital", self._ar_working_capital_optimization)
        workflow.add_node("customer_communication", self._ar_customer_communication)

        # Add triage and export nodes
        workflow.add_node("ar_triage", self._ar_triage_results)
        workflow.add_node("stage_export", self._ar_stage_export)

        # Add error handling and recovery nodes
        workflow.add_node("error_handler", self._ar_handle_error)
        workflow.add_node("retry", self._ar_retry_step)
        workflow.add_node("escalate", self._ar_escalate_exception)
        workflow.add_node("human_review", self._ar_human_review_interrupt)

        # Set entry point
        workflow.set_entry_point("receive")

        # Define main AR workflow edges
        workflow.add_edge("receive", "extract")
        workflow.add_edge("extract", "enhance")
        workflow.add_edge("enhance", "validate")
        workflow.add_edge("validate", "customer_validation")
        workflow.add_edge("customer_validation", "payment_terms")
        workflow.add_edge("payment_terms", "collection")
        workflow.add_edge("collection", "working_capital")
        workflow.add_edge("working_capital", "customer_communication")
        workflow.add_edge("customer_communication", "ar_triage")
        workflow.add_edge("stage_export", END)

        # Conditional routing from AR triage
        workflow.add_conditional_edges(
            "ar_triage",
            self._ar_triage_routing,
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
            self._ar_error_recovery_routing,
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
            self._ar_retry_routing,
            {
                "receive": "receive",
                "extract": "extract",
                "enhance": "enhance",
                "validate": "validate",
                "customer_validation": "customer_validation",
                "payment_terms": "payment_terms",
                "collection": "collection",
                "working_capital": "working_capital",
                "customer_communication": "customer_communication",
                "escalate": "escalate",
                "fail": END,
            }
        )

        # Human review completion routing
        workflow.add_conditional_edges(
            "human_review",
            self._ar_human_review_routing,
            {
                "continue": "ar_triage",
                "retry": "retry",
                "escalate": "escalate",
                "fail": END,
            }
        )

        # Escalation completion
        workflow.add_edge("escalate", END)

        return workflow

    # Core processing node implementations
    async def _ar_receive_invoice(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific invoice reception with customer identification validation."""
        start_time = datetime.utcnow()
        logger.info(f"Receiving AR invoice {state['invoice_id']} workflow {state['workflow_id']}")

        try:
            # Update processing metadata
            state["updated_at"] = datetime.utcnow().isoformat()

            # Validate file exists and is accessible
            file_path = state["file_path"]
            if not await self.storage_service.file_exists(file_path):
                raise WorkflowException(f"File not found: {file_path}")

            # Get file content and metadata
            file_content = await self.storage_service.get_file_content(file_path)
            file_size = len(file_content)

            # Validate file size
            max_size_mb = settings.MAX_FILE_SIZE_MB
            max_size_bytes = max_size_mb * 1024 * 1024
            if file_size > max_size_bytes:
                raise WorkflowException(f"File size {file_size} exceeds maximum {max_size_mb}MB")

            # Calculate file hash if not provided
            if not state.get("file_hash"):
                import hashlib
                state["file_hash"] = hashlib.sha256(file_content).hexdigest()

            # Update state with successful reception
            state.update({
                "current_step": "ar_received",
                "status": WorkflowStatus.PROCESSING.value,
                "ar_step": "received",
                "previous_step": state.get("current_step"),
                "requires_human_review": False,
                "error_message": None,
                "error_details": None,
                "retry_count": 0,
                "max_retries": 3,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "ar_receive",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "file_size": file_size,
                        "file_path": file_path,
                        "file_hash": state.get("file_hash"),
                        "invoice_type": "ar"
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["ar_receive"] = step_time

            logger.info(f"Successfully received AR invoice {state['invoice_id']} in {step_time}ms")
            return state

        except Exception as e:
            logger.error(f"Failed to receive AR invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_receive_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "receive_failed",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "ar_receive",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True
                }
            })

            return state

    async def _ar_extract_document(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific document extraction with customer field emphasis."""
        start_time = datetime.utcnow()
        logger.info(f"Extracting AR document for invoice {state['invoice_id']}")

        try:
            # Update processing metadata
            state["updated_at"] = datetime.utcnow().isoformat()

            # Get file content
            file_path = state["file_path"]
            file_content = await self.storage_service.get_file_content(file_path)

            # Perform enhanced extraction with AR focus
            extraction_result = await self.enhanced_extraction_service.extract_with_enhancement(
                file_content=file_content,
                file_path=file_path,
                enable_llm_patching=True,
                focus_fields=["customer_name", "customer_email", "customer_tax_id", "payment_terms", "due_date"]
            )

            # Extract detailed metadata
            extraction_metadata = extraction_result.metadata.model_dump()
            confidence_data = extraction_result.confidence.model_dump()

            # Store original confidence
            original_confidence = float(confidence_data.get("overall", 0.0))
            state["original_confidence"] = original_confidence

            # Check if LLM patching was applied
            llm_patched_fields = []
            processing_notes = extraction_result.processing_notes or []
            for note in processing_notes:
                if "LLM patched" in note:
                    llm_patched_fields.append(note)

            state["llm_patched_fields"] = llm_patched_fields
            state["enhancement_applied"] = len(llm_patched_fields) > 0

            # Update state with extraction results
            state.update({
                "extraction_result": extraction_result.model_dump(),
                "extraction_metadata": extraction_metadata,
                "current_step": "ar_extracted",
                "status": WorkflowStatus.PROCESSING.value,
                "ar_step": "extracted",
                "previous_step": state.get("current_step"),
                "enhanced_confidence": original_confidence,
                "completeness_score": float(extraction_metadata.get("completeness_score", 0.0)),
                "accuracy_score": float(extraction_metadata.get("accuracy_score", 0.0)),
                "processing_history": state.get("processing_history", []) + [{
                    "step": "ar_extract",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "extraction_confidence": original_confidence,
                        "completeness_score": extraction_metadata.get("completeness_score"),
                        "accuracy_score": extraction_metadata.get("accuracy_score"),
                        "parser_version": extraction_metadata.get("parser_version"),
                        "page_count": extraction_metadata.get("page_count"),
                        "llm_patched_fields": len(llm_patched_fields),
                        "customer_fields_extracted": self._check_customer_fields_extracted(extraction_result)
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["ar_extract"] = step_time

            logger.info(f"Successfully extracted AR invoice {state['invoice_id']} with confidence {original_confidence:.3f}")
            return state

        except Exception as e:
            logger.error(f"Failed to extract AR document for invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_extract_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "extract_failed",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "ar_extract",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": True
                }
            })

            return state

    def _check_customer_fields_extracted(self, extraction_result) -> Dict[str, bool]:
        """Check if essential customer fields were extracted."""
        header = extraction_result.header.model_dump(exclude_unset=True) if hasattr(extraction_result, 'header') else extraction_result.get("header", {})

        return {
            "customer_name": "customer_name" in header or "bill_to_name" in header,
            "customer_email": "customer_email" in header,
            "customer_tax_id": "customer_tax_id" in header or "customer_vat" in header,
            "payment_terms": "payment_terms" in header,
            "invoice_date": "invoice_date" in header,
            "total_amount": "total_amount" in header
        }

    async def _ar_enhance_extraction(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Apply AR-specific enhancement to extraction results."""
        start_time = datetime.utcnow()
        logger.info(f"Enhancing AR extraction for invoice {state['invoice_id']}")

        try:
            # Check if enhancement is needed
            current_confidence = state.get("enhanced_confidence", 0.0)
            if current_confidence >= settings.DOCLING_CONFIDENCE_THRESHOLD:
                logger.info(f"Confidence {current_confidence:.3f} already above threshold, skipping AR enhancement")
                state.update({
                    "current_step": "ar_enhancement_skipped",
                    "status": WorkflowStatus.PROCESSING.value,
                    "ar_step": "enhancement_skipped",
                    "enhancement_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "processing_history": state.get("processing_history", []) + [{
                        "step": "ar_enhance",
                        "status": "skipped",
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                        "metadata": {"reason": "confidence_above_threshold"}
                    }]
                })
                return state

            # Apply AR-specific enhancement
            extraction_result = state.get("extraction_result", {})
            if extraction_result:
                enhanced_result = await self._apply_ar_specific_enhancement(extraction_result, current_confidence)

                # Calculate improvement
                new_confidence = enhanced_result.get("confidence", {}).get("overall", current_confidence)
                confidence_improvement = new_confidence - current_confidence

                # Update enhancement metadata
                state.update({
                    "extraction_result": enhanced_result,
                    "enhanced_confidence": new_confidence,
                    "enhancement_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "enhancement_cost": self._estimate_enhancement_cost(enhanced_result),
                    "current_step": "ar_enhanced",
                    "status": WorkflowStatus.PROCESSING.value,
                    "ar_step": "enhanced",
                    "previous_step": state.get("current_step"),
                    "processing_history": state.get("processing_history", []) + [{
                        "step": "ar_enhance",
                        "status": "completed",
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                        "metadata": {
                            "original_confidence": current_confidence,
                            "new_confidence": new_confidence,
                            "confidence_improvement": confidence_improvement,
                            "enhancement_cost": state.get("enhancement_cost", 0.0),
                            "ar_focus": "customer_fields"
                        }
                    }]
                })

                logger.info(f"Enhanced AR extraction confidence from {current_confidence:.3f} to {new_confidence:.3f}")
            else:
                state.update({
                    "current_step": "ar_enhancement_failed",
                    "status": WorkflowStatus.FAILED.value,
                    "ar_step": "enhancement_failed",
                    "error_message": "No extraction result to enhance"
                })

            return state

        except Exception as e:
            logger.error(f"AR enhancement failed for invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_enhancement_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "enhancement_failed",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "ar_enhance",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            return state

    async def _ar_validate_invoice(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific invoice validation with customer-focused rules."""
        start_time = datetime.utcnow()
        logger.info(f"Validating AR invoice {state['invoice_id']}")

        try:
            # Update processing metadata
            state["updated_at"] = datetime.utcnow().isoformat()

            extraction_result = state.get("extraction_result", {})
            if not extraction_result:
                raise ValidationException("No extraction result to validate")

            # Perform AR-specific validation
            validation_result = await self.validation_engine.validate_ar_invoice(
                extraction_result=extraction_result,
                invoice_id=state["invoice_id"],
                customer_id=state.get("customer_id"),
                strict_mode=False
            )

            # Extract validation details
            validation_passed = validation_result.passed
            total_issues = validation_result.total_issues
            error_count = validation_result.error_count
            warning_count = validation_result.warning_count
            confidence_score = validation_result.confidence_score

            # Collect validation issues
            validation_issues = []
            for issue in validation_result.issues:
                validation_issues.append({
                    "code": issue.code.value if hasattr(issue.code, 'value') else str(issue.code),
                    "message": issue.message,
                    "severity": issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
                    "field": issue.field,
                    "line_number": issue.line_number,
                    "details": issue.details
                })

            # Get applied rules
            applied_rules = []
            if hasattr(validation_result, 'check_results'):
                check_results = validation_result.check_results.model_dump()
                applied_rules = [rule for rule, passed in check_results.items() if passed]

            # Create exceptions for validation failures
            exception_ids = []
            if not validation_passed and error_count > 0:
                try:
                    exceptions = await self.exception_service.create_exception_from_validation(
                        invoice_id=state["invoice_id"],
                        validation_issues=validation_result.issues
                    )
                    exception_ids = [exc.id for exc in exceptions]
                    logger.info(f"Created {len(exception_ids)} exceptions for AR invoice {state['invoice_id']}")
                except Exception as exc_error:
                    logger.error(f"Failed to create exceptions for AR invoice {state['invoice_id']}: {exc_error}")

            # Update state with validation results
            state.update({
                "validation_result": validation_result.model_dump(),
                "validation_issues": validation_issues,
                "validation_rules_applied": applied_rules,
                "current_step": "ar_validated",
                "status": WorkflowStatus.EXCEPTION.value if not validation_passed else WorkflowStatus.PROCESSING.value,
                "ar_step": "validated",
                "previous_step": state.get("current_step"),
                "requires_human_review": not validation_passed or error_count > 0,
                "exceptions": validation_issues,
                "exception_ids": state.get("exception_ids", []) + exception_ids,
                "error_message": None if validation_passed else f"AR validation failed with {error_count} errors",
                "error_details": None if validation_passed else {
                    "validation_errors": error_count,
                    "validation_warnings": warning_count,
                    "validation_confidence": confidence_score
                },
                "processing_history": state.get("processing_history", []) + [{
                    "step": "ar_validate",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "validation_passed": validation_passed,
                        "total_issues": total_issues,
                        "error_count": error_count,
                        "warning_count": warning_count,
                        "validation_confidence": confidence_score,
                        "rules_applied": len(applied_rules),
                        "exceptions_created": len(exception_ids),
                        "ar_focus": "customer_validation"
                    }
                }]
            })

            # Update step timings
            step_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state["step_timings"] = state.get("step_timings", {})
            state["step_timings"]["ar_validate"] = step_time

            logger.info(f"AR validation completed for invoice {state['invoice_id']}: {'PASSED' if validation_passed else 'FAILED'}")
            return state

        except Exception as e:
            logger.error(f"AR validation failed for invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_validation_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "validation_failed",
                "previous_step": state.get("current_step"),
                "error_message": str(e),
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "ar_validate",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            return state

    # AR-specific processing node implementations
    async def _ar_customer_validation(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Execute customer validation using AR workflow node."""
        # Convert to ARWorkflowState for node processing
        ar_state = ARWorkflowState(state)
        result_state = await self.customer_validation_node.execute(ar_state)

        # Update state with results
        state.update(result_state)
        return state

    async def _ar_payment_terms(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Execute payment terms processing using AR workflow node."""
        ar_state = ARWorkflowState(state)
        result_state = await self.payment_terms_node.execute(ar_state)

        # Update state with results
        state.update(result_state)
        return state

    async def _ar_collection_processing(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Execute collection processing using AR workflow node."""
        ar_state = ARWorkflowState(state)
        result_state = await self.collection_node.execute(ar_state)

        # Update state with results
        state.update(result_state)
        return state

    async def _ar_working_capital_optimization(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Execute working capital optimization using AR workflow node."""
        ar_state = ARWorkflowState(state)
        result_state = await self.working_capital_node.execute(ar_state)

        # Update state with results
        state.update(result_state)
        return state

    async def _ar_customer_communication(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """Execute customer communication using AR workflow node."""
        ar_state = ARWorkflowState(state)
        result_state = await self.customer_communication_node.execute(ar_state)

        # Update state with results
        state.update(result_state)
        return state

    # Additional helper methods
    async def _apply_ar_specific_enhancement(
        self, extraction_result: Dict[str, Any], current_confidence: float
    ) -> Dict[str, Any]:
        """Apply AR-specific enhancement to extraction results."""
        try:
            # Use LLM patch service with AR focus
            enhanced_result = await self.llm_patch_service.patch_fields(
                extraction_result,
                target_fields=["customer_name", "customer_email", "customer_tax_id", "payment_terms"]
            )
            return enhanced_result
        except Exception as e:
            logger.warning(f"AR-specific enhancement failed: {e}")
            return extraction_result

    def _estimate_enhancement_cost(self, extraction_result: Dict[str, Any]) -> float:
        """Estimate enhancement cost for AR processing."""
        line_count = len(extraction_result.get("lines", []))
        base_cost = 0.01
        per_line_cost = 0.002
        return base_cost + (line_count * per_line_cost)

    async def _ar_triage_results(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific triage with customer-focused decision making."""
        start_time = datetime.utcnow()
        logger.info(f"AR triaging results for invoice {state['invoice_id']}")

        try:
            # Get key metrics for AR triage
            validation_result = state.get("validation_result", {})
            customer_validation_result = state.get("customer_validation_result", {})
            collection_result = state.get("collection_result", {})
            working_capital_result = state.get("working_capital_result", {})
            confidence = state.get("enhanced_confidence", 0.0)

            # Calculate AR-specific triage decision
            triage_decision = self._calculate_ar_triage_decision(
                validation_passed=validation_result.get("passed", False),
                confidence_score=confidence,
                customer_valid=customer_validation_result.get("valid", False),
                collection_priority=collection_result.get("priority", "medium"),
                working_capital_score=working_capital_result.get("overall_score", 50.0),
                error_count=validation_result.get("error_count", 0),
                exceptions=state.get("validation_issues", [])
            )

            # Determine human review requirements
            human_review_required = self._determine_ar_review_requirements(
                triage_decision, validation_result, customer_validation_result, confidence
            )

            # Update state with triage results
            state.update({
                "current_step": "ar_triaged",
                "status": self._map_ar_triage_to_status(triage_decision),
                "ar_step": "triaged",
                "previous_step": state.get("current_step"),
                "requires_human_review": human_review_required,
                "processing_history": state.get("processing_history", []) + [{
                    "step": "ar_triage",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "triage_decision": triage_decision,
                        "human_review_required": human_review_required,
                        "confidence_score": confidence,
                        "customer_valid": customer_validation_result.get("valid", False),
                        "collection_priority": collection_result.get("priority"),
                        "working_capital_score": working_capital_result.get("overall_score"),
                        "validation_errors": validation_result.get("error_count", 0)
                    }
                }]
            })

            logger.info(f"AR triage completed for invoice {state['invoice_id']}: {triage_decision}")
            return state

        except Exception as e:
            logger.error(f"AR triage failed for invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_triage_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "triage_failed",
                "error_message": str(e)
            })

            return state

    def _calculate_ar_triage_decision(
        self,
        validation_passed: bool,
        confidence_score: float,
        customer_valid: bool,
        collection_priority: str,
        working_capital_score: float,
        error_count: int,
        exceptions: List[Dict[str, Any]]
    ) -> str:
        """Calculate AR-specific triage decision."""
        # All checks passed with good scores - auto approve
        if (validation_passed and customer_valid and
            confidence_score >= 0.9 and working_capital_score >= 80):
            return "auto_approve"

        # Passed validation but lower confidence - conditional approve
        if (validation_passed and customer_valid and
            confidence_score >= settings.DOCLING_CONFIDENCE_THRESHOLD and
            working_capital_score >= 60):
            return "conditional_approve"

        # High collection priority - needs review
        if collection_priority in ["high", "urgent"]:
            return "high_priority_review"

        # Customer validation failed - needs review
        if not customer_valid:
            return "customer_review_required"

        # Working capital score low - needs optimization review
        if working_capital_score < 50:
            return "working_capital_review"

        # Default to human review for safety
        return "human_review"

    def _determine_ar_review_requirements(
        self,
        triage_decision: str,
        validation_result: Dict[str, Any],
        customer_validation_result: Dict[str, Any],
        confidence_score: float
    ) -> bool:
        """Determine if human review is required for AR invoice."""
        auto_review_decisions = ["auto_approve", "conditional_approve"]

        # Additional AR-specific checks
        if triage_decision not in auto_review_decisions:
            return True

        # Check for critical customer issues
        if not customer_validation_result.get("valid", False):
            return True

        # Check for low confidence in customer fields
        if confidence_score < settings.DOCLING_CONFIDENCE_THRESHOLD:
            return True

        return False

    def _map_ar_triage_to_status(self, triage_decision: str) -> str:
        """Map AR triage decision to workflow status."""
        status_map = {
            "auto_approve": WorkflowStatus.READY.value,
            "conditional_approve": WorkflowStatus.READY.value,
            "high_priority_review": WorkflowStatus.EXCEPTION.value,
            "customer_review_required": WorkflowStatus.HUMAN_REVIEW.value,
            "working_capital_review": WorkflowStatus.HUMAN_REVIEW.value,
            "human_review": WorkflowStatus.HUMAN_REVIEW.value
        }
        return status_map.get(triage_decision, WorkflowStatus.EXCEPTION.value)

    async def _ar_stage_export(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific export staging with customer data."""
        start_time = datetime.utcnow()
        logger.info(f"Staging AR export for invoice {state['invoice_id']}")

        try:
            # Prepare AR-specific export payload
            extraction_result = state.get("extraction_result", {})
            export_format = state.get("export_format", "json")

            # Create comprehensive AR export payload
            export_payload = {
                "invoice_id": state["invoice_id"],
                "workflow_id": state["workflow_id"],
                "invoice_type": "ar",
                "header": extraction_result.get("header", {}),
                "lines": extraction_result.get("lines", []),
                "confidence": extraction_result.get("confidence", {}),
                "customer_data": state.get("customer_data"),
                "payment_terms": state.get("payment_terms"),
                "due_date": state.get("due_date"),
                "collection_priority": state.get("collection_priority"),
                "working_capital_score": state.get("working_capital_score"),
                "early_payment_discount": state.get("early_payment_discount"),
                "metadata": {
                    "extraction_confidence": state.get("enhanced_confidence", 0.0),
                    "validation_passed": state.get("validation_result", {}).get("passed", False),
                    "customer_validation_passed": state.get("customer_validation_result", {}).get("valid", False),
                    "working_capital_optimization": state.get("working_capital_result", {}),
                    "customer_communication": state.get("communication_result", {}),
                    "processed_at": datetime.utcnow().isoformat(),
                    "export_format": export_format,
                    "export_version": "ar-2.0.0",
                    "processing_summary": {
                        "total_steps": len(state.get("processing_history", [])),
                        "ar_steps": len(state.get("ar_processing_history", [])),
                        "total_time_ms": sum(
                            step.get("duration_ms", 0) for step in state.get("processing_history", [])
                        ),
                        "exceptions_resolved": len(state.get("exception_ids", []))
                    }
                }
            }

            # Generate export content
            if export_format.lower() == "json":
                export_content = await self.export_service.export_to_json(export_payload)
            elif export_format.lower() == "csv":
                export_content = await self.export_service.export_to_csv(export_payload)
            else:
                # Generate multiple formats
                export_content = {
                    "json": await self.export_service.export_to_json(export_payload),
                    "csv": await self.export_service.export_to_csv(export_payload),
                    "ar_json": export_payload  # Include AR-specific metadata
                }

            # Update state with export results
            state.update({
                "export_payload": export_payload,
                "export_format": export_format,
                "export_ready": True,
                "current_step": "ar_export_staged",
                "status": WorkflowStatus.COMPLETED.value,
                "ar_step": "export_staged",
                "previous_step": state.get("current_step"),
                "processing_history": state.get("processing_history", []) + [{
                    "step": "ar_stage_export",
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "metadata": {
                        "export_format": export_format,
                        "export_size": len(str(export_content)),
                        "export_version": "ar-2.0.0",
                        "customer_included": True,
                        "working_capital_included": True
                    }
                }]
            })

            logger.info(f"Successfully staged AR export for invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"AR export staging failed for invoice {state['invoice_id']}: {e}")

            state.update({
                "current_step": "ar_export_failed",
                "status": WorkflowStatus.FAILED.value,
                "ar_step": "export_failed",
                "error_message": str(e)
            })

            return state

    # Error handling methods (similar to main processor but AR-specific)
    async def _ar_handle_error(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific error handling."""
        logger.error(f"AR error handling for invoice {state['invoice_id']}")

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

    async def _ar_retry_step(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific retry logic."""
        retry_count = state.get("retry_count", 0) + 1
        previous_step = state.get("previous_step", "receive")

        logger.info(f"Retrying AR invoice {state['invoice_id']} step {previous_step} (attempt {retry_count})")

        # Update retry state
        state.update({
            "retry_count": retry_count,
            "current_step": f"ar_retry_{previous_step}",
            "status": WorkflowStatus.PROCESSING.value,
            "error_message": None,
            "error_details": None
        })

        # Route back to the failed step
        if retry_count <= state.get("max_retries", 3):
            return {**state, "status": previous_step}
        else:
            return {**state, "status": "escalate"}

    async def _ar_escalate_exception(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific exception escalation."""
        logger.error(f"Escalating AR invoice {state['invoice_id']} due to persistent errors")

        state.update({
            "current_step": "ar_escalated",
            "status": WorkflowStatus.ESCALATED.value,
            "ar_step": "escalated",
            "error_message": f"AR escalation after {state.get('retry_count', 0)} retries",
            "processing_history": state.get("processing_history", []) + [{
                "step": "ar_escalate",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "reason": "max_retries_exceeded",
                    "retry_count": state.get("retry_count", 0),
                    "final_error": state.get("error_message")
                }
            }]
        })

        return state

    async def _ar_human_review_interrupt(self, state: EnhancedARInvoiceState) -> EnhancedARInvoiceState:
        """AR-specific human review interrupt."""
        logger.info(f"Initiating AR human review for invoice {state['invoice_id']}")

        state.update({
            "current_step": "ar_human_review",
            "status": WorkflowStatus.HUMAN_REVIEW.value,
            "ar_step": "human_review",
            "interrupt_point": state.get("current_step"),
            "interrupt_data": {
                "reason": state.get("human_review_reason"),
                "context": state.get("human_review_data"),
                "available_actions": [
                    "approve_invoice",
                    "reject_invoice",
                    "request_customer_info",
                    "adjust_payment_terms",
                    "escalate_to_manager"
                ]
            },
            "processing_history": state.get("processing_history", []) + [{
                "step": "ar_human_review",
                "status": "interrupted",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "review_reason": state.get("human_review_reason"),
                    "waiting_for_human": True,
                    "ar_focus": "customer_review"
                }
            }]
        })

        return state

    # Routing methods for conditional edges
    def _ar_triage_routing(self, state: EnhancedARInvoiceState) -> str:
        """AR-specific triage routing."""
        status = state.get("status", "")
        current_step = state.get("current_step", "")

        if status == WorkflowStatus.READY.value and not state.get("requires_human_review", False):
            return "stage_export"
        elif state.get("requires_human_review", False):
            return "human_review"
        elif status == WorkflowStatus.FAILED.value:
            return "error_handler"
        elif status == WorkflowStatus.PROCESSING.value:
            return "retry"
        else:
            return "human_review"

    def _ar_error_recovery_routing(self, state: EnhancedARInvoiceState) -> str:
        """AR-specific error recovery routing."""
        error_type = state.get("error_details", {}).get("error_type", "")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        if retry_count < max_retries and error_type not in ["ValidationException"]:
            return "retry"
        elif error_type in ["ValidationException", "ExtractionException"]:
            return "human_review"
        else:
            return "escalate"

    def _ar_retry_routing(self, state: EnhancedARInvoiceState) -> str:
        """AR-specific retry routing."""
        previous_step = state.get("previous_step", "receive")

        # Route back to the failed step
        step_map = {
            "receive": "receive",
            "extract": "extract",
            "enhance": "enhance",
            "validate": "validate",
            "customer_validation": "customer_validation",
            "payment_terms": "payment_terms",
            "collection": "collection",
            "working_capital": "working_capital",
            "customer_communication": "customer_communication"
        }

        return step_map.get(previous_step, "escalate")

    def _ar_human_review_routing(self, state: EnhancedARInvoiceState) -> str:
        """AR-specific routing after human review."""
        interrupt_data = state.get("interrupt_data", {})
        human_action = interrupt_data.get("human_action", "continue")

        if human_action == "continue":
            return "ar_triage"
        elif human_action == "retry":
            return "retry"
        elif human_action == "escalate":
            return "escalate"
        else:
            return "fail"

    # Main processing method
    async def process_ar_invoice(
        self,
        invoice_id: str,
        file_path: str,
        customer_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Process AR invoice with comprehensive customer workflow."""
        workflow_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        logger.info(f"Starting AR invoice processing workflow for {invoice_id} (workflow: {workflow_id})")

        # Initialize AR state
        initial_state = EnhancedARInvoiceState(
            invoice_id=invoice_id,
            file_path=file_path,
            file_hash=kwargs.get("file_hash", ""),
            workflow_id=workflow_id,
            created_at=start_time.isoformat(),
            updated_at=start_time.isoformat(),
            invoice_type=InvoiceType.AR.value,
            customer_id=customer_id,
            current_step="initialized",
            status=WorkflowStatus.PROCESSING.value,
            ar_step="initialized",
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
            ar_processing_history=[],
            step_timings={},
            performance_metrics={},
            extraction_result=None,
            extraction_metadata=None,
            validation_result=None,
            validation_issues=[],
            validation_rules_applied=[],
            customer_validation_result=None,
            payment_terms_result=None,
            collection_result=None,
            working_capital_result=None,
            communication_result=None,
            original_confidence=None,
            enhanced_confidence=None,
            llm_patched_fields=[],
            patch_metadata={},
            enhancement_applied=False,
            enhancement_cost=0.0,
            enhancement_time_ms=0,
            export_payload=None,
            export_format=kwargs.get("export_format", "json"),
            export_ready=False,
            completeness_score=None,
            accuracy_score=None,
            processing_quality="unknown",
            customer_data=None,
            payment_terms=None,
            due_date=None,
            collection_priority="medium",
            working_capital_score=0.0,
            early_payment_discount=None,
        )

        try:
            # Run the AR workflow with state persistence
            thread_config = {"configurable": {"thread_id": workflow_id}}
            result = await self.runner.ainvoke(initial_state, config=thread_config)

            # Calculate comprehensive performance metrics
            total_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result["performance_metrics"] = {
                "total_processing_time_ms": total_time,
                "steps_completed": len(result.get("processing_history", [])),
                "ar_steps_completed": len(result.get("ar_processing_history", [])),
                "average_step_time_ms": total_time // max(len(result.get("processing_history", [])), 1),
                "enhancement_applied": result.get("enhancement_applied", False),
                "enhancement_cost": result.get("enhancement_cost", 0.0),
                "working_capital_score": result.get("working_capital_score", 0.0),
                "customer_validated": result.get("customer_validation_result", {}).get("valid", False),
                "communication_sent": result.get("communication_result", {}).get("sent", False),
                "exceptions_created": len(result.get("exception_ids", []))
            }

            # Log completion
            logger.info(
                f"Completed AR invoice processing for {invoice_id}: {result['status']} "
                f"in {total_time}ms with working capital score {result.get('working_capital_score', 0.0)}"
            )

            # Record comprehensive metrics
            await self._record_ar_metrics(invoice_id, result)

            return result

        except Exception as e:
            logger.error(f"AR workflow failed for invoice {invoice_id}: {e}")

            # Update state with workflow failure
            initial_state.update({
                "status": WorkflowStatus.FAILED.value,
                "error_message": f"AR workflow execution failed: {str(e)}",
                "error_details": {
                    "error_type": type(e).__name__,
                    "step": "ar_workflow_execution",
                    "timestamp": datetime.utcnow().isoformat(),
                    "recovery_possible": False
                },
                "performance_metrics": {
                    "total_processing_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "steps_completed": len(initial_state.get("processing_history", [])),
                    "ar_steps_completed": len(initial_state.get("ar_processing_history", [])),
                    "success_rate": 0.0,
                    "exceptions_created": len(initial_state.get("exception_ids", []))
                }
            })

            return initial_state

    async def _record_ar_metrics(self, invoice_id: str, result: Dict[str, Any]):
        """Record comprehensive metrics for AR processing."""
        try:
            await metrics_service.record_ar_invoice_metric(
                invoice_id=invoice_id,
                workflow_data=result,
                extraction_data=result.get("extraction_result"),
                validation_data=result.get("validation_result"),
                customer_data=result.get("customer_data"),
                working_capital_metrics={
                    "working_capital_score": result.get("working_capital_score", 0.0),
                    "collection_priority": result.get("collection_priority"),
                    "early_payment_discount": result.get("early_payment_discount")
                }
            )
            logger.debug(f"Recorded AR metrics for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to record AR metrics for invoice {invoice_id}: {e}")

    # Workflow management methods
    async def resume_ar_workflow(self, workflow_id: str, human_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Resume interrupted AR workflow with human decision input."""
        logger.info(f"Resuming AR workflow {workflow_id} with human decision: {human_decision.get('action')}")

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
                        current_state = await self._apply_ar_human_corrections(current_state, human_decision.get("corrections"))

                    # Resume workflow from interrupt point
                    result = await self.runner.ainvoke(
                        current_state,
                        config=thread_config
                    )

                    logger.info(f"Resumed AR workflow {workflow_id} completed with status: {result['status']}")
                    return result

            raise WorkflowException(f"Could not resume AR workflow {workflow_id}: state not found")

        except Exception as e:
            logger.error(f"Failed to resume AR workflow {workflow_id}: {e}")
            raise WorkflowException(f"AR workflow resume failed: {str(e)}")

    async def _apply_ar_human_corrections(self, state: EnhancedARInvoiceState, corrections: Dict[str, Any]) -> EnhancedARInvoiceState:
        """Apply human corrections to AR processing results."""
        try:
            # Apply customer data corrections
            if "customer_data" in corrections:
                state["customer_data"].update(corrections["customer_data"])

            # Apply extraction corrections
            if "extraction_result" in corrections:
                extraction_result = state.get("extraction_result", {})
                if "header" in extraction_result:
                    extraction_result["header"].update(corrections["extraction_result"].get("header", {}))
                state["extraction_result"] = extraction_result

            # Apply payment terms corrections
            if "payment_terms" in corrections:
                state["payment_terms"] = corrections["payment_terms"]

            # Re-validate after corrections
            if state.get("extraction_result"):
                validation_result = await self.validation_engine.validate_ar_invoice(
                    extraction_result=state["extraction_result"],
                    invoice_id=state["invoice_id"],
                    customer_id=state.get("customer_id")
                )
                state["validation_result"] = validation_result
                state["requires_human_review"] = not validation_result.get("passed", False)

            logger.info(f"Applied human corrections to AR invoice {state['invoice_id']}")
            return state

        except Exception as e:
            logger.error(f"Failed to apply AR human corrections: {e}")
            return state

    def get_ar_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current AR workflow state for monitoring and debugging."""
        try:
            if self.checkpointer:
                state_snapshot = self.checkpointer.get(workflow_id)
                if state_snapshot:
                    return state_snapshot.values
            return None
        except Exception as e:
            logger.error(f"Failed to get AR workflow state {workflow_id}: {e}")
            return None

    async def get_ar_workflow_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get AR workflow performance metrics for monitoring."""
        try:
            # This would integrate with your monitoring system
            # For now, return basic metrics
            return {
                "ar_workflows_processed": 0,  # Would query database
                "success_rate": 0.0,
                "average_processing_time_ms": 0,
                "average_working_capital_score": 0.0,
                "customer_validation_rate": 0.0,
                "communication_success_rate": 0.0,
                "exceptions_created": 0,
                "human_review_required": 0,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get AR workflow metrics: {e}")
            return {}