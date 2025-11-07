"""
Load testing for API endpoints under high concurrency.
"""

import asyncio
import io
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Tuple
import pytest
import psutil
from httpx import AsyncClient, ConnectError, ReadTimeout
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.models.invoice import Invoice, InvoiceStatus
from app.services.storage_service import StorageService
from tests.factories import InvoiceFactory


class LoadTestResult:
    """Container for load test results and metrics."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_response_time(self) -> float:
        """Calculate average response time in milliseconds."""
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def median_response_time(self) -> float:
        """Calculate median response time in milliseconds."""
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        return statistics.quantiles(self.response_times, n=20)[18]  # 95th percentile

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second."""
        if not self.start_time or not self.end_time:
            return 0.0
        duration = self.end_time - self.start_time
        if duration == 0:
            return 0.0
        return self.total_requests / duration

    def add_response(self, response_time: float, success: bool, error: str = None):
        """Add a response result to the metrics."""
        self.total_requests += 1
        self.response_times.append(response_time)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error:
                self.errors.append(error)

    def set_duration(self, start_time: float, end_time: float):
        """Set the test duration."""
        self.start_time = start_time
        self.end_time = end_time


@pytest.mark.performance
@pytest.mark.slow
class TestLoadTesting:
    """Load testing suite for API endpoints."""

    @pytest.fixture
    def sample_pdf_content(self) -> bytes:
        """Sample PDF content for upload testing."""
        return b"%PDF-1.4\n" + b"x" * (500 * 1024)  # 500KB PDF

    async def execute_concurrent_requests(
        self,
        async_client: AsyncClient,
        request_func,
        concurrent_users: int,
        requests_per_user: int,
        delay_between_requests: float = 0.1
    ) -> LoadTestResult:
        """Execute concurrent requests and collect metrics."""

        result = LoadTestResult()
        start_time = time.perf_counter()

        async def user_session(user_id: int):
            """Simulate a user session with multiple requests."""
            for request_num in range(requests_per_user):
                request_start = time.perf_counter()

                try:
                    response = await request_func(user_id, request_num)
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    success = 200 <= response.status_code < 400
                    error = None if success else f"HTTP {response.status_code}"

                    result.add_response(response_time, success, error)

                except Exception as e:
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000
                    result.add_response(response_time, False, str(e))

                # Delay between requests
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)

        # Create user sessions
        user_tasks = [
            asyncio.create_task(user_session(user_id))
            for user_id in range(concurrent_users)
        ]

        # Wait for all sessions to complete
        await asyncio.gather(*user_tasks, return_exceptions=True)

        end_time = time.perf_counter()
        result.set_duration(start_time, end_time)

        return result

    @pytest.mark.asyncio
    async def test_upload_load_test_small(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Load test for invoice upload with small concurrent load."""

        async def upload_request(user_id: int, request_num: int):
            """Single upload request."""
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"load_test_{user_id}_{request_num}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/load_{user_id}_{request_num}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"load-task-{user_id}-{request_num}")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        # Load test parameters
        concurrent_users = 10
        requests_per_user = 5

        result = await self.execute_concurrent_requests(
            async_client, upload_request, concurrent_users, requests_per_user
        )

        # Assertions
        total_expected = concurrent_users * requests_per_user
        assert result.total_requests == total_expected
        assert result.success_rate >= 95, f"Success rate {result.success_rate:.1f}% below 95%"
        assert result.average_response_time < 1000, f"Average response time {result.average_response_time:.2f}ms exceeds 1000ms"
        assert result.p95_response_time < 2000, f"P95 response time {result.p95_response_time:.2f}ms exceeds 2000ms"
        assert result.requests_per_second >= 5, f"RPS {result.requests_per_second:.2f} below minimum 5"

        print(f"Upload Load Test Results:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_upload_load_test_medium(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Load test for invoice upload with medium concurrent load."""

        async def upload_request(user_id: int, request_num: int):
            """Single upload request."""
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"medium_load_{user_id}_{request_num}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/medium_{user_id}_{request_num}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"medium-task-{user_id}-{request_num}")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        # Medium load test parameters
        concurrent_users = 25
        requests_per_user = 4

        result = await self.execute_concurrent_requests(
            async_client, upload_request, concurrent_users, requests_per_user, delay_between_requests=0.05
        )

        # Assertions for medium load
        total_expected = concurrent_users * requests_per_user
        assert result.total_requests == total_expected
        assert result.success_rate >= 90, f"Success rate {result.success_rate:.1f}% below 90%"
        assert result.average_response_time < 2000, f"Average response time {result.average_response_time:.2f}ms exceeds 2000ms"
        assert result.p95_response_time < 5000, f"P95 response time {result.p95_response_time:.2f}ms exceeds 5000ms"

        print(f"Medium Upload Load Test Results:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_list_invoices_load_test(self, async_client: AsyncClient, db_session: AsyncSession):
        """Load test for invoice list endpoint."""

        # Create test data
        invoices = InvoiceFactory.create_batch(200, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        async def list_request(user_id: int, request_num: int):
            """Single list request with varying parameters."""
            params = {
                "skip": (request_num * 10) % 100,
                "limit": 10,
                "status": ["received", "processed", "review"][user_id % 3] if user_id % 3 != 0 else None
            }
            response = await async_client.get("/api/v1/invoices/", params=params)
            return response

        # Load test parameters
        concurrent_users = 50
        requests_per_user = 10

        result = await self.execute_concurrent_requests(
            async_client, list_request, concurrent_users, requests_per_user, delay_between_requests=0.01
        )

        # Assertions
        total_expected = concurrent_users * requests_per_user
        assert result.total_requests == total_expected
        assert result.success_rate >= 98, f"Success rate {result.success_rate:.1f}% below 98%"
        assert result.average_response_time < 500, f"Average response time {result.average_response_time:.2f}ms exceeds 500ms"
        assert result.p95_response_time < 1000, f"P95 response time {result.p95_response_time:.2f}ms exceeds 1000ms"
        assert result.requests_per_second >= 100, f"RPS {result.requests_per_second:.2f} below minimum 100"

        print(f"List Invoices Load Test Results:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_get_invoice_load_test(self, async_client: AsyncClient, db_session: AsyncSession):
        """Load test for get invoice endpoint."""

        # Create test data
        invoices = InvoiceFactory.create_batch(100, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        async def get_request(user_id: int, request_num: int):
            """Single get request."""
            invoice_id = invoices[request_num % len(invoices)].id
            response = await async_client.get(f"/api/v1/invoices/{invoice_id}")
            return response

        # Load test parameters
        concurrent_users = 100
        requests_per_user = 5

        result = await self.execute_concurrent_requests(
            async_client, get_request, concurrent_users, requests_per_user, delay_between_requests=0.01
        )

        # Assertions
        total_expected = concurrent_users * requests_per_user
        assert result.total_requests == total_expected
        assert result.success_rate >= 99, f"Success rate {result.success_rate:.1f}% below 99%"
        assert result.average_response_time < 200, f"Average response time {result.average_response_time:.2f}ms exceeds 200ms"
        assert result.p95_response_time < 500, f"P95 response time {result.p95_response_time:.2f}ms exceeds 500ms"
        assert result.requests_per_second >= 200, f"RPS {result.requests_per_second:.2f} below minimum 200"

        print(f"Get Invoice Load Test Results:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_mixed_workload_load_test(self, async_client: AsyncClient, db_session: AsyncSession, sample_pdf_content: bytes):
        """Load test with mixed API operations."""

        # Create test data
        invoices = InvoiceFactory.create_batch(50, status=InvoiceStatus.PROCESSED)
        for invoice in invoices:
            db_session.add(invoice)
        await db_session.commit()

        async def mixed_request(user_id: int, request_num: int):
            """Mixed request with different operations."""
            operation = (user_id + request_num) % 4

            if operation == 0:  # Upload
                file_data = io.BytesIO(sample_pdf_content)
                files = {"file": (f"mixed_{user_id}_{request_num}.pdf", file_data, "application/pdf")}

                with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                    mock_storage.return_value = {"file_path": f"/tmp/mixed_{user_id}_{request_num}.pdf"}

                    with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                        mock_task.delay.return_value = AsyncMock(id=f"mixed-task-{user_id}-{request_num}")

                        return await async_client.post("/api/v1/invoices/upload", files=files)

            elif operation == 1:  # List
                params = {"limit": 10, "skip": (request_num * 10) % 50}
                return await async_client.get("/api/v1/invoices/", params=params)

            elif operation == 2:  # Get single
                invoice_id = invoices[request_num % len(invoices)].id
                return await async_client.get(f"/api/v1/invoices/{invoice_id}")

            else:  # Get single (more gets than others)
                invoice_id = invoices[(user_id + request_num) % len(invoices)].id
                return await async_client.get(f"/api/v1/invoices/{invoice_id}")

        # Load test parameters
        concurrent_users = 30
        requests_per_user = 10

        result = await self.execute_concurrent_requests(
            async_client, mixed_request, concurrent_users, requests_per_user, delay_between_requests=0.02
        )

        # Assertions for mixed workload
        total_expected = concurrent_users * requests_per_user
        assert result.total_requests == total_expected
        assert result.success_rate >= 95, f"Success rate {result.success_rate:.1f}% below 95%"
        assert result.average_response_time < 800, f"Average response time {result.average_response_time:.2f}ms exceeds 800ms"
        assert result.p95_response_time < 2000, f"P95 response time {result.p95_response_time:.2f}ms exceeds 2000ms"

        print(f"Mixed Workload Load Test Results:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_sustained_load_test(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Sustained load test over extended period."""

        async def upload_request(user_id: int, request_num: int):
            """Single upload request."""
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"sustained_{user_id}_{request_num}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/sustained_{user_id}_{request_num}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"sustained-task-{user_id}-{request_num}")

                    response = await async_client.post("/api/v1/invoices/upload", files=files)
                    return response

        # Sustained load parameters
        concurrent_users = 15
        test_duration_seconds = 30

        start_time = time.perf_counter()
        result = LoadTestResult()

        async def sustained_user_session(user_id: int):
            """User session that runs for the test duration."""
            request_num = 0
            while (time.perf_counter() - start_time) < test_duration_seconds:
                request_start = time.perf_counter()

                try:
                    response = await upload_request(user_id, request_num)
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    success = 200 <= response.status_code < 400
                    error = None if success else f"HTTP {response.status_code}"

                    result.add_response(response_time, success, error)
                    request_num += 1

                except Exception as e:
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000
                    result.add_response(response_time, False, str(e))

                # Variable delay to simulate realistic usage
                await asyncio.sleep(0.5 + (user_id * 0.1))

        # Start sustained user sessions
        user_tasks = [
            asyncio.create_task(sustained_user_session(user_id))
            for user_id in range(concurrent_users)
        ]

        # Wait for test duration
        await asyncio.sleep(test_duration_seconds)

        # Wait for remaining requests to complete
        await asyncio.gather(*user_tasks, return_exceptions=True)

        end_time = time.perf_counter()
        result.set_duration(start_time, end_time)

        # Assertions for sustained load
        assert result.total_requests > 0, "No requests completed during sustained test"
        assert result.success_rate >= 90, f"Success rate {result.success_rate:.1f}% below 90% over sustained period"
        assert result.average_response_time < 1500, f"Average response time {result.average_response_time:.2f}ms degrades over time"

        # Check for performance degradation
        if len(result.response_times) >= 100:
            first_half = result.response_times[:len(result.response_times)//2]
            second_half = result.response_times[len(result.response_times)//2:]

            first_avg = statistics.mean(first_half)
            second_avg = statistics.mean(second_half)

            degradation = (second_avg - first_avg) / first_avg * 100
            assert degradation < 50, f"Performance degradation {degradation:.1f}% exceeds 50%"

        print(f"Sustained Load Test Results ({test_duration_seconds}s):")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Average response time: {result.average_response_time:.2f}ms")
        print(f"  P95 response time: {result.p95_response_time:.2f}ms")
        print(f"  Requests per second: {result.requests_per_second:.2f}")

    @pytest.mark.asyncio
    async def test_resource_usage_monitoring(self, async_client: AsyncClient, sample_pdf_content: bytes):
        """Monitor system resource usage during load testing."""

        # Start resource monitoring
        initial_cpu = psutil.cpu_percent(interval=1)
        initial_memory = psutil.virtual_memory().used / 1024 / 1024  # MB

        resource_samples = []

        async def monitor_resources():
            """Monitor system resources during test."""
            while True:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_mb = psutil.virtual_memory().used / 1024 / 1024

                resource_samples.append({
                    "timestamp": time.perf_counter(),
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb
                })

                await asyncio.sleep(0.5)

        async def upload_request(user_id: int, request_num: int):
            """Upload request for load testing."""
            file_data = io.BytesIO(sample_pdf_content)
            files = {"file": (f"resource_{user_id}_{request_num}.pdf", file_data, "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": f"/tmp/resource_{user_id}_{request_num}.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id=f"resource-task-{user_id}-{request_num}")

                    return await async_client.post("/api/v1/invoices/upload", files=files)

        # Start monitoring and load test
        monitor_task = asyncio.create_task(monitor_resources())

        try:
            # Run load test
            result = await self.execute_concurrent_requests(
                async_client, upload_request, concurrent_users=20, requests_per_user=5
            )

        finally:
            # Stop monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Analyze resource usage
        if resource_samples:
            avg_cpu = statistics.mean(s["cpu_percent"] for s in resource_samples)
            max_cpu = max(s["cpu_percent"] for s in resource_samples)
            avg_memory = statistics.mean(s["memory_mb"] for s in resource_samples)
            max_memory = max(s["memory_mb"] for s in resource_samples)
            memory_increase = max_memory - initial_memory

            print(f"Resource Usage Analysis:")
            print(f"  CPU usage - Average: {avg_cpu:.1f}%, Max: {max_cpu:.1f}%")
            print(f"  Memory usage - Average: {avg_memory:.1f}MB, Max: {max_memory:.1f}MB")
            print(f"  Memory increase: {memory_increase:.1f}MB")

            # Resource assertions
            assert max_cpu < 90, f"CPU usage peaked at {max_cpu:.1f}%, exceeds 90%"
            assert memory_increase < 500, f"Memory increased by {memory_increase:.1f}MB, exceeds 500MB"

        # Performance assertions
        assert result.success_rate >= 95, f"Success rate {result.success_rate:.1f}% below 95%"