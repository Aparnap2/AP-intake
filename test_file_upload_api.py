#!/usr/bin/env python3
"""
Comprehensive test script for the file upload API endpoint.
Tests various scenarios including edge cases and error conditions.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

import httpx
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/api/v1/invoices/upload"
TEST_INVOICE_PATH = "/home/aparna/Desktop/ap_intake/test_invoices/test_invoice_standard_20251107_175127.pdf"

class TestResult(BaseModel):
    """Test result model."""
    test_name: str
    status: str  # "PASS", "FAIL", "ERROR"
    status_code: int = None
    response_time_ms: float = None
    error_message: str = None
    response_data: Dict[str, Any] = None

class FileUploadTester:
    """Comprehensive file upload API tester."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results: List[TestResult] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _log_result(self, result: TestResult):
        """Log test result."""
        status_icon = "✅" if result.status == "PASS" else "❌"
        logger.info(f"{status_icon} {result.test_name}: {result.status}")

        if result.status_code:
            logger.info(f"    Status Code: {result.status_code}")

        if result.response_time_ms:
            logger.info(f"    Response Time: {result.response_time_ms:.2f}ms")

        if result.error_message:
            logger.info(f"    Error: {result.error_message}")

        if result.response_data:
            logger.info(f"    Response: {json.dumps(result.response_data, indent=2)}")

    def _create_test_file(self, content: bytes, filename: str) -> str:
        """Create a temporary test file."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

    async def test_valid_pdf_upload(self) -> TestResult:
        """Test 1: Valid PDF upload."""
        try:
            if not os.path.exists(TEST_INVOICE_PATH):
                return TestResult(
                    test_name="Valid PDF Upload",
                    status="ERROR",
                    error_message=f"Test file not found: {TEST_INVOICE_PATH}"
                )

            start_time = time.time()

            with open(TEST_INVOICE_PATH, 'rb') as f:
                files = {'file': (os.path.basename(TEST_INVOICE_PATH), f, 'application/pdf')}
                response = await self.client.post(API_ENDPOINT, files=files)

            response_time = (time.time() - start_time) * 1000

            result = TestResult(
                test_name="Valid PDF Upload",
                status="PASS" if response.status_code == 200 else "FAIL",
                status_code=response.status_code,
                response_time_ms=response_time,
                response_data=response.json() if response.content else None
            )

            return result

        except Exception as e:
            return TestResult(
                test_name="Valid PDF Upload",
                status="ERROR",
                error_message=str(e)
            )

    async def test_missing_file(self) -> TestResult:
        """Test 2: Missing file in request."""
        try:
            start_time = time.time()
            response = await self.client.post(API_ENDPOINT)
            response_time = (time.time() - start_time) * 1000

            result = TestResult(
                test_name="Missing File",
                status="PASS" if response.status_code == 422 else "FAIL",
                status_code=response.status_code,
                response_time_ms=response_time,
                response_data=response.json() if response.content else None
            )

            return result

        except Exception as e:
            return TestResult(
                test_name="Missing File",
                status="ERROR",
                error_message=str(e)
            )

    async def test_invalid_file_type(self) -> TestResult:
        """Test 3: Invalid file type (txt file)."""
        try:
            # Create a temporary text file
            test_content = b"This is not a PDF file"
            temp_file = self._create_test_file(test_content, "test.txt")

            try:
                start_time = time.time()

                with open(temp_file, 'rb') as f:
                    files = {'file': ('test.txt', f, 'text/plain')}
                    response = await self.client.post(API_ENDPOINT, files=files)

                response_time = (time.time() - start_time) * 1000

                result = TestResult(
                    test_name="Invalid File Type",
                    status="PASS" if response.status_code == 400 else "FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response.json() if response.content else None
                )

                return result

            finally:
                os.unlink(temp_file)

        except Exception as e:
            return TestResult(
                test_name="Invalid File Type",
                status="ERROR",
                error_message=str(e)
            )

    async def test_large_file(self) -> TestResult:
        """Test 4: Large file upload (exceeding 25MB limit)."""
        try:
            # Create a large temporary file (30MB)
            large_content = b"X" * (30 * 1024 * 1024)  # 30MB
            temp_file = self._create_test_file(large_content, "large.pdf")

            try:
                start_time = time.time()

                with open(temp_file, 'rb') as f:
                    files = {'file': ('large.pdf', f, 'application/pdf')}
                    response = await self.client.post(API_ENDPOINT, files=files)

                response_time = (time.time() - start_time) * 1000

                result = TestResult(
                    test_name="Large File Upload",
                    status="PASS" if response.status_code == 400 else "FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response.json() if response.content else None
                )

                return result

            finally:
                os.unlink(temp_file)

        except Exception as e:
            return TestResult(
                test_name="Large File Upload",
                status="ERROR",
                error_message=str(e)
            )

    async def test_empty_file(self) -> TestResult:
        """Test 5: Empty file upload."""
        try:
            # Create an empty temporary file
            temp_file = self._create_test_file(b"", "empty.pdf")

            try:
                start_time = time.time()

                with open(temp_file, 'rb') as f:
                    files = {'file': ('empty.pdf', f, 'application/pdf')}
                    response = await self.client.post(API_ENDPOINT, files=files)

                response_time = (time.time() - start_time) * 1000

                result = TestResult(
                    test_name="Empty File Upload",
                    status="PASS" if response.status_code in [200, 400] else "FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response.json() if response.content else None
                )

                return result

            finally:
                os.unlink(temp_file)

        except Exception as e:
            return TestResult(
                test_name="Empty File Upload",
                status="ERROR",
                error_message=str(e)
            )

    async def test_corrupted_file(self) -> TestResult:
        """Test 6: Corrupted PDF file."""
        try:
            # Create a corrupted file (invalid PDF structure)
            corrupted_content = b"%PDF-1.4\nThis is not a valid PDF structure\n%%EOF"
            temp_file = self._create_test_file(corrupted_content, "corrupted.pdf")

            try:
                start_time = time.time()

                with open(temp_file, 'rb') as f:
                    files = {'file': ('corrupted.pdf', f, 'application/pdf')}
                    response = await self.client.post(API_ENDPOINT, files=files)

                response_time = (time.time() - start_time) * 1000

                # The API should accept the file initially (it only checks extension)
                # but the processing might fail later
                result = TestResult(
                    test_name="Corrupted File Upload",
                    status="PASS" if response.status_code == 200 else "FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response.json() if response.content else None
                )

                return result

            finally:
                os.unlink(temp_file)

        except Exception as e:
            return TestResult(
                test_name="Corrupted File Upload",
                status="ERROR",
                error_message=str(e)
            )

    async def test_duplicate_file(self) -> TestResult:
        """Test 7: Duplicate file upload (same hash)."""
        try:
            if not os.path.exists(TEST_INVOICE_PATH):
                return TestResult(
                    test_name="Duplicate File Upload",
                    status="ERROR",
                    error_message=f"Test file not found: {TEST_INVOICE_PATH}"
                )

            # First upload
            start_time = time.time()

            with open(TEST_INVOICE_PATH, 'rb') as f:
                files = {'file': (os.path.basename(TEST_INVOICE_PATH), f, 'application/pdf')}
                first_response = await self.client.post(API_ENDPOINT, files=files)

            first_response_time = (time.time() - start_time) * 1000

            # Second upload (should detect duplicate)
            start_time = time.time()

            with open(TEST_INVOICE_PATH, 'rb') as f:
                files = {'file': (os.path.basename(TEST_INVOICE_PATH), f, 'application/pdf')}
                second_response = await self.client.post(API_ENDPOINT, files=files)

            second_response_time = (time.time() - start_time) * 1000

            result = TestResult(
                test_name="Duplicate File Upload",
                status="PASS" if second_response.status_code == 409 else "FAIL",
                status_code=second_response.status_code,
                response_time_ms=second_response_time,
                response_data=second_response.json() if second_response.content else None,
                error_message=f"First upload: {first_response.status_code} ({first_response_time:.2f}ms)"
            )

            return result

        except Exception as e:
            return TestResult(
                test_name="Duplicate File Upload",
                status="ERROR",
                error_message=str(e)
            )

    async def test_no_filename(self) -> TestResult:
        """Test 8: File with no filename."""
        try:
            # Create a temporary file with no name
            test_content = b"%PDF-1.4\nTest content\n%%EOF"
            temp_file = self._create_test_file(test_content, "")

            try:
                start_time = time.time()

                with open(temp_file, 'rb') as f:
                    files = {'file': ('', f, 'application/pdf')}
                    response = await self.client.post(API_ENDPOINT, files=files)

                response_time = (time.time() - start_time) * 1000

                result = TestResult(
                    test_name="No Filename",
                    status="PASS" if response.status_code == 400 else "FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response.json() if response.content else None
                )

                return result

            finally:
                os.unlink(temp_file)

        except Exception as e:
            return TestResult(
                test_name="No Filename",
                status="ERROR",
                error_message=str(e)
            )

    async def test_different_image_formats(self) -> TestResult:
        """Test 9: Different allowed image formats."""
        try:
            # Test JPEG
            jpeg_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"  # JPEG header
            jpeg_file = self._create_test_file(jpeg_content, "test.jpg")

            # Test PNG
            png_content = b"\x89PNG\r\n\x1a\n"  # PNG header
            png_file = self._create_test_file(png_content, "test.png")

            results = []

            try:
                # Test JPEG
                start_time = time.time()
                with open(jpeg_file, 'rb') as f:
                    files = {'file': ('test.jpg', f, 'image/jpeg')}
                    response = await self.client.post(API_ENDPOINT, files=files)
                response_time = (time.time() - start_time) * 1000
                results.append(("JPEG", response.status_code, response_time))

                # Test PNG
                start_time = time.time()
                with open(png_file, 'rb') as f:
                    files = {'file': ('test.png', f, 'image/png')}
                    response = await self.client.post(API_ENDPOINT, files=files)
                response_time = (time.time() - start_time) * 1000
                results.append(("PNG", response.status_code, response_time))

                # JPEG and PNG should be accepted (status 200)
                jpeg_ok = results[0][1] == 200
                png_ok = results[1][1] == 200

                result = TestResult(
                    test_name="Different Image Formats",
                    status="PASS" if jpeg_ok and png_ok else "FAIL",
                    status_code=None,
                    response_time_ms=None,
                    response_data={
                        "jpeg": {"status": results[0][1], "time_ms": results[0][2]},
                        "png": {"status": results[1][1], "time_ms": results[1][2]}
                    }
                )

                return result

            finally:
                os.unlink(jpeg_file)
                os.unlink(png_file)

        except Exception as e:
            return TestResult(
                test_name="Different Image Formats",
                status="ERROR",
                error_message=str(e)
            )

    async def test_response_format(self) -> TestResult:
        """Test 10: Verify response format and required fields."""
        try:
            if not os.path.exists(TEST_INVOICE_PATH):
                return TestResult(
                    test_name="Response Format Validation",
                    status="ERROR",
                    error_message=f"Test file not found: {TEST_INVOICE_PATH}"
                )

            start_time = time.time()

            with open(TEST_INVOICE_PATH, 'rb') as f:
                files = {'file': (os.path.basename(TEST_INVOICE_PATH), f, 'application/pdf')}
                response = await self.client.post(API_ENDPOINT, files=files)

            response_time = (time.time() - start_time) * 1000

            if response.status_code != 200:
                return TestResult(
                    test_name="Response Format Validation",
                    status="FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    error_message="Upload failed"
                )

            response_data = response.json()

            # Check required fields
            required_fields = ['id', 'file_url', 'file_hash', 'file_name', 'file_size', 'status', 'workflow_state', 'created_at']
            missing_fields = [field for field in required_fields if field not in response_data]

            if missing_fields:
                return TestResult(
                    test_name="Response Format Validation",
                    status="FAIL",
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    response_data=response_data,
                    error_message=f"Missing required fields: {missing_fields}"
                )

            # Validate field formats
            validation_errors = []

            # Check UUID format for id
            try:
                import uuid
                uuid.UUID(response_data['id'])
            except ValueError:
                validation_errors.append("Invalid UUID format for 'id'")

            # Check status values
            valid_statuses = ['RECEIVED', 'PROCESSING', 'PROCESSED', 'READY', 'STAGED', 'EXPORTED', 'ERROR']
            if response_data.get('status') not in valid_statuses:
                validation_errors.append(f"Invalid status value: {response_data.get('status')}")

            result = TestResult(
                test_name="Response Format Validation",
                status="PASS" if not validation_errors else "FAIL",
                status_code=response.status_code,
                response_time_ms=response_time,
                response_data=response_data,
                error_message=f"Validation errors: {validation_errors}" if validation_errors else None
            )

            return result

        except Exception as e:
            return TestResult(
                test_name="Response Format Validation",
                status="ERROR",
                error_message=str(e)
            )

    async def run_all_tests(self) -> List[TestResult]:
        """Run all test scenarios."""
        logger.info("Starting comprehensive file upload API testing...")
        logger.info(f"API Endpoint: {API_ENDPOINT}")
        logger.info(f"Test File: {TEST_INVOICE_PATH}")
        logger.info("=" * 60)

        tests = [
            self.test_valid_pdf_upload(),
            self.test_missing_file(),
            self.test_invalid_file_type(),
            self.test_large_file(),
            self.test_empty_file(),
            self.test_corrupted_file(),
            self.test_duplicate_file(),
            self.test_no_filename(),
            self.test_different_image_formats(),
            self.test_response_format(),
        ]

        # Execute all tests
        results = await asyncio.gather(*tests, return_exceptions=True)

        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(TestResult(
                    test_name=f"Test {i+1}",
                    status="ERROR",
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
                self._log_result(result)

        return final_results

    def generate_report(self, results: List[TestResult]) -> str:
        """Generate comprehensive test report."""
        total_tests = len(results)
        passed_tests = len([r for r in results if r.status == "PASS"])
        failed_tests = len([r for r in results if r.status == "FAIL"])
        error_tests = len([r for r in results if r.status == "ERROR"])

        report = []
        report.append("\n" + "=" * 60)
        report.append("COMPREHENSIVE FILE UPLOAD API TEST REPORT")
        report.append("=" * 60)
        report.append(f"Total Tests: {total_tests}")
        report.append(f"Passed: {passed_tests} ✅")
        report.append(f"Failed: {failed_tests} ❌")
        report.append(f"Errors: {error_tests} ⚠️")
        report.append(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")

        # Detailed results
        for result in results:
            report.append(f"Test: {result.test_name}")
            report.append(f"Status: {result.status}")

            if result.status_code:
                report.append(f"HTTP Status: {result.status_code}")

            if result.response_time_ms:
                report.append(f"Response Time: {result.response_time_ms:.2f}ms")

            if result.error_message:
                report.append(f"Error: {result.error_message}")

            if result.response_data:
                report.append(f"Response: {json.dumps(result.response_data, indent=2)}")

            report.append("-" * 40)

        # Performance summary
        response_times = [r.response_time_ms for r in results if r.response_time_ms]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)

            report.append("PERFORMANCE SUMMARY")
            report.append(f"Average Response Time: {avg_response_time:.2f}ms")
            report.append(f"Min Response Time: {min_response_time:.2f}ms")
            report.append(f"Max Response Time: {max_response_time:.2f}ms")

        # Recommendations
        report.append("\nRECOMMENDATIONS")

        if failed_tests > 0:
            report.append("❌ Some tests failed. Review failed scenarios and fix issues.")

        if error_tests > 0:
            report.append("⚠️ Some tests encountered errors. Check error messages for debugging.")

        if any(r.response_time_ms and r.response_time_ms > 5000 for r in results):
            report.append("⚠️ Some tests took >5 seconds. Consider optimizing performance.")

        if passed_tests == total_tests:
            report.append("✅ All tests passed! The file upload API is working correctly.")

        report.append("=" * 60)

        return "\n".join(report)

async def main():
    """Main test execution function."""
    async with FileUploadTester() as tester:
        results = await tester.run_all_tests()
        report = tester.generate_report(results)
        print(report)

        # Save report to file
        timestamp = int(time.time())
        report_file = f"/home/aparna/Desktop/ap_intake/test_reports/file_upload_test_report_{timestamp}.txt"

        # Ensure report directory exists
        os.makedirs(os.path.dirname(report_file), exist_ok=True)

        with open(report_file, 'w') as f:
            f.write(report)

        logger.info(f"Test report saved to: {report_file}")

        return results

if __name__ == "__main__":
    asyncio.run(main())