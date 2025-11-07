"""
Enhanced validation service for invoice data validation and business rules.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.api.schemas.validation import (
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationResult,
    ValidationCheckResult,
    MathValidationResult,
    MatchingResult,
    VendorPolicyResult,
    DuplicateCheckResult,
    ValidationRulesConfig,
)
from app.api.schemas.exception import ExceptionResponse
from app.core.exceptions import ValidationException
from app.db.session import AsyncSessionLocal
from app.models.invoice import Invoice, InvoiceExtraction, Exception as ExceptionModel
from app.models.reference import Vendor, PurchaseOrder, GoodsReceiptNote

logger = logging.getLogger(__name__)


class ValidationService:
    """Enhanced service for validating invoice data against comprehensive business rules."""

    def __init__(self):
        """Initialize the enhanced validation service."""
        # Default validation rules configuration
        self.rules_config = self._get_default_rules_config()

        # Initialize validation components
        self.math_validator = MathValidator(self.rules_config)
        self.matching_validator = MatchingValidator(self.rules_config)
        self.vendor_policy_validator = VendorPolicyValidator(self.rules_config)
        self.duplicate_detector = DuplicateDetector(self.rules_config)

        # Import here to avoid circular imports
        from app.services.exception_service import ExceptionService
        self.exception_service = ExceptionService()

    def _get_default_rules_config(self) -> ValidationRulesConfig:
        """Get default validation rules configuration."""
        return ValidationRulesConfig(
            version="2.0.0",
            rules=[],  # No custom rules for now
            thresholds={
                "max_invoice_age_days": 365,
                "max_total_amount": 1000000,
                "min_line_amount": 0.01,
                "max_line_amount": 100000,
                "duplicate_confidence_threshold": 0.95,
                "po_amount_tolerance_percent": 5.0,
                "grn_quantity_tolerance_percent": 10.0,
                "math_tolerance_cents": 1,
            },
            required_fields={
                "header": ["vendor_name", "invoice_no", "invoice_date", "total"],
                "lines": ["description", "amount"],
            }
        )

    async def validate_invoice(
        self,
        extraction_result: Dict[str, Any],
        invoice_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        rules_config: Optional[ValidationRulesConfig] = None,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """Validate extracted invoice data with comprehensive business rules."""
        start_time = datetime.utcnow()
        logger.info(f"Enhanced validation starting for invoice {invoice_id}")

        # Use custom rules config if provided
        config = rules_config or self.rules_config

        # Initialize validation result
        issues: List[ValidationIssue] = []

        try:
            # Extract header and lines
            header = extraction_result.get("header", {})
            lines = extraction_result.get("lines", [])

            # Get database session for advanced validations
            async with AsyncSessionLocal() as session:
                # Run comprehensive validation checks
                structure_result = await self._validate_structure(header, lines, issues, config)
                header_result = await self._validate_header(header, issues, config)
                lines_result = await self._validate_lines(lines, issues, config)

                # Advanced validation modules
                math_result = await self.math_validator.validate(header, lines, issues)
                matching_result = await self.matching_validator.validate(header, lines, session, issues)
                vendor_policy_result = await self.vendor_policy_validator.validate(header, vendor_id, session, issues)
                duplicate_result = await self.duplicate_detector.check(header, invoice_id, session, issues)

            # Classify issues by severity
            error_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.ERROR)
            warning_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.WARNING)
            info_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.INFO)

            # Calculate overall validation result
            validation_passed = error_count == 0
            if strict_mode:
                validation_passed = validation_passed and warning_count == 0

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                structure_result, header_result, lines_result,
                math_result, matching_result, vendor_policy_result, duplicate_result
            )

            # Create comprehensive validation result
            result = ValidationResult(
                passed=validation_passed,
                confidence_score=confidence_score,
                total_issues=len(issues),
                error_count=error_count,
                warning_count=warning_count,
                info_count=info_count,
                issues=issues,
                math_validation=math_result,
                matching_result=matching_result,
                vendor_policy_result=vendor_policy_result,
                duplicate_check_result=duplicate_result,
                check_results=ValidationCheckResult(
                    structure_check=structure_result,
                    header_fields_check=header_result,
                    line_items_check=lines_result,
                    math_check=math_result is not None and math_result.subtotal_match and math_result.total_match,
                    business_rules_check=error_count == 0,
                    duplicate_check=duplicate_result is not None and not duplicate_result.is_duplicate,
                    vendor_policy_check=vendor_policy_result is not None and vendor_policy_result.vendor_active,
                    matching_check=matching_result is not None and (
                        matching_result.po_found or matching_result.matching_type == "none"
                    )
                ),
                validated_at=start_time,
                rules_version=config.version,
                validator_version="2.0.0",
                processing_time_ms=str(int((datetime.utcnow() - start_time).total_seconds() * 1000)),
                header_summary=self._create_header_summary(header),
                lines_summary=self._create_lines_summary(lines)
            )

            logger.info(
                f"Enhanced validation completed for invoice {invoice_id}: "
                f"{'PASSED' if result.passed else 'FAILED'} "
                f"(confidence: {confidence_score:.2f}, "
                f"errors: {error_count}, warnings: {warning_count})"
            )

            # Create exceptions for validation failures
            if not result.passed and invoice_id and error_count > 0:
                try:
                    # Create exception records asynchronously
                    await self._create_validation_exceptions(invoice_id, issues, session)
                except Exception as exc_error:
                    logger.error(f"Failed to create exceptions for invoice {invoice_id}: {exc_error}")
                    # Don't fail validation if exception creation fails

            return result.dict()

        except Exception as e:
            logger.error(f"Validation failed for invoice {invoice_id}: {e}")
            # Create error result
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
                check_results=ValidationCheckResult(
                    structure_check=False,
                    header_fields_check=False,
                    line_items_check=False,
                    math_check=False,
                    business_rules_check=False,
                    duplicate_check=False,
                    vendor_policy_check=False,
                    matching_check=False
                ),
                validated_at=start_time,
                rules_version=config.version,
                validator_version="2.0.0",
                header_summary={},
                lines_summary={}
            ).dict()

    async def _validate_structure(
        self, header: Dict[str, Any], lines: List[Dict[str, Any]],
        issues: List[ValidationIssue], config: ValidationRulesConfig
    ) -> bool:
        """Validate basic structure of extracted data."""
        logger.debug("Validating data structure")

        structure_valid = True

        # Check header structure
        if not isinstance(header, dict):
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_DATA_STRUCTURE,
                message="Header data is not a valid dictionary",
                severity=ValidationSeverity.ERROR,
                details={"expected_type": "dict", "actual_type": type(header).__name__}
            ))
            structure_valid = False

        # Check lines structure
        if not isinstance(lines, list):
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_DATA_STRUCTURE,
                message="Lines data is not a valid list",
                severity=ValidationSeverity.ERROR,
                details={"expected_type": "list", "actual_type": type(lines).__name__}
            ))
            structure_valid = False
        elif len(lines) == 0:
            issues.append(ValidationIssue(
                code=ValidationCode.NO_LINE_ITEMS,
                message="No line items found in invoice",
                severity=ValidationSeverity.ERROR
            ))
            structure_valid = False

        return structure_valid

    async def _validate_header(
        self, header: Dict[str, Any], issues: List[ValidationIssue], config: ValidationRulesConfig
    ) -> bool:
        """Validate header fields."""
        logger.debug("Validating header fields")

        header_valid = True
        required_fields = config.required_fields.get("header", [])

        for field in required_fields:
            value = header.get(field)
            if not value or (isinstance(value, str) and value.strip() == ""):
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message=f"Required header field '{field}' is missing or empty",
                    severity=ValidationSeverity.ERROR,
                    field=field
                ))
                header_valid = False

        # Validate specific field formats
        await self._validate_header_formats(header, issues, config)

        return header_valid

    async def _validate_header_formats(
        self, header: Dict[str, Any], issues: List[ValidationIssue], config: ValidationRulesConfig
    ) -> None:
        """Validate header field formats."""
        # Validate invoice number format
        invoice_no = header.get("invoice_no")
        if invoice_no and not str(invoice_no).strip():
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_FIELD_FORMAT,
                message="Invoice number cannot be empty",
                severity=ValidationSeverity.ERROR,
                field="invoice_no"
            ))

        # Validate date format
        invoice_date = header.get("invoice_date")
        if invoice_date:
            try:
                parsed_date = self._parse_date(invoice_date)
                if not parsed_date:
                    raise ValueError("Invalid date")
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_FIELD_FORMAT,
                    message=f"Invalid invoice date format: {invoice_date}",
                    severity=ValidationSeverity.ERROR,
                    field="invoice_date",
                    actual_value=str(invoice_date)
                ))

        # Validate currency
        currency = header.get("currency", "USD")
        if not (currency and len(str(currency)) == 3 and str(currency).isalpha()):
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_FIELD_FORMAT,
                message=f"Invalid currency format: {currency}",
                severity=ValidationSeverity.WARNING,
                field="currency",
                actual_value=str(currency)
            ))

    async def _validate_lines(
        self, lines: List[Dict[str, Any]], issues: List[ValidationIssue], config: ValidationRulesConfig
    ) -> bool:
        """Validate line items."""
        logger.debug("Validating line items")

        lines_valid = True
        required_fields = config.required_fields.get("lines", [])

        for i, line in enumerate(lines):
            line_valid = True

            # Check required fields
            for field in required_fields:
                value = line.get(field)
                if not value or (isinstance(value, str) and value.strip() == ""):
                    issues.append(ValidationIssue(
                        code=ValidationCode.MISSING_REQUIRED_FIELD,
                        message=f"Line {i+1}: Missing required field '{field}'",
                        severity=ValidationSeverity.ERROR,
                        field=field,
                        line_number=i+1
                    ))
                    line_valid = False

            # Validate amounts
            await self._validate_line_amounts(line, i, issues, config)

            if not line_valid:
                lines_valid = False

        return lines_valid

    async def _validate_line_amounts(
        self, line: Dict[str, Any], line_index: int, issues: List[ValidationIssue], config: ValidationRulesConfig
    ) -> None:
        """Validate line item amounts."""
        try:
            amount = float(line.get("amount", 0))
            quantity = float(line.get("quantity", 1))
            unit_price = float(line.get("unit_price", amount))

            # Check amount ranges
            min_amount = config.thresholds.get("min_line_amount", 0.01)
            max_amount = config.thresholds.get("max_line_amount", 100000)

            if amount < min_amount:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_AMOUNT,
                    message=f"Line {line_index+1}: Amount {amount} is below minimum {min_amount}",
                    severity=ValidationSeverity.ERROR,
                    field="amount",
                    line_number=line_index+1,
                    actual_value=str(amount),
                    expected_value=f">= {min_amount}"
                ))

            if amount > max_amount:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_AMOUNT,
                    message=f"Line {line_index+1}: Amount {amount} is unusually high",
                    severity=ValidationSeverity.WARNING,
                    field="amount",
                    line_number=line_index+1,
                    actual_value=str(amount)
                ))

            # Check quantity and unit price consistency
            expected_amount = quantity * unit_price
            tolerance = config.thresholds.get("math_tolerance_cents", 1) / 100
            if abs(amount - expected_amount) > tolerance:
                issues.append(ValidationIssue(
                    code=ValidationCode.LINE_MATH_MISMATCH,
                    message=f"Line {line_index+1}: Amount {amount} doesn't match quantity {quantity} × unit price {unit_price} = {expected_amount}",
                    severity=ValidationSeverity.WARNING,
                    field="amount",
                    line_number=line_index+1,
                    actual_value=str(amount),
                    expected_value=str(expected_amount),
                    details={"quantity": quantity, "unit_price": unit_price}
                ))

        except (ValueError, TypeError) as e:
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_AMOUNT,
                message=f"Line {line_index+1}: Invalid amount format - {str(e)}",
                severity=ValidationSeverity.ERROR,
                field="amount",
                line_number=line_index+1,
                actual_value=str(line.get("amount", "undefined"))
            ))

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None

        date_formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue

        return None

    def _is_valid_amount(self, amount: Any) -> bool:
        """Check if amount is a valid numeric value."""
        try:
            if amount is None:
                return False
            float(amount)
            return True
        except (ValueError, TypeError):
            return False

    def _calculate_confidence_score(
        self,
        structure_result: bool,
        header_result: bool,
        lines_result: bool,
        math_result: Optional[MathValidationResult],
        matching_result: Optional[MatchingResult],
        vendor_policy_result: Optional[VendorPolicyResult],
        duplicate_result: Optional[DuplicateCheckResult]
    ) -> float:
        """Calculate overall validation confidence score."""
        score = 0.0
        max_score = 100.0

        # Basic structure and field validation (40 points)
        if structure_result:
            score += 15.0
        if header_result:
            score += 15.0
        if lines_result:
            score += 10.0

        # Math validation (25 points)
        if math_result:
            if math_result.subtotal_match:
                score += 12.5
            if math_result.total_match:
                score += 12.5

        # Matching validation (20 points)
        if matching_result:
            if matching_result.po_found:
                score += 10.0
                if matching_result.po_amount_match:
                    score += 5.0
            if matching_result.grn_found and matching_result.quantity_match:
                score += 5.0

        # Vendor policy validation (10 points)
        if vendor_policy_result and vendor_policy_result.vendor_active:
            score += 5.0
            if vendor_policy_result.currency_valid:
                score += 2.5
            if vendor_policy_result.spend_limit_ok:
                score += 2.5

        # Duplicate check (5 points)
        if duplicate_result and not duplicate_result.is_duplicate:
            score += 5.0

        return round(score, 2)

    def _create_header_summary(self, header: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of header data for reporting."""
        return {
            "vendor_name": header.get("vendor_name"),
            "invoice_no": header.get("invoice_no"),
            "invoice_date": header.get("invoice_date"),
            "total": header.get("total"),
            "currency": header.get("currency"),
            "po_number": header.get("po_number"),
            "tax_amount": header.get("tax", 0)
        }

    def _create_lines_summary(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a summary of line items for reporting."""
        if not lines:
            return {"count": 0, "total": 0.0}

        total_amount = sum(
            float(line.get("amount", 0))
            for line in lines
            if self._is_valid_amount(line.get("amount"))
        )

        return {
            "count": len(lines),
            "total": total_amount,
            "descriptions": [line.get("description", "")[:50] + "..."
                           if len(line.get("description", "")) > 50
                           else line.get("description", "")
                           for line in lines[:5]]
        }


class MathValidator:
    """Specialized validator for mathematical relationships in invoices."""

    def __init__(self, config: ValidationRulesConfig):
        self.config = config

    async def validate(
        self, header: Dict[str, Any], lines: List[Dict[str, Any]], issues: List[ValidationIssue]
    ) -> Optional[MathValidationResult]:
        """Validate mathematical relationships in invoice."""
        logger.debug("Validating mathematical relationships")

        try:
            # Calculate line total
            lines_total = sum(
                float(line.get("amount", 0))
                for line in lines
                if self._is_valid_amount(line.get("amount"))
            )

            # Validate subtotal
            subtotal = float(header.get("subtotal", 0)) if self._is_valid_amount(header.get("subtotal")) else None
            subtotal_match = None
            subtotal_difference = None

            if subtotal is not None:
                tolerance = self.config.thresholds.get("math_tolerance_cents", 1) / 100
                subtotal_difference = abs(lines_total - subtotal)
                if subtotal_difference > tolerance:
                    issues.append(ValidationIssue(
                        code=ValidationCode.SUBTOTAL_MISMATCH,
                        message=f"Line items total {lines_total} doesn't match subtotal {subtotal}",
                        severity=ValidationSeverity.ERROR,
                        actual_value=str(lines_total),
                        expected_value=str(subtotal),
                        details={"difference": subtotal_difference}
                    ))
                    subtotal_match = False
                else:
                    subtotal_match = True
            else:
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message="Subtotal not found for validation",
                    severity=ValidationSeverity.WARNING,
                    field="subtotal"
                ))

            # Validate total
            total = float(header.get("total", 0)) if self._is_valid_amount(header.get("total")) else None
            total_match = None
            total_difference = None
            tax_amount = float(header.get("tax", 0)) if self._is_valid_amount(header.get("tax")) else 0

            if total is not None:
                expected_total = (subtotal or lines_total) + tax_amount
                tolerance = self.config.thresholds.get("math_tolerance_cents", 1) / 100
                total_difference = abs(total - expected_total)

                if total_difference > tolerance:
                    issues.append(ValidationIssue(
                        code=ValidationCode.TOTAL_MISMATCH,
                        message=f"Total {total} doesn't match expected {expected_total}",
                        severity=ValidationSeverity.ERROR,
                        actual_value=str(total),
                        expected_value=str(expected_total),
                        details={
                            "subtotal": subtotal or lines_total,
                            "tax": tax_amount,
                            "difference": total_difference
                        }
                    ))
                    total_match = False
                else:
                    total_match = True
            else:
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message="Total amount is missing",
                    severity=ValidationSeverity.ERROR,
                    field="total"
                ))

            # Validate individual line items
            line_item_validation = []
            for i, line in enumerate(lines):
                line_validation = {"line_index": i, "valid": True}
                await self._validate_line_math(line, i, issues, line_validation)
                line_item_validation.append(line_validation)

            return MathValidationResult(
                lines_total=lines_total,
                subtotal_match=subtotal_match,
                subtotal_difference=subtotal_difference,
                total_match=total_match,
                total_difference=total_difference,
                tax_amount=tax_amount,
                line_item_validation=line_item_validation
            )

        except Exception as e:
            issues.append(ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=f"Math validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error_type": type(e).__name__}
            ))
            return None

    async def _validate_line_math(
        self, line: Dict[str, Any], line_index: int, issues: List[ValidationIssue], line_validation: Dict[str, Any]
    ) -> None:
        """Validate math for individual line item."""
        try:
            amount = float(line.get("amount", 0))
            quantity = float(line.get("quantity", 1))
            unit_price = float(line.get("unit_price", amount))

            expected_amount = quantity * unit_price
            tolerance = self.config.thresholds.get("math_tolerance_cents", 1) / 100

            if abs(amount - expected_amount) > tolerance:
                issues.append(ValidationIssue(
                    code=ValidationCode.LINE_MATH_MISMATCH,
                    message=f"Line {line_index+1}: Amount {amount} doesn't match quantity {quantity} × unit price {unit_price} = {expected_amount}",
                    severity=ValidationSeverity.WARNING,
                    field="amount",
                    line_number=line_index+1,
                    actual_value=str(amount),
                    expected_value=str(expected_amount)
                ))
                line_validation["valid"] = False

        except (ValueError, TypeError) as e:
            issues.append(ValidationIssue(
                code=ValidationCode.INVALID_AMOUNT,
                message=f"Line {line_index+1}: Invalid amount format - {str(e)}",
                severity=ValidationSeverity.ERROR,
                field="amount",
                line_number=line_index+1
            ))
            line_validation["valid"] = False

    def _is_valid_amount(self, amount: Any) -> bool:
        """Check if amount is a valid numeric value."""
        try:
            if amount is None:
                return False
            float(amount)
            return True
        except (ValueError, TypeError):
            return False


class MatchingValidator:
    """Specialized validator for PO and GRN matching."""

    def __init__(self, config: ValidationRulesConfig):
        self.config = config

    async def validate(
        self,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]],
        session: AsyncSession,
        issues: List[ValidationIssue]
    ) -> Optional[MatchingResult]:
        """Validate invoice against POs and GRNs (2-way and 3-way matching)."""
        logger.debug("Performing PO and GRN matching")

        try:
            po_number = header.get("po_number")
            vendor_name = header.get("vendor_name")
            invoice_total = float(header.get("total", 0)) if self._is_valid_amount(header.get("total")) else 0

            if not po_number:
                logger.info("No PO number found, skipping matching validation")
                return MatchingResult(
                    po_found=False,
                    matching_type="none"
                )

            # Find PO by number and vendor
            po_query = select(PurchaseOrder).join(Vendor).where(
                PurchaseOrder.po_no == po_number,
                Vendor.name.ilike(f"%{vendor_name}%") if vendor_name else True
            )
            po_result = await session.execute(po_query)
            po = po_result.scalar_one_or_none()

            if not po:
                issues.append(ValidationIssue(
                    code=ValidationCode.PO_NOT_FOUND,
                    message=f"Purchase Order {po_number} not found for vendor {vendor_name}",
                    severity=ValidationSeverity.WARNING,
                    field="po_number",
                    actual_value=po_number
                ))
                return MatchingResult(
                    po_found=False,
                    po_number=po_number,
                    matching_type="2_way"
                )

            # Validate PO amount against invoice total
            po_amount = float(po.total_amount)
            tolerance_percent = self.config.thresholds.get("po_amount_tolerance_percent", 5.0)
            tolerance_amount = po_amount * (tolerance_percent / 100)
            amount_difference = abs(invoice_total - po_amount)
            amount_match = amount_difference <= tolerance_amount

            if not amount_match:
                issues.append(ValidationIssue(
                    code=ValidationCode.PO_AMOUNT_MISMATCH,
                    message=f"Invoice total {invoice_total} doesn't match PO total {po_amount}",
                    severity=ValidationSeverity.WARNING,
                    field="total",
                    actual_value=str(invoice_total),
                    expected_value=str(po_amount),
                    details={
                        "po_number": po_number,
                        "difference": amount_difference,
                        "tolerance_percent": tolerance_percent
                    }
                ))

            # Check for GRNs (3-way matching)
            grn_query = select(GoodsReceiptNote).where(
                GoodsReceiptNote.po_id == po.id
            )
            grn_result = await session.execute(grn_query)
            grns = grn_result.scalars().all()

            grn_found = len(grns) > 0
            grn_number = grns[0].grn_no if grns else None
            grn_status = grns[0].received_at.isoformat() if grns else None

            # If GRNs exist, validate quantities
            quantity_match = None
            quantity_difference = None

            if grns:
                # Calculate total received quantities from all GRNs
                total_received = {}
                for grn in grns:
                    grn_lines = grn.lines_json if isinstance(grn.lines_json, list) else []
                    for line in grn_lines:
                        item_code = line.get("item_code") or line.get("description")
                        if item_code:
                            total_received[item_code] = total_received.get(item_code, 0) + float(line.get("quantity", 0))

                # Compare with invoice line quantities
                tolerance_percent = self.config.thresholds.get("grn_quantity_tolerance_percent", 10.0)
                quantity_issues = []

                for line in lines:
                    item_desc = line.get("description", "")
                    invoice_qty = float(line.get("quantity", 0))
                    received_qty = total_received.get(item_desc, 0)

                    if received_qty > 0:
                        tolerance_qty = received_qty * (tolerance_percent / 100)
                        qty_difference = abs(invoice_qty - received_qty)

                        if qty_difference > tolerance_qty:
                            quantity_issues.append({
                                "item": item_desc,
                                "invoice_qty": invoice_qty,
                                "received_qty": received_qty,
                                "difference": qty_difference
                            })

                if quantity_issues:
                    quantity_match = False
                    quantity_difference = max(issue["difference"] for issue in quantity_issues)
                    issues.append(ValidationIssue(
                        code=ValidationCode.GRN_QUANTITY_MISMATCH,
                        message=f"Quantity mismatches found between invoice and GRNs",
                        severity=ValidationSeverity.WARNING,
                        details={"quantity_issues": quantity_issues}
                    ))
                else:
                    quantity_match = True

            matching_type = "3_way" if grn_found else "2_way"

            return MatchingResult(
                po_found=True,
                po_number=po_number,
                po_status=po.status.value,
                po_amount_match=amount_match,
                po_amount_difference=amount_difference if not amount_match else None,
                grn_found=grn_found,
                grn_number=grn_number,
                grn_status=grn_status,
                quantity_match=quantity_match,
                quantity_difference=quantity_difference,
                matching_type=matching_type
            )

        except Exception as e:
            issues.append(ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=f"PO/GRN matching validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error_type": type(e).__name__}
            ))
            return None

    def _is_valid_amount(self, amount: Any) -> bool:
        """Check if amount is a valid numeric value."""
        try:
            if amount is None:
                return False
            float(amount)
            return True
        except (ValueError, TypeError):
            return False


class VendorPolicyValidator:
    """Specialized validator for vendor-specific policies."""

    def __init__(self, config: ValidationRulesConfig):
        self.config = config

    async def validate(
        self,
        header: Dict[str, Any],
        vendor_id: Optional[str],
        session: AsyncSession,
        issues: List[ValidationIssue]
    ) -> Optional[VendorPolicyResult]:
        """Validate invoice against vendor policies."""
        logger.debug("Validating vendor policies")

        try:
            vendor_name = header.get("vendor_name")
            invoice_currency = header.get("currency", "USD")
            invoice_total = float(header.get("total", 0)) if self._is_valid_amount(header.get("total")) else 0
            tax_id = header.get("tax_id")

            # Find vendor by name or ID
            vendor = None
            if vendor_id:
                vendor_query = select(Vendor).where(Vendor.id == vendor_id)
                result = await session.execute(vendor_query)
                vendor = result.scalar_one_or_none()

            if not vendor and vendor_name:
                vendor_query = select(Vendor).where(Vendor.name.ilike(f"%{vendor_name}%"))
                result = await session.execute(vendor_query)
                vendor = result.scalar_one_or_none()

            if not vendor:
                issues.append(ValidationIssue(
                    code=ValidationCode.INACTIVE_VENDOR,
                    message=f"Vendor '{vendor_name}' not found in system",
                    severity=ValidationSeverity.WARNING,
                    field="vendor_name"
                ))
                return VendorPolicyResult(
                    vendor_active=False,
                    currency_valid=False,
                    tax_id_valid=None,
                    spend_limit_ok=None,
                    payment_terms_ok=True,
                    vendor_policy_issues=[]
                )

            policy_issues = []

            # Check vendor status
            vendor_active = vendor.active and vendor.status.value == "active"
            if not vendor_active:
                policy_issues.append(ValidationIssue(
                    code=ValidationCode.INACTIVE_VENDOR,
                    message=f"Vendor '{vendor.name}' is not active (status: {vendor.status.value})",
                    severity=ValidationSeverity.ERROR,
                    field="vendor_name"
                ))

            # Validate currency
            currency_valid = invoice_currency == vendor.currency
            if not currency_valid:
                policy_issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_CURRENCY,
                    message=f"Invoice currency {invoice_currency} doesn't match vendor currency {vendor.currency}",
                    severity=ValidationSeverity.ERROR,
                    field="currency",
                    actual_value=invoice_currency,
                    expected_value=vendor.currency
                ))

            # Validate tax ID
            tax_id_valid = None
            if vendor.tax_id and tax_id:
                tax_id_valid = str(tax_id).replace(" ", "").replace("-", "").upper() == \
                             str(vendor.tax_id).replace(" ", "").replace("-", "").upper()
                if not tax_id_valid:
                    policy_issues.append(ValidationIssue(
                        code=ValidationCode.INVALID_TAX_ID,
                        message=f"Invoice tax ID {tax_id} doesn't match vendor tax ID",
                        severity=ValidationSeverity.WARNING,
                        field="tax_id",
                        actual_value=str(tax_id),
                        expected_value=str(vendor.tax_id)
                    ))

            # Check spend limits
            spend_limit_ok = None
            current_spend = None
            spend_limit = None

            if vendor.credit_limit:
                spend_limit = float(vendor.credit_limit)
                # Calculate current spend for this vendor
                spend_query = select(func.sum(InvoiceExtraction.header_json['total'].cast(float)))\
                    .join(Invoice)\
                    .join(Vendor)\
                    .where(Vendor.id == vendor.id)
                spend_result = await session.execute(spend_query)
                current_spend = spend_result.scalar() or 0.0

                projected_spend = current_spend + invoice_total
                spend_limit_ok = projected_spend <= spend_limit

                if not spend_limit_ok:
                    policy_issues.append(ValidationIssue(
                        code=ValidationCode.SPEND_LIMIT_EXCEEDED,
                        message=f"Invoice would exceed vendor credit limit",
                        severity=ValidationSeverity.ERROR,
                        field="total",
                        actual_value=str(projected_spend),
                        expected_value=f"<= {spend_limit}",
                        details={
                            "current_spend": current_spend,
                            "invoice_amount": invoice_total,
                            "credit_limit": spend_limit
                        }
                    ))

            # Validate payment terms (basic check)
            payment_terms_ok = True
            # This could be enhanced to check against specific payment term policies

            return VendorPolicyResult(
                vendor_active=vendor_active,
                currency_valid=currency_valid,
                tax_id_valid=tax_id_valid,
                spend_limit_ok=spend_limit_ok,
                current_spend=current_spend,
                spend_limit=spend_limit,
                payment_terms_ok=payment_terms_ok,
                vendor_policy_issues=policy_issues
            )

        except Exception as e:
            issues.append(ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=f"Vendor policy validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error_type": type(e).__name__}
            ))
            return None

    def _is_valid_amount(self, amount: Any) -> bool:
        """Check if amount is a valid numeric value."""
        try:
            if amount is None:
                return False
            float(amount)
            return True
        except (ValueError, TypeError):
            return False


class DuplicateDetector:
    """Specialized service for detecting duplicate invoices."""

    def __init__(self, config: ValidationRulesConfig):
        self.config = config

    async def check(
        self,
        header: Dict[str, Any],
        invoice_id: Optional[str],
        session: AsyncSession,
        issues: List[ValidationIssue]
    ) -> Optional[DuplicateCheckResult]:
        """Check for duplicate invoices."""
        logger.debug("Checking for duplicate invoices")

        try:
            invoice_no = header.get("invoice_no")
            vendor_name = header.get("vendor_name")
            invoice_total = str(header.get("total", ""))
            invoice_date = header.get("invoice_date")

            if not invoice_no or not vendor_name:
                logger.info("Missing invoice number or vendor name, skipping duplicate check")
                return DuplicateCheckResult(
                    is_duplicate=False,
                    match_criteria={"reason": "insufficient_data"}
                )

            # Build similarity search criteria
            search_conditions = []

            # Exact invoice number + vendor match
            vendor_query = select(Vendor).where(Vendor.name.ilike(f"%{vendor_name}%"))
            vendor_result = await session.execute(vendor_query)
            vendor = vendor_result.scalar_one_or_none()

            if vendor:
                search_conditions.append(
                    and_(
                        Invoice.vendor_id == vendor.id,
                        InvoiceExtraction.header_json['invoice_no'].astext == invoice_no
                    )
                )

            # Execute duplicate search
            duplicate_invoices = []
            confidence = 0.0

            if search_conditions:
                duplicate_query = select(Invoice, InvoiceExtraction)\
                    .join(InvoiceExtraction)\
                    .where(or_(*search_conditions))

                if invoice_id:
                    duplicate_query = duplicate_query.where(Invoice.id != invoice_id)

                duplicate_result = await session.execute(duplicate_query)
                duplicates = duplicate_result.all()

                for duplicate_invoice, duplicate_extraction in duplicates:
                    duplicate_data = {
                        "invoice_id": str(duplicate_invoice.id),
                        "invoice_no": self._extract_header_value(duplicate_extraction.header_json, "invoice_no"),
                        "vendor_name": vendor_name,
                        "total": self._extract_header_value(duplicate_extraction.header_json, "total"),
                        "invoice_date": self._extract_header_value(duplicate_extraction.header_json, "invoice_date"),
                        "status": duplicate_invoice.status.value,
                        "created_at": duplicate_invoice.created_at.isoformat()
                    }
                    duplicate_invoices.append(duplicate_data)

            # Calculate duplicate confidence
            if duplicate_invoices:
                # High confidence if exact match on invoice number + vendor + total
                exact_matches = [
                    dup for dup in duplicate_invoices
                    if dup["total"] == invoice_total and dup["invoice_date"] == invoice_date
                ]
                if exact_matches:
                    confidence = 1.0
                else:
                    # Partial confidence based on matching fields
                    confidence = 0.8 if len(duplicate_invoices) > 0 else 0.0

            # Determine if duplicate based on confidence threshold
            confidence_threshold = self.config.thresholds.get("duplicate_confidence_threshold", 0.95)
            is_duplicate = confidence >= confidence_threshold

            if is_duplicate and duplicate_invoices:
                issues.append(ValidationIssue(
                    code=ValidationCode.DUPLICATE_INVOICE,
                    message=f"Potential duplicate invoice found",
                    severity=ValidationSeverity.ERROR,
                    details={
                        "duplicate_count": len(duplicate_invoices),
                        "duplicates": duplicate_invoices[:3]  # Limit to top 3
                    }
                ))

            return DuplicateCheckResult(
                is_duplicate=is_duplicate,
                duplicate_invoices=duplicate_invoices,
                match_criteria={
                    "invoice_no": invoice_no,
                    "vendor_name": vendor_name,
                    "total": invoice_total,
                    "invoice_date": invoice_date
                },
                confidence=confidence
            )

        except Exception as e:
            issues.append(ValidationIssue(
                code=ValidationCode.VALIDATION_ERROR,
                message=f"Duplicate check failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                details={"error_type": type(e).__name__}
            ))
            return None

    def _extract_header_value(self, header_json: Dict[str, Any], key: str) -> str:
        """Extract value from header JSON safely."""
        if isinstance(header_json, dict):
            return str(header_json.get(key, ""))
        return ""

    async def _create_validation_exceptions(
        self,
        invoice_id: str,
        issues: List[ValidationIssue],
        session: AsyncSession
    ) -> List[ExceptionResponse]:
        """Create exception records from validation issues."""
        try:
            exceptions = await self.exception_service.create_exception_from_validation(
                invoice_id=invoice_id,
                validation_issues=issues,
                session=session
            )
            logger.info(f"Created {len(exceptions)} exceptions for invoice {invoice_id}")
            return exceptions
        except Exception as e:
            logger.error(f"Failed to create exceptions for invoice {invoice_id}: {e}")
            raise