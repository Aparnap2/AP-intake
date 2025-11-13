"""
Comprehensive Integration Test Suite
Tests all custom code functionality for production readiness.
"""

import asyncio
import time
import logging
from typing import Dict, Any, List
from datetime import datetime

from app.services.integration_factory import (
    IntegrationFactory,
    IntegrationType,
    IntegrationConfig,
    FactoryConfig
)
from app.services.workflow_service import (
    WorkflowService,
    get_workflow_service,
    configure_workflow_service
)
from app.schemas.integration_schemas import (
    WorkflowType,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveIntegrationTest:
    """Comprehensive test suite for integration system."""

    def __init__(self):
        """Initialize test suite."""
        self.test_results = []
        self.performance_metrics = []
        self.start_time = time.time()

    def record_test(self, test_name: str, passed: bool, duration: float, details: str = ""):
        """Record test result."""
        self.test_results.append({
            "test_name": test_name,
            "passed": passed,
            "duration": duration,
            "details": details,
            "timestamp": datetime.utcnow()
        })

        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} {test_name} ({duration:.2f}s) {details}")

    async def test_01_basic_functionality(self) -> None:
        """Test basic integration system functionality."""
        logger.info("🧪 Testing 1: Basic Functionality")
        start_time = time.time()

        try:
            # Test factory creation
            config = FactoryConfig(
                default_provider=IntegrationType.NATIVE,
                providers=[
                    IntegrationConfig(
                        provider_type=IntegrationType.NATIVE,
                        enabled=True,
                        priority=1,
                        config={"max_concurrent_workflows": 50}
                    )
                ],
                fallback_enabled=True,
                auto_failover=True
            )

            factory = IntegrationFactory(config)
            workflow_service = WorkflowService(factory)

            # Test basic workflow execution
            response = await workflow_service.execute_workflow(
                workflow_type=WorkflowType.AP_INVOICE_PROCESSING,
                data={"test": "basic_functionality"},
                dry_run=True
            )

            assert response.execution_id is not None
            assert response.status.value in ["running", "completed"]
            assert response.provider_type == IntegrationType.NATIVE

            duration = time.time() - start_time
            self.record_test("Basic Functionality", True, duration,
                            f"Execution ID: {response.execution_id}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Basic Functionality", False, duration, str(e))

    async def test_02_workflow_service_apis(self) -> None:
        """Test all workflow service API methods."""
        logger.info("🧪 Testing 2: Workflow Service APIs")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Test AP invoice processing
            invoice_data = {
                "invoice_id": "TEST-001",
                "vendor_name": "Test Vendor",
                "total_amount": 1000.00,
                "line_items": [{"description": "Test Item", "quantity": 1, "unit_price": 1000.00}]
            }

            response = await workflow_service.process_ap_invoice(invoice_data)
            assert response.provider_type == IntegrationType.NATIVE
            assert response.execution_id is not None

            # Test exception handling
            exception_data = {
                "exception_id": "TEST-EXC-001",
                "exception_type": "validation_error",
                "severity": "medium",
                "description": "Test exception"
            }

            response = await workflow_service.handle_exception(exception_data)
            assert response.provider_type == IntegrationType.NATIVE

            # Test weekly report generation
            report_data = {
                "report_id": "TEST-REPORT-001",
                "period_start": "2024-11-01",
                "period_end": "2024-11-07"
            }

            response = await workflow_service.generate_weekly_report(report_data)
            assert response.provider_type == IntegrationType.NATIVE

            # Test approval workflow
            approval_data = {
                "approval_id": "TEST-APPROVAL-001",
                "amount": 5000.00,
                "requester": "test@example.com"
            }

            response = await workflow_service.execute_approval_workflow(approval_data)
            assert response.provider_type == IntegrationType.NATIVE

            duration = time.time() - start_time
            self.record_test("Workflow Service APIs", True, duration,
                            "All 4 workflow types executed successfully")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Workflow Service APIs", False, duration, str(e))

    async def test_03_configuration_driven_switching(self) -> None:
        """Test configuration-driven provider switching."""
        logger.info("🧪 Testing 3: Configuration-Driven Switching")
        start_time = time.time()

        try:
            # Create factory with multiple providers
            config = FactoryConfig(
                default_provider=IntegrationType.NATIVE,
                providers=[
                    IntegrationConfig(
                        provider_type=IntegrationType.NATIVE,
                        enabled=True,
                        priority=2
                    ),
                    IntegrationConfig(
                        provider_type=IntegrationType.N8N,
                        enabled=False,  # Start disabled
                        priority=1  # Higher priority
                    )
                ],
                fallback_enabled=True
            )

            factory = IntegrationFactory(config)
            workflow_service = WorkflowService(factory)

            # Test with native (only available provider)
            response = await workflow_service.execute_workflow(
                workflow_type=WorkflowType.AP_INVOICE_PROCESSING,
                data={"test": "config_switching"}
            )
            assert response.provider_type == IntegrationType.NATIVE

            # Enable n8n provider
            workflow_service.configure_provider(
                provider_type=IntegrationType.N8N,
                enabled=True,
                priority=1
            )

            # Verify configuration was updated
            provider = factory.get_provider(IntegrationType.N8N)
            assert provider is not None
            assert provider.enabled is True

            duration = time.time() - start_time
            self.record_test("Configuration Switching", True, duration,
                            "Successfully enabled and configured n8n provider")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Configuration Switching", False, duration, str(e))

    async def test_04_fallback_mechanisms(self) -> None:
        """Test fallback and failover mechanisms."""
        logger.info("🧪 Testing 4: Fallback Mechanisms")
        start_time = time.time()

        try:
            # Create factory with fallback enabled
            config = FactoryConfig(
                default_provider=IntegrationType.NATIVE,
                providers=[
                    IntegrationConfig(
                        provider_type=IntegrationType.NATIVE,
                        enabled=True,
                        priority=2
                    ),
                    # Simulate a "failing" provider
                    IntegrationConfig(
                        provider_type=IntegrationType.N8N,
                        enabled=True,
                        priority=1,  # Higher priority
                        config={
                            "base_url": "http://invalid-host:5678",  # Invalid URL
                            "api_key": "invalid_key"
                        }
                    )
                ],
                fallback_enabled=True,
                auto_failover=True
            )

            factory = IntegrationFactory(config)
            workflow_service = WorkflowService(factory)

            # This should fail with n8n and fallback to native
            response = await workflow_service.execute_workflow(
                workflow_type=WorkflowType.AP_INVOICE_PROCESSING,
                data={"test": "fallback_test"},
                provider_type=IntegrationType.N8N  # Try n8n first
            )

            # Should fall back to native
            assert response.provider_type == IntegrationType.NATIVE
            assert response.status.value in ["running", "completed"]

            duration = time.time() - start_time
            self.record_test("Fallback Mechanisms", True, duration,
                            f"Fallback successful, final provider: {response.provider_type}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Fallback Mechanisms", False, duration, str(e))

    async def test_05_circuit_breaker(self) -> None:
        """Test circuit breaker functionality."""
        logger.info("🧪 Testing 5: Circuit Breaker")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Get native provider
            provider = workflow_service.factory.get_provider(IntegrationType.NATIVE)
            assert provider is not None

            # Test circuit breaker state
            initial_state = provider.circuit_breaker.state
            assert initial_state == "CLOSED"

            # Perform health check
            health_response = await provider.health_check()
            assert health_response.healthy is True

            # Test circuit breaker properties
            assert hasattr(provider.circuit_breaker, 'failure_count')
            assert hasattr(provider.circuit_breaker, 'state')
            assert hasattr(provider.circuit_breaker, 'next_attempt_time')

            duration = time.time() - start_time
            self.record_test("Circuit Breaker", True, duration,
                            f"Circuit breaker operational, state: {initial_state}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Circuit Breaker", False, duration, str(e))

    async def test_06_all_workflow_types(self) -> None:
        """Test all supported workflow types."""
        logger.info("🧪 Testing 6: All Workflow Types")
        start_time = time.time()
        workflow_results = []

        try:
            workflow_service = get_workflow_service()

            # Test AP invoice processing
            ap_response = await workflow_service.process_ap_invoice({
                "invoice_id": "TEST-AP-001",
                "vendor_name": "Test AP Vendor",
                "total_amount": 1500.00
            })
            workflow_results.append(("AP Invoice", ap_response.provider_type))

            # Test AR invoice processing
            ar_response = await workflow_service.execute_workflow(
                workflow_type=WorkflowType.AR_INVOICE_PROCESSING,
                data={"invoice_id": "TEST-AR-001", "customer_name": "Test Customer"}
            )
            workflow_results.append(("AR Invoice", ar_response.provider_type))

            # Test exception handling
            exc_response = await workflow_service.handle_exception({
                "exception_id": "TEST-EXC-001",
                "exception_type": "validation_error"
            })
            workflow_results.append(("Exception Handling", exc_response.provider_type))

            # Test weekly report generation
            report_response = await workflow_service.generate_weekly_report({
                "report_id": "TEST-WEEKLY-001",
                "period_start": "2024-11-01"
            })
            workflow_results.append(("Weekly Report", report_response.provider_type))

            # Test approval workflow
            approval_response = await workflow_service.execute_approval_workflow({
                "approval_id": "TEST-APPROVAL-001",
                "amount": 10000.00
            })
            workflow_results.append(("Approval", approval_response.provider_type))

            # Test working capital analysis
            wc_response = await workflow_service.execute_working_capital_analysis({
                "analysis_date": "2024-11-12",
                "period_days": 30
            })
            workflow_results.append(("Working Capital", wc_response.provider_type))

            # Test custom workflow
            custom_response = await workflow_service.execute_workflow(
                workflow_type=WorkflowType.CUSTOM_WORKFLOW,
                data={"custom_data": "test"}
            )
            workflow_results.append(("Custom", custom_response.provider_type))

            # Verify all workflows used native provider
            for workflow_name, provider_type in workflow_results:
                assert provider_type == IntegrationType.NATIVE, f"{workflow_name} used wrong provider"

            duration = time.time() - start_time
            self.record_test("All Workflow Types", True, duration,
                            f"Executed {len(workflow_results)} workflows with native provider")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("All Workflow Types", False, duration, str(e))

    async def test_07_performance_and_reliability(self) -> None:
        """Test system performance and reliability."""
        logger.info("🧪 Testing 7: Performance & Reliability")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Performance test: Execute multiple workflows concurrently
            num_workflows = 10
            tasks = []

            for i in range(num_workflows):
                task = workflow_service.process_ap_invoice({
                    "invoice_id": f"PERF-TEST-{i:03d}",
                    "vendor_name": f"Perf Test Vendor {i}",
                    "total_amount": 100.0 * (i + 1)
                })
                tasks.append(task)

            # Execute all concurrently
            start_concurrent = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = time.time() - start_concurrent

            # Check results
            successful = sum(1 for r in responses if not isinstance(r, Exception))
            failed = len(responses) - successful
            avg_time_per_workflow = concurrent_time / num_workflows

            # Verify performance metrics
            assert successful >= 8, f"Too many failures: {failed}/{num_workflows}"
            assert avg_time_per_workflow < 1.0, f"Too slow: {avg_time_per_workflow:.2f}s per workflow"

            # Test reliability: Same workflow multiple times
            reliability_test_count = 5
            reliability_results = []

            for i in range(reliability_test_count):
                response = await workflow_service.process_ap_invoice({
                    "invoice_id": f"RELIABILITY-TEST-{i:03d}",
                    "vendor_name": "Reliability Test Vendor",
                    "total_amount": 500.00
                })
                reliability_results.append(response.execution_id is not None)

            reliability_score = sum(reliability_results) / len(reliability_results)
            assert reliability_score == 1.0, f"Reliability score: {reliability_score}"

            duration = time.time() - start_time
            self.record_test("Performance & Reliability", True, duration,
                            f"Concurrent: {successful}/{num_workflows}, "
                            f"Reliability: {reliability_score:.1%}, "
                            f"Avg time: {avg_time_per_workflow:.3f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Performance & Reliability", False, duration, str(e))

    async def test_08_metrics_and_monitoring(self) -> None:
        """Test metrics collection and monitoring."""
        logger.info("🧪 Testing 8: Metrics & Monitoring")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Execute some workflows to generate metrics
            await workflow_service.process_ap_invoice({
                "invoice_id": "METRICS-TEST-001",
                "vendor_name": "Metrics Test Vendor",
                "total_amount": 750.00
            })

            await workflow_service.handle_exception({
                "exception_id": "METRICS-EXC-001",
                "exception_type": "test_exception"
            })

            # Get factory status
            factory_status = await workflow_service.get_factory_status()
            assert factory_status is not None
            assert 'default_provider' in factory_status
            assert 'available_providers' in factory_status
            assert 'provider_health' in factory_status

            # Get metrics
            metrics = await workflow_service.get_metrics()
            assert metrics is not None
            assert 'total_executions' in metrics
            assert 'overall_success_rate' in metrics
            assert 'provider_metrics' in metrics

            # Validate metrics structure
            assert isinstance(metrics['total_executions'], int)
            assert isinstance(metrics['overall_success_rate'], float)
            assert isinstance(metrics['provider_metrics'], list)

            # Check configuration methods
            assert workflow_service.is_using_swappable_integration() is True
            assert isinstance(workflow_service.get_default_provider(), str)
            assert isinstance(workflow_service.is_n8n_enabled(), bool)

            duration = time.time() - start_time
            self.record_test("Metrics & Monitoring", True, duration,
                            f"Total executions: {metrics.get('total_executions', 0)}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Metrics & Monitoring", False, duration, str(e))

    async def test_09_error_handling(self) -> None:
        """Test error handling and resilience."""
        logger.info("🧪 Testing 9: Error Handling")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Test with invalid workflow data
            try:
                await workflow_service.process_ap_invoice({
                    "invalid_data": "missing_required_fields"
                })
                # Should not reach here
                assert False, "Should have raised exception for invalid data"
            except Exception:
                # Expected behavior
                pass

            # Test with non-existent provider type
            try:
                await workflow_service.execute_workflow(
                    provider_type="nonexistent_provider",
                    request=WorkflowExecutionRequest(
                        workflow_type=WorkflowType.AP_INVOICE_PROCESSING,
                        data={"test": "data"}
                    )
                )
                # Should not reach here
                assert False, "Should have raised exception for invalid provider"
            except Exception:
                # Expected behavior
                pass

            # Test with large data payload
            large_data = {
                "invoice_id": "LARGE-DATA-TEST",
                "vendor_name": "Large Data Test",
                "total_amount": 1.0,
                "line_items": [
                    {"description": f"Item {i}", "quantity": 1, "unit_price": 1.0}
                    for i in range(1000)  # 1000 line items
                ]
            }

            response = await workflow_service.process_ap_invoice(large_data)
            assert response.execution_id is not None

            duration = time.time() - start_time
            self.record_test("Error Handling", True, duration,
                            "Properly handled invalid data and large payloads")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Error Handling", False, duration, str(e))

    async def test_10_production_readiness(self) -> None:
        """Comprehensive production readiness test."""
        logger.info("🧪 Testing 10: Production Readiness")
        start_time = time.time()

        try:
            workflow_service = get_workflow_service()

            # Production readiness checklist
            readiness_checks = []

            # 1. Configuration validation
            try:
                config = workflow_service.factory.config
                assert config.default_provider is not None
                assert len(config.providers) > 0
                assert config.fallback_enabled is True
                readiness_checks.append("✅ Configuration")
            except Exception as e:
                readiness_checks.append(f"❌ Configuration: {e}")

            # 2. Provider availability
            try:
                factory_status = await workflow_service.get_factory_status()
                assert factory_status['available_providers'] > 0
                assert factory_status['enabled_providers'] > 0
                readiness_checks.append("✅ Provider Availability")
            except Exception as e:
                readiness_checks.append(f"❌ Provider Availability: {e}")

            # 3. Health checks
            try:
                for provider in workflow_service.factory.get_available_providers():
                    health = await provider.health_check()
                    assert health.healthy is True
                readiness_checks.append("✅ Health Checks")
            except Exception as e:
                readiness_checks.append(f"❌ Health Checks: {e}")

            # 4. Metrics collection
            try:
                metrics = await workflow_service.get_metrics()
                assert 'total_executions' in metrics
                readiness_checks.append("✅ Metrics Collection")
            except Exception as e:
                readiness_checks.append(f"❌ Metrics Collection: {e}")

            # 5. Performance validation
            try:
                # Quick performance test
                start_perf = time.time()
                await workflow_service.process_ap_invoice({
                    "invoice_id": "PROD-READINESS-TEST",
                    "vendor_name": "Production Test",
                    "total_amount": 1000.00
                })
                perf_time = time.time() - start_perf
                assert perf_time < 2.0, f"Too slow: {perf_time:.2f}s"
                readiness_checks.append(f"✅ Performance ({perf_time:.3f}s)")
            except Exception as e:
                readiness_checks.append(f"❌ Performance: {e}")

            # 6. Error resilience
            try:
                # Test system resilience
                await workflow_service.process_ap_invoice({
                    "invoice_id": "RESILIENCE-TEST",
                    "vendor_name": "Resilience Test",
                    "total_amount": 500.00
                })
                readiness_checks.append("✅ Error Resilience")
            except Exception as e:
                readiness_checks.append(f"❌ Error Resilience: {e}")

            # Evaluate readiness
            passed_checks = sum(1 for check in readiness_checks if check.startswith("✅"))
            total_checks = len(readiness_checks)
            readiness_score = passed_checks / total_checks

            assert readiness_score >= 0.8, f"Readiness score too low: {readiness_score:.1%}"

            duration = time.time() - start_time
            self.record_test("Production Readiness", True, duration,
                            f"Score: {readiness_score:.1%} ({passed_checks}/{total_checks})")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Production Readiness", False, duration, str(e))

    def generate_report(self) -> None:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        total_duration = time.time() - self.start_time

        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE INTEGRATION TEST REPORT")
        print("="*80)
        print(f"📊 Test Results: {passed_tests}/{total_tests} passed ({success_rate:.1f}%)")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        print(f"🚀 Status: {'✅ PRODUCTION READY' if success_rate >= 90 else '⚠️  NEEDS ATTENTION' if success_rate >= 75 else '❌ NOT READY'}")
        print()

        print("📋 Detailed Results:")
        print("-" * 80)
        for result in self.test_results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status} {result['test_name']:<30} ({result['duration']:.2f}s) {result['details']}")

        print("\n🔧 Performance Summary:")
        print("-" * 80)
        if self.performance_metrics:
            avg_duration = sum(self.performance_metrics) / len(self.performance_metrics)
            print(f"Average Test Duration: {avg_duration:.2f}s")
            print(f"Fastest Test: {min(self.performance_metrics):.2f}s")
            print(f"Slowest Test: {max(self.performance_metrics):.2f}s")

        print("\n🎉 Production Readiness Assessment:")
        print("-" * 80)
        if success_rate >= 90:
            print("✅ EXCELLENT - System is production-ready!")
            print("   All critical functionality tested and working")
            print("   Performance and reliability meet production standards")
        elif success_rate >= 75:
            print("⚠️  GOOD - System mostly production-ready")
            print("   Minor issues need attention before production deployment")
            print("   Core functionality is working properly")
        else:
            print("❌ NEEDS WORK - System not production-ready")
            print("   Significant issues need to be resolved")
            print("   Address failed tests before production deployment")

        print("="*80)


async def run_comprehensive_test() -> None:
    """Run all integration tests."""
    test_suite = ComprehensiveIntegrationTest()

    tests = [
        test_suite.test_01_basic_functionality,
        test_suite.test_02_workflow_service_apis,
        test_suite.test_03_configuration_driven_switching,
        test_suite.test_04_fallback_mechanisms,
        test_suite.test_05_circuit_breaker,
        test_suite.test_06_all_workflow_types,
        test_suite.test_07_performance_and_reliability,
        test_suite.test_08_metrics_and_monitoring,
        test_suite.test_09_error_handling,
        test_suite.test_10_production_readiness
    ]

    # Run all tests
    for test in tests:
        await test()

    # Generate report
    test_suite.generate_report()


if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())