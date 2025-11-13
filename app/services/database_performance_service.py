"""
Database performance monitoring and analysis service for AP Intake & Validation system.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_engine_from_config
from sqlalchemy.pool import QueuePool
from prometheus_client import Histogram, Counter, Gauge

from app.core.config import settings
from app.db.session import engine, AsyncSessionLocal
from app.services.prometheus_service import prometheus_service

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a database query."""
    query_hash: str
    query_pattern: str
    execution_time_ms: float
    rows_affected: int
    timestamp: datetime
    session_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    tables_accessed: List[str] = field(default_factory=list)
    indexes_used: List[str] = field(default_factory=list)
    execution_plan: Optional[Dict[str, Any]] = None
    slow_query_threshold_ms: float = 100.0

    @property
    def is_slow(self) -> bool:
        """Check if this is a slow query."""
        return self.execution_time_ms > self.slow_query_threshold_ms


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    timestamp: datetime

    # Connection metrics
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    connection_wait_time_ms: float = 0.0

    # Query metrics
    queries_per_second: float = 0.0
    avg_query_time_ms: float = 0.0
    slow_queries_per_second: float = 0.0

    # Resource metrics
    cache_hit_ratio: float = 0.0
    index_usage_ratio: float = 0.0
    table_locks: int = 0
    deadlocks: int = 0

    # Storage metrics
    database_size_mb: float = 0.0
    table_sizes: Dict[str, float] = field(default_factory=dict)
    index_sizes: Dict[str, float] = field(default_factory=dict)

    # Performance metrics
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    disk_io_mb_per_sec: float = 0.0
    network_io_mb_per_sec: float = 0.0


