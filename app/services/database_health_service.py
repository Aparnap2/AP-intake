"""
Database Health Monitoring Service for PostgreSQL performance tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DatabaseHealthService:
    """Service for monitoring database health and performance metrics."""

    def __init__(self):
        self.session_factory = AsyncSessionLocal

    async def get_connection_pool_status(self) -> Dict[str, Any]:
        """Get current connection pool status."""
        try:
            engine = self.session_factory.kw['bind']
            pool = engine.pool

            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "total_connections": pool.size() + pool.overflow(),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_database_metrics(self) -> Dict[str, Any]:
        """Get comprehensive database performance metrics."""
        try:
            async with self.session_factory() as session:
                # Connection statistics
                conn_result = await session.execute(text("""
                    SELECT
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections,
                        count(*) FILTER (WHERE wait_event_type = 'Lock') as blocked_connections,
                        count(*) FILTER (WHERE query != '<IDLE>') as active_queries
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """))
                conn_stats = conn_result.fetchone()._asdict()

                # Database size metrics
                size_result = await session.execute(text("""
                    SELECT
                        pg_size_pretty(pg_database_size(current_database())) as database_size,
                        pg_size_pretty(sum(pg_relation_size(schemaname||'.'||tablename))) as total_table_size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                """))
                size_stats = size_result.fetchone()._asdict()

                # Cache performance
                cache_result = await session.execute(text("""
                    SELECT
                        sum(heap_blks_read) as heap_blocks_read,
                        sum(heap_blks_hit) as heap_blocks_hit,
                        sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100 as cache_hit_ratio
                    FROM pg_statio_user_tables
                """))
                cache_stats = cache_result.fetchone()._asdict()

                # Lock monitoring
                lock_result = await session.execute(text("""
                    SELECT
                        count(*) as blocked_queries,
                        mode,
                        count(*) FILTER (WHERE wait_event IS NOT NULL) as waiting_queries
                    FROM pg_locks
                    JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
                    WHERE NOT granted
                    GROUP BY mode
                """))
                lock_stats = [row._asdict() for row in lock_result.fetchall()]

                return {
                    "connections": conn_stats,
                    "database_size": size_stats,
                    "cache_performance": cache_stats,
                    "locks": lock_stats,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting database metrics: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slow queries from pg_stat_statements."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(text("""
                    SELECT
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        rows,
                        100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                    FROM pg_stat_statements
                    WHERE mean_exec_time > 100
                    ORDER BY mean_exec_time DESC
                    LIMIT :limit
                """), {"limit": limit})

                return [row._asdict() for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting slow queries: {e}")
            return [{"error": str(e)}]

    async def get_table_statistics(self) -> Dict[str, Any]:
        """Get table-level performance statistics."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_tuples,
                        n_dead_tup as dead_tuples,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                """))

                tables = [row._asdict() for row in result.fetchall()]

                # Table sizes
                size_result = await session.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """))

                sizes = {row.tablename: row._asdict() for row in size_result.fetchall()}

                # Merge statistics
                for table in tables:
                    table.update(sizes.get(table['tablename'], {}))

                return {
                    "tables": tables,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting table statistics: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_index_usage(self) -> List[Dict[str, Any]]:
        """Get index usage statistics."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_tup_read as tuples_read,
                        idx_tup_fetch as tuples_fetched,
                        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                    FROM pg_stat_user_indexes
                    ORDER BY idx_tup_read DESC
                """))

                return [row._asdict() for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting index usage: {e}")
            return [{"error": str(e)}]

    async def check_database_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check and return health score."""
        try:
            metrics = await self.get_database_metrics()
            pool_status = await self.get_connection_pool_status()

            health_score = 100
            issues = []

            # Check connection pool utilization
            if 'total_connections' in pool_status and 'pool_size' in pool_status:
                utilization = (pool_status['checked_out'] / pool_status['total_connections']) * 100
                if utilization > 80:
                    health_score -= 20
                    issues.append(f"High connection pool utilization: {utilization:.1f}%")
                elif utilization > 60:
                    health_score -= 10
                    issues.append(f"Moderate connection pool utilization: {utilization:.1f}%")

            # Check blocked connections
            if 'connections' in metrics:
                blocked = metrics['connections'].get('blocked_connections', 0)
                if blocked > 5:
                    health_score -= 15
                    issues.append(f"High number of blocked connections: {blocked}")
                elif blocked > 0:
                    health_score -= 5
                    issues.append(f"Some blocked connections detected: {blocked}")

            # Check cache hit ratio
            if 'cache_performance' in metrics:
                hit_ratio = metrics['cache_performance'].get('cache_hit_ratio', 0)
                if hit_ratio < 90:
                    health_score -= 15
                    issues.append(f"Low cache hit ratio: {hit_ratio:.1f}%")
                elif hit_ratio < 95:
                    health_score -= 5
                    issues.append(f"Moderate cache hit ratio: {hit_ratio:.1f}%")

            # Check for locks
            if 'locks' in metrics and metrics['locks']:
                total_blocked = sum(lock.get('waiting_queries', 0) for lock in metrics['locks'])
                if total_blocked > 0:
                    health_score -= 10
                    issues.append(f"Lock contention detected: {total_blocked} waiting queries")

            # Determine health status
            if health_score >= 90:
                status = "excellent"
            elif health_score >= 75:
                status = "good"
            elif health_score >= 60:
                status = "warning"
            else:
                status = "critical"

            return {
                "health_score": max(0, health_score),
                "status": status,
                "issues": issues,
                "metrics": metrics,
                "pool_status": pool_status,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            return {
                "health_score": 0,
                "status": "error",
                "issues": [f"Health check failed: {str(e)}"],
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over time."""
        try:
            async with self.session_factory() as session:
                # Connection trends (if pg_stat_statements history is available)
                result = await session.execute(text("""
                    SELECT
                        date_trunc('hour', now() - n * interval '1 hour') as hour,
                        0 as avg_connections
                    FROM generate_series(0, :hours - 1) as n
                """), {"hours": hours})

                # This is a placeholder - real implementation would require
                # a metrics collection system like Prometheus or custom logging

                return {
                    "trends": {
                        "connection_trends": [row._asdict() for row in result.fetchall()],
                        "note": "Real trends require metrics collection system"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


# Database performance monitoring task
async def monitor_database_health():
    """Background task to monitor database health."""
    health_service = DatabaseHealthService()

    while True:
        try:
            health_status = await health_service.check_database_health()

            if health_status['status'] in ['warning', 'critical']:
                logger.warning(f"Database health issue detected: {health_status}")

            # Log metrics every 5 minutes
            logger.info(f"Database health score: {health_status['health_score']}")

            await asyncio.sleep(300)  # 5 minutes

        except Exception as e:
            logger.error(f"Error in database monitoring: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error