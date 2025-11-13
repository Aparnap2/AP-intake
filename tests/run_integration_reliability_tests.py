#!/usr/bin/env python3
"""
Integration and Reliability Test Runner for AP Intake & Validation System.

This script provides a comprehensive test runner that executes:
- ERP integration tests (QuickBooks, SAP, Generic)
- Storage systems reliability tests
- Email integration tests
- Retry logic and circuit breaker tests
- DLQ and redrive functionality tests
- Outbox pattern tests
- Fault injection and resilience tests
- Performance under failure tests

Usage:
    python run_integration_reliability_tests.py [--scenario SCENARIO] [--verbose] [--report-format FORMAT]

Author: Integration and Reliability Testing Specialist
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from comprehensive_integration_reliability_test import IntegrationReliabilityTestSuite, TestScenario
from erp_integration_test import ERPIntegrationTester
from reliability_testing_utils import FaultInjector, PerformanceMonitor, LoadGenerator


class TestRunner:
    """Comprehensive test runner for integration and reliability testing."""

    def __init__(self):
        """Initialize test runner."""
        self.setup_logging()
        self.results = {}
        self.start_time = None
        self.end_time = None

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('integration_reliability_tests.log')
            ]
        )

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration and reliability tests."""
        self.start_time = time.time()
        logging.info("Starting comprehensive integration and reliability testing")

        # 1. Run comprehensive integration reliability tests
        logging.info("Running comprehensive integration reliability tests...")
        integration_suite = IntegrationReliabilityTestSuite()
        self.results["integration_reliability"] = await integration_suite.run_all_tests()

        # 2. Run ERP-specific integration tests
        logging.info("Running ERP integration tests...")
        erp_tester = ERPIntegrationTester()
        self.results["erp_integration"] = await erp_tester.run_all_tests()

        # 3. Run fault injection and resilience tests
        logging.info("Running fault injection and resilience tests...")
        self.results["fault_injection"] = await self._run_fault_injection_tests()

        # 4. Run performance under failure tests
        logging.info("Running performance under failure tests...")
        self.results["performance_under_failure"] = await self._run_performance_failure_tests()

        self.end_time = time.time()
        self._generate_final_report()

        return self.results

    async def run_scenario_tests(self, scenario: str) -> Dict[str, Any]:
        """Run tests for a specific scenario."""
        self.start_time = time.time()
        logging.info(f"Running tests for scenario: {scenario}")

        try:
            test_scenario = TestScenario(scenario)
        except ValueError:
            available_scenarios = [s.value for s in TestScenario]
            logging.error(f"Invalid scenario: {scenario}. Available scenarios: {available_scenarios}")
            return {"error": f"Invalid scenario: {scenario}", "available_scenarios": available_scenarios}

        # Run specific scenario tests
        integration_suite = IntegrationReliabilityTestSuite()

        if test_scenario == TestScenario.ERP_SANDBOX:
            await integration_suite._test_erp_sandbox_integration()
        elif test_scenario == TestScenario.STORAGE_RELIABILITY:
            await integration_suite._test_storage_systems_reliability()
        elif test_scenario == TestScenario.EMAIL_INTEGRATION:
            await integration_suite._test_email_integration()
        elif test_scenario == TestScenario.RETRY_LOGIC:
            await integration_suite._test_retry_logic()
        elif test_scenario == TestScenario.DLQ_REDRIIVE:
            await integration_suite._test_dlq_redrive_functionality()
        elif test_scenario == TestScenario.OUTBOX_PATTERN:
            await integration_suite._test_outbox_pattern()
        elif test_scenario == TestScenario.FAULT_INJECTION:
            await integration_suite._test_fault_injection()
        elif test_scenario == TestScenario.PERFORMANCE_FAILURE:
            await integration_suite._test_performance_under_failure()

        self.end_time = time.time()
        self.results["scenario_tests"] = integration_suite.results

        return {
            "scenario": scenario,
            "results": [r.__dict__ for r in integration_suite.results],
            "summary": self._calculate_scenario_summary(integration_suite.results)
        }

    async def _run_fault_injection_tests(self) -> Dict[str, Any]:
        """Run fault injection tests."""
        fault_injector = FaultInjector()
        performance_monitor = PerformanceMonitor()

        # Add failure scenarios
        fault_injector.add_scenario("network_timeout", {
            "type": "network_timeout",
            "probability": 0.3,
            "metadata": {"timeout_seconds": 5.0}
        })

        fault_injector.add_scenario("database_failure", {
            "type": "database_failure",
            "probability": 0.2,
            "metadata": {"recovery_time_seconds": 2.0}
        })

        fault_injector.add_scenario("rate_limit", {
            "type": "rate_limit",
            "probability": 0.4,
            "metadata": {"retry_after_seconds": 1.0}
        })

        performance_monitor.start_monitoring()

        # Test operations with fault injection
        for i in range(50):
            async with fault_injector.failure_context("api_client"):
                start_time = time.time()
                try:
                    # Simulate API operation
                    await asyncio.sleep(0.1)
                    duration = (time.time() - start_time) * 1000
                    performance_monitor.record_operation(True, duration)
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    performance_monitor.record_operation(False, duration, type(e).__name__)

        performance_monitor.stop_monitoring()

        return {
            "performance_report": performance_monitor.get_performance_report(),
            "injection_summary": fault_injector.get_injection_summary()
        }

    async def _run_performance_failure_tests(self) -> Dict[str, Any]:
        """Run performance under failure tests."""
        load_generator = LoadGenerator()

        # Define test operation
        async def test_operation():
            await asyncio.sleep(0.05)  # 50ms operation
            if random.random() < 0.1:  # 10% failure rate
                raise Exception("Simulated operation failure")

        # Run constant load with failures
        result = await load_generator.generate_constant_load(
            operation=test_operation,
            requests_per_second=10.0,
            duration_seconds=30.0,
            concurrent_workers=5
        )

        return {
            "load_test_result": result,
            "test_configuration": {
                "requests_per_second": 10.0,
                "duration_seconds": 30.0,
                "concurrent_workers": 5,
                "failure_rate": 0.1
            }
        }

    def _calculate_scenario_summary(self, results: List) -> Dict[str, Any]:
        """Calculate summary statistics for scenario results."""
        if not results:
            return {}

        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0

        durations = [r.duration_ms for r in results]
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": round(success_rate, 2),
            "avg_duration_ms": round(avg_duration, 2),
            "max_duration_ms": round(max_duration, 2)
        }

    def _generate_final_report(self):
        """Generate final test report."""
        total_duration = (self.end_time - self.start_time) * 1000 if self.end_time and self.start_time else 0

        # Calculate overall statistics
        total_tests = 0
        successful_tests = 0

        for category, results in self.results.items():
            if isinstance(results, dict) and "total_tests" in results:
                total_tests += results["total_tests"]
                successful_tests += results.get("successful_tests", 0)
            elif category == "scenario_tests" and isinstance(results, list):
                total_tests += len(results)
                successful_tests += sum(1 for r in results if r.success)

        overall_success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0

        report = {
            "test_execution": {
                "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat() if self.start_time else None,
                "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
                "total_duration_ms": round(total_duration, 2)
            },
            "overall_results": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": round(overall_success_rate, 2)
            },
            "category_results": {}
        }

        # Add category-specific results
        for category, results in self.results.items():
            if isinstance(results, dict):
                report["category_results"][category] = results

        # Save report to file
        report_filename = f"integration_reliability_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logging.info(f"Test report saved to: {report_filename}")
        self._print_summary(report)

    def _print_summary(self, report: Dict[str, Any]):
        """Print test summary to console."""
        print("\n" + "="*80)
        print("INTEGRATION AND RELIABILITY TEST REPORT")
        print("="*80)

        print(f"Test Duration: {report['test_execution']['total_duration_ms']:.2f}ms")
        print(f"Total Tests: {report['overall_results']['total_tests']}")
        print(f"Successful: {report['overall_results']['successful_tests']}")
        print(f"Failed: {report['overall_results']['failed_tests']}")
        print(f"Success Rate: {report['overall_results']['success_rate']}%")

        print("\nResults by Category:")
        for category, results in report["category_results"].items():
            if isinstance(results, dict) and "success_rate" in results:
                print(f"  {category}: {results.get('successful_tests', 0)}/{results.get('total_tests', 0)} "
                      f"({results.get('success_rate', 0):.1f}%)")

        print("\nDetailed Results:")
        for category, results in report["category_results"].items():
            print(f"\n{category.upper()}:")
            if isinstance(results, dict):
                for key, value in results.items():
                    if key != "detailed_results" and not isinstance(value, (dict, list)):
                        print(f"  {key}: {value}")
            elif isinstance(results, list):
                scenario_counts = {}
                for result in results:
                    scenario = result.get("scenario", "unknown")
                    if scenario not in scenario_counts:
                        scenario_counts[scenario] = {"total": 0, "success": 0}
                    scenario_counts[scenario]["total"] += 1
                    if result.get("success"):
                        scenario_counts[scenario]["success"] += 1

                for scenario, counts in scenario_counts.items():
                    success_rate = counts["success"] / counts["total"] * 100 if counts["total"] > 0 else 0
                    print(f"  {scenario}: {counts['success']}/{counts['total']} ({success_rate:.1f}%)")

        print("="*80)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run integration and reliability tests for AP Intake & Validation System"
    )

    parser.add_argument(
        "--scenario",
        choices=[s.value for s in TestScenario],
        help="Run tests for a specific scenario only"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--report-format",
        choices=["json", "text"],
        default="text",
        help="Report output format (default: text)"
    )

    parser.add_argument(
        "--output-file",
        help="Save report to specified file"
    )

    return parser


async def main():
    """Main function."""
    parser = create_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = TestRunner()

    try:
        if args.scenario:
            # Run specific scenario
            results = await runner.run_scenario_tests(args.scenario)
        else:
            # Run all tests
            results = await runner.run_all_tests()

        # Save to custom file if specified
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Report saved to: {args.output_file}")

        # Return appropriate exit code
        overall_success_rate = results.get("overall_results", {}).get("success_rate", 0)
        if overall_success_rate >= 80.0:
            print("\n✅ Tests completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Tests completed with low success rate: {overall_success_rate}%")
            sys.exit(1)

    except Exception as e:
        logging.error(f"Test execution failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())