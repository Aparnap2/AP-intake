#!/usr/bin/env python3
"""
Comprehensive Performance Test Runner for AP Intake & Validation System

This script orchestrates all performance testing components:
- External load testing (Apache Bench, wrk)
- Custom load testing scenarios
- Database performance testing
- System resource monitoring
- Performance regression detection
- Automated reporting and analysis

Usage:
    python run_performance_tests.py --suite all --duration 300 --report-dir ./performance_reports
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import argparse
import psutil

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.performance.comprehensive_performance_test import PerformanceTestRunner
from tests.performance.external_load_testing import ApacheBenchRunner, WrkRunner, CustomLoadTester
from tests.performance.database_performance_test import DatabasePerformanceTester
from tests.performance.performance_monitor import PerformanceMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTestSuite:
    """Main performance test suite orchestrator."""

    def __init__(self, base_url: str = "http://localhost:8000", report_dir: str = "./performance_reports"):
        self.base_url = base_url
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.monitor = PerformanceMonitor(sampling_interval=1.0)
        self.custom_runner = PerformanceTestRunner(base_url)
        self.ab_runner = ApacheBenchRunner(base_url)
        self.wrk_runner = WrkRunner(base_url)
        self.db_tester = DatabasePerformanceTester()

        # Test results storage
        self.test_results: Dict[str, Any] = {
            "suite_info": {
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "base_url": base_url,
                "system_info": self._get_system_info()
            },
            "load_tests": {},
            "database_tests": {},
            "monitoring_data": {
                "alerts": [],
                "system_metrics": [],
                "database_metrics": [],
                "application_metrics": []
            },
            "summary": {}
        }

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for test context."""
        return {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "disk_total_gb": psutil.disk_usage('/').total / 1024 / 1024 / 1024,
            "python_version": sys.version,
            "platform": sys.platform
        }

    async def run_suite(
        self,
        suite_type: str = "all",
        duration_minutes: int = 5,
        concurrent_users: int = 20,
        output_format: str = "json"
    ) -> Dict[str, Any]:
        """Run the complete performance test suite."""
        logger.info(f"Starting performance test suite: {suite_type}")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Duration: {duration_minutes} minutes")
        logger.info(f"Concurrent users: {concurrent_users}")

        self.test_results["suite_info"]["start_time"] = time.time()

        # Start performance monitoring
        await self.monitor.start_monitoring(api_base_url=self.base_url)

        try:
            if suite_type in ["all", "load"]:
                await self._run_load_tests(concurrent_users, duration_minutes)

            if suite_type in ["all", "database"]:
                await self._run_database_tests()

            if suite_type in ["all", "stress"]:
                await self._run_stress_tests(concurrent_users)

            if suite_type in ["all", "endurance"]:
                await self._run_endurance_tests(duration_minutes)

            # Wait for monitoring to collect final data
            await asyncio.sleep(5)

        finally:
            # Stop monitoring
            await self.monitor.stop_monitoring()

            # Collect monitoring data
            self._collect_monitoring_data()

        self.test_results["suite_info"]["end_time"] = time.time()
        self.test_results["suite_info"]["duration"] = (
            self.test_results["suite_info"]["end_time"] - self.test_results["suite_info"]["start_time"]
        )

        # Generate summary
        self._generate_summary()

        # Export results
        await self._export_results(output_format)

        logger.info(f"Performance test suite completed in {self.test_results['suite_info']['duration']:.1f} seconds")
        return self.test_results

    async def _run_load_tests(self, concurrent_users: int, duration_minutes: int):
        """Run load testing scenarios."""
        logger.info("Running load tests...")

        load_results = {}

        # Custom load test - gradual ramp-up
        logger.info("Running custom load test with gradual ramp-up...")
        custom_result = await self.custom_runner.run_load_test(
            endpoint="/api/v1/invoices/",
            method="GET",
            concurrent_users=concurrent_users,
            requests_per_user=20,
            delay_between_requests=0.1
        )
        load_results["custom_gradual"] = custom_result.to_dict()

        # Apache Bench test
        if self.ab_runner.is_available():
            logger.info("Running Apache Bench test...")
            ab_result = await self.ab_runner.run_test(
                endpoint="/api/v1/invoices/",
                concurrent_users=concurrent_users,
                total_requests=concurrent_users * 10
            )
            load_results["apache_bench"] = ab_result.to_dict()

        # wrk test
        if self.wrk_runner.is_available():
            logger.info("Running wrk test...")
            wrk_result = await self.wrk_runner.run_test(
                endpoint="/api/v1/invoices/",
                concurrent_users=concurrent_users,
                duration_seconds=60
            )
            load_results["wrk"] = wrk_result.to_dict()

        # Upload performance test
        logger.info("Running upload performance test...")
        sample_content = b"%PDF-1.4\n" + b"x" * (1024 * 1024)  # 1MB PDF

        async def upload_request():
            from unittest.mock import AsyncMock, patch
            from app.services.storage_service import StorageService
            import io

            files = {"file": ("load_test.pdf", io.BytesIO(sample_content), "application/pdf")}

            with patch.object(StorageService, 'store_file', new_callable=AsyncMock) as mock_storage:
                mock_storage.return_value = {"file_path": "/tmp/load_test.pdf"}

                with patch('app.api.api_v1.endpoints.invoices.process_invoice_task') as mock_task:
                    mock_task.delay.return_value = AsyncMock(id="load-test-task")

                    return files, {"mocked": True}

        upload_result = await self.custom_runner.run_load_test(
            endpoint="/api/v1/invoices/upload",
            method="POST",
            concurrent_users=min(concurrent_users, 10),  # Limit for upload tests
            requests_per_user=5,
            delay_between_requests=0.5
        )
        load_results["upload_test"] = upload_result.to_dict()

        self.test_results["load_tests"] = load_results

    async def _run_database_tests(self):
        """Run database performance tests."""
        logger.info("Running database performance tests...")

        db_results = {}

        # Connection pool test
        logger.info("Testing database connection pool...")
        pool_result = await self.db_tester.test_connection_pool_performance(
            max_connections=30,
            concurrent_workers=15,
            operations_per_worker=40
        )
        db_results["connection_pool"] = pool_result.to_dict()

        # SELECT performance test
        logger.info("Testing SELECT performance...")
        select_result = await self.db_tester.test_select_performance(
            concurrent_sessions=10,
            queries_per_session=50,
            query_complexity="simple"
        )
        db_results["select_simple"] = select_result.to_dict()

        # Complex SELECT test
        logger.info("Testing complex SELECT performance...")
        complex_select_result = await self.db_tester.test_select_performance(
            concurrent_sessions=8,
            queries_per_session=30,
            query_complexity="complex"
        )
        db_results["select_complex"] = complex_select_result.to_dict()

        # INSERT performance test
        logger.info("Testing INSERT performance...")
        insert_result = await self.db_tester.test_insert_performance(
            concurrent_sessions=8,
            inserts_per_session=25,
            batch_size=1
        )
        db_results["insert_single"] = insert_result.to_dict()

        # Transaction performance test
        logger.info("Testing transaction performance...")
        tx_result = await self.db_tester.test_transaction_performance(
            concurrent_sessions=10,
            transactions_per_session=20,
            operations_per_transaction=3
        )
        db_results["transaction"] = tx_result.to_dict()

        # Mixed workload test
        logger.info("Testing mixed database workload...")
        mixed_result = await self.db_tester.test_mixed_workload_performance(
            concurrent_sessions=15,
            operations_per_session=60
        )
        db_results["mixed_workload"] = mixed_result.to_dict()

        self.test_results["database_tests"] = db_results

    async def _run_stress_tests(self, concurrent_users: int):
        """Run stress testing scenarios."""
        logger.info("Running stress tests...")

        # API stress test with increasing load
        stress_levels = [10, 25, 50, 100, 150]
        stress_results = []

        for users in stress_levels:
            logger.info(f"Running stress test with {users} concurrent users...")

            try:
                result = await self.custom_runner.run_load_test(
                    endpoint="/api/v1/invoices/",
                    method="GET",
                    concurrent_users=users,
                    requests_per_user=10,
                    delay_between_requests=0.01
                )

                stress_results.append({
                    "concurrent_users": users,
                    "success_rate": result.success_rate,
                    "average_response_time": result.average_response_time,
                    "requests_per_second": result.actual_rps,
                    "errors": len(result.errors)
                })

                # Stop if success rate drops too low
                if result.success_rate < 70:
                    logger.warning(f"Success rate dropped to {result.success_rate:.1f}% at {users} users")
                    break

            except Exception as e:
                logger.error(f"Stress test failed at {users} users: {e}")
                stress_results.append({
                    "concurrent_users": users,
                    "success_rate": 0,
                    "average_response_time": 0,
                    "requests_per_second": 0,
                    "error": str(e)
                })
                break

            # Brief pause between stress levels
            await asyncio.sleep(3)

        self.test_results["load_tests"]["stress_test"] = stress_results

        # Database stress test
        logger.info("Running database stress test...")
        db_stress_result = await self.db_tester.test_database_stress(
            max_connections=50,
            test_duration_seconds=60
        )
        self.test_results["database_tests"]["stress_test"] = db_stress_result.to_dict()

    async def _run_endurance_tests(self, duration_minutes: int):
        """Run endurance testing scenarios."""
        logger.info(f"Running endurance tests for {duration_minutes} minutes...")

        # Sustained load test
        endurance_result = await self.custom_runner.run_load_test(
            endpoint="/api/v1/invoices/",
            method="GET",
            concurrent_users=15,
            duration_seconds=duration_minutes * 60
        )
        self.test_results["load_tests"]["endurance_test"] = endurance_result.to_dict()

    def _collect_monitoring_data(self):
        """Collect monitoring data from the performance monitor."""
        self.test_results["monitoring_data"]["alerts"] = self.monitor.alerts
        self.test_results["monitoring_data"]["system_metrics"] = [
            m.to_dict() for m in self.monitor.system_metrics
        ]
        self.test_results["monitoring_data"]["database_metrics"] = [
            m.to_dict() for m in self.monitor.database_metrics
        ]
        self.test_results["monitoring_data"]["application_metrics"] = [
            m.to_dict() for m in self.monitor.application_metrics
        ]

    def _generate_summary(self):
        """Generate summary statistics and analysis."""
        summary = {
            "overall_performance": {},
            "bottlenecks": [],
            "recommendations": [],
            "sla_compliance": {},
            "alerts_summary": {
                "total": len(self.monitor.alerts),
                "warnings": len([a for a in self.monitor.alerts if a.get("severity") == "warning"]),
                "critical": len([a for a in self.monitor.alerts if a.get("severity") == "critical"])
            }
        }

        # Analyze load test results
        if self.test_results["load_tests"]:
            best_rps = 0
            worst_response_time = 0
            lowest_success_rate = 100

            for test_name, result in self.test_results["load_tests"].items():
                if isinstance(result, dict) and "requests_per_second" in result:
                    best_rps = max(best_rps, result["requests_per_second"])
                if isinstance(result, dict) and "average_response_time" in result:
                    worst_response_time = max(worst_response_time, result["average_response_time"])
                if isinstance(result, dict) and "success_rate" in result:
                    lowest_success_rate = min(lowest_success_rate, result["success_rate"])

            summary["overall_performance"]["max_throughput"] = best_rps
            summary["overall_performance"]["worst_response_time"] = worst_response_time
            summary["overall_performance"]["lowest_success_rate"] = lowest_success_rate

        # Analyze database test results
        if self.test_results["database_tests"]:
            db_qps = []
            db_response_times = []

            for test_name, result in self.test_results["database_tests"].items():
                if isinstance(result, dict) and "queries_per_second" in result:
                    db_qps.append(result["queries_per_second"])
                if isinstance(result, dict) and "average_query_time" in result:
                    db_response_times.append(result["average_query_time"])

            if db_qps:
                summary["overall_performance"]["max_database_qps"] = max(db_qps)
            if db_response_times:
                summary["overall_performance"]["worst_db_response_time"] = max(db_response_times)

        # Identify bottlenecks
        if summary["alerts_summary"]["critical"] > 0:
            summary["bottlenecks"].append("Critical performance alerts detected - system overloaded")

        if worst_response_time > 5000:
            summary["bottlenecks"].append("High response times detected - possible performance bottlenecks")

        if lowest_success_rate < 95:
            summary["bottlenecks"].append("Low success rate - system instability under load")

        # Generate recommendations
        if best_rps < 100:
            summary["recommendations"].append("Consider optimizing API endpoints for better throughput")

        if summary["alerts_summary"]["total"] > 10:
            summary["recommendations"].append("Investigate frequent performance alerts - resource constraints")

        if worst_response_time > 2000:
            summary["recommendations"].append("Optimize slow queries and implement caching strategies")

        # SLA compliance assessment
        summary["sla_compliance"] = {
            "response_time_target": "200ms",
            "response_time_achieved": worst_response_time <= 200,
            "availability_target": "99.9%",
            "availability_achieved": lowest_success_rate >= 99.9,
            "throughput_target": "100 RPS",
            "throughput_achieved": best_rps >= 100
        }

        self.test_results["summary"] = summary

    async def _export_results(self, output_format: str):
        """Export test results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export main results
        results_file = self.report_dir / f"performance_test_results_{timestamp}.{output_format}"
        if output_format == "json":
            with open(results_file, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
        else:
            # Export as markdown report
            await self._export_markdown_report(timestamp)

        # Export monitoring data
        if self.monitor.system_metrics:
            monitor_file = self.report_dir / f"monitoring_data_{timestamp}.json"
            self.monitor.export_data(str(monitor_file))

        # Generate performance report
        report_file = self.report_dir / f"performance_report_{timestamp}.md"
        report = self.monitor.generate_report()
        with open(report_file, 'w') as f:
            f.write(report)

        logger.info(f"Results exported to {self.report_dir}")
        logger.info(f"Main results: {results_file}")
        logger.info(f"Monitoring data: {monitor_file}")
        logger.info(f"Performance report: {report_file}")

    async def _export_markdown_report(self, timestamp: str):
        """Export results as markdown report."""
        report_file = self.report_dir / f"performance_test_report_{timestamp}.md"

        report = []
        report.append("# Performance Test Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Test Duration: {self.test_results['suite_info']['duration']:.1f} seconds")
        report.append(f"Base URL: {self.test_results['suite_info']['base_url']}")
        report.append("")

        # System Information
        report.append("## System Information")
        sys_info = self.test_results["suite_info"]["system_info"]
        report.append(f"- **CPU Cores:** {sys_info['cpu_count']}")
        report.append(f"- **Total Memory:** {sys_info['memory_total_gb']:.1f} GB")
        report.append(f"- **Total Disk:** {sys_info['disk_total_gb']:.1f} GB")
        report.append("")

        # Test Results Summary
        report.append("## Test Results Summary")
        summary = self.test_results.get("summary", {})

        if "overall_performance" in summary:
            perf = summary["overall_performance"]
            report.append(f"- **Max Throughput:** {perf.get('max_throughput', 0):.1f} RPS")
            report.append(f"- **Worst Response Time:** {perf.get('worst_response_time', 0):.1f} ms")
            report.append(f"- **Lowest Success Rate:** {perf.get('lowest_success_rate', 100):.1f}%")

        report.append(f"- **Total Alerts:** {summary.get('alerts_summary', {}).get('total', 0)}")
        report.append("")

        # Load Test Results
        if self.test_results["load_tests"]:
            report.append("## Load Test Results")
            for test_name, result in self.test_results["load_tests"].items():
                report.append(f"### {test_name.replace('_', ' ').title()}")
                if isinstance(result, dict):
                    report.append(f"- **Success Rate:** {result.get('success_rate', 0):.1f}%")
                    report.append(f"- **RPS:** {result.get('requests_per_second', 0):.1f}")
                    report.append(f"- **Avg Response Time:** {result.get('average_response_time', 0):.1f} ms")
                report.append("")

        # Database Test Results
        if self.test_results["database_tests"]:
            report.append("## Database Test Results")
            for test_name, result in self.test_results["database_tests"].items():
                report.append(f"### {test_name.replace('_', ' ').title()}")
                if isinstance(result, dict):
                    report.append(f"- **Success Rate:** {result.get('success_rate', 0):.1f}%")
                    report.append(f"- **QPS:** {result.get('queries_per_second', 0):.1f}")
                    report.append(f"- **Avg Query Time:** {result.get('average_query_time', 0):.1f} ms")
                report.append("")

        # Alerts and Issues
        if summary.get("bottlenecks"):
            report.append("## Bottlenecks Identified")
            for bottleneck in summary["bottlenecks"]:
                report.append(f"- {bottleneck}")
            report.append("")

        # Recommendations
        if summary.get("recommendations"):
            report.append("## Recommendations")
            for rec in summary["recommendations"]:
                report.append(f"- {rec}")
            report.append("")

        # SLA Compliance
        if summary.get("sla_compliance"):
            report.append("## SLA Compliance")
            sla = summary["sla_compliance"]
            report.append(f"- **Response Time Target ({sla['response_time_target']}):** "
                         f"{'✅ PASS' if sla['response_time_achieved'] else '❌ FAIL'}")
            report.append(f"- **Availability Target ({sla['availability_target']}):** "
                         f"{'✅ PASS' if sla['availability_achieved'] else '❌ FAIL'}")
            report.append(f"- **Throughput Target ({sla['throughput_target']}):** "
                         f"{'✅ PASS' if sla['throughput_achieved'] else '❌ FAIL'}")
            report.append("")

        with open(report_file, 'w') as f:
            f.write("\n".join(report))


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Performance Testing Suite for AP Intake System"
    )
    parser.add_argument(
        "--suite",
        choices=["all", "load", "database", "stress", "endurance"],
        default="all",
        help="Test suite to run"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL for testing"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=5,
        help="Test duration in minutes"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=20,
        help="Concurrent users for load tests"
    )
    parser.add_argument(
        "--report-dir",
        default="./performance_reports",
        help="Directory for reports"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate that the target service is running
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{args.url}/health")
            if response.status_code != 200:
                logger.error(f"Target service health check failed: {response.status_code}")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Cannot connect to target service at {args.url}: {e}")
        logger.error("Please ensure the AP Intake service is running before running performance tests")
        sys.exit(1)

    # Run the performance test suite
    suite = PerformanceTestSuite(base_url=args.url, report_dir=args.report_dir)

    try:
        results = await suite.run_suite(
            suite_type=args.suite,
            duration_minutes=args.duration,
            concurrent_users=args.users,
            output_format=args.format
        )

        # Print summary
        summary = results.get("summary", {})
        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)

        if "overall_performance" in summary:
            perf = summary["overall_performance"]
            print(f"Max Throughput: {perf.get('max_throughput', 0):.1f} RPS")
            print(f"Worst Response Time: {perf.get('worst_response_time', 0):.1f} ms")
            print(f"Lowest Success Rate: {perf.get('lowest_success_rate', 100):.1f}%")

        alerts = summary.get("alerts_summary", {})
        print(f"Total Alerts: {alerts.get('total', 0)}")
        print(f"Critical Alerts: {alerts.get('critical', 0)}")

        bottlenecks = summary.get("bottlenecks", [])
        if bottlenecks:
            print("\nBottlenecks Identified:")
            for bottleneck in bottlenecks:
                print(f"  - {bottleneck}")

        recommendations = summary.get("recommendations", [])
        if recommendations:
            print("\nRecommendations:")
            for rec in recommendations:
                print(f"  - {rec}")

        print(f"\nDetailed reports saved to: {args.report_dir}")
        print("="*60)

    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Import httpx for health check
    import httpx
    asyncio.run(main())