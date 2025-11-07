"""
Original LangGraph state machine for invoice processing workflow.
This is a backup of the original implementation.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict

from langfuse import Langfuse
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolInvocation

from app.core.config import settings
from app.core.exceptions import ExtractionException, ValidationException, WorkflowException
from app.services.docling_service import DoclingService
from app.services.llm_service import LLMService
from app.services.validation_service import ValidationService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class InvoiceState(TypedDict):
    """State object for invoice processing workflow."""

    # Invoice metadata
    invoice_id: str
    file_path: str
    file_hash: str
    vendor_id: Optional[str]

    # Processing results
    extraction_result: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    confidence_score: Optional[float]

    # Workflow state
    current_step: str
    status: str
    error_message: Optional[str]
    requires_human_review: bool

    # Export data
    export_payload: Optional[Dict[str, Any]]
    export_format: str


class InvoiceProcessor:
    """LangGraph-based invoice processor."""

    def __init__(self):
        """Initialize the invoice processor."""
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

        # Build the state graph
        self.graph = self._build_graph()
        self.runner = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(InvoiceState)

        # Add nodes
        workflow.add_node("receive", self._receive_invoice)
        workflow.add_node("parse", self._parse_document)
        workflow.add_node("patch", self._patch_low_confidence)
        workflow.add_node("validate", self._validate_invoice)
        workflow.add_node("triage", self._triage_results)
        workflow.add_node("stage_export", self._stage_export)

        # Set entry point
        workflow.set_entry_point("receive")

        # Define edges
        workflow.add_edge("receive", "parse")
        workflow.add_edge("parse", "patch")
        workflow.add_edge("patch", "validate")
        workflow.add_edge("validate", "triage")

        # Conditional routing from triage
        workflow.add_conditional_edges(
            "triage",
            self._should_stage_export,
            {
                "stage_export": "stage_export",
                "human_review": END,
                "error": END,
            }
        )

        workflow.add_edge("stage_export", END)

        return workflow

    async def _receive_invoice(self, state: InvoiceState) -> InvoiceState:
        """Receive and validate invoice file."""
        logger.info(f"Receiving invoice {state['invoice_id']}")

        try:
            # Validate file exists and is accessible
            file_path = state["file_path"]
            if not await self.storage_service.file_exists(file_path):
                raise WorkflowException(f"File not found: {file_path}")

            # Update state
            state["current_step"] = "received"
            state["status"] = "received"
            state["requires_human_review"] = False
            state["error_message"] = None

            # Trace the operation
            if self.langfuse:
                self.langfuse.trace(
                    name="invoice_received",
                    input=state,
                    metadata={"step": "receive", "timestamp": datetime.utcnow().isoformat()}
                )

            return state

        except Exception as e:
            logger.error(f"Failed to receive invoice {state['invoice_id']}: {e}")
            state["current_step"] = "receive_failed"
            state["status"] = "error"
            state["error_message"] = str(e)
            return state

    # ... (rest of original implementation would be here)