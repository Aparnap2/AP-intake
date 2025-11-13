"""
Standalone Comprehensive Validation Test Suite

This module runs comprehensive validation tests without database dependencies
to accurately assess the validation framework's logic and performance.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from validation_test_engine import TestValidationEngine
from app.api.schemas.validation import ValidationCode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StandaloneValidationTestSuite:
    """Standalone validation test suite using TestValidationEngine."""

    def __init__(self):
        self.validation_engine = TestValidationEngine()
        self.test_results = {
            "structural_tests": [],
            "mathematical_tests": [],
            "field_mapping_tests": [],
            "summary": {}
        }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests without database dependencies."""
        logger.info("Starting standalone comprehensive validation testing")

        await self._run_structural_validation_tests()
        await self._run_mathematical_validation_tests()
        await self._run_field_mapping_tests()

        self._generate_summary()
        return self.test_results

    async def _run_structural_validation_tests(self):
        """Test structural validation scenarios."""
        logger.info("Running structural validation tests")

        test_cases = [
            {
                "name": "completely_valid_invoice",
                "description": "Test completely valid invoice structure",
                "should_pass": True,
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
                }
            },
            {
                "name": "missing_vendor_name",
                "description": "Test invoice with missing vendor name",
                "should_pass": False,
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD],
                "data": {
                    "header": {
                        "vendor_name": "",
                        "invoice_number": "INV-2024-002",
                        "total_amount": "100.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "missing_invoice_number",
                "description": "Test invoice with missing invoice number",
                "should_pass": False,
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "",
                        "total_amount": "100.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "missing_total_amount",
                "description": "Test invoice with missing total amount",
                "should_pass": False,
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-003",
                        "total_amount": "",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "invalid_date_format",
                "description": "Test with invalid date format",
                "should_pass": False,
                "expected_errors": [ValidationCode.INVALID_FIELD_FORMAT],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-004",
                        "total_amount": "100.00",
                        "invoice_date": "not-a-valid-date"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "invalid_amount_format",
                "description": "Test with invalid amount format",
                "should_pass": False,
                "expected_errors": [ValidationCode.INVALID_FIELD_FORMAT],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-005",
                        "total_amount": "invalid-amount",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "invalid-amount"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "no_line_items",
                "description": "Test invoice with no line items",
                "should_pass": False,
                "expected_errors": [ValidationCode.NO_LINE_ITEMS],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-006",
                        "total_amount": "100.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [],
                    "confidence": {"overall": 0.8}
                }
            }
        ]

        for test_case in test_cases:
            result = await self._run_validation_test(test_case, "structural")
            self.test_results["structural_tests"].append(result)

    async def _run_mathematical_validation_tests(self):
        """Test mathematical validation scenarios."""
        logger.info("Running mathematical validation tests")

        test_cases = [
            {
                "name": "perfect_calculations",
                "description": "Test with perfect mathematical calculations",
                "should_pass": True,
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-001",
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
                }
            },
            {
                "name": "line_item_calculation_error",
                "description": "Test with incorrect line item calculation",
                "should_pass": False,
                "expected_errors": [ValidationCode.LINE_MATH_MISMATCH],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-002",
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
                }
            },
            {
                "name": "subtotal_mismatch",
                "description": "Test with subtotal mismatch",
                "should_pass": False,
                "expected_errors": [ValidationCode.SUBTOTAL_MISMATCH],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-003",
                        "total_amount": "275.00",
                        "subtotal_amount": "250.00",  # Should be 200.00
                        "tax_amount": "25.00",
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
                }
            },
            {
                "name": "total_amount_mismatch",
                "description": "Test with total amount mismatch",
                "should_pass": False,
                "expected_errors": [ValidationCode.TOTAL_MISMATCH],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-004",
                        "total_amount": "300.00",  # Should be 220.00
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
                }
            },
            {
                "name": "rounding_precision_test",
                "description": "Test with rounding precision challenges",
                "should_pass": True,  # Should pass with tolerance
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-005",
                        "total_amount": "33.34",
                        "subtotal_amount": "33.33",
                        "tax_amount": "0.01",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [
                        {
                            "description": "Item 1",
                            "quantity": 3,
                            "unit_price": "11.11",
                            "total_amount": "33.33"
                        }
                    ],
                    "confidence": {"overall": 0.9}
                }
            },
            {
                "name": "multiple_line_items_math",
                "description": "Test with multiple line items",
                "should_pass": True,
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-MATH-006",
                        "total_amount": "330.00",
                        "subtotal_amount": "300.00",
                        "tax_amount": "30.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [
                        {
                            "description": "Item 1",
                            "quantity": 2,
                            "unit_price": "100.00",
                            "total_amount": "200.00"
                        },
                        {
                            "description": "Item 2",
                            "quantity": 1,
                            "unit_price": "100.00",
                            "total_amount": "100.00"
                        }
                    ],
                    "confidence": {"overall": 0.95}
                }
            }
        ]

        for test_case in test_cases:
            result = await self._run_validation_test(test_case, "mathematical")
            self.test_results["mathematical_tests"].append(result)

    async def _run_field_mapping_tests(self):
        """Test different field name variations."""
        logger.info("Running field mapping tests")

        test_cases = [
            {
                "name": "standard_field_names",
                "description": "Test with standard field names",
                "should_pass": True,
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "total_amount": "100.00",
                        "invoice_number": "INV-FIELD-001",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "alternative_field_names",
                "description": "Test with alternative field names",
                "should_pass": False,  # Should fail - field mapping issue
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD],
                "data": {
                    "header": {
                        "vendor": "Test Vendor",  # Different field name
                        "amount": "100.00",      # Different field name
                        "invoice_no": "INV-FIELD-002",  # Different field name
                        "date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "mixed_field_names",
                "description": "Test with mixed field name conventions",
                "should_pass": False,  # Should fail - inconsistent field names
                "expected_errors": [ValidationCode.MISSING_REQUIRED_FIELD],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "amount": "100.00",  # Should be "total_amount"
                        "invoice_number": "INV-FIELD-003",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            }
        ]

        for test_case in test_cases:
            result = await self._run_validation_test(test_case, "field_mapping")
            self.test_results["field_mapping_tests"].append(result)

    async def _run_validation_test(self, test_case: Dict[str, Any], test_type: str) -> Dict[str, Any]:
        """Run a single validation test."""
        try:
            result = await self.validation_engine.validate_comprehensive(
                extraction_result=test_case["data"],
                invoice_id=f"test-{test_case['name']}",
                strict_mode=False,
                skip_db_operations=True
            )

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
                "test_passed": self._evaluate_test_result(test_case, result)
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

    def _evaluate_test_result(self, test_case: Dict[str, Any], result) -> bool:
        """Evaluate if a test passed based on expected vs actual results."""
        expected_errors = test_case.get("expected_errors", [])

        if not expected_errors:
            # Should pass with no errors
            return result.passed and result.error_count == 0
        else:
            # Should fail with specific errors
            actual_error_codes = [issue.code.value for issue in result.issues]
            expected_error_codes = [code.value for code in expected_errors]

            # Check if any expected error is found
            has_expected_error = any(expected in actual_error_codes for expected in expected_error_codes)

            # Should not pass and should have expected errors
            return not result.passed and has_expected_error

    def _generate_summary(self):
        """Generate test summary."""
        all_tests = []
        for category in ["structural_tests", "mathematical_tests", "field_mapping_tests"]:
            all_tests.extend(self.test_results[category])

        total_tests = len(all_tests)
        passed_tests = sum(1 for test in all_tests if test.get("test_passed", False))

        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "category_results": {
                "structural_validation": self._calculate_category_stats("structural_tests"),
                "mathematical_validation": self._calculate_category_stats("mathematical_tests"),
                "field_mapping": self._calculate_category_stats("field_mapping_tests")
            }
        }

    def _calculate_category_stats(self, category_key: str) -> Dict[str, Any]:
        """Calculate statistics for a test category."""
        tests = self.test_results[category_key]
        if not tests:
            return {"tests_run": 0, "tests_passed": 0, "success_rate": 0}

        passed = sum(1 for test in tests if test.get("test_passed", False))
        return {
            "tests_run": len(tests),
            "tests_passed": passed,
            "success_rate": (passed / len(tests) * 100)
        }

    def generate_report(self) -> str:
        """Generate comprehensive test report."""
        report = []
        report.append("="*80)
        report.append("STANDALONE VALIDATION FRAMEWORK TEST REPORT")
        report.append("="*80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Test Engine: TestValidationEngine (database-free)")
        report.append("")

        # Summary
        summary = self.test_results["summary"]
        report.append("OVERALL RESULTS:")
        report.append(f"  Total Tests: {summary['total_tests']}")
        report.append(f"  Passed: {summary['passed_tests']}")
        report.append(f"  Success Rate: {summary['success_rate']:.1f}%")
        report.append("")

        # Category results
        report.append("CATEGORY RESULTS:")
        for category, stats in summary["category_results"].items():
            status = "✓" if stats["success_rate"] >= 90 else "✗" if stats["success_rate"] < 70 else "⚠"
            report.append(f"  {status} {category.replace('_', ' ').title()}: "
                         f"{stats['success_rate']:.1f}% ({stats['tests_passed']}/{stats['tests_run']})")
        report.append("")

        # Detailed results
        for category in ["structural_tests", "mathematical_tests", "field_mapping_tests"]:
            if not self.test_results[category]:
                continue

            report.append(f"{category.upper().replace('_', ' ')}:")
            report.append("-" * 60)

            for test in self.test_results[category]:
                status = "PASS" if test.get("test_passed", False) else "FAIL"
                report.append(f"  [{status}] {test['test_name']}")
                report.append(f"    Description: {test['test_description']}")

                if not test.get("test_passed", False):
                    report.append(f"    Expected: {'PASS' if test['should_pass'] else 'FAIL'}")
                    report.append(f"    Actual: {'PASS' if test['validation_passed'] else 'FAIL'}")

                    if test.get("issues_found"):
                        report.append("    Issues:")
                        for issue in test["issues_found"]:
                            report.append(f"      - {issue['code']}: {issue['message']}")

                    if test.get("math_validation"):
                        math = test["math_validation"]
                        report.append(f"    Math Validation:")
                        report.append(f"      Lines Total: {math['lines_total']}")
                        report.append(f"      Subtotal Match: {math['subtotal_match']}")
                        report.append(f"      Total Match: {math['total_match']}")
                        if math.get("subtotal_difference"):
                            report.append(f"      Subtotal Difference: {math['subtotal_difference']}")
                        if math.get("total_difference"):
                            report.append(f"      Total Difference: {math['total_difference']}")

                report.append(f"    Confidence Score: {test.get('confidence_score', 0):.3f}")
                report.append("")

        # Assessment
        report.append("="*80)
        report.append("ASSESSMENT AND RECOMMENDATIONS")
        report.append("="*80)

        success_rate = summary["success_rate"]
        if success_rate >= 95:
            assessment = "EXCELLENT"
            readiness = "PRODUCTION READY"
        elif success_rate >= 90:
            assessment = "GOOD"
            readiness = "NEAR PRODUCTION READY"
        elif success_rate >= 80:
            assessment = "FAIR"
            readiness = "NEEDS IMPROVEMENT"
        else:
            assessment = "POOR"
            readiness = "NOT PRODUCTION READY"

        report.append(f"Overall Assessment: {assessment}")
        report.append(f"Production Readiness: {readiness}")
        report.append("")

        # Recommendations
        report.append("KEY RECOMMENDATIONS:")

        structural_stats = summary["category_results"]["structural_validation"]
        if structural_stats["success_rate"] < 100:
            report.append("• Fix structural validation issues for production readiness")

        math_stats = summary["category_results"]["mathematical_validation"]
        if math_stats["success_rate"] < 100:
            report.append("• Review mathematical validation logic and tolerance settings")

        field_stats = summary["category_results"]["field_mapping"]
        if field_stats["success_rate"] < 100:
            report.append("• Improve field mapping to handle various data formats")

        if success_rate < 90:
            report.append("• Overall framework requires significant improvement before production")
        elif success_rate >= 95:
            report.append("• Framework performing excellently - proceed with production deployment")

        report.append("")

        return "\n".join(report)


async def main():
    """Run standalone validation tests."""
    test_suite = StandaloneValidationTestSuite()
    await test_suite.run_all_tests()

    report = test_suite.generate_report()
    print(report)

    # Save report
    with open("standalone_validation_test_report.txt", "w") as f:
        f.write(report)

    print(f"\nReport saved to: standalone_validation_test_report.txt")


if __name__ == "__main__":
    asyncio.run(main())