"""
Reliability Testing Utilities for AP Intake & Validation System.

This module provides utilities for:
- Fault injection and simulation
- Performance monitoring under stress
- Network failure simulation
- Database failure simulation
- Memory pressure testing
- Rate limiting simulation
- Circuit breaker testing
- Metrics collection and analysis

Author: Integration and Reliability Testing Specialist
"""

import asyncio
import random
import time
import logging
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
import statistics
import random

import aiohttp
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures to simulate."""
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_CONNECTION_REFUSED = "network_connection_refused"
    NETWORK_DNS_FAILURE = "network_dns_failure"
    DATABASE_CONNECTION_LOST = "database_connection_lost"
    DATABASE_TIMEOUT = "database_timeout"
    DATABASE_CONSTRAINT_VIOLATION = "database_constraint_violation"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_OVERLOAD = "cpu_overload"
    DISK_FULL = "disk_full"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PERMISSION_DENIED = "permission_denied"
    DATA_CORRUPTION = "data_corruption"
    PARTIAL_FAILURE = "partial_failure"


class Severity(Enum):
    """Failure severity levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class FailureScenario:
    """Definition of a failure scenario."""
    failure_type: FailureType
    severity: Severity
    probability: float  # 0.0 to 1.0
    duration_seconds: Optional[float] = None
    affected_components: List[str] = None
    custom_behavior: Optional[Callable] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.affected_components is None:
            self.affected_components = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TestMetrics:
    """Metrics collected during reliability testing."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_duration_ms: float = 0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0
    response_times: List[float] = None
    error_types: Dict[str, int] = None
    circuit_breaker_activations: int = 0
    retry_attempts: int = 0
    throughput_per_second: float = 0

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.error_types is None:
            self.error_types = {}

    def add_response_time(self, duration_ms: float):
        """Add a response time measurement."""
        self.response_times.append(duration_ms)
        self.min_response_time_ms = min(self.min_response_time_ms, duration_ms)
        self.max_response_time_ms = max(self.max_response_time_ms, duration_ms)

    def calculate_stats(self) -> Dict[str, Any]:
        """Calculate statistical metrics."""
        if not self.response_times:
            return {}

        return {
            "avg_response_time_ms": statistics.mean(self.response_times),
            "median_response_time_ms": statistics.median(self.response_times),
            "p95_response_time_ms": self._percentile(self.response_times, 95),
            "p99_response_time_ms": self._percentile(self.response_times, 99),
            "std_deviation_ms": statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0
        }

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


class FaultInjector:
    """Advanced fault injection utility for reliability testing."""

    def __init__(self):
        """Initialize fault injector."""
        self.active_scenarios: Dict[str, FailureScenario] = {}
        self.injection_history: List[Dict[str, Any]] = []
        self.metrics = TestMetrics()

    def add_scenario(self, scenario_id: str, scenario: Union[FailureScenario, Dict[str, Any]]):
        """Add a failure scenario."""
        # Convert dict to FailureScenario if needed
        if isinstance(scenario, dict):
            failure_type = FailureType(scenario.get("type", "network_timeout"))
            severity = Severity(scenario.get("severity", 1))
            scenario_obj = FailureScenario(
                failure_type=failure_type,
                severity=severity,
                probability=scenario.get("probability", 0.1),
                duration_seconds=scenario.get("duration_seconds"),
                affected_components=scenario.get("affected_components", []),
                metadata=scenario.get("metadata", {})
            )
        else:
            scenario_obj = scenario

        self.active_scenarios[scenario_id] = scenario_obj
        logger.info(f"Added failure scenario: {scenario_id} - {scenario_obj.failure_type.value}")

    def remove_scenario(self, scenario_id: str):
        """Remove a failure scenario."""
        if scenario_id in self.active_scenarios:
            del self.active_scenarios[scenario_id]
            logger.info(f"Removed failure scenario: {scenario_id}")

    def clear_scenarios(self):
        """Clear all failure scenarios."""
        self.active_scenarios.clear()
        logger.info("Cleared all failure scenarios")

    async def should_inject_failure(self, component: str = None) -> Optional[FailureScenario]:
        """Check if a failure should be injected."""
        for scenario_id, scenario in self.active_scenarios.items():
            # Check if component is affected
            if component and scenario.affected_components and component not in scenario.affected_components:
                continue

            # Check probability
            if random.random() < scenario.probability:
                self._record_injection(scenario_id, scenario)
                return scenario

        return None

    def _record_injection(self, scenario_id: str, scenario: FailureScenario):
        """Record a fault injection event."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_id": scenario_id,
            "failure_type": scenario.failure_type.value,
            "severity": scenario.severity.value,
            "probability": scenario.probability
        }
        self.injection_history.append(record)
        logger.warning(f"Injected failure: {scenario.failure_type.value} (severity: {scenario.severity.name})")

    @asynccontextmanager
    async def failure_context(self, component: str = None):
        """Context manager for automatic failure injection."""
        scenario = await self.should_inject_failure(component)
        if scenario:
            async with self._simulate_failure(scenario):
                yield
        else:
            yield

    async def simulate_failure(self, failure_type: FailureType, **kwargs):
        """Simulate a specific failure type."""
        scenario = FailureScenario(
            failure_type=failure_type,
            severity=Severity.HIGH,
            probability=1.0,  # Always inject
            **kwargs
        )
        async with self._simulate_failure(scenario):
            pass

    @asynccontextmanager
    async def _simulate_failure(self, scenario: FailureScenario):
        """Simulate the actual failure based on scenario."""
        failure_type = scenario.failure_type

        if failure_type == FailureType.NETWORK_TIMEOUT:
            await self._simulate_network_timeout(scenario)
        elif failure_type == FailureType.NETWORK_CONNECTION_REFUSED:
            await self._simulate_connection_refused(scenario)
        elif failure_type == FailureType.DATABASE_CONNECTION_LOST:
            await self._simulate_database_connection_lost(scenario)
        elif failure_type == FailureType.MEMORY_PRESSURE:
            await self._simulate_memory_pressure(scenario)
        elif failure_type == FailureType.RATE_LIMIT_EXCEEDED:
            await self._simulate_rate_limit_exceeded(scenario)
        elif failure_type == FailureType.SERVICE_UNAVAILABLE:
            await self._simulate_service_unavailable(scenario)
        elif failure_type == FailureType.DATA_CORRUPTION:
            await self._simulate_data_corruption(scenario)
        elif scenario.custom_behavior:
            await scenario.custom_behavior(scenario)
        else:
            await self._simulate_generic_failure(scenario)

        yield

    async def _simulate_network_timeout(self, scenario: FailureScenario):
        """Simulate network timeout."""
        delay = scenario.metadata.get("timeout_seconds", 30.0)
        await asyncio.sleep(delay)
        raise aiohttp.ServerTimeoutError(f"Network timeout after {delay}s")

    async def _simulate_connection_refused(self, scenario: FailureScenario):
        """Simulate connection refused."""
        raise aiohttp.ClientConnectorError("Connection refused")

    async def _simulate_database_connection_lost(self, scenario: FailureScenario):
        """Simulate database connection lost."""
        raise Exception("Database connection lost")

    async def _simulate_memory_pressure(self, scenario: FailureScenario):
        """Simulate memory pressure."""
        # Allocate memory to simulate pressure
        memory_size = scenario.metadata.get("memory_mb", 100)
        try:
            data = b"x" * (memory_size * 1024 * 1024)
            # Hold memory for specified duration
            if scenario.duration_seconds:
                await asyncio.sleep(scenario.duration_seconds)
            del data
        except MemoryError:
            raise Exception("Out of memory")

    async def _simulate_rate_limit_exceeded(self, scenario: FailureScenario):
        """Simulate rate limit exceeded."""
        raise aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=429,
            message="Rate limit exceeded"
        )

    async def _simulate_service_unavailable(self, scenario: FailureScenario):
        """Simulate service unavailable."""
        raise aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=503,
            message="Service unavailable"
        )

    async def _simulate_data_corruption(self, scenario: FailureScenario):
        """Simulate data corruption."""
        corrupt_probability = scenario.metadata.get("corruption_probability", 0.1)
        if random.random() < corrupt_probability:
            raise ValueError("Data corruption detected")

    async def _simulate_generic_failure(self, scenario: FailureScenario):
        """Simulate generic failure."""
        error_message = scenario.metadata.get("error_message", "Simulated failure")
        raise Exception(error_message)

    def get_injection_summary(self) -> Dict[str, Any]:
        """Get summary of fault injections."""
        failure_counts = {}
        for record in self.injection_history:
            failure_type = record["failure_type"]
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1

        return {
            "total_injections": len(self.injection_history),
            "active_scenarios": len(self.active_scenarios),
            "failure_types": failure_counts,
            "injection_history": self.injection_history[-10:]  # Last 10 injections
        }


