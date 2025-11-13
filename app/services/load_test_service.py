"""
Load testing orchestration service for AP Intake & Validation system.
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.metrics import SystemMetric
from app.services.prometheus_service import prometheus_service

logger = logging.getLogger(__name__)


class LoadTestType(Enum):
    """Types of load tests."""
    SMOKE = "smoke"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    STRESS = "stress"
    SPIKE = "spike"
    VOLUME = "volume"
    ENDURANCE = "endurance"


class LoadTestStatus(Enum):
    """Load test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LoadTestConfig:
    """Configuration for a load test."""
    test_type: LoadTestType
    num_users: int
    hatch_rate: int
    run_time_seconds: int
    target_host: str
    test_scenarios: List[str] = field(default_factory=list)
    ramp_up_time: int = 60  # seconds
    ramp_down_time: int = 30  # seconds
    think_time_factor: float = 1.0  # multiplier for user think time
    timeout: int = 30  # seconds
    expect_failures: float = 0.01  # 1% expected failure rate
    max_response_time_p95: float = 500.0  # ms
    max_response_time_p99: float = 1000.0  # ms
    min_throughput: float = 10.0  # requests per second
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadTestResult:
    """Results from a load test execution."""
    test_id: str
    test_type: LoadTestType
    start_time: datetime
    end_time: Optional[datetime] = None
    status: LoadTestStatus = LoadTestStatus.PENDING

    # Test metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    failure_rate: float = 0.0

    # Performance metrics
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p50_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0

    # Throughput metrics
    requests_per_second: float = 0.0
    peak_rps: float = 0.0

    # User metrics
    concurrent_users: int = 0
    peak_users: int = 0

    # System metrics
    cpu_usage_avg: float = 0.0
    memory_usage_avg: float = 0.0
    disk_io_avg: float = 0.0

    # Additional data
    endpoint_stats: Dict[str, Any] = field(default_factory=dict)
    error_summary: List[Dict[str, Any]] = field(default_factory=list)
    custom_metrics: Dict[str, Any] = field(default_factory=dict)

    # Performance validation
    performance_passed: bool = False
    validation_errors: List[str] = field(default_factory=list)

    def calculate_duration(self) -> Optional[float]:
        """Calculate test duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def calculate_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests > 0:
            return (self.successful_requests / self.total_requests) * 100
        return 0.0


class LoadTestService:
    """Service for orchestrating load tests."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_tests: Dict[str, LoadTestResult] = {}
        self.test_configs: Dict[LoadTestType, LoadTestConfig] = self._initialize_test_configs()

    def _initialize_test_configs(self) -> Dict[LoadTestType, LoadTestConfig]:
        """Initialize predefined load test configurations."""
        base_host = settings.API_HOST or "http://localhost:8000"

        return {
            LoadTestType.SMOKE: LoadTestConfig(
                test_type=LoadTestType.SMOKE,
                num_users=5,
                hatch_rate=1,
                run_time_seconds=120,
                target_host=base_host,
                test_scenarios=["health_check", "basic_api"],
                expect_failures=0.0,
                max_response_time_p95=200.0,
                min_throughput=1.0
            ),

            LoadTestType.LIGHT: LoadTestConfig(
                test_type=LoadTestType.LIGHT,
                num_users=20,
                hatch_rate=2,
                run_time_seconds=300,
                target_host=base_host,
                test_scenarios=["api_endpoints", "invoice_upload"],
                expect_failures=0.01,
                max_response_time_p95=300.0,
                min_throughput=5.0
            ),

            LoadTestType.MEDIUM: LoadTestConfig(
                test_type=LoadTestType.MEDIUM,
                num_users=50,
                hatch_rate=5,
                run_time_seconds=600,
                target_host=base_host,
                test_scenarios=["full_workload"],
                expect_failures=0.02,
                max_response_time_p95=500.0,
                min_throughput=10.0
            ),

            LoadTestType.HEAVY: LoadTestConfig(
                test_type=LoadTestType.HEAVY,
                num_users=100,
                hatch_rate=10,
                run_time_seconds=900,
                target_host=base_host,
                test_scenarios=["full_workload", "stress_scenarios"],
                expect_failures=0.05,
                max_response_time_p95=1000.0,
                min_throughput=20.0
            ),

            LoadTestType.STRESS: LoadTestConfig(
                test_type=LoadTestType.STRESS,
                num_users=200,
                hatch_rate=20,
                run_time_seconds=600,
                target_host=base_host,
                test_scenarios=["stress_test"],
                expect_failures=0.10,
                max_response_time_p95=2000.0,
                min_throughput=30.0
            ),

            LoadTestType.SPIKE: LoadTestConfig(
                test_type=LoadTestType.SPIKE,
                num_users=150,
                hatch_rate=50,
                run_time_seconds=300,
                target_host=base_host,
                test_scenarios=["spike_test"],
                ramp_up_time=30,
                expect_failures=0.15,
                max_response_time_p95=1500.0,
                min_throughput=25.0
            ),

            LoadTestType.VOLUME: LoadTestConfig(
                test_type=LoadTestType.VOLUME,
                num_users=50,
                hatch_rate=5,
                run_time_seconds=3600,  # 1 hour
                target_host=base_host,
                test_scenarios=["volume_test"],
                expect_failures=0.02,
                max_response_time_p95=800.0,
                min_throughput=15.0
            ),

            LoadTestType.ENDURANCE: LoadTestConfig(
                test_type=LoadTestType.ENDURANCE,
                num_users=25,
                hatch_rate=2,
                run_time_seconds=14400,  # 4 hours
                target_host=base_host,
                test_scenarios=["endurance_test"],
                expect_failures=0.01,
                max_response_time_p95=600.0,
                min_throughput=8.0
            ),
        }

    async def run_load_test(self, test_type: LoadTestType, custom_config: Optional[LoadTestConfig] = None) -> str:
        """
        Run a load test with the specified type or custom configuration.

        Args:
            test_type: Type of load test to run
            custom_config: Optional custom configuration to override defaults

        Returns:
            Test ID for tracking the test execution
        """
        config = custom_config or self.test_configs[test_type]
        test_id = f"{test_type.value}_{int(time.time())}_{config.num_users}users"

        self.logger.info(f"Starting load test {test_id}: {config.num_users} users for {config.run_time_seconds}s")

        # Initialize test result
        test_result = LoadTestResult(
            test_id=test_id,
            test_type=test_type,
            start_time=datetime.utcnow(),
            status=LoadTestStatus.RUNNING,
            concurrent_users=config.num_users
        )

        self.active_tests[test_id] = test_result

        try:
            # Start system metrics collection
            metrics_task = asyncio.create_task(self._collect_system_metrics(test_id, config.run_time_seconds))

            # Execute the load test
            await self._execute_locust_test(test_id, config, test_result)

            # Wait for metrics collection to complete
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass

            # Calculate final metrics
            await self._calculate_final_metrics(test_id, config, test_result)

            # Validate performance against expectations
            self._validate_performance(config, test_result)

            test_result.status = LoadTestStatus.COMPLETED
            test_result.end_time = datetime.utcnow()

            self.logger.info(f"Load test {test_id} completed successfully")

        except Exception as e:
            self.logger.error(f"Load test {test_id} failed: {e}")
            test_result.status = LoadTestStatus.FAILED
            test_result.end_time = datetime.utcnow()
            test_result.validation_errors.append(str(e))

        # Record results in database
        await self._store_test_results(test_result)

        return test_id

    async def _execute_locust_test(self, test_id: str, config: LoadTestConfig, test_result: LoadTestResult):
        """Execute Locust load test."""
        try:
            # Prepare Locust command
            cmd = [
                "locust",
                "-f", "tests/load_test/locustfile.py",
                "--host", config.target_host,
                "--users", str(config.num_users),
                "--hatch-rate", str(config.hatch_rate),
                "--run-time", f"{config.run_time_seconds}s",
                "--headless",
                "--html", f"reports/load_test_{test_id}.html",
                "--csv", f"reports/load_test_{test_id}",
                "--loglevel", "INFO"
            ]

            # Add custom parameters
            if config.custom_params:
                for key, value in config.custom_params.items():
                    cmd.extend(["--extra-tag", f"{key}={value}"])

            self.logger.info(f"Executing Locust command: {' '.join(cmd)}")

            # Create reports directory
            Path("reports").mkdir(exist_ok=True)

            # Execute Locust
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.cwd())
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"Locust execution failed: {error_msg}")

            # Parse CSV results
            await self._parse_locust_results(test_id, config, test_result)

            self.logger.info(f"Locust test {test_id} completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to execute Locust test {test_id}: {e}")
            raise

    async def _parse_locust_results(self, test_id: str, config: LoadTestConfig, test_result: LoadTestResult):
        """Parse Locust CSV results."""
        try:
            import csv

            # Parse requests statistics
            requests_file = Path(f"reports/load_test_{test_id}_requests.csv")
            if requests_file.exists():
                with open(requests_file, 'r') as f:
                    reader = csv.DictReader(f)
                    requests_data = list(reader)

                    if requests_data:
                        # Calculate aggregate metrics
                        total_requests = len(requests_data)
                        successful_requests = sum(1 for r in requests_data if r['Request Type'] != 'None')
                        failed_requests = total_requests - successful_requests

                        response_times = [float(r['Median Response Time']) for r in requests_data if r['Median Response Time']]
                        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

                        test_result.total_requests = total_requests
                        test_result.successful_requests = successful_requests
                        test_result.failed_requests = failed_requests
                        test_result.failure_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
                        test_result.avg_response_time = avg_response_time

                        # Calculate throughput
                        duration = test_result.calculate_duration()
                        if duration:
                            test_result.requests_per_second = total_requests / duration

                        # Parse endpoint-specific stats
                        endpoint_stats = {}
                        for row in requests_data:
                            endpoint = row['Name']
                            if endpoint not in endpoint_stats:
                                endpoint_stats[endpoint] = {
                                    'request_count': 0,
                                    'failure_count': 0,
                                    'avg_response_time': 0,
                                    'max_response_time': 0
                                }

                            endpoint_stats[endpoint]['request_count'] += int(row['Request Count'])
                            endpoint_stats[endpoint]['failure_count'] += int(row.get('Failure Count', 0))
                            endpoint_stats[endpoint]['avg_response_time'] = float(row['Median Response Time'])
                            endpoint_stats[endpoint]['max_response_time'] = float(row['Max Response Time'])

                        test_result.endpoint_stats = endpoint_stats

            # Parse exceptions if available
            exceptions_file = Path(f"reports/load_test_{test_id}_exceptions.csv")
            if exceptions_file.exists():
                with open(exceptions_file, 'r') as f:
                    reader = csv.DictReader(f)
                    exceptions_data = list(reader)

                    error_summary = []
                    for row in exceptions_data:
                        error_summary.append({
                            'exception': row['Exception'],
                            'count': int(row['Count']),
                            'percentage': float(row['Percentage'])
                        })

                    test_result.error_summary = error_summary

        except Exception as e:
            self.logger.warning(f"Failed to parse Locust results for {test_id}: {e}")

    async def _collect_system_metrics(self, test_id: str, duration_seconds: int):
        """Collect system metrics during load test."""
        try:
            import psutil

            start_time = time.time()
            cpu_readings = []
            memory_readings = []

            while time.time() - start_time < duration_seconds:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    cpu_readings.append(cpu_percent)

                    # Memory usage
                    memory = psutil.virtual_memory()
                    memory_readings.append(memory.percent)

                    # Record metrics in Prometheus
                    prometheus_service.set_cpu_usage("load_test", cpu_percent)
                    prometheus_service.set_memory_usage("load_test", memory.used)

                    await asyncio.sleep(5)  # Collect every 5 seconds

                except Exception as e:
                    self.logger.warning(f"Error collecting system metrics: {e}")
                    await asyncio.sleep(5)

            # Calculate averages
            if cpu_readings:
                self.active_tests[test_id].cpu_usage_avg = sum(cpu_readings) / len(cpu_readings)
            if memory_readings:
                self.active_tests[test_id].memory_usage_avg = sum(memory_readings) / len(memory_readings)

        except ImportError:
            self.logger.warning("psutil not available, system metrics not collected")
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")

    async def _calculate_final_metrics(self, test_id: str, config: LoadTestConfig, test_result: LoadTestResult):
        """Calculate final performance metrics."""
        try:
            # Get Prometheus metrics for the test period
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(seconds=config.run_time_seconds)

            # This would integrate with Prometheus to get detailed metrics
            # For now, we'll use the metrics already collected in test_result

            # Calculate percentiles (placeholder - would be calculated from actual data)
            if test_result.avg_response_time > 0:
                test_result.p50_response_time = test_result.avg_response_time * 0.8
                test_result.p95_response_time = test_result.avg_response_time * 1.5
                test_result.p99_response_time = test_result.avg_response_time * 2.0

            # Peak RPS estimation
            test_result.peak_rps = test_result.requests_per_second * 1.2

            self.logger.debug(f"Calculated final metrics for {test_id}")

        except Exception as e:
            self.logger.warning(f"Failed to calculate final metrics for {test_id}: {e}")

    def _validate_performance(self, config: LoadTestConfig, test_result: LoadTestResult):
        """Validate test results against performance expectations."""
        validation_errors = []

        # Check failure rate
        actual_failure_rate = test_result.failure_rate / 100
        if actual_failure_rate > config.expect_failures:
            validation_errors.append(
                f"Failure rate too high: {actual_failure_rate:.2%} > {config.expect_failures:.2%}"
            )

        # Check response times
        if test_result.p95_response_time > config.max_response_time_p95:
            validation_errors.append(
                f"P95 response time too high: {test_result.p95_response_time:.2f}ms > {config.max_response_time_p95:.2f}ms"
            )

        # Check throughput
        if test_result.requests_per_second < config.min_throughput:
            validation_errors.append(
                f"Throughput too low: {test_result.requests_per_second:.2f} RPS < {config.min_throughput:.2f} RPS"
            )

        test_result.validation_errors = validation_errors
        test_result.performance_passed = len(validation_errors) == 0

        if validation_errors:
            self.logger.warning(f"Performance validation failed for {test_result.test_id}: {validation_errors}")
        else:
            self.logger.info(f"Performance validation passed for {test_result.test_id}")

    async def _store_test_results(self, test_result: LoadTestResult):
        """Store test results in database."""
        try:
            async with AsyncSessionLocal() as session:
                # Store as system metric for historical tracking
                metric = SystemMetric(
                    metric_name="load_test_result",
                    metric_category="performance",
                    measurement_timestamp=test_result.start_time,
                    value=Decimal(str(test_result.requests_per_second)),
                    unit="requests_per_second",
                    dimensions={
                        "test_id": test_result.test_id,
                        "test_type": test_result.test_type.value,
                        "status": test_result.status.value
                    },
                    metadata={
                        "total_requests": test_result.total_requests,
                        "failure_rate": test_result.failure_rate,
                        "avg_response_time": test_result.avg_response_time,
                        "performance_passed": test_result.performance_passed,
                        "validation_errors": test_result.validation_errors
                    },
                    data_source="load_test_service"
                )

                session.add(metric)
                await session.commit()

                self.logger.debug(f"Stored load test results for {test_result.test_id}")

        except Exception as e:
            self.logger.error(f"Failed to store load test results: {e}")

    async def get_test_results(self, test_id: str) -> Optional[LoadTestResult]:
        """Get results for a specific load test."""
        return self.active_tests.get(test_id)

    async def get_active_tests(self) -> List[LoadTestResult]:
        """Get list of currently active load tests."""
        return [
            result for result in self.active_tests.values()
            if result.status in [LoadTestStatus.PENDING, LoadTestStatus.RUNNING]
        ]

    async def get_test_history(self, limit: int = 50) -> List[LoadTestResult]:
        """Get historical load test results."""
        # This would query from database in a real implementation
        return list(self.active_tests.values())[-limit:]

    async def cancel_test(self, test_id: str) -> bool:
        """Cancel a running load test."""
        if test_id in self.active_tests:
            test_result = self.active_tests[test_id]
            if test_result.status == LoadTestStatus.RUNNING:
                test_result.status = LoadTestStatus.CANCELLED
                test_result.end_time = datetime.utcnow()
                self.logger.info(f"Load test {test_id} cancelled")
                return True
        return False

    async def generate_performance_report(self, test_id: str) -> Dict[str, Any]:
        """Generate comprehensive performance report for a load test."""
        test_result = await self.get_test_results(test_id)
        if not test_result:
            raise ValueError(f"Test {test_id} not found")

        report = {
            "test_summary": {
                "test_id": test_result.test_id,
                "test_type": test_result.test_type.value,
                "start_time": test_result.start_time.isoformat(),
                "end_time": test_result.end_time.isoformat() if test_result.end_time else None,
                "duration_seconds": test_result.calculate_duration(),
                "status": test_result.status.value,
                "performance_passed": test_result.performance_passed
            },
            "test_metrics": {
                "total_requests": test_result.total_requests,
                "successful_requests": test_result.successful_requests,
                "failed_requests": test_result.failed_requests,
                "failure_rate": test_result.failure_rate,
                "success_rate": test_result.calculate_success_rate()
            },
            "performance_metrics": {
                "avg_response_time": test_result.avg_response_time,
                "min_response_time": test_result.min_response_time,
                "max_response_time": test_result.max_response_time,
                "p50_response_time": test_result.p50_response_time,
                "p95_response_time": test_result.p95_response_time,
                "p99_response_time": test_result.p99_response_time
            },
            "throughput_metrics": {
                "requests_per_second": test_result.requests_per_second,
                "peak_rps": test_result.peak_rps
            },
            "system_metrics": {
                "cpu_usage_avg": test_result.cpu_usage_avg,
                "memory_usage_avg": test_result.memory_usage_avg,
                "concurrent_users": test_result.concurrent_users
            },
            "endpoint_performance": test_result.endpoint_stats,
            "error_summary": test_result.error_summary,
            "validation_errors": test_result.validation_errors,
            "recommendations": self._generate_recommendations(test_result)
        }

        return report

    def _generate_recommendations(self, test_result: LoadTestResult) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        if test_result.failure_rate > 5:
            recommendations.append("High error rate detected. Check application logs and error handling.")

        if test_result.p95_response_time > 1000:
            recommendations.append("P95 response time is high. Consider optimizing slow endpoints and implementing caching.")

        if test_result.cpu_usage_avg > 80:
            recommendations.append("High CPU usage detected. Consider optimizing algorithms or scaling horizontally.")

        if test_result.memory_usage_avg > 80:
            recommendations.append("High memory usage detected. Check for memory leaks and optimize memory usage.")

        if test_result.requests_per_second < 10 and test_result.test_type in [LoadTestType.MEDIUM, LoadTestType.HEAVY]:
            recommendations.append("Low throughput under load. Check database performance and connection pooling.")

        if test_result.performance_passed:
            recommendations.append("Performance targets met. System is performing well under current load conditions.")

        return recommendations


# Singleton instance
load_test_service = LoadTestService()