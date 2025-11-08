#!/usr/bin/env python3
"""
Comprehensive Performance Testing Suite for AP Intake & Validation System

This module provides extensive performance testing capabilities including:
- Load testing with concurrent users
- Stress testing with increasing load
- Resource monitoring and analysis
- Performance regression detection
- API response time analysis
- Database performance testing
- File upload performance testing
"""

import asyncio
import io
import json
import logging
import statistics
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import warnings

import httpx
import psutil
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from unittest.mock import AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress SSL warnings for testing
warnings.filterwarnings("ignore", module="httpx._client")

from app.models.invoice import Invoice, InvoiceStatus
from app.services.storage_service import StorageService
from tests.factories import InvoiceFactory, ExtractionDataFactory


@dataclass
class PerformanceMetrics:
    """Container for performance test metrics."""

    # Basic metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Timing metrics
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    # Resource metrics
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    initial_memory: float = 0.0
    peak_memory: float = 0.0

    # Throughput metrics
    bytes_transferred: int = 0
    requests_per_second: float = 0.0

    # Concurrency metrics
    concurrent_users: int = 0
    max_concurrent_requests: int = 0

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
        return statistics.quantiles(self.response_times, n=20)[18]

    @property
    def p99_response_time(self) -> float:
        """Calculate 99th percentile response time."""
        if not self.response_times:
            return 0.0
        return statistics.quantiles(self.response_times, n=100)[98]

    @property
    def duration(self) -> float:
        """Calculate total test duration in seconds."""
        if not self.start_time or not self.end_time:
            return 0.0
        return self.end_time - self.start_time

    @property
    def actual_rps(self) -> float:
        """Calculate actual requests per second."""
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration

    @property
    def average_cpu_usage(self) -> float:
        """Calculate average CPU usage during test."""
        if not self.cpu_samples:
            return 0.0
        return statistics.mean(self.cpu_samples)

    @property
    def peak_cpu_usage(self) -> float:
        """Calculate peak CPU usage during test."""
        if not self.cpu_samples:
            return 0.0
        return max(self.cpu_samples)

    @property
    def memory_increase(self) -> float:
        """Calculate memory increase in MB."""
        return self.peak_memory - self.initial_memory

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "median_response_time": self.median_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "duration": self.duration,
            "actual_rps": self.actual_rps,
            "average_cpu_usage": self.average_cpu_usage,
            "peak_cpu_usage": self.peak_cpu_usage,
            "memory_increase": self.memory_increase,
            "bytes_transferred": self.bytes_transferred,
            "concurrent_users": self.concurrent_users,
            "error_summary": self._summarize_errors()
        }

    def _summarize_errors(self) -> Dict[str, int]:
        """Summarize errors by type."""
        error_counts = {}
        for error in self.errors:
            error_type = error.split(':')[0] if ':' in error else 'unknown'
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        return error_counts


class ResourceMonitor:
    """Monitor system resources during performance tests."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.monitoring = False
        self.cpu_samples: List[float] = []
        self.memory_samples: List[float] = []
        self.disk_io_samples: List[Dict[str, float]] = []
        self.network_io_samples: List[Dict[str, float]] = []
        self.process = psutil.Process()

    async def start_monitoring(self):
        """Start resource monitoring in background."""
        self.monitoring = True
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring = False
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Resource monitoring loop."""
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=None)
                self.cpu_samples.append(cpu_percent)

                # Memory usage
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                self.memory_samples.append(memory_mb)

                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    self.disk_io_samples.append({
                        "read_bytes": disk_io.read_bytes,
                        "write_bytes": disk_io.write_bytes,
                        "read_count": disk_io.read_count,
                        "write_count": disk_io.write_count
                    })

                # Network I/O
                network_io = psutil.net_io_counters()
                if network_io:
                    self.network_io_samples.append({
                        "bytes_sent": network_io.bytes_sent,
                        "bytes_recv": network_io.bytes_recv,
                        "packets_sent": network_io.packets_sent,
                        "packets_recv": network_io.packets_recv
                    })

                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.warning(f"Resource monitoring error: {e}")
                await asyncio.sleep(self.interval)

    def get_peak_memory(self) -> float:
        """Get peak memory usage in MB."""
        if not self.memory_samples:
            return 0.0
        return max(self.memory_samples)

    def get_average_cpu(self) -> float:
        """Get average CPU usage."""
        if not self.cpu_samples:
            return 0.0
        return statistics.mean(self.cpu_samples)

    def get_peak_cpu(self) -> float:
        """Get peak CPU usage."""
        if not self.cpu_samples:
            return 0.0
        return max(self.cpu_samples)


