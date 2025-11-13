"""
End-to-End Integration Tests

Comprehensive integration tests that validate the complete AP Intake & Validation
workflow from file upload through processing, validation, and export.
"""

import asyncio
import json
import uuid
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_async_session
from app.main import app
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ingestion import IngestionJob, IngestionStatus
from app.models.validation import ValidationSession, ValidationRule
from app.models.extraction import ExtractionSession, FieldExtraction
from app.services.test_data_service import TestDataGenerator, TestScenario
from app.services.invoice_seeding_service import InvoiceSeedingService


class TestEndToEndWorkflow:
    """Test complete end-to-end invoice processing workflow"""

    @pytest.fixture
    async def test_client(self):
        """Test client for API calls"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def test_data_generator(self):
        """Test data generator fixture"""
        return TestDataGenerator()

    @pytest.fixture
    async def sample_invoice_pdf(self, test_data_generator):
        """Generate a sample invoice PDF for testing"""
        template = test_data_generator.pdf_generator

        # Create a simple invoice template
        from app.services.test_data_service import InvoiceTemplate
        invoice_template = InvoiceTemplate(
            vendor_name="Test Vendor Corp",
            vendor_address="123 Test St\nTest City, TS 12345",
            vendor_tax_id="12-3456789",
            customer_name="Test Customer",
            customer_address="456 Customer Ave\nCustomer City, CC 67890",
            invoice_number="TEST-001",
            invoice_date=datetime.now(),
            due_date=datetime.now() + timedelta(days=30),
            items=[
                {
                    "description": "Test Service",
                    "quantity": 1,
                    "unit_price": Decimal("100.00"),
                    "amount": Decimal("100.00")
                }
            ],
            subtotal=Decimal("100.00"),
            tax_rate=Decimal("0.08"),
            tax_amount=Decimal("8.00"),
            total_amount=Decimal("108.00"),
            currency="USD"
        )

        # Generate PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            filepath = template.generate_invoice_pdf(invoice_template, Path(tmp_file.name).name)
            return filepath

    @pytest.mark.asyncio
    async def test_complete_invoice_processing_workflow(self, test_client, sample_invoice_pdf):
        """Test complete workflow from upload to processed status"""
        # Step 1: Upload invoice
        with open(sample_invoice_pdf, 'rb') as f:
            upload_response = await test_client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("test_invoice.pdf", f, "application/pdf")},
                data={
                    "source_type": "test",
                    "source_reference": "e2e_test",
                    "uploaded_by": "test_user"
                }
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        assert "ingestion_job_id" in upload_data
        assert "invoice_id" in upload_data

        ingestion_job_id = upload_data["ingestion_job_id"]
        invoice_id = upload_data["invoice_id"]

        # Step 2: Monitor processing status
        max_attempts = 30  # 30 seconds timeout
        for attempt in range(max_attempts):
            status_response = await test_client.get(f"/api/v1/ingestion/status/{ingestion_job_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()
            processing_status = status_data.get("status")

            if processing_status == "completed":
                break
            elif processing_status == "failed":
                pytest.fail(f"Invoice processing failed: {status_data.get('error_message', 'Unknown error')}")

            await asyncio.sleep(1)
        else:
            pytest.fail("Invoice processing timed out")

        # Step 3: Verify invoice data
        invoice_response = await test_client.get(f"/api/v1/invoices/{invoice_id}")
        assert invoice_response.status_code == 200

        invoice_data = invoice_response.json()
        assert invoice_data["invoice_number"] is not None
        assert invoice_data["vendor_name"] is not None
        assert invoice_data["total_amount"] is not None
        assert invoice_data["status"] in ["processed", "needs_review", "exception"]

        # Step 4: Check extraction results
        extraction_response = await test_client.get(f"/api/v1/invoices/{invoice_id}/extractions")
        assert extraction_response.status_code == 200

        extraction_data = extraction_response.json()
        assert len(extraction_data["field_extractions"]) > 0

        # Step 5: Check validation results
        validation_response = await test_client.get(f"/api/v1/invoices/{invoice_id}/validations")
        assert validation_response.status_code == 200

        validation_data = validation_response.json()
        assert "validation_session" in validation_data
        assert "rule_results" in validation_data

        # Step 6: Check if export is ready
        export_response = await test_client.get(f"/api/v1/invoices/{invoice_id}/export/status")
        assert export_response.status_code == 200

        export_data = export_response.json()
        assert "export_ready" in export_data

        print(f"✅ End-to-end workflow test passed for invoice {invoice_id}")

    @pytest.mark.asyncio
    async def test_batch_invoice_processing(self, test_client, test_data_generator):
        """Test processing multiple invoices in batch"""
        # Generate multiple test invoices
        test_scenarios = test_data_generator._generate_standard_invoices(5)

        # Upload all invoices
        uploaded_invoices = []
        for scenario in test_scenarios:
            # Generate PDF for this scenario
            filepath = test_data_generator.pdf_generator.output_dir / scenario.file_name
            if not filepath.exists():
                # Generate the PDF if it doesn't exist
                # This is a simplified approach - in real implementation,
                # we'd use the actual template data
                continue

            with open(filepath, 'rb') as f:
                upload_response = await test_client.post(
                    "/api/v1/ingestion/upload",
                    files={"file": (scenario.file_name, f, "application/pdf")},
                    data={
                        "source_type": "batch_test",
                        "source_reference": f"batch_{scenario.scenario_id}",
                        "uploaded_by": "test_user"
                    }
                )

                if upload_response.status_code == 200:
                    upload_data = upload_response.json()
                    uploaded_invoices.append({
                        "scenario_id": scenario.scenario_id,
                        "invoice_id": upload_data["invoice_id"],
                        "ingestion_job_id": upload_data["ingestion_job_id"]
                    })

        assert len(uploaded_invoices) > 0, "No invoices were successfully uploaded"

        # Wait for all invoices to process
        max_attempts = 60  # 60 seconds timeout
        for attempt in range(max_attempts):
            completed_count = 0
            for invoice in uploaded_invoices:
                status_response = await test_client.get(f"/api/v1/ingestion/status/{invoice['ingestion_job_id']}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get("status") == "completed":
                        completed_count += 1
                    elif status_data.get("status") == "failed":
                        print(f"⚠️ Invoice {invoice['invoice_id']} failed processing")

            if completed_count == len(uploaded_invoices):
                break

            await asyncio.sleep(1)
        else:
            pytest.fail(f"Batch processing timed out. Only {completed_count}/{len(uploaded_invoices)} completed.")

        # Verify results
        processed_count = 0
        for invoice in uploaded_invoices:
            invoice_response = await test_client.get(f"/api/v1/invoices/{invoice['invoice_id']}")
            if invoice_response.status_code == 200:
                invoice_data = invoice_response.json()
                if invoice_data["status"] in ["processed", "needs_review", "exception"]:
                    processed_count += 1

        assert processed_count == len(uploaded_invoices), "Not all invoices were processed successfully"
        print(f"✅ Batch processing test passed for {len(uploaded_invoices)} invoices")

    @pytest.mark.asyncio
    async def test_invoice_duplicate_detection(self, test_client, sample_invoice_pdf):
        """Test duplicate invoice detection"""
        # Upload first invoice
        with open(sample_invoice_pdf, 'rb') as f:
            first_upload = await test_client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("original.pdf", f, "application/pdf")},
                data={"source_type": "duplicate_test", "uploaded_by": "test_user"}
            )

        assert first_upload.status_code == 200
        first_invoice_id = first_upload.json()["invoice_id"]

        # Wait for first invoice to process
        await self._wait_for_processing(test_client, first_upload.json()["ingestion_job_id"])

        # Upload the same invoice again (should detect duplicate)
        with open(sample_invoice_pdf, 'rb') as f:
            duplicate_upload = await test_client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("duplicate.pdf", f, "application/pdf")},
                data={"source_type": "duplicate_test", "uploaded_by": "test_user"}
            )

        assert duplicate_upload.status_code == 200
        duplicate_invoice_id = duplicate_upload.json()["invoice_id"]

        # Wait for duplicate invoice to process
        await self._wait_for_processing(test_client, duplicate_upload.json()["ingestion_job_id"])

        # Check duplicate detection
        duplicate_response = await test_client.get(f"/api/v1/invoices/{duplicate_invoice_id}")
        assert duplicate_response.status_code == 200

        duplicate_data = duplicate_response.json()
        # The duplicate should be flagged
        assert duplicate_data["status"] in ["duplicate", "needs_review", "exception"]

        # Check duplicates endpoint
        duplicates_response = await test_client.get(f"/api/v1/invoices/{first_invoice_id}/duplicates")
        assert duplicates_response.status_code == 200

        duplicates_data = duplicates_response.json()
        assert len(duplicates_data["duplicates"]) > 0

        print(f"✅ Duplicate detection test passed")

    @pytest.mark.asyncio
    async def test_invoice_exception_handling(self, test_client, test_data_generator):
        """Test invoice exception handling workflow"""
        # Generate an invoice that should trigger an exception
        exception_scenarios = test_data_generator._generate_exception_cases(1)
        scenario = exception_scenarios[0]

        # Generate PDF for this exception scenario
        filepath = test_data_generator.pdf_generator.output_dir / scenario.file_name
        if not filepath.exists():
            pytest.skip(f"Exception scenario PDF not found: {scenario.file_name}")

        # Upload exception invoice
        with open(filepath, 'rb') as f:
            upload_response = await test_client.post(
                "/api/v1/ingestion/upload",
                files={"file": (scenario.file_name, f, "application/pdf")},
                data={
                    "source_type": "exception_test",
                    "source_reference": scenario.scenario_id,
                    "uploaded_by": "test_user"
                }
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        invoice_id = upload_data["invoice_id"]

        # Wait for processing
        await self._wait_for_processing(test_client, upload_data["ingestion_job_id"])

        # Check invoice status
        invoice_response = await test_client.get(f"/api/v1/invoices/{invoice_id}")
        assert invoice_response.status_code == 200

        invoice_data = invoice_response.json()
        # Should be in exception or needs_review status
        assert invoice_data["status"] in ["exception", "needs_review"]

        # Check for exception details
        if invoice_data["status"] == "exception":
            exceptions_response = await test_client.get(f"/api/v1/invoices/{invoice_id}/exceptions")
            assert exceptions_response.status_code == 200

            exceptions_data = exceptions_response.json()
            assert len(exceptions_data["exceptions"]) > 0

            # Test exception resolution
            exception_id = exceptions_data["exceptions"][0]["id"]
            resolution_response = await test_client.post(
                f"/api/v1/exceptions/{exception_id}/resolve",
                json={
                    "resolution_method": "manual_correction",
                    "resolution_notes": "Test exception resolution",
                    "assign_to": "test_user"
                }
            )
            assert resolution_response.status_code == 200

        print(f"✅ Exception handling test passed for scenario: {scenario.scenario_id}")

    @pytest.mark.asyncio
    async def test_invoice_export_functionality(self, test_client, sample_invoice_pdf):
        """Test invoice export functionality"""
        # Upload and process invoice
        with open(sample_invoice_pdf, 'rb') as f:
            upload_response = await test_client.post(
                "/api/v1/ingestion/upload",
                files={"file": ("export_test.pdf", f, "application/pdf")},
                data={"source_type": "export_test", "uploaded_by": "test_user"}
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        invoice_id = upload_data["invoice_id"]

        # Wait for processing
        await self._wait_for_processing(test_client, upload_data["ingestion_job_id"])

        # Request export
        export_response = await test_client.post(
            f"/api/v1/invoices/{invoice_id}/export",
            json={
                "export_format": "json",
                "destination": "quickbooks"
            }
        )
        assert export_response.status_code == 200

        export_data = export_response.json()
        assert "export_job_id" in export_data

        # Monitor export status
        export_job_id = export_data["export_job_id"]
        max_attempts = 30
        for attempt in range(max_attempts):
            status_response = await test_client.get(f"/api/v1/exports/{export_job_id}/status")
            assert status_response.status_code == 200

            status_data = status_response.json()
            export_status = status_data.get("status")

            if export_status == "completed":
                break
            elif export_status == "failed":
                pytest.fail(f"Export failed: {status_data.get('error_message', 'Unknown error')}")

            await asyncio.sleep(1)
        else:
            pytest.fail("Export processing timed out")

        # Download export
        download_response = await test_client.get(f"/api/v1/exports/{export_job_id}/download")
        assert download_response.status_code == 200

        # Verify export content
        export_content = download_response.content
        assert len(export_content) > 0

        print(f"✅ Export functionality test passed")

    async def _wait_for_processing(self, test_client, ingestion_job_id: int, timeout: int = 60):
        """Wait for invoice processing to complete"""
        max_attempts = timeout
        for attempt in range(max_attempts):
            status_response = await test_client.get(f"/api/v1/ingestion/status/{ingestion_job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data.get("status") in ["completed", "failed"]:
                    return status_data

            await asyncio.sleep(1)

        raise TimeoutError(f"Processing timeout for ingestion job {ingestion_job_id}")


class TestDatabaseSeeding:
    """Test database seeding functionality"""

    @pytest.mark.asyncio
    async def test_test_data_seeding(self):
        """Test seeding test data into database"""
        seeder = InvoiceSeedingService()

        # Clear existing test data
        await seeder.clear_test_data()

        # Generate test data
        generator = TestDataGenerator()
        test_scenarios = generator.generate_all_test_data()
        assert len(test_scenarios["scenarios"]) > 0

        # Seed database with a subset of scenarios
        categories = ["standard_invoices", "exception_cases"]
        result = await seeder.seed_database(categories=categories, limit=10)

        assert len(result["seeded_scenarios"]) > 0
        assert result["statistics"]["total_scenarios"] <= 10

        # Verify data was seeded correctly
        stats = await seeder.get_seeding_statistics()
        assert stats["total_test_invoices"] > 0

        print(f"✅ Database seeding test passed")

    @pytest.mark.asyncio
    async def test_seeding_statistics(self):
        """Test seeding statistics functionality"""
        seeder = InvoiceSeedingService()

        # Get statistics
        stats = await seeder.get_seeding_statistics()

        assert "total_test_invoices" in stats
        assert "categories" in stats
        assert "statuses" in stats

        print(f"✅ Seeding statistics test passed")


class TestAPIEndpoints:
    """Test individual API endpoints"""

    @pytest.fixture
    async def test_client(self):
        """Test client for API calls"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        """Test health check endpoint"""
        response = await test_client.get("/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert health_data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_api_info(self, test_client):
        """Test API info endpoint"""
        response = await test_client.get("/api/v1/info")
        assert response.status_code == 200

        info_data = response.json()
        assert "version" in info_data
        assert "name" in info_data

    @pytest.mark.asyncio
    async def test_invoice_list(self, test_client):
        """Test invoice list endpoint"""
        response = await test_client.get("/api/v1/invoices")
        assert response.status_code == 200

        invoices_data = response.json()
        assert "invoices" in invoices_data
        assert "pagination" in invoices_data

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint"""
        response = await test_client.get("/metrics")
        # Metrics endpoint might return different status codes depending on configuration
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_validation_rules(self, test_client):
        """Test validation rules endpoint"""
        response = await test_client.get("/api/v1/validation/rules")
        assert response.status_code == 200

        rules_data = response.json()
        assert "rules" in rules_data

    @pytest.mark.asyncio
    async def test_exception_management(self, test_client):
        """Test exception management endpoints"""
        # List exceptions
        response = await test_client.get("/api/v1/exceptions")
        assert response.status_code == 200

        exceptions_data = response.json()
        assert "exceptions" in exceptions_data

        # Get exception types
        response = await test_client.get("/api/v1/exceptions/types")
        assert response.status_code == 200

        types_data = response.json()
        assert "exception_types" in types_data


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])