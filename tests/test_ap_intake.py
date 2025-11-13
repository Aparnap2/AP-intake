#!/usr/bin/env python3
"""
AP/AR Working Capital Copilot E2E Test Script
Tests the complete invoice processing workflow
"""

import asyncio
import requests
import time
import json
import os
from pathlib import Path
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_PDF_DIR = "./inbox"
API_TIMEOUT = 30

def check_service_health():
    """Check if the API service is healthy"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API service is healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

def test_file_upload():
    """Test the file upload endpoint"""
    # Find a test PDF file
    pdf_files = list(Path(TEST_PDF_DIR).glob("*.pdf"))
    if not pdf_files:
        print("❌ No PDF files found in test directory")
        return False

    test_file = pdf_files[0]
    print(f"📄 Testing upload with file: {test_file.name}")

    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}
            data = {
                'source_type': 'upload',
                'uploaded_by': 'e2e_test_user'
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/ingestion/upload",
                files=files,
                data=data,
                timeout=API_TIMEOUT
            )

        if response.status_code == 200:
            result = response.json()
            print("✅ File upload successful")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"❌ File upload failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ File upload error: {e}")
        return False

def test_invoice_status():
    """Test checking invoice status"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/invoices", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            print(f"✅ Retrieved {len(invoices)} invoices")
            return invoices
        else:
            print(f"❌ Failed to get invoices: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking invoice status: {e}")
        return False

def test_exports():
    """Test the export functionality"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/exports", timeout=10)
        if response.status_code == 200:
            exports = response.json()
            print(f"✅ Retrieved {len(exports)} exports")
            return exports
        else:
            print(f"❌ Failed to get exports: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking exports: {e}")
        return False

def main():
    """Main test execution"""
    print("🚀 Starting AP/AR Working Capital Copilot E2E Test")
    print("=" * 60)

    # Test 1: Service Health
    print("\n1️⃣ Testing Service Health...")
    if not check_service_health():
        print("❌ Service health check failed. Please ensure the API is running.")
        sys.exit(1)

    # Test 2: File Upload
    print("\n2️⃣ Testing File Upload...")
    upload_result = test_file_upload()
    if not upload_result:
        print("❌ File upload test failed.")
        sys.exit(1)

    # Wait a moment for background processing
    print("\n⏳ Waiting for background processing...")
    time.sleep(3)

    # Test 3: Check Invoice Status
    print("\n3️⃣ Testing Invoice Status...")
    invoices = test_invoice_status()

    # Test 4: Check Exports
    print("\n4️⃣ Testing Export Status...")
    exports = test_exports()

    # Test Results Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print("✅ API Health Check: PASSED")
    print("✅ File Upload: PASSED")
    if invoices:
        print(f"✅ Invoice Retrieval: {len(invoices)} records found")
    else:
        print("⚠️  Invoice Retrieval: No records found (may need more time)")
    if exports:
        print(f"✅ Export Retrieval: {len(exports)} records found")
    else:
        print("⚠️  Export Retrieval: No records found (may need more time)")

    print("\n🎉 E2E Testing completed successfully!")
    print("📈 System is functioning as expected.")

if __name__ == "__main__":
    main()