class DatabasePerformanceService:
    """Service for monitoring and analyzing database performance."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.query_metrics: List[QueryMetrics] = []
        self.slow_queries: List[QueryMetrics] = []
        self.max_query_history = 10000
        self.max_slow_query_history = 1000

        # Prometheus metrics for database performance
        self.db_query_duration_histogram = Histogram(
            'ap_intake_database_query_duration_ms',
            'Database query duration in milliseconds',
            ['query_type', 'table_name', 'is_slow'],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000],
            registry=prometheus_service.registry
        )

        self.db_connections_gauge = Gauge(
            'ap_intake_database_connections_by_state',
            'Number of database connections by state',
            ['state'],  # active, idle, total
            registry=prometheus_service.registry
        )

        self.db_slow_queries_counter = Counter(
            'ap_intake_database_slow_queries_total',
            'Total number of slow database queries',
            ['query_hash', 'table_name'],
            registry=prometheus_service.registry
        )

        self.db_cache_hit_ratio_gauge = Gauge(
            'ap_intake_database_cache_hit_ratio',
            'Database cache hit ratio',
            registry=prometheus_service.registry
        )

        self.db_locks_gauge = Gauge(
            'ap_intake_database_locks',
            'Number of database locks',
            ['lock_type'],
            registry=prometheus_service.registry
        )

        # Register query listeners
        self._setup_query_listeners()

    def _setup_query_listeners(self):
        """Setup SQLAlchemy event listeners for query monitoring."""
        try:
            # Register event listener for query execution
            @event.listens_for(engine.sync_engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                context._query_start_time = time.time()

            @event.listens_for(engine.sync_engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                if hasattr(context, '_query_start_time'):
                    execution_time_ms = (time.time() - context._query_start_time) * 1000
                    self._record_query_metrics(statement, parameters, execution_time_ms, cursor)

        except Exception as e:
            self.logger.warning(f"Failed to setup query listeners: {e}")

    def _record_query_metrics(self, query: str, parameters: Any, execution_time_ms: float, cursor):
        """Record metrics for a executed query."""
        try:
            # Generate query hash for pattern matching
            query_hash = self._generate_query_hash(query)
            query_pattern = self._normalize_query(query)

            # Extract table names from query
            tables_accessed = self._extract_table_names(query)

            # Create metrics record
            query_metrics = QueryMetrics(
                query_hash=query_hash,
                query_pattern=query_pattern,
                execution_time_ms=execution_time_ms,
                rows_affected=cursor.rowcount if cursor else 0,
                timestamp=datetime.utcnow(),
                session_id=str(id(cursor.connection) if cursor else "unknown"),
                parameters=parameters if isinstance(parameters, dict) else {}
            )

            query_metrics.tables_accessed = tables_accessed

            # Add to history
            self.query_metrics.append(query_metrics)
            if len(self.query_metrics) > self.max_query_history:
                self.query_metrics = self.query_metrics[-self.max_query_history:]

            # Track slow queries
            if query_metrics.is_slow:
                self.slow_queries.append(query_metrics)
                if len(self.slow_queries) > self.max_slow_query_history:
                    self.slow_queries = self.slow_queries[-self.max_slow_query_history:]

                # Record in Prometheus
                for table in tables_accessed:
                    self.db_slow_queries_counter.labels(
                        query_hash=query_hash[:16],  # Truncate for label
                        table_name=table
                    ).inc()

            # Record in Prometheus histograms
            query_type = self._classify_query(query)
            for table in tables_accessed:
                self.db_query_duration_histogram.labels(
                    query_type=query_type,
                    table_name=table,
                    is_slow=str(query_metrics.is_slow).lower()
                ).observe(execution_time_ms)

        except Exception as e:
            self.logger.warning(f"Failed to record query metrics: {e}")

    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for query pattern matching."""
        # Normalize query by removing parameter values and whitespace
        normalized = self._normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _normalize_query(self, query: str) -> str:
        """Normalize query by removing parameter values and standardizing format."""
        import re

        # Convert to uppercase for consistency
        query = query.upper()

        # Replace string literals with placeholders
        query = re.sub(r"'[^']*'", "'?'", query)
        query = re.sub(r'"[^"]*"', '"?"', query)

        # Replace numeric values with placeholders
        query = re.sub(r'\b\d+\b', '?', query)

        # Standardize whitespace
        query = re.sub(r'\s+', ' ', query).strip()

        return query

    def _extract_table_names(self, query: str) -> List[str]:
        """Extract table names from SQL query."""
        import re

        tables = []
        query_upper = query.upper()

        # Find FROM clause
        from_match = re.search(r'FROM\s+([^\s,]+(?:\s*,\s*[^\s,]+)*)', query_upper)
        if from_match:
            tables.extend([t.strip() for t in from_match.group(1).split(',')])

        # Find JOIN clauses
        join_matches = re.findall(r'JOIN\s+([^\s]+)', query_upper)
        tables.extend(join_matches)

        # Remove duplicates and common SQL keywords
        tables = list(set(tables))
        tables = [t for t in tables if t not in ['SELECT', 'WHERE', 'ORDER', 'GROUP', 'HAVING', 'LIMIT']]

        return tables

    def _classify_query(self, query: str) -> str:
        """Classify query type based on SQL keywords."""
        query_upper = query.upper().strip()

        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('CREATE'):
            return 'CREATE'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        elif query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('TRUNCATE'):
            return 'TRUNCATE'
        else:
            return 'OTHER'

    async def collect_database_metrics(self) -> DatabaseMetrics:
        """Collect comprehensive database performance metrics."""
        try:
            metrics = DatabaseMetrics(timestamp=datetime.utcnow())

            async with AsyncSessionLocal() as session:
                # Collect connection metrics
                await self._collect_connection_metrics(session, metrics)

                # Collect query performance metrics
                await self._collect_query_metrics(session, metrics)

                # Collect resource metrics
                await self._collect_resource_metrics(session, metrics)

                # Collect storage metrics
                await self._collect_storage_metrics(session, metrics)

                # Update Prometheus gauges
                self._update_prometheus_metrics(metrics)

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to collect database metrics: {e}")
            return DatabaseMetrics(timestamp=datetime.utcnow())

    async def _collect_connection_metrics(self, session: AsyncSession, metrics: DatabaseMetrics):
        """Collect database connection metrics."""
        try:
            # PostgreSQL connection metrics
            if "postgresql" in str(engine.url).lower():
                result = await session.execute(text("""
                    SELECT
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections,
                        avg(EXTRACT(EPOCH FROM (now() - state_change)) * 1000) as avg_wait_time_ms
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """))

                row = result.fetchone()
                if row:
                    metrics.total_connections = row.total_connections or 0
                    metrics.active_connections = row.active_connections or 0
                    metrics.idle_connections = row.idle_connections or 0
                    metrics.connection_wait_time_ms = row.avg_wait_time_ms or 0.0

        except Exception as e:
            self.logger.warning(f"Failed to collect connection metrics: {e}")

    async def _collect_query_metrics(self, session: AsyncSession, metrics: DatabaseMetrics):
        """Collect query performance metrics."""
        try:
            if "postgresql" in str(engine.url).lower():
                # PostgreSQL query metrics
                result = await session.execute(text("""
                    SELECT
                        sum(xact_commit + xact_rollback) as total_queries,
                        sum(blks_hit) / greatest(sum(blks_hit + blks_read), 1) as cache_hit_ratio,
                        sum(tup_returned) / greatest(sum(tup_fetched), 1) as index_usage_ratio
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """))

                row = result.fetchone()
                if row:
                    # Calculate queries per second (approximate)
                    time_window = 60  # 1 minute window
                    metrics.queries_per_second = (row.total_queries or 0) / time_window
                    metrics.cache_hit_ratio = float(row.cache_hit_ratio or 0)
                    metrics.index_usage_ratio = float(row.index_usage_ratio or 0)

                # Get slow query count
                slow_result = await session.execute(text("""
                    SELECT count(*)
                    FROM pg_stat_statements
                    WHERE mean_exec_time > 100  -- queries slower than 100ms
                """))

                slow_row = slow_result.fetchone()
                if slow_row:
                    metrics.slow_queries_per_second = (slow_row.count or 0) / time_window

        except Exception as e:
            self.logger.warning(f"Failed to collect query metrics: {e}")

    async def _collect_resource_metrics(self, session: AsyncSession, metrics: DatabaseMetrics):
        """Collect database resource metrics."""
        try:
            if "postgresql" in str(engine.url).lower():
                # Lock information
                lock_result = await session.execute(text("""
                    SELECT
                        locktype,
                        count(*) as lock_count
                    FROM pg_locks
                    WHERE pid != pg_backend_pid()
                    GROUP BY locktype
                """))

                locks = {}
                for row in lock_result:
                    locks[row.locktype] = row.lock_count

                metrics.table_locks = locks.get('relation', 0)

                # Deadlock information
                deadlock_result = await session.execute(text("""
                    SELECT count(*)
                    FROM pg_stat_database
                    WHERE datname = current_database() AND deadlocks > 0
                """))

                deadlock_row = deadlock_result.fetchone()
                metrics.deadlocks = deadlock_row.count if deadlock_row else 0

        except Exception as e:
            self.logger.warning(f"Failed to collect resource metrics: {e}")

    async def _collect_storage_metrics(self, session: AsyncSession, metrics: DatabaseMetrics):
        """Collect database storage metrics."""
        try:
            if "postgresql" in str(engine.url).lower():
                # Database size
                size_result = await session.execute(text("""
                    SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
                """))

                size_row = size_result.fetchone()
                if size_row:
                    metrics.database_size_mb = size_row.size_mb or 0

                # Table sizes
                table_result = await session.execute(text("""
                    SELECT
                        schemaname||'.'||tablename as table_name,
                        pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024 as size_mb
                    FROM pg_tables
                    WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                    ORDER BY size_mb DESC
                    LIMIT 20
                """))

                for row in table_result:
                    metrics.table_sizes[row.table_name] = row.size_mb or 0

        except Exception as e:
            self.logger.warning(f"Failed to collect storage metrics: {e}")

    def _update_prometheus_metrics(self, metrics: DatabaseMetrics):
        """Update Prometheus gauges with collected metrics."""
        try:
            # Connection metrics
            self.db_connections_gauge.labels(state='active').set(metrics.active_connections)
            self.db_connections_gauge.labels(state='idle').set(metrics.idle_connections)
            self.db_connections_gauge.labels(state='total').set(metrics.total_connections)

            # Performance metrics
            self.db_cache_hit_ratio_gauge.set(metrics.cache_hit_ratio)
            self.db_locks_gauge.labels(lock_type='table').set(metrics.table_locks)
            self.db_locks_gauge.labels(lock_type='deadlock').set(metrics.deadlocks)

        except Exception as e:
            self.logger.warning(f"Failed to update Prometheus metrics: {e}")

    async def get_slow_queries(self, limit: int = 100, time_window_hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent slow queries."""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

        slow_queries = [
            {
                "query_hash": q.query_hash,
                "query_pattern": q.query_pattern,
                "execution_time_ms": q.execution_time_ms,
                "rows_affected": q.rows_affected,
                "timestamp": q.timestamp.isoformat(),
                "tables_accessed": q.tables_accessed,
                "parameters": q.parameters
            }
            for q in self.slow_queries
            if q.timestamp >= cutoff_time
        ]

        # Sort by execution time (slowest first) and limit
        slow_queries.sort(key=lambda x: x["execution_time_ms"], reverse=True)
        return slow_queries[:limit]

    async def get_query_performance_summary(self, time_window_hours: int = 1) -> Dict[str, Any]:
        """Get query performance summary for the specified time window."""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_queries = [q for q in self.query_metrics if q.timestamp >= cutoff_time]

        if not recent_queries:
            return {"message": "No queries found in the specified time window"}

        # Calculate statistics
        execution_times = [q.execution_time_ms for q in recent_queries]
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)

        # Calculate percentiles
        sorted_times = sorted(execution_times)
        p50 = sorted_times[len(sorted_times) // 2]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]

        # Count slow queries
        slow_count = sum(1 for q in recent_queries if q.is_slow)
        slow_rate = (slow_count / len(recent_queries)) * 100

        # Group by query type
        query_types = {}
        for query in recent_queries:
            query_type = self._classify_query(query.query_pattern)
            if query_type not in query_types:
                query_types[query_type] = {"count": 0, "total_time": 0, "slow_count": 0}

            query_types[query_type]["count"] += 1
            query_types[query_type]["total_time"] += query.execution_time_ms
            if query.is_slow:
                query_types[query_type]["slow_count"] += 1

        # Calculate averages for each type
        for qtype in query_types:
            count = query_types[qtype]["count"]
            query_types[qtype]["avg_time"] = query_types[qtype]["total_time"] / count
            query_types[qtype]["slow_rate"] = (query_types[qtype]["slow_count"] / count) * 100

        return {
            "time_window_hours": time_window_hours,
            "total_queries": len(recent_queries),
            "slow_queries": slow_count,
            "slow_rate_percent": round(slow_rate, 2),
            "timing": {
                "avg_ms": round(avg_time, 2),
                "min_ms": round(min_time, 2),
                "max_ms": round(max_time, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2)
            },
            "query_types": query_types
        }

    async def analyze_query_patterns(self) -> Dict[str, Any]:
        """Analyze query patterns to identify optimization opportunities."""
        if not self.query_metrics:
            return {"message": "No query data available for analysis"}

        # Group queries by pattern
        patterns = {}
        for query in self.query_metrics:
            pattern = query.query_pattern
            if pattern not in patterns:
                patterns[pattern] = {
                    "count": 0,
                    "total_time": 0,
                    "total_rows": 0,
                    "slow_count": 0,
                    "tables": set()
                }

            patterns[pattern]["count"] += 1
            patterns[pattern]["total_time"] += query.execution_time_ms
            patterns[pattern]["total_rows"] += query.rows_affected
            patterns[pattern]["tables"].update(query.tables_accessed)

            if query.is_slow:
                patterns[pattern]["slow_count"] += 1

        # Calculate statistics and identify optimization opportunities
        analysis = {
            "total_patterns": len(patterns),
            "optimization_opportunities": []
        }

        for pattern, stats in patterns.items():
            avg_time = stats["total_time"] / stats["count"]
            slow_rate = (stats["slow_count"] / stats["count"]) * 100

            # Identify optimization opportunities
            if avg_time > 500:  # Slow on average
                analysis["optimization_opportunities"].append({
                    "type": "slow_average",
                    "pattern": pattern[:200] + "..." if len(pattern) > 200 else pattern,
                    "avg_time_ms": round(avg_time, 2),
                    "execution_count": stats["count"],
                    "tables": list(stats["tables"]),
                    "recommendation": "Consider adding indexes or optimizing query structure"
                })

            if slow_rate > 20:  # High variance
                analysis["optimization_opportunities"].append({
                    "type": "high_variance",
                    "pattern": pattern[:200] + "..." if len(pattern) > 200 else pattern,
                    "slow_rate_percent": round(slow_rate, 2),
                    "execution_count": stats["count"],
                    "tables": list(stats["tables"]),
                    "recommendation": "Query performance is inconsistent - check for parameter sniffing or missing indexes"
                })

            if stats["count"] > 100 and avg_time > 100:  # Frequent and slow
                analysis["optimization_opportunities"].append({
                    "type": "frequent_slow",
                    "pattern": pattern[:200] + "..." if len(pattern) > 200 else pattern,
                    "avg_time_ms": round(avg_time, 2),
                    "execution_count": stats["count"],
                    "tables": list(stats["tables"]),
                    "recommendation": "High-frequency slow query - prioritize optimization"
                })

        # Sort opportunities by impact
        analysis["optimization_opportunities"].sort(
            key=lambda x: x["execution_count"] * x.get("avg_time_ms", 0),
            reverse=True
        )

        return analysis

    async def generate_database_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive database health report."""
        try:
            # Collect current metrics
            current_metrics = await self.collect_database_metrics()

            # Get query performance summary
            query_summary = await self.get_query_performance_summary()

            # Get recent slow queries
            slow_queries = await self.get_slow_queries(limit=10)

            # Analyze query patterns
            pattern_analysis = await self.analyze_query_patterns()

            # Calculate health score
            health_score = self._calculate_health_score(current_metrics, query_summary)

            # Generate recommendations
            recommendations = self._generate_health_recommendations(
                current_metrics, query_summary, pattern_analysis
            )

            report = {
                "generated_at": datetime.utcnow().isoformat(),
                "health_score": health_score,
                "status": "healthy" if health_score >= 80 else "warning" if health_score >= 60 else "critical",
                "current_metrics": {
                    "connections": {
                        "active": current_metrics.active_connections,
                        "idle": current_metrics.idle_connections,
                        "total": current_metrics.total_connections
                    },
                    "performance": {
                        "queries_per_second": round(current_metrics.queries_per_second, 2),
                        "avg_query_time_ms": round(current_metrics.avg_query_time_ms, 2),
                        "slow_queries_per_second": round(current_metrics.slow_queries_per_second, 2)
                    },
                    "resources": {
                        "cache_hit_ratio": round(current_metrics.cache_hit_ratio * 100, 2),
                        "index_usage_ratio": round(current_metrics.index_usage_ratio * 100, 2),
                        "table_locks": current_metrics.table_locks,
                        "deadlocks": current_metrics.deadlocks
                    },
                    "storage": {
                        "database_size_mb": round(current_metrics.database_size_mb, 2),
                        "table_count": len(current_metrics.table_sizes)
                    }
                },
                "query_analysis": query_summary,
                "slow_queries_sample": slow_queries[:5],  # Top 5 slowest queries
                "pattern_analysis": pattern_analysis,
                "recommendations": recommendations,
                "alerts": self._generate_health_alerts(current_metrics, query_summary)
            }

            return report

        except Exception as e:
            self.logger.error(f"Failed to generate database health report: {e}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }

    def _calculate_health_score(self, metrics: DatabaseMetrics, query_summary: Dict[str, Any]) -> float:
        """Calculate overall database health score (0-100)."""
        score = 100.0

        # Deduct for high slow query rate
        if "slow_rate_percent" in query_summary:
            slow_rate = query_summary["slow_rate_percent"]
            if slow_rate > 10:
                score -= 30
            elif slow_rate > 5:
                score -= 15
            elif slow_rate > 2:
                score -= 5

        # Deduct for low cache hit ratio
        if metrics.cache_hit_ratio < 0.90:
            score -= 20
        elif metrics.cache_hit_ratio < 0.95:
            score -= 10

        # Deduct for high number of locks
        if metrics.table_locks > 50:
            score -= 15
        elif metrics.table_locks > 20:
            score -= 5

        # Deduct for deadlocks
        if metrics.deadlocks > 0:
            score -= 25

        # Deduct for high connection count
        if metrics.active_connections > 80:
            score -= 20
        elif metrics.active_connections > 50:
            score -= 10

        return max(0, score)

    def _generate_health_recommendations(
        self,
        metrics: DatabaseMetrics,
        query_summary: Dict[str, Any],
        pattern_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate database health recommendations."""
        recommendations = []

        # Cache recommendations
        if metrics.cache_hit_ratio < 0.95:
            recommendations.append(
                f"Cache hit ratio is {metrics.cache_hit_ratio:.1%} - consider increasing shared_buffers or "
                "optimizing queries to reduce disk I/O"
            )

        # Query performance recommendations
        if "slow_rate_percent" in query_summary and query_summary["slow_rate_percent"] > 5:
            recommendations.append(
                f"Slow query rate is {query_summary['slow_rate_percent']:.1f}% - review and optimize slow queries"
            )

        # Connection recommendations
        if metrics.active_connections > 50:
            recommendations.append(
                f"High number of active connections ({metrics.active_connections}) - consider using "
                "connection pooling or reducing connection lifetime"
            )

        # Lock recommendations
        if metrics.table_locks > 20:
            recommendations.append(
                f"High number of table locks ({metrics.table_locks}) - check for long-running transactions "
                "and optimize transaction boundaries"
            )

        if metrics.deadlocks > 0:
            recommendations.append(
                f"{metrics.deadlocks} deadlocks detected - review transaction ordering and consider "
                "adding appropriate indexes"
            )

        # Index usage recommendations
        if metrics.index_usage_ratio < 0.90:
            recommendations.append(
                f"Index usage ratio is {metrics.index_usage_ratio:.1%} - review index effectiveness "
                "and consider adding missing indexes"
            )

        # Pattern analysis recommendations
        if "optimization_opportunities" in pattern_analysis:
            opportunities = pattern_analysis["optimization_opportunities"][:3]  # Top 3
            for opp in opportunities:
                recommendations.append(f"Query optimization: {opp['recommendation']}")

        return recommendations

    def _generate_health_alerts(self, metrics: DatabaseMetrics, query_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate health alerts for critical issues."""
        alerts = []

        # Critical alerts
        if metrics.deadlocks > 0:
            alerts.append({
                "severity": "critical",
                "message": f"Database deadlocks detected: {metrics.deadlocks}",
                "recommendation": "Investigate deadlock sources immediately"
            })

        if "slow_rate_percent" in query_summary and query_summary["slow_rate_percent"] > 20:
            alerts.append({
                "severity": "critical",
                "message": f"Very high slow query rate: {query_summary['slow_rate_percent']:.1f}%",
                "recommendation": "Immediate query optimization required"
            })

        if metrics.active_connections > 80:
            alerts.append({
                "severity": "warning",
                "message": f"Very high connection count: {metrics.active_connections}",
                "recommendation": "Monitor for connection exhaustion"
            })

        if metrics.cache_hit_ratio < 0.85:
            alerts.append({
                "severity": "warning",
                "message": f"Low cache hit ratio: {metrics.cache_hit_ratio:.1%}",
                "recommendation": "Consider increasing buffer pool size"
            })

        return alerts

    def clear_metrics_history(self, older_than_hours: int = 24):
        """Clear metrics history older than specified hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

            # Clear query metrics
            self.query_metrics = [
                q for q in self.query_metrics
                if q.timestamp >= cutoff_time
            ]

            # Clear slow queries
            self.slow_queries = [
                q for q in self.slow_queries
                if q.timestamp >= cutoff_time
            ]

            self.logger.info(f"Cleared metrics history older than {older_than_hours} hours")

        except Exception as e:
            self.logger.error(f"Failed to clear metrics history: {e}")


# Singleton instance
database_performance_service = DatabasePerformanceService()