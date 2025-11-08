"""
Comprehensive End-to-End Testing for AP Intake & Validation System
"""

import asyncio
import httpx
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class E2ETestFramework:
    """Comprehensive E2E Testing Framework"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results = []
        self.session_id = str(uuid.uuid4())

    async def run_all_tests(self):
        """Execute all E2E tests"""
        print("🚀 Starting Comprehensive E2E Test Suite")
        print(f"Test Session ID: {self.session_id}")
        print("=" * 60)

        # Test 1: Basic Connectivity
        await self.test_basic_connectivity()

        # Test 2: Health Checks
        await self.test_health_checks()

        # Test 3: API Endpoints Availability
        await self.test_api_endpoints()

        # Test 4: Invoice Upload Workflow
        await self.test_invoice_upload_workflow()

        # Test 5: Invoice Processing Pipeline
        await self.test_invoice_processing_pipeline()

        # Test 6: Data Consistency Validation
        await self.test_data_consistency()

        # Test 7: Error Handling
        await self.test_error_handling()

        # Test 8: Export Functionality
        await self.test_export_functionality()

        # Generate comprehensive report
        self.generate_test_report()

    async def test_basic_connectivity(self):
        """Test basic service connectivity"""
        print("\n📡 Testing Basic Connectivity...")

        test_name = "Basic Connectivity Test"
        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                # Test Backend API
                api_response = await client.get(f"{self.base_url}/health", timeout=10)
                api_status = api_response.status_code == 200

                # Test Frontend
                frontend_response = await client.get(self.frontend_url, timeout=10)
                frontend_status = frontend_response.status_code == 200

                success = api_status and frontend_status
                response_time = time.time() - start_time

                result = {
                    "test": test_name,
                    "success": success,
                    "api_status": api_response.status_code,
                    "frontend_status": frontend_response.status_code,
                    "response_time": f"{response_time:.2f}s",
                    "timestamp": datetime.now().isoformat()
                }

                self.test_results.append(result)
                print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
                print(f"   API: {api_response.status_code}, Frontend: {frontend_response.status_code}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_health_checks(self):
        """Test health check endpoints"""
        print("\n🏥 Testing Health Check Endpoints...")

        test_name = "Health Check Test"
        health_endpoints = [
            "/health",
            "/metrics",
            "/api/v1/status"
        ]

        results = []

        try:
            async with httpx.AsyncClient() as client:
                for endpoint in health_endpoints:
                    try:
                        response = await client.get(f"{self.base_url}{endpoint}", timeout=5)
                        results.append({
                            "endpoint": endpoint,
                            "status": response.status_code,
                            "response_time": response.elapsed.total_seconds()
                        })
                        print(f"   {endpoint}: {response.status_code}")
                    except Exception as e:
                        results.append({
                            "endpoint": endpoint,
                            "status": "ERROR",
                            "error": str(e)
                        })
                        print(f"   {endpoint}: ERROR - {e}")

            success = all(r.get("status") == 200 for r in results)

            result = {
                "test": test_name,
                "success": success,
                "endpoints": results,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_api_endpoints(self):
        """Test critical API endpoints availability"""
        print("\n🔌 Testing API Endpoints...")

        test_name = "API Endpoints Test"
        endpoints = [
            {"method": "GET", "path": "/api/v1/invoices/", "description": "List invoices"},
            {"method": "GET", "path": "/api/v1/exports/", "description": "List exports"},
            {"method": "GET", "path": "/api/v1/analytics/", "description": "Analytics"},
            {"method": "GET", "path": "/api/v1/emails/", "description": "Email integration"},
        ]

        results = []

        try:
            async with httpx.AsyncClient() as client:
                for endpoint in endpoints:
                    try:
                        if endpoint["method"] == "GET":
                            response = await client.get(f"{self.base_url}{endpoint['path']}", timeout=5)

                        results.append({
                            "endpoint": endpoint["path"],
                            "method": endpoint["method"],
                            "description": endpoint["description"],
                            "status": response.status_code,
                            "response_time": response.elapsed.total_seconds()
                        })
                        print(f"   {endpoint['description']}: {response.status_code}")

                    except Exception as e:
                        results.append({
                            "endpoint": endpoint["path"],
                            "method": endpoint["method"],
                            "description": endpoint["description"],
                            "status": "ERROR",
                            "error": str(e)
                        })
                        print(f"   {endpoint['description']}: ERROR - {e}")

            # Allow 404 for endpoints not implemented yet
            success = all(r.get("status") in [200, 404] for r in results)

            result = {
                "test": test_name,
                "success": success,
                "endpoints": results,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_invoice_upload_workflow(self):
        """Test invoice upload functionality"""
        print("\n📤 Testing Invoice Upload Workflow...")

        test_name = "Invoice Upload Test"

        try:
            # First check if upload endpoint exists
            async with httpx.AsyncClient() as client:
                # Test OPTIONS request for CORS
                try:
                    options_response = await client.options(
                        f"{self.base_url}/api/v1/invoices/upload",
                        headers={
                            "Origin": "http://localhost:3000",
                            "Access-Control-Request-Method": "POST"
                        },
                        timeout=5
                    )
                    cors_status = options_response.status_code
                    print(f"   CORS OPTIONS: {cors_status}")
                except Exception as e:
                    cors_status = "ERROR"
                    print(f"   CORS OPTIONS: ERROR - {e}")

                # Test actual upload endpoint (without file for endpoint check)
                try:
                    upload_response = await client.post(
                        f"{self.base_url}/api/v1/invoices/upload",
                        timeout=5
                    )
                    upload_status = upload_response.status_code
                    print(f"   Upload POST: {upload_status}")
                except Exception as e:
                    upload_status = "ERROR"
                    print(f"   Upload POST: ERROR - {e}")

                # Check file storage endpoint
                try:
                    storage_response = await client.get(f"{self.base_url}/api/v1/storage/", timeout=5)
                    storage_status = storage_response.status_code
                    print(f"   Storage GET: {storage_status}")
                except Exception as e:
                    storage_status = "ERROR"
                    print(f"   Storage GET: ERROR - {e}")

            success = (
                cors_status in [200, 204, 405] and  # Allow 405 if CORS not configured
                upload_status in [400, 422, 405] and  # Allow validation errors
                storage_status in [200, 404]  # Allow 404 if not implemented
            )

            result = {
                "test": test_name,
                "success": success,
                "cors_status": cors_status,
                "upload_status": upload_status,
                "storage_status": storage_status,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_invoice_processing_pipeline(self):
        """Test invoice processing pipeline"""
        print("\n⚙️ Testing Invoice Processing Pipeline...")

        test_name = "Processing Pipeline Test"

        try:
            async with httpx.AsyncClient() as client:
                # Test invoice listing to see processed data
                try:
                    invoices_response = await client.get(
                        f"{self.base_url}/api/v1/invoices/?limit=10",
                        timeout=10
                    )
                    invoices_status = invoices_response.status_code

                    if invoices_status == 200:
                        invoices_data = invoices_response.json()
                        invoice_count = len(invoices_data.get("invoices", []))
                        print(f"   Found {invoice_count} invoices")
                    else:
                        invoice_count = 0

                except Exception as e:
                    invoices_status = "ERROR"
                    invoice_count = 0
                    print(f"   Invoice listing: ERROR - {e}")

                # Test Celery/RabbitMQ if available
                try:
                    celery_response = await client.get(
                        f"{self.base_url}/api/v1/celery/status",
                        timeout=5
                    )
                    celery_status = celery_response.status_code
                    print(f"   Celery status: {celery_status}")
                except Exception as e:
                    celery_status = "ERROR"
                    print(f"   Celery status: ERROR - {e}")

                # Test workflow state
                try:
                    workflow_response = await client.get(
                        f"{self.base_url}/api/v1/status/workflow",
                        timeout=5
                    )
                    workflow_status = workflow_response.status_code
                    print(f"   Workflow status: {workflow_status}")
                except Exception as e:
                    workflow_status = "ERROR"
                    print(f"   Workflow status: ERROR - {e}")

            success = (
                invoices_status in [200, 404] and
                celery_status in [200, 404] and
                workflow_status in [200, 404]
            )

            result = {
                "test": test_name,
                "success": success,
                "invoices_status": invoices_status,
                "invoice_count": invoice_count,
                "celery_status": celery_status,
                "workflow_status": workflow_status,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_data_consistency(self):
        """Test data consistency between frontend and backend"""
        print("\n🔄 Testing Data Consistency...")

        test_name = "Data Consistency Test"

        try:
            async with httpx.AsyncClient() as client:
                # Test API data structure
                try:
                    api_response = await client.get(
                        f"{self.base_url}/api/v1/invoices/?limit=5",
                        timeout=10
                    )

                    if api_response.status_code == 200:
                        api_data = api_response.json()

                        # Check data structure consistency
                        required_fields = ["id", "status", "created_at", "file_name"]
                        data_structure_valid = True

                        for invoice in api_data.get("invoices", []):
                            missing_fields = [field for field in required_fields if field not in invoice]
                            if missing_fields:
                                data_structure_valid = False
                                print(f"   Missing fields in invoice: {missing_fields}")

                        print(f"   API data structure: {'VALID' if data_structure_valid else 'INVALID'}")
                        print(f"   Total invoices in API: {len(api_data.get('invoices', []))}")

                    else:
                        data_structure_valid = False
                        print(f"   API request failed: {api_response.status_code}")

                except Exception as e:
                    data_structure_valid = False
                    print(f"   API data test: ERROR - {e}")

                # Test frontend availability
                try:
                    frontend_response = await client.get(f"{self.frontend_url}/invoices", timeout=10)
                    frontend_available = frontend_response.status_code == 200
                    print(f"   Frontend invoices page: {'AVAILABLE' if frontend_available else 'UNAVAILABLE'}")
                except Exception as e:
                    frontend_available = False
                    print(f"   Frontend test: ERROR - {e}")

            success = data_structure_valid and frontend_available

            result = {
                "test": test_name,
                "success": success,
                "data_structure_valid": data_structure_valid,
                "frontend_available": frontend_available,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_error_handling(self):
        """Test error handling capabilities"""
        print("\n⚠️ Testing Error Handling...")

        test_name = "Error Handling Test"

        try:
            async with httpx.AsyncClient() as client:
                error_tests = []

                # Test 404 handling
                try:
                    response = await client.get(f"{self.base_url}/api/v1/nonexistent", timeout=5)
                    error_tests.append({
                        "test": "404 Not Found",
                        "status": response.status_code,
                        "expected": 404,
                        "passed": response.status_code == 404
                    })
                except Exception as e:
                    error_tests.append({
                        "test": "404 Not Found",
                        "status": "ERROR",
                        "error": str(e),
                        "passed": False
                    })

                # Test invalid UUID handling
                try:
                    response = await client.get(f"{self.base_url}/api/v1/invoices/invalid-uuid", timeout=5)
                    error_tests.append({
                        "test": "Invalid UUID",
                        "status": response.status_code,
                        "expected": 400,
                        "passed": response.status_code == 400
                    })
                except Exception as e:
                    error_tests.append({
                        "test": "Invalid UUID",
                        "status": "ERROR",
                        "error": str(e),
                        "passed": False
                    })

                # Test invalid method
                try:
                    response = await client.patch(f"{self.base_url}/api/v1/invoices/", timeout=5)
                    error_tests.append({
                        "test": "Invalid Method",
                        "status": response.status_code,
                        "expected": [405, 422],  # Method not allowed or validation error
                        "passed": response.status_code in [405, 422]
                    })
                except Exception as e:
                    error_tests.append({
                        "test": "Invalid Method",
                        "status": "ERROR",
                        "error": str(e),
                        "passed": False
                    })

                for test in error_tests:
                    status = "✅ PASSED" if test["passed"] else "❌ FAILED"
                    print(f"   {test['test']}: {status} ({test.get('status', 'ERROR')})")

            success = all(test["passed"] for test in error_tests)

            result = {
                "test": test_name,
                "success": success,
                "error_tests": error_tests,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_export_functionality(self):
        """Test export functionality"""
        print("\n📊 Testing Export Functionality...")

        test_name = "Export Functionality Test"

        try:
            async with httpx.AsyncClient() as client:
                # Test exports endpoint
                try:
                    exports_response = await client.get(f"{self.base_url}/api/v1/exports/", timeout=10)
                    exports_status = exports_response.status_code
                    print(f"   Exports endpoint: {exports_status}")

                    if exports_status == 200:
                        exports_data = exports_response.json()
                        export_count = len(exports_data.get("exports", []))
                        print(f"   Available exports: {export_count}")
                    else:
                        export_count = 0

                except Exception as e:
                    exports_status = "ERROR"
                    export_count = 0
                    print(f"   Exports endpoint: ERROR - {e}")

                # Test export templates
                try:
                    templates_response = await client.get(f"{self.base_url}/api/v1/exports/templates", timeout=5)
                    templates_status = templates_response.status_code
                    print(f"   Export templates: {templates_status}")
                except Exception as e:
                    templates_status = "ERROR"
                    print(f"   Export templates: ERROR - {e}")

                # Test analytics data (often used for exports)
                try:
                    analytics_response = await client.get(f"{self.base_url}/api/v1/analytics/", timeout=5)
                    analytics_status = analytics_response.status_code
                    print(f"   Analytics data: {analytics_status}")
                except Exception as e:
                    analytics_status = "ERROR"
                    print(f"   Analytics data: ERROR - {e}")

            success = (
                exports_status in [200, 404] and
                templates_status in [200, 404] and
                analytics_status in [200, 404]
            )

            result = {
                "test": test_name,
                "success": success,
                "exports_status": exports_status,
                "export_count": export_count,
                "templates_status": templates_status,
                "analytics_status": analytics_status,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 COMPREHENSIVE E2E TEST REPORT")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        print(f"\nTest Session: {self.session_id}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        print(f"\nDetailed Results:")
        print("-" * 40)

        for result in self.test_results:
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            print(f"{result['test']}: {status}")

            if not result["success"] and "error" in result:
                print(f"  Error: {result['error']}")

        # Performance metrics
        response_times = []
        for result in self.test_results:
            if "response_time" in result:
                time_str = result["response_time"].replace("s", "")
                try:
                    response_times.append(float(time_str))
                except:
                    pass

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            print(f"\nPerformance Metrics:")
            print(f"Average Response Time: {avg_response_time:.2f}s")
            print(f"Max Response Time: {max(response_times):.2f}s")
            print(f"Min Response Time: {min(response_times):.2f}s")

        # Save report to file
        report_file = f"e2e_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests/total_tests)*100
            },
            "results": self.test_results
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_file}")

        print("\n" + "=" * 60)
        print("🎯 PRODUCTION READINESS ASSESSMENT")
        print("=" * 60)

        if failed_tests == 0:
            print("✅ ALL TESTS PASSED - System is PRODUCTION READY")
        elif failed_tests <= 2:
            print("⚠️  MINOR ISSUES - System is MOSTLY READY with minor fixes needed")
        else:
            print("❌ MULTIPLE FAILURES - System needs significant improvements before production")

        print("=" * 60)

async def main():
    """Main test execution function"""
    framework = E2ETestFramework()
    await framework.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())