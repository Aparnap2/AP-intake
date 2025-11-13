"""
Simple Standalone Validation Test

This module tests the core validation logic without complex dependencies.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simplified validation components for testing
class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationCode(str, Enum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_FORMAT = "INVALID_FIELD_FORMAT"
    NO_LINE_ITEMS = "NO_LINE_ITEMS"
    SUBTOTAL_MISMATCH = "SUBTOTAL_MISMATCH"
    TOTAL_MISMATCH = "TOTAL_MISMATCH"
    LINE_MATH_MISMATCH = "LINE_MATH_MISMATCH"
    INVALID_AMOUNT = "INVALID_AMOUNT"

class SimpleValidationIssue:
    def __init__(self, code: str, message: str, severity: str, details: Dict = None):
        self.code = code
        self.message = message
        self.severity = severity
        self.details = details or {}

class SimpleValidationResult:
    def __init__(self):
        self.passed = True
        self.issues = []
        self.confidence_score = 0.0
        self.error_count = 0
        self.warning_count = 0

class SimpleValidationEngine:
    """Simplified validation engine for testing core logic."""

    def __init__(self):
        self.tolerance_cents = 1

    def validate_required_fields(self, header: Dict[str, Any]) -> List[SimpleValidationIssue]:
        """Validate required header fields."""
        issues = []
        required_fields = ["vendor_name", "invoice_number", "total_amount"]

        for field in required_fields:
            value = header.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(SimpleValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message=f"Missing required field: {field}",
                    severity=ValidationSeverity.ERROR,
                    details={"field": field}
                ))

        return issues

    def validate_field_formats(self, header: Dict[str, Any]) -> List[SimpleValidationIssue]:
        """Validate field formats."""
        issues = []

        # Validate date format
        invoice_date = header.get("invoice_date")
        if invoice_date and not self._is_valid_date(invoice_date):
            issues.append(SimpleValidationIssue(
                code=ValidationCode.INVALID_FIELD_FORMAT,
                message=f"Invalid date format: {invoice_date}",
                severity=ValidationSeverity.ERROR,
                details={"field": "invoice_date", "value": invoice_date}
            ))

        # Validate amount format
        total_amount = header.get("total_amount")
        if total_amount and not self._is_valid_amount(total_amount):
            issues.append(SimpleValidationIssue(
                code=ValidationCode.INVALID_FIELD_FORMAT,
                message=f"Invalid amount format: {total_amount}",
                severity=ValidationSeverity.ERROR,
                details={"field": "total_amount", "value": total_amount}
            ))

        return issues

    def validate_line_items(self, lines: List[Dict[str, Any]]) -> List[SimpleValidationIssue]:
        """Validate line items."""
        issues = []

        if not lines:
            issues.append(SimpleValidationIssue(
                code=ValidationCode.NO_LINE_ITEMS,
                message="No line items found",
                severity=ValidationSeverity.ERROR
            ))
            return issues

        # Validate line item calculations
        for i, line in enumerate(lines):
            try:
                quantity = self._safe_decimal(line.get("quantity", 1))
                unit_price = self._safe_decimal(line.get("unit_price", 0))
                amount = self._safe_decimal(line.get("total_amount") or line.get("amount", 0))

                expected_amount = quantity * unit_price
                difference = abs(amount - expected_amount)

                if difference > Decimal(str(self.tolerance_cents / 100)):
                    issues.append(SimpleValidationIssue(
                        code=ValidationCode.LINE_MATH_MISMATCH,
                        message=f"Line {i+1} calculation error: {quantity} × {unit_price} = {expected_amount}, got {amount}",
                        severity=ValidationSeverity.ERROR,
                        details={
                            "line_number": i+1,
                            "quantity": float(quantity),
                            "unit_price": float(unit_price),
                            "actual_amount": float(amount),
                            "expected_amount": float(expected_amount),
                            "difference": float(difference)
                        }
                    ))

            except (InvalidOperation, TypeError) as e:
                issues.append(SimpleValidationIssue(
                    code=ValidationCode.INVALID_AMOUNT,
                    message=f"Invalid numeric values in line {i+1}: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                    details={"line_number": i+1, "error": str(e)}
                ))

        return issues

    def validate_mathematical_calculations(self, header: Dict[str, Any], lines: List[Dict[str, Any]]) -> List[SimpleValidationIssue]:
        """Validate mathematical calculations."""
        issues = []

        if not lines:
            return issues

        try:
            # Calculate lines total
            lines_total = sum(
                self._safe_decimal(line.get("total_amount") or line.get("amount", 0))
                for line in lines
            )

            # Validate subtotal
            header_subtotal = self._safe_decimal(header.get("subtotal_amount", 0))
            if header_subtotal > 0:
                difference = abs(lines_total - header_subtotal)
                tolerance = Decimal(str(self.tolerance_cents / 100))

                if difference > tolerance:
                    issues.append(SimpleValidationIssue(
                        code=ValidationCode.SUBTOTAL_MISMATCH,
                        message=f"Subtotal mismatch: lines total {lines_total}, header subtotal {header_subtotal}",
                        severity=ValidationSeverity.ERROR,
                        details={
                            "lines_total": float(lines_total),
                            "header_subtotal": float(header_subtotal),
                            "difference": float(difference),
                            "tolerance": float(tolerance)
                        }
                    ))

            # Validate total amount
            header_total = self._safe_decimal(header.get("total_amount", 0))
            tax_amount = self._safe_decimal(header.get("tax_amount", 0))
            expected_total = (header_subtotal if header_subtotal > 0 else lines_total) + tax_amount

            if header_total > 0:
                difference = abs(header_total - expected_total)
                tolerance = Decimal(str(self.tolerance_cents / 100))

                if difference > tolerance:
                    issues.append(SimpleValidationIssue(
                        code=ValidationCode.TOTAL_MISMATCH,
                        message=f"Total amount mismatch: expected {expected_total}, actual {header_total}",
                        severity=ValidationSeverity.ERROR,
                        details={
                            "expected_total": float(expected_total),
                            "actual_total": float(header_total),
                            "difference": float(difference),
                            "tolerance": float(tolerance)
                        }
                    ))

        except Exception as e:
            issues.append(SimpleValidationIssue(
                code=ValidationCode.INVALID_AMOUNT,
                message=f"Calculation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error": str(e)}
            ))

        return issues

    def validate_comprehensive(self, extraction_result: Dict[str, Any]) -> SimpleValidationResult:
        """Perform comprehensive validation."""
        result = SimpleValidationResult()

        header = extraction_result.get("header", {})
        lines = extraction_result.get("lines", [])
        confidence = extraction_result.get("confidence", {})

        # Run all validations
        result.issues.extend(self.validate_required_fields(header))
        result.issues.extend(self.validate_field_formats(header))
        result.issues.extend(self.validate_line_items(lines))
        result.issues.extend(self.validate_mathematical_calculations(header, lines))

        # Calculate result
        result.error_count = sum(1 for issue in result.issues if issue.severity == ValidationSeverity.ERROR)
        result.warning_count = sum(1 for issue in result.issues if issue.severity == ValidationSeverity.WARNING)
        result.passed = result.error_count == 0
        result.confidence_score = confidence.get("overall", 0.0)

        return result

    def _is_valid_date(self, date_value: Any) -> bool:
        """Check if date value is valid."""
        if isinstance(date_value, datetime):
            return True

        if isinstance(date_value, str):
            date_patterns = [
                r"^\d{4}-\d{2}-\d{2}$",
                r"^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$"
            ]
            import re
            return any(re.match(pattern, date_value.strip()) for pattern in date_patterns)

        return False

    def _is_valid_amount(self, amount_value: Any) -> bool:
        """Check if amount value is valid."""
        try:
            if isinstance(amount_value, (int, float, Decimal)):
                return float(amount_value) >= 0

            if isinstance(amount_value, str):
                cleaned = amount_value.replace("$", "").replace(",", "").strip()
                amount = float(cleaned)
                return amount >= 0
        except (ValueError, TypeError):
            pass

        return False

    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None:
            return Decimal("0")

        try:
            if isinstance(value, Decimal):
                return value
            elif isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                cleaned = value.replace("$", "").replace(",", "").strip()
                return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            pass

        return Decimal("0")


class ValidationTestSuite:
    """Comprehensive validation test suite."""

    def __init__(self):
        self.engine = SimpleValidationEngine()
        self.results = []

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests."""
        logger.info("Starting comprehensive validation test suite")

        test_cases = self._create_test_cases()

        for test_case in test_cases:
            result = await self._run_test(test_case)
            self.results.append(result)

        return self._generate_summary()

    def _create_test_cases(self) -> List[Dict[str, Any]]:
        """Create comprehensive test cases."""
        return [
            # Structural validation tests
            {
                "name": "valid_invoice_structure",
                "category": "structural",
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
                "category": "structural",
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
                "name": "invalid_date_format",
                "category": "structural",
                "description": "Test with invalid date format",
                "should_pass": False,
                "expected_errors": [ValidationCode.INVALID_FIELD_FORMAT],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-003",
                        "total_amount": "100.00",
                        "invoice_date": "not-a-valid-date"
                    },
                    "lines": [{"description": "Test", "total_amount": "100.00"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "invalid_amount_format",
                "category": "structural",
                "description": "Test with invalid amount format",
                "should_pass": False,
                "expected_errors": [ValidationCode.INVALID_FIELD_FORMAT],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-004",
                        "total_amount": "invalid-amount",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [{"description": "Test", "total_amount": "invalid-amount"}],
                    "confidence": {"overall": 0.8}
                }
            },
            {
                "name": "no_line_items",
                "category": "structural",
                "description": "Test invoice with no line items",
                "should_pass": False,
                "expected_errors": [ValidationCode.NO_LINE_ITEMS],
                "data": {
                    "header": {
                        "vendor_name": "Test Vendor",
                        "invoice_number": "INV-2024-005",
                        "total_amount": "100.00",
                        "invoice_date": "2024-01-15"
                    },
                    "lines": [],
                    "confidence": {"overall": 0.8}
                }
            },

            # Mathematical validation tests
            {
                "name": "perfect_calculations",
                "category": "mathematical",
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
                "name": "line_calculation_error",
                "category": "mathematical",
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
                "category": "mathematical",
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
                "category": "mathematical",
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
                "category": "mathematical",
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
                "name": "multiple_line_items",
                "category": "mathematical",
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

    async def _run_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test case."""
        try:
            result = self.engine.validate_comprehensive(test_case["data"])

            test_result = {
                "name": test_case["name"],
                "category": test_case["category"],
                "description": test_case["description"],
                "should_pass": test_case["should_pass"],
                "validation_passed": result.passed,
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "confidence_score": result.confidence_score,
                "issues": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "severity": issue.severity,
                        "details": issue.details
                    }
                    for issue in result.issues
                ],
                "test_passed": self._evaluate_test_result(test_case, result)
            }

            return test_result

        except Exception as e:
            logger.error(f"Test {test_case['name']} failed with error: {e}")
            return {
                "name": test_case["name"],
                "category": test_case["category"],
                "test_passed": False,
                "error": str(e)
            }

    def _evaluate_test_result(self, test_case: Dict[str, Any], result: SimpleValidationResult) -> bool:
        """Evaluate if test passed."""
        expected_errors = test_case.get("expected_errors", [])

        if not expected_errors:
            # Should pass with no errors
            return result.passed and result.error_count == 0
        else:
            # Should fail with specific errors
            actual_error_codes = [issue.code for issue in result.issues]
            expected_error_codes = [code.value for code in expected_errors]

            # Check if any expected error is found
            has_expected_error = any(expected in actual_error_codes for expected in expected_error_codes)

            # Should not pass and should have expected errors
            return not result.passed and has_expected_error

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results if result.get("test_passed", False))

        category_results = {}
        for category in ["structural", "mathematical"]:
            category_tests = [r for r in self.results if r.get("category") == category]
            if category_tests:
                passed = sum(1 for r in category_tests if r.get("test_passed", False))
                category_results[category] = {
                    "total": len(category_tests),
                    "passed": passed,
                    "success_rate": (passed / len(category_tests) * 100)
                }

        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "overall_success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "category_results": category_results,
            "detailed_results": self.results
        }


async def main():
    """Run the validation test suite."""
    test_suite = ValidationTestSuite()
    results = await test_suite.run_all_tests()

    # Generate report
    report = []
    report.append("="*80)
    report.append("SIMPLE VALIDATION FRAMEWORK TEST REPORT")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Overall results
    report.append("OVERALL RESULTS:")
    report.append(f"  Total Tests: {results['total_tests']}")
    report.append(f"  Passed: {results['passed_tests']}")
    report.append(f"  Success Rate: {results['overall_success_rate']:.1f}%")
    report.append("")

    # Category results
    report.append("CATEGORY RESULTS:")
    for category, stats in results["category_results"].items():
        status = "✓" if stats["success_rate"] >= 90 else "✗" if stats["success_rate"] < 70 else "⚠"
        report.append(f"  {status} {category.title()}: {stats['success_rate']:.1f}% ({stats['passed']}/{stats['total']})")
    report.append("")

    # Detailed results
    report.append("DETAILED RESULTS:")
    report.append("-" * 60)

    for result in results["detailed_results"]:
        status = "PASS" if result.get("test_passed", False) else "FAIL"
        report.append(f"  [{status}] {result['name']} ({result['category']})")
        report.append(f"    Description: {result['description']}")

        if not result.get("test_passed", False):
            report.append(f"    Expected: {'PASS' if result['should_pass'] else 'FAIL'}")
            report.append(f"    Actual: {'PASS' if result['validation_passed'] else 'FAIL'}")

            if result.get("issues"):
                report.append("    Issues:")
                for issue in result["issues"]:
                    report.append(f"      - {issue['code']}: {issue['message']}")

        report.append(f"    Confidence: {result.get('confidence_score', 0):.3f}")
        report.append("")

    # Assessment
    report.append("="*80)
    report.append("ASSESSMENT")
    report.append("="*80)

    success_rate = results["overall_success_rate"]
    if success_rate >= 95:
        assessment = "EXCELLENT - Production Ready"
    elif success_rate >= 90:
        assessment = "GOOD - Near Production Ready"
    elif success_rate >= 80:
        assessment = "FAIR - Needs Improvement"
    else:
        assessment = "POOR - Not Production Ready"

    report.append(f"Overall Assessment: {assessment}")
    report.append(f"Success Rate: {success_rate:.1f}%")

    if success_rate < 90:
        report.append("\nRECOMMENDATIONS:")
        if "structural" in results["category_results"] and results["category_results"]["structural"]["success_rate"] < 90:
            report.append("• Fix structural validation issues")
        if "mathematical" in results["category_results"] and results["category_results"]["mathematical"]["success_rate"] < 90:
            report.append("• Review mathematical validation logic")
        report.append("• Overall framework requires improvement before production")

    report_text = "\n".join(report)
    print(report_text)

    # Save report
    with open("simple_validation_test_report.txt", "w") as f:
        f.write(report_text)

    print(f"\nReport saved to: simple_validation_test_report.txt")
    return results


if __name__ == "__main__":
    asyncio.run(main())