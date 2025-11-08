#!/usr/bin/env python3
"""
Performance Monitor for AP Intake & Validation System

This module provides comprehensive system monitoring during performance tests:
- CPU, memory, disk, and network monitoring
- Database connection pool monitoring
- API response time monitoring
- Custom metrics collection
- Real-time alerting on threshold breaches
- Performance data export and analysis
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
import httpx
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """Container for system performance metrics."""

    timestamp: float
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_available_mb: float
    memory_used_mb: float
    disk_usage_percent: float
    disk_read_mb_s: float
    disk_write_mb_s: float
    network_sent_mb_s: float
    network_recv_mb_s: float
    load_average: List[float] = field(default_factory=list)
    process_count: int = 0
    running_processes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "cpu_count": self.cpu_count,
            "memory_percent": self.memory_percent,
            "memory_available_mb": self.memory_available_mb,
            "memory_used_mb": self.memory_used_mb,
            "disk_usage_percent": self.disk_usage_percent,
            "disk_read_mb_s": self.disk_read_mb_s,
            "disk_write_mb_s": self.disk_write_mb_s,
            "network_sent_mb_s": self.network_sent_mb_s,
            "network_recv_mb_s": self.network_recv_mb_s,
            "load_average": self.load_average,
            "process_count": self.process_count,
            "running_processes": self.running_processes
        }


@dataclass
class DatabaseMetrics:
    """Container for database performance metrics."""

    timestamp: float
    active_connections: int
    idle_connections: int
    total_connections: int
    waiting_connections: int
    database_size_mb: float
    cache_hit_ratio: float
    transactions_per_second: float
    queries_per_second: float
    avg_query_time_ms: float
    slow_queries_count: int
    lock_waits: int
    deadlock_count: int
    replication_lag_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "total_connections": self.total_connections,
            "waiting_connections": self.waiting_connections,
            "database_size_mb": self.database_size_mb,
            "cache_hit_ratio": self.cache_hit_ratio,
            "transactions_per_second": self.transactions_per_second,
            "queries_per_second": self.queries_per_second,
            "avg_query_time_ms": self.avg_query_time_ms,
            "slow_queries_count": self.slow_queries_count,
            "lock_waits": self.lock_waits,
            "deadlock_count": self.deadlock_count,
            "replication_lag_seconds": self.replication_lag_seconds
        }


@dataclass
class ApplicationMetrics:
    """Container for application-specific metrics."""

    timestamp: float
    active_requests: int
    queued_requests: int
    avg_response_time_ms: float
    requests_per_second: float
    error_rate: float
    active_workers: int
    queue_size: int
    processing_time_avg_ms: float
    memory_usage_mb: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "active_requests": self.active_requests,
            "queued_requests": self.queued_requests,
            "avg_response_time_ms": self.avg_response_time_ms,
            "requests_per_second": self.requests_per_second,
            "error_rate": self.error_rate,
            "active_workers": self.active_workers,
            "queue_size": self.queue_size,
            "processing_time_avg_ms": self.processing_time_avg_ms,
            "memory_usage_mb": self.memory_usage_mb
        }


class PerformanceMonitor:
    """Main performance monitoring class."""

    def __init__(
        self,
        sampling_interval: float = 1.0,
        max_samples: int = 3600,  # 1 hour at 1s intervals
        alert_thresholds: Optional[Dict[str, float]] = None
    ):
        self.sampling_interval = sampling_interval
        self.max_samples = max_samples
        self.alert_thresholds = alert_thresholds or {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_usage_percent": 90.0,
            "error_rate": 5.0,
            "avg_response_time_ms": 2000.0,
            "queue_size": 100,
            "database_connections": 80
        }

        # Data storage
        self.system_metrics: deque = deque(maxlen=max_samples)
        self.database_metrics: deque = deque(maxlen=max_samples)
        self.application_metrics: deque = deque(maxlen=max_samples)
        self.alerts: List[Dict[str, Any]] = []

        # Monitoring state
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.start_time: Optional[float] = None

        # Previous measurements for rate calculations
        self.prev_disk_io: Optional[psutil.disk_io_counters] = None
        self.prev_network_io: Optional[psutil.net_io_counters] = None
        self.prev_db_stats: Optional[Dict[str, Any]] = None

    async def start_monitoring(
        self,
        api_base_url: str = "http://localhost:8000",
        database_url: str = None
    ):
        """Start performance monitoring."""
        if self.monitoring:
            logger.warning("Monitoring is already running")
            return

        self.monitoring = True
        self.start_time = time.perf_counter()
        self.api_base_url = api_base_url
        self.database_url = database_url

        logger.info(f"Starting performance monitoring with {self.sampling_interval}s interval")

        self.monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.monitoring:
            return

        logger.info("Stopping performance monitoring")

        self.monitoring = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                timestamp = time.perf_counter()

                # Collect system metrics
                system_metrics = await self._collect_system_metrics(timestamp)
                self.system_metrics.append(system_metrics)

                # Collect database metrics
                try:
                    db_metrics = await self._collect_database_metrics(timestamp)
                    self.database_metrics.append(db_metrics)
                except Exception as e:
                    logger.warning(f"Failed to collect database metrics: {e}")

                # Collect application metrics
                try:
                    app_metrics = await self._collect_application_metrics(timestamp)
                    self.application_metrics.append(app_metrics)
                except Exception as e:
                    logger.warning(f"Failed to collect application metrics: {e}")

                # Check for alerts
                await self._check_alerts(system_metrics, db_metrics, app_metrics)

                await asyncio.sleep(self.sampling_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.sampling_interval)

    async def _collect_system_metrics(self, timestamp: float) -> SystemMetrics:
        """Collect system-level metrics."""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count()

        # Memory metrics
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / 1024 / 1024
        memory_used_mb = memory.used / 1024 / 1024

        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_usage_percent = disk.percent

        # Disk I/O rates
        current_disk_io = psutil.disk_io_counters()
        disk_read_mb_s = 0.0
        disk_write_mb_s = 0.0

        if self.prev_disk_io and current_disk_io:
            time_delta = self.sampling_interval
            disk_read_mb_s = (current_disk_io.read_bytes - self.prev_disk_io.read_bytes) / 1024 / 1024 / time_delta
            disk_write_mb_s = (current_disk_io.write_bytes - self.prev_disk_io.write_bytes) / 1024 / 1024 / time_delta

        self.prev_disk_io = current_disk_io

        # Network I/O rates
        current_network_io = psutil.net_io_counters()
        network_sent_mb_s = 0.0
        network_recv_mb_s = 0.0

        if self.prev_network_io and current_network_io:
            time_delta = self.sampling_interval
            network_sent_mb_s = (current_network_io.bytes_sent - self.prev_network_io.bytes_sent) / 1024 / 1024 / time_delta
            network_recv_mb_s = (current_network_io.bytes_recv - self.prev_network_io.bytes_recv) / 1024 / 1024 / time_delta

        self.prev_network_io = current_network_io

        # Load average (Unix-like systems)
        try:
            load_average = list(psutil.getloadavg())
        except AttributeError:
            # Windows doesn't have load average
            load_average = [0.0, 0.0, 0.0]

        # Process metrics
        process_count = len(psutil.pids())
        running_processes = len([p for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING])

        return SystemMetrics(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            memory_used_mb=memory_used_mb,
            disk_usage_percent=disk_usage_percent,
            disk_read_mb_s=disk_read_mb_s,
            disk_write_mb_s=disk_write_mb_s,
            network_sent_mb_s=network_sent_mb_s,
            network_recv_mb_s=network_recv_mb_s,
            load_average=load_average,
            process_count=process_count,
            running_processes=running_processes
        )

    async def _collect_database_metrics(self, timestamp: float) -> DatabaseMetrics:
        """Collect database performance metrics."""
        # Import here to avoid circular imports
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Connection metrics
            conn_result = await session.execute(text("""
                SELECT
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections,
                    count(*) FILTER (WHERE wait_event_type = 'Lock') as waiting_connections
                FROM pg_stat_activity
                WHERE datname = current_database()
            """))

            conn_stats = conn_result.fetchone()._asdict()

            # Database size
            size_result = await session.execute(text("""
                SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
            """))
            database_size_mb = size_result.scalar()

            # Cache hit ratio
            cache_result = await session.execute(text("""
                SELECT
                    sum(blks_hit)::float / nullif(sum(blks_hit) + sum(blks_read), 0) * 100 as cache_hit_ratio
                FROM pg_stat_database
                WHERE datname = current_database()
            """))
            cache_hit_ratio = cache_result.scalar() or 0.0

            # Query statistics (if pg_stat_statements is available)
            try:
                stats_result = await session.execute(text("""
                    SELECT
                        sum(calls) as total_calls,
                        sum(total_exec_time) as total_time,
                        sum(mean_exec_time * calls) as total_mean_time,
                        count(*) FILTER (WHERE mean_exec_time > 1000) as slow_queries
                    FROM pg_stat_statements
                """))

                stats = stats_result.fetchone()._asdict()

                # Calculate rates
                if self.prev_db_stats and self.prev_db_stats['timestamp']:
                    time_delta = timestamp - self.prev_db_stats['timestamp']
                    if time_delta > 0:
                        calls_delta = stats['total_calls'] - self.prev_db_stats['total_calls']
                        transactions_per_second = calls_delta / time_delta
                        queries_per_second = transactions_per_second  # Simplified
                    else:
                        transactions_per_second = 0.0
                        queries_per_second = 0.0
                else:
                    transactions_per_second = 0.0
                    queries_per_second = 0.0

                avg_query_time_ms = (stats['total_mean_time'] / stats['total_calls']) if stats['total_calls'] > 0 else 0.0
                slow_queries_count = stats['slow_queries']

                # Store current stats for next iteration
                self.prev_db_stats = {
                    'timestamp': timestamp,
                    'total_calls': stats['total_calls']
                }

            except Exception:
                # pg_stat_statements might not be available
                transactions_per_second = 0.0
                queries_per_second = 0.0
                avg_query_time_ms = 0.0
                slow_queries_count = 0

            # Lock metrics
            lock_result = await session.execute(text("""
                SELECT count(*) as lock_waits
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.granted = false
                AND a.datname = current_database()
            """))
            lock_waits = lock_result.scalar() or 0

            # Deadlock count (from log, might not be available)
            deadlock_count = 0  # Would need to query logs

            return DatabaseMetrics(
                timestamp=timestamp,
                active_connections=conn_stats['active_connections'],
                idle_connections=conn_stats['idle_connections'],
                total_connections=conn_stats['total_connections'],
                waiting_connections=conn_stats['waiting_connections'],
                database_size_mb=database_size_mb,
                cache_hit_ratio=cache_hit_ratio,
                transactions_per_second=transactions_per_second,
                queries_per_second=queries_per_second,
                avg_query_time_ms=avg_query_time_ms,
                slow_queries_count=slow_queries_count,
                lock_waits=lock_waits,
                deadlock_count=deadlock_count
            )

    async def _collect_application_metrics(self, timestamp: float) -> ApplicationMetrics:
        """Collect application-specific metrics."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                # Get metrics endpoint
                response = await client.get(f"{self.api_base_url}/metrics")
                if response.status_code == 200:
                    # Parse Prometheus metrics (simplified)
                    metrics_text = response.text
                    metrics = self._parse_prometheus_metrics(metrics_text)

                    return ApplicationMetrics(
                        timestamp=timestamp,
                        active_requests=metrics.get('http_requests_active', 0),
                        queued_requests=metrics.get('http_requests_queued', 0),
                        avg_response_time_ms=metrics.get('http_request_duration_seconds', 0) * 1000,
                        requests_per_second=metrics.get('http_requests_total', 0),
                        error_rate=metrics.get('http_requests_failed_total', 0) / max(metrics.get('http_requests_total', 1), 1) * 100,
                        active_workers=metrics.get('celery_workers_active', 0),
                        queue_size=metrics.get('celery_queue_length', 0),
                        processing_time_avg_ms=metrics.get('invoice_processing_time_seconds', 0) * 1000,
                        memory_usage_mb=metrics.get('process_resident_memory_bytes', 0) / 1024 / 1024
                    )
                else:
                    # Fallback to health check
                    health_response = await client.get(f"{self.api_base_url}/health")
                    return ApplicationMetrics(
                        timestamp=timestamp,
                        active_requests=0,
                        queued_requests=0,
                        avg_response_time_ms=0,
                        requests_per_second=0,
                        error_rate=0,
                        active_workers=0,
                        queue_size=0,
                        processing_time_avg_ms=0,
                        memory_usage_mb=0
                    )

            except Exception as e:
                logger.warning(f"Failed to collect application metrics: {e}")
                return ApplicationMetrics(
                    timestamp=timestamp,
                    active_requests=0,
                    queued_requests=0,
                    avg_response_time_ms=0,
                    requests_per_second=0,
                    error_rate=0,
                    active_workers=0,
                    queue_size=0,
                    processing_time_avg_ms=0,
                    memory_usage_mb=0
                )

    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, float]:
        """Parse Prometheus metrics text format."""
        metrics = {}
        for line in metrics_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '{' in line:
                # Parse metric line
                try:
                    parts = line.split('{')
                    metric_name = parts[0]
                    value_part = parts[1].split('}')[1].strip()
                    value = float(value_part)
                    metrics[metric_name] = value
                except (IndexError, ValueError):
                    continue
        return metrics

    async def _check_alerts(
        self,
        system_metrics: SystemMetrics,
        db_metrics: Optional[DatabaseMetrics],
        app_metrics: Optional[ApplicationMetrics]
    ):
        """Check for performance alerts based on thresholds."""
        alerts = []

        # System alerts
        if system_metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            alerts.append({
                "timestamp": system_metrics.timestamp,
                "type": "system",
                "metric": "cpu_percent",
                "value": system_metrics.cpu_percent,
                "threshold": self.alert_thresholds["cpu_percent"],
                "severity": "warning" if system_metrics.cpu_percent < 95 else "critical"
            })

        if system_metrics.memory_percent > self.alert_thresholds["memory_percent"]:
            alerts.append({
                "timestamp": system_metrics.timestamp,
                "type": "system",
                "metric": "memory_percent",
                "value": system_metrics.memory_percent,
                "threshold": self.alert_thresholds["memory_percent"],
                "severity": "warning" if system_metrics.memory_percent < 95 else "critical"
            })

        if system_metrics.disk_usage_percent > self.alert_thresholds["disk_usage_percent"]:
            alerts.append({
                "timestamp": system_metrics.timestamp,
                "type": "system",
                "metric": "disk_usage_percent",
                "value": system_metrics.disk_usage_percent,
                "threshold": self.alert_thresholds["disk_usage_percent"],
                "severity": "warning" if system_metrics.disk_usage_percent < 98 else "critical"
            })

        # Database alerts
        if db_metrics:
            if db_metrics.total_connections > self.alert_thresholds["database_connections"]:
                alerts.append({
                    "timestamp": db_metrics.timestamp,
                    "type": "database",
                    "metric": "total_connections",
                    "value": db_metrics.total_connections,
                    "threshold": self.alert_thresholds["database_connections"],
                    "severity": "warning"
                })

            if db_metrics.lock_waits > 10:
                alerts.append({
                    "timestamp": db_metrics.timestamp,
                    "type": "database",
                    "metric": "lock_waits",
                    "value": db_metrics.lock_waits,
                    "threshold": 10,
                    "severity": "warning"
                })

        # Application alerts
        if app_metrics:
            if app_metrics.error_rate > self.alert_thresholds["error_rate"]:
                alerts.append({
                    "timestamp": app_metrics.timestamp,
                    "type": "application",
                    "metric": "error_rate",
                    "value": app_metrics.error_rate,
                    "threshold": self.alert_thresholds["error_rate"],
                    "severity": "warning" if app_metrics.error_rate < 10 else "critical"
                })

            if app_metrics.avg_response_time_ms > self.alert_thresholds["avg_response_time_ms"]:
                alerts.append({
                    "timestamp": app_metrics.timestamp,
                    "type": "application",
                    "metric": "avg_response_time_ms",
                    "value": app_metrics.avg_response_time_ms,
                    "threshold": self.alert_thresholds["avg_response_time_ms"],
                    "severity": "warning"
                })

            if app_metrics.queue_size > self.alert_thresholds["queue_size"]:
                alerts.append({
                    "timestamp": app_metrics.timestamp,
                    "type": "application",
                    "metric": "queue_size",
                    "value": app_metrics.queue_size,
                    "threshold": self.alert_thresholds["queue_size"],
                    "severity": "warning"
                })

        # Store alerts
        self.alerts.extend(alerts)

        # Log alerts
        for alert in alerts:
            level = logging.WARNING if alert["severity"] == "warning" else logging.ERROR
            logger.log(
                level,
                f"PERFORMANCE ALERT: {alert['type']} {alert['metric']} = {alert['value']} "
                f"(threshold: {alert['threshold']}) - {alert['severity'].upper()}"
            )

    def get_summary_statistics(
        self,
        minutes_back: int = 10
    ) -> Dict[str, Any]:
        """Get summary statistics for the last N minutes."""
        cutoff_time = time.perf_counter() - (minutes_back * 60)

        # Filter recent metrics
        recent_system = [m for m in self.system_metrics if m.timestamp >= cutoff_time]
        recent_db = [m for m in self.database_metrics if m.timestamp >= cutoff_time]
        recent_app = [m for m in self.application_metrics if m.timestamp >= cutoff_time]

        summary = {
            "time_range_minutes": minutes_back,
            "system_metrics": {},
            "database_metrics": {},
            "application_metrics": {},
            "alerts": [a for a in self.alerts if a["timestamp"] >= cutoff_time]
        }

        # System statistics
        if recent_system:
            cpu_values = [m.cpu_percent for m in recent_system]
            memory_values = [m.memory_percent for m in recent_system]

            summary["system_metrics"] = {
                "cpu": {
                    "current": cpu_values[-1] if cpu_values else 0,
                    "average": np.mean(cpu_values) if cpu_values else 0,
                    "max": np.max(cpu_values) if cpu_values else 0,
                    "min": np.min(cpu_values) if cpu_values else 0
                },
                "memory": {
                    "current": memory_values[-1] if memory_values else 0,
                    "average": np.mean(memory_values) if memory_values else 0,
                    "max": np.max(memory_values) if memory_values else 0,
                    "min": np.min(memory_values) if memory_values else 0
                },
                "samples": len(recent_system)
            }

        # Database statistics
        if recent_db:
            connection_values = [m.total_connections for m in recent_db]
            qps_values = [m.queries_per_second for m in recent_db]

            summary["database_metrics"] = {
                "connections": {
                    "current": connection_values[-1] if connection_values else 0,
                    "average": np.mean(connection_values) if connection_values else 0,
                    "max": np.max(connection_values) if connection_values else 0
                },
                "queries_per_second": {
                    "current": qps_values[-1] if qps_values else 0,
                    "average": np.mean(qps_values) if qps_values else 0,
                    "max": np.max(qps_values) if qps_values else 0
                },
                "samples": len(recent_db)
            }

        # Application statistics
        if recent_app:
            rps_values = [m.requests_per_second for m in recent_app]
            response_time_values = [m.avg_response_time_ms for m in recent_app]

            summary["application_metrics"] = {
                "requests_per_second": {
                    "current": rps_values[-1] if rps_values else 0,
                    "average": np.mean(rps_values) if rps_values else 0,
                    "max": np.max(rps_values) if rps_values else 0
                },
                "response_time_ms": {
                    "current": response_time_values[-1] if response_time_values else 0,
                    "average": np.mean(response_time_values) if response_time_values else 0,
                    "max": np.max(response_time_values) if response_time_values else 0
                },
                "samples": len(recent_app)
            }

        return summary

    def export_data(
        self,
        output_file: str,
        format: str = "json"
    ):
        """Export monitoring data to file."""
        data = {
            "export_timestamp": time.time(),
            "monitoring_duration": time.perf_counter() - self.start_time if self.start_time else 0,
            "system_metrics": [m.to_dict() for m in self.system_metrics],
            "database_metrics": [m.to_dict() for m in self.database_metrics],
            "application_metrics": [m.to_dict() for m in self.application_metrics],
            "alerts": self.alerts,
            "alert_thresholds": self.alert_thresholds
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "json":
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
        elif format.lower() == "csv":
            # Export as CSV (system metrics only for simplicity)
            import csv

            with open(output_path, 'w', newline='') as f:
                if self.system_metrics:
                    fieldnames = self.system_metrics[0].to_dict().keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for metric in self.system_metrics:
                        writer.writerow(metric.to_dict())
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Data exported to {output_path}")

    def generate_report(self) -> str:
        """Generate performance monitoring report."""
        if not self.system_metrics:
            return "No monitoring data available"

        # Get overall statistics
        duration = time.perf_counter() - self.start_time if self.start_time else 0
        summary = self.get_summary_statistics(minutes_back=int(duration // 60) or 1)

        report = []
        report.append("# Performance Monitoring Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Monitoring Duration: {duration:.1f} seconds")
        report.append(f"Total Samples: {len(self.system_metrics)}")
        report.append(f"Total Alerts: {len(self.alerts)}")
        report.append("")

        # System metrics summary
        if "system_metrics" in summary and summary["system_metrics"]:
            sys_stats = summary["system_metrics"]
            report.append("## System Metrics Summary")
            report.append(f"- **CPU Usage:** Current {sys_stats['cpu']['current']:.1f}%, "
                         f"Avg {sys_stats['cpu']['average']:.1f}%, "
                         f"Max {sys_stats['cpu']['max']:.1f}%")
            report.append(f"- **Memory Usage:** Current {sys_stats['memory']['current']:.1f}%, "
                         f"Avg {sys_stats['memory']['average']:.1f}%, "
                         f"Max {sys_stats['memory']['max']:.1f}%")
            report.append("")

        # Database metrics summary
        if "database_metrics" in summary and summary["database_metrics"]:
            db_stats = summary["database_metrics"]
            report.append("## Database Metrics Summary")
            report.append(f"- **Connections:** Current {db_stats['connections']['current']}, "
                         f"Avg {db_stats['connections']['average']:.1f}, "
                         f"Max {db_stats['connections']['max']}")
            report.append(f"- **Queries/sec:** Current {db_stats['queries_per_second']['current']:.1f}, "
                         f"Avg {db_stats['queries_per_second']['average']:.1f}, "
                         f"Max {db_stats['queries_per_second']['max']:.1f}")
            report.append("")

        # Application metrics summary
        if "application_metrics" in summary and summary["application_metrics"]:
            app_stats = summary["application_metrics"]
            report.append("## Application Metrics Summary")
            report.append(f"- **Requests/sec:** Current {app_stats['requests_per_second']['current']:.1f}, "
                         f"Avg {app_stats['requests_per_second']['average']:.1f}, "
                         f"Max {app_stats['requests_per_second']['max']:.1f}")
            report.append(f"- **Response Time:** Current {app_stats['response_time_ms']['current']:.1f}ms, "
                         f"Avg {app_stats['response_time_ms']['average']:.1f}ms, "
                         f"Max {app_stats['response_time_ms']['max']:.1f}ms")
            report.append("")

        # Recent alerts
        if summary["alerts"]:
            report.append("## Recent Alerts")
            for alert in summary["alerts"][-10:]:  # Last 10 alerts
                alert_time = datetime.fromtimestamp(alert["timestamp"]).strftime('%H:%M:%S')
                report.append(f"- **{alert_time}** [{alert['severity'].upper()}] "
                             f"{alert['type']} {alert['metric']}: {alert['value']} "
                             f"(threshold: {alert['threshold']})")
            report.append("")

        # Performance thresholds
        report.append("## Performance Thresholds")
        for metric, threshold in self.alert_thresholds.items():
            report.append(f"- **{metric}**: {threshold}")
        report.append("")

        return "\n".join(report)


async def main():
    """CLI interface for performance monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="Run performance monitoring")
    parser.add_argument("--duration", type=int, default=300, help="Monitoring duration in seconds")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", help="Output file for monitoring data")
    parser.add_argument("--report", help="Output file for monitoring report")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")

    args = parser.parse_args()

    # Configure thresholds
    thresholds = {
        "cpu_percent": 80.0,
        "memory_percent": 85.0,
        "disk_usage_percent": 90.0,
        "error_rate": 5.0,
        "avg_response_time_ms": 2000.0,
        "queue_size": 100,
        "database_connections": 80
    }

    monitor = PerformanceMonitor(
        sampling_interval=args.interval,
        alert_thresholds=thresholds
    )

    print(f"Starting performance monitoring for {args.duration} seconds...")
    print(f"Sampling interval: {args.interval}s")
    print(f"API URL: {args.api_url}")
    print(f"Press Ctrl+C to stop early")

    try:
        await monitor.start_monitoring(api_base_url=args.api_url)

        # Monitor for specified duration
        await asyncio.sleep(args.duration)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")

    finally:
        await monitor.stop_monitoring()

    # Generate and display summary
    summary = monitor.get_summary_statistics()
    print("\n=== Performance Summary ===")
    print(json.dumps(summary, indent=2))

    # Export data if requested
    if args.output:
        monitor.export_data(args.output, args.format)
        print(f"\nData exported to {args.output}")

    # Generate report if requested
    if args.report:
        report = monitor.generate_report()
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.report}")
        print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())