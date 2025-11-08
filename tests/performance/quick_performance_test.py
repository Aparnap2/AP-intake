#!/usr/bin/env python3
"""
Quick Performance Test for AP Intake & Validation System

This script provides a quick way to run basic performance tests
to identify immediate performance issues.

Usage:
    python quick_performance_test.py
"""

import asyncio
import json
import logging
import time
from typing import Dict, List

import httpx
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuickPerformanceTest:
    """Quick performance test to identify immediate issues."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "test_time": time.time(),
            "base_url": base_url,
            "system_info": self._get_system_info(),
            "tests": {}
        }

    def _get_system_info(self) -> Dict:
        """Get basic system information."""
        return {
            "cpu_count": psutil.cpu_count(),
            "memory_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "python_version": psutil.__version__
        }

    async def run_quick_tests(self) -> Dict:
        """Run a quick battery of performance tests."""
        logger.info("Starting quick performance tests...")

        # Test 1: Basic API response time
        await self._test_api_response_time()

        # Test 2: Concurrent load test (small scale)
        await self._test_concurrent_load()

        # Test 3: Database query performance
        await self._test_database_performance()

        # Test 4: Memory usage check
        await self._test_memory_usage()

        # Test 5: Error rate under load
        await self._test_error_rate()

        # Analyze results
        self._analyze_results()

        return self.results

    async def _test_api_response_time(self):
        """Test basic API response times."""
        logger.info("Testing API response times...")

        endpoints = [
            "/health",
            "/api/v1/invoices/",
            "/metrics"
        ]

        results = {}

        for endpoint in endpoints:
            times = []
            for _ in range(10):
                start = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(f"{self.base_url}{endpoint}")
                        end = time.perf_counter()
                        times.append((end - start) * 1000)
                except Exception as e:
                    logger.warning(f"Endpoint {endpoint} failed: {e}")
                    times.append(10000)  # 10 second penalty

            avg_time = sum(times) / len(times)
            max_time = max(times)

            results[endpoint] = {
                "average_ms": avg_time,
                "max_ms": max_time,
                "samples": len(times)
            }

        self.results["tests"]["api_response_time"] = results

    async def _test_concurrent_load(self):
        """Test basic concurrent load handling."""
        logger.info("Testing concurrent load...")

        async def single_request():
            start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(f"{self.base_url}/api/v1/invoices/?limit=10")
                    end = time.perf_counter()
                    return {
                        "success": response.status_code == 200,
                        "response_time_ms": (end - start) * 1000,
                        "status_code": response.status_code
                    }
            except Exception as e:
                end = time.perf_counter()
                return {
                    "success": False,
                    "response_time_ms": (end - start) * 1000,
                    "error": str(e)
                }

        # Test with 10 concurrent requests
        concurrent_requests = 10
        tasks = [single_request() for _ in range(concurrent_requests)]

        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()

        successful = [r for r in results if isinstance(r, dict) and r.get("success", False)]
        failed = [r for r in results if isinstance(r, dict) and not r.get("success", False)]

        if successful:
            response_times = [r["response_time_ms"] for r in successful]
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = 0
            max_response_time = 0

        self.results["tests"]["concurrent_load"] = {
            "concurrent_requests": concurrent_requests,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": len(successful) / concurrent_requests * 100,
            "total_time_seconds": end_time - start_time,
            "requests_per_second": concurrent_requests / (end_time - start_time),
            "average_response_time_ms": avg_response_time,
            "max_response_time_ms": max_response_time
        }

    async def _test_database_performance(self):
        """Test basic database performance."""
        logger.info("Testing database performance...")

        # This is a simplified test - in real implementation,
        # you would connect directly to the database
        try:
            # Test API that queries database
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/invoices/?limit=50")
            end = time.perf_counter()

            self.results["tests"]["database_performance"] = {
                "large_query_response_time_ms": (end - start) * 1000,
                "records_returned": len(response.json().get("invoices", [])) if response.status_code == 200 else 0,
                "success": response.status_code == 200
            }
        except Exception as e:
            self.results["tests"]["database_performance"] = {
                "error": str(e),
                "success": False
            }

    async def _test_memory_usage(self):
        """Test memory usage."""
        logger.info("Testing memory usage...")

        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        # Perform some operations
        for _ in range(50):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.get(f"{self.base_url}/api/v1/invoices/?limit=20")
            except:
                pass

        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before

        self.results["tests"]["memory_usage"] = {
            "memory_before_mb": memory_before,
            "memory_after_mb": memory_after,
            "memory_increase_mb": memory_increase,
            "system_memory_percent": psutil.virtual_memory().percent
        }

    async def _test_error_rate(self):
        """Test error rate under moderate load."""
        logger.info("Testing error rate...")

        async def stress_request():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Test various endpoints including potentially problematic ones
                    endpoints = [
                        "/api/v1/invoices/",
                        "/api/v1/invoices/?limit=1000",  # Large limit
                        "/api/v1/invoices/nonexistent",  # Invalid endpoint
                        "/health"
                    ]
                    endpoint = endpoints[hash(str(time.time())) % len(endpoints)]

                    response = await client.get(f"{self.base_url}{endpoint}")
                    return response.status_code
            except:
                return 0  # Connection error

        # Run 20 requests
        status_codes = await asyncio.gather(*[stress_request() for _ in range(20)])

        successful = len([code for code in status_codes if 200 <= code < 400])
        client_errors = len([code for code in status_codes if 400 <= code < 500])
        server_errors = len([code for code in status_codes if 500 <= code < 600])
        connection_errors = len([code for code in status_codes if code == 0])

        self.results["tests"]["error_rate"] = {
            "total_requests": 20,
            "successful": successful,
            "client_errors": client_errors,
            "server_errors": server_errors,
            "connection_errors": connection_errors,
            "success_rate_percent": successful / 20 * 100,
            "error_rate_percent": (20 - successful) / 20 * 100
        }

    def _analyze_results(self):
        """Analyze results and identify issues."""
        logger.info("Analyzing results...")

        issues = []
        recommendations = []

        # Check API response times
        api_results = self.results["tests"].get("api_response_time", {})
        for endpoint, data in api_results.items():
            if data["average_ms"] > 1000:
                issues.append(f"Slow response time for {endpoint}: {data['average_ms']:.1f}ms")
                recommendations.append(f"Optimize {endpoint} - response time exceeds 1000ms")

        # Check concurrent load performance
        load_results = self.results["tests"].get("concurrent_load", {})
        if load_results.get("success_rate", 100) < 95:
            issues.append(f"Low success rate under load: {load_results['success_rate']:.1f}%")
            recommendations.append("Investigate load handling - success rate below 95%")

        if load_results.get("average_response_time_ms", 0) > 2000:
            issues.append(f"Slow response under load: {load_results['average_response_time_ms']:.1f}ms")
            recommendations.append("Optimize for concurrent load - response time exceeds 2000ms")

        # Check memory usage
        memory_results = self.results["tests"].get("memory_usage", {})
        if memory_results.get("memory_increase_mb", 0) > 100:
            issues.append(f"High memory increase: {memory_results['memory_increase_mb']:.1f}MB")
            recommendations.append("Check for memory leaks - high memory usage increase")

        # Check error rate
        error_results = self.results["tests"].get("error_rate", {})
        if error_results.get("error_rate_percent", 0) > 5:
            issues.append(f"High error rate: {error_results['error_rate_percent']:.1f}%")
            recommendations.append("Investigate error handling - error rate exceeds 5%")

        if error_results.get("server_errors", 0) > 0:
            issues.append(f"Server errors detected: {error_results['server_errors']}")
            recommendations.append("Check application logs for server errors")

        self.results["analysis"] = {
            "issues_count": len(issues),
            "issues": issues,
            "recommendations_count": len(recommendations),
            "recommendations": recommendations,
            "overall_health": "GOOD" if len(issues) == 0 else "NEEDS_ATTENTION" if len(issues) < 3 else "POOR"
        }

    def print_summary(self):
        """Print a summary of the test results."""
        print("\n" + "="*60)
        print("QUICK PERFORMANCE TEST RESULTS")
        print("="*60)

        # API Response Times
        api_results = self.results["tests"].get("api_response_time", {})
        if api_results:
            print("\n📊 API Response Times:")
            for endpoint, data in api_results.items():
                status = "✅" if data["average_ms"] < 500 else "⚠️" if data["average_ms"] < 1000 else "❌"
                print(f"  {status} {endpoint}: {data['average_ms']:.1f}ms avg")

        # Concurrent Load
        load_results = self.results["tests"].get("concurrent_load", {})
        if load_results:
            print(f"\n🚀 Concurrent Load Test:")
            success_rate = load_results.get("success_rate", 0)
            rps = load_results.get("requests_per_second", 0)
            avg_time = load_results.get("average_response_time_ms", 0)

            status = "✅" if success_rate >= 95 and avg_time < 1000 else "⚠️" if success_rate >= 90 else "❌"
            print(f"  {status} Success Rate: {success_rate:.1f}%")
            print(f"  📈 Throughput: {rps:.1f} RPS")
            print(f"  ⏱️  Avg Response: {avg_time:.1f}ms")

        # Memory Usage
        memory_results = self.results["tests"].get("memory_usage", {})
        if memory_results:
            print(f"\n💾 Memory Usage:")
            increase = memory_results.get("memory_increase_mb", 0)
            status = "✅" if increase < 50 else "⚠️" if increase < 100 else "❌"
            print(f"  {status} Memory Increase: {increase:.1f}MB")
            print(f"  🖥️  System Memory: {memory_results.get('system_memory_percent', 0):.1f}%")

        # Error Rate
        error_results = self.results["tests"].get("error_rate", {})
        if error_results:
            print(f"\n🚨 Error Rate:")
            error_rate = error_results.get("error_rate_percent", 0)
            status = "✅" if error_rate == 0 else "⚠️" if error_rate < 5 else "❌"
            print(f"  {status} Error Rate: {error_rate:.1f}%")
            if error_results.get("server_errors", 0) > 0:
                print(f"  ❌ Server Errors: {error_results['server_errors']}")

        # Analysis
        analysis = self.results.get("analysis", {})
        if analysis:
            print(f"\n📋 Overall Health: {analysis.get('overall_health', 'UNKNOWN')}")

            if analysis.get("issues"):
                print(f"\n⚠️  Issues Found ({analysis['issues_count']}):")
                for issue in analysis["issues"]:
                    print(f"    • {issue}")

            if analysis.get("recommendations"):
                print(f"\n💡 Recommendations ({analysis['recommendations_count']}):")
                for rec in analysis["recommendations"]:
                    print(f"    • {rec}")

        print("\n" + "="*60)


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Quick performance test for AP Intake System")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check if service is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{args.url}/health")
            if response.status_code != 200:
                print(f"❌ Service health check failed: {response.status_code}")
                return
    except Exception as e:
        print(f"❌ Cannot connect to service at {args.url}: {e}")
        print("Please ensure the AP Intake service is running")
        return

    # Run quick performance test
    test = QuickPerformanceTest(base_url=args.url)
    results = await test.run_quick_tests()

    # Print summary
    test.print_summary()

    # Save results
    import json
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quick_performance_test_{timestamp}.json"

    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n📄 Detailed results saved to: {filename}")


if __name__ == "__main__":
    asyncio.run(main())