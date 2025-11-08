#!/usr/bin/env python3
"""
Test script to verify OpenRouter LLM integration.
"""

import asyncio
import logging
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.llm_service import LLMService
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_openrouter_integration():
    """Test OpenRouter LLM integration."""
    print("🧪 Testing OpenRouter LLM Integration")
    print("=" * 50)

    # Display configuration
    print(f"📋 Configuration:")
    print(f"  Provider: {settings.LLM_PROVIDER}")
    print(f"  Model: {settings.LLM_MODEL}")
    print(f"  Base URL: {settings.OPENROUTER_BASE_URL}")
    print(f"  API Key configured: {'✅ Yes' if settings.OPENROUTER_API_KEY else '❌ No'}")
    print(f"  App Name: {settings.OPENROUTER_APP_NAME}")
    print()

    # Initialize LLM service
    print("🔧 Initializing LLM service...")
    llm_service = LLMService()
    print()

    # Test connection
    print("🌐 Testing connection...")
    connection_result = await llm_service.test_connection()

    if connection_result["status"] == "success":
        print("✅ Connection successful!")
        print(f"  Response: {connection_result['test_response']}")
        print(f"  Response time: {connection_result['response_time']}")
        print(f"  Base URL: {connection_result['base_url']}")
    else:
        print("❌ Connection failed!")
        print(f"  Error: {connection_result['message']}")
        return

    print()

    # Test basic functionality
    print("🤖 Testing basic LLM functionality...")
    try:
        test_prompt = "Extract invoice information from this text: Invoice #12345 from ABC Corp for $100.00 due on 2024-01-15."

        # We'll call the internal LLM method directly
        response = await llm_service._call_llm_with_retry(test_prompt)

        print("✅ LLM API call successful!")
        print(f"  Response type: {type(response)}")
        if isinstance(response, dict):
            print(f"  Response keys: {list(response.keys())}")
        else:
            print(f"  Response: {response}")

    except Exception as e:
        print(f"❌ LLM API call failed: {e}")

    print()

    # Test low-confidence patching
    print("🔧 Testing low-confidence field patching...")
    try:
        sample_extraction = {
            "header": {
                "vendor_name": "ABC Corpration",  # Typo - should be "Corporation"
                "invoice_no": "INV-00123",
                "total_amount": 150.00
            },
            "lines": [
                {"description": "Office Supplies", "amount": 75.00},
                {"description": "Cleaning Service", "amount": 75.00}
            ],
            "confidence": {
                "header": {
                    "vendor_name": 0.7,  # Low confidence
                    "invoice_no": 0.95,
                    "total_amount": 0.9,
                    "overall": 0.85
                },
                "lines": [0.95, 0.95]
            },
            "overall_confidence": 0.87
        }

        patched_result = await llm_service.patch_low_confidence_fields(
            sample_extraction,
            0.87
        )

        print("✅ Low-confidence patching successful!")
        print(f"  Original vendor: {sample_extraction['header']['vendor_name']}")
        print(f"  Patched vendor: {patched_result['header']['vendor_name']}")
        print(f"  Original confidence: {sample_extraction['overall_confidence']}")
        print(f"  Patched confidence: {patched_result['overall_confidence']}")

    except Exception as e:
        print(f"❌ Low-confidence patching failed: {e}")

    print()

    # Display usage statistics
    print("📊 Usage Statistics:")
    usage_stats = llm_service.get_usage_stats()
    for key, value in usage_stats.items():
        print(f"  {key}: {value}")

    print()
    print("🎉 OpenRouter integration test completed!")


if __name__ == "__main__":
    asyncio.run(test_openrouter_integration())