class PerformanceMonitor:
    """Monitor performance during reliability testing."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics = TestMetrics()
        self.start_time = None
        self.end_time = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        logger.info("Started performance monitoring")

    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.end_time = time.time()
        if self.start_time:
            total_duration = (self.end_time - self.start_time) * 1000
            self.metrics.total_duration_ms = total_duration

            # Calculate throughput
            if total_duration > 0:
                self.metrics.throughput_per_second = (
                    self.metrics.total_operations / (total_duration / 1000)
                )

        logger.info(f"Stopped performance monitoring. Duration: {total_duration:.2f}ms")

    def record_operation(self, success: bool, duration_ms: float, error_type: str = None):
        """Record an operation."""
        self.metrics.total_operations += 1
        self.metrics.add_response_time(duration_ms)

        if success:
            self.metrics.successful_operations += 1
        else:
            self.metrics.failed_operations += 1
            if error_type:
                self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1

    def record_retry(self):
        """Record a retry attempt."""
        self.metrics.retry_attempts += 1

    def record_circuit_breaker_activation(self):
        """Record circuit breaker activation."""
        self.metrics.circuit_breaker_activations += 1

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        stats = self.metrics.calculate_stats()

        report = {
            "summary": {
                "total_operations": self.metrics.total_operations,
                "successful_operations": self.metrics.successful_operations,
                "failed_operations": self.metrics.failed_operations,
                "success_rate": (
                    self.metrics.successful_operations / self.metrics.total_operations * 100
                    if self.metrics.total_operations > 0 else 0
                ),
                "total_duration_ms": self.metrics.total_duration_ms,
                "throughput_per_second": self.metrics.throughput_per_second
            },
            "response_times": stats,
            "errors": {
                "total_errors": len(self.metrics.error_types),
                "error_types": self.metrics.error_types,
                "retry_attempts": self.metrics.retry_attempts,
                "circuit_breaker_activations": self.metrics.circuit_breaker_activations
            }
        }

        return report


class CircuitBreakerTester:
    """Test circuit breaker implementations."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """Initialize circuit breaker tester."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.call_count = 0
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_opens": 0,
            "circuit_closes": 0
        }

    async def call(self, operation: Callable, should_fail: bool = False) -> Any:
        """Execute operation with circuit breaker protection."""
        self.metrics["total_calls"] += 1
        self.call_count += 1

        # Check circuit state
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            # Execute operation
            if should_fail:
                raise Exception("Simulated failure")

            result = await operation()

            # Success - reset failure count if circuit was closing
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                self.metrics["circuit_closes"] += 1
                logger.info("Circuit breaker closed after successful call")

            self.metrics["successful_calls"] += 1
            return result

        except Exception as e:
            self.failure_count += 1
            self.metrics["failed_calls"] += 1
            self.last_failure_time = time.time()

            # Check if circuit should open
            if self.failure_count >= self.failure_threshold:
                if self.state != "OPEN":
                    self.state = "OPEN"
                    self.metrics["circuit_opens"] += 1
                    logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if not self.last_failure_time:
            return False
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "state": self.state,
            "call_count": self.call_count,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "metrics": self.metrics
        }


