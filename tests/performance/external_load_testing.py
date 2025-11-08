#!/usr/bin/env python3
"""
External Load Testing Integration for AP Intake & Validation System

This module provides integration with professional load testing tools:
- Apache Bench (ab)
- wrk (HTTP benchmarking tool)
- Custom concurrent request testing
- Database performance testing under load
- Background task queue stress testing
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import psutil
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

from app.models.invoice import Invoice, InvoiceStatus
from tests.factories import InvoiceFactory


@dataclass
class LoadTestResult:
    """Container for load test results from external tools."""

    tool_name: str
    test_url: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    requests_per_second: float = 0.0
    time_per_request: float = 0.0
    time_per_request_concurrent: float = 0.0
    transfer_rate: float = 0.0
    min_response_time: float = 0.0
    mean_response_time: float = 0.0
    max_response_time: float = 0.0
    percentile_50: float = 0.0
    percentile_95: float = 0.0
    percentile_99: float = 0.0
    errors: List[str] = field(default_factory=list)
    raw_output: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    concurrent_users: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def duration(self) -> float:
        """Test duration in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "test_url": self.test_url,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "requests_per_second": self.requests_per_second,
            "time_per_request": self.time_per_request,
            "time_per_request_concurrent": self.time_per_request_concurrent,
            "transfer_rate": self.transfer_rate,
            "min_response_time": self.min_response_time,
            "mean_response_time": self.mean_response_time,
            "max_response_time": self.max_response_time,
            "percentile_50": self.percentile_50,
            "percentile_95": self.percentile_95,
            "percentile_99": self.percentile_99,
            "duration": self.duration,
            "concurrent_users": self.concurrent_users,
            "errors": self.errors
        }


