"""
Integration tests for invoice API endpoints.
"""

import asyncio
import io
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.models.invoice import Invoice, InvoiceStatus
from app.services.storage_service import StorageService
from tests.factories import InvoiceFactory, VendorFactory


class TestInvoiceUploadEndpoint:
    """Test suite for invoice upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_invoice_success(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test successful invoice upload."""
        # Create test file content
        pdf_content = b"%PDF-1.4\nfake pdf content for testing"
        file_data = io.BytesIO(pdf_content)
        files = {"file": ("test_invoice.pdf", file_data, "application/pdf")}

        # Mock storage service
        with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
            mock_storage.return_value = {"file_path": "/tmp/test_invoice.pdf"}

            # Mock Celery task
            with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                mock_task.delay.return_value = AsyncMock(id="test-task-id")

                response = await async_client.post("/api/v1/invoices/upload", files=files)

                assert response.status_code == 200
                data = response.json()
                assert "id" in data
                assert data["file_name"] == "test_invoice.pdf"
                assert data["status"] == InvoiceStatus.RECEIVED.value
                assert data["workflow_state"] == "uploaded"

                # Verify storage service was called
                mock_storage.assert_called_once()

                # Verify Celery task was queued
                mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_invoice_invalid_file_type(self, async_client: AsyncClient):
        """Test upload with invalid file type."""
        # Create test file with invalid extension
        file_data = io.BytesIO(b"fake content")
        files = {"file": ("test_invoice.txt", file_data, "text/plain")}

        response = await async_client.post("/api/v1/invoices/upload", files=files)

        assert response.status_code == 400
        assert "File type 'txt' not allowed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_invoice_no_filename(self, async_client: AsyncClient):
        """Test upload without filename."""
        file_data = io.BytesIO(b"fake content")
        files = {"file": (None, file_data, "application/pdf")}

        response = await async_client.post("/api/v1/invoices/upload", files=files)

        assert response.status_code == 400
        assert "No filename provided" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_invoice_file_too_large(self, async_client: AsyncClient):
        """Test upload with file exceeding size limit."""
        # Create large file content
        large_content = b"x" * (50 * 1024 * 1024)  # 50MB
        file_data = io.BytesIO(large_content)
        files = {"file": ("large_invoice.pdf", file_data, "application/pdf")}

        response = await async_client.post("/api/v1/invoices/upload", files=files)

        assert response.status_code == 400
        assert "exceeds maximum" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_duplicate_file(self, async_client: AsyncSession, async_client: AsyncClient):
        """Test upload of duplicate file."""
        # Create test file content
        pdf_content = b"%PDF-1.4\nfake pdf content for testing"
        file_hash = "test_hash_123"

        # Create existing invoice with same hash
        existing_invoice = InvoiceFactory.create(
            file_hash=file_hash,
            status=InvoiceStatus.PROCESSED
        )
        db_session.add(existing_invoice)
        await db_session.commit()

        # Mock hash calculation
        with patch('hashlib.sha256') as mock_hash:
            mock_hash.return_value.hexdigest.return_value = file_hash

            file_data = io.BytesIO(pdf_content)
            files = {"file": ("duplicate_invoice.pdf", file_data, "application/pdf")}

            response = await async_client.post("/api/v1/invoices/upload", files=files)

            assert response.status_code == 409
            assert "Duplicate file detected" in response.json()["detail"]
            assert existing_invoice.id in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_storage_error(self, async_client: AsyncClient):
        """Test upload when storage service fails."""
        pdf_content = b"%PDF-1.4\nfake pdf content for testing"
        file_data = io.BytesIO(pdf_content)
        files = {"file": ("test_invoice.pdf", file_data, "application/pdf")}

        # Mock storage service to raise exception
        with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
            from app.core.exceptions import StorageException
            mock_storage.side_effect = StorageException("Storage service unavailable")

            response = await async_client.post("/api/v1/invoices/upload", files=files)

            assert response.status_code == 500
            assert "Storage service unavailable" in response.json()["detail"]


