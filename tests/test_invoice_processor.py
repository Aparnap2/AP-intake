"""
Test suite for LangGraph invoice processor workflow.
Tests the complete 6-stage workflow: receive -> parse -> patch -> validate -> triage -> stage_export
"""

import pytest
import asyncio
import tempfile
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.workflows.invoice_processor import InvoiceProcessor, InvoiceState
from app.core.exceptions import WorkflowException, ExtractionException, ValidationException
from app.models.invoice import InvoiceStatus


class TestInvoiceProcessorWorkflow:
    """Test cases for the LangGraph invoice processor workflow."""

    @pytest.fixture
    def processor(self):
        """Create a fresh invoice processor instance for each test."""
        return InvoiceProcessor()

    @pytest.fixture
    def sample_invoice_state(self):
        """Create a sample invoice state for testing."""
        return InvoiceState(
            invoice_id=str(uuid.uuid4()),
            file_path="/tmp/test_invoice.pdf",
            file_hash="abc123",
            vendor_id="vendor_001",
            workflow_id=str(uuid.uuid4()),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            current_step="initialized",
            status="processing",
            previous_step=None,
            error_message=None,
            error_details=None,
            requires_human_review=False,
            retry_count=0,
            max_retries=3,
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
            export_format="json",
            export_ready=False,
        )

    @pytest.fixture
    def sample_file_content(self):
        """Create sample PDF file content for testing."""
        return b"sample_pdf_content_for_testing"

    @pytest.fixture
    def temp_pdf_file(self, sample_file_content):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(sample_file_content)
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    class TestWorkflowInitialization:
        """Test workflow initialization and configuration."""

        def test_checkpointer_initialization(self, processor):
            """Test that checkpointer is properly initialized."""
            assert processor.checkpointer is not None
            # Check that checkpointer is not a context manager
            assert not str(type(processor.checkpointer).__name__).startswith('_GeneratorContextManager')

        def test_graph_compilation(self, processor):
            """Test that the state graph is properly compiled."""
            assert processor.graph is not None
            assert processor.runner is not None

            # Verify graph has all required nodes
            nodes = processor.graph.nodes
            required_nodes = [
                "receive", "parse", "patch", "validate",
                "triage", "stage_export", "error_handler",
                "retry", "escalate", "human_review"
            ]
            for node in required_nodes:
                assert node in nodes, f"Missing required node: {node}"

        def test_state_schema_structure(self):
            """Test that the InvoiceState schema has all required fields."""
            required_fields = [
                "invoice_id", "file_path", "workflow_id", "current_step",
                "status", "extraction_result", "validation_result",
                "confidence_score", "requires_human_review"
            ]

            for field in required_fields:
                assert field in InvoiceState.__annotations__, f"Missing required field: {field}"

    class TestReceiveNode:
        """Test the receive invoice node."""

        @pytest.mark.asyncio
        async def test_receive_success(self, processor, sample_invoice_state, temp_pdf_file):
            """Test successful invoice reception."""
            # Update state with actual temp file path
            sample_invoice_state["file_path"] = temp_pdf_file

            # Mock storage service
            with patch.object(processor.storage_service, 'file_exists', return_value=True), \
                 patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
                 patch.object(processor, '_check_duplicate_invoice', return_value=None), \
                 patch.object(processor, '_update_invoice_status'), \
                 patch('app.workflows.invoice_processor.AsyncSessionLocal'):

                result = await processor._receive_invoice(sample_invoice_state)

                assert result["current_step"] == "received"
                assert result["status"] == "processing"
                assert result["error_message"] is None
                assert len(result["processing_history"]) > 0

        @pytest.mark.asyncio
        async def test_receive_file_not_found(self, processor, sample_invoice_state):
            """Test handling of missing file."""
            with patch.object(processor.storage_service, 'file_exists', return_value=False), \
                 patch('app.workflows.invoice_processor.AsyncSessionLocal'):
                result = await processor._receive_invoice(sample_invoice_state)

                assert result["current_step"] == "receive_failed"
                assert result["status"] == "error"
                assert "File not found" in result["error_message"]

    class TestParseNode:
        """Test the document parsing node."""

        @pytest.mark.asyncio
        async def test_parse_success(self, processor, sample_invoice_state):
            """Test successful document parsing."""
            # Mock extraction result
            mock_extraction = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}],
                "overall_confidence": 0.95,
                "metadata": {"parser_version": "1.0", "pages_processed": 1}
            }

            with patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
                 patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
                 patch.object(processor, '_update_invoice_status'), \
                 patch.object(processor, '_save_extraction_result'), \
                 patch('app.workflows.invoice_processor.AsyncSessionLocal'):

                result = await processor._parse_document(sample_invoice_state)

                assert result["current_step"] == "parsed"
                assert result["status"] == "processing"
                assert result["extraction_result"] == mock_extraction
                assert result["confidence_score"] == 0.95

        @pytest.mark.asyncio
        async def test_parse_failure(self, processor, sample_invoice_state):
            """Test handling of parsing failure."""
            with patch.object(processor.docling_service, 'extract_from_content',
                             side_effect=ExtractionException("Parsing failed")):

                result = await processor._parse_document(sample_invoice_state)

                assert result["current_step"] == "parse_failed"
                assert result["status"] == "error"
                assert "Parsing failed" in result["error_message"]

    class TestPatchNode:
        """Test the low-confidence patching node."""

        @pytest.mark.asyncio
        async def test_patch_above_threshold(self, processor, sample_invoice_state):
            """Test patching when confidence is above threshold."""
            sample_invoice_state["confidence_score"] = 0.95
            sample_invoice_state["extraction_result"] = {
                "header": {"total": "100.00"},
                "lines": []
            }

            result = await processor._patch_low_confidence(sample_invoice_state)

            assert result["current_step"] == "patch_skipped"
            assert result["status"] == "processing"
            # Should not call LLM service

        @pytest.mark.asyncio
        async def test_patch_below_threshold(self, processor, sample_invoice_state):
            """Test patching when confidence is below threshold."""
            sample_invoice_state["confidence_score"] = 0.70
            sample_invoice_state["extraction_result"] = {
                "header": {"total": "100.00"},
                "lines": []
            }

            mock_patched_result = {
                "header": {"total": "150.00"},  # Corrected amount
                "lines": [],
                "overall_confidence": 0.92
            }

            with patch.object(processor.llm_service, 'patch_low_confidence_fields',
                             return_value=mock_patched_result):

                result = await processor._patch_low_confidence(sample_invoice_state)

                assert result["current_step"] == "patched"
                assert result["status"] == "processing"
                assert result["confidence_score"] == 0.92
                assert result["extraction_result"]["header"]["total"] == "150.00"

    class TestValidateNode:
        """Test the invoice validation node."""

        @pytest.mark.asyncio
        async def test_validation_success(self, processor, sample_invoice_state):
            """Test successful invoice validation."""
            sample_invoice_state["extraction_result"] = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}]
            }

            mock_validation_result = {
                "passed": True,
                "total_issues": 0,
                "error_count": 0,
                "warning_count": 0,
                "confidence_score": 0.95,
                "issues": [],
                "check_results": {}
            }

            with patch.object(processor.validation_service, 'validate_invoice',
                             return_value=mock_validation_result):

                result = await processor._validate_invoice(sample_invoice_state)

                assert result["current_step"] == "validated"
                assert result["status"] == "processing"
                assert result["validation_result"]["passed"] is True
                assert result["requires_human_review"] is False

        @pytest.mark.asyncio
        async def test_validation_failure(self, processor, sample_invoice_state):
            """Test handling of validation failure."""
            sample_invoice_state["extraction_result"] = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}]
            }

            mock_validation_result = {
                "passed": False,
                "total_issues": 2,
                "error_count": 2,
                "warning_count": 0,
                "confidence_score": 0.60,
                "issues": [
                    {"code": "VENDOR_NOT_FOUND", "severity": "ERROR"},
                    {"code": "DUPLICATE_INVOICE", "severity": "ERROR"}
                ],
                "check_results": {}
            }

            with patch.object(processor.validation_service, 'validate_invoice',
                             return_value=mock_validation_result), \
                 patch.object(processor.exception_service, 'create_exception_from_validation',
                             return_value=[MagicMock(id="exc_001"), MagicMock(id="exc_002")]):

                result = await processor._validate_invoice(sample_invoice_state)

                assert result["current_step"] == "validated"
                assert result["status"] == "exception"
                assert result["requires_human_review"] is True
                assert len(result["exception_ids"]) == 2

    class TestTriageNode:
        """Test the triage decision node."""

        @pytest.mark.asyncio
        async def test_triage_auto_approve(self, processor, sample_invoice_state):
            """Test triage resulting in auto-approval."""
            sample_invoice_state["validation_result"] = {
                "passed": True,
                "error_count": 0
            }
            sample_invoice_state["confidence_score"] = 0.95

            result = await processor._triage_results(sample_invoice_state)

            assert result["current_step"] == "triaged"
            assert result["status"] == "ready"
            assert result["requires_human_review"] is False

        @pytest.mark.asyncio
        async def test_triage_human_review(self, processor, sample_invoice_state):
            """Test triage resulting in human review."""
            sample_invoice_state["validation_result"] = {
                "passed": False,
                "error_count": 3
            }
            sample_invoice_state["confidence_score"] = 0.70
            sample_invoice_state["exceptions"] = [
                {"severity": "ERROR", "auto_resolution_possible": False}
            ]

            result = await processor._triage_results(sample_invoice_state)

            assert result["current_step"] == "triaged"
            assert result["status"] == "exception"
            assert result["requires_human_review"] is True
            assert result["human_review_reason"] is not None

    class TestStageExportNode:
        """Test the stage export node."""

        @pytest.mark.asyncio
        async def test_stage_export_success(self, processor, sample_invoice_state):
            """Test successful export staging."""
            sample_invoice_state["extraction_result"] = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}]
            }
            sample_invoice_state["confidence_score"] = 0.95

            mock_export_content = '{"invoice_id": "test", "header": {}, "lines": []}'

            with patch.object(processor.export_service, 'export_to_json',
                             return_value=mock_export_content):

                result = await processor._stage_export(sample_invoice_state)

                assert result["current_step"] == "export_staged"
                assert result["status"] == "staged"
                assert result["export_ready"] is True
                assert result["export_payload"] is not None

    class TestErrorHandling:
        """Test error handling and recovery mechanisms."""

        @pytest.mark.asyncio
        async def test_error_handler_retry(self, processor, sample_invoice_state):
            """Test error handler routing to retry."""
            sample_invoice_state["error_details"] = {
                "error_type": "ExtractionException",
                "recovery_possible": True
            }
            sample_invoice_state["retry_count"] = 1
            sample_invoice_state["max_retries"] = 3

            result = await processor._handle_error(sample_invoice_state)

            assert result["status"] == "retry"

        @pytest.mark.asyncio
        async def test_error_handler_escalate(self, processor, sample_invoice_state):
            """Test error handler routing to escalation."""
            sample_invoice_state["error_details"] = {
                "error_type": "ValidationException",
                "recovery_possible": False
            }
            sample_invoice_state["retry_count"] = 3
            sample_invoice_state["max_retries"] = 3

            result = await processor._handle_error(sample_invoice_state)

            assert result["status"] == "escalate"

    class TestRoutingLogic:
        """Test conditional routing logic."""

        def test_triage_routing_to_export(self, processor, sample_invoice_state):
            """Test triage routing to export when ready."""
            sample_invoice_state["status"] = "ready"
            sample_invoice_state["requires_human_review"] = False

            route = processor._triage_routing(sample_invoice_state)

            assert route == "stage_export"

        def test_triage_routing_to_human_review(self, processor, sample_invoice_state):
            """Test triage routing to human review."""
            sample_invoice_state["requires_human_review"] = True

            route = processor._triage_routing(sample_invoice_state)

            assert route == "human_review"

        def test_triage_routing_to_error_handler(self, processor, sample_invoice_state):
            """Test triage routing to error handler."""
            sample_invoice_state["status"] = "error"

            route = processor._triage_routing(sample_invoice_state)

            assert route == "error_handler"

    class TestEndToEndWorkflow:
        """Test the complete end-to-end workflow."""

        @pytest.mark.asyncio
        @pytest.mark.integration
        async def test_successful_workflow(self, processor, temp_pdf_file):
            """Test complete successful workflow execution."""
            invoice_id = str(uuid.uuid4())

            # Mock all service calls for successful execution
            mock_extraction = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}],
                "overall_confidence": 0.95,
                "metadata": {"parser_version": "1.0", "pages_processed": 1}
            }

            mock_validation = {
                "passed": True,
                "total_issues": 0,
                "error_count": 0,
                "warning_count": 0,
                "confidence_score": 0.95,
                "issues": [],
                "check_results": {}
            }

            with patch.object(processor.storage_service, 'file_exists', return_value=True), \
                 patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
                 patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
                 patch.object(processor.validation_service, 'validate_invoice', return_value=mock_validation), \
                 patch.object(processor.export_service, 'export_to_json', return_value='{"test": "export"}'), \
                 patch.object(processor, '_update_invoice_status'), \
                 patch.object(processor, '_save_extraction_result'), \
                 patch.object(processor, '_save_validation_result'), \
                 patch.object(processor, '_save_staged_export'):

                result = await processor.process_invoice(
                    invoice_id=invoice_id,
                    file_path=temp_pdf_file
                )

                assert result["status"] in ["staged", "ready"]
                assert result["current_step"] == "export_staged"
                assert result["export_ready"] is True
                assert len(result["processing_history"]) >= 6  # All 6 stages completed

        @pytest.mark.asyncio
        @pytest.mark.integration
        async def test_workflow_with_human_review(self, processor, temp_pdf_file):
            """Test workflow that requires human review."""
            invoice_id = str(uuid.uuid4())

            # Mock service calls that result in human review
            mock_extraction = {
                "header": {"invoice_number": "INV-001", "total": "100.00"},
                "lines": [{"description": "Item 1", "amount": "100.00"}],
                "overall_confidence": 0.85,
                "metadata": {"parser_version": "1.0", "pages_processed": 1}
            }

            mock_validation = {
                "passed": False,
                "total_issues": 2,
                "error_count": 2,
                "warning_count": 0,
                "confidence_score": 0.70,
                "issues": [
                    {"code": "VENDOR_NOT_FOUND", "severity": "ERROR", "auto_resolution_possible": False},
                    {"code": "INVALID_AMOUNT", "severity": "ERROR", "auto_resolution_possible": False}
                ],
                "check_results": {}
            }

            with patch.object(processor.storage_service, 'file_exists', return_value=True), \
                 patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
                 patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
                 patch.object(processor.validation_service, 'validate_invoice', return_value=mock_validation), \
                 patch.object(processor.exception_service, 'create_exception_from_validation',
                             return_value=[MagicMock(id="exc_001"), MagicMock(id="exc_002")]), \
                 patch.object(processor, '_update_invoice_status'), \
                 patch.object(processor, '_save_extraction_result'), \
                 patch.object(processor, '_save_validation_result'):

                result = await processor.process_invoice(
                    invoice_id=invoice_id,
                    file_path=temp_pdf_file
                )

                assert result["status"] == "exception"
                assert result["requires_human_review"] is True
                assert result["human_review_reason"] is not None
                assert len(result["exception_ids"]) == 2

    class TestWorkflowResume:
        """Test workflow resumption after human review."""

        @pytest.mark.asyncio
        async def test_resume_workflow_after_approval(self, processor, sample_invoice_state):
            """Test resuming workflow after human approval."""
            workflow_id = sample_invoice_state["workflow_id"]

            human_decision = {
                "action": "continue",
                "notes": "Reviewed and approved",
                "corrections": {}
            }

            # Mock checkpointer state retrieval
            mock_state_snapshot = MagicMock()
            mock_state_snapshot.values = sample_invoice_state
            mock_state_snapshot.values["interrupt_data"] = {
                "human_action": "continue",
                "human_notes": "Reviewed and approved",
                "human_corrections": {}
            }

            with patch.object(processor.checkpointer, 'aget', return_value=mock_state_snapshot), \
                 patch.object(processor.runner, 'ainvoke', return_value={**sample_invoice_state, "status": "staged"}):

                result = await processor.resume_workflow(workflow_id, human_decision)

                assert result["status"] == "staged"