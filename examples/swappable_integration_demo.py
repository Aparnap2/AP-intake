"""
Demonstration of the swappable integration system.
Shows how to use different providers and switch between them at runtime.
"""

import asyncio
import logging
from typing import Dict, Any

from app.services.integration_factory import (
    IntegrationFactory,
    IntegrationType,
    IntegrationConfig,
    FactoryConfig
)
from app.services.workflow_service import WorkflowService, get_workflow_service
from app.schemas.integration_schemas import (
    WorkflowType,
    WorkflowExecutionRequest
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_basic_usage():
    """Demonstrate basic usage of the swappable integration system."""
    print("🚀 Basic Swappable Integration Demo")
    print("=" * 50)

    # Get the global workflow service
    workflow_service = get_workflow_service()

    # Check configuration
    print(f"Default Provider: {workflow_service.get_default_provider()}")
    print(f"Using Swappable Integration: {workflow_service.is_using_swappable_integration()}")
    print(f"N8N Enabled: {workflow_service.is_n8n_enabled()}")
    print()

    # Process an AP invoice
    invoice_data = {
        "invoice_id": "INV-2024-001",
        "vendor_name": "Office Supplies Co",
        "total_amount": 1250.00,
        "due_date": "2024-12-15",
        "line_items": [
            {"description": "Office Supplies", "quantity": 10, "unit_price": 125.00}
        ]
    }

    try:
        print("📄 Processing AP Invoice...")
        response = await workflow_service.process_ap_invoice(invoice_data)

        print(f"✅ Success!")
        print(f"   Execution ID: {response.execution_id}")
        print(f"   Status: {response.status}")
        print(f"   Provider: {response.provider_type}")
        print(f"   Duration: {response.duration_ms}ms")
        if response.result:
            print(f"   Result: {response.result.get('processing_result', 'N/A')}")
        print()

    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        print()


async def demo_provider_switching():
    """Demonstrate switching between providers."""
    print("🔄 Provider Switching Demo")
    print("=" * 50)

    # Create custom factory configuration
    config = FactoryConfig(
        default_provider=IntegrationType.NATIVE,
        providers=[
            IntegrationConfig(
                provider_type=IntegrationType.NATIVE,
                enabled=True,
                priority=1,
                config={"max_concurrent_workflows": 50}
            ),
            IntegrationConfig(
                provider_type=IntegrationType.N8N,
                enabled=False,  # Start disabled
                priority=2,
                config={
                    "base_url": "http://localhost:5678",
                    "api_key": "demo_key"
                }
            )
        ],
        fallback_enabled=True,
        auto_failover=True
    )

    # Create factory with custom config
    factory = IntegrationFactory(config)
    workflow_service = WorkflowService(factory)

    print("Initial Configuration:")
    factory_status = await workflow_service.get_factory_status()
    print(f"  Available Providers: {factory_status['available_providers']}")
    print(f"  Default Provider: {factory_status['default_provider']}")
    print()

    # Execute workflow with native provider
    invoice_data = {
        "invoice_id": "INV-2024-002",
        "vendor_name": "Tech Supplies Inc",
        "total_amount": 2500.00
    }

    print("📋 Processing with Native Provider...")
    response = await workflow_service.process_ap_invoice(invoice_data)
    print(f"   Used Provider: {response.provider_type}")
    print()

    # Configure n8n provider (simulate enabling it)
    print("⚙️  Enabling N8N Provider...")
    workflow_service.configure_provider(
        provider_type=IntegrationType.N8N,
        enabled=True,
        priority=1  # Higher priority than native
    )

    # Check updated status
    factory_status = await workflow_service.get_factory_status()
    print(f"  Available Providers: {factory_status['available_providers']}")
    print()

    # Execute workflow again (should use n8n if available)
    print("📋 Processing with Configured Provider (should use N8N if available)...")
    try:
        response = await workflow_service.process_ap_invoice(invoice_data)
        print(f"   Used Provider: {response.provider_type}")
        if response.provider_type == IntegrationType.N8N:
            print("   ✅ Successfully switched to N8N provider!")
        else:
            print("   ℹ️  Fell back to Native provider (N8N not available)")
    except Exception as e:
        print(f"   ⚠️  N8N provider failed, falling back: {str(e)}")
        # Try with explicit fallback to native
        response = await workflow_service.process_ap_invoice(
            invoice_data,
            provider_type=IntegrationType.NATIVE
        )
        print(f"   Used fallback provider: {response.provider_type}")

    print()


async def demo_error_handling():
    """Demonstrate error handling and fallback."""
    print("🛡️  Error Handling & Fallback Demo")
    print("=" * 50)

    # Configure factory with fallback enabled
    config = FactoryConfig(
        default_provider=IntegrationType.NATIVE,
        providers=[
            IntegrationConfig(
                provider_type=IntegrationType.NATIVE,
                enabled=True,
                priority=2
            ),
            # Add a "failing" provider (n8n with invalid config)
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

    invoice_data = {
        "invoice_id": "INV-2024-003",
        "vendor_name": "Emergency Supplies",
        "total_amount": 5000.00
    }

    print("📋 Processing with Fallback-Enabled Factory...")
    print("  Primary: N8N (will fail)")
    print("  Fallback: Native (will succeed)")
    print()

    try:
        # This should fail with n8n and fallback to native
        response = await workflow_service.process_ap_invoice(invoice_data)
        print(f"✅ Success with fallback!")
        print(f"   Final Provider: {response.provider_type}")
        print(f"   Status: {response.status}")
        print()

    except Exception as e:
        print(f"❌ All providers failed: {str(e)}")
        print()


async def demo_metrics():
    """Demonstrate metrics collection."""
    print("📊 Metrics Collection Demo")
    print("=" * 50)

    workflow_service = get_workflow_service()

    # Execute multiple workflows to generate metrics
    print("🔄 Executing multiple workflows...")

    tasks = []
    for i in range(5):
        invoice_data = {
            "invoice_id": f"INV-2024-{i:03d}",
            "vendor_name": f"Vendor {i}",
            "total_amount": 100.00 * (i + 1)
        }
        tasks.append(workflow_service.process_ap_invoice(invoice_data))

    # Wait for all to complete
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for r in responses if not isinstance(r, Exception))
    failed = len(responses) - successful

    print(f"  Executed: {len(responses)} workflows")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print()

    # Get metrics
    print("📈 Workflow Metrics:")
    try:
        metrics = await workflow_service.get_metrics()

        print(f"  Total Executions: {metrics['total_executions']}")
        print(f"  Overall Success Rate: {metrics['overall_success_rate']:.1%}")
        print(f"  Most Used Provider: {metrics['most_used_provider']}")
        print(f"  Average Execution Time: {metrics['average_execution_time_ms']:.1f}ms")

        print("\n📋 Provider Breakdown:")
        for provider_metric in metrics['provider_metrics']:
            provider_name = provider_metric['provider_type']
            success_rate = provider_metric['success_rate']
            avg_time = provider_metric['average_execution_time_ms']
            total = provider_metric['total_executions']

            print(f"  {provider_name}:")
            print(f"    Total: {total}")
            print(f"    Success Rate: {success_rate:.1%}")
            print(f"    Avg Time: {avg_time:.1f}ms")

    except Exception as e:
        print(f"  Error getting metrics: {str(e)}")

    print()


async def demo_configuration_options():
    """Demonstrate various configuration options."""
    print("⚙️  Configuration Options Demo")
    print("=" * 50)

    # Show current configuration
    workflow_service = get_workflow_service()

    print("Current Configuration:")
    print(f"  Default Provider: {workflow_service.get_default_provider()}")
    print(f"  Swappable Integration: {workflow_service.is_using_swappable_integration()}")
    print(f"  N8N Enabled: {workflow_service.is_n8n_enabled()}")
    print()

    # Demonstrate different workflow types
    print("🔄 Testing Different Workflow Types:")

    # Exception handling
    exception_data = {
        "exception_id": "EXC-001",
        "exception_type": "validation_error",
        "severity": "medium",
        "description": "Invoice amount validation failed"
    }

    print("\n1. Exception Handling:")
    try:
        response = await workflow_service.handle_exception(exception_data)
        print(f"   ✅ Exception handled with {response.provider_type}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")

    # Weekly report
    report_data = {
        "report_id": "WEEKLY-2024-45",
        "period_start": "2024-11-04",
        "period_end": "2024-11-10",
        "include_charts": True
    }

    print("\n2. Weekly Report Generation:")
    try:
        response = await workflow_service.generate_weekly_report(report_data)
        print(f"   ✅ Report generated with {response.provider_type}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")

    # Approval workflow
    approval_data = {
        "approval_id": "APPROVAL-001",
        "requester": "john.doe@company.com",
        "amount": 15000.00,
        "description": "Q4 Software Licenses"
    }

    print("\n3. Approval Workflow:")
    try:
        response = await workflow_service.execute_approval_workflow(approval_data)
        print(f"   ✅ Approval workflow executed with {response.provider_type}")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")

    print()


async def main():
    """Run all demonstrations."""
    print("🎯 Swappable Integration System Demo")
    print("=" * 60)
    print()

    await demo_basic_usage()
    await demo_provider_switching()
    await demo_error_handling()
    await demo_metrics()
    await demo_configuration_options()

    print("🎉 Demo completed!")
    print("\nKey Takeaways:")
    print("✅ Swappable integration allows runtime provider switching")
    print("✅ Automatic fallback ensures system reliability")
    print("✅ Circuit breaker protects against failing providers")
    print("✅ Metrics provide insights into performance")
    print("✅ Configuration-driven approach enables flexibility")
    print("\nConfiguration Example:")
    print("  # Enable n8n integration")
    print("  export N8N_PROVIDER_ENABLED=true")
    print("  export INTEGRATION_DEFAULT_PROVIDER=n8n")
    print("  export USE_SWAPPABLE_INTEGRATION=true")


if __name__ == "__main__":
    asyncio.run(main())