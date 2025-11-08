#!/usr/bin/env python3
"""
Focused API testing script with better error handling.
"""

import json
import os
import sys
import time
import tempfile
import requests
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/api/v1/invoices/upload"
LIST_ENDPOINT = f"{API_BASE_URL}/api/v1/invoices/"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"

# Test files
TEST_INVOICE_PATH = "/home/aparna/Desktop/ap_intake/test_invoices/test_invoice_standard_20251107_175127.pdf"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

def log_info(msg):
    print(f"{Colors.BLUE}[INFO]{Colors.ENDC} {msg}")

def log_success(msg):
    print(f"{Colors.GREEN}[PASS]{Colors.ENDC} {msg}")

def log_failure(msg):
    print(f"{Colors.RED}[FAIL]{Colors.ENDC} {msg}")

def log_warning(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.ENDC} {msg}")

def test_api_health():
    """Test API health endpoint."""
    log_info("Testing API health...")
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                log_success(f"API is healthy - Version: {data.get('version')}")
                return True
            else:
                log_failure(f"API status: {data.get('status')}")
                return False
        else:
            log_failure(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        log_failure(f"Health check error: {e}")
        return False

def test_file_upload_scenarios():
    """Test key file upload scenarios."""
    log_info("Testing key file upload scenarios...")

    if not os.path.exists(TEST_INVOICE_PATH):
        log_failure(f"Test invoice not found: {TEST_INVOICE_PATH}")
        return []

    results = []

    # Test 1: Valid PDF upload
    log_info("Test 1: Valid PDF upload")
    start_time = time.time()
    try:
        with open(TEST_INVOICE_PATH, 'rb') as f:
            files = {'file': (os.path.basename(TEST_INVOICE_PATH), f, 'application/pdf')}
            response = requests.post(API_ENDPOINT, files=files, timeout=60)

        response_time = (time.time() - start_time) * 1000
        status = response.status_code

        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("✅ Valid PDF upload successful")
            try:
                data = response.json()
                invoice_id = data.get('id')
                file_name = data.get('file_name')
                log_info(f"   Invoice ID: {invoice_id}")
                log_info(f"   File name: {file_name}")
                log_info(f"   Status: {data.get('status')}")
                log_info(f"   Workflow state: {data.get('workflow_state')}")
                results.append(("Valid PDF Upload", True, status, response_time, data))
            except:
                log_warning("Could not parse response JSON")
                results.append(("Valid PDF Upload", True, status, response_time, None))
        elif status == 409:
            log_warning("⚠️  Duplicate file detected (this is expected behavior)")
            results.append(("Valid PDF Upload", True, status, response_time, None))
        else:
            log_failure(f"❌ Unexpected status: {status}")
            log_info(f"Response: {response.text[:200]}")
            results.append(("Valid PDF Upload", False, status, response_time, None))

    except requests.exceptions.Timeout:
        log_failure("❌ Upload timed out (>60s)")
        results.append(("Valid PDF Upload", False, None, 60000, None))
    except Exception as e:
        log_failure(f"❌ Upload failed: {e}")
        results.append(("Valid PDF Upload", False, None, None, None))

    # Test 2: Invalid file type
    log_info("Test 2: Invalid file type (text file)")
    start_time = time.time()
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a text file, not a PDF")
            temp_file = f.name

        try:
            with open(temp_file, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                response = requests.post(API_ENDPOINT, files=files, timeout=10)

            response_time = (time.time() - start_time) * 1000
            status = response.status_code

            log_info(f"Status: {status}, Time: {response_time:.2f}ms")

            if status == 400:
                log_success("✅ Invalid file type correctly rejected")
                try:
                    data = response.json()
                    log_info(f"   Error message: {data.get('detail')}")
                    results.append(("Invalid File Type", True, status, response_time, data))
                except:
                    results.append(("Invalid File Type", True, status, response_time, None))
            else:
                log_failure(f"❌ Expected 400, got {status}")
                results.append(("Invalid File Type", False, status, response_time, None))

        finally:
            os.unlink(temp_file)

    except Exception as e:
        log_failure(f"❌ Invalid file type test failed: {e}")
        results.append(("Invalid File Type", False, None, None, None))

    # Test 3: Missing file
    log_info("Test 3: Missing file in request")
    start_time = time.time()
    try:
        response = requests.post(API_ENDPOINT, timeout=10)
        response_time = (time.time() - start_time) * 1000
        status = response.status_code

        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 422:
            log_success("✅ Missing file correctly handled")
            try:
                data = response.json()
                log_info(f"   Error message: {data.get('detail')}")
                results.append(("Missing File", True, status, response_time, data))
            except:
                results.append(("Missing File", True, status, response_time, None))
        else:
            log_failure(f"❌ Expected 422, got {status}")
            results.append(("Missing File", False, status, response_time, None))

    except Exception as e:
        log_failure(f"❌ Missing file test failed: {e}")
        results.append(("Missing File", False, None, None, None))

    return results

def test_other_endpoints():
    """Test other API endpoints."""
    log_info("Testing other API endpoints...")
    results = []

    # Test list invoices
    log_info("Test: List invoices endpoint")
    try:
        start_time = time.time()
        response = requests.get(LIST_ENDPOINT, timeout=10)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            log_success(f"✅ List invoices: {response.status_code} ({response_time:.2f}ms)")
            try:
                data = response.json()
                total_invoices = data.get('total', 0)
                log_info(f"   Total invoices: {total_invoices}")
                results.append(("List Invoices", True, response.status_code, response_time, data))
            except:
                results.append(("List Invoices", True, response.status_code, response_time, None))
        else:
            log_failure(f"❌ List invoices failed: {response.status_code}")
            results.append(("List Invoices", False, response.status_code, response_time, None))

    except Exception as e:
        log_failure(f"❌ List invoices error: {e}")
        results.append(("List Invoices", False, None, None, None))

    # Test API docs
    log_info("Test: API documentation")
    try:
        docs_response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if docs_response.status_code == 200:
            log_success("✅ API docs accessible")
            results.append(("API Docs", True, docs_response.status_code, None, None))
        else:
            log_failure(f"❌ API docs not accessible: {docs_response.status_code}")
            results.append(("API Docs", False, docs_response.status_code, None, None))

    except Exception as e:
        log_failure(f"❌ API docs error: {e}")
        results.append(("API Docs", False, None, None, None))

    return results

def analyze_results(upload_results, other_results):
    """Analyze test results and provide insights."""
    print("\n" + "="*60)
    print("COMPREHENSIVE API TEST ANALYSIS")
    print("="*60)

    all_results = upload_results + other_results
    total_tests = len(all_results)
    passed_tests = len([r for r in all_results if r[1]])
    failed_tests = total_tests - passed_tests

    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")

    if total_tests > 0:
        success_rate = (passed_tests / total_tests) * 100
        print(f"Success Rate: {success_rate:.1f}%")

    print("\nDetailed Results:")
    print("-" * 40)

    for test_name, passed, status, response_time, data in all_results:
        status_icon = "✅" if passed else "❌"
        status_text = f"Status: {status}" if status else "Error"
        time_text = f"({response_time:.2f}ms)" if response_time else ""
        print(f"{status_icon} {test_name}: {status_text} {time_text}")

    print("\nKey Findings:")
    print("-" * 40)

    # Analyze upload functionality
    upload_test = next((r for r in upload_results if r[0] == "Valid PDF Upload"), None)
    if upload_test:
        if upload_test[1] and upload_test[2] in [200, 409]:
            print("✅ File upload functionality is working correctly")
            if upload_test[2] == 409:
                print("✅ Duplicate file detection is working")
        else:
            print("❌ File upload functionality has issues")

    # Analyze validation
    validation_test = next((r for r in upload_results if r[0] == "Invalid File Type"), None)
    if validation_test and validation_test[1]:
        print("✅ File type validation is working correctly")
    else:
        print("❌ File type validation may have issues")

    # Analyze performance
    response_times = [r[3] for r in all_results if r[3] is not None]
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        print(f"📊 Average response time: {avg_time:.2f}ms")
        print(f"📊 Maximum response time: {max_time:.2f}ms")

        # Find slow tests
        slow_tests = [(r[0], r[3]) for r in all_results if r[3] and r[3] > 5000]
        if slow_tests:
            print(f"⚠️  Slow tests (>5s): {[f'{name} ({time/1000:.1f}s)' for name, time in slow_tests]}")

    print("\nRecommendations:")
    print("-" * 40)

    if passed_tests == total_tests:
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("🔧 Some tests failed. Key recommendations:")

        if upload_test and not upload_test[1]:
            print("   - Fix file upload functionality")
            print("   - Check server logs for error details")

        if validation_test and not validation_test[1]:
            print("   - Review file validation logic")

        if any(r[3] and r[3] > 20000 for r in all_results):
            print("   - Some requests are taking too long (>20s)")
            print("   - Check for background processing issues")

    # Check if there are any invoices in the system
    list_test = next((r for r in other_results if r[0] == "List Invoices"), None)
    if list_test and list_test[4] and list_test[4].get('total', 0) > 0:
        print(f"\n📋 System currently has {list_test[4].get('total')} invoices")

    print("="*60)

def main():
    """Main test execution."""
    print("Starting Focused API Testing...")
    print("="*60)

    # Test API health
    if not test_api_health():
        log_failure("API is not healthy. Cannot proceed with tests.")
        return 1

    print("\n" + "-"*60)

    # Test file upload functionality
    upload_results = test_file_upload_scenarios()

    print("\n" + "-"*60)

    # Test other API endpoints
    other_results = test_other_endpoints()

    # Analyze results
    analyze_results(upload_results, other_results)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)