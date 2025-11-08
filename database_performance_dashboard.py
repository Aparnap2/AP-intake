#!/usr/bin/env python3
"""
Database Performance Dashboard for AP Intake & Validation System

This script provides real-time monitoring of database performance metrics
and can be used for ongoing database health monitoring.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import asyncpg

class DatabasePerformanceDashboard:
    """Real-time database performance monitoring dashboard."""

    def __init__(self, db_url: str = "postgresql://postgres:postgres@localhost:5432/ap_intake"):
        self.db_url = db_url
        self.metrics_history = []

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect current database performance metrics."""
        conn = await asyncpg.connect(self.db_url)

        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'connection_metrics': await self._get_connection_metrics(conn),
                'performance_metrics': await self._get_performance_metrics(conn),
                'size_metrics': await self._get_size_metrics(conn),
                'activity_metrics': await self._get_activity_metrics(conn),
                'index_metrics': await self._get_index_metrics(conn),
                'lock_metrics': await self._get_lock_metrics(conn)
            }

            return metrics

        finally:
            await conn.close()

    async def _get_connection_metrics(self, conn) -> Dict[str, Any]:
        """Get connection-related metrics."""
        try:
            # Active connections
            active_connections = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'active'
            """)

            # Total connections
            total_connections = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
            """)

            # Idle connections
            idle_connections = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'idle'
            """)

            return {
                'active_connections': active_connections,
                'total_connections': total_connections,
                'idle_connections': idle_connections,
                'connection_utilization_percent': (active_connections / total_connections * 100) if total_connections > 0 else 0
            }

        except Exception as e:
            return {'error': str(e)}

    async def _get_performance_metrics(self, conn) -> Dict[str, Any]:
        """Get performance-related metrics."""
        try:
            # Database statistics
            stats = await conn.fetchrow("""
                SELECT
                    xact_commit as transactions_committed,
                    xact_rollback as transactions_rolled_back,
                    blks_read as blocks_read,
                    blks_hit as blocks_hit,
                    tup_returned as tuples_returned,
                    tup_fetched as tuples_fetched,
                    tup_inserted as tuples_inserted,
                    tup_updated as tuples_updated,
                    tup_deleted as tuples_deleted
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            if stats:
                cache_hit_ratio = (stats['blocks_hit'] / (stats['blocks_hit'] + stats['blocks_read']) * 100) if (stats['blocks_hit'] + stats['blocks_read']) > 0 else 0

                return {
                    'transactions_committed': stats['transactions_committed'],
                    'transactions_rolled_back': stats['transactions_rolled_back'],
                    'cache_hit_ratio_percent': round(cache_hit_ratio, 2),
                    'tuples_returned': stats['tuples_returned'],
                    'tuples_fetched': stats['tuples_fetched'],
                    'tuples_inserted': stats['tuples_inserted'],
                    'tuples_updated': stats['tuples_updated'],
                    'tuples_deleted': stats['tuples_deleted']
                }
            else:
                return {'error': 'No database stats found'}

        except Exception as e:
            return {'error': str(e)}

    async def _get_size_metrics(self, conn) -> Dict[str, Any]:
        """Get database and table size metrics."""
        try:
            # Database size
            db_size = await conn.fetchval("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """)

            # Table sizes
            table_sizes = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """)

            return {
                'database_size': db_size,
                'largest_tables': [dict(table) for table in table_sizes]
            }

        except Exception as e:
            return {'error': str(e)}

    async def _get_activity_metrics(self, conn) -> Dict[str, Any]:
        """Get recent database activity metrics."""
        try:
            # Recent queries
            recent_queries = await conn.fetch("""
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows
                FROM pg_stat_statements
                ORDER BY total_exec_time DESC
                LIMIT 5
            """)

            # Slow queries (more than 1 second)
            slow_queries = await conn.fetch("""
                SELECT
                    query,
                    calls,
                    mean_exec_time,
                    total_exec_time
                FROM pg_stat_statements
                WHERE mean_exec_time > 1000
                ORDER BY mean_exec_time DESC
                LIMIT 5
            """)

            return {
                'top_queries_by_time': [dict(q) for q in recent_queries] if recent_queries else [],
                'slow_queries': [dict(q) for q in slow_queries] if slow_queries else []
            }

        except Exception as e:
            # pg_stat_statements might not be available
            return {'error': 'pg_stat_statements extension not available', 'details': str(e)}

    async def _get_index_metrics(self, conn) -> Dict[str, Any]:
        """Get index usage metrics."""
        try:
            # Index usage statistics
            index_stats = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                ORDER BY idx_scan DESC
                LIMIT 10
            """)

            # Unused indexes
            unused_indexes = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                ORDER BY pg_relation_size(indexrelid) DESC
            """)

            return {
                'most_used_indexes': [dict(idx) for idx in index_stats] if index_stats else [],
                'unused_indexes': [dict(idx) for idx in unused_indexes] if unused_indexes else [],
                'total_unused_count': len(unused_indexes) if unused_indexes else 0
            }

        except Exception as e:
            return {'error': str(e)}

    async def _get_lock_metrics(self, conn) -> Dict[str, Any]:
        """Get lock-related metrics."""
        try:
            # Current locks
            locks = await conn.fetch("""
                SELECT
                    locktype,
                    mode,
                    count(*) as lock_count
                FROM pg_locks
                GROUP BY locktype, mode
                ORDER BY lock_count DESC
            """)

            # Waiting locks
            waiting_locks = await conn.fetch("""
                SELECT count(*) as waiting_count
                FROM pg_locks
                WHERE granted = false
            """)

            return {
                'lock_distribution': [dict(lock) for lock in locks] if locks else [],
                'waiting_locks_count': waiting_locks[0]['waiting_count'] if waiting_locks else 0
            }

        except Exception as e:
            return {'error': str(e)}

    def display_dashboard(self, metrics: Dict[str, Any]):
        """Display a formatted dashboard of current metrics."""
        print("\n" + "=" * 80)
        print(f"📊 DATABASE PERFORMANCE DASHBOARD")
        print(f"🕐 Timestamp: {metrics['timestamp']}")
        print("=" * 80)

        # Connection Metrics
        conn_metrics = metrics.get('connection_metrics', {})
        if 'error' not in conn_metrics:
            print(f"\n🔌 CONNECTION METRICS:")
            print(f"   • Active Connections: {conn_metrics.get('active_connections', 0)}")
            print(f"   • Total Connections: {conn_metrics.get('total_connections', 0)}")
            print(f"   • Idle Connections: {conn_metrics.get('idle_connections', 0)}")
            print(f"   • Utilization: {conn_metrics.get('connection_utilization_percent', 0):.1f}%")

        # Performance Metrics
        perf_metrics = metrics.get('performance_metrics', {})
        if 'error' not in perf_metrics:
            print(f"\n⚡ PERFORMANCE METRICS:")
            print(f"   • Cache Hit Ratio: {perf_metrics.get('cache_hit_ratio_percent', 0):.2f}%")
            print(f"   • Transactions Committed: {perf_metrics.get('transactions_committed', 0)}")
            print(f"   • Transactions Rolled Back: {perf_metrics.get('transactions_rolled_back', 0)}")
            print(f"   • Tuples Returned: {perf_metrics.get('tuples_returned', 0)}")
            print(f"   • Tuples Inserted: {perf_metrics.get('tuples_inserted', 0)}")

        # Size Metrics
        size_metrics = metrics.get('size_metrics', {})
        if 'error' not in size_metrics:
            print(f"\n💾 SIZE METRICS:")
            print(f"   • Database Size: {size_metrics.get('database_size', 'Unknown')}")

            largest_tables = size_metrics.get('largest_tables', [])[:3]
            if largest_tables:
                print(f"   • Largest Tables:")
                for table in largest_tables:
                    print(f"     - {table['tablename']}: {table['size']}")

        # Index Metrics
        index_metrics = metrics.get('index_metrics', {})
        if 'error' not in index_metrics:
            print(f"\n📊 INDEX METRICS:")
            unused_count = index_metrics.get('total_unused_count', 0)
            print(f"   • Unused Indexes: {unused_count}")

            most_used = index_metrics.get('most_used_indexes', [])[:3]
            if most_used:
                print(f"   • Most Used Indexes:")
                for idx in most_used:
                    print(f"     - {idx['indexname']}: {idx['index_scans']} scans")

        # Lock Metrics
        lock_metrics = metrics.get('lock_metrics', {})
        if 'error' not in lock_metrics:
            print(f"\n🔒 LOCK METRICS:")
            print(f"   • Waiting Locks: {lock_metrics.get('waiting_locks_count', 0)}")

            lock_dist = lock_metrics.get('lock_distribution', [])
            if lock_dist:
                print(f"   • Lock Distribution:")
                for lock in lock_dist[:3]:
                    print(f"     - {lock['locktype']} ({lock['mode']}): {lock['lock_count']}")

        # Activity Metrics
        activity_metrics = metrics.get('activity_metrics', {})
        if 'error' not in activity_metrics and 'error' not in activity_metrics:
            slow_queries = activity_metrics.get('slow_queries', [])
            if slow_queries:
                print(f"\n⚠️ SLOW QUERIES:")
                for query in slow_queries[:3]:
                    print(f"   • Avg: {query['mean_exec_time']:.2f}ms - {query['query'][:50]}...")

        print("\n" + "=" * 80)

    async def monitor_continuous(self, interval: int = 30, duration: int = 300):
        """Monitor database continuously for specified duration."""
        print(f"🚀 Starting continuous database monitoring...")
        print(f"📊 Interval: {interval} seconds")
        print(f"⏱️  Duration: {duration} seconds")
        print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        start_time = time.time()
        iterations = 0

        while time.time() - start_time < duration:
            try:
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)

                self.display_dashboard(metrics)

                iterations += 1
                remaining_time = duration - (time.time() - start_time)

                if remaining_time > interval:
                    print(f"\n⏳ Next update in {interval} seconds... (Remaining: {int(remaining_time)}s)")
                    await asyncio.sleep(interval)
                else:
                    break

            except KeyboardInterrupt:
                print("\n⏹️  Monitoring stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Error during monitoring: {e}")
                await asyncio.sleep(interval)

        # Summary
        total_time = time.time() - start_time
        print(f"\n📈 MONITORING SUMMARY:")
        print(f"   • Total Duration: {total_time:.1f} seconds")
        print(f"   • Data Points Collected: {iterations}")
        print(f"   • Average Interval: {total_time/iterations:.1f} seconds")
        print(f"   • Monitoring Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async def save_metrics_history(self, filename: str = None):
        """Save collected metrics history to file."""
        if not filename:
            filename = f"db_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(self.metrics_history, f, indent=2, default=str)

        print(f"📄 Metrics history saved to: {filename}")

# Main execution
async def main():
    """Run the database performance dashboard."""
    dashboard = DatabasePerformanceDashboard()

    # Single snapshot
    print("📊 Collecting current database metrics...")
    metrics = await dashboard.collect_metrics()
    dashboard.display_dashboard(metrics)

    # Ask user if they want continuous monitoring
    print("\n" + "="*50)
    print("For continuous monitoring, run:")
    print("uv run python database_performance_dashboard.py --monitor")
    print("="*50)

async def monitor_main():
    """Run continuous monitoring."""
    dashboard = DatabasePerformanceDashboard()
    await dashboard.monitor_continuous(interval=30, duration=300)
    await dashboard.save_metrics_history()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        asyncio.run(monitor_main())
    else:
        asyncio.run(main())