class PerformanceTestRunner:
    """Main performance test runner with comprehensive monitoring."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[PerformanceMetrics] = []
        self.resource_monitor = ResourceMonitor()

    async def run_load_test(
        self,
        endpoint: str,
        method: str = "GET",
        concurrent_users: int = 10,
        requests_per_user: int = 10,
        duration_seconds: Optional[int] = None,
        request_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        files: Optional[Dict] = None,
        delay_between_requests: float = 0.1
    ) -> PerformanceMetrics:
        """Run a comprehensive load test."""

        metrics = PerformanceMetrics()
        metrics.concurrent_users = concurrent_users
        metrics.start_time = time.perf_counter()

        # Start resource monitoring
        await self.resource_monitor.start_monitoring()
        metrics.initial_memory = self.resource_monitor.initial_memory

        try:
            if duration_seconds:
                # Run for specified duration
                await self._run_duration_test(
                    metrics, endpoint, method, concurrent_users,
                    duration_seconds, request_data, headers, files
                )
            else:
                # Run fixed number of requests
                await self._run_fixed_requests_test(
                    metrics, endpoint, method, concurrent_users,
                    requests_per_user, request_data, headers, files, delay_between_requests
                )
        finally:
            metrics.end_time = time.perf_counter()

            # Stop monitoring and collect resource metrics
            await self.resource_monitor.stop_monitoring()
            metrics.cpu_samples = self.resource_monitor.cpu_samples
            metrics.memory_samples = self.resource_monitor.memory_samples
            metrics.peak_memory = self.resource_monitor.get_peak_memory()

        # Calculate final metrics
        metrics.requests_per_second = metrics.actual_rps

        self.results.append(metrics)
        return metrics

    async def _run_fixed_requests_test(
        self,
        metrics: PerformanceMetrics,
        endpoint: str,
        method: str,
        concurrent_users: int,
        requests_per_user: int,
        request_data: Optional[Dict],
        headers: Optional[Dict],
        files: Optional[Dict],
        delay: float
    ):
        """Run test with fixed number of requests per user."""

        async def user_session(user_id: int):
            """Simulate a user session."""
            for request_num in range(requests_per_user):
                request_start = time.perf_counter()

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await self._make_request(
                            client, endpoint, method, request_data, headers, files
                        )

                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    success = 200 <= response.status_code < 400
                    error = None if success else f"HTTP {response.status_code}: {response.text[:200]}"

                    metrics.total_requests += 1
                    metrics.response_times.append(response_time)
                    metrics.bytes_transferred += len(response.content)

                    if success:
                        metrics.successful_requests += 1
                    else:
                        metrics.failed_requests += 1
                        metrics.errors.append(error)

                except Exception as e:
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    metrics.total_requests += 1
                    metrics.response_times.append(response_time)
                    metrics.failed_requests += 1
                    metrics.errors.append(f"Exception: {str(e)}")

                # Delay between requests
                if delay > 0:
                    await asyncio.sleep(delay)

        # Create and run user sessions
        user_tasks = [
            asyncio.create_task(user_session(user_id))
            for user_id in range(concurrent_users)
        ]

        await asyncio.gather(*user_tasks, return_exceptions=True)

    async def _run_duration_test(
        self,
        metrics: PerformanceMetrics,
        endpoint: str,
        method: str,
        concurrent_users: int,
        duration_seconds: int,
        request_data: Optional[Dict],
        headers: Optional[Dict],
        files: Optional[Dict]
    ):
        """Run test for specified duration."""

        async def continuous_user_session(user_id: int):
            """User session that runs for the test duration."""
            start_time = time.perf_counter()
            request_num = 0

            while (time.perf_counter() - start_time) < duration_seconds:
                request_start = time.perf_counter()

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await self._make_request(
                            client, endpoint, method, request_data, headers, files
                        )

                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    success = 200 <= response.status_code < 400
                    error = None if success else f"HTTP {response.status_code}"

                    metrics.total_requests += 1
                    metrics.response_times.append(response_time)
                    metrics.bytes_transferred += len(response.content)

                    if success:
                        metrics.successful_requests += 1
                    else:
                        metrics.failed_requests += 1
                        metrics.errors.append(error)

                    request_num += 1

                except Exception as e:
                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    metrics.total_requests += 1
                    metrics.response_times.append(response_time)
                    metrics.failed_requests += 1
                    metrics.errors.append(f"Exception: {str(e)}")

                # Variable delay to simulate realistic usage
                await asyncio.sleep(0.1 + (user_id * 0.05))

        # Start continuous user sessions
        user_tasks = [
            asyncio.create_task(continuous_user_session(user_id))
            for user_id in range(concurrent_users)
        ]

        # Wait for test duration
        await asyncio.sleep(duration_seconds)

        # Wait for remaining requests to complete
        await asyncio.gather(*user_tasks, return_exceptions=True)

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str,
        data: Optional[Dict],
        headers: Optional[Dict],
        files: Optional[Dict]
    ) -> httpx.Response:
        """Make HTTP request with proper error handling."""
        url = f"{self.base_url}{endpoint}"

        if method.upper() == "GET":
            return await client.get(url, headers=headers, params=data)
        elif method.upper() == "POST":
            if files:
                return await client.post(url, headers=headers, data=data, files=files)
            else:
                return await client.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            if files:
                return await client.put(url, headers=headers, data=data, files=files)
            else:
                return await client.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            return await client.delete(url, headers=headers, params=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive performance test report."""
        if not self.results:
            return "No test results available"

        report = []
        report.append("# Performance Test Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total test scenarios: {len(self.results)}")
        report.append("")

        # Summary table
        report.append("## Test Summary")
        report.append("| Test | Requests | Success Rate | Avg Response | P95 Response | RPS | Peak CPU | Memory Increase |")
        report.append("|------|----------|--------------|--------------|--------------|-----|----------|-----------------|")

        for i, metrics in enumerate(self.results):
            report.append(
                f"| Test {i+1} | {metrics.total_requests} | "
                f"{metrics.success_rate:.1f}% | {metrics.average_response_time:.1f}ms | "
                f"{metrics.p95_response_time:.1f}ms | {metrics.actual_rps:.1f} | "
                f"{metrics.peak_cpu_usage:.1f}% | {metrics.memory_increase:.1f}MB |"
            )

        report.append("")

        # Detailed results for each test
        for i, metrics in enumerate(self.results):
            report.append(f"## Test {i+1} Detailed Results")
            report.append(json.dumps(metrics.to_dict(), indent=2))
            report.append("")

        report_text = "\n".join(report)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            logger.info(f"Report saved to {output_file}")

        return report_text


