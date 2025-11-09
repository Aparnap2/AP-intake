"""
AR-specific validation service extending the base validation service.

This service provides validation rules specific to AR invoices and customers,
integrating with the existing validation framework.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.ar_invoice import Customer, ARInvoice, PaymentStatus
from app.models.invoice import Invoice
from app.services.validation_service import ValidationService, ValidationCode, ValidationIssue, ValidationSeverity


class ARValidationService(ValidationService):
    """Extended validation service for AR-specific rules."""

    async def validate_ar_invoice(
        self,
        db: AsyncSession,
        ar_invoice_data: Dict,
        customer_id: Optional[str] = None
    ) -> Dict:
        """Validate AR invoice with AR-specific business rules."""
        issues = []

        # Get customer for validation
        customer = None
        if customer_id:
            result = await db.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            customer = result.scalar_one_or_none()

        # AR-specific validations
        await self._validate_ar_invoice_business_rules(db, ar_invoice_data, customer, issues)
        await self._validate_ar_invoice_amounts(ar_invoice_data, issues)
        await self._validate_ar_invoice_dates(ar_invoice_data, issues)
        await self._validate_customer_credit_limit(db, ar_invoice_data, customer, issues)

        # Run base validation on extracted data structure
        structure_result = await self._validate_ar_invoice_structure(ar_invoice_data, issues)

        # Calculate confidence score
        confidence_score = self._calculate_ar_confidence_score(
            structure_result,
            len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            len([i for i in issues if i.severity == ValidationSeverity.WARNING])
        )

        return {
            "passed": len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0,
            "issues": issues,
            "error_count": len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            "warning_count": len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            "confidence_score": confidence_score,
            "validations": {
                "structure": structure_result,
                "business_rules": len([i for i in issues if i.code in self._get_business_rule_codes()]) == 0,
                "credit_limit": not any(i.code == ValidationCode.CREDIT_LIMIT_EXCEEDED for i in issues)
            }
        }

    async def validate_customer(
        self,
        db: AsyncSession,
        customer_data: Dict
    ) -> Dict:
        """Validate customer data with business rules."""
        issues = []

        # Customer-specific validations
        await self._validate_customer_business_rules(db, customer_data, issues)
        await self._validate_customer_financial_data(customer_data, issues)
        await self._validate_customer_contact_data(customer_data, issues)

        # Check for duplicates
        await self._validate_customer_uniqueness(db, customer_data, issues)

        return {
            "passed": len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0,
            "issues": issues,
            "error_count": len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            "warning_count": len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
        }

    async def _validate_ar_invoice_business_rules(
        self,
        db: AsyncSession,
        ar_invoice_data: Dict,
        customer: Optional[Customer],
        issues: List[ValidationIssue]
    ):
        """Validate AR invoice business rules."""
        invoice_number = ar_invoice_data.get("invoice_number")

        # Check for duplicate invoice numbers
        if invoice_number:
            result = await db.execute(
                select(ARInvoice).where(ARInvoice.invoice_number == invoice_number)
            )
            duplicate = result.scalar_one_or_none()

            if duplicate:
                issues.append(ValidationIssue(
                    code=ValidationCode.DUPLICATE_INVOICE,
                    message=f"Invoice number {invoice_number} already exists",
                    severity=ValidationSeverity.ERROR,
                    field="invoice_number"
                ))

        # Validate currency matches customer
        if customer and "currency" in ar_invoice_data:
            if ar_invoice_data["currency"] != customer.currency:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_CURRENCY,
                    message=f"Invoice currency {ar_invoice_data['currency']} doesn't match customer currency {customer.currency}",
                    severity=ValidationSeverity.ERROR,
                    field="currency"
                ))

        # Validate payment terms alignment
        if customer and "due_date" in ar_invoice_data and "invoice_date" in ar_invoice_data:
            expected_due_date = customer.calculate_due_date(ar_invoice_data["invoice_date"].date())
            actual_due_date = ar_invoice_data["due_date"].date()

            if abs((expected_due_date - actual_due_date).days) > 5:  # Allow 5 days variance
                issues.append(ValidationIssue(
                    code=ValidationCode.PAYMENT_TERMS_MISMATCH,
                    message=f"Due date doesn't match customer payment terms of {customer.payment_terms_days} days",
                    severity=ValidationSeverity.WARNING,
                    field="due_date"
                ))

    async def _validate_ar_invoice_amounts(self, ar_invoice_data: Dict, issues: List[ValidationIssue]):
        """Validate AR invoice amounts."""
        required_amount_fields = ["subtotal", "tax_amount", "total_amount"]
        for field in required_amount_fields:
            if field not in ar_invoice_data:
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message=f"Missing required amount field: {field}",
                    severity=ValidationSeverity.ERROR,
                    field=field
                ))

        # Validate amount calculations
        if all(field in ar_invoice_data for field in required_amount_fields):
            expected_total = ar_invoice_data["subtotal"] + ar_invoice_data["tax_amount"]
            actual_total = ar_invoice_data["total_amount"]

            tolerance = Decimal("0.01")  # 1 cent tolerance
            if abs(expected_total - actual_total) > tolerance:
                issues.append(ValidationIssue(
                    code=ValidationCode.TOTAL_MISMATCH,
                    message=f"Total amount mismatch: expected {expected_total}, got {actual_total}",
                    severity=ValidationSeverity.ERROR,
                    field="total_amount"
                ))

        # Validate negative amounts
        for field in required_amount_fields:
            if field in ar_invoice_data and ar_invoice_data[field] < 0:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_AMOUNT,
                    message=f"Amount cannot be negative: {field}",
                    severity=ValidationSeverity.ERROR,
                    field=field
                ))

    async def _validate_ar_invoice_dates(self, ar_invoice_data: Dict, issues: List[ValidationIssue]):
        """Validate AR invoice dates."""
        # Check required date fields
        required_date_fields = ["invoice_date", "due_date"]
        for field in required_date_fields:
            if field not in ar_invoice_data:
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message=f"Missing required date field: {field}",
                    severity=ValidationSeverity.ERROR,
                    field=field
                ))

        # Validate date relationship
        if all(field in ar_invoice_data for field in required_date_fields):
            if ar_invoice_data["due_date"] <= ar_invoice_data["invoice_date"]:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_DATE_RANGE,
                    message="Due date must be after invoice date",
                    severity=ValidationSeverity.ERROR,
                    field="due_date"
                ))

        # Validate early payment discount dates
        if ("early_payment_discount_days" in ar_invoice_data and
            "invoice_date" in ar_invoice_data and
            ar_invoice_data["early_payment_discount_days"]):

            try:
                discount_days = int(ar_invoice_data["early_payment_discount_days"])
                discount_deadline = ar_invoice_data["invoice_date"] + timedelta(days=discount_days)

                if discount_deadline > ar_invoice_data["due_date"]:
                    issues.append(ValidationIssue(
                        code=ValidationCode.DISCOUNT_PERIOD_INVALID,
                        message="Early payment discount deadline is after due date",
                        severity=ValidationSeverity.WARNING,
                        field="early_payment_discount_days"
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_FIELD_FORMAT,
                    message="Early payment discount days must be a valid number",
                    severity=ValidationSeverity.ERROR,
                    field="early_payment_discount_days"
                ))

    async def _validate_customer_credit_limit(
        self,
        db: AsyncSession,
        ar_invoice_data: Dict,
        customer: Optional[Customer],
        issues: List[ValidationIssue]
    ):
        """Validate invoice against customer credit limit."""
        if not customer or "total_amount" not in ar_invoice_data:
            return

        # Get current outstanding balance
        result = await db.execute(
            select(func.coalesce(func.sum(ARInvoice.outstanding_amount), 0))
            .where(
                ARInvoice.customer_id == customer.id,
                ARInvoice.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID, PaymentStatus.OVERDUE])
            )
        )
        current_outstanding = result.scalar() or Decimal("0.00")

        # Calculate new total after this invoice
        new_total = current_outstanding + ar_invoice_data["total_amount"]
        credit_limit = customer.credit_limit or Decimal("0.00")

        if credit_limit > 0 and new_total > credit_limit:
            issues.append(ValidationIssue(
                code=ValidationCode.CREDIT_LIMIT_EXCEEDED,
                message=f"Invoice would exceed credit limit: {new_total} > {credit_limit}",
                severity=ValidationSeverity.WARNING,
                field="total_amount"
            ))

        # Check if approaching credit limit (within 80%)
        if credit_limit > 0 and new_total > (credit_limit * Decimal("0.8")):
            issues.append(ValidationIssue(
                code=ValidationCode.CREDIT_LIMIT_WARNING,
                message=f"Invoice approaches credit limit: {new_total} of {credit_limit}",
                severity=ValidationSeverity.INFO,
                field="total_amount"
            ))

    async def _validate_customer_business_rules(
        self,
        db: AsyncSession,
        customer_data: Dict,
        issues: List[ValidationIssue]
    ):
        """Validate customer business rules."""
        # Check for existing customers with same tax_id or email
        if "tax_id" in customer_data and customer_data["tax_id"]:
            result = await db.execute(
                select(Customer).where(Customer.tax_id == customer_data["tax_id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                issues.append(ValidationIssue(
                    code=ValidationCode.DUPLICATE_CUSTOMER,
                    message=f"Customer with tax ID {customer_data['tax_id']} already exists",
                    severity=ValidationSeverity.ERROR,
                    field="tax_id"
                ))

        if "email" in customer_data and customer_data["email"]:
            result = await db.execute(
                select(Customer).where(Customer.email == customer_data["email"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                issues.append(ValidationIssue(
                    code=ValidationCode.DUPLICATE_CUSTOMER,
                    message=f"Customer with email {customer_data['email']} already exists",
                    severity=ValidationSeverity.ERROR,
                    field="email"
                ))

    async def _validate_customer_financial_data(self, customer_data: Dict, issues: List[ValidationIssue]):
        """Validate customer financial data."""
        # Validate credit limit
        if "credit_limit" in customer_data:
            credit_limit = customer_data["credit_limit"]
            if credit_limit < 0:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_AMOUNT,
                    message="Credit limit cannot be negative",
                    severity=ValidationSeverity.ERROR,
                    field="credit_limit"
                ))
            elif credit_limit > Decimal("1000000"):  # $1M limit warning
                issues.append(ValidationIssue(
                    code=ValidationCode.HIGH_CREDIT_LIMIT,
                    message="Credit limit is unusually high",
                    severity=ValidationSeverity.WARNING,
                    field="credit_limit"
                ))

        # Validate payment terms
        if "payment_terms_days" in customer_data:
            try:
                terms = int(customer_data["payment_terms_days"])
                if terms < 0:
                    issues.append(ValidationIssue(
                        code=ValidationCode.INVALID_FIELD_FORMAT,
                        message="Payment terms cannot be negative",
                        severity=ValidationSeverity.ERROR,
                        field="payment_terms_days"
                    ))
                elif terms > 120:
                    issues.append(ValidationIssue(
                        code=ValidationCode.LONG_PAYMENT_TERMS,
                        message="Payment terms are unusually long",
                        severity=ValidationSeverity.WARNING,
                        field="payment_terms_days"
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_FIELD_FORMAT,
                    message="Payment terms must be a valid number",
                    severity=ValidationSeverity.ERROR,
                    field="payment_terms_days"
                ))

    async def _validate_customer_contact_data(self, customer_data: Dict, issues: List[ValidationIssue]):
        """Validate customer contact information."""
        # Validate email format
        if "email" in customer_data and customer_data["email"]:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, customer_data["email"]):
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_EMAIL_FORMAT,
                    message="Invalid email format",
                    severity=ValidationSeverity.ERROR,
                    field="email"
                ))

        # Validate phone format (basic validation)
        if "phone" in customer_data and customer_data["phone"]:
            phone = customer_data["phone"].replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            if not phone.isdigit() or len(phone) < 10:
                issues.append(ValidationIssue(
                    code=ValidationCode.INVALID_PHONE_FORMAT,
                    message="Invalid phone number format",
                    severity=ValidationSeverity.WARNING,
                    field="phone"
                ))

    async def _validate_customer_uniqueness(
        self,
        db: AsyncSession,
        customer_data: Dict,
        issues: List[ValidationIssue]
    ):
        """Validate customer uniqueness constraints."""
        # This is already handled in _validate_customer_business_rules
        pass

    async def _validate_ar_invoice_structure(self, ar_invoice_data: Dict, issues: List[ValidationIssue]) -> bool:
        """Validate AR invoice data structure."""
        required_fields = [
            "invoice_number",
            "invoice_date",
            "due_date",
            "total_amount"
        ]

        structure_valid = True
        for field in required_fields:
            if field not in ar_invoice_data or ar_invoice_data[field] is None:
                issues.append(ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    message=f"Missing required field: {field}",
                    severity=ValidationSeverity.ERROR,
                    field=field
                ))
                structure_valid = False

        return structure_valid

    def _calculate_ar_confidence_score(
        self,
        structure_result: bool,
        error_count: int,
        warning_count: int
    ) -> float:
        """Calculate confidence score for AR validation."""
        base_score = 100.0

        if not structure_result:
            base_score -= 30.0

        base_score -= (error_count * 20.0)
        base_score -= (warning_count * 5.0)

        return max(0.0, min(100.0, base_score))

    def _get_business_rule_codes(self) -> List[str]:
        """Get list of business rule validation codes."""
        return [
            ValidationCode.DUPLICATE_INVOICE,
            ValidationCode.INVALID_CURRENCY,
            ValidationCode.PAYMENT_TERMS_MISMATCH,
            ValidationCode.CREDIT_LIMIT_EXCEEDED,
            ValidationCode.CREDIT_LIMIT_WARNING,
            ValidationCode.DISCOUNT_PERIOD_INVALID,
            ValidationCode.DUPLICATE_CUSTOMER,
            ValidationCode.HIGH_CREDIT_LIMIT,
            ValidationCode.LONG_PAYMENT_TERMS
        ]