class LoadGenerator:
    """Generate load for reliability testing."""

    def __init__(self):
        """Initialize load generator."""
        self.active_generators = []
        self.metrics = PerformanceMonitor()

    async def generate_constant_load(
        self,
        operation: Callable,
        requests_per_second: float,
        duration_seconds: float,
        concurrent_workers: int = 10
    ) -> Dict[str, Any]:
        """Generate constant load."""
        self.metrics.start_monitoring()

        interval = 1.0 / requests_per_second
        end_time = time.time() + duration_seconds

        async def worker():
            while time.time() < end_time:
                start_time = time.time()
                try:
                    await operation()
                    duration = (time.time() - start_time) * 1000
                    self.metrics.record_operation(True, duration)
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    self.metrics.record_operation(False, duration, type(e).__name__)

                await asyncio.sleep(interval)

        # Start workers
        tasks = [worker() for _ in range(concurrent_workers)]
        try:
            await asyncio.gather(*tasks)
        finally:
            self.metrics.stop_monitoring()

        return self.metrics.get_performance_report()

    async def generate_burst_load(
        self,
        operation: Callable,
        burst_size: int,
        burst_interval: float,
        num_bursts: int
    ) -> Dict[str, Any]:
        """Generate burst load pattern."""
        self.metrics.start_monitoring()

        for burst in range(num_bursts):
            # Generate burst
            tasks = []
            for _ in range(burst_size):
                task = asyncio.create_task(self._execute_and_record(operation))
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Wait between bursts
            if burst < num_bursts - 1:
                await asyncio.sleep(burst_interval)

        self.metrics.stop_monitoring()
        return self.metrics.get_performance_report()

    async def _execute_and_record(self, operation: Callable):
        """Execute operation and record metrics."""
        start_time = time.time()
        try:
            await operation()
            duration = (time.time() - start_time) * 1000
            self.metrics.record_operation(True, duration)
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.metrics.record_operation(False, duration, type(e).__name__)

    async def generate_ramp_up_load(
        self,
        operation: Callable,
        initial_rps: float,
        target_rps: float,
        ramp_up_seconds: float,
        step_interval: float = 1.0
    ) -> Dict[str, Any]:
        """Generate ramp-up load pattern."""
        self.metrics.start_monitoring()

        rps_increment = (target_rps - initial_rps) / (ramp_up_seconds / step_interval)
        current_rps = initial_rps
        end_time = time.time() + ramp_up_seconds

        async def worker():
            while time.time() < end_time:
                interval = 1.0 / current_rps
                start_time = time.time()
                try:
                    await operation()
                    duration = (time.time() - start_time) * 1000
                    self.metrics.record_operation(True, duration)
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    self.metrics.record_operation(False, duration, type(e).__name__)

                await asyncio.sleep(interval)

        # Update RPS periodically
        async def rps_updater():
            while time.time() < end_time:
                await asyncio.sleep(step_interval)
                current_rps = min(current_rps + rps_increment, target_rps)

        # Run worker and updater
        await asyncio.gather(worker(), rps_updater())
        self.metrics.stop_monitoring()

        return self.metrics.get_performance_report()


