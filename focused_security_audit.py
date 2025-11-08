#!/usr/bin/env python3
"""
Focused Security Audit for AP Intake & Validation System
Analyzes code for security vulnerabilities and configuration issues
"""

import ast
import re
import os
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SecurityIssue:
    """Security issue data structure."""
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str
    title: str
    description: str
    file_path: str
    line_number: Optional[int]
    code_snippet: Optional[str]
    recommendation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None

class SecurityAuditor:
    """Security code auditor."""

    def __init__(self):
        self.issues: List[SecurityIssue] = []
        self.base_path = Path("/home/aparna/Desktop/ap_intake")

    def add_issue(self, severity: str, category: str, title: str, description: str,
                  file_path: str, line_number: Optional[int] = None,
                  code_snippet: Optional[str] = None, recommendation: str = "",
                  cwe_id: Optional[str] = None, owasp_category: Optional[str] = None):
        """Add a security issue."""
        issue = SecurityIssue(
            severity=severity,
            category=category,
            title=title,
            description=description,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
            recommendation=recommendation,
            cwe_id=cwe_id,
            owasp_category=owasp_category
        )
        self.issues.append(issue)

    def analyze_file(self, file_path: Path) -> None:
        """Analyze a Python file for security issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return

            # Check for security issues
            self.check_hardcoded_secrets(file_path, lines)
            self.check_sql_injection(file_path, lines, tree)
            self.check_insecure_deserialization(file_path, lines, tree)
            self.check_path_traversal(file_path, lines)
            self.check_weak_crypto(file_path, lines, tree)
            self.check_input_validation(file_path, lines, tree)
            self.check_cors_configuration(file_path, lines)
            self.check_debug_mode(file_path, lines)
            self.check_authentication_issues(file_path, lines, tree)

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")

    def check_hardcoded_secrets(self, file_path: Path, lines: List[str]) -> None:
        """Check for hardcoded secrets and credentials."""
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret_key\s*=\s*["\'][^"\']+["\']', "Hardcoded secret key"),
            (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token"),
            (r'aws_access_key_id\s*=\s*["\'][^"\']+["\']', "Hardcoded AWS access key"),
            (r'aws_secret_access_key\s*=\s*["\'][^"\']+["\']', "Hardcoded AWS secret"),
            (r'database_url\s*=\s*["\'][^"\']*password[^"\']*["\']', "Database URL with password"),
            (r'connection_string\s*=\s*["\'][^"\']*password[^"\']*["\']', "Connection string with password"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, issue_type in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Skip obvious placeholders
                    if any(placeholder in line.lower() for placeholder in [
                        'your-', 'change-', 'placeholder', 'example', 'test', 'demo'
                    ]):
                        continue

                    self.add_issue(
                        severity="HIGH",
                        category="Secrets Management",
                        title=issue_type,
                        description=f"Potential hardcoded credential found",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Use environment variables or secret management systems",
                        cwe_id="CWE-798",
                        owasp_category="A02:2021-Identification and Authentication Failures"
                    )

    def check_sql_injection(self, file_path: Path, lines: List[str], tree: ast.AST) -> None:
        """Check for SQL injection vulnerabilities."""
        dangerous_patterns = [
            r'execute\s*\(\s*["\'][^"\']*%s[^"\']*["\']',
            r'execute\s*\(\s*f["\'][^"\']*{[^}]*}[^"\']*["\']',
            r'execute\s*\(\s*["\'][^"\']*format\s*\(',
            r'execute\s*\(\s*["\'][^"\']*\+[^"\']*["\']',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add_issue(
                        severity="CRITICAL",
                        category="SQL Injection",
                        title="Potential SQL injection vulnerability",
                        description="SQL query built with string formatting or concatenation",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Use parameterized queries or ORM methods",
                        cwe_id="CWE-89",
                        owasp_category="A01:2021-Injection"
                    )

        # Check AST for unsafe database operations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and
                    node.func.attr in ['execute', 'executemany']):
                    # Check if using string formatting
                    for arg in node.args:
                        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                            if any(isinstance(child, ast.Str) for child in [arg.left, arg.right]):
                                self.add_issue(
                                    severity="CRITICAL",
                                    category="SQL Injection",
                                    title="SQL query with string concatenation",
                                    description="SQL query built using string concatenation",
                                    file_path=str(file_path),
                                    line_number=getattr(node, 'lineno', None),
                                    code_snippet=''.join(lines[max(0, node.lineno-2):node.lineno+1]),
                                    recommendation="Use parameterized queries",
                                    cwe_id="CWE-89",
                                    owasp_category="A01:2021-Injection"
                                )

    def check_insecure_deserialization(self, file_path: Path, lines: List[str], tree: ast.AST) -> None:
        """Check for insecure deserialization."""
        dangerous_functions = ['pickle.loads', 'pickle.load', 'cPickle.loads', 'cPickle.load']
        dangerous_modules = ['pickle', 'cPickle', 'dill', 'shelve']

        for line_num, line in enumerate(lines, 1):
            for func in dangerous_functions:
                if func in line:
                    self.add_issue(
                        severity="HIGH",
                        category="Insecure Deserialization",
                        title="Use of dangerous deserialization function",
                        description=f"Dangerous deserialization function {func} detected",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Use safe serialization formats like JSON",
                        cwe_id="CWE-502",
                        owasp_category="A08:2021-Software and Data Integrity Failures"
                    )

        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in dangerous_modules:
                        self.add_issue(
                            severity="MEDIUM",
                            category="Insecure Deserialization",
                            title="Import of dangerous serialization module",
                            description=f"Import of potentially unsafe module: {alias.name}",
                            file_path=str(file_path),
                            line_number=getattr(node, 'lineno', None),
                            code_snippet=f"import {alias.name}",
                            recommendation="Avoid using pickle for untrusted data",
                            cwe_id="CWE-502",
                            owasp_category="A08:2021-Software and Data Integrity Failures"
                        )

    def check_path_traversal(self, file_path: Path, lines: List[str]) -> None:
        """Check for path traversal vulnerabilities."""
        dangerous_patterns = [
            r'open\s*\(\s*[^)]*\.\.',
            r'open\s*\(\s*[^)]*%s',
            r'open\s*\(\s*f["\'][^"\']*{[^}]*}',
            r'os\.path\.join\s*\([^)]*\.\.',
            r'os\.path\.join\s*\([^)]*%s',
            r'file\s*=\s*[^)]*\.\.',
            r'\.read\s*\(\s*[^)]*\.\.',
            r'\.write\s*\(\s*[^)]*\.\.',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if re.search(pattern, line):
                    self.add_issue(
                        severity="HIGH",
                        category="Path Traversal",
                        title="Potential path traversal vulnerability",
                        description="File operation with potentially unsafe path",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Validate and sanitize file paths",
                        cwe_id="CWE-22",
                        owasp_category="A01:2021-Injection"
                    )

    def check_weak_crypto(self, file_path: Path, lines: List[str], tree: ast.AST) -> None:
        """Check for weak cryptography usage."""
        weak_algorithms = [
            'md5', 'sha1', 'des', 'rc4', 'blowfish', 'ecb'
        ]

        # Check for weak hash functions
        for line_num, line in enumerate(lines, 1):
            for algo in weak_algorithms:
                if algo in line.lower() and 'hashlib' in line:
                    self.add_issue(
                        severity="MEDIUM",
                        category="Weak Cryptography",
                        title=f"Use of weak cryptographic algorithm: {algo.upper()}",
                        description=f"Weak hash algorithm {algo.upper()} detected",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation=f"Replace {algo.upper()} with stronger alternatives (SHA-256, SHA-512)",
                        cwe_id="CWE-327",
                        owasp_category="A02:2021-Cryptographic Failures"
                    )

        # Check for hardcoded salts/keys
        salt_patterns = [
            r'salt\s*=\s*["\'][^"\']+["\']',
            r'key\s*=\s*["\'][^"\']+["\'].*crypto',
            r'iv\s*=\s*["\'][^"\']+["\']',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in salt_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    if len(line.split('"')[1]) < 16:  # Short salt/key
                        self.add_issue(
                            severity="MEDIUM",
                            category="Weak Cryptography",
                            title="Hardcoded or weak cryptographic key/salt",
                            description="Hardcoded or insufficiently long cryptographic key/salt",
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=line.strip(),
                            recommendation="Use cryptographically secure random values",
                            cwe_id="CWE-331",
                            owasp_category="A02:2021-Cryptographic Failures"
                        )

    def check_input_validation(self, file_path: Path, lines: List[str], tree: ast.AST) -> None:
        """Check for input validation issues."""
        # Look for file upload handling without validation
        file_upload_patterns = [
            r'UploadFile\s*\=',
            r'save_file\s*\(',
            r'store_file\s*\(',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in file_upload_patterns:
                if re.search(pattern, line):
                    # Check if there's validation nearby
                    validation_found = False
                    for offset in range(-5, 6):  # Check 5 lines before and after
                        check_line = line_num + offset - 1
                        if 0 <= check_line < len(lines):
                            check_content = lines[check_line].lower()
                            if any(vuln in check_content for vuln in [
                                'validate', 'sanitize', 'allowed', 'extension', 'mime'
                            ]):
                                validation_found = True
                                break

                    if not validation_found:
                        self.add_issue(
                            severity="MEDIUM",
                            category="Input Validation",
                            title="File upload without proper validation",
                            description="File upload operation detected without obvious validation",
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=line.strip(),
                            recommendation="Implement file type validation and content scanning",
                            cwe_id="CWE-434",
                            owasp_category="A03:2021-Injection"
                        )

    def check_cors_configuration(self, file_path: Path, lines: List[str]) -> None:
        """Check CORS configuration for security issues."""
        cors_patterns = [
            r'allow_origins\s*=\s*\["\*"\]',
            r'allow_origins\s*=\s*\["\*"\]',
            r'allow_methods\s*=\s*\["\*"\]',
            r'allow_headers\s*=\s*\["\*"\]',
            r'allow_credentials\s*=\s*True.*allow_origins.*\*',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in cors_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    severity = "MEDIUM" if "credentials" in line.lower() and "*" in line else "LOW"
                    self.add_issue(
                        severity=severity,
                        category="CORS Configuration",
                        title="Overly permissive CORS configuration",
                        description="CORS configuration allows all origins/methods/headers",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Restrict CORS to specific trusted origins",
                        cwe_id="CWE-942",
                        owasp_category="A05:2021-Security Misconfiguration"
                    )

    def check_debug_mode(self, file_path: Path, lines: List[str]) -> None:
        """Check for debug mode in production."""
        debug_patterns = [
            r'debug\s*=\s*True',
            r'DEBUG\s*=\s*True',
            r'app\.debug\s*=\s*True',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in debug_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add_issue(
                        severity="MEDIUM",
                        category="Information Disclosure",
                        title="Debug mode enabled",
                        description="Debug mode is enabled in the code",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Disable debug mode in production",
                        cwe_id="CWE-215",
                        owasp_category="A05:2021-Security Misconfiguration"
                    )

    def check_authentication_issues(self, file_path: Path, lines: List[str], tree: ast.AST) -> None:
        """Check for authentication and authorization issues."""
        # Look for placeholder authentication
        placeholder_patterns = [
            r'# TODO.*auth',
            r'# TODO.*login',
            r'# TODO.*permission',
            r'pass\s*#.*authentication',
            'return None  # TODO: implement auth',
            'get_current_user.*return None',
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in placeholder_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add_issue(
                        severity="HIGH",
                        category="Authentication",
                        title="Placeholder or missing authentication",
                        description="Authentication is not properly implemented",
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation="Implement proper authentication and authorization",
                        cwe_id="CWE-287",
                        owasp_category="A02:2021-Identification and Authentication Failures"
                    )

        # Check for missing authentication decorators
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if it's an API endpoint without authentication
                if any(decorator.id in ['get', 'post', 'put', 'delete', 'patch']
                       for decorator in node.decorator_list
                       if isinstance(decorator, ast.Name) and isinstance(decorator.ctx, ast.Load)):

                    # Check if authentication dependency is used
                    has_auth = False
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            if (hasattr(decorator.func, 'id') and
                                decorator.func.id in ['Depends', 'require_authenticated']):
                                has_auth = True
                            elif (hasattr(decorator.func, 'attr') and
                                  decorator.func.attr in ['require_authenticated']):
                                has_auth = True

                    if not has_auth and 'upload' not in node.name.lower():
                        self.add_issue(
                            severity="MEDIUM",
                            category="Authentication",
                            title=f"API endpoint without authentication: {node.name}",
                            description=f"API endpoint {node.name} may lack proper authentication",
                            file_path=str(file_path),
                            line_number=getattr(node, 'lineno', None),
                            code_snippet=f"@app.{node.name}",
                            recommendation="Add authentication dependency to API endpoints",
                            cwe_id="CWE-306",
                            owasp_category="A02:2021-Identification and Authentication Failures"
                        )

    def analyze_configuration_files(self) -> None:
        """Analyze configuration files for security issues."""
        config_files = [
            '.env',
            '.env.example',
            'docker-compose.yml',
            'Dockerfile',
            'pyproject.toml',
        ]

        for config_file in config_files:
            file_path = self.base_path / config_file
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    # Check for exposed secrets in config
                    if config_file == '.env' and '=' in content:
                        lines = content.split('\n')
                        for line_num, line in enumerate(lines, 1):
                            if '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                if any(secret in key.lower() for secret in ['password', 'secret', 'key', 'token']):
                                    if len(value) > 10 and not any(placeholder in value.lower()
                                        for placeholder in ['your', 'change', 'example', 'test']):
                                        self.add_issue(
                                            severity="HIGH",
                                            category="Secrets Management",
                                            title="Potential secret in configuration file",
                                            description=f"Sensitive configuration in {config_file}",
                                            file_path=str(file_path),
                                            line_number=line_num,
                                            code_snippet=line.strip(),
                                            recommendation="Use environment variables or secret management",
                                            cwe_id="CWE-798",
                                            owasp_category="A02:2021-Identification and Authentication Failures"
                                        )

                    # Check Docker security
                    if config_file in ['Dockerfile', 'docker-compose.yml']:
                        if 'root' in content.lower() or 'USER root' in content:
                            self.add_issue(
                                severity="MEDIUM",
                                category="Container Security",
                                title="Container running as root",
                                description="Docker container configured to run as root user",
                                file_path=str(file_path),
                                recommendation="Use non-root user in containers",
                                cwe_id="CWE-250",
                                owasp_category="A05:2021-Security Misconfiguration"
                            )

                except Exception as e:
                    print(f"Error analyzing config file {config_file}: {e}")

    def run_audit(self) -> None:
        """Run the complete security audit."""
        print("Starting security audit of AP Intake & Validation System...")

        # Analyze Python files
        python_files = list(self.base_path.rglob("*.py"))
        for file_path in python_files:
            if 'venv' not in str(file_path) and 'site-packages' not in str(file_path):
                self.analyze_file(file_path)

        # Analyze configuration files
        self.analyze_configuration_files()

        print(f"Security audit completed. Found {len(self.issues)} potential issues.")

    def generate_report(self) -> str:
        """Generate a comprehensive security audit report."""
        report = []
        report.append("# SECURITY AUDIT REPORT")
        report.append("AP Intake & Validation System - Code Analysis")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Summary
        critical = len([i for i in self.issues if i.severity == "CRITICAL"])
        high = len([i for i in self.issues if i.severity == "HIGH"])
        medium = len([i for i in self.issues if i.severity == "MEDIUM"])
        low = len([i for i in self.issues if i.severity == "LOW"])

        report.append("## EXECUTIVE SUMMARY")
        report.append(f"- **Critical Issues**: {critical}")
        report.append(f"- **High Issues**: {high}")
        report.append(f"- **Medium Issues**: {medium}")
        report.append(f"- **Low Issues**: {low}")
        report.append(f"- **Total Issues**: {len(self.issues)}")

        if critical > 0:
            report.append("🚨 **CRITICAL**: Immediate action required")
        elif high > 0:
            report.append("⚠️ **HIGH**: Prompt action required")
        elif medium > 0:
            report.append("⚡ **MEDIUM**: Action recommended")
        else:
            report.append("✅ **GOOD**: No critical issues found")
        report.append("")

        # Group by severity
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            severity_issues = [i for i in self.issues if i.severity == severity]
            if severity_issues:
                report.append(f"## {severity} SEVERITY ISSUES")

                # Group by category
                categories = {}
                for issue in severity_issues:
                    if issue.category not in categories:
                        categories[issue.category] = []
                    categories[issue.category].append(issue)

                for category, issues in categories.items():
                    report.append(f"### {category}")
                    for issue in issues:
                        report.append(f"#### {issue.title}")
                        report.append(f"**File**: {issue.file_path}")
                        if issue.line_number:
                            report.append(f"**Line**: {issue.line_number}")
                        report.append(f"**Description**: {issue.description}")
                        if issue.code_snippet:
                            report.append(f"**Code**: `{issue.code_snippet}`")
                        report.append(f"**Recommendation**: {issue.recommendation}")
                        if issue.cwe_id:
                            report.append(f"**CWE**: {issue.cwe_id}")
                        if issue.owasp_category:
                            report.append(f"**OWASP**: {issue.owasp_category}")
                        report.append("")

        # Recommendations
        report.append("## SECURITY RECOMMENDATIONS")
        recommendations = [
            "1. **Immediate Actions** (Critical/High Issues)",
            "   - Address all critical vulnerabilities immediately",
            "   - Implement proper authentication and authorization",
            "   - Fix SQL injection vulnerabilities",
            "   - Remove hardcoded credentials",
            "",
            "2. **Short-term Actions** (Medium Issues)",
            "   - Implement proper input validation",
            "   - Configure CORS properly",
            "   - Add security headers",
            "   - Improve error handling",
            "",
            "3. **Long-term Actions** (Low Issues & Best Practices)",
            "   - Implement security monitoring",
            "   - Add automated security testing",
            "   - Create security documentation",
            "   - Train developers on secure coding",
            "",
            "4. **Infrastructure Security**",
            "   - Use HTTPS in production",
            "   - Implement rate limiting",
            "   - Add monitoring and alerting",
            "   - Regular security assessments",
        ]
        report.extend(recommendations)

        # OWASP Top 10 Mapping
        report.append("")
        report.append("## OWASP TOP 10 2021 MAPPING")
        owasp_mapping = {
            "A01:2021-Injection": "SQL Injection, Command Injection",
            "A02:2021-Cryptographic Failures": "Weak cryptography, hardcoded secrets",
            "A03:2021-Injection": "XSS, deserialization, input validation",
            "A04:2021-Insecure Design": "Missing access controls, rate limiting",
            "A05:2021-Security Misconfiguration": "Debug mode, CORS, headers",
            "A06:2021-Vulnerable and Outdated Components": "Dependency issues",
            "A07:2021-Identification and Authentication Failures": "Auth bypass, weak auth",
            "A08:2021-Software and Data Integrity Failures": "Insecure deserialization",
            "A09:2021-Security Logging and Monitoring Failures": "Missing logging",
            "A10:2021-Server-Side Request Forgery": "SSRF vulnerabilities",
        }

        for category, description in owasp_mapping.items():
            issues = [i for i in self.issues if i.owasp_category == category]
            if issues:
                report.append(f"**{category}**: {len(issues)} issue(s) - {description}")

        report.append("")
        report.append("---")
        report.append("*This report was generated by the Security Code Auditor*")
        report.append("*Complement this analysis with dynamic penetration testing*")

        return "\n".join(report)

def main():
    """Main function to run the security audit."""
    auditor = SecurityAuditor()
    auditor.run_audit()

    report = auditor.generate_report()

    # Save report
    report_file = f"security_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"\nSecurity audit completed!")
    print(f"Report saved to: {report_file}")
    print(f"Total issues found: {len(auditor.issues)}")

    # Print summary
    critical = len([i for i in auditor.issues if i.severity == "CRITICAL"])
    high = len([i for i in auditor.issues if i.severity == "HIGH"])
    medium = len([i for i in auditor.issues if i.severity == "MEDIUM"])

    print(f"\nSeverity breakdown:")
    print(f"  Critical: {critical}")
    print(f"  High: {high}")
    print(f"  Medium: {medium}")
    print(f"  Low: {len(auditor.issues) - critical - high - medium}")

    if critical > 0 or high > 0:
        print("\n🚨 Critical or High severity issues found - Immediate attention required!")

if __name__ == "__main__":
    main()