class ApacheBenchRunner:
    """Apache Bench (ab) integration for load testing."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ab_path = self._find_ab_executable()

    def _find_ab_executable(self) -> Optional[str]:
        """Find Apache Bench executable."""
        possible_paths = [
            "/usr/bin/ab",
            "/usr/local/bin/ab",
            "/usr/sbin/ab",
            "ab"  # Try PATH
        ]

        for path in possible_paths:
            try:
                if path == "ab":
                    # Check if ab is in PATH
                    result = subprocess.run(["which", "ab"], capture_output=True, text=True)
                    if result.returncode == 0:
                        return result.stdout.strip()
                else:
                    # Check if path exists
                    if os.path.exists(path):
                        return path
            except Exception:
                continue

        return None

    def is_available(self) -> bool:
        """Check if Apache Bench is available."""
        return self.ab_path is not None

    async def run_test(
        self,
        endpoint: str,
        concurrent_users: int = 10,
        total_requests: int = 100,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
        post_data: Optional[str] = None
    ) -> LoadTestResult:
        """Run Apache Bench load test."""
        if not self.is_available():
            raise RuntimeError("Apache Bench (ab) is not available")

        result = LoadTestResult(
            tool_name="Apache Bench",
            test_url=f"{self.base_url}{endpoint}",
            concurrent_users=concurrent_users
        )

        # Build ab command
        cmd = [
            self.ab_path,
            "-n", str(total_requests),
            "-c", str(concurrent_users),
            "-t", str(timeout),
            "-g", "/tmp/ab_plot.tsv",  # GNUPLOT output
            "-e", "/tmp/ab_csv.csv",   # CSV output
        ]

        # Add headers
        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        # Add POST data
        if post_data:
            cmd.extend(["-p", post_data, "-T", "application/json"])

        # Add URL
        cmd.append(f"{self.base_url}{endpoint}")

        logger.info(f"Running Apache Bench: {' '.join(cmd)}")

        # Run test
        start_time = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            result.start_time = start_time
            result.end_time = time.perf_counter()

            if process.returncode != 0:
                result.errors.append(f"Apache Bench failed with return code {process.returncode}")
                result.errors.append(stderr.decode())
                return result

            # Parse output
            result.raw_output = stdout.decode()
            self._parse_ab_output(result)

        except Exception as e:
            result.end_time = time.perf_counter()
            result.errors.append(f"Exception running Apache Bench: {str(e)}")

        return result

    def _parse_ab_output(self, result: LoadTestResult):
        """Parse Apache Bench output."""
        lines = result.raw_output.split('\n')

        for line in lines:
            line = line.strip()

            # Parse key metrics
            if "Complete requests:" in line:
                result.successful_requests = int(line.split(':')[1].strip())
            elif "Failed requests:" in line:
                result.failed_requests = int(line.split(':')[1].strip())
            elif "Requests per second:" in line:
                result.requests_per_second = float(line.split(':')[1].split()[0])
            elif "Time per request:" in line and "mean, across all" not in line:
                result.time_per_request = float(line.split(':')[1].split()[0])
            elif "Time per request:" in line and "mean, across all" in line:
                result.time_per_request_concurrent = float(line.split(':')[1].split()[0])
            elif "Transfer rate:" in line:
                result.transfer_rate = float(line.split(':')[1].split()[0])
            elif "Connection Times (ms)" in line:
                # Parse the table that follows
                self._parse_connection_times(lines, result)

        result.total_requests = result.successful_requests + result.failed_requests

    def _parse_connection_times(self, lines: List[str], result: LoadTestResult):
        """Parse connection times table from Apache Bench output."""
        try:
            # Find the connection times table
            table_start = None
            for i, line in enumerate(lines):
                if "Connection Times (ms)" in line:
                    table_start = i + 2  # Skip header lines
                    break

            if table_start and table_start + 2 < len(lines):
                # Parse min, mean, max values
                total_line = lines[table_start + 2].strip()
                if total_line.startswith("Total:"):
                    parts = total_line.split()
                    if len(parts) >= 4:
                        result.min_response_time = float(parts[1])
                        result.mean_response_time = float(parts[2])
                        result.max_response_time = float(parts[3])
        except Exception as e:
            logger.warning(f"Failed to parse connection times: {e}")


class WrkRunner:
    """wrk HTTP benchmarking tool integration."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.wrk_path = self._find_wrk_executable()

    def _find_wrk_executable(self) -> Optional[str]:
        """Find wrk executable."""
        possible_paths = [
            "/usr/bin/wrk",
            "/usr/local/bin/wrk",
            "wrk"  # Try PATH
        ]

        for path in possible_paths:
            try:
                if path == "wrk":
                    result = subprocess.run(["which", "wrk"], capture_output=True, text=True)
                    if result.returncode == 0:
                        return result.stdout.strip()
                else:
                    if os.path.exists(path):
                        return path
            except Exception:
                continue

        return None

    def is_available(self) -> bool:
        """Check if wrk is available."""
        return self.wrk_path is not None

    async def run_test(
        self,
        endpoint: str,
        concurrent_users: int = 10,
        duration_seconds: int = 30,
        timeout: int = 30,
        script: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> LoadTestResult:
        """Run wrk load test."""
        if not self.is_available():
            raise RuntimeError("wrk is not available")

        result = LoadTestResult(
            tool_name="wrk",
            test_url=f"{self.base_url}{endpoint}",
            concurrent_users=concurrent_users
        )

        # Build wrk command
        cmd = [
            self.wrk_path,
            "-t", str(min(concurrent_users, 12)),  # threads, max 12
            "-c", str(concurrent_users),            # connections
            "-d", f"{duration_seconds}s",           # duration
            "--timeout", str(timeout),              # timeout
        ]

        # Add script if provided
        if script:
            cmd.extend(["-s", script])

        # Add URL
        cmd.append(f"{self.base_url}{endpoint}")

        logger.info(f"Running wrk: {' '.join(cmd)}")

        # Run test
        start_time = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            result.start_time = start_time
            result.end_time = time.perf_counter()

            if process.returncode != 0:
                result.errors.append(f"wrk failed with return code {process.returncode}")
                result.errors.append(stderr.decode())
                return result

            # Parse output
            result.raw_output = stdout.decode()
            self._parse_wrk_output(result)

        except Exception as e:
            result.end_time = time.perf_counter()
            result.errors.append(f"Exception running wrk: {str(e)}")

        return result

    def _parse_wrk_output(self, result: LoadTestResult):
        """Parse wrk output."""
        lines = result.raw_output.split('\n')

        for line in lines:
            line = line.strip()

            # Parse key metrics
            if "requests in" in line and "seconds" in line:
                parts = line.split()
                result.total_requests = int(parts[0])
                # Duration is in the line
                for i, part in enumerate(parts):
                    if part == "requests" and i + 2 < len(parts):
                        result.end_time = result.start_time + float(parts[i + 1])
                        break

            elif "requests/sec" in line:
                result.requests_per_second = float(line.split()[0])

            elif "Latency Distribution" in line:
                # Parse latency distribution
                self._parse_latency_distribution(lines, result)

        # Calculate successful requests (wrk doesn't report failures separately)
        result.successful_requests = result.total_requests

    def _parse_latency_distribution(self, lines: List[str], result: LoadTestResult):
        """Parse latency distribution from wrk output."""
        try:
            # Find the latency distribution section
            table_start = None
            for i, line in enumerate(lines):
                if "Latency Distribution" in line:
                    table_start = i + 2  # Skip header
                    break

            if table_start:
                # Parse percentile values
                for i in range(table_start, min(table_start + 10, len(lines))):
                    line = lines[i].strip()
                    if "%" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            percentile = parts[0]
                            latency = parts[1].replace('ms', '').replace('us', '')

                            # Convert to milliseconds
                            if 'us' in parts[1]:
                                latency_ms = float(latency) / 1000
                            else:
                                latency_ms = float(latency)

                            if percentile == "50%":
                                result.percentile_50 = latency_ms
                            elif percentile == "95%":
                                result.percentile_95 = latency_ms
                            elif percentile == "99%":
                                result.percentile_99 = latency_ms

                            # Also capture min/max if available
                            if percentile == "min":
                                result.min_response_time = latency_ms
                            elif percentile == "max":
                                result.max_response_time = latency_ms

                # Calculate mean if not directly available
                if result.percentile_50 > 0 and result.mean_response_time == 0:
                    result.mean_response_time = result.percentile_50

        except Exception as e:
            logger.warning(f"Failed to parse latency distribution: {e}")


class CustomLoadTester:
    """Custom Python-based load tester for advanced scenarios."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def run_custom_load_test(
        self,
        scenarios: List[Dict[str, Any]],
        duration_seconds: int = 60,
        ramp_up_seconds: int = 10
    ) -> List[LoadTestResult]:
        """Run custom load test with multiple scenarios."""
        results = []

        for scenario in scenarios:
            logger.info(f"Running scenario: {scenario.get('name', 'unnamed')}")

            result = await self._run_scenario(scenario, duration_seconds, ramp_up_seconds)
            results.append(result)

        return results

    async def _run_scenario(
        self,
        scenario: Dict[str, Any],
        duration_seconds: int,
        ramp_up_seconds: int
    ) -> LoadTestResult:
        """Run a single load test scenario."""
        result = LoadTestResult(
            tool_name="Custom Load Tester",
            test_url=f"{self.base_url}{scenario['endpoint']}",
            concurrent_users=scenario['concurrent_users']
        )

        start_time = time.perf_counter()
        result.start_time = start_time

        # Ramp-up logic
        active_sessions = []
        session_start_interval = ramp_up_seconds / scenario['concurrent_users']

        async def user_session(user_id: int, start_delay: float):
            """Individual user session."""
            await asyncio.sleep(start_delay)  # Ramp-up delay

            session_start = time.perf_counter()
            requests_made = 0

            while (time.perf_counter() - session_start) < duration_seconds:
                request_start = time.perf_counter()

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        method = scenario.get('method', 'GET').upper()
                        endpoint = scenario['endpoint']
                        headers = scenario.get('headers', {})
                        data = scenario.get('data')

                        if method == 'GET':
                            response = await client.get(
                                f"{self.base_url}{endpoint}",
                                headers=headers,
                                params=data
                            )
                        elif method == 'POST':
                            response = await client.post(
                                f"{self.base_url}{endpoint}",
                                headers=headers,
                                json=data
                            )
                        else:
                            raise ValueError(f"Unsupported method: {method}")

                    request_end = time.perf_counter()
                    response_time = (request_end - request_start) * 1000

                    success = 200 <= response.status_code < 400
                    error = None if success else f"HTTP {response.status_code}"

                    result.total_requests += 1
                    if success:
                        result.successful_requests += 1
                    else:
                        result.failed_requests += 1
                        result.errors.append(error)

                    # Update response time metrics
                    result.response_times.append(response_time) if hasattr(result, 'response_times') else None

                    requests_made += 1

                    # Delay between requests
                    delay = scenario.get('delay_between_requests', 0.1)
                    await asyncio.sleep(delay)

                except Exception as e:
                    request_end = time.perf_counter()
                    result.failed_requests += 1
                    result.errors.append(f"Exception: {str(e)}")

        # Start user sessions with ramp-up
        for user_id in range(scenario['concurrent_users']):
            start_delay = user_id * session_start_interval
            session = asyncio.create_task(user_session(user_id, start_delay))
            active_sessions.append(session)

        # Wait for all sessions to complete
        await asyncio.gather(*active_sessions, return_exceptions=True)

        result.end_time = time.perf_counter()
        result.requests_per_second = result.total_requests / result.duration if result.duration > 0 else 0

        return result


class DatabaseLoadTester:
    """Database performance testing under load."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def test_database_load(
        self,
        concurrent_connections: int = 20,
        queries_per_connection: int = 100,
        query_types: List[str] = None
    ) -> Dict[str, Any]:
        """Test database performance under concurrent load."""
        if query_types is None:
            query_types = ['select', 'insert', 'update', 'complex_select']

        results = {
            'query_types': {},
            'total_queries': 0,
            'total_time': 0,
            'errors': []
        }

        start_time = time.perf_counter()

        for query_type in query_types:
            logger.info(f"Testing {query_type} queries under load")

            type_results = await self._test_query_type(
                query_type,
                concurrent_connections,
                queries_per_connection
            )

            results['query_types'][query_type] = type_results
            results['total_queries'] += type_results['total_queries']
            results['total_time'] += type_results['total_time']
            results['errors'].extend(type_results['errors'])

        results['total_time'] = time.perf_counter() - start_time
        results['queries_per_second'] = results['total_queries'] / results['total_time'] if results['total_time'] > 0 else 0

        return results

    async def _test_query_type(
        self,
        query_type: str,
        concurrent_connections: int,
        queries_per_connection: int
    ) -> Dict[str, Any]:
        """Test specific query type under load."""
        results = {
            'query_type': query_type,
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_time': 0,
            'query_times': [],
            'errors': []
        }

        async def db_session_worker():
            """Worker that executes database queries."""
            for i in range(queries_per_connection):
                query_start = time.perf_counter()

                try:
                    if query_type == 'select':
                        result = await self.db_session.execute(
                            text("SELECT COUNT(*) FROM invoices LIMIT 1")
                        )
                    elif query_type == 'insert':
                        # Insert test record
                        await self.db_session.execute(
                            text("""
                                INSERT INTO invoices (id, vendor_id, status, created_at)
                                VALUES (gen_random_uuid(), gen_random_uuid(), 'received', NOW())
                            """)
                        )
                        await self.db_session.commit()
                    elif query_type == 'update':
                        # Update random record
                        await self.db_session.execute(
                            text("""
                                UPDATE invoices
                                SET status = 'processed'
                                WHERE id = (
                                    SELECT id FROM invoices
                                    WHERE status = 'received'
                                    LIMIT 1
                                )
                            """)
                        )
                        await self.db_session.commit()
                    elif query_type == 'complex_select':
                        # Complex analytical query
                        result = await self.db_session.execute(text("""
                            SELECT
                                status,
                                COUNT(*) as count,
                                AVG(EXTRACT(EPOCH FROM (NOW() - created_at))/3600) as avg_age_hours
                            FROM invoices
                            GROUP BY status
                            ORDER BY count DESC
                        """))
                    else:
                        raise ValueError(f"Unknown query type: {query_type}")

                    query_end = time.perf_counter()
                    query_time = (query_end - query_start) * 1000

                    results['total_queries'] += 1
                    results['successful_queries'] += 1
                    results['query_times'].append(query_time)

                except Exception as e:
                    query_end = time.perf_counter()
                    results['total_queries'] += 1
                    results['failed_queries'] += 1
                    results['errors'].append(f"Query {i} failed: {str(e)}")

                # Small delay between queries
                await asyncio.sleep(0.01)

        # Run concurrent database sessions
        start_time = time.perf_counter()
        workers = [
            asyncio.create_task(db_session_worker())
            for _ in range(concurrent_connections)
        ]

        await asyncio.gather(*workers, return_exceptions=True)
        results['total_time'] = time.perf_counter() - start_time

        # Calculate statistics
        if results['query_times']:
            results['avg_query_time'] = sum(results['query_times']) / len(results['query_times'])
            results['min_query_time'] = min(results['query_times'])
            results['max_query_time'] = max(results['query_times'])
        else:
            results['avg_query_time'] = 0
            results['min_query_time'] = 0
            results['max_query_time'] = 0

        return results


