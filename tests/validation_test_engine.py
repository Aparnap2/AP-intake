"""
Test-specific validation engine that operates without database dependencies.

This enables comprehensive validation testing without requiring database setup.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.validation_engine import ValidationEngine, RuleExecutionResult, ReasonTaxonomy
from app.api.schemas.validation import ValidationCode, ValidationSeverity

logger = logging.getLogger(__name__)


class TestValidationEngine(ValidationEngine):
    """
    Test-specific validation engine that mocks database operations for testing.

    This extends the base ValidationEngine but overrides database-dependent methods
    to work with test data and predictable responses.
    """

    def __init__(self):
        super().__init__()
        self.test_vendors = {
            "Acme Corporation": {"id": "vendor-1", "active": True, "currency": "USD"},
            "Acme Corp": {"id": "vendor-1", "active": True, "currency": "USD"},
            "Test Vendor": {"id": "vendor-2", "active": True, "currency": "USD"},
            "Unknown Vendor": {"id": None, "active": False, "currency": "USD"}
        }
        self.test_pos = {
            "PO-001": {"id": "po-1", "vendor_id": "vendor-1", "amount": "1000.00", "status": "open"},
            "PO-002": {"id": "po-2", "vendor_id": "vendor-1", "amount": "2000.00", "status": "open"}
        }

    async def validate_comprehensive(
        self,
        extraction_result: Dict[str, Any],
        invoice_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        strict_mode: bool = False,
        custom_rules: Optional[Dict[str, List]] = None,
        skip_db_operations: bool = True
    ) -> 'ValidationResult':
        """
        Override comprehensive validation to skip database operations when testing.
        """
        from app.api.schemas.validation import ValidationResult, ValidationCheckResult

        start_time = datetime.utcnow()
        logger.info(f"Starting test validation for invoice {invoice_id}")

        # Extract data
        header = extraction_result.get("header", {})
        lines = extraction_result.get("lines", [])
        confidence = extraction_result.get("confidence", {})

        # Initialize results
        all_issues = []
        rule_results = []
        validation_results = {}

        # Create a mock database session
        class MockSession:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        try:
            # Execute validation rules without database dependency
            for category, rules in (custom_rules or self.rules).items():
                if skip_db_operations and category == "business_rules":
                    # Skip database-dependent business rules
                    continue

                category_results = await self._execute_rule_category_test(
                    category, rules, header, lines, confidence, invoice_id, vendor_id
                )
                rule_results.extend(category_results)

                # Collect issues
                for result in category_results:
                    if not result.passed:
                        issue = self._create_validation_issue(result)
                        all_issues.append(issue)

                # Store category-specific results
                if category == "mathematical":
                    validation_results["math_validation"] = self._create_math_result(
                        category_results, header, lines
                    )
                elif category == "business_rules" and not skip_db_operations:
                    validation_results["matching_result"] = self._create_matching_result(
                        category_results, invoice_id, MockSession()
                    )
                    validation_results["vendor_policy_result"] = self._create_vendor_policy_result(
                        category_results
                    )
                    validation_results["duplicate_check_result"] = self._create_duplicate_result(
                        category_results
                    )

            # Calculate overall validation result
            error_count = sum(1 for issue in all_issues if issue.severity == ValidationSeverity.ERROR)
            warning_count = sum(1 for issue in all_issues if issue.severity == ValidationSeverity.WARNING)
            info_count = sum(1 for issue in all_issues if issue.severity == ValidationSeverity.INFO)

            validation_passed = error_count == 0
            if strict_mode:
                validation_passed = validation_passed and warning_count == 0

            # Calculate confidence score
            confidence_score = self._calculate_validation_confidence(rule_results, confidence)

            # Create validation result
            result = ValidationResult(
                passed=validation_passed,
                confidence_score=confidence_score,
                total_issues=len(all_issues),
                error_count=error_count,
                warning_count=warning_count,
                info_count=info_count,
                issues=all_issues,
                math_validation=validation_results.get("math_validation"),
                matching_result=validation_results.get("matching_result"),
                vendor_policy_result=validation_results.get("vendor_policy_result"),
                duplicate_check_result=validation_results.get("duplicate_check_result"),
                check_results=self._create_check_results(rule_results),
                validated_at=start_time,
                rules_version=self.rules_version,
                validator_version="2.0.0-test",
                processing_time_ms=str(int((datetime.utcnow() - start_time).total_seconds() * 1000)),
                header_summary=self._create_header_summary(header),
                lines_summary=self._create_lines_summary(lines)
            )

            logger.info(
                f"Test validation completed for invoice {invoice_id}: "
                f"{'PASSED' if result.passed else 'FAILED'} "
                f"(errors: {error_count}, warnings: {warning_count}, confidence: {confidence_score:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Test validation failed: {e}")
            # Create error result
            from app.api.schemas.validation import ValidationIssue
            error_issue = ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=f"Validation process failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error_type": type(e).__name__}
            )

            return ValidationResult(
                passed=False,
                confidence_score=0.0,
                total_issues=1,
                error_count=1,
                warning_count=0,
                info_count=0,
                issues=[error_issue],
                check_results=self._create_error_check_results(),
                validated_at=start_time,
                rules_version=self.rules_version,
                validator_version="2.0.0-test",
                header_summary={},
                lines_summary={}
            )

    async def _execute_rule_category_test(
        self,
        category: str,
        rules: List,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]],
        confidence: Dict[str, Any],
        invoice_id: Optional[str],
        vendor_id: Optional[str]
    ) -> List[RuleExecutionResult]:
        """Execute rule category without database dependencies."""
        results = []

        for rule in rules:
            if not rule.enabled:
                continue

            try:
                start_time = datetime.utcnow()
                result = await self._execute_single_rule_test(
                    rule, header, lines, confidence, invoice_id, vendor_id
                )
                result.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                results.append(result)

            except Exception as e:
                logger.error(f"Rule {rule.name} execution failed: {e}")
                results.append(RuleExecutionResult(
                    rule_name=rule.name,
                    passed=False,
                    reason_taxonomy=ReasonTaxonomy.SYSTEM_ERROR,
                    message=f"Rule execution failed: {str(e)}",
                    details={"error_type": type(e).__name__}
                ))

        return results

    async def _execute_single_rule_test(
        self,
        rule,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]],
        confidence: Dict[str, Any],
        invoice_id: Optional[str],
        vendor_id: Optional[str]
    ) -> RuleExecutionResult:
        """Execute single rule without database dependencies."""
        if rule.name == "required_header_fields":
            return await self._validate_required_header_fields(rule, header)
        elif rule.name == "required_line_item_fields":
            return await self._validate_required_line_item_fields(rule, lines)
        elif rule.name == "field_format_validation":
            return await self._validate_field_formats(rule, header, lines)
        elif rule.name == "line_item_count_validation":
            return await self._validate_line_item_count(rule, lines)
        elif rule.name == "line_item_math_validation":
            return await self._validate_line_item_math(rule, lines)
        elif rule.name == "subtotal_validation":
            return await self._validate_subtotal(rule, header, lines)
        elif rule.name == "total_amount_validation":
            return await self._validate_total_amount(rule, header, lines)
        elif rule.name == "tax_calculation_validation":
            return await self._validate_tax_calculation(rule, header, lines)
        elif rule.name == "vendor_validation":
            return await self._validate_vendor_test(rule, header)
        elif rule.name == "currency_validation":
            return await self._validate_currency_test(rule, header)
        elif rule.name == "duplicate_detection":
            return await self._validate_duplicates_test(rule, header, invoice_id)
        elif rule.name == "po_matching_validation":
            return await self._validate_po_matching_test(rule, header)
        elif rule.name == "grn_matching_validation":
            return await self._validate_grn_matching_test(rule, header, lines)
        else:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=True,  # Default to pass for unimplemented rules
                message=f"Rule {rule.name} skipped in test mode"
            )

    async def _validate_vendor_test(self, rule, header: Dict[str, Any]) -> RuleExecutionResult:
        """Test vendor validation without database."""
        vendor_name = header.get("vendor_name")

        if not vendor_name:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=False,
                reason_taxonomy=ReasonTaxonomy.MISSING_REQUIRED_FIELDS,
                message="Vendor name not provided"
            )

        # Check against test vendor data
        vendor_found = False
        vendor_active = False

        for test_name, vendor_data in self.test_vendors.items():
            if test_name.lower() in vendor_name.lower() or vendor_name.lower() in test_name.lower():
                vendor_found = True
                vendor_active = vendor_data["active"]
                break

        if not vendor_found:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=False,
                reason_taxonomy=ReasonTaxonomy.VENDOR_NOT_FOUND,
                message=f"Vendor '{vendor_name}' not found in system",
                details={"vendor_name": vendor_name}
            )

        if not vendor_active:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=False,
                reason_taxonomy=ReasonTaxonomy.INACTIVE_VENDOR,
                message=f"Vendor '{vendor_name}' is inactive",
                details={"vendor_name": vendor_name}
            )

        return RuleExecutionResult(
            rule_name=rule.name,
            passed=True,
            message=f"Vendor validation passed: {vendor_name}",
            details={"vendor_name": vendor_name}
        )

    async def _validate_currency_test(self, rule, header: Dict[str, Any]) -> RuleExecutionResult:
        """Test currency validation without database."""
        invoice_currency = header.get("currency", "USD")
        vendor_name = header.get("vendor_name")

        if not vendor_name:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=True,
                message="Currency validation skipped (no vendor)"
            )

        # Find vendor in test data
        vendor_currency = None
        for test_name, vendor_data in self.test_vendors.items():
            if test_name.lower() in vendor_name.lower() or vendor_name.lower() in test_name.lower():
                vendor_currency = vendor_data.get("currency")
                break

        if vendor_currency and invoice_currency != vendor_currency:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=False,
                reason_taxonomy=ReasonTaxonomy.INVALID_CURRENCY,
                message=f"Currency mismatch: invoice {invoice_currency}, vendor {vendor_currency}",
                details={
                    "invoice_currency": invoice_currency,
                    "vendor_currency": vendor_currency
                }
            )

        return RuleExecutionResult(
            rule_name=rule.name,
            passed=True,
            message="Currency validation passed"
        )

    async def _validate_duplicates_test(self, rule, header: Dict[str, Any], invoice_id: Optional[str]) -> RuleExecutionResult:
        """Test duplicate validation without database."""
        invoice_number = header.get("invoice_number")
        vendor_name = header.get("vendor_name")
        total_amount = header.get("total_amount")

        if not invoice_number or not vendor_name:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=True,
                message="Duplicate check skipped (insufficient data)"
            )

        # Simple test logic - no duplicates found in test environment
        return RuleExecutionResult(
            rule_name=rule.name,
            passed=True,
            message="No duplicate invoices found",
            details={"invoice_number": invoice_number, "vendor_name": vendor_name}
        )

    async def _validate_po_matching_test(self, rule, header: Dict[str, Any]) -> RuleExecutionResult:
        """Test PO validation without database."""
        po_number = header.get("po_number")

        if not po_number:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=True,
                message="No PO number provided"
            )

        # Check against test PO data
        po_found = po_number in self.test_pos

        if po_found:
            po_data = self.test_pos[po_number]
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=True,
                message=f"PO validation passed: {po_number}",
                details={
                    "po_number": po_number,
                    "po_status": po_data["status"],
                    "po_amount": po_data["amount"]
                }
            )
        else:
            return RuleExecutionResult(
                rule_name=rule.name,
                passed=False,
                reason_taxonomy=ReasonTaxonomy.PO_NOT_FOUND,
                message=f"PO '{po_number}' not found in system",
                details={"po_number": po_number}
            )

    async def _validate_grn_matching_test(self, rule, header: Dict[str, Any], lines: List[Dict[str, Any]]) -> RuleExecutionResult:
        """Test GRN validation without database."""
        return RuleExecutionResult(
            rule_name=rule.name,
            passed=True,
            message="GRN validation passed (test mode)"
        )