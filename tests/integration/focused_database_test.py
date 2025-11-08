#!/usr/bin/env python3
"""
Focused Database Testing Suite for AP Intake & Validation System

This is a streamlined version that works with the current database setup
and focuses on essential database testing areas.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import statistics
import concurrent.futures
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# Get project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ap_intake',
    'user': 'postgres',
    'password': 'postgres',
    'minconn': 1,
    'maxconn': 20
}

ASYNC_DB_URL = "postgresql://postgres:postgres@localhost:5432/ap_intake"
SYNC_DB_URL = "postgresql://postgres:postgres@localhost:5432/ap_intake"

class FocusedDatabaseTestSuite:
    """Focused database testing suite for essential functionality."""

    def __init__(self):
        self.results = {
            'connectivity': {},
            'basic_crud': {},
            'data_integrity': {},
            'performance': {},
            'connection_pool': {},
            'transaction_testing': {}
        }
        self.test_start_time = time.time()

    async def run_all_tests(self):
        """Run all focused database tests."""
        print("🚀 Starting Focused Database Testing Suite")
        print("=" * 60)

        try:
            # Test database connectivity first
            await self.test_database_connectivity()

            if self.results['connectivity'].get('status') != 'PASSED':
                print("❌ Database connectivity failed. Skipping remaining tests.")
                return

            # Run core test categories
            await self.test_basic_crud_operations()
            await self.test_data_integrity()
            await self.test_connection_pool()
            await self.test_transaction_rollback()
            await self.test_performance_metrics()

            # Generate comprehensive report
            self._generate_final_report()

        except Exception as e:
            print(f"❌ Test suite execution failed: {e}")
            self._generate_final_report()

    async def test_database_connectivity(self):
        """Test basic database connectivity."""
        print("\n🔌 Testing Database Connectivity...")

        start_time = time.time()

        try:
            # Test async connection
            async_conn = await asyncpg.connect(ASYNC_DB_URL)
            version = await async_conn.fetchval("SELECT version()")
            await async_conn.close()

            # Test sync connection
            engine = create_engine(SYNC_DB_URL)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test")).scalar()

            self.results['connectivity'] = {
                'status': 'PASSED',
                'duration': time.time() - start_time,
                'postgresql_version': version,
                'sync_connection': True,
                'async_connection': True
            }

            print("✅ Database connectivity established")
            print(f"   PostgreSQL: {version.split(',')[0]}")

        except Exception as e:
            self.results['connectivity'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ Database connectivity failed: {e}")

    async def test_basic_crud_operations(self):
        """Test basic CRUD operations."""
        print("\n📝 Testing Basic CRUD Operations...")

        start_time = time.time()

        try:
            conn = await asyncpg.connect(ASYNC_DB_URL)

            try:
                # Create test vendor
                vendor_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO vendors (id, name, currency, active, status)
                    VALUES ($1, $2, $3, $4, $5)
                """, vendor_id, "CRUD Test Vendor", "USD", True, "active")

                # Read operation
                vendor_name = await conn.fetchval(
                    "SELECT name FROM vendors WHERE id = $1", vendor_id
                )
                assert vendor_name == "CRUD Test Vendor"

                # Update operation
                await conn.execute("""
                    UPDATE vendors SET name = $1 WHERE id = $2
                """, "Updated CRUD Test Vendor", vendor_id)

                updated_name = await conn.fetchval(
                    "SELECT name FROM vendors WHERE id = $1", vendor_id
                )
                assert updated_name == "Updated CRUD Test Vendor"

                # Delete operation
                await conn.execute("DELETE FROM vendors WHERE id = $1", vendor_id)

                # Verify deletion
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM vendors WHERE id = $1", vendor_id
                )
                assert count == 0

                self.results['basic_crud'] = {
                    'status': 'PASSED',
                    'duration': time.time() - start_time,
                    'create_test': True,
                    'read_test': True,
                    'update_test': True,
                    'delete_test': True
                }

                print("✅ CRUD operations working correctly")

            finally:
                await conn.close()

        except Exception as e:
            self.results['basic_crud'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ CRUD operations test failed: {e}")

    async def test_data_integrity(self):
        """Test data integrity constraints."""
        print("\n🔒 Testing Data Integrity...")

        start_time = time.time()

        try:
            conn = await asyncpg.connect(ASYNC_DB_URL)

            try:
                integrity_tests = []

                # Test 1: Primary Key Constraint
                vendor_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO vendors (id, name, currency, active, status)
                    VALUES ($1, $2, $3, $4, $5)
                """, vendor_id, "PK Test", "USD", True, "active")

                try:
                    await conn.execute("""
                        INSERT INTO vendors (id, name, currency, active, status)
                        VALUES ($1, $2, $3, $4, $5)
                    """, vendor_id, "PK Test 2", "USD", True, "active")
                    integrity_tests.append(("Primary Key", False))
                except Exception:
                    integrity_tests.append(("Primary Key", True))

                await conn.execute("DELETE FROM vendors WHERE id = $1", vendor_id)

                # Test 2: Not Null Constraint
                try:
                    await conn.execute("""
                        INSERT INTO vendors (id, name, currency, active, status)
                        VALUES ($1, NULL, $2, $3, $4)
                    """, uuid.uuid4(), "USD", True, "active")
                    integrity_tests.append(("Not Null", False))
                except Exception:
                    integrity_tests.append(("Not Null", True))

                # Test 3: Foreign Key Constraint
                vendor_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO vendors (id, name, currency, active, status)
                    VALUES ($1, $2, $3, $4, $5)
                """, vendor_id, "FK Test", "USD", True, "active")

                try:
                    fake_vendor_id = uuid.uuid4()
                    await conn.execute("""
                        INSERT INTO invoices (id, vendor_id, file_url, file_hash, file_name, file_size, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, uuid.uuid4(), fake_vendor_id, "test.pdf", "abc123", "test.pdf", "1MB", "received")
                    integrity_tests.append(("Foreign Key", False))
                except Exception:
                    integrity_tests.append(("Foreign Key", True))

                await conn.execute("DELETE FROM vendors WHERE id = $1", vendor_id)

                all_passed = all(result for _, result in integrity_tests)

                self.results['data_integrity'] = {
                    'status': 'PASSED' if all_passed else 'FAILED',
                    'duration': time.time() - start_time,
                    'constraint_tests': integrity_tests,
                    'all_constraints_passed': all_passed
                }

                print(f"✅ Data integrity tests: {sum(1 for _, passed in integrity_tests if passed)}/{len(integrity_tests)} passed")

            finally:
                await conn.close()

        except Exception as e:
            self.results['data_integrity'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ Data integrity test failed: {e}")

    async def test_connection_pool(self):
        """Test connection pool functionality."""
        print("\n🔗 Testing Connection Pool...")

        start_time = time.time()

        try:
            # Create connection pool
            pool = await asyncpg.create_pool(
                ASYNC_DB_URL,
                min_size=2,
                max_size=10,
                command_timeout=5.0
            )

            try:
                # Test basic pool functionality
                async with pool.acquire() as conn:
                    result = await conn.fetchval("SELECT 1")
                    assert result == 1

                # Test concurrent connections
                async def pool_test(task_id):
                    async with pool.acquire() as conn:
                        await conn.execute("SELECT pg_sleep(0.01)")
                        return task_id

                # Run 10 concurrent tasks
                start_time = time.time()
                tasks = [pool_test(i) for i in range(10)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                duration = time.time() - start_time

                successful = sum(1 for r in results if not isinstance(r, Exception))

                self.results['connection_pool'] = {
                    'status': 'PASSED' if successful >= 8 else 'FAILED',
                    'duration': time.time() - start_time,
                    'concurrent_tasks': 10,
                    'successful_tasks': successful,
                    'pool_size': 10,
                    'task_duration': duration
                }

                print(f"✅ Connection pool: {successful}/10 tasks successful ({duration:.2f}s)")

            finally:
                await pool.close()

        except Exception as e:
            self.results['connection_pool'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ Connection pool test failed: {e}")

    async def test_transaction_rollback(self):
        """Test transaction rollback functionality."""
        print("\n🔄 Testing Transaction Rollback...")

        start_time = time.time()

        try:
            conn = await asyncpg.connect(ASYNC_DB_URL)

            try:
                rollback_tests = []

                # Test 1: Explicit rollback
                vendor_id = uuid.uuid4()

                try:
                    async with conn.transaction():
                        await conn.execute("""
                            INSERT INTO vendors (id, name, currency, active, status)
                            VALUES ($1, $2, $3, $4, $5)
                        """, vendor_id, "Rollback Test", "USD", True, "active")

                        # Force rollback
                        raise Exception("Force rollback")

                except Exception:
                    pass  # Expected

                # Verify rollback worked
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM vendors WHERE id = $1", vendor_id
                )
                rollback_tests.append(("Explicit Rollback", count == 0))

                # Test 2: Exception rollback
                vendor_id2 = uuid.uuid4()

                try:
                    async with conn.transaction():
                        await conn.execute("""
                            INSERT INTO vendors (id, name, currency, active, status)
                            VALUES ($1, $2, $3, $4, $5)
                        """, vendor_id2, "Exception Test", "USD", True, "active")

                        # Cause exception
                        await conn.execute("SELECT * FROM nonexistent_table")

                except Exception:
                    pass  # Expected

                # Verify rollback worked
                count2 = await conn.fetchval(
                    "SELECT COUNT(*) FROM vendors WHERE id = $1", vendor_id2
                )
                rollback_tests.append(("Exception Rollback", count2 == 0))

                all_passed = all(result for _, result in rollback_tests)

                self.results['transaction_testing'] = {
                    'status': 'PASSED' if all_passed else 'FAILED',
                    'duration': time.time() - start_time,
                    'rollback_tests': rollback_tests,
                    'all_rollbacks_worked': all_passed
                }

                print(f"✅ Transaction rollback: {sum(1 for _, passed in rollback_tests if passed)}/{len(rollback_tests)} tests passed")

            finally:
                await conn.close()

        except Exception as e:
            self.results['transaction_testing'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ Transaction rollback test failed: {e}")

    async def test_performance_metrics(self):
        """Test basic performance metrics."""
        print("\n⚡ Testing Performance Metrics...")

        start_time = time.time()

        try:
            conn = await asyncpg.connect(ASYNC_DB_URL)

            try:
                performance_results = {}

                # Test 1: Simple query performance
                start_time = time.time()
                for _ in range(50):
                    await conn.fetchval("SELECT 1")
                query_duration = time.time() - start_time

                performance_results['simple_queries'] = {
                    'total_time': query_duration,
                    'avg_time_ms': (query_duration / 50) * 1000,
                    'queries_per_second': 50 / query_duration
                }

                # Test 2: Insert performance
                start_time = time.time()
                insert_ids = []

                for i in range(20):
                    vendor_id = uuid.uuid4()
                    insert_ids.append(vendor_id)
                    await conn.execute("""
                        INSERT INTO vendors (id, name, currency, active, status)
                        VALUES ($1, $2, $3, $4, $5)
                    """, vendor_id, f"Perf Test {i}", "USD", True, "active")

                insert_duration = time.time() - start_time

                performance_results['inserts'] = {
                    'total_time': insert_duration,
                    'avg_time_ms': (insert_duration / 20) * 1000,
                    'inserts_per_second': 20 / insert_duration
                }

                # Test 3: Select performance
                start_time = time.time()
                for _ in range(20):
                    await conn.fetch("SELECT * FROM vendors WHERE active = TRUE LIMIT 10")
                select_duration = time.time() - start_time

                performance_results['selects'] = {
                    'total_time': select_duration,
                    'avg_time_ms': (select_duration / 20) * 1000,
                    'selects_per_second': 20 / select_duration
                }

                # Test 4: Update performance
                start_time = time.time()
                for i, vendor_id in enumerate(insert_ids[:10]):
                    await conn.execute("""
                        UPDATE vendors SET name = $1 WHERE id = $2
                    """, f"Updated Perf Test {i}", vendor_id)

                update_duration = time.time() - start_time

                performance_results['updates'] = {
                    'total_time': update_duration,
                    'avg_time_ms': (update_duration / 10) * 1000,
                    'updates_per_second': 10 / update_duration
                }

                # Test 5: Delete performance
                start_time = time.time()
                for vendor_id in insert_ids:
                    await conn.execute("DELETE FROM vendors WHERE id = $1", vendor_id)

                delete_duration = time.time() - start_time

                performance_results['deletes'] = {
                    'total_time': delete_duration,
                    'avg_time_ms': (delete_duration / 20) * 1000,
                    'deletes_per_second': 20 / delete_duration
                }

                # Performance assessment
                query_avg = performance_results['simple_queries']['avg_time_ms']
                insert_avg = performance_results['inserts']['avg_time_ms']

                performance_good = query_avg < 10 and insert_avg < 50  # milliseconds

                self.results['performance'] = {
                    'status': 'PASSED' if performance_good else 'WARNING',
                    'duration': time.time() - start_time,
                    'metrics': performance_results,
                    'performance_assessment': 'GOOD' if performance_good else 'NEEDS_OPTIMIZATION'
                }

                print(f"✅ Performance metrics collected")
                print(f"   • Simple queries: {query_avg:.2f}ms avg")
                print(f"   • Inserts: {insert_avg:.2f}ms avg")
                print(f"   • Selects: {performance_results['selects']['avg_time_ms']:.2f}ms avg")
                print(f"   • Updates: {performance_results['updates']['avg_time_ms']:.2f}ms avg")
                print(f"   • Deletes: {performance_results['deletes']['avg_time_ms']:.2f}ms avg")

            finally:
                await conn.close()

        except Exception as e:
            self.results['performance'] = {
                'status': 'FAILED',
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"❌ Performance metrics test failed: {e}")

    def _generate_final_report(self):
        """Generate comprehensive final report."""
        print("\n" + "=" * 80)
        print("📊 FOCUSED DATABASE TESTING REPORT")
        print("=" * 80)

        total_duration = time.time() - self.test_start_time

        # Summary
        print(f"\n⏱️  Total Test Duration: {total_duration:.2f} seconds")
        print(f"🕐 Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Test Results Summary
        print(f"\n📋 TEST RESULTS SUMMARY:")
        print("-" * 40)

        passed_tests = 0
        total_tests = len(self.results)

        for test_category, results in self.results.items():
            status = results.get('status', 'UNKNOWN')
            status_emoji = "✅" if status == 'PASSED' else "⚠️" if status == 'WARNING' else "❌"
            duration = results.get('duration', 0)

            print(f"{status_emoji} {test_category.replace('_', ' ').title()}: {status} ({duration:.2f}s)")

            if status == 'PASSED':
                passed_tests += 1

            # Print additional details for each category
            if test_category == 'performance' and status == 'PASSED':
                perf_assessment = results.get('performance_assessment', 'UNKNOWN')
                print(f"    • Assessment: {perf_assessment}")

            elif test_category == 'data_integrity' and status == 'PASSED':
                constraints = results.get('constraint_tests', [])
                passed_constraints = sum(1 for _, passed in constraints if passed)
                print(f"    • Constraints: {passed_constraints}/{len(constraints)} passed")

            elif test_category == 'connection_pool' and status == 'PASSED':
                successful = results.get('successful_tasks', 0)
                total = results.get('concurrent_tasks', 0)
                print(f"    • Pool tasks: {successful}/{total} successful")

        # Overall Score
        success_rate = passed_tests / total_tests * 100 if total_tests > 0 else 0
        print(f"\n🎯 OVERALL TEST SCORE: {passed_tests}/{total_tests} ({success_rate:.1f}%)")

        # Database Health Assessment
        print(f"\n🏥 DATABASE HEALTH ASSESSMENT:")
        print("-" * 40)

        critical_issues = []

        if self.results.get('connectivity', {}).get('status') != 'PASSED':
            critical_issues.append("Database connectivity failed")

        if self.results.get('data_integrity', {}).get('status') != 'PASSED':
            critical_issues.append("Data integrity issues detected")

        if self.results.get('transaction_testing', {}).get('status') != 'PASSED':
            critical_issues.append("Transaction handling issues")

        if critical_issues:
            print("❌ CRITICAL ISSUES FOUND:")
            for issue in critical_issues:
                print(f"    • {issue}")
        else:
            print("✅ Database health: GOOD")
            print("   • Basic connectivity working")
            print("   • Data integrity constraints enforced")
            print("   • Transaction handling functional")

        # Performance Assessment
        print(f"\n⚡ PERFORMANCE ASSESSMENT:")
        print("-" * 40)

        if 'performance' in self.results:
            perf = self.results['performance']
            if perf.get('status') == 'PASSED':
                metrics = perf.get('metrics', {})
                if 'simple_queries' in metrics:
                    query_time = metrics['simple_queries']['avg_time_ms']
                    print(f"• Query response time: {query_time:.2f}ms {'✅' if query_time < 10 else '⚠️'}")

                if 'inserts' in metrics:
                    insert_time = metrics['inserts']['avg_time_ms']
                    print(f"• Insert operation time: {insert_time:.2f}ms {'✅' if insert_time < 50 else '⚠️'}")

            elif perf.get('status') == 'WARNING':
                print("⚠️ Performance needs optimization")
            else:
                print("❌ Performance testing failed")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 40)

        recommendations = []

        if success_rate >= 80:
            recommendations.append("✅ Database configuration is solid")
            recommendations.append("✅ Continue with current monitoring")
        elif success_rate >= 60:
            recommendations.append("⚠️ Address failed tests before production")
        else:
            recommendations.append("❌ Significant database issues found - immediate attention required")

        # Performance recommendations
        if 'performance' in self.results:
            perf = self.results['performance']
            if perf.get('status') == 'WARNING':
                recommendations.append("⚠️ Consider database optimization for better performance")
                recommendations.append("⚠️ Review query indexes and configuration")

        # Connection pool recommendations
        if 'connection_pool' in self.results:
            pool = self.results['connection_pool']
            if pool.get('status') != 'PASSED':
                recommendations.append("⚠️ Review connection pool configuration")
            else:
                successful = pool.get('successful_tasks', 0)
                total = pool.get('concurrent_tasks', 0)
                if successful < total:
                    recommendations.append(f"⚠️ Connection pool handled {successful}/{total} tasks - consider tuning")

        if not recommendations:
            recommendations.append("✅ Database is ready for production use")

        for rec in recommendations:
            print(f"• {rec}")

        # Export Results
        print(f"\n📄 EXPORTING RESULTS...")

        report_data = {
            "test_summary": {
                "total_duration": total_duration,
                "timestamp": datetime.now().isoformat(),
                "tests_run": total_tests,
                "tests_passed": passed_tests,
                "success_rate": success_rate
            },
            "detailed_results": self.results,
            "database_info": {
                "type": "PostgreSQL",
                "version": self.results.get('connectivity', {}).get('postgresql_version', 'Unknown'),
                "host": "localhost:5432",
                "database": "ap_intake"
            }
        }

        # Save detailed report
        report_file = f"os.path.join(PROJECT_ROOT, "focused_db_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")"
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"✅ Detailed report saved to: {report_file}")

        print("\n" + "=" * 80)
        print("🎉 FOCUSED DATABASE TESTING COMPLETED")
        print("=" * 80)

# Main execution
async def main():
    """Run the focused database test suite."""
    test_suite = FocusedDatabaseTestSuite()
    await test_suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())