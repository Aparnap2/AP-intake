"""
Performance tests for API endpoints.
"""

import asyncio
import io
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import pytest
import psutil
import gc
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.models.invoice import Invoice, InvoiceStatus
from app.services.storage_service import StorageService
from app.services.docling_service import DoclingService
from tests.factories import InvoiceFactory, ExtractionDataFactory


class PerformanceTestMixin:
    """Mixin class with performance testing utilities."""

    @staticmethod
    def get_memory_usage() -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    @staticmethod
    def get_cpu_usage() -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    @staticmethod
    async def measure_async_execution(func, *args, **kwargs) -> Dict[str, Any]:
        """Measure execution time and resource usage of async function."""
        gc.collect()  # Force garbage collection

        start_memory = PerformanceTestMixin.get_memory_usage()
        start_time = time.perf_counter()

        try:
            result = await func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            result = None

        end_time = time.perf_counter()
        end_memory = PerformanceTestMixin.get_memory_usage()

        return {
            "result": result,
            "success": success,
            "error": error,
            "duration_ms": (end_time - start_time) * 1000,
            "memory_delta_mb": end_memory - start_memory,
            "memory_peak_mb": end_memory
        }


@pytest.mark.performance
class TestInvoiceUploadPerformance(PerformanceTestMixin):
    """Performance tests for invoice upload endpoint."""

    @pytest.fixture
    async def sample_pdf_content(self) -> bytes:
        """Sample PDF content for testing."""
        return b"%PDF-1.4\n" + b"x" * (1024 * 1024)  # 1MB PDF content

    @pytest.mark.asyncio
    async def test_upload_small_file_performance(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Test upload performance with small file (1MB)."""

        async def upload_file():
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": ("small_invoice.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/test.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="test-task-id")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        # Run multiple iterations to get average
        iterations = 10
        durations = []
        memory_usages = []

        for _ in range(iterations):
            metrics = await self.measure_async_execution(upload_file)

            assert metrics["success"], f"Upload failed: {metrics['error']}"
            assert metrics["result"].status_code == 200

            durations.append(metrics["duration_ms"])
            memory_usages.append(metrics["memory_delta_mb"])

            # Small delay between requests
            await asyncio.sleep(0.1)

        avg_duration = sum(durations) / len(durations)
        avg_memory = sum(memory_usages) / len(memory_usages)

        # Performance assertions
        assert avg_duration < 1000, f"Average upload time {avg_duration:.2f}ms exceeds 1000ms"
        assert avg_memory < 50, f"Average memory usage {avg_memory:.2f}MB exceeds 50MB"

    @pytest.mark.asyncio
    async def test_upload_medium_file_performance(self, async_client: AsyncClient):
        """Test upload performance with medium file (5MB)."""

        # Create 5MB content
        medium_content = b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024)

        async def upload_file():
            file_data = io.BytesIO(medium_content)
            files = {"file": ("medium_invoice.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/medium.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="test-task-id")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        metrics = await self.measure_async_execution(upload_file)

        assert metrics["success"], f"Upload failed: {metrics['error']}"
        assert metrics["result"].status_code == 200

        # Performance assertions for medium files
        assert metrics["duration_ms"] < 3000, f"Upload time {metrics['duration_ms']:.2f}ms exceeds 3000ms"
        assert metrics["memory_delta_mb"] < 200, f"Memory usage {metrics['memory_delta_mb']:.2f}MB exceeds 200MB"

    @pytest.mark.asyncio
    async def test_concurrent_uploads_performance(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Test performance of concurrent uploads."""

        async def upload_file(index: int):
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"concurrent_{index}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/concurrent_{index}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"task-{index}")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        # Test with 10 concurrent uploads
        concurrent_requests = 10
        start_time = time.perf_counter()

        tasks = [upload_file(i) for i in range(concurrent_requests)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()
        total_duration = (end_time - start_time) * 1000

        # Check all responses
        successful_responses = 0
        for response in responses:
            if isinstance(response, Exception):
                print(f"Request failed with exception: {response}")
            else:
                assert response.status_code == 200
                successful_responses += 1

        # Performance assertions
        assert successful_responses >= concurrent_requests * 0.8, f"Too many failed requests: {successful_responses}/{concurrent_requests}"
        assert total_duration < 5000, f"Concurrent uploads took {total_duration:.2f}ms, exceeds 5000ms"

    @pytest.mark.asyncio
    async def test_upload_memory_cleanup(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Test that memory is properly cleaned up after uploads."""

        initial_memory = self.get_memory_usage()

        # Perform multiple uploads
        for i in range(20):
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"cleanup_test_{i}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/cleanup_{i}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"cleanup-task-{i}")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    assert response.status_code == 200

        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)

        final_memory = self.get_memory_usage()
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f}MB after uploads"


@pytest.mark.performance
class TestInvoiceListPerformance(PerformanceTestMixin):
    """Performance tests for invoice list endpoint."""

    @pytest.mark.asyncio
    async def test_list_small_dataset_performance(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test list performance with small dataset (100 invoices)."""

        # Create test data
        invoices = InvoiceFactory.create_batch(100, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        async def list_invoices():
            response = await async_client.get("/api/v1/invoices/")
            return response

        # Measure performance
        metrics = await self.measure_async_execution(list_invoices)

        assert metrics["success"], f"List request failed: {metrics['error']}"
        assert metrics["result"].status_code == 200

        data = metrics["result"].json()
        assert len(data["invoices"]) == 100

        # Performance assertions
        assert metrics["duration_ms"] < 500, f"List request took {metrics['duration_ms']:.2f}ms, exceeds 500ms"
        assert metrics["memory_delta_mb"] < 20, f"Memory usage {metrics['memory_delta_mb']:.2f}MB exceeds 20MB"

    @pytest.mark.asyncio
    async def test_list_large_dataset_performance(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test list performance with large dataset (1000 invoices)."""

        # Create test data
        invoices = InvoiceFactory.create_batch(1000, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        async def list_invoices():
            response = await async_client.get("/api/v1/invoices/?limit=100")
            return response

        # Measure performance
        metrics = await self.measure_async_execution(list_invoices)

        assert metrics["success"], f"List request failed: {metrics['error']}"
        assert metrics["result"].status_code == 200

        data = metrics["result"].json()
        assert len(data["invoices"]) == 100
        assert data["total"] == 1000

        # Performance assertions for large dataset
        assert metrics["duration_ms"] < 1000, f"List request took {metrics['duration_ms']:.2f}ms, exceeds 1000ms"
        assert metrics["memory_delta_mb"] < 50, f"Memory usage {metrics['memory_delta_mb']:.2f}MB exceeds 50MB"

    @pytest.mark.asyncio
    async def test_list_pagination_performance(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test pagination performance across multiple pages."""

        # Create test data
        invoices = InvoiceFactory.create_batch(500, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        # Test multiple pages
        page_times = []
        for page in range(0, 500, 100):
            async def get_page(skip=page):
                response = await async_client.get(f"/api/v1/invoices/?skip={skip}&limit=100")
                return response

            metrics = await self.measure_async_execution(get_page)

            assert metrics["success"], f"Page {page} request failed: {metrics['error']}"
            assert metrics["result"].status_code == 200

            page_times.append(metrics["duration_ms"])

        # Performance should be consistent across pages
        avg_page_time = sum(page_times) / len(page_times)
        max_page_time = max(page_times)

        assert avg_page_time < 300, f"Average page time {avg_page_time:.2f}ms exceeds 300ms"
        assert max_page_time < 500, f"Max page time {max_page_time:.2f}ms exceeds 500ms"

    @pytest.mark.asyncio
    async def test_list_filtering_performance(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test filtering performance on large dataset."""

        # Create test data with different statuses
        status_distribution = [
            InvoiceFactory.create_batch(200, status=InvoiceStatus.RECEIVED),
            InvoiceFactory.create_batch(300, status=InvoiceStatus.PROCESSED),
            InvoiceFactory.create_batch(250, status=InvoiceStatus.REVIEW),
            InvoiceFactory.create_batch(250, status=InvoiceStatus.READY),
        ]

        for batch in status_distribution:
            for invoice in batch:
                db_session.add(invoice)
        await db_session.commit()

        # Test different filters
        filters = [
            {"status": "processed"},
            {"status": "review"},
            {"vendor_id": "test-vendor-id"},  # Should return empty
        ]

        for filter_params in filters:
            async def filter_invoices(params=filter_params):
                response = await async_client.get("/api/v1/invoices/", params=params)
                return response

            metrics = await self.measure_async_execution(filter_invoices)

            assert metrics["success"], f"Filter {filter_params} failed: {metrics['error']}"
            assert metrics["result"].status_code == 200

            # Filtering should be efficient
            assert metrics["duration_ms"] < 200, f"Filter {filter_params} took {metrics['duration_ms']:.2f}ms, exceeds 200ms"


@pytest.mark.performance
class TestServiceLayerPerformance(PerformanceTestMixin):
    """Performance tests for service layer components."""

    @pytest.mark.asyncio
    async def test_docling_service_performance(self):
        """Test DoclingService extraction performance."""

        # Create test PDF content of different sizes
        test_sizes = [1, 5, 10, 20]  # MB

        for size_mb in test_sizes:
            pdf_content = b"%PDF-1.4\n" + b"x" * (size_mb * 1024 * 1024)

            async def extract_content():
                docling_service = DoclingService()

                with patch.object(docling_service.converter, 'convert') as mock_convert:
                    # Mock document processing
                    mock_document = MagicMock()
                    mock_document.text = f"Test content for {size_mb}MB file"
                    mock_document.pages = [MagicMock() for _ in range(size_mb)]

                    mock_result = MagicMock()
                    mock_result.document = mock_document
                    mock_result.status = "success"
                    mock_convert.return_value = mock_result

                    result = await docling_service.extract_from_content(pdf_content)
                    return result

            metrics = await self.measure_async_execution(extract_content)

            assert metrics["success"], f"Extraction failed for {size_mb}MB: {metrics['error']}"

            # Performance assertions based on file size
            max_time_ms = size_mb * 1000  # 1 second per MB
            max_memory_mb = size_mb * 50   # 50MB per MB of input

            assert metrics["duration_ms"] < max_time_ms, f"{size_mb}MB extraction took {metrics['duration_ms']:.2f}ms, exceeds {max_time_ms}ms"
            assert metrics["memory_delta_mb"] < max_memory_mb, f"{size_mb}MB extraction used {metrics['memory_delta_mb']:.2f}MB, exceeds {max_memory_mb}MB"

    @pytest.mark.asyncio
    async def test_validation_service_performance(self):
        """Test ValidationService performance with different data sizes."""

        # Create extraction data with different numbers of line items
        line_counts = [5, 25, 50, 100]

        for line_count in line_counts:
            from app.services.validation_service import ValidationService

            # Create test data
            extraction_data = ExtractionDataFactory()
            extraction_data["lines"] = [
                {
                    "description": f"Test Product {i}",
                    "quantity": i + 1,
                    "unit_price": 10.0 * (i + 1),
                    "amount": 10.0 * (i + 1) * (i + 1)
                }
                for i in range(line_count)
            ]

            async def validate_data():
                validation_service = ValidationService()
                result = await validation_service.validate_invoice(extraction_data)
                return result

            metrics = await self.measure_async_execution(validate_data)

            assert metrics["success"], f"Validation failed for {line_count} lines: {metrics['error']}"

            # Validation should be fast regardless of line count
            max_time_ms = 100 + (line_count * 2)  # 100ms base + 2ms per line

            assert metrics["duration_ms"] < max_time_ms, f"Validation of {line_count} lines took {metrics['duration_ms']:.2f}ms, exceeds {max_time_ms}ms"

    @pytest.mark.asyncio
    async def test_storage_service_performance(self):
        """Test StorageService performance."""
        from app.services.storage_service import StorageService

        # Test different file sizes
        file_sizes = [1, 5, 10, 25]  # MB

        for size_mb in file_sizes:
            file_content = b"x" * (size_mb * 1024 * 1024)
            filename = f"test_file_{size_mb}mb.dat"

            async def store_file():
                storage_service = StorageService()

                with patch.object(storage_service, '_store_local') as mock_store:
                    mock_store.return_value = f"/tmp/{filename}"

                    result = await storage_service.store_file(file_content, filename)
                    return result

            metrics = await self.measure_async_execution(store_file)

            assert metrics["success"], f"Storage failed for {size_mb}MB: {metrics['error']}"

            # Storage should be relatively fast
            max_time_ms = size_mb * 200  # 200ms per MB

            assert metrics["duration_ms"] < max_time_ms, f"Storage of {size_mb}MB took {metrics['duration_ms']:.2f}ms, exceeds {max_time_ms}ms"


@pytest.mark.performance
@pytest.mark.slow
class TestSystemLoadPerformance(PerformanceTestMixin):
    """System-level performance tests under load."""

    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Test system performance under sustained load."""

        upload_count = 50
        duration_seconds = 30

        async def continuous_upload():
            """Perform uploads continuously for specified duration."""
            start_time = time.perf_counter()
            uploads_completed = 0
            errors = []

            while (time.perf_counter() - start_time) < duration_seconds:
                try:
                    file_data = io.BytesIO(sample_pdf_content)
                    files = {"file": (f"load_test_{uploads_completed}.pdf", file_data, "application/pdf")}

                    with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                        mock_storage.return_value = {"file_path": f"/tmp/load_{uploads_completed}.pdf"}

                        with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                            mock_task.delay.return_value = AsyncMock(id=f"load-task-{uploads_completed}")

                            response = await async_client.post("/api/v1/invoices/upload", files=files)

                            if response.status_code == 200:
                                uploads_completed += 1
                            else:
                                errors.append(f"HTTP {response.status_code}")

                except Exception as e:
                    errors.append(str(e))

                # Small delay between uploads
                await asyncio.sleep(0.1)

            return {
                "uploads_completed": uploads_completed,
                "errors": errors,
                "duration": time.perf_counter() - start_time
            }

        # Monitor system resources during test
        initial_memory = self.get_memory_usage()
        initial_cpu = self.get_cpu_usage()

        result = await continuous_upload()

        final_memory = self.get_memory_usage()
        final_cpu = self.get_cpu_usage()

        # Performance assertions
        uploads_per_second = result["uploads_completed"] / result["duration"]
        error_rate = len(result["errors"]) / (result["uploads_completed"] + len(result["errors"]))

        assert uploads_per_second >= 1.0, f"Upload rate {uploads_per_second:.2f}/s below minimum 1.0/s"
        assert error_rate < 0.05, f"Error rate {error_rate:.2%} exceeds 5%"
        assert (final_memory - initial_memory) < 200, f"Memory increased by {final_memory - initial_memory:.2f}MB"

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Test for memory leaks during repeated operations."""

        initial_memory = self.get_memory_usage()
        memory_samples = [initial_memory]

        # Perform many operations
        for cycle in range(10):
            # Upload and process multiple invoices
            for i in range(10):
                file_data = io.BytesIO(sample_pdf_content)
                files = {"file": (f"leak_test_{cycle}_{i}.pdf", file_data, "application/pdf")}

                with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                    mock_storage.return_value = {"file_path": f"/tmp/leak_{cycle}_{i}.pdf"}

                    with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                        mock_task.delay.return_value = AsyncMock(id=f"leak-task-{cycle}-{i}")

                        response = await async_client.post("/api/v1/invoices/upload", files=files)
                        assert response.status_code == 200

            # Force garbage collection
            gc.collect()
            await asyncio.sleep(0.5)

            # Sample memory usage
            current_memory = self.get_memory_usage()
            memory_samples.append(current_memory)

            print(f"Cycle {cycle}: Memory usage {current_memory:.2f}MB")

        final_memory = memory_samples[-1]
        total_increase = final_memory - initial_memory
        max_memory = max(memory_samples)

        # Memory should not grow excessively
        assert total_increase < 100, f"Memory increased by {total_increase:.2f}MB over test period"
        assert max_memory - initial_memory < 200, f"Peak memory increase {max_memory - initial_memory:.2f}MB exceeds limit"

        # Check for consistent growth (potential leak)
        if len(memory_samples) >= 5:
            recent_samples = memory_samples[-5:]
            is_increasing = all(recent_samples[i] <= recent_samples[i + 1] for i in range(len(recent_samples) - 1))
            assert not is_increasing, "Memory usage shows consistent growth pattern - possible leak"


@pytest.mark.performance
class TestPerformanceRegression(PerformanceTestMixin):
    """Performance regression tests to catch performance degradation."""

    @pytest.mark.asyncio
    async def test_api_response_time_baseline(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test that API response times meet baseline expectations."""

        # Create minimal test data
        invoices = InvoiceFactory.create_batch(10, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        # Baseline performance expectations (in milliseconds)
        baseline_expectations = {
            "list_invoices": 200,
            "get_invoice": 100,
            "upload_invoice": 500,
        }

        # Test list invoices
        async def test_list():
            response = await async_client.get("/api/v1/invoices/")
            return response

        metrics = await self.measure_async_execution(test_list)
        assert metrics["duration_ms"] <= baseline_expectations["list_invoices"], \
            f"List invoices {metrics['duration_ms']:.2f}ms exceeds baseline {baseline_expectations['list_invoices']}ms"

        # Test get single invoice
        test_invoice = invoices[0]
        async def test_get():
            response = await async_client.get(f"/api/v1/invoices/{test_invoice.id}")
            return response

        metrics = await self.measure_async_execution(test_get)
        assert metrics["duration_ms"] <= baseline_expectations["get_invoice"], \
            f"Get invoice {metrics['duration_ms']:.2f}ms exceeds baseline {baseline_expectations['get_invoice']}ms"

        # Test upload (mocked)
        pdf_content = b"%PDF-1.4\nfake content"
        async def test_upload():
            file_data = io.BytesIO(pdf_content)
            files = {"file": ("baseline_test.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/baseline.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="baseline-task")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        metrics = await self.measure_async_execution(test_upload)
        assert metrics["duration_ms"] <= baseline_expectations["upload_invoice"], \
            f"Upload invoice {metrics['duration_ms']:.2f}ms exceeds baseline {baseline_expectations['upload_invoice']}ms"