@pytest.mark.performance
@pytest.mark.slow
class TestComprehensivePerformance:
    """Comprehensive performance testing suite."""

    @pytest.fixture
    def sample_pdf_content(self) -> bytes:
        """Sample PDF content for upload testing."""
        return b"%PDF-1.4\n" + b"x" * (1024 * 1024)  # 1MB PDF

    @pytest.fixture
    def performance_runner(self) -> PerformanceTestRunner:
        """Get performance test runner instance."""
        return PerformanceTestRunner()

    @pytest.mark.asyncio
    async def test_api_load_test_small(self, performance_runner: PerformanceTestRunner):
        """Small load test - 10 concurrent users, 10 requests each."""

        metrics = await performance_runner.run_load_test(
            endpoint="/api/v1/invoices/",
            method="GET",
            concurrent_users=10,
            requests_per_user=10,
            delay_between_requests=0.1
        )

        # Assertions
        assert metrics.total_requests == 100
        assert metrics.success_rate >= 95, f"Success rate {metrics.success_rate:.1f}% below 95%"
        assert metrics.average_response_time < 500, f"Average response time {metrics.average_response_time:.2f}ms exceeds 500ms"
        assert metrics.p95_response_time < 1000, f"P95 response time {metrics.p95_response_time:.2f}ms exceeds 1000ms"
        assert metrics.actual_rps >= 50, f"RPS {metrics.actual_rps:.2f} below minimum 50"
        assert metrics.peak_cpu_usage < 80, f"Peak CPU usage {metrics.peak_cpu_usage:.1f}% exceeds 80%"
        assert metrics.memory_increase < 100, f"Memory increase {metrics.memory_increase:.1f}MB exceeds 100MB"

        logger.info(f"Small Load Test Results: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_api_load_test_medium(self, performance_runner: PerformanceTestRunner):
        """Medium load test - 25 concurrent users, 20 requests each."""

        metrics = await performance_runner.run_load_test(
            endpoint="/api/v1/invoices/",
            method="GET",
            concurrent_users=25,
            requests_per_user=20,
            delay_between_requests=0.05
        )

        # Assertions for medium load
        assert metrics.total_requests == 500
        assert metrics.success_rate >= 90, f"Success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.average_response_time < 1000, f"Average response time {metrics.average_response_time:.2f}ms exceeds 1000ms"
        assert metrics.p95_response_time < 2000, f"P95 response time {metrics.p95_response_time:.2f}ms exceeds 2000ms"
        assert metrics.peak_cpu_usage < 90, f"Peak CPU usage {metrics.peak_cpu_usage:.1f}% exceeds 90%"

        logger.info(f"Medium Load Test Results: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_api_stress_test(self, performance_runner: PerformanceTestRunner):
        """Stress test - gradually increasing concurrent users."""

        stress_results = []
        user_counts = [5, 10, 20, 50, 100]

        for users in user_counts:
            logger.info(f"Running stress test with {users} concurrent users")

            metrics = await performance_runner.run_load_test(
                endpoint="/api/v1/invoices/",
                method="GET",
                concurrent_users=users,
                requests_per_user=5,
                delay_between_requests=0.01
            )

            stress_results.append({
                "concurrent_users": users,
                "success_rate": metrics.success_rate,
                "avg_response_time": metrics.average_response_time,
                "p95_response_time": metrics.p95_response_time,
                "rps": metrics.actual_rps,
                "peak_cpu": metrics.peak_cpu_usage,
                "memory_increase": metrics.memory_increase
            })

            # Stop if success rate drops too low
            if metrics.success_rate < 80:
                logger.warning(f"Success rate dropped to {metrics.success_rate:.1f}% at {users} users - stopping stress test")
                break

            # Brief pause between stress levels
            await asyncio.sleep(2)

        # Analyze stress test results
        logger.info(f"Stress Test Results: {json.dumps(stress_results, indent=2)}")

        # Find breaking point
        acceptable_tests = [r for r in stress_results if r["success_rate"] >= 90 and r["avg_response_time"] < 2000]
        max_sustainable_users = max([r["concurrent_users"] for r in acceptable_tests]) if acceptable_tests else 0

        assert max_sustainable_users >= 20, f"System should sustain at least 20 concurrent users, only sustained {max_sustainable_users}"

        logger.info(f"Maximum sustainable concurrent users: {max_sustainable_users}")

    @pytest.mark.asyncio
    async def test_upload_performance_load(self, performance_runner: PerformanceTestRunner, sample_pdf_content: bytes):
        """File upload performance test under load."""

        async def upload_request():
            """Prepare upload request data."""
            files = {
                "file": ("load_test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")
            }

            # Mock storage service to avoid actual file operations
            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/load_test.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="load-test-task")

                    return files, {"mocked": True}

        # Test upload performance
        metrics = await performance_runner.run_load_test(
            endpoint="/api/v1/invoices/upload",
            method="POST",
            concurrent_users=15,
            requests_per_user=5,
            delay_between_requests=0.2
        )

        # Upload-specific assertions
        assert metrics.total_requests == 75
        assert metrics.success_rate >= 90, f"Upload success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.average_response_time < 2000, f"Upload average response time {metrics.average_response_time:.2f}ms exceeds 2000ms"
        assert metrics.p95_response_time < 5000, f"Upload P95 response time {metrics.p95_response_time:.2f}ms exceeds 5000ms"

        logger.info(f"Upload Load Test Results: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, performance_runner: PerformanceTestRunner):
        """Sustained load test over extended period."""

        # Run sustained load for 60 seconds
        metrics = await performance_runner.run_load_test(
            endpoint="/api/v1/invoices/",
            method="GET",
            concurrent_users=20,
            duration_seconds=60
        )

        # Sustained load assertions
        assert metrics.total_requests > 100, "Too few requests completed during sustained test"
        assert metrics.success_rate >= 95, f"Success rate {metrics.success_rate:.1f}% below 95% over sustained period"
        assert metrics.average_response_time < 1000, f"Average response time {metrics.average_response_time:.2f}ms degrades over time"
        assert metrics.memory_increase < 200, f"Memory increased by {metrics.memory_increase:.1f}MB during sustained test"

        # Check for performance degradation
        if len(metrics.response_times) >= 100:
            first_half = metrics.response_times[:len(metrics.response_times)//2]
            second_half = metrics.response_times[len(metrics.response_times)//2:]

            first_avg = statistics.mean(first_half)
            second_avg = statistics.mean(second_half)

            degradation = (second_avg - first_avg) / first_avg * 100 if first_avg > 0 else 0
            assert degradation < 30, f"Performance degradation {degradation:.1f}% exceeds 30%"

        logger.info(f"Sustained Load Test Results: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, performance_runner: PerformanceTestRunner, sample_pdf_content: bytes):
        """Mixed workload test with different API endpoints."""

        # Define mixed workload scenarios
        workload_scenarios = [
            {"endpoint": "/api/v1/invoices/", "method": "GET", "weight": 0.6},
            {"endpoint": "/api/v1/invoices/", "method": "GET", "weight": 0.3, "params": {"limit": 10}},
            {"endpoint": "/api/v1/invoices/upload", "method": "POST", "weight": 0.1},
        ]

        metrics = PerformanceMetrics()
        metrics.concurrent_users = 25
        metrics.start_time = time.perf_counter()

        await performance_runner.resource_monitor.start_monitoring()
        metrics.initial_memory = performance_runner.resource_monitor.initial_memory

        try:
            async def mixed_user_session(user_id: int):
                """User session with mixed API calls."""
                request_num = 0

                while request_num < 20:  # 20 requests per user
                    # Choose scenario based on weights
                    import random
                    scenario = random.choices(
                        workload_scenarios,
                        weights=[s["weight"] for s in workload_scenarios]
                    )[0]

                    request_start = time.perf_counter()

                    try:
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            if scenario["method"] == "GET":
                                response = await client.get(
                                    f"{performance_runner.base_url}{scenario['endpoint']}",
                                    params=scenario.get("params")
                                )
                            elif scenario["method"] == "POST":
                                files = {"file": ("mixed.pdf", io.BytesIO(sample_pdf_content), "application/pdf")}

                                with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                                    mock_storage.return_value = {"file_path": "/tmp/mixed.pdf"}

                                    with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                                        mock_task.delay.return_value = AsyncMock(id="mixed-task")

                                        response = await client.post(
                                            f"{performance_runner.base_url}{scenario['endpoint']}",
                                            files=files
                                        )

                        request_end = time.perf_counter()
                        response_time = (request_end - request_start) * 1000

                        success = 200 <= response.status_code < 400
                        error = None if success else f"HTTP {response.status_code}"

                        metrics.total_requests += 1
                        metrics.response_times.append(response_time)
                        metrics.bytes_transferred += len(response.content)

                        if success:
                            metrics.successful_requests += 1
                        else:
                            metrics.failed_requests += 1
                            metrics.errors.append(error)

                        request_num += 1

                    except Exception as e:
                        request_end = time.perf_counter()
                        response_time = (request_end - request_start) * 1000

                        metrics.total_requests += 1
                        metrics.response_times.append(response_time)
                        metrics.failed_requests += 1
                        metrics.errors.append(f"Exception: {str(e)}")
                        request_num += 1

                    # Variable delay
                    await asyncio.sleep(0.1 + (user_id * 0.02))

            # Run mixed workload sessions
            user_tasks = [
                asyncio.create_task(mixed_user_session(user_id))
                for user_id in range(metrics.concurrent_users)
            ]

            await asyncio.gather(*user_tasks, return_exceptions=True)

        finally:
            metrics.end_time = time.perf_counter()
            await performance_runner.resource_monitor.stop_monitoring()
            metrics.cpu_samples = performance_runner.resource_monitor.cpu_samples
            metrics.memory_samples = performance_runner.resource_monitor.memory_samples
            metrics.peak_memory = performance_runner.resource_monitor.get_peak_memory()
            metrics.requests_per_second = metrics.actual_rps

        # Mixed workload assertions
        assert metrics.total_requests > 400, "Too few requests in mixed workload test"
        assert metrics.success_rate >= 90, f"Mixed workload success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.average_response_time < 800, f"Mixed workload average response time {metrics.average_response_time:.2f}ms exceeds 800ms"

        logger.info(f"Mixed Workload Test Results: {json.dumps(metrics.to_dict(), indent=2)}")

    def test_performance_report_generation(self, performance_runner: PerformanceTestRunner):
        """Test performance report generation."""
        # Mock some test results
        mock_metrics = PerformanceMetrics()
        mock_metrics.total_requests = 100
        mock_metrics.successful_requests = 95
        mock_metrics.response_times = [100, 150, 200, 120, 180]
        mock_metrics.start_time = time.perf_counter() - 10
        mock_metrics.end_time = time.perf_counter()
        mock_metrics.concurrent_users = 10
        mock_metrics.cpu_samples = [30, 40, 35, 45, 38]
        mock_metrics.memory_samples = [100, 110, 105, 115, 108]
        mock_metrics.peak_memory = 120
        mock_metrics.initial_memory = 95

        performance_runner.results.append(mock_metrics)

        # Generate report
        report = performance_runner.generate_report()

        # Verify report content
        assert "Performance Test Report" in report
        assert "Test Summary" in report
        assert "100" in report  # Total requests
        assert "95.0%" in report  # Success rate

        # Test file output
        report_file = "/tmp/test_performance_report.md"
        performance_runner.generate_report(report_file)

        assert Path(report_file).exists()

        # Clean up
        Path(report_file).unlink()


# CLI interface for running performance tests
async def main():
    """CLI interface for running performance tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Run performance tests for AP Intake System")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--requests", type=int, default=10, help="Requests per user")
    parser.add_argument("--duration", type=int, help="Test duration in seconds")
    parser.add_argument("--endpoint", default="/api/v1/invoices/", help="API endpoint to test")
    parser.add_argument("--method", default="GET", help="HTTP method")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--upload", action="store_true", help="Test file upload")

    args = parser.parse_args()

    runner = PerformanceTestRunner(args.url)

    if args.upload:
        # Sample file for upload testing
        sample_content = b"%PDF-1.4\n" + b"x" * (1024 * 1024)

        async def upload_request():
            files = {"file": ("test.pdf", io.BytesIO(sample_content), "application/pdf")}
            return files, {}

        metrics = await runner.run_load_test(
            endpoint=args.endpoint,
            method=args.method,
            concurrent_users=args.users,
            requests_per_user=args.requests,
            duration_seconds=args.duration
        )
    else:
        metrics = await runner.run_load_test(
            endpoint=args.endpoint,
            method=args.method,
            concurrent_users=args.users,
            requests_per_user=args.requests,
            duration_seconds=args.duration
        )

    # Generate and print report
    report = runner.generate_report(args.output)
    print(report)

    # Print summary to stdout
    print(f"\n=== Performance Test Summary ===")
    print(f"Total Requests: {metrics.total_requests}")
    print(f"Success Rate: {metrics.success_rate:.1f}%")
    print(f"Average Response Time: {metrics.average_response_time:.2f}ms")
    print(f"P95 Response Time: {metrics.p95_response_time:.2f}ms")
    print(f"Requests Per Second: {metrics.actual_rps:.2f}")
    print(f"Peak CPU Usage: {metrics.peak_cpu_usage:.1f}%")
    print(f"Memory Increase: {metrics.memory_increase:.1f}MB")


if __name__ == "__main__":
    asyncio.run(main())