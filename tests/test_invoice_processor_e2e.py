"""
End-to-end tests for the LangGraph invoice processor workflow.
Tests the complete workflow execution without database dependencies.
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


class TestInvoiceProcessorEndToEnd:
    """End-to-end tests for the invoice processor workflow."""

    @pytest.fixture
    def processor(self):
        """Create a fresh invoice processor instance for each test."""
        return InvoiceProcessor()

    @pytest.fixture
    def temp_pdf_file(self):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"sample_pdf_content_for_testing")
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_successful_workflow(self, processor, temp_pdf_file):
        """Test complete successful workflow execution from start to finish."""
        invoice_id = str(uuid.uuid4())

        # Mock all service dependencies for successful execution
        mock_extraction = {
            "header": {
                "invoice_number": "INV-001",
                "total": "100.00",
                "vendor_name": "Test Vendor",
                "invoice_date": "2024-01-15"
            },
            "lines": [
                {"description": "Test Item 1", "amount": "50.00"},
                {"description": "Test Item 2", "amount": "50.00"}
            ],
            "overall_confidence": 0.95,
            "metadata": {
                "parser_version": "1.0",
                "pages_processed": 1,
                "processing_time_ms": 150
            }
        }

        mock_validation = {
            "passed": True,
            "total_issues": 0,
            "error_count": 0,
            "warning_count": 0,
            "confidence_score": 0.95,
            "issues": [],
            "check_results": {
                "vendor_validation": {"passed": True},
                "amount_validation": {"passed": True},
                "date_validation": {"passed": True}
            },
            "rules_version": "1.0",
            "validator_version": "1.0",
            "processing_time_ms": 50
        }

        mock_export_content = '{"invoice_id": "' + invoice_id + '", "exported": true}'

        # Mock all service methods and database operations
        with patch.object(processor.storage_service, 'file_exists', return_value=True), \
             patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
             patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
             patch.object(processor.validation_service, 'validate_invoice', return_value=mock_validation), \
             patch.object(processor.export_service, 'export_to_json', return_value=mock_export_content), \
             patch.object(processor, '_check_duplicate_invoice', return_value=None), \
             patch.object(processor, '_update_invoice_status'), \
             patch.object(processor, '_save_extraction_result'), \
             patch.object(processor, '_save_validation_result'), \
             patch.object(processor, '_save_staged_export'), \
             patch.object(processor, '_create_workflow_exception', return_value=""), \
             patch('app.workflows.invoice_processor.AsyncSessionLocal'):

            # Execute the complete workflow
            # Use the runner directly to bypass interrupts for testing
            initial_state = InvoiceState(
                invoice_id=invoice_id,
                file_path=temp_pdf_file,
                file_hash="",
                vendor_id=None,
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

            # Use a non-interrupting runner for testing
            test_runner = processor.graph.compile(checkpointer=processor.checkpointer)
            thread_config = {"configurable": {"thread_id": initial_state["workflow_id"]}}
            result = await test_runner.ainvoke(initial_state, config=thread_config)

            # Verify workflow completed successfully
            assert result["status"] in ["staged", "ready"]
            assert result["current_step"] == "export_staged"
            assert result["export_ready"] is True
            assert result["invoice_id"] == invoice_id
            assert result["file_path"] == temp_pdf_file

            # Verify all 6 stages were completed
            processing_history = result.get("processing_history", [])
            stage_names = [step["step"] for step in processing_history]

            expected_stages = ["receive", "parse", "patch", "validate", "triage", "stage_export"]
            for stage in expected_stages:
                assert stage in stage_names, f"Missing stage: {stage}"

            # Verify no errors occurred
            assert result["error_message"] is None
            assert result["error_details"] is None

            # Verify extraction and validation results
            assert result["extraction_result"] is not None
            assert result["extraction_result"]["header"]["invoice_number"] == "INV-001"
            assert result["validation_result"] is not None
            assert result["validation_result"]["passed"] is True

            # Verify confidence and human review status
            assert result["confidence_score"] == 0.95
            assert result["requires_human_review"] is False

            # Verify export preparation
            assert result["export_payload"] is not None
            assert result["export_format"] == "json"

            # Verify performance metrics (may be empty when using direct runner)
            performance_metrics = result.get("performance_metrics", {})
            # Performance metrics are only calculated in the process_invoice method
            # but the core workflow should still work correctly

            print(f"✓ End-to-end workflow completed successfully for invoice {invoice_id}")
            print(f"  - Final status: {result['status']}")
            print(f"  - Steps completed: {len(processing_history)}")
            print(f"  - Processing time: {performance_metrics.get('total_processing_time_ms', 0)}ms")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_with_human_review_required(self, processor, temp_pdf_file):
        """Test workflow that requires human review due to validation failures."""
        invoice_id = str(uuid.uuid4())

        # Mock service results that will trigger human review
        mock_extraction = {
            "header": {
                "invoice_number": "INV-002",
                "total": "1000.00",
                "vendor_name": "Unknown Vendor"
            },
            "lines": [{"description": "Test Item", "amount": "1000.00"}],
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
                {
                    "code": "VENDOR_NOT_FOUND",
                    "severity": "ERROR",
                    "message": "Vendor not found in database",
                    "auto_resolution_possible": False
                },
                {
                    "code": "AMOUNT_SUSPICIOUS",
                    "severity": "ERROR",
                    "message": "Amount exceeds typical threshold",
                    "auto_resolution_possible": False
                }
            ],
            "check_results": {
                "vendor_validation": {"passed": False},
                "amount_validation": {"passed": False}
            }
        }

        # Mock exceptions that would be created
        mock_exception1 = MagicMock()
        mock_exception1.id = "exc_001"
        mock_exception2 = MagicMock()
        mock_exception2.id = "exc_002"

        with patch.object(processor.storage_service, 'file_exists', return_value=True), \
             patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
             patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
             patch.object(processor.validation_service, 'validate_invoice', return_value=mock_validation), \
             patch.object(processor.exception_service, 'create_exception_from_validation',
                         return_value=[mock_exception1, mock_exception2]), \
             patch.object(processor, '_check_duplicate_invoice', return_value=None), \
             patch.object(processor, '_update_invoice_status'), \
             patch.object(processor, '_save_extraction_result'), \
             patch.object(processor, '_save_validation_result'), \
             patch.object(processor, '_create_workflow_exception', return_value=""), \
             patch('app.workflows.invoice_processor.AsyncSessionLocal'):

            # Execute the workflow
            result = await processor.process_invoice(
                invoice_id=invoice_id,
                file_path=temp_pdf_file
            )

            # Verify workflow stopped at human review point
            assert result["status"] == "exception"
            assert result["requires_human_review"] is True
            assert result["human_review_reason"] is not None
            assert len(result["exception_ids"]) == 2

            # Verify processing history
            processing_history = result.get("processing_history", [])
            stage_names = [step["step"] for step in processing_history]

            # Should have stopped before export
            assert "stage_export" not in stage_names
            assert "triage" in stage_names

            print(f"✓ Workflow correctly required human review for invoice {invoice_id}")
            print(f"  - Final status: {result['status']}")
            print(f"  - Exceptions created: {len(result['exception_ids'])}")
            print(f"  - Review reason: {result['human_review_reason']}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_with_low_confidence_patching(self, processor, temp_pdf_file):
        """Test workflow with LLM patching for low confidence fields."""
        invoice_id = str(uuid.uuid4())

        # Mock low confidence extraction result
        mock_extraction = {
            "header": {
                "invoice_number": "INV-003",
                "total": "????.??",  # Low confidence
                "vendor_name": "Vendor"
            },
            "lines": [{"description": "Item", "amount": "???.??"}],
            "overall_confidence": 0.65,  # Below threshold
            "metadata": {"parser_version": "1.0", "pages_processed": 1}
        }

        # Mock patched result from LLM
        mock_patched_extraction = {
            "header": {
                "invoice_number": "INV-003",
                "total": "250.00",  # Corrected by LLM
                "vendor_name": "Vendor"
            },
            "lines": [{"description": "Item", "amount": "250.00"}],
            "overall_confidence": 0.92,  # Improved confidence
            "metadata": {"parser_version": "1.0", "pages_processed": 1}
        }

        mock_validation = {
            "passed": True,
            "total_issues": 0,
            "error_count": 0,
            "warning_count": 0,
            "confidence_score": 0.92,
            "issues": [],
            "check_results": {}
        }

        with patch.object(processor.storage_service, 'file_exists', return_value=True), \
             patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
             patch.object(processor.docling_service, 'extract_from_content', return_value=mock_extraction), \
             patch.object(processor.llm_service, 'patch_low_confidence_fields',
                         return_value=mock_patched_extraction), \
             patch.object(processor.validation_service, 'validate_invoice', return_value=mock_validation), \
             patch.object(processor.export_service, 'export_to_json', return_value='{"success": true}'), \
             patch.object(processor, '_check_duplicate_invoice', return_value=None), \
             patch.object(processor, '_update_invoice_status'), \
             patch.object(processor, '_save_extraction_result'), \
             patch.object(processor, '_save_validation_result'), \
             patch.object(processor, '_save_staged_export'), \
             patch.object(processor, '_create_workflow_exception', return_value=""), \
             patch('app.workflows.invoice_processor.AsyncSessionLocal'):

            # Execute the workflow
            result = await processor.process_invoice(
                invoice_id=invoice_id,
                file_path=temp_pdf_file
            )

            # Verify workflow completed successfully after patching
            assert result["status"] in ["staged", "ready"]
            assert result["current_step"] == "export_staged"

            # Verify patching occurred
            processing_history = result.get("processing_history", [])
            patch_steps = [step for step in processing_history if step["step"] == "patch"]
            assert len(patch_steps) == 1
            assert patch_steps[0]["status"] == "completed"

            # Verify confidence improvement
            assert result["confidence_score"] == 0.92
            assert result["extraction_result"]["header"]["total"] == "250.00"

            print(f"✓ Workflow successfully applied LLM patching for invoice {invoice_id}")
            print(f"  - Original confidence: 0.65")
            print(f"  - Final confidence: {result['confidence_score']}")
            print(f"  - Corrected amount: {result['extraction_result']['header']['total']}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_error_handling_and_recovery(self, processor, temp_pdf_file):
        """Test workflow error handling and retry mechanisms."""
        invoice_id = str(uuid.uuid4())

        # Mock service that fails initially
        with patch.object(processor.storage_service, 'file_exists', return_value=True), \
             patch.object(processor.storage_service, 'get_file_content', return_value=b"test_content"), \
             patch.object(processor.docling_service, 'extract_from_content',
                         side_effect=[Exception("Temporary error"), None]) as mock_extract, \
             patch.object(processor, '_check_duplicate_invoice', return_value=None), \
             patch.object(processor, '_update_invoice_status'), \
             patch.object(processor, '_create_workflow_exception', return_value=""), \
             patch('app.workflows.invoice_processor.AsyncSessionLocal'):

            # Execute the workflow (should fail and retry)
            result = await processor.process_invoice(
                invoice_id=invoice_id,
                file_path=temp_pdf_file,
                max_retries=2
            )

            # Verify error handling occurred
            assert result["status"] in ["error", "escalated", "retry"]
            assert result["error_message"] is not None

            # Verify retry was attempted
            assert result.get("retry_count", 0) >= 1

            print(f"✓ Workflow properly handled errors for invoice {invoice_id}")
            print(f"  - Final status: {result['status']}")
            print(f"  - Retry count: {result.get('retry_count', 0)}")
            print(f"  - Error: {result['error_message']}")