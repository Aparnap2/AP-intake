"""
Focused Validation Testing Suite

This module provides targeted testing of specific validation scenarios to identify and fix
issues in the validation framework. Tests are designed to isolate specific validation logic
and provide detailed diagnostic information.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.validation_engine import ValidationEngine
from app.api.schemas.validation import ValidationCode, ValidationSeverity

logger = logging.getLogger(__name__)


class FocusedValidationTestSuite:
    """Focused validation testing to diagnose specific issues."""

    def __init__(self):
        self.validation_engine = ValidationEngine()
        self.test_results = {}

    async def run_focused_tests(self) -> Dict[str, Any]:
        """Run focused validation tests to identify specific issues."""
        logger.info("Starting focused validation testing")

        # Test each validation component separately
        await self._test_structural_validation()
        await self._test_mathematical_validation()
        await self._test_field_mapping()

        return self.test_results

    async def _test_structural_validation(self):
        """Test structural validation with detailed diagnostics."""
        logger.info("Testing structural validation logic")

        test_cases = [
            {
                "name": "valid_invoice_structure",
                "description": "Test completely valid invoice structure",
                "data": {
                    "header": {
                        "vendor_name": "Acme Corporation",
                        "invoice_number": "INV-2024-001",
                        "total_amount": "150.00",
                        "subtotal_amount": "135.00",
                        "tax_amount": "15.00",
                        "invoice_date": "2024-01-15",
                        "currency": "USD"
                    },
                    "lines": [
                        {
                            "description": "Consulting Services",
                            "quantity": 1,
                            "unit_price": "135.00",
                            "total_amount": "135.00"
                        }
                    ],
                    "confidence": {"overall": 0.95}
                },
                "should_pass": True
            },
            {
                "name": "missing_vendor_name",
                "description": "Test invoice with empty vendor name",
                "data": {
                    "header": {
                        "vendor_name": "",
                        "invoice_number": "INV-2024-002",
                        "total_amount": "100.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                },
                "should_pass": False,
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD]
            },
            {
                "name": "invalid_date_format",
                "description": "Test with invalid date format",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-003",
                        "total_amount": "100.00",
                        "invoice_date": "not-a-date"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                },
                "should_pass": False,
                "expected_errors": [ValidationCode.INVALID_FIELD_FORMAT]
            }
        ]

        results = []
        for test_case in test_cases:
            result = await self._run_single_validation_test(test_case, "structural")
            results.append(result)

        self.test_results["structural_validation"] = results

    async def _test_mathematical_validation(self):
        """Test mathematical validation with detailed diagnostics."""
        logger.info("Testing mathematical validation logic")

        test_cases = [
            {
                "name": "perfect_calculations",
                "description": "Test with perfect mathematical calculations",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-004",
                        "total_amount": "220.00",
                        "subtotal_amount": "200.00",
                        "tax_amount": "20.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [
                        {
                            "description": "Item 1",
                            "quantity": 2,
                            "unit_price": "100.00",
                            "total_amount": "200.00"
                        }
                    ],
                    "confidence": {"overall": 0.95}
                },
                "should_pass": True
            },
            {
                "name": "line_calculation_error",
                "description": "Test with incorrect line item calculation",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-005",
                        "total_amount": "250.00",
                        "subtotal_amount": "250.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [
                        {
                            "description": "Item 1",
                            "quantity": 2,
                            "unit_price": "100.00",
                            "total_amount": "250.00"  # Should be 200.00
                        }
                    ],
                    "confidence": {"overall": 0.8}
                },
                "should_pass": False,
                "expected_errors": [ValidationCode.LINE_MATH_MISMATCH]
            },
            {
                "name": "total_mismatch",
                "description": "Test with total amount mismatch",
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-006",
                        "total_amount": "300.00",  # Wrong - should be 220.00
                        "subtotal_amount": "200.00",
                        "tax_amount": "20.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [
                        {
                            "description": "Item 1",
                            "quantity": 2,
                            "unit_price": "100.00",
                            "total_amount": "200.00"
                        }
                    ],
                    "confidence": {"overall": 0.8}
                },
                "should_pass": False,
                "expected_errors": [ValidationCode.TOTAL_MISMATCH]
            }
        ]

        results = []
        for test_case in test_cases:
            result = await self._run_single_validation_test(test_case, "mathematical")
            results.append(result)

        self.test_results["mathematical_validation"] = results

    async def _test_field_mapping(self):
        """Test field mapping logic specifically."""
        logger.info("Testing field mapping logic")

        # Test different field name variations
        field_variations = [
            {"vendor_name": "Test Vendor", "total_amount": "100.00"},
            {"vendor": "Test Vendor", "total": "100.00"},
            {"vendor": "Test Vendor", "amount": "100.00"},
            {"vendor_name": "Test Vendor", "amount": "100.00"}
        ]

        results = []
        for i, header_data in enumerate(field_variations):
            test_case = {
                "name": f"field_mapping_test_{i+1}",
                "description": f"Test field mapping with: {list(header_data.keys())}",
                "data": {
                    "header": {
                        **header_data,
                        "invoice_number": f"INV-FIELD-{i+1}",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                },
                "should_pass": True
            }
            result = await self._run_single_validation_test(test_case, "field_mapping")
            results.append(result)

        self.test_results["field_mapping"] = results

    async def _run_single_validation_test(self, test_case: Dict[str, Any], test_type: str) -> Dict[str, Any]:
        """Run a single validation test and capture detailed results."""
        try:
            result = await self.validation_engine.validate_comprehensive(
                extraction_result=test_case["data"],
                invoice_id=f"test-{test_case['name']}",
                strict_mode=False
            )

            # Analyze results
            test_result = {
                "test_name": test_case["name"],
                "test_description": test_case["description"],
                "test_type": test_type,
                "should_pass": test_case["should_pass"],
                "validation_passed": result.passed,
                "total_issues": result.total_issues,
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "confidence_score": result.confidence_score,
                "issues_found": [
                    {
                        "code": issue.code.value,
                        "message": issue.message,
                        "severity": issue.severity.value,
                        "field": issue.field,
                        "details": issue.details
                    }
                    for issue in result.issues
                ],
                "math_validation": None,
                "header_summary": result.header_summary,
                "lines_summary": result.lines_summary
            }

            if result.math_validation:
                test_result["math_validation"] = {
                    "lines_total": result.math_validation.lines_total,
                    "subtotal_match": result.math_validation.subtotal_match,
                    "total_match": result.math_validation.total_match,
                    "subtotal_difference": result.math_validation.subtotal_difference,
                    "total_difference": result.math_validation.total_difference,
                    "tax_amount": result.math_validation.tax_amount
                }

            # Evaluate if test passed
            expected_errors = test_case.get("expected_errors", [])
            if not expected_errors:
                # Should pass with no errors
                test_result["test_passed"] = result.passed and result.error_count == 0
            else:
                # Should fail with specific errors
                actual_error_codes = [issue["code"] for issue in test_result["issues_found"]]
                test_result["test_passed"] = (
                    not result.passed and
                    any(expected in actual_error_codes for expected in [code.value for code in expected_errors])
                )

            return test_result

        except Exception as e:
            logger.error(f"Test {test_case['name']} failed with error: {e}")
            return {
                "test_name": test_case["name"],
                "test_type": test_type,
                "test_passed": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def generate_diagnostic_report(self) -> str:
        """Generate detailed diagnostic report."""
        report = []
        report.append("="*80)
        report.append("FOCUSED VALIDATION DIAGNOSTIC REPORT")
        report.append("="*80)

        for category, tests in self.test_results.items():
            report.append(f"\n{category.upper()} RESULTS:")
            report.append("-" * 40)

            total_tests = len(tests)
            passed_tests = sum(1 for test in tests if test.get("test_passed", False))

            report.append(f"Success Rate: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")

            for test in tests:
                status = "PASS" if test.get("test_passed", False) else "FAIL"
                report.append(f"  [{status}] {test['test_name']}")
                report.append(f"    Description: {test['test_description']}")

                if not test.get("test_passed", False):
                    if "error" in test:
                        report.append(f"    Error: {test['error']}")
                    else:
                        report.append(f"    Expected: {'PASS' if test['should_pass'] else 'FAIL'}")
                        report.append(f"    Actual: {'PASS' if test['validation_passed'] else 'FAIL'}")
                        if test.get("issues_found"):
                            report.append("    Issues Found:")
                            for issue in test["issues_found"]:
                                report.append(f"      - {issue['code']}: {issue['message']}")

        # Add specific findings and recommendations
        report.append("\n" + "="*80)
        report.append("KEY FINDINGS AND RECOMMENDATIONS")
        report.append("="*80)

        findings = self._analyze_results()
        for finding in findings:
            report.append(f"\n• {finding}")

        return "\n".join(report)

    def _analyze_results(self) -> List[str]:
        """Analyze test results and generate findings."""
        findings = []

        # Analyze structural validation
        if "structural_validation" in self.test_results:
            structural_tests = self.test_results["structural_validation"]
            valid_invoice_test = next((t for t in structural_tests if t["test_name"] == "valid_invoice_structure"), None)

            if valid_invoice_test and not valid_invoice_test.get("test_passed", False):
                findings.append("CRITICAL: Valid invoices are failing structural validation - check field mapping logic")

        # Analyze mathematical validation
        if "mathematical_validation" in self.test_results:
            math_tests = self.test_results["mathematical_validation"]
            perfect_calc_test = next((t for t in math_tests if t["test_name"] == "perfect_calculations"), None)

            if perfect_calc_test and not perfect_calc_test.get("test_passed", False):
                findings.append("CRITICAL: Perfect mathematical calculations are failing - check tolerance and precision logic")

        # Analyze field mapping
        if "field_mapping" in self.test_results:
            field_tests = self.test_results["field_mapping"]
            failed_mappings = [t for t in field_tests if not t.get("test_passed", False)]

            if failed_mappings:
                findings.append(f"ISSUE: {len(failed_mappings)} field mapping variations are failing - expand field mapping logic")

        # Overall assessment
        total_tests = sum(len(tests) for tests in self.test_results.values())
        total_passed = sum(
            sum(1 for test in tests if test.get("test_passed", False))
            for tests in self.test_results.values()
        )

        if total_passed / total_tests < 0.8:
            findings.append("OVERALL: Validation framework requires significant improvement before production use")
        elif total_passed / total_tests < 0.95:
            findings.append("OVERALL: Validation framework needs targeted improvements for production readiness")
        else:
            findings.append("OVERALL: Validation framework is performing well")

        return findings


async def main():
    """Run focused validation tests and generate report."""
    test_suite = FocusedValidationTestSuite()
    await test_suite.run_focused_tests()

    report = test_suite.generate_diagnostic_report()
    print(report)

    # Save report to file
    with open("focused_validation_diagnostic_report.txt", "w") as f:
        f.write(report)

    print(f"\nDetailed report saved to: focused_validation_diagnostic_report.txt")


if __name__ == "__main__":
    asyncio.run(main())