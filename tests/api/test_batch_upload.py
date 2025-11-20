"""
Test batch upload endpoint using TDD approach.
"""

import pytest
import asyncio
import io
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.api.schemas import IngestionResponse
from app.core.config import settings
from app.services.ingestion_service import IngestionService

client = TestClient(app)


class TestBatchUploadEndpoint:
    """Test cases for batch upload endpoint."""

    @pytest.fixture
    def mock_ingestion_service(self):
        """Mock ingestion service."""
        with patch('app.api.api_v1.endpoints.ingestion.ingestion_service') as mock:
            yield mock

    @pytest.fixture
    def mock_idempotency_service(self):
        """Mock idempotency service."""
        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service') as mock:
            yield mock

    @pytest.fixture
    def sample_files(self):
        """Create sample files for testing."""
        files = {
            "file1": ("invoice1.pdf", io.BytesIO(b"%PDF-1.4 sample content 1"), "application/pdf"),
            "file2": ("invoice2.pdf", io.BytesIO(b"%PDF-1.4 sample content 2"), "application/pdf"),
            "file3": ("invoice3.jpg", io.BytesIO(b"\xff\xd8\xff\xe0 sample image"), "image/jpeg"),
        }
        return files

    @pytest.fixture
    def sample_ingestion_response(self):
        """Sample ingestion response."""
        return {
            "ingestion_job_id": "12345678-1234-1234-1234-123456789012",
            "file_size": 1024,
            "file_hash": "sha256_hash_here",
            "status": "pending",
            "storage_path": "/uploads/test.pdf",
            "duplicate_analysis": {},
            "estimated_processing_time": 30,
        }

    def test_batch_upload_success(self, sample_files, mock_ingestion_service, sample_ingestion_response):
        """Test successful batch upload."""
        # Mock ingestion service response
        mock_ingestion_service.ingest_file = AsyncMock(return_value=sample_ingestion_response)

        # Mock idempotency service
        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "test-idempotency-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            # Prepare files for upload
            files_data = []
            for field_name, (filename, content, content_type) in sample_files.items():
                files_data.append(
                    ("files", (filename, content.read(), content_type))
                )
                content.seek(0)  # Reset file pointer

            # Make batch upload request
            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={
                    "source_type": "batch_upload",
                    "uploaded_by": "test_user"
                }
            )

            assert response.status_code == 200
            response_data = response.json()

            # Verify batch response structure
            assert "results" in response_data
            assert "summary" in response_data
            assert "batch_id" in response_data

            # Verify individual file results
            results = response_data["results"]
            assert len(results) == len(sample_files)

            for result in results:
                assert "id" in result
                assert "original_filename" in result
                assert "status" in result
                assert "file_hash_sha256" in result
                assert "created_at" in result

    def test_batch_upload_single_file_equivalence(self, sample_files, mock_ingestion_service, sample_ingestion_response):
        """Test that batch upload with single file is equivalent to single upload."""
        # Mock services
        mock_ingestion_service.ingest_file = AsyncMock(return_value=sample_ingestion_response)

        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "test-idempotency-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            # Single file batch upload
            single_file = sample_files["file1"]
            filename, content, content_type = single_file
            content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=[("files", (filename, content.read(), content_type))],
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data["results"]) == 1

    def test_batch_upload_max_files_limit(self, mock_ingestion_service):
        """Test batch upload respects maximum files limit."""
        # Create too many files (over limit)
        files_data = []
        for i in range(55):  # Over 50 file limit
            files_data.append(
                ("files", (f"invoice_{i}.pdf", io.BytesIO(f"%PDF content {i}".encode()), "application/pdf"))
            )

        response = client.post(
            "/api/v1/ingestion/batch-upload",
            files=files_data,
            data={"source_type": "batch_upload"}
        )

        assert response.status_code == 400
        assert "Maximum" in response.json()["detail"] and "files" in response.json()["detail"]

    def test_batch_upload_file_size_validation(self, mock_ingestion_service):
        """Test batch upload validates individual file sizes."""
        # Create a file that's too large
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB, over 50MB limit

        response = client.post(
            "/api/v1/ingestion/batch-upload",
            files=[("files", ("large_file.pdf", io.BytesIO(large_content), "application/pdf"))],
            data={"source_type": "batch_upload"}
        )

        assert response.status_code == 400
        assert "file size" in response.json()["detail"].lower() or "too large" in response.json()["detail"].lower()

    def test_batch_upload_supported_file_types(self, mock_ingestion_service):
        """Test batch upload validates file types."""
        # Unsupported file type
        response = client.post(
            "/api/v1/ingestion/batch-upload",
            files=[("files", ("test.txt", io.BytesIO(b"text content"), "text/plain"))],
            data={"source_type": "batch_upload"}
        )

        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower() or "supported" in response.json()["detail"].lower()

    def test_batch_upload_partial_failure_handling(self, sample_files, mock_ingestion_service):
        """Test batch upload handles partial failures gracefully."""
        # Mock ingestion service to fail for specific files
        def mock_ingest_file_side_effect(*args, **kwargs):
            if "invoice2" in str(args):
                raise Exception("Processing failed for invoice2")
            return {
                "ingestion_job_id": "success-job-id",
                "file_size": 1024,
                "file_hash": "success_hash",
                "status": "pending",
                "storage_path": "/uploads/success.pdf",
                "duplicate_analysis": {},
                "estimated_processing_time": 30,
            }

        mock_ingestion_service.ingest_file = AsyncMock(side_effect=mock_ingest_file_side_effect)

        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "test-idempotency-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            files_data = []
            for field_name, (filename, content, content_type) in sample_files.items():
                files_data.append(
                    ("files", (filename, content.read(), content_type))
                )
                content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            assert response.status_code == 207  # Multi-Status for partial success
            response_data = response.json()

            # Should have both successful and failed results
            results = response_data["results"]
            assert len(results) == len(sample_files)

            # Check summary statistics
            summary = response_data["summary"]
            assert summary["total_files"] == len(sample_files)
            assert summary["successful_uploads"] > 0
            assert summary["failed_uploads"] > 0

    def test_batch_upload_duplicate_detection(self, sample_files, mock_ingestion_service, sample_ingestion_response):
        """Test batch upload handles duplicate detection."""
        # Mock idempotency service to return existing record for duplicate
        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "duplicate-key"

        existing_record = Mock()
        existing_record.operation_status.value = "completed"
        existing_record.result_data = sample_ingestion_response

        mock_idempotency_service.check_and_create_idempotency_record.return_value = (existing_record, False)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            files_data = []
            filename, content, content_type = sample_files["file1"]
            files_data.append(("files", (filename, content.read(), content_type)))
            content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            assert response.status_code == 200
            response_data = response.json()

            # Should return existing ingestion result
            results = response_data["results"]
            assert len(results) == 1
            assert results[0]["id"] == sample_ingestion_response["ingestion_job_id"]

    def test_batch_upload_concurrent_processing(self, sample_files, mock_ingestion_service):
        """Test batch upload can handle concurrent processing."""
        # Mock ingestion service with realistic processing delay
        async def delayed_ingest(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate processing time
            return {
                "ingestion_job_id": f"job-{asyncio.current_task().get_name()}",
                "file_size": 1024,
                "file_hash": "hash",
                "status": "pending",
                "storage_path": "/uploads/test.pdf",
                "duplicate_analysis": {},
                "estimated_processing_time": 30,
            }

        mock_ingestion_service.ingest_file = AsyncMock(side_effect=delayed_ingest)

        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "concurrent-test-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            files_data = []
            for field_name, (filename, content, content_type) in sample_files.items():
                files_data.append(
                    ("files", (filename, content.read(), content_type))
                )
                content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            assert response.status_code == 200
            response_data = response.json()

            # All files should be processed
            assert len(response_data["results"]) == len(sample_files)

            # Verify different job IDs (indicating concurrent processing)
            job_ids = [result["id"] for result in response_data["results"]]
            assert len(set(job_ids)) == len(sample_files)  # All unique

    def test_batch_upload_response_format(self, sample_files, mock_ingestion_service, sample_ingestion_response):
        """Test batch upload response format matches specification."""
        mock_ingestion_service.ingest_file = AsyncMock(return_value=sample_ingestion_response)

        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "format-test-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_completed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            files_data = []
            for field_name, (filename, content, content_type) in sample_files.items():
                files_data.append(
                    ("files", (filename, content.read(), content_type))
                )
                content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            assert response.status_code == 200
            response_data = response.json()

            # Verify required top-level fields
            assert "batch_id" in response_data
            assert "results" in response_data
            assert "summary" in response_data
            assert "created_at" in response_data
            assert "processing_time_seconds" in response_data

            # Verify batch_id format (UUID)
            batch_id = response_data["batch_id"]
            assert len(batch_id) == 36  # UUID length
            assert batch_id.count('-') == 4  # UUID format

            # Verify summary structure
            summary = response_data["summary"]
            assert "total_files" in summary
            assert "successful_uploads" in summary
            assert "failed_uploads" in summary
            assert "total_file_size_bytes" in summary
            assert "duplicates_detected" in summary

            # Verify summary calculations
            assert summary["total_files"] == len(sample_files)
            assert summary["successful_uploads"] + summary["failed_uploads"] == summary["total_files"]

            # Verify created_at is valid datetime
            created_at = datetime.fromisoformat(response_data["created_at"].replace('Z', '+00:00'))
            assert isinstance(created_at, datetime)

            # Verify processing time is reasonable
            processing_time = response_data["processing_time_seconds"]
            assert isinstance(processing_time, (int, float))
            assert processing_time >= 0

    def test_batch_upload_empty_files_list(self):
        """Test batch upload with empty files list."""
        response = client.post(
            "/api/v1/ingestion/batch-upload",
            files=[],
            data={"source_type": "batch_upload"}
        )

        assert response.status_code == 400
        assert "No files" in response.json()["detail"]

    def test_batch_upload_malformed_files(self):
        """Test batch upload with malformed file data."""
        # Test with non-file data
        response = client.post(
            "/api/v1/ingestion/batch-upload",
            data={"source_type": "batch_upload"}
        )

        assert response.status_code == 422  # Validation error

    def test_batch_upload_error_handling(self, sample_files, mock_ingestion_service):
        """Test batch upload error handling when services are unavailable."""
        # Mock ingestion service to raise an exception
        mock_ingestion_service.ingest_file = AsyncMock(side_effect=Exception("Service unavailable"))

        mock_idempotency_service = AsyncMock()
        mock_idempotency_service.generate_idempotency_key.return_value = "error-test-key"
        mock_idempotency_service.check_and_create_idempotency_record.return_value = (None, True)
        mock_idempotency_service.mark_operation_started = AsyncMock()
        mock_idempotency_service.mark_operation_failed = AsyncMock()

        with patch('app.api.api_v1.endpoints.ingestion.idempotency_service', mock_idempotency_service):
            files_data = []
            filename, content, content_type = sample_files["file1"]
            files_data.append(("files", (filename, content.read(), content_type)))
            content.seek(0)

            response = client.post(
                "/api/v1/ingestion/batch-upload",
                files=files_data,
                data={"source_type": "batch_upload", "uploaded_by": "test_user"}
            )

            # Should return error status with details
            assert response.status_code in [500, 207]
            response_data = response.json()

            if response.status_code == 207:  # Partial success
                assert "results" in response_data
                assert response_data["summary"]["failed_uploads"] > 0