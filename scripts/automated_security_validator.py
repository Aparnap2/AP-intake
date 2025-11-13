#!/usr/bin/env python3
"""
Automated Security Validation Script
Tests security controls and validates implementation
"""

import asyncio
import json
import logging
import uuid
import time
import hashlib
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecurityValidator:
    """Validates security controls and implementation."""

    def __init__(self):
        self.base_path = Path("/home/aparna/Desktop/ap_intake")
        self.results = []
        self.score = 0
        self.max_score = 100

    def add_result(self, test_name: str, category: str, points: int, max_points: int,
                   status: str, description: str, evidence: str, recommendation: str):
        """Add test result."""
        result = {
            "test_name": test_name,
            "category": category,
            "points": points,
            "max_points": max_points,
            "status": status,
            "description": description,
            "evidence": evidence,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        self.score += points
        logger.info(f"VALIDATION: {test_name} - {status} - {points}/{max_points} points")

    def check_authentication_implementation(self):
        """Check if authentication system is properly implemented."""
        logger.info("Checking Authentication Implementation...")

        deps_file = self.base_path / "app/api/api_v1/deps.py"
        if deps_file.exists():
            content = deps_file.read_text()

            # Check if get_current_user returns None (placeholder)
            if "return None" in content and "get_current_user" in content:
                self.add_result(
                    test_name="Authentication System Implementation",
                    category="Authentication",
                    points=0,
                    max_points=20,
                    status="FAIL",
                    description="Authentication system is not implemented (placeholder)",
                    evidence="get_current_user returns None",
                    recommendation="Implement proper JWT authentication system"
                )
            else:
                # Check for proper authentication dependencies
                auth_patterns = [
                    "HTTPBearer",
                    "HTTPAuthorizationCredentials",
                    "jwt.decode",
                    "get_current_user.*User",
                ]

                found_patterns = sum(1 for pattern in auth_patterns if pattern in content)
                points = min(found_patterns * 5, 20)

                if points >= 15:
                    status = "PASS"
                elif points >= 10:
                    status = "PARTIAL"
                else:
                    status = "FAIL"

                self.add_result(
                    test_name="Authentication System Implementation",
                    category="Authentication",
                    points=points,
                    max_points=20,
                    status=status,
                    description=f"Authentication implementation {'complete' if points >= 15 else 'partial' if points >= 10 else 'incomplete'}",
                    evidence=f"Found {found_patterns} out of 4 required patterns",
                    recommendation="Complete authentication system implementation"
                )

    def check_sql_injection_protection(self):
        """Check SQL injection protection measures."""
        logger.info("Checking SQL Injection Protection...")

        python_files = list(self.base_path.rglob("*.py"))
        vulnerable_patterns = 0
        safe_patterns = 0

        for file_path in python_files:
            if 'venv' in str(file_path) or 'site-packages' in str(file_path):
                continue

            try:
                content = file_path.read_text()

                # Check for vulnerable patterns
                vulnerable_patterns += len(re.findall(r'execute\s*\(\s*["\'][^"\']*%s[^"\']*["\']', content))
                vulnerable_patterns += len(re.findall(r'execute\s*\(\s*f["\'][^"\']*{[^}]*}[^"\']*["\']', content))
                vulnerable_patterns += len(re.findall(r'\.format\s*\([^)]*\)\s*\)', content))

                # Check for safe patterns
                safe_patterns += len(re.findall(r'select\(', content))
                safe_patterns += len(re.findall(r'text\(', content))
                safe_patterns += len(re.findall(r'SELECT.*WHERE.*:', content))

            except Exception:
                continue

        if vulnerable_patterns == 0:
            points = 15
            status = "PASS"
        elif vulnerable_patterns <= 2:
            points = 10
            status = "PARTIAL"
        else:
            points = 0
            status = "FAIL"

        self.add_result(
            test_name="SQL Injection Protection",
            category="Injection",
            points=points,
            max_points=15,
            status=status,
            description=f"Found {vulnerable_patterns} potentially vulnerable SQL patterns",
            evidence=f"Vulnerable patterns: {vulnerable_patterns}, Safe patterns: {safe_patterns}",
            recommendation="Use parameterized queries and SQLAlchemy ORM"
        )

    def check_file_upload_security(self):
        """Check file upload security implementation."""
        logger.info("Checking File Upload Security...")

        invoice_endpoint = self.base_path / "app/api/api_v1/endpoints/invoices.py"
        if invoice_endpoint.exists():
            content = invoice_endpoint.read_text()

            # Check for security measures
            security_measures = {
                "File type validation": len(re.findall(r'ALLOWED_FILE_TYPES|content_type', content)),
                "File size validation": len(re.findall(r'MAX_FILE_SIZE|file_size', content)),
                "Filename sanitization": len(re.findall(r'sanitize|safe.*filename', content)),
                "Magic bytes validation": len(re.findall(r'magic|mimetypes|content_type', content)),
            }

            total_measures = sum(security_measures.values())
            points = min(total_measures * 2, 15)

            if points >= 12:
                status = "PASS"
            elif points >= 8:
                status = "PARTIAL"
            else:
                status = "FAIL"

            self.add_result(
                test_name="File Upload Security",
                category="File Upload",
                points=points,
                max_points=15,
                status=status,
                description=f"File upload security: {points}/15 points",
                evidence=f"Security measures found: {security_measures}",
                recommendation="Implement comprehensive file upload validation"
            )

    def check_cors_configuration(self):
        """Check CORS configuration security."""
        logger.info("Checking CORS Configuration...")

        config_files = [
            self.base_path / "app/core/config.py",
            self.base_path / "app/main.py"
        ]

        cors_issues = 0
        cors_score = 0

        for config_file in config_files:
            if config_file.exists():
                content = config_file.read_text()

                # Check for insecure CORS settings
                if 'allow_origins=["*"]' in content or "allow_origins = ['*']" in content:
                    cors_issues += 1
                if 'allow_methods=["*"]' in content or "allow_methods = ['*']" in content:
                    cors_issues += 1
                if 'allow_headers=["*"]' in content or "allow_headers = ['*']" in content:
                    cors_issues += 1

                # Check for secure CORS settings
                if 'CORS_ORIGINS' in content:
                    cors_score += 2
                if 'TrustedHostMiddleware' in content:
                    cors_score += 1

        if cors_issues == 0 and cors_score >= 2:
            points = 10
            status = "PASS"
        elif cors_issues <= 1 and cors_score >= 1:
            points = 5
            status = "PARTIAL"
        else:
            points = 0
            status = "FAIL"

        self.add_result(
            test_name="CORS Configuration Security",
            category="Web Security",
            points=points,
            max_points=10,
            status=status,
            description=f"CORS configuration: {points}/10 points",
            evidence=f"CORS issues: {cors_issues}, Security measures: {cors_score}",
            recommendation="Restrict CORS to specific trusted origins"
        )

    def check_security_headers(self):
        """Check security headers implementation."""
        logger.info("Checking Security Headers...")

        # Check for security headers middleware
        middleware_files = list(self.base_path.rglob("middleware/*.py"))
        main_file = self.base_path / "app/main.py"

        headers_found = 0
        total_headers = 6

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "Referrer-Policy"
        ]

        all_files = middleware_files + [main_file]
        for file_path in all_files:
            if file_path.exists():
                content = file_path.read_text()
                for header in required_headers:
                    if header in content:
                        headers_found += 1
                        required_headers.remove(header)
                        break

        points = (headers_found / total_headers) * 10
        status = "PASS" if points >= 8 else "PARTIAL" if points >= 5 else "FAIL"

        self.add_result(
            test_name="Security Headers Implementation",
            category="Security Headers",
            points=int(points),
            max_points=10,
            status=status,
            description=f"Security headers: {headers_found}/{total_headers} implemented",
            evidence=f"Headers found: {6 - len(required_headers)}",
            recommendation="Implement all required security headers"
        )

    def check_input_validation(self):
        """Check input validation implementation."""
        logger.info("Checking Input Validation...")

        # Check for Pydantic models and validation
        schema_files = list(self.base_path.rglob("schemas/*.py"))
        validation_score = 0

        for schema_file in schema_files:
            if schema_file.exists():
                content = schema_file.read_text()

                # Check for validation decorators
                validation_score += len(re.findall(r'@validator', content))
                validation_score += len(re.findall(r'Field\(', content))
                validation_score += len(re.findall(r'email_str|EmailStr', content))
                validation_score += len(re.findall(r'min_length|max_length', content))

        # Check endpoint validation
        endpoint_files = list(self.base_path.rglob("endpoints/*.py"))
        for endpoint_file in endpoint_files:
            if endpoint_file.exists():
                content = endpoint_file.read_text()
                validation_score += len(re.findall(r'Query\(', content))
                validation_score += len(re.findall(r'ValidationError', content))

        points = min(validation_score, 10)
        status = "PASS" if points >= 8 else "PARTIAL" if points >= 5 else "FAIL"

        self.add_result(
            test_name="Input Validation Implementation",
            category="Input Validation",
            points=points,
            max_points=10,
            status=status,
            description=f"Input validation: {points}/10 points",
            evidence=f"Validation patterns found: {validation_score}",
            recommendation="Implement comprehensive input validation"
        )

    def check_error_handling(self):
        """Check secure error handling."""
        logger.info("Checking Error Handling...")

        # Check for custom exception classes
        exception_files = [
            self.base_path / "app/core/exceptions.py",
            self.base_path / "app/main.py"
        ]

        error_handling_score = 0

        for file_path in exception_files:
            if file_path.exists():
                content = file_path.read_text()

                # Check for secure error handling
                error_handling_score += len(re.findall(r'exception_handler', content))
                error_handling_score += len(re.findall(r'HTTPException', content))
                error_handling_score += len(re.findall(r'ValidationError', content))

                # Check for debug mode checks
                if 'settings.DEBUG' in content:
                    error_handling_score += 2

        points = min(error_handling_score, 10)
        status = "PASS" if points >= 8 else "PARTIAL" if points >= 5 else "FAIL"

        self.add_result(
            test_name="Secure Error Handling",
            category="Error Handling",
            points=points,
            max_points=10,
            status=status,
            description=f"Error handling: {points}/10 points",
            evidence=f"Error handling patterns found: {error_handling_score}",
            recommendation="Implement secure error handling without information disclosure"
        )

    def check_dependency_security(self):
        """Check dependency security."""
        logger.info("Checking Dependency Security...")

        pyproject_file = self.base_path / "pyproject.toml"
        if pyproject_file.exists():
            content = pyproject_file.read_text()

            # Check for known vulnerable versions (simplified check)
            vulnerable_packages = {
                "requests": "< 2.20.0",
                "urllib3": "< 1.24.2",
                "pyyaml": "< 5.1",
                "jinja2": "< 2.11.3",
            }

            vulnerabilities_found = 0
            for package, version_constraint in vulnerable_packages.items():
                if package in content.lower():
                    # This is a simplified check - real implementation would parse versions
                    vulnerabilities_found += 1

            # Check for security tools in dependencies
            security_tools = 0
            if "bandit" in content or "safety" in content or "semgrep" in content:
                security_tools += 5

            points = max(10 - vulnerabilities_found, 0) + security_tools
            points = min(points, 10)
            status = "PASS" if points >= 8 else "PARTIAL" if points >= 5 else "FAIL"

            self.add_result(
                test_name="Dependency Security",
                category="Dependencies",
                points=points,
                max_points=10,
                status=status,
                description=f"Dependency security: {points}/10 points",
                evidence=f"Potential vulnerabilities: {vulnerabilities_found}, Security tools: {security_tools}",
                recommendation="Update dependencies and implement security scanning"
            )

    def check_logging_and_monitoring(self):
        """Check logging and monitoring implementation."""
        logger.info("Checking Logging and Monitoring...")

        # Check for logging implementation
        logging_files = list(self.base_path.rglob("*.py"))
        logging_score = 0

        for file_path in logging_files:
            if 'venv' in str(file_path) or 'site-packages' in str(file_path):
                continue

            try:
                content = file_path.read_text()

                # Check for logging patterns
                logging_score += len(re.findall(r'logger\.', content))
                logging_score += len(re.findall(r'logging\.', content))
                logging_score += len(re.findall(r'import logging', content))

                # Check for security event logging
                if 'security' in content.lower() and 'log' in content.lower():
                    logging_score += 2

            except Exception:
                continue

        points = min(logging_score // 10, 10)  # Scale down to 10 points
        status = "PASS" if points >= 7 else "PARTIAL" if points >= 4 else "FAIL"

        self.add_result(
            test_name="Logging and Monitoring",
            category="Monitoring",
            points=points,
            max_points=10,
            status=status,
            description=f"Logging implementation: {points}/10 points",
            evidence=f"Logging patterns found: {logging_score}",
            recommendation="Implement comprehensive security logging and monitoring"
        )

    def run_validation(self):
        """Run all security validations."""
        logger.info("Starting Automated Security Validation...")

        # Run all checks
        self.check_authentication_implementation()
        self.check_sql_injection_protection()
        self.check_file_upload_security()
        self.check_cors_configuration()
        self.check_security_headers()
        self.check_input_validation()
        self.check_error_handling()
        self.check_dependency_security()
        self.check_logging_and_monitoring()

        logger.info(f"Security validation completed. Score: {self.score}/{self.max_score}")

    def generate_report(self) -> str:
        """Generate security validation report."""
        report = []
        report.append("# AUTOMATED SECURITY VALIDATION REPORT")
        report.append("AP Intake & Validation System - Security Controls Validation")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall score
        percentage = (self.score / self.max_score) * 100
        if percentage >= 80:
            grade = "A - EXCELLENT"
            status = "✅ STRONG SECURITY POSTURE"
        elif percentage >= 70:
            grade = "B - GOOD"
            status = "✅ GOOD SECURITY POSTURE"
        elif percentage >= 60:
            grade = "C - SATISFACTORY"
            status = "⚡ NEEDS IMPROVEMENT"
        elif percentage >= 50:
            grade = "D - POOR"
            status = "⚠️ SIGNIFICANT ISSUES"
        else:
            grade = "F - CRITICAL"
            status = "🚨 CRITICAL SECURITY ISSUES"

        report.append("## OVERALL SECURITY SCORE")
        report.append(f"**Score**: {self.score}/{self.max_score} ({percentage:.1f}%)")
        report.append(f"**Grade**: {grade}")
        report.append(f"**Status**: {status}")
        report.append("")

        # Category breakdown
        categories = {}
        for result in self.results:
            if result['category'] not in categories:
                categories[result['category']] = {"points": 0, "max_points": 0, "count": 0}
            categories[result['category']]['points'] += result['points']
            categories[result['category']]['max_points'] += result['max_points']
            categories[result['category']]['count'] += 1

        report.append("## SECURITY CATEGORY BREAKDOWN")
        for category, scores in categories.items():
            cat_percentage = (scores['points'] / scores['max_points']) * 100
            report.append(f"**{category}**: {scores['points']}/{scores['max_points']} ({cat_percentage:.1f}%)")
        report.append("")

        # Detailed results
        report.append("## DETAILED VALIDATION RESULTS")
        for result in self.results:
            report.append(f"### {result['test_name']}")
            report.append(f"**Category**: {result['category']}")
            report.append(f"**Score**: {result['points']}/{result['max_points']}")
            report.append(f"**Status**: {result['status']}")
            report.append(f"**Description**: {result['description']}")
            if result['evidence']:
                report.append(f"**Evidence**: {result['evidence']}")
            if result['recommendation']:
                report.append(f"**Recommendation**: {result['recommendation']}")
            report.append("")

        # Recommendations
        report.append("## SECURITY RECOMMENDATIONS")

        # Group recommendations by priority
        critical_recommendations = [r for r in self.results if r['status'] == 'FAIL' and r['max_points'] >= 15]
        high_recommendations = [r for r in self.results if r['status'] == 'FAIL' and r['max_points'] < 15]
        medium_recommendations = [r for r in self.results if r['status'] == 'PARTIAL']

        if critical_recommendations:
            report.append("### 🚨 CRITICAL - Immediate Action Required")
            for rec in critical_recommendations:
                report.append(f"- **{rec['test_name']}**: {rec['recommendation']}")
            report.append("")

        if high_recommendations:
            report.append("### ⚠️ HIGH - Prompt Action Required")
            for rec in high_recommendations:
                report.append(f"- **{rec['test_name']}**: {rec['recommendation']}")
            report.append("")

        if medium_recommendations:
            report.append("### ⚡ MEDIUM - Action Recommended")
            for rec in medium_recommendations:
                report.append(f"- **{rec['test_name']}**: {rec['recommendation']}")
            report.append("")

        # Implementation timeline
        report.append("## IMPLEMENTATION TIMELINE")
        report.append("### Week 1: Critical Fixes")
        report.append("- Implement authentication system")
        report.append("- Fix SQL injection vulnerabilities")
        report.append("- Secure file upload system")
        report.append("")
        report.append("### Week 2: High Priority Fixes")
        report.append("- Fix CORS configuration")
        report.append("- Add security headers")
        report.append("- Implement input validation")
        report.append("")
        report.append("### Week 3-4: Medium Priority Fixes")
        report.append("- Improve error handling")
        report.append("- Update dependencies")
        report.append("- Enhance logging and monitoring")
        report.append("")

        # Next steps
        report.append("## NEXT STEPS")
        report.append("1. Review this validation report")
        report.append("2. Create detailed implementation plan")
        report.append("3. Assign development resources")
        report.append("4. Implement fixes in priority order")
        report.append("5. Re-run validation after each fix")
        report.append("6. Schedule regular security assessments")
        report.append("")

        # Contact information
        report.append("## SECURITY CONTACTS")
        report.append("- **Security Team**: security@company.com")
        report.append("- **Incident Response**: incident@company.com")
        report.append("- **Vulnerability Disclosure**: security@company.com")
        report.append("")

        report.append("---")
        report.append("*This report was generated by the Automated Security Validator*")
        report.append(f"*Security Score: {self.score}/{self.max_score} ({percentage:.1f}%)*")

        return "\n".join(report)

def main():
    """Main function to run security validation."""
    validator = SecurityValidator()
    validator.run_validation()

    report = validator.generate_report()

    # Save report
    report_file = f"security_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = Path("/home/aparna/Desktop/ap_intake") / report_file

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\nSecurity validation completed!")
    print(f"Report saved to: {report_path}")
    print(f"Overall Security Score: {validator.score}/{validator.max_score}")

    # Print summary
    percentage = (validator.score / validator.max_score) * 100
    print(f"Security Grade: {percentage:.1f}%")

    if percentage >= 80:
        print("✅ EXCELLENT security posture")
    elif percentage >= 70:
        print("✅ GOOD security posture")
    elif percentage >= 60:
        print("⚡ SATISFACTORY - needs improvement")
    elif percentage >= 50:
        print("⚠️ POOR - significant issues")
    else:
        print("🚨 CRITICAL security issues - immediate action required")

if __name__ == "__main__":
    main()