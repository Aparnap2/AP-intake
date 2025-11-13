#!/usr/bin/env python3
"""
Validate that the integration and reliability testing infrastructure is working.

This script performs basic validation of:
- Test framework imports
- Mock functionality
- Basic test execution
- Error handling
- Result collection
"""

import sys
import asyncio
import logging
import traceback
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        # Test utility imports
        from reliability_testing_utils import FaultInjector, PerformanceMonitor, LoadGenerator
        from reliability_testing_utils import NetworkSimulator, DatabaseSimulator
        print("✅ reliability_testing_utils imports successful")

        # Test integration test imports
        from comprehensive_integration_reliability_test import IntegrationReliabilityTestSuite, TestScenario
        print("✅ comprehensive_integration_reliability_test imports successful")

        # Test ERP integration imports
        from erp_integration_test import ERPIntegrationTester, ERPTestScenario
        print("✅ erp_integration_test imports successful")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        traceback.print_exc()
        return False

def test_fault_injector():
    """Test fault injector functionality."""
    print("\nTesting FaultInjector...")

    try:
        from reliability_testing_utils import FaultInjector, FailureType, Severity

        fault_injector = FaultInjector()

        # Test adding scenarios
        fault_injector.add_scenario("test_scenario", {
            "failure_type": FailureType.NETWORK_TIMEOUT,
            "severity": Severity.HIGH,
            "probability": 0.1
        })

        assert len(fault_injector.active_scenarios) == 1
        print("✅ Fault injection scenario added successfully")

        # Test scenario removal
        fault_injector.remove_scenario("test_scenario")
        assert len(fault_injector.active_scenarios) == 0
        print("✅ Fault injection scenario removed successfully")

        # Test injection summary
        summary = fault_injector.get_injection_summary()
        assert "total_injections" in summary
        print("✅ Fault injection summary generated successfully")

        return True

    except Exception as e:
        print(f"❌ FaultInjector test failed: {e}")
        traceback.print_exc()
        return False

def test_performance_monitor():
    """Test performance monitor functionality."""
    print("\nTesting PerformanceMonitor...")

    try:
        from reliability_testing_utils import PerformanceMonitor

        monitor = PerformanceMonitor()

        # Test monitoring
        monitor.start_monitoring()
        monitor.record_operation(True, 100.0)
        monitor.record_operation(False, 200.0, "TestError")
        monitor.stop_monitoring()

        # Test report generation
        report = monitor.get_performance_report()

        assert "summary" in report
        assert report["summary"]["total_operations"] == 2
        assert report["summary"]["successful_operations"] == 1
        assert report["summary"]["failed_operations"] == 1
        print("✅ Performance monitoring and reporting successful")

        return True

    except Exception as e:
        print(f"❌ PerformanceMonitor test failed: {e}")
        traceback.print_exc()
        return False

async def test_async_components():
    """Test async components."""
    print("\nTesting async components...")

    try:
        from reliability_testing_utils import CircuitBreakerTester

        # Test circuit breaker
        circuit_tester = CircuitBreakerTester(failure_threshold=3)

        # Test successful operations
        await circuit_tester.call(lambda: asyncio.sleep(0.01))
        assert circuit_tester.state == "CLOSED"

        # Test failures
        for i in range(3):
            try:
                await circuit_tester.call(lambda: asyncio.sleep(0.01), should_fail=True)
            except:
                pass

        assert circuit_tester.state == "OPEN"
        print("✅ Circuit breaker functionality working")

        # Test state reporting
        state = circuit_tester.get_state()
        assert "state" in state
        assert "metrics" in state
        print("✅ Circuit breaker state reporting working")

        return True

    except Exception as e:
        print(f"❌ Async components test failed: {e}")
        traceback.print_exc()
        return False

def test_integration_suite():
    """Test integration test suite."""
    print("\nTesting IntegrationReliabilityTestSuite...")

    try:
        from comprehensive_integration_reliability_test import IntegrationReliabilityTestSuite, TestScenario

        suite = IntegrationReliabilityTestSuite()

        # Test configuration
        assert suite.test_config is not None
        assert "erp_test_timeout" in suite.test_config
        print("✅ Integration test suite configuration loaded")

        # Test scenario enums
        scenarios = list(TestScenario)
        assert len(scenarios) >= 8  # Should have at least 8 scenarios
        print(f"✅ {len(scenarios)} test scenarios available")

        return True

    except Exception as e:
        print(f"❌ Integration suite test failed: {e}")
        traceback.print_exc()
        return False

def test_erp_integration():
    """Test ERP integration components."""
    print("\nTesting ERP integration components...")

    try:
        from erp_integration_test import ERPIntegrationTester, ERPTestScenario, ERPSystemType

        tester = ERPIntegrationTester()

        # Test configuration loading
        assert len(tester.configs) >= 2  # Should have QuickBooks and SAP configs
        print("✅ ERP configurations loaded")

        # Test test data loading
        quickbooks_config = tester.configs.get(ERPSystemType.QUICKBOOKS)
        if quickbooks_config:
            assert "vendors" in quickbooks_config.test_data
            assert "bills" in quickbooks_config.test_data
            print("✅ QuickBooks test data loaded")

        return True

    except Exception as e:
        print(f"❌ ERP integration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all validation tests."""
    print("=" * 60)
    print("INTEGRATION AND RELIABILITY TEST INFRASTRUCTURE VALIDATION")
    print("=" * 60)

    tests = [
        ("Module Imports", test_imports),
        ("Fault Injector", test_fault_injector),
        ("Performance Monitor", test_performance_monitor),
        ("Async Components", test_async_components),
        ("Integration Suite", test_integration_suite),
        ("ERP Integration", test_erp_integration),
    ]

    passed_tests = 0
    total_tests = len(tests)

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()

            if result:
                passed_tests += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")

        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print("\n" + "=" * 60)
    print(f"VALIDATION RESULTS: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("🎉 All validation tests passed! The test infrastructure is ready.")
        return True
    else:
        print("⚠️  Some validation tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)