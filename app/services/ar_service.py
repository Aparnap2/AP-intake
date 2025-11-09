"""
AR (Accounts Receivable) service for managing customers and invoices.

This service provides business logic for AR operations, working capital optimization,
and integration with existing validation, deduplication, and metrics services.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_

from app.models.ar_invoice import (
    Customer,
    ARInvoice,
    PaymentStatus,
    CollectionPriority
)
from app.models.invoice import Invoice, InvoiceStatus
from app.services.validation_service import ValidationService
from app.services.deduplication_service import DeduplicationService
from app.services.metrics_service import MetricsService


class ARService:
    """Service for managing AR customers and invoices."""

    def __init__(self):
        """Initialize AR service with integrated services."""
        self.validation_service = ValidationService()
        self.deduplication_service = DeduplicationService()
        self.metrics_service = MetricsService()

    async def create_customer(
        self,
        db: AsyncSession,
        customer_data: Dict
    ) -> Customer:
        """Create a new AR customer with validation."""
        # Validate customer data
        await self._validate_customer_data(db, customer_data)

        # Check for duplicate customer
        existing_customer = await self._find_duplicate_customer(db, customer_data)
        if existing_customer:
            raise ValueError(f"Customer already exists: {existing_customer.id}")

        # Create customer
        customer = Customer(
            name=customer_data["name"],
            tax_id=customer_data.get("tax_id"),
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            address=customer_data.get("address"),
            currency=customer_data.get("currency", "USD"),
            credit_limit=Decimal(str(customer_data.get("credit_limit", 0))),
            payment_terms_days=str(customer_data.get("payment_terms_days", 30)),
            active=customer_data.get("active", True)
        )

        db.add(customer)
        await db.commit()
        await db.refresh(customer)

        # Log metrics
        await self.metrics_service.record_customer_created(customer)

        return customer

    async def create_ar_invoice(
        self,
        db: AsyncSession,
        invoice_data: Dict
    ) -> ARInvoice:
        """Create a new AR invoice with validation and deduplication."""
        # Validate customer exists
        customer = await self._get_customer(db, invoice_data["customer_id"])
        if not customer:
            raise ValueError(f"Customer not found: {invoice_data['customer_id']}")

        # Validate invoice data
        await self._validate_ar_invoice_data(db, invoice_data, customer)

        # Check for duplicate invoice
        duplicate = await self._find_duplicate_ar_invoice(db, invoice_data)
        if duplicate:
            raise ValueError(f"Duplicate invoice found: {duplicate.invoice_number}")

        # Create AR invoice
        ar_invoice = ARInvoice(
            customer_id=invoice_data["customer_id"],
            invoice_number=invoice_data["invoice_number"],
            invoice_date=invoice_data["invoice_date"],
            due_date=invoice_data["due_date"],
            currency=invoice_data.get("currency", customer.currency),
            subtotal=Decimal(str(invoice_data["subtotal"])),
            tax_amount=Decimal(str(invoice_data["tax_amount"])),
            total_amount=Decimal(str(invoice_data["total_amount"])),
            outstanding_amount=Decimal(str(invoice_data["total_amount"])),
            status=PaymentStatus.PENDING,
            collection_priority=self._determine_initial_collection_priority(
                invoice_data, customer
            ),
            early_payment_discount_percent=Decimal(str(invoice_data.get("early_payment_discount_percent", 0))),
            early_payment_discount_days=str(invoice_data.get("early_payment_discount_days", 0)),
            expected_payment_date=invoice_data.get("expected_payment_date"),
            working_capital_impact=Decimal(str(invoice_data.get("working_capital_impact", invoice_data["total_amount"])))
        )

        db.add(ar_invoice)
        await db.commit()
        await db.refresh(ar_invoice)

        # Log metrics
        await self.metrics_service.record_ar_invoice_created(ar_invoice)

        # Update customer collection priority if needed
        await self._update_customer_collection_priority(db, customer)

        return ar_invoice

    async def get_customer_outstanding_invoices(
        self,
        db: AsyncSession,
        customer_id: uuid.UUID
    ) -> List[ARInvoice]:
        """Get all outstanding invoices for a customer."""
        result = await db.execute(
            select(ARInvoice).where(
                and_(
                    ARInvoice.customer_id == customer_id,
                    ARInvoice.status.in_([
                        PaymentStatus.PENDING,
                        PaymentStatus.PARTIALLY_PAID,
                        PaymentStatus.OVERDUE
                    ])
                )
            ).order_by(ARInvoice.due_date)
        )
        return result.scalars().all()

    async def get_overdue_invoices(
        self,
        db: AsyncSession,
        customer_id: Optional[uuid.UUID] = None,
        priority: Optional[CollectionPriority] = None
    ) -> List[ARInvoice]:
        """Get overdue invoices with optional filtering."""
        query = select(ARInvoice).where(
            and_(
                ARInvoice.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID]),
                ARInvoice.due_date < datetime.utcnow()
            )
        )

        if customer_id:
            query = query.where(ARInvoice.customer_id == customer_id)

        if priority:
            query = query.where(ARInvoice.collection_priority == priority)

        query = query.order_by(ARInvoice.due_date)

        result = await db.execute(query)
        return result.scalars().all()

    async def apply_payment(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        payment_amount: Decimal,
        payment_date: Optional[datetime] = None
    ) -> ARInvoice:
        """Apply payment to an AR invoice."""
        # Get invoice
        result = await db.execute(
            select(ARInvoice).where(ARInvoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        if payment_amount <= 0:
            raise ValueError("Payment amount must be positive")

        # Apply payment
        success = await invoice.apply_payment(payment_amount, db)
        if not success:
            raise ValueError("Payment application failed")

        await db.refresh(invoice)

        # Log metrics
        await self.metrics_service.record_payment_applied(invoice, payment_amount)

        # Update customer collection priority
        customer = await self._get_customer(db, invoice.customer_id)
        await self._update_customer_collection_priority(db, customer)

        return invoice

    async def get_working_capital_summary(
        self,
        db: AsyncSession,
        customer_id: Optional[uuid.UUID] = None
    ) -> Dict:
        """Get working capital summary for AR portfolio."""
        base_query = select(ARInvoice).where(
            ARInvoice.status.in_([
                PaymentStatus.PENDING,
                PaymentStatus.PARTIALLY_PAID,
                PaymentStatus.OVERDUE
            ])
        )

        if customer_id:
            base_query = base_query.where(ARInvoice.customer_id == customer_id)

        result = await db.execute(base_query)
        invoices = result.scalars().all()

        if not invoices:
            return {
                "total_outstanding": Decimal("0.00"),
                "invoice_count": 0,
                "overdue_count": 0,
                "average_days_outstanding": 0,
                "working_capital_impact": Decimal("0.00")
            }

        # Calculate metrics
        total_outstanding = sum(inv.outstanding_amount for inv in invoices)
        overdue_invoices = [inv for inv in invoices if inv.is_overdue()]

        # Calculate average days outstanding
        days_outstanding = []
        for inv in invoices:
            days = (datetime.utcnow() - inv.invoice_date).days
            days_outstanding.append(days)

        avg_days_outstanding = sum(days_outstanding) / len(days_outstanding) if days_outstanding else 0

        # Calculate working capital impact
        wc_impact = sum(inv.working_capital_impact or Decimal("0.00") for inv in invoices)

        return {
            "total_outstanding": total_outstanding,
            "invoice_count": len(invoices),
            "overdue_count": len(overdue_invoices),
            "overdue_percentage": (len(overdue_invoices) / len(invoices)) * 100,
            "average_days_outstanding": round(avg_days_outstanding, 2),
            "working_capital_impact": wc_impact
        }

    async def get_collection_recommendations(
        self,
        db: AsyncSession,
        customer_id: Optional[uuid.UUID] = None
    ) -> List[Dict]:
        """Get collection recommendations for overdue invoices."""
        overdue_invoices = await self.get_overdue_invoices(db, customer_id)

        recommendations = []
        for invoice in overdue_invoices:
            days_overdue = invoice.days_overdue()

            if days_overdue > 90:
                recommendations.append({
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "customer_id": invoice.customer_id,
                    "days_overdue": days_overdue,
                    "amount": invoice.outstanding_amount,
                    "recommendation": "Escalate to collections agency",
                    "priority": "URGENT"
                })
            elif days_overdue > 60:
                recommendations.append({
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "customer_id": invoice.customer_id,
                    "days_overdue": days_overdue,
                    "amount": invoice.outstanding_amount,
                    "recommendation": "Send formal demand letter",
                    "priority": "HIGH"
                })
            elif days_overdue > 30:
                recommendations.append({
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "customer_id": invoice.customer_id,
                    "days_overdue": days_overdue,
                    "amount": invoice.outstanding_amount,
                    "recommendation": "Send payment reminder with late fees",
                    "priority": "MEDIUM"
                })
            else:
                recommendations.append({
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "customer_id": invoice.customer_id,
                    "days_overdue": days_overdue,
                    "amount": invoice.outstanding_amount,
                    "recommendation": "Send friendly payment reminder",
                    "priority": "LOW"
                })

        return sorted(recommendations, key=lambda x: x["days_overdue"], reverse=True)

    # Private helper methods

    async def _validate_customer_data(self, db: AsyncSession, customer_data: Dict):
        """Validate customer data."""
        if not customer_data.get("name") or not customer_data["name"].strip():
            raise ValueError("Customer name is required")

        # Validate email format if provided
        if customer_data.get("email"):
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, customer_data["email"]):
                raise ValueError("Invalid email format")

        # Validate currency format
        currency = customer_data.get("currency", "USD")
        if not re.match(r'^[A-Z]{3}$', currency):
            raise ValueError("Currency must be a valid 3-letter code")

        # Validate credit limit is positive
        if "credit_limit" in customer_data and customer_data["credit_limit"] < 0:
            raise ValueError("Credit limit must be non-negative")

    async def _find_duplicate_customer(self, db: AsyncSession, customer_data: Dict) -> Optional[Customer]:
        """Find duplicate customer based on tax_id or email."""
        query = select(Customer).where(
            or_(
                Customer.tax_id == customer_data.get("tax_id"),
                Customer.email == customer_data.get("email")
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _get_customer(self, db: AsyncSession, customer_id: uuid.UUID) -> Optional[Customer]:
        """Get customer by ID."""
        result = await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def _validate_ar_invoice_data(self, db: AsyncSession, invoice_data: Dict, customer: Customer):
        """Validate AR invoice data."""
        # Required fields
        required_fields = ["invoice_number", "invoice_date", "due_date", "total_amount"]
        for field in required_fields:
            if field not in invoice_data:
                raise ValueError(f"Missing required field: {field}")

        # Validate dates
        if invoice_data["due_date"] <= invoice_data["invoice_date"]:
            raise ValueError("Due date must be after invoice date")

        # Validate amount
        if invoice_data["total_amount"] <= 0:
            raise ValueError("Total amount must be positive")

        # Validate currency matches customer
        invoice_currency = invoice_data.get("currency", customer.currency)
        if invoice_currency != customer.currency:
            raise ValueError(f"Invoice currency {invoice_currency} doesn't match customer currency {customer.currency}")

    async def _find_duplicate_ar_invoice(self, db: AsyncSession, invoice_data: Dict) -> Optional[ARInvoice]:
        """Find duplicate AR invoice."""
        result = await db.execute(
            select(ARInvoice).where(ARInvoice.invoice_number == invoice_data["invoice_number"])
        )
        return result.scalar_one_or_none()

    def _determine_initial_collection_priority(
        self,
        invoice_data: Dict,
        customer: Customer
    ) -> CollectionPriority:
        """Determine initial collection priority for invoice."""
        amount = invoice_data["total_amount"]

        # High value invoices get higher priority
        if amount >= Decimal("10000.00"):
            return CollectionPriority.HIGH
        elif amount >= Decimal("5000.00"):
            return CollectionPriority.MEDIUM
        else:
            return CollectionPriority.LOW

    async def _update_customer_collection_priority(self, db: AsyncSession, customer: Customer):
        """Update customer's overall collection priority based on invoices."""
        # Get outstanding invoices
        result = await db.execute(
            select(ARInvoice).where(
                and_(
                    ARInvoice.customer_id == customer.id,
                    ARInvoice.status.in_([
                        PaymentStatus.PENDING,
                        PaymentStatus.PARTIALLY_PAID,
                        PaymentStatus.OVERDUE
                    ])
                )
            )
        )
        invoices = result.scalars().all()

        if not invoices:
            return

        # Update collection priorities for overdue invoices
        for invoice in invoices:
            if invoice.is_overdue():
                invoice.update_collection_priority()

        await db.commit()