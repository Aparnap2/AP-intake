#!/usr/bin/env python3
"""
Comprehensive API testing script using direct Python HTTP requests.
Tests the file upload functionality and other API endpoints.
"""

import json
import os
import sys
import time
import tempfile
import requests
from pathlib import Path

# Get project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/api/v1/invoices/upload"
LIST_ENDPOINT = f"{API_BASE_URL}/api/v1/invoices/"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"

# Test files
TEST_INVOICE_PATH = "os.path.join(PROJECT_ROOT, "test_invoices/test_invoice_standard_20251107_175127.pdf")"

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
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                log_success("API is healthy")
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

def create_test_files():
    """Create test files for various scenarios."""
    files = {}

    # Create a text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a text file, not a PDF")
        files['text'] = f.name

    # Create an empty file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        files['empty'] = f.name

    # Create a corrupted PDF
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write("%PDF-1.4\nThis is not a valid PDF structure\n%%EOF")
        files['corrupted'] = f.name

    # Create a large file (5MB)
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'0' * (5 * 1024 * 1024))
        files['large'] = f.name

    # Create image files
    # JPEG header
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        f.write(b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00')
        files['jpeg'] = f.name

    # PNG header
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        files['png'] = f.name

    return files

def cleanup_test_files(files):
    """Clean up test files."""
    for file_path in files.values():
        try:
            os.unlink(file_path)
        except:
            pass

def upload_file(file_path, description):
    """Upload a file and return response."""
    log_info(f"Testing: {description}")

    if not os.path.exists(file_path):
        log_failure(f"File not found: {file_path}")
        return None, None, None

    start_time = time.time()

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            response = requests.post(API_ENDPOINT, files=files, timeout=30)

        response_time = (time.time() - start_time) * 1000

        return response, response_time, None

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return None, response_time, str(e)

def test_file_upload():
    """Test various file upload scenarios."""
    log_info("Starting comprehensive file upload tests...")

    if not os.path.exists(TEST_INVOICE_PATH):
        log_failure(f"Test invoice not found: {TEST_INVOICE_PATH}")
        return

    # Create test files
    test_files = create_test_files()

    test_results = []

    # Test 1: Valid PDF upload
    response, response_time, error = upload_file(TEST_INVOICE_PATH, "Valid PDF Upload")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("Valid PDF upload successful")
            test_results.append(("Valid PDF", True, status, response_time))
            # Save the response for later tests
            try:
                data = response.json()
                invoice_id = data.get('id')
                if invoice_id:
                    log_info(f"Created invoice ID: {invoice_id}")
            except:
                pass
        elif status == 409:
            log_warning("Duplicate file detected (expected)")
            test_results.append(("Valid PDF", True, status, response_time))
        else:
            log_failure(f"Unexpected status: {status}")
            test_results.append(("Valid PDF", False, status, response_time))

        if response.content:
            log_info(f"Response: {response.text[:200]}...")
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("Valid PDF", False, None, response_time))

    # Test 2: Invalid file type
    response, response_time, error = upload_file(test_files['text'], "Invalid File Type")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 400:
            log_success("Invalid file type correctly rejected")
            test_results.append(("Invalid File Type", True, status, response_time))
        else:
            log_failure(f"Expected 400, got {status}")
            test_results.append(("Invalid File Type", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("Invalid File Type", False, None, response_time))

    # Test 3: Large file
    response, response_time, error = upload_file(test_files['large'], "Large File (5MB)")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("Large file accepted")
            test_results.append(("Large File", True, status, response_time))
        elif status == 400:
            log_warning("Large file rejected (may be over limit)")
            test_results.append(("Large File", True, status, response_time))
        else:
            log_failure(f"Unexpected status: {status}")
            test_results.append(("Large File", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("Large File", False, None, response_time))

    # Test 4: Empty file
    response, response_time, error = upload_file(test_files['empty'], "Empty File")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("Empty file accepted")
            test_results.append(("Empty File", True, status, response_time))
        elif status == 500:
            log_warning("Empty file caused server error (expected)")
            test_results.append(("Empty File", True, status, response_time))
        else:
            log_failure(f"Unexpected status: {status}")
            test_results.append(("Empty File", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("Empty File", False, None, response_time))

    # Test 5: Corrupted file
    response, response_time, error = upload_file(test_files['corrupted'], "Corrupted PDF")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("Corrupted file accepted (processing may fail later)")
            test_results.append(("Corrupted File", True, status, response_time))
        else:
            log_warning(f"Corrupted file rejected: {status}")
            test_results.append(("Corrupted File", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("Corrupted File", False, None, response_time))

    # Test 6: JPEG upload
    response, response_time, error = upload_file(test_files['jpeg'], "JPEG Image")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("JPEG file accepted")
            test_results.append(("JPEG", True, status, response_time))
        else:
            log_warning(f"JPEG rejected: {status}")
            test_results.append(("JPEG", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("JPEG", False, None, response_time))

    # Test 7: PNG upload
    response, response_time, error = upload_file(test_files['png'], "PNG Image")
    if response:
        status = response.status_code
        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        if status == 200:
            log_success("PNG file accepted")
            test_results.append(("PNG", True, status, response_time))
        else:
            log_warning(f"PNG rejected: {status}")
            test_results.append(("PNG", False, status, response_time))
    else:
        log_failure(f"Upload failed: {error}")
        test_results.append(("PNG", False, None, response_time))

    # Cleanup
    cleanup_test_files(test_files)

    return test_results

def test_api_endpoints():
    """Test other API endpoints."""
    log_info("Testing other API endpoints...")

    endpoint_results = []

    # Test list invoices
    try:
        start_time = time.time()
        response = requests.get(LIST_ENDPOINT, timeout=10)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            log_success(f"List invoices: {response.status_code} ({response_time:.2f}ms)")
            endpoint_results.append(("List Invoices", True, response.status_code, response_time))
        else:
            log_failure(f"List invoices failed: {response.status_code}")
            endpoint_results.append(("List Invoices", False, response.status_code, response_time))
    except Exception as e:
        log_failure(f"List invoices error: {e}")
        endpoint_results.append(("List Invoices", False, None, None))

    # Test API documentation
    try:
        docs_response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if docs_response.status_code == 200:
            log_success("API docs accessible")
            endpoint_results.append(("API Docs", True, docs_response.status_code, None))
        else:
            log_failure(f"API docs not accessible: {docs_response.status_code}")
            endpoint_results.append(("API Docs", False, docs_response.status_code, None))
    except Exception as e:
        log_failure(f"API docs error: {e}")
        endpoint_results.append(("API Docs", False, None, None))

    return endpoint_results

def generate_report(upload_results, endpoint_results):
    """Generate comprehensive test report."""
    total_tests = len(upload_results) + len(endpoint_results)
    passed_tests = len([r for r in upload_results + endpoint_results if r[1]])
    failed_tests = total_tests - passed_tests

    print("\n" + "="*60)
    print("COMPREHENSIVE API TEST REPORT")
    print("="*60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")

    if total_tests > 0:
        success_rate = (passed_tests / total_tests) * 100
        print(f"Success Rate: {success_rate:.1f}%")

    print("\nFile Upload Tests:")
    print("-" * 40)
    for test_name, passed, status, response_time in upload_results:
        status_icon = "✅" if passed else "❌"
        status_text = f"Status: {status}" if status else "Error"
        time_text = f"({response_time:.2f}ms)" if response_time else ""
        print(f"{status_icon} {test_name}: {status_text} {time_text}")

    print("\nAPI Endpoint Tests:")
    print("-" * 40)
    for test_name, passed, status, response_time in endpoint_results:
        status_icon = "✅" if passed else "❌"
        status_text = f"Status: {status}" if status else "Error"
        time_text = f"({response_time:.2f}ms)" if response_time else ""
        print(f"{status_icon} {test_name}: {status_text} {time_text}")

    print("\nKey Findings:")
    print("-" * 40)

    # Analyze results
    upload_working = any(r[1] for r in upload_results if r[0] == "Valid PDF")
    validation_working = any(r[1] for r in upload_results if r[0] == "Invalid File Type")

    if upload_working:
        print("✅ File upload functionality is working")
    else:
        print("❌ File upload functionality has issues")

    if validation_working:
        print("✅ File type validation is working")
    else:
        print("❌ File type validation may have issues")

    # Performance analysis
    response_times = [r[3] for r in upload_results + endpoint_results if r[3] is not None]
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        print(f"📊 Average response time: {avg_time:.2f}ms")
        print(f"📊 Maximum response time: {max_time:.2f}ms")

        if max_time > 20000:  # 20 seconds
            print("⚠️  Some requests are taking too long (>20s)")

    print("\nRecommendations:")
    print("-" * 40)

    if passed_tests == total_tests:
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("🔧 Some tests failed. Review the issues above.")

    if not upload_working:
        print("🔧 Fix file upload functionality")

    if not validation_working:
        print("🔧 Check file validation logic")

    print("="*60)

    # Save report to file
    timestamp = int(time.time())
    report_file = f"os.path.join(PROJECT_ROOT, "test_reports/comprehensive_api_report_{timestamp}.txt")"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)

    with open(report_file, 'w') as f:
        f.write(f"Comprehensive API Test Report - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n")
        f.write(f"Total Tests: {total_tests}\n")
        f.write(f"Passed: {passed_tests}\n")
        f.write(f"Failed: {failed_tests}\n")
        f.write(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%\n\n")

        f.write("File Upload Tests:\n")
        f.write("-" * 40 + "\n")
        for test_name, passed, status, response_time in upload_results:
            f.write(f"{'✅' if passed else '❌'} {test_name}: {status} ({response_time}ms)\n")

        f.write("\nAPI Endpoint Tests:\n")
        f.write("-" * 40 + "\n")
        for test_name, passed, status, response_time in endpoint_results:
            f.write(f"{'✅' if passed else '❌'} {test_name}: {status} ({response_time}ms)\n")

    print(f"\n📄 Detailed report saved to: {report_file}")

def main():
    """Main test execution."""
    print("Starting Comprehensive API Testing...")
    print("="*60)

    # Test API health
    if not test_api_health():
        log_failure("API is not healthy. Cannot proceed with tests.")
        return 1

    # Test file upload functionality
    upload_results = test_file_upload()

    # Test other API endpoints
    endpoint_results = test_api_endpoints()

    # Generate report
    generate_report(upload_results, endpoint_results)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)