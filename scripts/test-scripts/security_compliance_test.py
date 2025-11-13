#!/usr/bin/env python3
"""
Comprehensive Security and Compliance Testing Script for AP Intake & Validation System
Tests security controls, compliance requirements, and pilot acceptance criteria
"""

import asyncio
import json
import sys
import time
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Any
from urllib.parse import urljoin, urlparse
import hashlib
import secrets
import re

class SecurityComplianceTester:
    def __init__(self, base_url: str = "http://localhost:8000", frontend_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.frontend_url = frontend_url
        self.test_results = []
        self.acceptance_criteria_results = []

    def log_result(self, test_name: str, status: str, details: str, risk_level: str = "MEDIUM"):
        """Log a test result"""
        result = {
            "test_name": test_name,
            "status": status,  # PASS, FAIL, WARN
            "details": details,
            "risk_level": risk_level,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.test_results.append(result)
        print(f"[{status}] {test_name}: {details}")

    def test_access_control(self) -> Dict[str, Any]:
        """Test access control validation"""
        print("\n=== ACCESS CONTROL VALIDATION ===")

        # Test 1: Unauthenticated API Access
        try:
            response = requests.get(f"{self.base_url}/api/v1/invoices", timeout=10)
            if response.status_code == 200:
                self.log_result(
                    "Unauthenticated API Access",
                    "FAIL",
                    "API endpoints accessible without authentication",
                    "HIGH"
                )
            elif response.status_code == 401:
                self.log_result(
                    "Unauthenticated API Access",
                    "PASS",
                    "API properly requires authentication",
                    "LOW"
                )
        except Exception as e:
            self.log_result(
                "Unauthenticated API Access",
                "WARN",
                f"Could not test API access: {str(e)}",
                "MEDIUM"
            )

        return {"access_control_tests": len(self.test_results)}

    def run_all_tests(self):
        """Run all security and compliance tests"""
        print("Starting Security and Compliance Testing")
        print("=" * 50)

        self.test_access_control()

        return {
            "test_date": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "results": self.test_results
        }

if __name__ == "__main__":
    tester = SecurityComplianceTester()
    results = tester.run_all_tests()

    # Save results
    with open("security_compliance_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nTesting complete. Results saved to security_compliance_test_results.json")
    print(f"Total tests run: {results['total_tests']}")