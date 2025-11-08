#!/usr/bin/env python3
"""
Database Performance Testing for AP Intake & Validation System

This module provides comprehensive database performance testing:
- Connection pool stress testing
- Query performance under concurrent load
- Transaction throughput testing
- Index performance analysis
- Database resource monitoring
- Performance regression detection
"""

import asyncio
import json
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.pool
import pytest
import psutil
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, select, update, delete, insert
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.db.session import async_engine, AsyncSessionLocal
from app.models.invoice import Invoice, InvoiceStatus, InvoiceExtraction, Validation
from tests.factories import InvoiceFactory, ExtractionDataFactory

logger = logging.getLogger(__name__)


@dataclass
class DatabaseMetrics:
    """Container for database performance metrics."""

    query_type: str
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_time: float = 0.0
    query_times: List[float] = field(default_factory=list)
    connection_errors: List[str] = field(default_factory=list)
    query_errors: List[str] = field(default_factory=list)

    # Connection pool metrics
    pool_size_at_start: int = 0
    pool_size_at_end: int = 0
    active_connections: int = 0
    idle_connections: int = 0

    # Resource usage
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate query success rate."""
        if self.total_queries == 0:
            return 0.0
        return (self.successful_queries / self.total_queries) * 100

    @property
    def queries_per_second(self) -> float:
        """Calculate queries per second."""
        if self.total_time == 0:
            return 0.0
        return self.total_queries / self.total_time

    @property
    def average_query_time(self) -> float:
        """Calculate average query time in milliseconds."""
        if not self.query_times:
            return 0.0
        return statistics.mean(self.query_times)

    @property
    def median_query_time(self) -> float:
        """Calculate median query time in milliseconds."""
        if not self.query_times:
            return 0.0
        return statistics.median(self.query_times)

    @property
    def p95_query_time(self) -> float:
        """Calculate 95th percentile query time."""
        if not self.query_times:
            return 0.0
        return statistics.quantiles(self.query_times, n=20)[18]

    @property
    def p99_query_time(self) -> float:
        """Calculate 99th percentile query time."""
        if not self.query_times:
            return 0.0
        return statistics.quantiles(self.query_times, n=100)[98]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query_type": self.query_type,
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "success_rate": self.success_rate,
            "queries_per_second": self.queries_per_second,
            "average_query_time": self.average_query_time,
            "median_query_time": self.median_query_time,
            "p95_query_time": self.p95_query_time,
            "p99_query_time": self.p99_query_time,
            "total_time": self.total_time,
            "pool_size_change": self.pool_size_at_end - self.pool_size_at_start,
            "connection_errors": len(self.connection_errors),
            "query_errors": len(self.query_errors)
        }


class DatabasePerformanceTester:
    """Main database performance testing class."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL
        self.test_results: List[DatabaseMetrics] = []

    async def test_connection_pool_performance(
        self,
        max_connections: int = 50,
        concurrent_workers: int = 20,
        operations_per_worker: int = 50
    ) -> DatabaseMetrics:
        """Test database connection pool under concurrent load."""
        metrics = DatabaseMetrics(query_type="connection_pool")

        logger.info(f"Testing connection pool with {concurrent_workers} workers, {operations_per_worker} ops each")

        # Get initial pool state
        pool = async_engine.pool
        metrics.pool_size_at_start = pool.size()

        start_time = time.perf_counter()

        async def pool_worker(worker_id: int):
            """Worker that performs database operations."""
            worker_session = async_sessionmaker(async_engine, class_=AsyncSession)

            for op_id in range(operations_per_worker):
                query_start = time.perf_counter()

                try:
                    async with worker_session() as session:
                        # Simple SELECT query
                        result = await session.execute(
                            text("SELECT 1 as test")
                        )
                        await session.commit()

                    query_end = time.perf_counter()
                    query_time = (query_end - query_start) * 1000

                    metrics.total_queries += 1
                    metrics.successful_queries += 1
                    metrics.query_times.append(query_time)

                except Exception as e:
                    query_end = time.perf_counter()
                    metrics.total_queries += 1
                    metrics.failed_queries += 1
                    metrics.query_errors.append(f"Worker {worker_id}, Op {op_id}: {str(e)}")

                # Small delay between operations
                await asyncio.sleep(0.01)

        # Run concurrent workers
        workers = [
            asyncio.create_task(pool_worker(i))
            for i in range(concurrent_workers)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        end_time = time.perf_counter()
        metrics.total_time = end_time - start_time

        # Get final pool state
        metrics.pool_size_at_end = pool.size()

        self.test_results.append(metrics)
        return metrics

    async def test_select_performance(
        self,
        concurrent_sessions: int = 15,
        queries_per_session: int = 100,
        query_complexity: str = "simple"
    ) -> DatabaseMetrics:
        """Test SELECT query performance under load."""
        metrics = DatabaseMetrics(query_type=f"select_{query_complexity}")

        # Define queries based on complexity
        queries = {
            "simple": "SELECT COUNT(*) FROM invoices WHERE status = 'processed'",
            "moderate": """
                SELECT i.id, i.status, i.created_at, ie.confidence_json
                FROM invoices i
                LEFT JOIN invoice_extractions ie ON i.id = ie.invoice_id
                WHERE i.status IN ('processed', 'review')
                ORDER BY i.created_at DESC
                LIMIT 10
            """,
            "complex": """
                SELECT
                    i.status,
                    COUNT(*) as invoice_count,
                    AVG(EXTRACT(EPOCH FROM (NOW() - i.created_at))/3600) as avg_age_hours,
                    COUNT(DISTINCT i.vendor_id) as unique_vendors
                FROM invoices i
                LEFT JOIN invoice_extractions ie ON i.id = ie.invoice_id
                LEFT JOIN validations v ON i.id = v.invoice_id
                WHERE i.created_at > NOW() - INTERVAL '24 hours'
                GROUP BY i.status
                HAVING COUNT(*) > 0
                ORDER BY invoice_count DESC
            """
        }

        query = queries.get(query_complexity, queries["simple"])

        logger.info(f"Testing {query_complexity} SELECT with {concurrent_sessions} sessions")

        start_time = time.perf_counter()

        async def select_worker(session_id: int):
            """Worker that performs SELECT queries."""
            async with AsyncSessionLocal() as session:
                for query_id in range(queries_per_session):
                    query_start = time.perf_counter()

                    try:
                        result = await session.execute(text(query))
                        rows = result.fetchall()

                        query_end = time.perf_counter()
                        query_time = (query_end - query_start) * 1000

                        metrics.total_queries += 1
                        metrics.successful_queries += 1
                        metrics.query_times.append(query_time)

                    except Exception as e:
                        query_end = time.perf_counter()
                        metrics.total_queries += 1
                        metrics.failed_queries += 1
                        metrics.query_errors.append(f"Session {session_id}, Query {query_id}: {str(e)}")

                    # Delay between queries
                    await asyncio.sleep(0.02)

        # Run concurrent sessions
        workers = [
            asyncio.create_task(select_worker(i))
            for i in range(concurrent_sessions)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        end_time = time.perf_counter()
        metrics.total_time = end_time - start_time

        self.test_results.append(metrics)
        return metrics

    async def test_insert_performance(
        self,
        concurrent_sessions: int = 10,
        inserts_per_session: int = 50,
        batch_size: int = 1
    ) -> DatabaseMetrics:
        """Test INSERT performance under load."""
        metrics = DatabaseMetrics(query_type=f"insert_batch_{batch_size}")

        logger.info(f"Testing INSERT performance with {concurrent_sessions} sessions, batch size {batch_size}")

        start_time = time.perf_counter()

        async def insert_worker(session_id: int):
            """Worker that performs INSERT operations."""
            async with AsyncSessionLocal() as session:
                for batch_start in range(0, inserts_per_session, batch_size):
                    batch_end = min(batch_start + batch_size, inserts_per_session)
                    query_start = time.perf_counter()

                    try:
                        # Prepare batch insert data
                        invoices_data = []
                        for i in range(batch_start, batch_end):
                            invoices_data.append({
                                'id': f"test-invoice-{session_id}-{i}",
                                'vendor_id': f"test-vendor-{session_id}",
                                'status': 'received',
                                'workflow_state': 'receive',
                                'created_at': 'NOW()'
                            })

                        # Perform batch insert
                        if batch_size == 1:
                            # Single insert
                            await session.execute(text("""
                                INSERT INTO invoices (id, vendor_id, status, workflow_state, created_at)
                                VALUES (:id, :vendor_id, :status, :workflow_state, NOW())
                            """), invoices_data[0])
                        else:
                            # Batch insert
                            values = ", ".join([
                                f"('{data['id']}', '{data['vendor_id']}', '{data['status']}', '{data['workflow_state']}', NOW())"
                                for data in invoices_data
                            ])
                            await session.execute(text(f"""
                                INSERT INTO invoices (id, vendor_id, status, workflow_state, created_at)
                                VALUES {values}
                            """))

                        await session.commit()

                        query_end = time.perf_counter()
                        query_time = (query_end - query_start) * 1000

                        metrics.total_queries += (batch_end - batch_start)
                        metrics.successful_queries += (batch_end - batch_start)
                        metrics.query_times.append(query_time)

                    except Exception as e:
                        query_end = time.perf_counter()
                        metrics.total_queries += (batch_end - batch_start)
                        metrics.failed_queries += (batch_end - batch_start)
                        metrics.query_errors.append(f"Session {session_id}, Batch {batch_start}: {str(e)}")
                        await session.rollback()

                    # Delay between batches
                    await asyncio.sleep(0.05)

        # Run concurrent sessions
        workers = [
            asyncio.create_task(insert_worker(i))
            for i in range(concurrent_sessions)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        end_time = time.perf_counter()
        metrics.total_time = end_time - start_time

        self.test_results.append(metrics)
        return metrics

    async def test_transaction_performance(
        self,
        concurrent_sessions: int = 15,
        transactions_per_session: int = 30,
        operations_per_transaction: int = 5
    ) -> DatabaseMetrics:
        """Test transaction performance under load."""
        metrics = DatabaseMetrics(query_type="transaction")

        logger.info(f"Testing transaction performance with {concurrent_sessions} sessions")

        start_time = time.perf_counter()

        async def transaction_worker(session_id: int):
            """Worker that performs transactions."""
            async with AsyncSessionLocal() as session:
                for tx_id in range(transactions_per_session):
                    tx_start = time.perf_counter()

                    try:
                        # Begin transaction
                        async with session.begin():
                            # Create invoice
                            invoice_id = f"tx-test-{session_id}-{tx_id}"
                            await session.execute(text("""
                                INSERT INTO invoices (id, vendor_id, status, workflow_state, created_at)
                                VALUES (:id, :vendor_id, :status, :workflow_state, NOW())
                            """), {
                                'id': invoice_id,
                                'vendor_id': f"tx-vendor-{session_id}",
                                'status': 'received',
                                'workflow_state': 'receive'
                            })

                            # Create extraction
                            await session.execute(text("""
                                INSERT INTO invoice_extractions (invoice_id, raw_data, confidence_json, created_at)
                                VALUES (:invoice_id, :raw_data, :confidence_json, NOW())
                            """), {
                                'invoice_id': invoice_id,
                                'raw_data': '{"test": "data"}',
                                'confidence_json': '{"overall": 0.95}'
                            })

                            # Create validation
                            await session.execute(text("""
                                INSERT INTO validations (invoice_id, passed, validation_results, created_at)
                                VALUES (:invoice_id, :passed, :validation_results, NOW())
                            """), {
                                'invoice_id': invoice_id,
                                'passed': True,
                                'validation_results': '{"valid": true}'
                            })

                            # Read back the data
                            result = await session.execute(text("""
                                SELECT i.id, ie.confidence_json, v.passed
                                FROM invoices i
                                LEFT JOIN invoice_extractions ie ON i.id = ie.invoice_id
                                LEFT JOIN validations v ON i.id = v.invoice_id
                                WHERE i.id = :invoice_id
                            """), {'invoice_id': invoice_id})

                            rows = result.fetchall()
                            if not rows:
                                raise Exception("Failed to read back inserted data")

                        tx_end = time.perf_counter()
                        tx_time = (tx_end - tx_start) * 1000

                        metrics.total_queries += operations_per_transaction
                        metrics.successful_queries += operations_per_transaction
                        metrics.query_times.append(tx_time)

                    except Exception as e:
                        tx_end = time.perf_counter()
                        metrics.total_queries += operations_per_transaction
                        metrics.failed_queries += operations_per_transaction
                        metrics.query_errors.append(f"Session {session_id}, TX {tx_id}: {str(e)}")

                    # Delay between transactions
                    await asyncio.sleep(0.1)

        # Run concurrent sessions
        workers = [
            asyncio.create_task(transaction_worker(i))
            for i in range(concurrent_sessions)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        end_time = time.perf_counter()
        metrics.total_time = end_time - start_time

        self.test_results.append(metrics)
        return metrics

    async def test_mixed_workload_performance(
        self,
        concurrent_sessions: int = 20,
        operations_per_session: int = 100,
        operation_weights: Optional[Dict[str, float]] = None
    ) -> DatabaseMetrics:
        """Test mixed database workload performance."""
        metrics = DatabaseMetrics(query_type="mixed_workload")

        if operation_weights is None:
            operation_weights = {
                'select': 0.6,
                'insert': 0.2,
                'update': 0.15,
                'delete': 0.05
            }

        logger.info(f"Testing mixed workload with {concurrent_sessions} sessions")

        start_time = time.perf_counter()

        async def mixed_worker(session_id: int):
            """Worker that performs mixed database operations."""
            import random

            async with AsyncSessionLocal() as session:
                for op_id in range(operations_per_session):
                    # Choose operation based on weights
                    operation = random.choices(
                        list(operation_weights.keys()),
                        weights=list(operation_weights.values())
                    )[0]

                    op_start = time.perf_counter()

                    try:
                        if operation == 'select':
                            # SELECT operation
                            result = await session.execute(text("""
                                SELECT COUNT(*) FROM invoices
                                WHERE created_at > NOW() - INTERVAL '1 hour'
                            """))
                            result.fetchone()

                        elif operation == 'insert':
                            # INSERT operation
                            invoice_id = f"mixed-{session_id}-{op_id}"
                            await session.execute(text("""
                                INSERT INTO invoices (id, vendor_id, status, workflow_state, created_at)
                                VALUES (:id, :vendor_id, :status, :workflow_state, NOW())
                            """), {
                                'id': invoice_id,
                                'vendor_id': f"mixed-vendor-{session_id}",
                                'status': 'received',
                                'workflow_state': 'receive'
                            })

                        elif operation == 'update':
                            # UPDATE operation
                            await session.execute(text("""
                                UPDATE invoices
                                SET status = 'processed'
                                WHERE status = 'received'
                                AND id IN (
                                    SELECT id FROM invoices
                                    WHERE status = 'received'
                                    LIMIT 1
                                )
                            """))

                        elif operation == 'delete':
                            # DELETE operation (clean up test data)
                            await session.execute(text("""
                                DELETE FROM invoices
                                WHERE id LIKE 'mixed-%'
                                LIMIT 1
                            """))

                        await session.commit()

                        op_end = time.perf_counter()
                        op_time = (op_end - op_start) * 1000

                        metrics.total_queries += 1
                        metrics.successful_queries += 1
                        metrics.query_times.append(op_time)

                    except Exception as e:
                        op_end = time.perf_counter()
                        metrics.total_queries += 1
                        metrics.failed_queries += 1
                        metrics.query_errors.append(f"Session {session_id}, Op {op_id} ({operation}): {str(e)}")
                        await session.rollback()

                    # Delay between operations
                    await asyncio.sleep(0.03)

        # Run concurrent sessions
        workers = [
            asyncio.create_task(mixed_worker(i))
            for i in range(concurrent_sessions)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        end_time = time.perf_counter()
        metrics.total_time = end_time - start_time

        self.test_results.append(metrics)
        return metrics

    async def test_index_performance(self) -> Dict[str, DatabaseMetrics]:
        """Test performance with and without indexes."""
        results = {}

        # Test queries that would benefit from indexes
        test_queries = [
            {
                'name': 'status_filter',
                'query': "SELECT * FROM invoices WHERE status = 'processed' ORDER BY created_at DESC LIMIT 50"
            },
            {
                'name': 'vendor_filter',
                'query': "SELECT COUNT(*) FROM invoices WHERE vendor_id = 'test-vendor-123'"
            },
            {
                'name': 'date_range',
                'query': "SELECT * FROM invoices WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at"
            },
            {
                'name': 'complex_join',
                'query': """
                    SELECT i.id, ie.confidence_json, v.passed
                    FROM invoices i
                    JOIN invoice_extractions ie ON i.id = ie.invoice_id
                    JOIN validations v ON i.id = v.invoice_id
                    WHERE i.status = 'processed'
                    ORDER BY i.created_at DESC
                    LIMIT 25
                """
            }
        ]

        for query_info in test_queries:
            logger.info(f"Testing index performance for {query_info['name']}")

            metrics = DatabaseMetrics(query_type=f"index_{query_info['name']}")

            start_time = time.perf_counter()

            async def index_query_worker():
                """Worker that executes the test query repeatedly."""
                async with AsyncSessionLocal() as session:
                    for i in range(50):
                        query_start = time.perf_counter()

                        try:
                            result = await session.execute(text(query_info['query']))
                            rows = result.fetchall()

                            query_end = time.perf_counter()
                            query_time = (query_end - query_start) * 1000

                            metrics.total_queries += 1
                            metrics.successful_queries += 1
                            metrics.query_times.append(query_time)

                        except Exception as e:
                            query_end = time.perf_counter()
                            metrics.total_queries += 1
                            metrics.failed_queries += 1
                            metrics.query_errors.append(f"Query {i}: {str(e)}")

                        await asyncio.sleep(0.02)

            # Run multiple workers for the query
            workers = [
                asyncio.create_task(index_query_worker())
                for _ in range(5)
            ]

            await asyncio.gather(*workers, return_exceptions=True)

            end_time = time.perf_counter()
            metrics.total_time = end_time - start_time

            results[query_info['name']] = metrics
            self.test_results.append(metrics)

        return results

    async def test_database_stress(
        self,
        max_connections: int = 100,
        test_duration_seconds: int = 60
    ) -> DatabaseMetrics:
        """Stress test database with maximum concurrent connections."""
        metrics = DatabaseMetrics(query_type="stress_test")

        logger.info(f"Running database stress test with {max_connections} connections for {test_duration_seconds}s")

        start_time = time.perf_counter()
        end_time = start_time + test_duration_seconds

        async def stress_worker(worker_id: int):
            """Worker that runs continuously for the stress test duration."""
            query_count = 0

            while time.perf_counter() < end_time:
                query_start = time.perf_counter()

                try:
                    async with AsyncSessionLocal() as session:
                        # Mix of operations
                        if query_count % 4 == 0:
                            # SELECT
                            result = await session.execute(text("SELECT COUNT(*) FROM invoices"))
                        elif query_count % 4 == 1:
                            # Complex SELECT
                            result = await session.execute(text("""
                                SELECT status, COUNT(*) FROM invoices
                                GROUP BY status ORDER BY COUNT(*) DESC
                            """))
                        elif query_count % 4 == 2:
                            # INSERT (with cleanup)
                            test_id = f"stress-{worker_id}-{query_count}"
                            await session.execute(text("""
                                INSERT INTO invoices (id, vendor_id, status, workflow_state, created_at)
                                VALUES (:id, :vendor_id, :status, :workflow_state, NOW())
                                ON CONFLICT (id) DO NOTHING
                            """), {
                                'id': test_id,
                                'vendor_id': f"stress-vendor-{worker_id}",
                                'status': 'received',
                                'workflow_state': 'receive'
                            })
                        else:
                            # UPDATE
                            await session.execute(text("""
                                UPDATE invoices
                                SET status = CASE
                                    WHEN status = 'received' THEN 'processed'
                                    WHEN status = 'processed' THEN 'review'
                                    ELSE 'received'
                                END
                                WHERE id IN (
                                    SELECT id FROM invoices
                                    WHERE id LIKE 'stress-%'
                                    LIMIT 5
                                )
                            """))

                        await session.commit()

                    query_end = time.perf_counter()
                    query_time = (query_end - query_start) * 1000

                    metrics.total_queries += 1
                    metrics.successful_queries += 1
                    metrics.query_times.append(query_time)

                except Exception as e:
                    query_end = time.perf_counter()
                    metrics.total_queries += 1
                    metrics.failed_queries += 1
                    metrics.query_errors.append(f"Worker {worker_id}, Query {query_count}: {str(e)}")

                query_count += 1
                await asyncio.sleep(0.01)

        # Start stress workers
        workers = [
            asyncio.create_task(stress_worker(i))
            for i in range(max_connections)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        actual_end_time = time.perf_counter()
        metrics.total_time = actual_end_time - start_time

        self.test_results.append(metrics)
        return metrics

    def generate_performance_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive database performance report."""
        if not self.test_results:
            return "No test results available"

        report = []
        report.append("# Database Performance Test Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total test scenarios: {len(self.test_results)}")
        report.append("")

        # Summary table
        report.append("## Test Summary")
        report.append("| Query Type | Queries | Success Rate | QPS | Avg Time | P95 Time |")
        report.append("|------------|---------|--------------|-----|----------|----------|")

        for metrics in self.test_results:
            report.append(
                f"| {metrics.query_type} | {metrics.total_queries} | "
                f"{metrics.success_rate:.1f}% | {metrics.queries_per_second:.1f} | "
                f"{metrics.average_query_time:.1f}ms | {metrics.p95_query_time:.1f}ms |"
            )

        report.append("")

        # Detailed results
        report.append("## Detailed Results")
        for metrics in self.test_results:
            report.append(f"### {metrics.query_type}")
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
class TestDatabasePerformance:
    """Database performance test suite."""

    @pytest.fixture
    def db_tester(self):
        """Get database performance tester."""
        return DatabasePerformanceTester()

    @pytest.mark.asyncio
    async def test_connection_pool_performance(self, db_tester: DatabasePerformanceTester):
        """Test database connection pool under load."""
        metrics = await db_tester.test_connection_pool_performance(
            max_connections=30,
            concurrent_workers=15,
            operations_per_worker=40
        )

        # Assertions
        assert metrics.total_queries == 600  # 15 workers * 40 operations
        assert metrics.success_rate >= 95, f"Connection pool success rate {metrics.success_rate:.1f}% below 95%"
        assert metrics.queries_per_second >= 50, f"Connection pool QPS {metrics.queries_per_second:.1f} below 50"
        assert metrics.average_query_time < 200, f"Average query time {metrics.average_query_time:.1f}ms exceeds 200ms"

        logger.info(f"Connection Pool Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_select_performance_simple(self, db_tester: DatabasePerformanceTester):
        """Test simple SELECT query performance."""
        metrics = await db_tester.test_select_performance(
            concurrent_sessions=10,
            queries_per_session=50,
            query_complexity="simple"
        )

        # Simple SELECT should be very fast
        assert metrics.total_queries == 500
        assert metrics.success_rate >= 99, f"Simple SELECT success rate {metrics.success_rate:.1f}% below 99%"
        assert metrics.average_query_time < 50, f"Simple SELECT average time {metrics.average_query_time:.1f}ms exceeds 50ms"
        assert metrics.p95_query_time < 100, f"Simple SELECT P95 time {metrics.p95_query_time:.1f}ms exceeds 100ms"

        logger.info(f"Simple SELECT Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_select_performance_complex(self, db_tester: DatabasePerformanceTester):
        """Test complex SELECT query performance."""
        metrics = await db_tester.test_select_performance(
            concurrent_sessions=8,
            queries_per_session=30,
            query_complexity="complex"
        )

        # Complex SELECT can be slower but should still be reasonable
        assert metrics.total_queries == 240
        assert metrics.success_rate >= 95, f"Complex SELECT success rate {metrics.success_rate:.1f}% below 95%"
        assert metrics.average_query_time < 500, f"Complex SELECT average time {metrics.average_query_time:.1f}ms exceeds 500ms"
        assert metrics.p95_query_time < 1000, f"Complex SELECT P95 time {metrics.p95_query_time:.1f}ms exceeds 1000ms"

        logger.info(f"Complex SELECT Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_insert_performance_single(self, db_tester: DatabasePerformanceTester):
        """Test single INSERT performance."""
        metrics = await db_tester.test_insert_performance(
            concurrent_sessions=8,
            inserts_per_session=25,
            batch_size=1
        )

        # Single INSERT performance
        assert metrics.total_queries == 200
        assert metrics.success_rate >= 95, f"Single INSERT success rate {metrics.success_rate:.1f}% below 95%"
        assert metrics.average_query_time < 100, f"Single INSERT average time {metrics.average_query_time:.1f}ms exceeds 100ms"

        logger.info(f"Single INSERT Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_insert_performance_batch(self, db_tester: DatabasePerformanceTester):
        """Test batch INSERT performance."""
        metrics = await db_tester.test_insert_performance(
            concurrent_sessions=6,
            inserts_per_session=30,
            batch_size=5
        )

        # Batch INSERT should be more efficient
        assert metrics.total_queries == 180
        assert metrics.success_rate >= 90, f"Batch INSERT success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.average_query_time < 200, f"Batch INSERT average time {metrics.average_query_time:.1f}ms exceeds 200ms"

        logger.info(f"Batch INSERT Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_transaction_performance(self, db_tester: DatabasePerformanceTester):
        """Test transaction performance."""
        metrics = await db_tester.test_transaction_performance(
            concurrent_sessions=10,
            transactions_per_session=20,
            operations_per_transaction=3
        )

        # Transaction performance
        assert metrics.total_queries == 600
        assert metrics.success_rate >= 90, f"Transaction success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.average_query_time < 300, f"Transaction average time {metrics.average_query_time:.1f}ms exceeds 300ms"

        logger.info(f"Transaction Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, db_tester: DatabasePerformanceTester):
        """Test mixed database workload performance."""
        metrics = await db_tester.test_mixed_workload_performance(
            concurrent_sessions=15,
            operations_per_session=60
        )

        # Mixed workload performance
        assert metrics.total_queries == 900
        assert metrics.success_rate >= 90, f"Mixed workload success rate {metrics.success_rate:.1f}% below 90%"
        assert metrics.queries_per_second >= 30, f"Mixed workload QPS {metrics.queries_per_second:.1f} below 30"

        logger.info(f"Mixed Workload Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_database_stress_test(self, db_tester: DatabasePerformanceTester):
        """Test database performance under stress."""
        metrics = await db_tester.test_database_stress(
            max_connections=50,
            test_duration_seconds=30
        )

        # Stress test performance (more lenient thresholds)
        assert metrics.total_queries > 1000, "Stress test should handle significant load"
        assert metrics.success_rate >= 80, f"Stress test success rate {metrics.success_rate:.1f}% below 80%"
        assert metrics.queries_per_second >= 20, f"Stress test QPS {metrics.queries_per_second:.1f} below 20"

        logger.info(f"Stress Test: {json.dumps(metrics.to_dict(), indent=2)}")

    @pytest.mark.asyncio
    async def test_index_performance(self, db_tester: DatabasePerformanceTester):
        """Test index performance impact."""
        index_results = await db_tester.test_index_performance()

        # All index tests should complete successfully
        for query_name, metrics in index_results.items():
            assert metrics.success_rate >= 95, f"Index test {query_name} success rate {metrics.success_rate:.1f}% below 95%"
            assert metrics.average_query_time < 1000, f"Index test {query_name} average time {metrics.average_query_time:.1f}ms exceeds 1000ms"

        logger.info(f"Index Performance Tests: {json.dumps({k: v.to_dict() for k, v in index_results.items()}, indent=2)}")

    def test_performance_report_generation(self, db_tester: DatabasePerformanceTester):
        """Test performance report generation."""
        # Mock some test results
        mock_metrics = DatabaseMetrics(query_type="test")
        mock_metrics.total_queries = 1000
        mock_metrics.successful_queries = 950
        mock_metrics.query_times = [10, 20, 30, 15, 25] * 200
        mock_metrics.total_time = 10.0

        db_tester.test_results.append(mock_metrics)

        # Generate report
        report = db_tester.generate_performance_report()

        # Verify report content
        assert "Database Performance Test Report" in report
        assert "test" in report
        assert "1000" in report
        assert "95.0%" in report

        # Test file output
        report_file = "/tmp/test_db_performance_report.md"
        db_tester.generate_performance_report(report_file)

        import os
        assert os.path.exists(report_file)

        # Clean up
        os.remove(report_file)


# CLI interface
async def main():
    """CLI for running database performance tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Run database performance tests")
    parser.add_argument("--test", choices=[
        "connection_pool", "select", "insert", "transaction", "mixed", "stress", "index", "all"
    ], default="all", help="Test type to run")
    parser.add_argument("--connections", type=int, default=20, help="Number of concurrent connections")
    parser.add_argument("--operations", type=int, default=100, help="Operations per session")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--output", help="Output file for report")

    args = parser.parse_args()

    tester = DatabasePerformanceTester()

    if args.test in ["connection_pool", "all"]:
        print("Running connection pool test...")
        await tester.test_connection_pool_performance(
            max_connections=args.connections,
            concurrent_workers=args.connections // 2,
            operations_per_worker=args.operations
        )

    if args.test in ["select", "all"]:
        print("Running SELECT performance test...")
        await tester.test_select_performance(
            concurrent_sessions=args.connections,
            queries_per_session=args.operations
        )

    if args.test in ["insert", "all"]:
        print("Running INSERT performance test...")
        await tester.test_insert_performance(
            concurrent_sessions=args.connections // 2,
            inserts_per_session=args.operations
        )

    if args.test in ["transaction", "all"]:
        print("Running transaction performance test...")
        await tester.test_transaction_performance(
            concurrent_sessions=args.connections,
            transactions_per_session=args.operations // 3
        )

    if args.test in ["mixed", "all"]:
        print("Running mixed workload test...")
        await tester.test_mixed_workload_performance(
            concurrent_sessions=args.connections,
            operations_per_session=args.operations
        )

    if args.test in ["stress", "all"]:
        print("Running stress test...")
        await tester.test_database_stress(
            max_connections=args.connections * 2,
            test_duration_seconds=args.duration
        )

    if args.test in ["index", "all"]:
        print("Running index performance test...")
        await tester.test_index_performance()

    # Generate report
    report = tester.generate_performance_report(args.output)
    print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())