class TestInvoiceListEndpoint:
    """Test suite for invoice list endpoint."""

    @pytest.mark.asyncio
    async def test_list_invoices_default(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test listing invoices with default parameters."""
        # Create test invoices
        invoices = InvoiceFactory.create_batch(5, status=InvoiceStatus.RECEIVED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        response = await async_client.get("/api/v1/invoices/")

        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["invoices"]) == 5
        assert data["total"] == 5
        assert data["skip"] == 0
        assert data["limit"] == 100

    @pytest.mark.asyncio
    async def test_list_invoices_with_pagination(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test listing invoices with pagination."""
        # Create test invoices
        invoices = InvoiceFactory.create_batch(15, status=InvoiceStatus.RECEIVED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        response = await async_client.get("/api/v1/invoices/?skip=5&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) == 5
        assert data["skip"] == 5
        assert data["limit"] == 5
        assert data["total"] == 15

    @pytest.mark.asyncio
    async def test_list_invoices_filter_by_status(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test listing invoices filtered by status."""
        # Create invoices with different statuses
        received_invoices = InvoiceFactory.create_batch(3, status=InvoiceStatus.RECEIVED)
        processed_invoices = InvoiceFactory.create_batch(2, status=InvoiceStatus.PROCESSED)

        for invoice in received_invoices + processed_invoices:
            db_session.add(invoice)
        await db_session.commit()

        response = await async_client.get("/api/v1/invoices/?status=received")

        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) == 3
        assert data["total"] == 3
        assert all(inv["status"] == "received" for inv in data["invoices"])

    @pytest.mark.asyncio
    async def test_list_invoices_filter_by_vendor(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test listing invoices filtered by vendor."""
        vendor_id = "test-vendor-id"

        # Create invoices for specific vendor
        vendor_invoices = InvoiceFactory.create_batch(2, vendor_id=vendor_id)
        other_invoices = InvoiceFactory.create_batch(3)

        for invoice in vendor_invoices + other_invoices:
            db_session.add(invoice)
        await db_session.commit()

        response = await async_client.get(f"/api/v1/invoices/?vendor_id={vendor_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) == 2
        assert data["total"] == 2
        assert all(inv["vendor_id"] == vendor_id for inv in data["invoices"])

    @pytest.mark.asyncio
    async def test_list_invoices_invalid_status(self, async_client: AsyncClient):
        """Test listing invoices with invalid status filter."""
        response = await async_client.get("/api/v1/invoices/?status=invalid_status")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_invoices_invalid_vendor_id(self, async_client: AsyncClient):
        """Test listing invoices with invalid vendor ID."""
        response = await async_client.get("/api/v1/invoices/?vendor_id=invalid-uuid")

        assert response.status_code == 400
        assert "Invalid vendor_id format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_invoices_limit_exceeded(self, async_client: AsyncClient):
        """Test listing invoices with limit exceeding maximum."""
        response = await async_client.get("/api/v1/invoices/?limit=2000")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_invoices_empty_result(self, async_client: AsyncClient):
        """Test listing invoices when no invoices exist."""
        response = await async_client.get("/api/v1/invoices/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) == 0
        assert data["total"] == 0


class TestInvoiceGetEndpoint:
    """Test suite for get invoice endpoint."""

    @pytest.mark.asyncio
    async def test_get_invoice_success(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test successful invoice retrieval."""
        # Create test invoice
        invoice = InvoiceFactory.create(status=InvoiceStatus.PROCESSED)
        db_session.add(invoice)
        await db_session.commit()

        response = await async_client.get(f"/api/v1/invoices/{invoice.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["file_name"] == invoice.file_name
        assert data["status"] == invoice.status.value

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, async_client: AsyncClient):
        """Test retrieving non-existent invoice."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/api/v1/invoices/{fake_id}")

        assert response.status_code == 404
        assert "Invoice not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_invoice_invalid_uuid(self, async_client: AsyncClient):
        """Test retrieving invoice with invalid UUID."""
        response = await async_client.get("/api/v1/invoices/invalid-uuid")

        assert response.status_code == 400
        assert "Invalid invoice_id format" in response.json()["detail"]


class TestInvoiceReviewEndpoint:
    """Test suite for invoice review endpoint."""

    @pytest.mark.asyncio
    async def test_review_invoice_success(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test successful invoice review update."""
        # Create test invoice
        invoice = InvoiceFactory.create(status=InvoiceStatus.REVIEW)
        db_session.add(invoice)
        await db_session.commit()

        update_data = {
            "status": "ready",
            "reviewed_by": "test_reviewer",
            "review_notes": "Invoice verified and approved"
        }

        response = await async_client.put(
            f"/api/v1/invoices/{invoice.id}/review",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["status"] == "ready"
        assert data["reviewed_by"] == "test_reviewer"

    @pytest.mark.asyncio
    async def test_review_invoice_not_found(self, async_client: AsyncClient):
        """Test reviewing non-existent invoice."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        update_data = {"status": "ready"}

        response = await async_client.put(f"/api/v1/invoices/{fake_id}/review", json=update_data)

        assert response.status_code == 404
        assert "Invoice not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_review_invoice_invalid_uuid(self, async_client: AsyncClient):
        """Test reviewing invoice with invalid UUID."""
        update_data = {"status": "ready"}

        response = await async_client.put("/api/v1/invoices/invalid-uuid/review", json=update_data)

        assert response.status_code == 400
        assert "Invalid invoice_id format" in response.json()["detail"]


class TestInvoiceApproveEndpoint:
    """Test suite for invoice approve endpoint."""

    @pytest.mark.asyncio
    async def test_approve_invoice_success(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test successful invoice approval."""
        # Create test invoice
        invoice = InvoiceFactory.create(status=InvoiceStatus.READY)
        db_session.add(invoice)
        await db_session.commit()

        # Mock export task
        with patch('app.api.api_v1.endpoints.invoices.export_invoice_task') as mock_export:
            mock_export.delay.return_value = AsyncMock(id="export-task-id")

            response = await async_client.post(f"/api/v1/invoices/{invoice.id}/approve")

            assert response.status_code == 200
            data = response.json()
            assert data["invoice_id"] == str(invoice.id)
            assert data["status"] == "staged"
            assert "approved and queued for export" in data["message"]

            # Verify export task was queued
            mock_export.delay.assert_called_once_with(str(invoice.id))

    @pytest.mark.asyncio
    async def test_approve_invoice_not_ready(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test approving invoice not in ready status."""
        # Create test invoice in received status
        invoice = InvoiceFactory.create(status=InvoiceStatus.RECEIVED)
        db_session.add(invoice)
        await db_session.commit()

        response = await async_client.post(f"/api/v1/invoices/{invoice.id}/approve")

        assert response.status_code == 400
        assert "must be in 'ready' status to approve" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_approve_invoice_not_found(self, async_client: AsyncClient):
        """Test approving non-existent invoice."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.post(f"/api/v1/invoices/{fake_id}/approve")

        assert response.status_code == 404
        assert "Invoice not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_approve_invoice_invalid_uuid(self, async_client: AsyncClient):
        """Test approving invoice with invalid UUID."""
        response = await async_client.post("/api/v1/invoices/invalid-uuid/approve")

        assert response.status_code == 400
        assert "Invalid invoice_id format" in response.json()["detail"]


class TestInvoiceEdgeCases:
    """Test suite for edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_uploads_same_file(self, async_client: AsyncClient):
        """Test concurrent uploads of the same file."""
        pdf_content = b"%PDF-1.4\nfake pdf content for testing"
        file_hash = "concurrent_test_hash"

        # Mock hash calculation
        with patch('hashlib.sha256') as mock_hash:
            mock_hash.return_value.hexdigest.return_value = file_hash

            # Mock storage service
            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/test_invoice.pdf"}

                # Mock Celery task
                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="test-task-id")

                    # Create multiple concurrent requests
                    file_data = io.BytesIO(pdf_content)
                    files = {"file": ("concurrent_test.pdf", file_data, "application/pdf")}

                    responses = await asyncio.gather(*[
                        async_client.post("/api/v1/invoices/upload", files=files)
                        for _ in range(3)
                    ])

                    # One should succeed, others should fail with duplicate
                    success_count = sum(1 for r in responses if r.status_code == 200)
                    duplicate_count = sum(1 for r in responses if r.status_code == 409)

                    assert success_count == 1
                    assert duplicate_count == 2

    @pytest.mark.asyncio
    async def test_malformed_json_request(self, async_client: AsyncClient):
        """Test handling of malformed JSON in review endpoint."""
        response = await async_client.put(
            "/api/v1/invoices/test-id/review",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_file_upload(self, async_client: AsyncClient):
        """Test upload of empty file."""
        file_data = io.BytesIO(b"")
        files = {"file": ("empty.pdf", file_data, "application/pdf")}

        response = await async_client.post("/api/v1/invoices/upload", files=files)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_large_request_payload(self, async_client: AsyncClient):
        """Test handling of large request payloads."""
        large_notes = "x" * 10000  # 10KB of notes
        update_data = {
            "status": "ready",
            "review_notes": large_notes
        }

        # This should still work if within reasonable limits
        response = await async_client.put(
            "/api/v1/invoices/test-id/review",
            json=update_data
        )

        # Should get 404 since invoice doesn't exist, but not a payload error
        assert response.status_code in [404, 400]