class NetworkSimulator:
    """Simulate various network conditions."""

    def __init__(self):
        """Initialize network simulator."""
        self.conditions = {}

    def set_condition(self, name: str, condition: Dict[str, Any]):
        """Set network condition."""
        self.conditions[name] = condition
        logger.info(f"Set network condition: {name}")

    async def apply_condition(self, name: str, operation: Callable):
        """Apply network condition to operation."""
        if name not in self.conditions:
            return await operation()

        condition = self.conditions[name]
        condition_type = condition.get("type")

        if condition_type == "latency":
            await self._apply_latency(condition)
            return await operation()
        elif condition_type == "packet_loss":
            return await self._apply_packet_loss(condition, operation)
        elif condition_type == "bandwidth_limit":
            return await self._apply_bandwidth_limit(condition, operation)
        elif condition_type == "jitter":
            await self._apply_jitter(condition)
            return await operation()
        else:
            return await operation()

    async def _apply_latency(self, condition: Dict[str, Any]):
        """Apply network latency."""
        latency_ms = condition.get("latency_ms", 100)
        jitter_ms = condition.get("jitter_ms", 20)

        actual_latency = latency_ms + random.uniform(-jitter_ms, jitter_ms)
        await asyncio.sleep(max(0, actual_latency / 1000))

    async def _apply_packet_loss(self, condition: Dict[str, Any], operation: Callable):
        """Apply packet loss simulation."""
        loss_rate = condition.get("loss_rate", 0.1)

        if random.random() < loss_rate:
            raise aiohttp.ClientError("Packet loss simulated")

        return await operation()

    async def _apply_bandwidth_limit(self, condition: Dict[str, Any], operation: Callable):
        """Apply bandwidth limit simulation."""
        bandwidth_mbps = condition.get("bandwidth_mbps", 1.0)
        max_data_mb = condition.get("max_data_mb", 10.0)

        # Calculate transfer time based on bandwidth
        transfer_time = (max_data_mb * 8) / bandwidth_mbps  # seconds
        await asyncio.sleep(transfer_time)

        return await operation()

    async def _apply_jitter(self, condition: Dict[str, Any]):
        """Apply network jitter."""
        jitter_ms = condition.get("jitter_ms", 50)
        delay = random.uniform(0, jitter_ms / 1000)
        await asyncio.sleep(delay)


