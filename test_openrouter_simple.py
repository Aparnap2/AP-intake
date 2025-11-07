#!/usr/bin/env python3
"""
Simple test script to verify OpenRouter LLM integration without full app imports.
"""

import asyncio
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Simple test using OpenAI client directly
async def test_openrouter_direct():
    """Test OpenRouter connection using OpenAI client directly."""
    print("🧪 Testing OpenRouter LLM Integration (Direct)")
    print("=" * 50)

    # Get configuration from environment
    api_key = os.getenv('OPENROUTER_API_KEY', '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')
    model = os.getenv('LLM_MODEL', 'z-ai/glm-4.5-air:free')
    base_url = 'https://openrouter.ai/api/v1'

    print(f"📋 Configuration:")
    print(f"  API Key: {'✅ Configured' if api_key else '❌ Missing'}")
    print(f"  Model: {model}")
    print(f"  Base URL: {base_url}")
    print()

    if not api_key:
        print("❌ OpenRouter API key not configured!")
        return

    try:
        from openai import OpenAI

        # Set up client with OpenRouter
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/ap-team/ap-intake",
                "X-Title": "AP Intake & Validation",
            },
        )

        print("✅ OpenAI client initialized with OpenRouter configuration")

        # Test basic connection
        print("🌐 Testing basic connection...")
        start_time = asyncio.get_event_loop().time()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Respond with 'OK' to confirm connection."}
            ],
            max_tokens=10,
            temperature=0.0,
        )

        response_time = asyncio.get_event_loop().time() - start_time

        print(f"✅ Connection successful!")
        print(f"  Response: {response.choices[0].message.content.strip()}")
        print(f"  Response time: {response_time:.2f}s")

        if response.usage:
            print(f"  Tokens used: {response.usage.total_tokens}")
            print(f"  Prompt tokens: {response.usage.prompt_tokens}")
            print(f"  Completion tokens: {response.usage.completion_tokens}")

        print()

        # Test invoice processing scenario
        print("🤖 Testing invoice data extraction...")
        test_prompt = """
Extract the following information from this invoice text and return as JSON:
- Vendor name
- Invoice number
- Total amount
- Due date

Invoice text: "Invoice #INV-2024-123 from Global Supplies Inc. for $1,250.00 due on January 15, 2024"
"""

        start_time = asyncio.get_event_loop().time()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert invoice data extraction specialist. Always respond with valid JSON."},
                {"role": "user", "content": test_prompt}
            ],
            max_tokens=200,
            temperature=0.1,
        )

        response_time = asyncio.get_event_loop().time() - start_time

        print(f"✅ Invoice extraction test completed!")
        print(f"  Response time: {response_time:.2f}s")
        print(f"  Response: {response.choices[0].message.content.strip()}")

        if response.usage:
            print(f"  Tokens used: {response.usage.total_tokens}")

        print()
        print("🎉 OpenRouter integration test completed successfully!")
        print(f"📊 Model {model} is working correctly with OpenRouter!")

    except ImportError:
        print("❌ OpenAI package not installed!")
        print("Please install with: uv add 'openai>=1.0.0'")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("OpenRouter test failed")

if __name__ == "__main__":
    asyncio.run(test_openrouter_direct())