@pytest.mark.performance
@pytest.mark.slow
class TestExternalLoadTesting:
    """Integration tests with external load testing tools."""

    @pytest.fixture
    def ab_runner(self):
        """Get Apache Bench runner."""
        return ApacheBenchRunner()

    @pytest.fixture
    def wrk_runner(self):
        """Get wrk runner."""
        return WrkRunner()

    @pytest.fixture
    def custom_runner(self):
        """Get custom load tester."""
        return CustomLoadTester()

    @pytest.mark.asyncio
    async def test_apache_bench_basic(self, ab_runner: ApacheBenchRunner):
        """Test Apache Bench basic functionality."""
        if not ab_runner.is_available():
            pytest.skip("Apache Bench (ab) is not available")

        result = await ab_runner.run_test(
            endpoint="/api/v1/invoices/",
            concurrent_users=10,
            total_requests=100
        )

        # Verify results
        assert result.tool_name == "Apache Bench"
        assert result.total_requests == 100
        assert result.success_rate >= 95, f"Success rate {result.success_rate:.1f}% below 95%"
        assert result.requests_per_second > 0, "No requests per second recorded"
        assert result.concurrent_users == 10

        logger.info(f"Apache Bench Test Results: {json.dumps(result.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_apache_bench_stress(self, ab_runner: ApacheBenchRunner):
        """Apache Bench stress test with higher load."""
        if not ab_runner.is_available():
            pytest.skip("Apache Bench (ab) is not available")

        result = await ab_runner.run_test(
            endpoint="/api/v1/invoices/",
            concurrent_users=50,
            total_requests=500
        )

        # Stress test assertions
        assert result.total_requests == 500
        assert result.success_rate >= 85, f"Stress test success rate {result.success_rate:.1f}% below 85%"
        assert result.requests_per_second > 10, "Requests per second too low under stress"

        logger.info(f"Apache Bench Stress Test Results: {json.dumps(result.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_wrk_basic(self, wrk_runner: WrkRunner):
        """Test wrk basic functionality."""
        if not wrk_runner.is_available():
            pytest.skip("wrk is not available")

        result = await wrk_runner.run_test(
            endpoint="/api/v1/invoices/",
            concurrent_users=10,
            duration_seconds=30
        )

        # Verify results
        assert result.tool_name == "wrk"
        assert result.total_requests > 0, "No requests completed"
        assert result.successful_requests > 0, "No successful requests"
        assert result.requests_per_second > 0, "No requests per second recorded"
        assert result.concurrent_users == 10

        logger.info(f"wrk Test Results: {json.dumps(result.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_wrk_sustained_load(self, wrk_runner: WrkRunner):
        """wrk sustained load test."""
        if not wrk_runner.is_available():
            pytest.skip("wrk is not available")

        result = await wrk_runner.run_test(
            endpoint="/api/v1/invoices/",
            concurrent_users=25,
            duration_seconds=60
        )

        # Sustained load assertions
        assert result.total_requests > 1000, "Too few requests in sustained test"
        assert result.successful_requests > result.total_requests * 0.95, "Success rate too low in sustained test"
        assert result.requests_per_second > 20, "Requests per second too low for sustained test"

        logger.info(f"wrk Sustained Load Test Results: {json.dumps(result.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_custom_load_test_mixed_workload(self, custom_runner: CustomLoadTester):
        """Test custom load tester with mixed workload."""
        scenarios = [
            {
                'name': 'Light reads',
                'endpoint': '/api/v1/invoices/',
                'method': 'GET',
                'concurrent_users': 15,
                'delay_between_requests': 0.2
            },
            {
                'name': 'Heavy reads',
                'endpoint': '/api/v1/invoices/?limit=50',
                'method': 'GET',
                'concurrent_users': 10,
                'delay_between_requests': 0.1
            },
            {
                'name': 'API health checks',
                'endpoint': '/health',
                'method': 'GET',
                'concurrent_users': 20,
                'delay_between_requests': 0.05
            }
        ]

        results = await custom_runner.run_custom_load_test(
            scenarios=scenarios,
            duration_seconds=30,
            ramp_up_seconds=5
        )

        # Verify all scenarios completed
        assert len(results) == len(scenarios), "Not all scenarios completed"

        for i, result in enumerate(results):
            assert result.total_requests > 0, f"Scenario {i} made no requests"
            assert result.success_rate >= 90, f"Scenario {i} success rate {result.success_rate:.1f}% too low"

        logger.info(f"Custom Load Test Results: {[r.to_dict() for r in results]}")

    @pytest.mark.asyncio
    async def test_database_load_performance(self, db_session: AsyncSession):
        """Test database performance under load."""
        db_tester = DatabaseLoadTester(db_session)

        results = await db_tester.test_database_load(
            concurrent_connections=10,
            queries_per_connection=50,
            query_types=['select', 'complex_select']
        )

        # Verify database load test results
        assert results['total_queries'] > 0, "No database queries executed"
        assert results['queries_per_second'] > 0, "No database throughput recorded"

        for query_type, type_results in results['query_types'].items():
            assert type_results['total_queries'] > 0, f"No {query_type} queries executed"
            assert type_results['successful_queries'] > 0, f"No successful {query_type} queries"
            assert type_results['avg_query_time'] < 1000, f"{query_type} queries too slow: {type_results['avg_query_time']:.2f}ms"

        logger.info(f"Database Load Test Results: {json.dumps(results, indent=2)}")

    @pytest.mark.asyncio
    async def test_comparative_load_testing(self, ab_runner: ApacheBenchRunner, wrk_runner: WrkRunner):
        """Compare results from different load testing tools."""
        test_params = {
            'endpoint': '/api/v1/invoices/',
            'concurrent_users': 20,
        }

        results = []

        # Run Apache Bench
        if ab_runner.is_available():
            ab_result = await ab_runner.run_test(
                concurrent_users=test_params['concurrent_users'],
                total_requests=200,
                **test_params
            )
            results.append(ab_result)

        # Run wrk
        if wrk_runner.is_available():
            wrk_result = await wrk_runner.run_test(
                concurrent_users=test_params['concurrent_users'],
                duration_seconds=30,
                **test_params
            )
            results.append(wrk_result)

        # Run custom tester
        custom_runner = CustomLoadTester()
        custom_scenarios = [{
            'name': 'Comparative test',
            'endpoint': test_params['endpoint'],
            'method': 'GET',
            'concurrent_users': test_params['concurrent_users'],
            'delay_between_requests': 0.05
        }]

        custom_results = await custom_runner.run_custom_load_test(
            scenarios=custom_scenarios,
            duration_seconds=30
        )

        if custom_results:
            results.append(custom_results[0])

        # Analyze and compare results
        assert len(results) >= 2, "Need at least 2 tools for comparison"

        logger.info("Comparative Load Testing Results:")
        for result in results:
            logger.info(f"{result.tool_name}: {result.requests_per_second:.2f} RPS, "
                       f"{result.success_rate:.1f}% success, "
                       f"{result.mean_response_time or 0:.1f}ms avg response")

        # Check that results are in reasonable range
        rpss = [r.requests_per_second for r in results]
        max_rps = max(rpss)
        min_rps = min(rpss)

        # Results shouldn't vary by more than 3x
        assert max_rps / min_rps < 3, f"Load testing tools disagree too much: {min_rps:.2f} - {max_rps:.2f} RPS"


# CLI interface
async def main():
    """CLI for running external load tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Run external load tests")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--tool", choices=["ab", "wrk", "custom", "all"], default="all", help="Load testing tool")
    parser.add_argument("--users", type=int, default=20, help="Concurrent users")
    parser.add_argument("--requests", type=int, default=500, help="Total requests (for ab)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (for wrk/custom)")
    parser.add_argument("--endpoint", default="/api/v1/invoices/", help="API endpoint")

    args = parser.parse_args()

    results = []

    if args.tool in ["ab", "all"]:
        ab_runner = ApacheBenchRunner(args.url)
        if ab_runner.is_available():
            print("Running Apache Bench test...")
            result = await ab_runner.run_test(
                endpoint=args.endpoint,
                concurrent_users=args.users,
                total_requests=args.requests
            )
            results.append(result)
            print(f"Apache Bench: {result.requests_per_second:.2f} RPS, {result.success_rate:.1f}% success")
        else:
            print("Apache Bench not available")

    if args.tool in ["wrk", "all"]:
        wrk_runner = WrkRunner(args.url)
        if wrk_runner.is_available():
            print("Running wrk test...")
            result = await wrk_runner.run_test(
                endpoint=args.endpoint,
                concurrent_users=args.users,
                duration_seconds=args.duration
            )
            results.append(result)
            print(f"wrk: {result.requests_per_second:.2f} RPS, {result.success_rate:.1f}% success")
        else:
            print("wrk not available")

    if args.tool in ["custom", "all"]:
        custom_runner = CustomLoadTester(args.url)
        print("Running custom load test...")
        scenarios = [{
            'name': 'CLI test',
            'endpoint': args.endpoint,
            'method': 'GET',
            'concurrent_users': args.users,
            'delay_between_requests': 0.1
        }]

        custom_results = await custom_runner.run_custom_load_test(
            scenarios=scenarios,
            duration_seconds=args.duration
        )

        for result in custom_results:
            results.append(result)
            print(f"Custom: {result.requests_per_second:.2f} RPS, {result.success_rate:.1f}% success")

    # Generate summary report
    print(f"\n=== Load Testing Summary ===")
    for result in results:
        print(f"{result.tool_name}:")
        print(f"  Requests: {result.total_requests}")
        print(f"  Success Rate: {result.success_rate:.1f}%")
        print(f"  RPS: {result.requests_per_second:.2f}")
        print(f"  Avg Response Time: {result.mean_response_time or 0:.1f}ms")
        print()


if __name__ == "__main__":
    asyncio.run(main())