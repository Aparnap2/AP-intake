"""
Advanced performance monitoring middleware for comprehensive request and system tracking.
"""

import time
import logging
import asyncio
import psutil
import gc
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy import text
from prometheus_client import Histogram, Counter, Gauge

from app.services.prometheus_service import prometheus_service
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics collected during request processing."""
    request_id: str
    method: str
    path: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0

    # System metrics at start
    memory_mb_start: float = 0.0
    cpu_percent_start: float = 0.0
    open_files_start: int = 0

    # System metrics at end
    memory_mb_end: float = 0.0
    cpu_percent_end: float = 0.0
    open_files_end: int = 0
    memory_delta_mb: float = 0.0

    # Database metrics
    db_query_count: int = 0
    db_total_time_ms: float = 0.0
    db_connections_active: int = 0

    # Response metrics
    response_status_code: int = 0
    response_size_bytes: int = 0
    response_content_type: str = ""

    # Processing details
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    user_agent: str = ""
    client_ip: str = ""

    # Custom metrics
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Advanced performance monitoring middleware with comprehensive metrics collection."""

    def __init__(self, app,
                 enable_detailed_profiling: bool = True,
                 enable_memory_tracking: bool = True,
                 enable_database_tracking: bool = True,
                 enable_response_tracking: bool = True):
        super().__init__(app)
        self.enable_detailed_profiling = enable_detailed_profiling
        self.enable_memory_tracking = enable_memory_tracking
        self.enable_database_tracking = enable_database_tracking
        self.enable_response_tracking = enable_response_tracking

        # Create additional Prometheus metrics for detailed monitoring
        self.memory_usage_histogram = Histogram(
            'ap_intake_request_memory_usage_histogram_mb',
            'Memory usage during request processing in MB',
            ['endpoint', 'method'],
            buckets=[1, 5, 10, 25, 50, 100, 200, 500, 1000],
            registry=prometheus_service.registry
        )

        self.cpu_usage_histogram = Histogram(
            'ap_intake_request_cpu_usage_histogram_percent',
            'CPU usage during request processing',
            ['endpoint', 'method'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 20, 50, 100],
            registry=prometheus_service.registry
        )

        self.database_query_histogram = Histogram(
            'ap_intake_database_query_histogram_duration_ms',
            'Database query duration in milliseconds',
            ['query_type', 'endpoint'],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000],
            registry=prometheus_service.registry
        )

        self.response_size_histogram = Histogram(
            'ap_intake_response_size_histogram_bytes',
            'Response size in bytes',
            ['endpoint', 'status_code', 'content_type'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
            registry=prometheus_service.registry
        )

        self.gc_collections_counter = Counter(
            'ap_intake_gc_collections_total',
            'Number of garbage collections during requests',
            ['generation'],
            registry=prometheus_service.registry
        )

        self.active_requests_gauge = Gauge(
            'ap_intake_active_requests',
            'Number of currently active requests',
            ['endpoint'],
            registry=prometheus_service.registry
        )

        logger.info("Performance middleware initialized with detailed monitoring")

    async def dispatch(self, request: Request, call_next):
        """Process request with comprehensive performance monitoring."""
        # Generate unique request ID
        request_id = f"{int(time.time() * 1000)}-{id(request)}"

        # Initialize metrics
        metrics = PerformanceMetrics(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
            client_ip=self._get_client_ip(request)
        )

        # Store request context
        request.state.performance_metrics = metrics
        request.state.request_id = request_id

        # Update active requests gauge
        endpoint_key = self._normalize_endpoint(request.url.path)
        self.active_requests_gauge.labels(endpoint=endpoint_key).inc()

        try:
            # Collect initial system metrics
            if self.enable_memory_tracking:
                await self._collect_system_metrics_start(metrics)

            # Start database tracking
            if self.enable_database_tracking:
                await self._start_database_tracking(request)

            # Process the request
            response = await call_next(request)

            # Record completion metrics
            metrics.end_time = time.time()
            metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000
            metrics.response_status_code = response.status_code
            metrics.response_content_type = response.headers.get("content-type", "")

            # Collect final system metrics
            if self.enable_memory_tracking:
                await self._collect_system_metrics_end(metrics)

            # Track response size
            if self.enable_response_tracking:
                await self._track_response_size(request, response, metrics)

            # Record metrics in Prometheus
            await self._record_prometheus_metrics(request, response, metrics)

            # Add performance headers to response
            self._add_performance_headers(response, metrics)

            return response

        except Exception as e:
            # Record exception metrics
            metrics.exception_type = type(e).__name__
            metrics.exception_message = str(e)
            metrics.end_time = time.time()
            metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000

            # Log performance details for errors
            logger.error(
                f"Request {request_id} failed after {metrics.duration_ms:.2f}ms: "
                f"{request.method} {request.url.path} - {type(e).__name__}: {str(e)}"
            )

            # Re-raise the exception
            raise

        finally:
            # Update active requests gauge
            self.active_requests_gauge.labels(endpoint=endpoint_key).dec()

            # Log detailed performance metrics (debug level)
            if logger.isEnabledFor(logging.DEBUG):
                await self._log_detailed_metrics(request, metrics)

            # Store metrics for analysis (if enabled)
            if self.enable_detailed_profiling:
                await self._store_detailed_metrics(metrics)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics grouping."""
        # Replace dynamic path parameters with placeholders
        import re

        # UUID patterns
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path)

        # Numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)

        # Common patterns
        path = re.sub(r'/api/v\d+/', '/api/v{version}/', path)

        return path

    async def _collect_system_metrics_start(self, metrics: PerformanceMetrics):
        """Collect system metrics at request start."""
        try:
            process = psutil.Process()

            # Memory metrics
            memory_info = process.memory_info()
            metrics.memory_mb_start = memory_info.rss / 1024 / 1024

            # CPU metrics
            metrics.cpu_percent_start = process.cpu_percent()

            # Open files
            try:
                metrics.open_files_start = len(process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                metrics.open_files_start = 0

        except Exception as e:
            logger.warning(f"Failed to collect start system metrics: {e}")

    async def _collect_system_metrics_end(self, metrics: PerformanceMetrics):
        """Collect system metrics at request end."""
        try:
            process = psutil.Process()

            # Memory metrics
            memory_info = process.memory_info()
            metrics.memory_mb_end = memory_info.rss / 1024 / 1024
            metrics.memory_delta_mb = metrics.memory_mb_end - metrics.memory_mb_start

            # CPU metrics
            metrics.cpu_percent_end = process.cpu_percent()

            # Open files
            try:
                metrics.open_files_end = len(process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                metrics.open_files_end = 0

            # Garbage collection metrics
            gc_stats = gc.get_stats()
            total_collections = sum(stat.get('collections', 0) for stat in gc_stats)

            # Record GC collections in Prometheus
            for generation, stat in enumerate(gc_stats):
                collections = stat.get('collections', 0)
                if collections > 0:
                    self.gc_collections_counter.labels(generation=str(generation)).inc(collections)

        except Exception as e:
            logger.warning(f"Failed to collect end system metrics: {e}")

    async def _start_database_tracking(self, request: Request):
        """Start database query tracking."""
        try:
            # Store initial query count if available
            request.state.db_query_start_time = time.time()
            request.state.db_query_count = 0
            request.state.db_total_time = 0.0

        except Exception as e:
            logger.warning(f"Failed to start database tracking: {e}")

    async def _track_response_size(self, request: Request, response: Response, metrics: PerformanceMetrics):
        """Track response size metrics."""
        try:
            # For streaming responses, we can't easily measure size
            if isinstance(response, StreamingResponse):
                metrics.response_size_bytes = 0
                return

            # Try to get response size from headers or content
            content_length = response.headers.get("content-length")
            if content_length:
                metrics.response_size_bytes = int(content_length)
            else:
                # For small responses, we can try to measure
                if hasattr(response, 'body'):
                    metrics.response_size_bytes = len(response.body or b'')

        except Exception as e:
            logger.warning(f"Failed to track response size: {e}")

    async def _record_prometheus_metrics(self, request: Request, response: Response, metrics: PerformanceMetrics):
        """Record metrics in Prometheus."""
        try:
            endpoint_key = self._normalize_endpoint(request.url.path)
            status_group = str(response.status_code)[0] + "xx"

            # Record basic request metrics (already handled by existing prometheus service)
            prometheus_service.record_api_request(
                method=request.method,
                endpoint=endpoint_key,
                status_code=response.status_code,
                duration_seconds=metrics.duration_ms / 1000.0
            )

            # Record memory usage
            if self.enable_memory_tracking:
                self.memory_usage_histogram.labels(
                    endpoint=endpoint_key,
                    method=request.method
                ).observe(metrics.memory_mb_end)

            # Record CPU usage
            if self.enable_memory_tracking:
                self.cpu_usage_histogram.labels(
                    endpoint=endpoint_key,
                    method=request.method
                ).observe(max(metrics.cpu_percent_start, metrics.cpu_percent_end))

            # Record database metrics
            if self.enable_database_tracking and metrics.db_query_count > 0:
                # Record average query time
                avg_query_time = metrics.db_total_time_ms / metrics.db_query_count
                self.database_query_histogram.labels(
                    query_type="all",
                    endpoint=endpoint_key
                ).observe(avg_query_time)

            # Record response size
            if self.enable_response_tracking and metrics.response_size_bytes > 0:
                content_type_group = self._normalize_content_type(metrics.response_content_type)
                self.response_size_histogram.labels(
                    endpoint=endpoint_key,
                    status_code=status_group,
                    content_type=content_type_group
                ).observe(metrics.response_size_bytes)

        except Exception as e:
            logger.warning(f"Failed to record Prometheus metrics: {e}")

    def _normalize_content_type(self, content_type: str) -> str:
        """Normalize content type for metrics grouping."""
        content_type = content_type.lower()

        if 'json' in content_type:
            return 'json'
        elif 'html' in content_type:
            return 'html'
        elif 'text' in content_type:
            return 'text'
        elif 'image' in content_type:
            return 'image'
        elif 'application' in content_type:
            return 'application'
        else:
            return 'other'

    def _add_performance_headers(self, response: Response, metrics: PerformanceMetrics):
        """Add performance-related headers to response."""
        try:
            response.headers["X-Request-ID"] = metrics.request_id
            response.headers["X-Process-Time-Ms"] = f"{metrics.duration_ms:.2f}"

            if self.enable_memory_tracking and metrics.memory_delta_mb != 0:
                response.headers["X-Memory-Delta-MB"] = f"{metrics.memory_delta_mb:.2f}"

            if self.enable_database_tracking and metrics.db_query_count > 0:
                response.headers["X-DB-Queries"] = str(metrics.db_query_count)
                response.headers["X-DB-Time-Ms"] = f"{metrics.db_total_time_ms:.2f}"

        except Exception as e:
            logger.warning(f"Failed to add performance headers: {e}")

    async def _log_detailed_metrics(self, request: Request, metrics: PerformanceMetrics):
        """Log detailed performance metrics for debugging."""
        try:
            log_data = {
                "request_id": metrics.request_id,
                "method": metrics.method,
                "path": metrics.path,
                "duration_ms": round(metrics.duration_ms, 2),
                "status": metrics.response_status_code,
                "memory_mb": {
                    "start": round(metrics.memory_mb_start, 2),
                    "end": round(metrics.memory_mb_end, 2),
                    "delta": round(metrics.memory_delta_mb, 2)
                },
                "cpu_percent": {
                    "start": round(metrics.cpu_percent_start, 2),
                    "end": round(metrics.cpu_percent_end, 2)
                },
                "client_ip": metrics.client_ip,
                "user_agent": metrics.user_agent[:100]  # Truncate for readability
            }

            if self.enable_database_tracking:
                log_data["database"] = {
                    "query_count": metrics.db_query_count,
                    "total_time_ms": round(metrics.db_total_time_ms, 2)
                }

            if metrics.exception_type:
                log_data["exception"] = {
                    "type": metrics.exception_type,
                    "message": metrics.exception_message
                }

            logger.debug(f"Performance metrics: {log_data}")

        except Exception as e:
            logger.warning(f"Failed to log detailed metrics: {e}")

    async def _store_detailed_metrics(self, metrics: PerformanceMetrics):
        """Store detailed metrics for analysis (optional)."""
        try:
            # This could store metrics in a time-series database,
            # file system, or other storage for later analysis
            # For now, we'll just log a summary

            if metrics.duration_ms > 1000:  # Log slow requests
                logger.warning(
                    f"Slow request detected: {metrics.method} {metrics.path} "
                    f"took {metrics.duration_ms:.2f}ms (ID: {metrics.request_id})"
                )

        except Exception as e:
            logger.warning(f"Failed to store detailed metrics: {e}")


class DatabaseQueryMonitor:
    """Monitor database queries during request processing."""

    def __init__(self):
        self.query_count = 0
        self.total_time_ms = 0.0
        self.query_times = []

    def record_query(self, query: str, duration_ms: float):
        """Record a database query."""
        self.query_count += 1
        self.total_time_ms += duration_ms
        self.query_times.append({
            "query": query[:100],  # Truncate for storage
            "duration_ms": duration_ms,
            "timestamp": time.time()
        })

    def get_stats(self) -> Dict[str, Any]:
        """Get query statistics."""
        return {
            "query_count": self.query_count,
            "total_time_ms": self.total_time_ms,
            "average_time_ms": self.total_time_ms / max(1, self.query_count),
            "max_time_ms": max([q["duration_ms"] for q in self.query_times], default=0),
            "slow_queries": [q for q in self.query_times if q["duration_ms"] > 100]
        }


# Global database monitor instance
db_monitor = DatabaseQueryMonitor()