class DatabaseSimulator:
    """Simulate database conditions and failures."""

    def __init__(self):
        """Initialize database simulator."""
        self.conditions = {}

    def set_condition(self, name: str, condition: Dict[str, Any]):
        """Set database condition."""
        self.conditions[name] = condition
        logger.info(f"Set database condition: {name}")

    async def execute_with_condition(self, name: str, operation: Callable):
        """Execute operation with database condition."""
        if name not in self.conditions:
            return await operation()

        condition = self.conditions[name]
        condition_type = condition.get("type")

        if condition_type == "slow_query":
            await self._apply_slow_query(condition)
        elif condition_type == "connection_drop":
            await self._apply_connection_drop(condition)
        elif condition_type == "deadlock":
            await self._apply_deadlock(condition)
        elif condition_type == "constraint_violation":
            await self._apply_constraint_violation(condition)

        return await operation()

    async def _apply_slow_query(self, condition: Dict[str, Any]):
        """Apply slow query simulation."""
        delay_seconds = condition.get("delay_seconds", 5.0)
        await asyncio.sleep(delay_seconds)

    async def _apply_connection_drop(self, condition: Dict[str, Any]):
        """Apply connection drop simulation."""
        raise Exception("Database connection dropped")

    async def _apply_deadlock(self, condition: Dict[str, Any]):
        """Apply deadlock simulation."""
        raise Exception("Deadlock detected")

    async def _apply_constraint_violation(self, condition: Dict[str, Any]):
        """Apply constraint violation simulation."""
        raise Exception("Constraint violation")


# Utility functions for creating common test scenarios

def create_network_failure_scenario(probability: float = 0.1) -> FailureScenario:
    """Create a network failure scenario."""
    return FailureScenario(
        failure_type=FailureType.NETWORK_TIMEOUT,
        severity=Severity.HIGH,
        probability=probability,
        duration_seconds=30.0,
        affected_components=["http_client", "api_client"],
        metadata={"timeout_seconds": 30.0}
    )


def create_database_failure_scenario(probability: float = 0.05) -> FailureScenario:
    """Create a database failure scenario."""
    return FailureScenario(
        failure_type=FailureType.DATABASE_CONNECTION_LOST,
        severity=Severity.CRITICAL,
        probability=probability,
        duration_seconds=10.0,
        affected_components=["database", "orm"],
        metadata={"recovery_time_seconds": 10.0}
    )


def create_rate_limit_scenario(probability: float = 0.2) -> FailureScenario:
    """Create a rate limit scenario."""
    return FailureScenario(
        failure_type=FailureType.RATE_LIMIT_EXCEEDED,
        severity=Severity.MEDIUM,
        probability=probability,
        affected_components=["api_client", "external_services"],
        metadata={"retry_after_seconds": 60, "limit_per_minute": 100}
    )


def create_memory_pressure_scenario(probability: float = 0.1) -> FailureScenario:
    """Create a memory pressure scenario."""
    return FailureScenario(
        failure_type=FailureType.MEMORY_PRESSURE,
        severity=Severity.HIGH,
        probability=probability,
        duration_seconds=15.0,
        affected_components=["processing", "file_handling"],
        metadata={"memory_mb": 200}
    )


# Context managers for easy testing

@asynccontextmanager
async def reliability_test_context(
    fault_injector: FaultInjector = None,
    performance_monitor: PerformanceMonitor = None
):
    """Context manager for reliability testing."""
    if fault_injector is None:
        fault_injector = FaultInjector()
    if performance_monitor is None:
        performance_monitor = PerformanceMonitor()

    performance_monitor.start_monitoring()

    try:
        yield fault_injector, performance_monitor
    finally:
        performance_monitor.stop_monitoring()


@asynccontextmanager
async def load_test_context(load_generator: LoadGenerator = None):
    """Context manager for load testing."""
    if load_generator is None:
        load_generator = LoadGenerator()

    yield load_generator


# Example usage functions

async def example_reliability_test():
    """Example of how to use the reliability testing utilities."""
    # Create fault injector
    fault_injector = FaultInjector()

    # Add failure scenarios
    fault_injector.add_scenario("network_timeout", create_network_failure_scenario(0.1))
    fault_injector.add_scenario("database_failure", create_database_failure_scenario(0.05))

    # Create performance monitor
    performance_monitor = PerformanceMonitor()

    async with reliability_test_context(fault_injector, performance_monitor):
        # Simulate operations with failures
        for i in range(100):
            async with fault_injector.failure_context("api_client"):
                start_time = time.time()
                try:
                    # Simulate API call
                    await asyncio.sleep(0.1)
                    duration = (time.time() - start_time) * 1000
                    performance_monitor.record_operation(True, duration)
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    performance_monitor.record_operation(False, duration, type(e).__name__)

    # Get results
    report = performance_monitor.get_performance_report()
    injection_summary = fault_injector.get_injection_summary()

    return {
        "performance_report": report,
        "fault_injection_summary": injection_summary
    }


if __name__ == "__main__":
    # Run example test
    async def main():
        print("Running reliability testing example...")
        result = await example_reliability_test()
        print("Test completed. Results:")
        print(json.dumps(result, indent=2))

    asyncio.run(main())