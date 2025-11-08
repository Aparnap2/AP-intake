#!/usr/bin/env python3
"""
Advanced API testing with different file and database diagnostics.
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
TEST_INVOICE_FILES = [
    "/home/aparna/Desktop/ap_intake/test_invoices/test_invoice_complex_20251107_175127.pdf",
    "/home/aparna/Desktop/ap_intake/test_invoices/test_invoice_error_scenarios_20251107_175127.pdf",
    "/home/aparna/Desktop/ap_intake/test_invoices/test_invoice_minimal_20251107_175127.pdf"
]

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'

def log_info(msg):
    print(f"{Colors.BLUE}[INFO]{Colors.ENDC} {msg}")

def log_success(msg):
    print(f"{Colors.GREEN}[PASS]{Colors.ENDC} {msg}")

def log_failure(msg):
    print(f"{Colors.RED}[FAIL]{Colors.ENDC} {msg}")

def log_warning(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.ENDC} {msg}")

def log_debug(msg):
    print(f"{Colors.CYAN}[DEBUG]{Colors.ENDC} {msg}")

def test_api_health():
    """Test API health endpoint."""
    log_info("Testing API health...")
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_success(f"API is healthy - Version: {data.get('version')}, Environment: {data.get('environment')}")
            return True, data
        else:
            log_failure(f"Health check failed: {response.status_code}")
            return False, None
    except Exception as e:
        log_failure(f"Health check error: {e}")
        return False, None

def upload_file_with_analysis(file_path, description):
    """Upload a file and provide detailed analysis."""
    log_info(f"Testing: {description}")
    log_debug(f"File path: {file_path}")
    log_debug(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'} bytes")

    if not os.path.exists(file_path):
        log_failure(f"File not found: {file_path}")
        return None, None, None

    start_time = time.time()

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            response = requests.post(API_ENDPOINT, files=files, timeout=60)

        response_time = (time.time() - start_time) * 1000
        status = response.status_code

        log_info(f"Status: {status}, Time: {response_time:.2f}ms")

        # Analyze response
        if status == 200:
            log_success("✅ Upload successful")
            try:
                data = response.json()
                log_info(f"   Invoice ID: {data.get('id')}")
                log_info(f"   File name: {data.get('file_name')}")
                log_info(f"   File size: {data.get('file_size')}")
                log_info(f"   Status: {data.get('status')}")
                log_info(f"   Workflow state: {data.get('workflow_state')}")
                log_info(f"   File hash: {data.get('file_hash', 'N/A')[:16]}...")
                log_debug(f"   File URL: {data.get('file_url')}")
                return True, status, data
            except json.JSONDecodeError as e:
                log_warning(f"Could not parse response JSON: {e}")
                log_debug(f"Response content: {response.text[:200]}")
                return True, status, None
        elif status == 409:
            log_warning("⚠️  Duplicate file detected")
            try:
                data = response.json()
                existing_id = data.get('detail', '').split('ID: ')[-1]
                log_info(f"   Existing invoice ID: {existing_id}")
                return True, status, data
            except:
                return True, status, None
        else:
            log_failure(f"❌ Unexpected status: {status}")
            log_debug(f"Response content: {response.text[:300]}")
            return False, status, None

    except requests.exceptions.Timeout:
        log_failure("❌ Upload timed out (>60s)")
        return False, None, None
    except Exception as e:
        log_failure(f"❌ Upload failed: {e}")
        log_debug(f"Exception type: {type(e).__name__}")
        return False, None, None

def test_database_connectivity():
    """Test database connectivity through API."""
    log_info("Testing database connectivity...")

    # Test 1: List invoices with detailed error analysis
    try:
        start_time = time.time()
        response = requests.get(LIST_ENDPOINT, timeout=10)
        response_time = (time.time() - start_time) * 1000

        log_info(f"List invoices status: {response.status_code}, Time: {response_time:.2f}ms")

        if response.status_code == 200:
            try:
                data = response.json()
                total_invoices = data.get('total', 0)
                log_success(f"✅ Database connectivity working - {total_invoices} invoices found")

                # Show recent invoices
                invoices = data.get('invoices', [])
                if invoices:
                    log_info("Recent invoices:")
                    for i, invoice in enumerate(invoices[:3]):
                        log_info(f"   {i+1}. ID: {invoice.get('id', 'N/A')[:8]}..., "
                               f"File: {invoice.get('file_name', 'N/A')}, "
                               f"Status: {invoice.get('status', 'N/A')}")

                return True, data
            except json.JSONDecodeError:
                log_warning("Could not parse list response JSON")
                log_debug(f"Response: {response.text[:200]}")
                return False, None
        else:
            log_failure(f"❌ List invoices failed: {response.status_code}")
            log_debug(f"Error response: {response.text[:300]}")

            # Try to understand the error
            if response.status_code == 500:
                log_warning("Internal server error - possible database connection issue")

            return False, None

    except requests.exceptions.Timeout:
        log_failure("❌ Database query timed out")
        return False, None
    except Exception as e:
        log_failure(f"❌ Database connectivity test failed: {e}")
        return False, None

def test_storage_functionality():
    """Test file storage functionality."""
    log_info("Testing file storage...")

    # Create a small test PDF
    test_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000079 00000 n\n0000000173 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n298\n%%EOF"

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(test_content)
        temp_file = f.name

    try:
        success, status, data = upload_file_with_analysis(temp_file, "Minimal PDF upload")

        if success and status == 200:
            log_success("✅ File storage functionality working")

            # Check if file was stored
            file_url = data.get('file_url') if data else None
            if file_url:
                log_info(f"File stored at: {file_url}")

            return True
        else:
            log_failure("❌ File storage test failed")
            return False

    finally:
        os.unlink(temp_file)

def test_edge_cases():
    """Test edge cases and error handling."""
    log_info("Testing edge cases...")

    edge_case_results = []

    # Test 1: Very large filename
    log_info("Edge case: Very long filename")
    long_name = "a" * 200 + ".pdf"
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b"test content")
        temp_file = f.name

    try:
        start_time = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (long_name, f, 'application/pdf')}
            response = requests.post(API_ENDPOINT, files=files, timeout=10)

        response_time = (time.time() - start_time) * 1000
        log_info(f"Long filename test - Status: {response.status_code}, Time: {response_time:.2f}ms")

        if response.status_code in [200, 400]:
            log_success("✅ Long filename handled correctly")
            edge_case_results.append(("Long Filename", True))
        else:
            log_failure(f"❌ Long filename issue: {response.status_code}")
            edge_case_results.append(("Long Filename", False))

    finally:
        os.unlink(temp_file)

    # Test 2: Special characters in filename
    log_info("Edge case: Special characters in filename")
    special_name = "test_file(1)@#$%^&*().pdf"
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b"test content")
        temp_file = f.name

    try:
        start_time = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (special_name, f, 'application/pdf')}
            response = requests.post(API_ENDPOINT, files=files, timeout=10)

        response_time = (time.time() - start_time) * 1000
        log_info(f"Special characters test - Status: {response.status_code}, Time: {response_time:.2f}ms")

        if response.status_code in [200, 400]:
            log_success("✅ Special characters handled correctly")
            edge_case_results.append(("Special Characters", True))
        else:
            log_failure(f"❌ Special characters issue: {response.status_code}")
            edge_case_results.append(("Special Characters", False))

    finally:
        os.unlink(temp_file)

    return edge_case_results

def generate_comprehensive_report(results):
    """Generate a comprehensive test report."""
    print("\n" + "="*70)
    print("COMPREHENSIVE FILE UPLOAD API TEST REPORT")
    print("="*70)

    # Summary
    total_tests = sum(len(result_group) for result_group in results.values() if isinstance(result_group, list))
    passed_tests = sum(sum(1 for r in result_group if isinstance(r, tuple) and len(r) > 1 and r[1])
                      for result_group in results.values() if isinstance(result_group, list))

    print(f"Total Test Scenarios: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {total_tests - passed_tests} ❌")

    if total_tests > 0:
        success_rate = (passed_tests / total_tests) * 100
        print(f"Success Rate: {success_rate:.1f}%")

    print("\nDetailed Results:")
    print("-" * 70)

    # API Health
    if 'health' in results:
        health_data = results['health']
        if health_data[0]:
            print(f"✅ API Health: Version {health_data[1].get('version')}, Environment {health_data[1].get('environment')}")
        else:
            print("❌ API Health: Failed")

    # File Upload Tests
    if 'uploads' in results:
        print("\nFile Upload Tests:")
        for test_name, success, status, data in results['uploads']:
            status_icon = "✅" if success else "❌"
            status_text = f"Status: {status}" if status else "Error"
            print(f"  {status_icon} {test_name}: {status_text}")

    # Database Tests
    if 'database' in results:
        print("\nDatabase Tests:")
        db_success, db_data = results['database']
        if db_success and db_data:
            print(f"✅ Database Connectivity: {db_data.get('total', 0)} invoices in system")
        else:
            print("❌ Database Connectivity: Failed")

    # Storage Tests
    if 'storage' in results:
        print(f"\nStorage Tests: {'✅ Working' if results['storage'] else '❌ Failed'}")

    # Edge Cases
    if 'edge_cases' in results:
        print("\nEdge Case Tests:")
        for test_name, success in results['edge_cases']:
            status_icon = "✅" if success else "❌"
            print(f"  {status_icon} {test_name}")

    print("\nKey Findings:")
    print("-" * 70)

    # Analysis
    upload_working = any(r[1] for r in results.get('uploads', []))
    validation_working = any("Invalid File Type" in str(r) and r[1] for r in results.get('uploads', []))
    db_working = results.get('database', [False])[0]

    if upload_working:
        print("✅ File upload functionality is operational")
    else:
        print("❌ File upload functionality needs attention")

    if validation_working:
        print("✅ File validation is working correctly")
    else:
        print("❌ File validation may have issues")

    if db_working:
        print("✅ Database connectivity is working")
    else:
        print("❌ Database connectivity issues detected")

    # Performance analysis
    upload_times = [r[3] for r in results.get('uploads', []) if r[3] is not None]
    if upload_times:
        avg_time = sum(upload_times) / len(upload_times)
        max_time = max(upload_times)
        print(f"📊 Average upload time: {avg_time:.2f}ms")
        print(f"📊 Maximum upload time: {max_time:.2f}ms")

    print("\nRecommendations:")
    print("-" * 70)

    if not db_working:
        print("🔧 PRIORITY: Fix database connectivity issues")
        print("   - Check database service status")
        print("   - Verify connection strings")
        print("   - Review database logs")

    if not upload_working:
        print("🔧 Fix file upload issues")
        print("   - Check storage service configuration")
        print("   - Review file permission settings")

    if upload_working and db_working:
        print("🎉 Core functionality is working correctly!")
        print("📋 System is ready for invoice processing")

    print("="*70)

def main():
    """Main test execution."""
    print("Starting Advanced File Upload API Testing...")
    print("="*70)

    results = {}

    # Test API health
    log_info("=== API Health Test ===")
    health_success, health_data = test_api_health()
    results['health'] = (health_success, health_data)

    if not health_success:
        log_failure("API is not healthy. Cannot proceed with comprehensive tests.")
        return 1

    print("\n" + "="*70)

    # Test different invoice files
    log_info("=== Multiple File Upload Tests ===")
    upload_results = []

    for i, test_file in enumerate(TEST_INVOICE_FILES):
        if os.path.exists(test_file):
            filename = os.path.basename(test_file)
            success, status, data = upload_file_with_analysis(test_file, f"Test File {i+1}: {filename}")
            upload_results.append((f"Upload {filename}", success, status, data))
        else:
            log_warning(f"Test file not found: {test_file}")

    results['uploads'] = upload_results

    print("\n" + "="*70)

    # Test database connectivity
    log_info("=== Database Connectivity Test ===")
    db_success, db_data = test_database_connectivity()
    results['database'] = (db_success, db_data)

    print("\n" + "="*70)

    # Test storage functionality
    log_info("=== Storage Functionality Test ===")
    storage_working = test_storage_functionality()
    results['storage'] = storage_working

    print("\n" + "="*70)

    # Test edge cases
    log_info("=== Edge Case Tests ===")
    edge_case_results = test_edge_cases()
    results['edge_cases'] = edge_case_results

    # Generate comprehensive report
    generate_comprehensive_report(results)

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