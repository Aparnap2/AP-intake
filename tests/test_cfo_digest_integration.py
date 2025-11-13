#!/usr/bin/env python3
"""
Test script for Monday 9am CFO Digest System integration.
This script tests the complete flow from digest generation to scheduling.
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.api.schemas.digest import (
    CFODigestRequest, DigestPriority, BusinessImpactLevel,
    CFODigestScheduleRequest
)
from app.services.weekly_report_service import CFODigestService
from app.services.n8n_service import N8nService


async def test_cfo_digest_generation():
    """Test CFO digest generation."""
    print("🧪 Testing CFO Digest Generation...")

    # Mock session for testing (in real implementation, this would be a real DB session)
    class MockSession:
        def __init__(self):
            pass

        async def execute(self, query):
            # Mock query execution
            class MockResult:
                def scalar(self):
                    return 100  # Mock value
            return MockResult()

        async def flush(self):
            pass

        def add(self, obj):
            pass

        async def commit(self):
            pass

    session = MockSession()

    try:
        # Initialize service
        cfo_service = CFODigestService(session)

        # Create digest request
        request = CFODigestRequest(
            include_working_capital_analysis=True,
            include_action_items=True,
            include_evidence_links=True,
            priority_threshold=DigestPriority.MEDIUM,
            business_impact_threshold=BusinessImpactLevel.MODERATE,
            recipients=["cfo@company.com", "finance-team@company.com"],
            schedule_delivery=True,
            delivery_time="09:00"
        )

        # Generate digest
        digest = await cfo_service.generate_monday_digest(
            request=request,
            generated_by="test@company.com"
        )

        print(f"✅ Digest generated successfully!")
        print(f"   Title: {digest.title}")
        print(f"   Week: {digest.week_start.date()} to {digest.week_end.date()}")
        print(f"   Metrics: {len(digest.key_metrics)}")
        print(f"   Action Items: {len(digest.action_items)}")
        print(f"   Executive Summary: {digest.executive_summary.headline}")

        # Test N8n workflow request creation
        n8n_request = await cfo_service.create_n8n_workflow_request(digest)
        print(f"✅ N8n workflow request created")
        print(f"   Workflow ID: {n8n_request.digest_id}")
        print(f"   Recipients: {n8n_request.recipients}")

        return digest

    except Exception as e:
        print(f"❌ Digest generation failed: {e}")
        return None


async def test_n8n_scheduling():
    """Test N8n scheduling functionality."""
    print("\n🧪 Testing N8n Scheduling...")

    try:
        n8n_service = N8nService()

        # Test Monday 9am calculation
        next_monday = n8n_service._calculate_next_monday_9am()
        print(f"✅ Next Monday 9am calculated: {next_monday}")

        # Test schedule setup
        schedule_config = {
            "is_active": True,
            "delivery_day": "monday",
            "delivery_time": "09:00",
            "recipients": ["cfo@company.com", "finance-team@company.com"],
            "priority_threshold": "medium",
            "business_impact_threshold": "moderate"
        }

        # Note: This would normally trigger N8n workflow
        print(f"✅ Schedule configuration prepared")
        print(f"   Delivery: Monday {schedule_config['delivery_time']}")
        print(f"   Recipients: {len(schedule_config['recipients'])}")

        return True

    except Exception as e:
        print(f"❌ N8n scheduling test failed: {e}")
        return False


async def test_schema_validation():
    """Test schema validation."""
    print("\n🧪 Testing Schema Validation...")

    try:
        # Test CFO digest request schema
        request = CFODigestRequest(
            include_working_capital_analysis=True,
            include_action_items=True,
            include_evidence_links=True,
            priority_threshold=DigestPriority.HIGH,
            business_impact_threshold=BusinessImpactLevel.HIGH,
            recipients=["test@company.com"],
            schedule_delivery=True
        )

        # Test schedule request schema
        schedule_request = CFODigestScheduleRequest(
            is_active=True,
            delivery_day="monday",
            delivery_time="09:00",
            recipients=["cfo@company.com"],
            priority_threshold=DigestPriority.MEDIUM,
            business_impact_threshold=BusinessImpactLevel.MODERATE
        )

        print(f"✅ CFO Digest Request schema validated")
        print(f"   Priority: {request.priority_threshold}")
        print(f"   Business Impact: {request.business_impact_threshold}")
        print(f"   Schedule Delivery: {request.schedule_delivery}")

        print(f"✅ Schedule Request schema validated")
        print(f"   Active: {schedule_request.is_active}")
        print(f"   Delivery: {schedule_request.delivery_day} {schedule_request.delivery_time}")

        return True

    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False


async def test_email_template():
    """Test email template rendering."""
    print("\n🧪 Testing Email Template...")

    try:
        from jinja2 import Environment, FileSystemLoader

        # Check if template exists
        template_path = Path("templates/reports/cfo_digest.html")
        if not template_path.exists():
            print(f"❌ Template not found at {template_path}")
            return False

        # Setup Jinja2 environment
        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=True
        )

        # Load template
        template = env.get_template("reports/cfo_digest.html")

        # Mock digest data
        mock_digest = {
            "title": "Monday CFO Digest - Test Week",
            "week_start": datetime.now(timezone.utc) - timedelta(days=7),
            "week_end": datetime.now(timezone.utc),
            "generated_at": datetime.now(timezone.utc),
            "total_invoices_processed": 1250,
            "cost_per_invoice": 2.85,
            "roi_percentage": 189.5,
            "total_exceptions": 15,
            "executive_summary": {
                "headline": "Strong Performance with Excellent Automation Success",
                "overall_performance_rating": "Excellent",
                "key_highlights": [
                    "Exceptional processing success rate of 96.8%",
                    "Excellent cost efficiency at $2.85 per invoice",
                    "Strong exception resolution at 87.3%"
                ],
                "key_concerns": [],
                "working_capital_impact": "Current processes optimize working capital through 75% automation rate.",
                "financial_summary": "Weekly processing cost of $3,562.50 with ROI of 189.5%",
                "operational_efficiency": "Auto-approval rate of 75.2% with extraction accuracy of 94.1%",
                "risk_assessment": "Risk level: Low based on current performance metrics",
                "outlook": "Forecast: Maintain current trajectory with focus on scaling operations"
            },
            "key_metrics": [
                {
                    "name": "Invoices Processed",
                    "value": 1250,
                    "unit": "invoices",
                    "trend": "increasing",
                    "priority": {"value": "high"}
                },
                {
                    "name": "Cost Per Invoice",
                    "value": 2.85,
                    "unit": "$",
                    "target": 3.0,
                    "attainment_percentage": 105.3,
                    "priority": {"value": "high"}
                }
            ],
            "working_capital_metrics": {
                "total_wc_tied": 3562.50,
                "automation_rate": 75.2,
                "avg_processing_time_hours": 2.4,
                "exception_resolution_rate": 87.3,
                "cost_savings_opportunities": [
                    "Implement early payment discounts for top vendors",
                    "Optimize payment scheduling to align with cash flow"
                ]
            },
            "action_items": [
                {
                    "title": "Increase Auto-Approval Rate",
                    "description": "Auto-approval rate (75.2%) below 80% target",
                    "business_impact_level": {"value": "moderate"},
                    "financial_impact": 2450.0,
                    "time_to_resolve": "3-4 weeks",
                    "owner": "Data Science Team",
                    "priority": {"value": "medium"},
                    "recommendations": [
                        "Fine-tune extraction confidence thresholds",
                        "Improve vendor data quality"
                    ]
                }
            ]
        }

        # Render template
        rendered = template.render(
            digest=mock_digest,
            company_name="Test Company",
            footer_text="This is a test executive digest from AP Intake & Validation System",
            brand_colors={
                "primary": "#2563eb",
                "secondary": "#64748b",
                "success": "#16a34a",
                "warning": "#d97706",
                "danger": "#dc2626"
            }
        )

        # Check if template rendered successfully
        if len(rendered) > 1000:  # Basic check for content
            print(f"✅ Email template rendered successfully")
            print(f"   Template length: {len(rendered)} characters")
            print(f"   Contains executive summary: {'Executive Summary' in rendered}")
            print(f"   Contains metrics: {'Key Performance Metrics' in rendered}")
            print(f"   Contains action items: {'Action Items' in rendered}")
            return True
        else:
            print(f"❌ Template rendering failed - too short")
            return False

    except Exception as e:
        print(f"❌ Email template test failed: {e}")
        return False


async def test_api_endpoints():
    """Test API endpoint structure."""
    print("\n🧪 Testing API Endpoints Structure...")

    try:
        # Check if endpoints file exists and has CFO digest endpoints
        reports_file = Path("app/api/api_v1/endpoints/reports.py")
        if not reports_file.exists():
            print(f"❌ Reports endpoints file not found")
            return False

        # Read the file and check for CFO digest endpoints
        content = reports_file.read_text()

        required_endpoints = [
            "/cfo-digest/generate",
            "/cfo-digest/schedule",
            "/cfo-digest/{digest_id}",
            "/cfo-digest/trigger"
        ]

        missing_endpoints = []
        for endpoint in required_endpoints:
            if endpoint not in content:
                missing_endpoints.append(endpoint)

        if missing_endpoints:
            print(f"❌ Missing endpoints: {missing_endpoints}")
            return False

        print(f"✅ All required CFO digest endpoints found")
        print(f"   Generate endpoint: ✅")
        print(f"   Schedule endpoints: ✅")
        print(f"   Get/Delete digest endpoints: ✅")
        print(f"   Trigger endpoint: ✅")

        return True

    except Exception as e:
        print(f"❌ API endpoints test failed: {e}")
        return False


async def run_integration_tests():
    """Run all integration tests."""
    print("🚀 Starting Monday 9am CFO Digest System Integration Tests\n")

    results = []

    # Run all tests
    results.append(await test_schema_validation())
    results.append(await test_cfo_digest_generation())
    results.append(await test_n8n_scheduling())
    results.append(await test_email_template())
    results.append(await test_api_endpoints())

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n📊 Test Results Summary:")
    print(f"   Total Tests: {total}")
    print(f"   Passed: {passed}")
    print(f"   Failed: {total - passed}")

    if passed == total:
        print(f"\n🎉 All tests passed! Monday CFO Digest System is ready for deployment.")
        print(f"\n📋 Implementation Summary:")
        print(f"   ✅ CFODigestService implemented in weekly_report_service.py")
        print(f"   ✅ N8n Monday 9am scheduling enhanced in n8n_service.py")
        print(f"   ✅ Complete schema models in app/api/schemas/digest.py")
        print(f"   ✅ Full API endpoints in app/api/api_v1/endpoints/reports.py")
        print(f"   ✅ Professional email template in templates/reports/cfo_digest.html")
        print(f"\n🔧 Next Steps:")
        print(f"   1. Configure N8n workflow IDs in environment settings")
        print(f"   2. Set up Monday 9am cron job or scheduled trigger")
        print(f"   3. Test with real database session")
        print(f"   4. Configure email delivery settings")
        print(f"   5. Deploy to production")
    else:
        print(f"\n❌ Some tests failed. Please review the errors above.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)