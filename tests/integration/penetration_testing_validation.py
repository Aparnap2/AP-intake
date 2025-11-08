#!/usr/bin/env python3
"""
Penetration Testing Validation Script
Validates specific security vulnerabilities found in the AP Intake & Validation System
"""

import asyncio
import json
import logging
import uuid
import time
import hashlib
import base64
from datetime import datetime
from typing import Dict, List, Any

try:
    import aiohttp
    import requests
except ImportError:
    print("Required packages not installed. Install with: pip install aiohttp requests")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PenetrationTestValidator:
    """Validates specific penetration testing scenarios."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_results = []

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def add_result(self, test_name: str, severity: str, status: str,
                   description: str, evidence: str, recommendation: str):
        """Add test result."""
        result = {
            "test_name": test_name,
            "severity": severity,
            "status": status,
            "description": description,
            "evidence": evidence,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        logger.info(f"TEST: {test_name} - {status} - {severity}")

    async def test_authentication_bypass(self):
        """Test CRITICAL vulnerability: Authentication bypass."""
        logger.info("Testing Authentication Bypass Vulnerability...")

        # Test 1: Access protected endpoints without authentication
        protected_endpoints = [
            "/api/v1/invoices/",
            "/api/v1/exports/",
            "/api/v1/exports/templates",
        ]

        for endpoint in protected_endpoints:
            try:
                async with self.session.get(f"{self.base_url}{endpoint}") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.add_result(
                            test_name="Authentication Bypass - Direct Access",
                            severity="CRITICAL",
                            status="FAIL",
                            description=f"Protected endpoint accessible without authentication: {endpoint}",
                            evidence=f"Status: {response.status}, Response: {str(data)[:200]}",
                            recommendation="Implement proper authentication middleware"
                        )
                    else:
                        self.add_result(
                            test_name="Authentication Bypass - Direct Access",
                            severity="CRITICAL",
                            status="PASS",
                            description=f"Endpoint properly protected: {endpoint}",
                            evidence=f"Status: {response.status}",
                            recommendation="Authentication appears to be working"
                        )
            except Exception as e:
                logger.warning(f"Could not test {endpoint}: {e}")

        # Test 2: Fake JWT token
        fake_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.fake_signature"
        headers = {"Authorization": f"Bearer {fake_token}"}

        try:
            async with self.session.get(f"{self.base_url}/api/v1/invoices/", headers=headers) as response:
                if response.status == 200:
                    self.add_result(
                        test_name="Authentication Bypass - Fake JWT",
                        severity="CRITICAL",
                        status="FAIL",
                        description="Fake JWT token accepted",
                        evidence=f"Token: {fake_token[:50]}..., Status: {response.status}",
                        recommendation="Implement proper JWT validation"
                    )
        except Exception as e:
            logger.info(f"Fake JWT correctly rejected: {e}")

    async def test_sql_injection(self):
        """Test CRITICAL vulnerability: SQL Injection."""
        logger.info("Testing SQL Injection Vulnerability...")

        # SQL injection payloads
        payloads = [
            "1' OR '1'='1",
            "1' UNION SELECT null, username, password FROM users--",
            "1'; DROP TABLE invoices;--",
            "1' AND (SELECT COUNT(*) FROM users) > 0--",
        ]

        test_endpoint = f"{self.base_url}/api/v1/invoices/"

        for payload in payloads:
            try:
                async with self.session.get(f"{test_endpoint}?vendor_id={payload}") as response:
                    if response.status == 200:
                        text = await response.text()
                        # Check for SQL errors or unexpected data
                        sql_errors = ["sql", "mysql", "postgresql", "sqlite", "ora-", "warning: mysql"]
                        if any(error in text.lower() for error in sql_errors):
                            self.add_result(
                                test_name="SQL Injection - Error Based",
                                severity="CRITICAL",
                                status="FAIL",
                                description=f"SQL error in response: {payload}",
                                evidence=f"Payload: {payload}, Response contains SQL error",
                                recommendation="Use parameterized queries"
                            )
            except Exception as e:
                logger.info(f"SQL injection test failed (expected): {e}")

        # Test file upload SQL injection
        try:
            malicious_filename = "test'; DROP TABLE invoices; --.pdf"
            test_data = aiohttp.FormData()
            test_data.add_field('file', b'fake content',
                              filename=malicious_filename,
                              content_type='application/pdf')

            async with self.session.post(f"{self.base_url}/api/v1/invoices/upload", data=test_data) as response:
                if response.status == 200:
                    self.add_result(
                        test_name="SQL Injection - File Upload",
                        severity="CRITICAL",
                        status="FAIL",
                        description="Malicious filename with SQL injection accepted",
                        evidence=f"Filename: {malicious_filename}, Status: {response.status}",
                        recommendation="Validate and sanitize all filenames"
                    )
        except Exception as e:
            logger.info(f"File upload SQL injection blocked: {e}")

    async def test_file_upload_vulnerabilities(self):
        """Test HIGH vulnerability: Malicious file upload."""
        logger.info("Testing File Upload Vulnerabilities...")

        # Test malicious files
        malicious_files = [
            ("malware.exe", b"MZ\x90\x00", "application/octet-stream", "Executable file"),
            ("script.php", b"<?php system($_GET['cmd']); ?>", "application/x-php", "PHP web shell"),
            ("shell.jsp", b"<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>", "application/x-jsp", "JSP web shell"),
            ("../../../etc/passwd", b"content", "text/plain", "Path traversal"),
            ("huge.pdf", b"A" * (50 * 1024 * 1024), "application/pdf", "Large file DoS"),
        ]

        for filename, content, content_type, description in malicious_files:
            try:
                test_data = aiohttp.FormData()
                test_data.add_field('file', content,
                                  filename=filename,
                                  content_type=content_type)

                start_time = time.time()
                async with self.session.post(f"{self.base_url}/api/v1/invoices/upload", data=test_data) as response:
                    upload_time = time.time() - start_time

                    if response.status == 200:
                        self.add_result(
                            test_name="Malicious File Upload",
                            severity="HIGH",
                            status="FAIL",
                            description=f"Malicious file uploaded: {description}",
                            evidence=f"File: {filename}, Upload time: {upload_time:.2f}s",
                            recommendation="Implement comprehensive file validation"
                        )
                    else:
                        logger.info(f"Malicious file correctly blocked: {filename}")
            except Exception as e:
                logger.info(f"File upload blocked by system: {filename} - {e}")

        # Test double extension bypass
        try:
            test_data = aiohttp.FormData()
            test_data.add_field('file', b'fake content',
                              filename='invoice.pdf.php',
                              content_type='application/pdf')

            async with self.session.post(f"{self.base_url}/api/v1/invoices/upload", data=test_data) as response:
                if response.status == 200:
                    self.add_result(
                        test_name="Double Extension Bypass",
                        severity="HIGH",
                        status="FAIL",
                        description="Double extension file upload bypass",
                        evidence="File: invoice.pdf.php uploaded successfully",
                        recommendation="Implement magic byte validation"
                    )
        except Exception as e:
            logger.info(f"Double extension blocked: {e}")

    async def test_cors_misconfiguration(self):
        """Test HIGH vulnerability: CORS misconfiguration."""
        logger.info("Testing CORS Misconfiguration...")

        # Test various origins
        test_origins = [
            "http://evil.com",
            "https://malicious-site.com",
            "null",
        ]

        for origin in test_origins:
            try:
                headers = {"Origin": origin}
                async with self.session.options(f"{self.base_url}/api/v1/invoices/", headers=headers) as response:
                    cors_headers = {
                        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                        'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
                    }

                    if cors_headers['Access-Control-Allow-Origin'] == "*":
                        self.add_result(
                            test_name="CORS Wildcard Origin",
                            severity="HIGH",
                            status="FAIL",
                            description="CORS allows wildcard origin",
                            evidence=f"Origin: {origin}, Allow-Origin: *",
                            recommendation="Restrict CORS to specific origins"
                        )
                    elif cors_headers['Access-Control-Allow-Origin'] == origin and cors_headers['Access-Control-Allow-Credentials'] == 'true':
                        self.add_result(
                            test_name="CORS Untrusted Origin with Credentials",
                            severity="MEDIUM",
                            status="FAIL",
                            description="CORS allows untrusted origin with credentials",
                            evidence=f"Origin: {origin}, Credentials: true",
                            recommendation="Restrict CORS to trusted origins only"
                        )
            except Exception as e:
                logger.warning(f"CORS test failed for {origin}: {e}")

    async def test_security_headers(self):
        """Test HIGH vulnerability: Missing security headers."""
        logger.info("Testing Security Headers...")

        required_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': None,  # Just check existence
            'Content-Security-Policy': None,
        }

        try:
            async with self.session.get(f"{self.base_url}/") as response:
                headers = response.headers

                for header, expected_value in required_headers.items():
                    actual_value = headers.get(header)

                    if actual_value is None:
                        self.add_result(
                            test_name=f"Missing Security Header: {header}",
                            severity="HIGH",
                            status="FAIL",
                            description=f"Required security header missing: {header}",
                            evidence=f"Header: {header} not found in response",
                            recommendation=f"Implement {header} security header"
                        )
                    elif expected_value is not None:
                        if isinstance(expected_value, list):
                            if actual_value not in expected_value:
                                self.add_result(
                                    test_name=f"Weak Security Header: {header}",
                                    severity="MEDIUM",
                                    status="FAIL",
                                    description=f"Security header has weak value: {header}={actual_value}",
                                    evidence=f"Expected one of {expected_value}, got: {actual_value}",
                                    recommendation=f"Strengthen {header} security header"
                                )
        except Exception as e:
            logger.error(f"Security headers test failed: {e}")

    async def test_information_disclosure(self):
        """Test MEDIUM vulnerability: Information disclosure."""
        logger.info("Testing Information Disclosure...")

        # Test sensitive paths
        sensitive_paths = [
            "/.env",
            "/config.py",
            "/requirements.txt",
            "/debug",
            "/admin",
            "/phpinfo.php",
        ]

        for path in sensitive_paths:
            try:
                async with self.session.get(f"{self.base_url}{path}") as response:
                    if response.status == 200:
                        content_length = len(await response.text())
                        if content_length > 0:
                            self.add_result(
                                test_name="Information Disclosure",
                                severity="MEDIUM",
                                status="FAIL",
                                description=f"Sensitive file accessible: {path}",
                                evidence=f"Path: {path}, Content length: {content_length}",
                                recommendation="Restrict access to sensitive files"
                            )
            except Exception as e:
                logger.info(f"Sensitive path correctly blocked: {path}")

        # Test error messages
        try:
            async with self.session.get(f"{self.base_url}/api/v1/invoices/invalid-uuid") as response:
                if response.status in [400, 404, 500]:
                    text = await response.text()
                    if any(pattern in text.lower() for pattern in ['traceback', 'exception', 'error at line']):
                        self.add_result(
                            test_name="Error Message Information Disclosure",
                            severity="MEDIUM",
                            status="FAIL",
                            description="Detailed error information exposed",
                            evidence=f"Error response contains technical details",
                            recommendation="Implement generic error messages"
                        )
        except Exception as e:
            logger.warning(f"Error disclosure test failed: {e}")

    async def test_rate_limiting(self):
        """Test MEDIUM vulnerability: Rate limiting."""
        logger.info("Testing Rate Limiting...")

        # Test rapid requests
        request_count = 0
        blocked_count = 0
        start_time = time.time()

        try:
            for i in range(50):  # Send 50 rapid requests
                async with self.session.get(f"{self.base_url}/api/v1/invoices/") as response:
                    request_count += 1
                    if response.status == 429:
                        blocked_count += 1
                        break

                    if i % 10 == 0:  # Check time every 10 requests
                        if time.time() - start_time > 5:  # If taking more than 5 seconds
                            break
        except Exception as e:
            logger.warning(f"Rate limiting test failed: {e}")

        elapsed_time = time.time() - start_time

        if blocked_count == 0 and request_count > 20:
            self.add_result(
                test_name="Missing Rate Limiting",
                severity="MEDIUM",
                status="FAIL",
                description="No rate limiting detected",
                evidence=f"Made {request_count} requests in {elapsed_time:.2f}s without being blocked",
                recommendation="Implement rate limiting on API endpoints"
            )

    async def run_all_tests(self):
        """Run all penetration testing validations."""
        logger.info("Starting Penetration Testing Validation...")

        # Check if service is running
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status != 200:
                    logger.error(f"Service not healthy: {response.status}")
                    return
                logger.info("Service is healthy - starting tests...")
        except Exception as e:
            logger.error(f"Cannot connect to service: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_authentication_bypass,
            self.test_sql_injection,
            self.test_file_upload_vulnerabilities,
            self.test_cors_misconfiguration,
            self.test_security_headers,
            self.test_information_disclosure,
            self.test_rate_limiting,
        ]

        for test_method in test_methods:
            try:
                await test_method()
                await asyncio.sleep(1)  # Brief pause between tests
            except Exception as e:
                logger.error(f"Test {test_method.__name__} failed: {e}")

    def generate_report(self) -> str:
        """Generate penetration testing validation report."""
        report = []
        report.append("# PENETRATION TESTING VALIDATION REPORT")
        report.append("AP Intake & Validation System - Live Testing Results")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Target: {self.base_url}")
        report.append("")

        # Summary
        critical = len([r for r in self.test_results if r['severity'] == 'CRITICAL'])
        high = len([r for r in self.test_results if r['severity'] == 'HIGH'])
        medium = len([r for r in self.test_results if r['severity'] == 'MEDIUM'])

        report.append("## VALIDATION SUMMARY")
        report.append(f"- **Critical Vulnerabilities Confirmed**: {critical}")
        report.append(f"- **High Vulnerabilities Confirmed**: {high}")
        report.append(f"- **Medium Vulnerabilities Confirmed**: {medium}")
        report.append(f"- **Total Tests Run**: {len(self.test_results)}")
        report.append("")

        # Detailed results
        report.append("## DETAILED VALIDATION RESULTS")

        for severity in ['CRITICAL', 'HIGH', 'MEDIUM']:
            severity_results = [r for r in self.test_results if r['severity'] == severity]
            if severity_results:
                report.append(f"### {severity} SEVERITY")
                for result in severity_results:
                    report.append(f"#### {result['test_name']}")
                    report.append(f"**Status**: {result['status']}")
                    report.append(f"**Description**: {result['description']}")
                    report.append(f"**Evidence**: {result['evidence']}")
                    report.append(f"**Recommendation**: {result['recommendation']}")
                    report.append("")

        # Risk assessment
        report.append("## RISK ASSESSMENT")
        if critical > 0:
            report.append("🚨 **CRITICAL RISK**: System is actively vulnerable to attacks")
            report.append("- Immediate action required before production deployment")
        elif high > 0:
            report.append("⚠️ **HIGH RISK**: Significant security vulnerabilities present")
            report.append("- Prompt remediation required")
        elif medium > 0:
            report.append("⚡ **MEDIUM RISK**: Security improvements needed")
            report.append("- Action recommended")
        else:
            report.append("✅ **LOW RISK**: Basic security controls in place")
        report.append("")

        # Immediate actions
        report.append("## IMMEDIATE ACTIONS REQUIRED")
        if critical > 0:
            report.append("1. **IMMEDIATELY** address all CRITICAL vulnerabilities")
            report.append("2. Block access from untrusted networks")
            report.append("3. Implement emergency security controls")

        if high > 0:
            report.append("4. **PRIORITY**: Address HIGH vulnerabilities within 24 hours")
            report.append("5. Review and restrict system access")

        report.append("6. Implement monitoring for suspicious activity")
        report.append("7. Prepare incident response procedures")
        report.append("")

        return "\n".join(report)

async def main():
    """Main function to run penetration testing validation."""
    base_url = os.getenv("TARGET_URL", "http://localhost:8000")

    async with PenetrationTestValidator(base_url) as validator:
        await validator.run_all_tests()
        report = validator.generate_report()

        # Save report
        report_file = f"penetration_testing_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"\nPenetration testing validation completed!")
        print(f"Report saved to: {report_file}")
        print(f"Total tests run: {len(validator.test_results)}")

        # Print summary
        critical = len([r for r in validator.test_results if r['severity'] == 'CRITICAL'])
        high = len([r for r in validator.test_results if r['severity'] == 'HIGH'])
        medium = len([r for r in validator.test_results if r['severity'] == 'MEDIUM'])

        print(f"\nVulnerabilities confirmed:")
        print(f"  Critical: {critical}")
        print(f"  High: {high}")
        print(f"  Medium: {medium}")

        if critical > 0:
            print("\n🚨 CRITICAL VULNERABILITIES CONFIRMED - IMMEDIATE ACTION REQUIRED!")
        elif high > 0:
            print("\n⚠️ HIGH VULNERABILITIES CONFIRMED - PROMPT ACTION REQUIRED!")

if __name__ == "__main__":
    import os
    asyncio.run(main())