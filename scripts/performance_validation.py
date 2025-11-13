#!/usr/bin/env python3
"""
Comprehensive performance validation script for AP Intake & Validation system.
This script runs various performance tests and validates system capabilities.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

import httpx
import psutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.load_test_service import load_test_service, LoadTestType
from app.services.database_performance_service import database_performance_service
from app.services.performance_profiling_service import performance_profiling_service
from app.services.metrics_service import metrics_service
from app.services.prometheus_service import prometheus_service
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_validation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class PerformanceValidator:
    """Comprehensive performance validation system."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.results = {
            "validation_started": datetime.utcnow().isoformat(),
            "base_url": base_url,
            "tests": [],
            "summary": {},
            "recommendations": []
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def run_all_validations(self) -> Dict[str, Any]:
        """Run all performance validations."""
        logger.info("Starting comprehensive performance validation")

        try:
            # System health check
            await self._validate_system_health()

            # Basic API performance tests
            await self._validate_api_performance()

            # Load testing
            await self._validate_load_performance()

            # Database performance
            await self._validate_database_performance()

            # Memory and CPU profiling
            await self._validate_resource_usage()

            # SLO compliance
            await self._validate_slo_compliance()

            # Generate summary
            self._generate_summary()

            logger.info("Performance validation completed")
            return self.results

        except Exception as e:
            logger.error(f"Performance validation failed: {e}")
            self.results["error"] = str(e)
            return self.results

    async def _validate_system_health(self):
        """Validate basic system health."""
        logger.info("Validating system health...")

        test_result = {
            "name": "System Health Check",
            "started_at": datetime.utcnow().isoformat(),
            "checks": []
        }

        try:
            # Health endpoint
            response = await self.client.get("/health")
            health_data = response.json()
            test_result["checks"].append({
                "name": "Health Endpoint",
                "status": "pass" if response.status_code == 200 else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": health_data
            })

            # Metrics endpoint
            response = await self.client.get("/metrics")
            test_result["checks"].append({
                "name": "Metrics Endpoint",
                "status": "pass" if response.status_code == 200 else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": "Metrics accessible"
            })

            # API docs endpoint
            response = await self.client.get("/docs")
            test_result["checks"].append({
                "name": "API Documentation",
                "status": "pass" if response.status_code == 200 else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": "API docs accessible"
            })

            test_result["status"] = "passed"
            test_result["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            test_result["status"] = "failed"
            test_result["error"] = str(e)
            logger.error(f"System health validation failed: {e}")

        self.results["tests"].append(test_result)

    async def _validate_api_performance(self):
        """Validate API endpoint performance."""
        logger.info("Validating API performance...")

        test_result = {
            "name": "API Performance Tests",
            "started_at": datetime.utcnow().isoformat(),
            "endpoints": []
        }

        endpoints = [
            {"path": "/", "name": "Root Endpoint"},
            {"path": "/health", "name": "Health Check"},
            {"path": "/api/v1/invoices/", "name": "List Invoices"},
            {"path": "/api/v1/auth/dev-token", "name": "Get Auth Token"},
            {"path": "/api/v1/metrics/slos/dashboard", "name": "SLO Dashboard"},
        ]

        for endpoint in endpoints:
            try:
                # Measure response time for multiple requests
                response_times = []
                for _ in range(5):
                    start_time = time.time()
                    response = await self.client.get(endpoint["path"])
                    end_time = time.time()
                    response_times.append((end_time - start_time) * 1000)

                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                min_response_time = min(response_times)

                test_result["endpoints"].append({
                    "name": endpoint["name"],
                    "path": endpoint["path"],
                    "status": "pass" if response.status_code == 200 else "fail",
                    "avg_response_time_ms": avg_response_time,
                    "max_response_time_ms": max_response_time,
                    "min_response_time_ms": min_response_time,
                    "sample_count": len(response_times)
                })

            except Exception as e:
                test_result["endpoints"].append({
                    "name": endpoint["name"],
                    "path": endpoint["path"],
                    "status": "failed",
                    "error": str(e)
                })

        test_result["status"] = "completed"
        test_result["completed_at"] = datetime.utcnow().isoformat()

        self.results["tests"].append(test_result)

    async def _validate_load_performance(self):
        """Validate system performance under load."""
        logger.info("Validating load performance...")

        test_result = {
            "name": "Load Performance Tests",
            "started_at": datetime.utcnow().isoformat(),
            "load_tests": []
        }

        # Run different types of load tests
        load_test_configs = [
            {"type": LoadTestType.SMOKE, "description": "Smoke Test - Light Load"},
            {"type": LoadTestType.LIGHT, "description": "Light Load Test"},
            {"type": LoadTestType.MEDIUM, "description": "Medium Load Test"},
        ]

        for config in load_test_configs:
            try:
                logger.info(f"Running {config['description']}...")

                # Start load test
                test_id = await load_test_service.run_load_test(config["type"])

                # Wait for test to complete
                max_wait_time = 600  # 10 minutes
                wait_interval = 10
                elapsed_time = 0

                while elapsed_time < max_wait_time:
                    test_result_data = await load_test_service.get_test_results(test_id)
                    if test_result_data and test_result_data.status.value in ["completed", "failed"]:
                        break
                    await asyncio.sleep(wait_interval)
                    elapsed_time += wait_interval

                # Get final results
                final_results = await load_test_service.get_test_results(test_id)
                if final_results:
                    test_result["load_tests"].append({
                        "type": config["type"].value,
                        "description": config["description"],
                        "test_id": test_id,
                        "status": final_results.status.value,
                        "duration_seconds": final_results.calculate_duration(),
                        "total_requests": final_results.total_requests,
                        "requests_per_second": final_results.requests_per_second,
                        "avg_response_time_ms": final_results.avg_response_time,
                        "p95_response_time_ms": final_results.p95_response_time,
                        "failure_rate": final_results.failure_rate,
                        "performance_passed": final_results.performance_passed,
                        "validation_errors": final_results.validation_errors
                    })
                else:
                    test_result["load_tests"].append({
                        "type": config["type"].value,
                        "description": config["description"],
                        "test_id": test_id,
                        "status": "timeout",
                        "error": "Test did not complete within timeout period"
                    })

            except Exception as e:
                test_result["load_tests"].append({
                    "type": config["type"].value,
                    "description": config["description"],
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(f"Load test {config['type'].value} failed: {e}")

        test_result["status"] = "completed"
        test_result["completed_at"] = datetime.utcnow().isoformat()

        self.results["tests"].append(test_result)

    async def _validate_database_performance(self):
        """Validate database performance."""
        logger.info("Validating database performance...")

        test_result = {
            "name": "Database Performance Tests",
            "started_at": datetime.utcnow().isoformat(),
            "metrics": {}
        }

        try:
            # Collect current database metrics
            db_metrics = await database_performance_service.collect_database_metrics()

            test_result["metrics"] = {
                "active_connections": db_metrics.active_connections,
                "total_connections": db_metrics.total_connections,
                "cache_hit_ratio": db_metrics.cache_hit_ratio,
                "queries_per_second": db_metrics.queries_per_second,
                "avg_query_time_ms": db_metrics.avg_query_time_ms,
                "database_size_mb": db_metrics.database_size_mb,
                "table_locks": db_metrics.table_locks,
                "deadlocks": db_metrics.deadlocks
            }

            # Get query performance summary
            query_summary = await database_performance_service.get_query_performance_summary(1)
            test_result["query_performance"] = query_summary

            # Check for slow queries
            slow_queries = await database_performance_service.get_slow_queries(limit=10)
            test_result["slow_queries_count"] = len(slow_queries)
            test_result["slow_queries_sample"] = slow_queries[:3]

            # Generate database health report
            health_report = await database_performance_service.generate_database_health_report()
            test_result["health_score"] = health_report.get("health_score", 0)
            test_result["health_status"] = health_report.get("status", "unknown")
            test_result["health_recommendations"] = health_report.get("recommendations", [])

            test_result["status"] = "completed"

        except Exception as e:
            test_result["status"] = "failed"
            test_result["error"] = str(e)
            logger.error(f"Database performance validation failed: {e}")

        test_result["completed_at"] = datetime.utcnow().isoformat()

        self.results["tests"].append(test_result)

    async def _validate_resource_usage(self):
        """Validate system resource usage."""
        logger.info("Validating resource usage...")

        test_result = {
            "name": "Resource Usage Validation",
            "started_at": datetime.utcnow().isoformat(),
            "metrics": {}
        }

        try:
            # Get current system metrics
            process = psutil.Process()
            system_memory = psutil.virtual_memory()
            system_cpu = psutil.cpu_percent(interval=1)

            test_result["metrics"] = {
                "process_memory_mb": process.memory_info().rss / 1024 / 1024,
                "process_cpu_percent": process.cpu_percent(),
                "system_memory_total_gb": system_memory.total / 1024 / 1024 / 1024,
                "system_memory_available_gb": system_memory.available / 1024 / 1024 / 1024,
                "system_memory_percent": system_memory.percent,
                "system_cpu_percent": system_cpu,
                "process_threads": process.num_threads(),
                "process_open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
            }

            # Get performance profiling summary
            profile_summary = await performance_profiling_service.get_profile_summary()
            test_result["profiling_summary"] = profile_summary

            test_result["status"] = "completed"

        except Exception as e:
            test_result["status"] = "failed"
            test_result["error"] = str(e)
            logger.error(f"Resource usage validation failed: {e}")

        test_result["completed_at"] = datetime.utcnow().isoformat()

        self.results["tests"].append(test_result)

    async def _validate_slo_compliance(self):
        """Validate SLO compliance."""
        logger.info("Validating SLO compliance...")

        test_result = {
            "name": "SLO Compliance Validation",
            "started_at": datetime.utcnow().isoformat(),
            "slo_data": {}
        }

        try:
            # Get SLO dashboard data
            slo_dashboard = await metrics_service.get_slo_dashboard_data(7)  # Last 7 days
            test_result["slo_data"] = slo_dashboard

            # Check SLO health
            summary = slo_dashboard.get("summary", {})
            total_slos = summary.get("total_slos", 0)
            healthy_slos = summary.get("healthy_slos", 0)
            warning_slos = summary.get("warning_slos", 0)
            critical_slos = summary.get("critical_slos", 0)

            test_result["compliance"] = {
                "total_slos": total_slos,
                "healthy_slos": healthy_slos,
                "warning_slos": warning_slos,
                "critical_slos": critical_slos,
                "health_percentage": (healthy_slos / total_slos * 100) if total_slos > 0 else 0
            }

            test_result["status"] = "completed"

        except Exception as e:
            test_result["status"] = "failed"
            test_result["error"] = str(e)
            logger.error(f"SLO compliance validation failed: {e}")

        test_result["completed_at"] = datetime.utcnow().isoformat()

        self.results["tests"].append(test_result)

    def _generate_summary(self):
        """Generate overall validation summary."""
        logger.info("Generating validation summary...")

        total_tests = len(self.results["tests"])
        passed_tests = len([t for t in self.results["tests"] if t.get("status") == "completed" or t.get("status") == "passed"])
        failed_tests = total_tests - passed_tests

        # Calculate overall performance score
        performance_score = 0
        max_score = 100

        # API performance (30 points)
        api_test = next((t for t in self.results["tests"] if t["name"] == "API Performance Tests"), None)
        if api_test and api_test.get("status") == "completed":
            api_score = 30
            # Check response times
            for endpoint in api_test.get("endpoints", []):
                if endpoint.get("avg_response_time_ms", 0) > 1000:  # > 1 second
                    api_score -= 5
                elif endpoint.get("avg_response_time_ms", 0) > 500:  # > 500ms
                    api_score -= 2
            performance_score += max(0, api_score)

        # Load test performance (40 points)
        load_test = next((t for t in self.results["tests"] if t["name"] == "Load Performance Tests"), None)
        if load_test and load_test.get("status") == "completed":
            load_score = 40
            for test in load_test.get("load_tests", []):
                if test.get("performance_passed", False):
                    # Points based on test difficulty
                    if test["type"] == "medium":
                        load_score += 15
                    elif test["type"] == "light":
                        load_score += 10
                    elif test["type"] == "smoke":
                        load_score += 5
            performance_score += min(40, load_score)

        # Database performance (20 points)
        db_test = next((t for t in self.results["tests"] if t["name"] == "Database Performance Tests"), None)
        if db_test and db_test.get("status") == "completed":
            db_score = 20
            health_score = db_test.get("health_score", 0)
            if health_score >= 90:
                db_score = 20
            elif health_score >= 80:
                db_score = 15
            elif health_score >= 70:
                db_score = 10
            else:
                db_score = 5
            performance_score += db_score

        # Resource usage (10 points)
        resource_test = next((t for t in self.results["tests"] if t["name"] == "Resource Usage Validation"), None)
        if resource_test and resource_test.get("status") == "completed":
            resource_score = 10
            metrics = resource_test.get("metrics", {})
            if metrics.get("process_memory_mb", 0) > 500:  # > 500MB
                resource_score -= 3
            if metrics.get("system_memory_percent", 0) > 80:  # > 80%
                resource_score -= 3
            if metrics.get("system_cpu_percent", 0) > 80:  # > 80%
                resource_score -= 2
            performance_score += max(0, resource_score)

        # Generate recommendations
        recommendations = []
        if performance_score < 70:
            recommendations.append("Performance score is below 70% - review all performance metrics and optimize bottlenecks")

        if api_test:
            slow_endpoints = [e for e in api_test.get("endpoints", []) if e.get("avg_response_time_ms", 0) > 500]
            if slow_endpoints:
                recommendations.append(f"Optimize {len(slow_endpoints)} slow API endpoints")

        if db_test:
            health_score = db_test.get("health_score", 0)
            if health_score < 80:
                recommendations.append("Database health score is low - review query performance and indexes")

        if load_test:
            failed_load_tests = [t for t in load_test.get("load_tests", []) if not t.get("performance_passed", True)]
            if failed_load_tests:
                recommendations.append(f"{len(failed_load_tests)} load test(s) failed - review system capacity")

        self.results["summary"] = {
            "validation_completed": datetime.utcnow().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "performance_score": performance_score,
            "max_score": max_score,
            "grade": self._get_performance_grade(performance_score)
        }

        self.results["recommendations"] = recommendations

    def _get_performance_grade(self, score: float) -> str:
        """Get performance grade based on score."""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def save_results(self, filename: str = None):
        """Save validation results to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_validation_results_{timestamp}.json"

        filepath = Path("reports") / filename
        filepath.parent.mkdir(exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"Validation results saved to {filepath}")
        return filepath


async def main():
    """Main validation script."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    logger.info(f"Starting performance validation for {base_url}")

    async with PerformanceValidator(base_url) as validator:
        results = await validator.run_all_validations()

        # Save results
        results_file = validator.save_results()

        # Print summary
        summary = results.get("summary", {})
        print("\n" + "="*60)
        print("PERFORMANCE VALIDATION SUMMARY")
        print("="*60)
        print(f"Tests Run: {summary.get('total_tests', 0)}")
        print(f"Tests Passed: {summary.get('passed_tests', 0)}")
        print(f"Tests Failed: {summary.get('failed_tests', 0)}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        print(f"Performance Score: {summary.get('performance_score', 0)}/{summary.get('max_score', 100)}")
        print(f"Grade: {summary.get('grade', 'N/A')}")
        print("="*60)

        if results.get("recommendations"):
            print("\nRECOMMENDATIONS:")
            for i, rec in enumerate(results["recommendations"], 1):
                print(f"{i}. {rec}")

        print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())