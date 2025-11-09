"""
AR (Accounts Receivable) invoice and customer models.

This module extends the existing invoice structure to support AR invoices,
customer management, and working capital optimization features.
"""

import enum
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    """Payment status for AR invoices."""

    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITE_OFF = "write_off"
    DISPUTED = "disputed"


class CollectionPriority(str, enum.Enum):
    """Collection priority for AR invoices."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Customer(Base, UUIDMixin, TimestampMixin):
    """Customer master data for AR invoices."""

    __tablename__ = "customers"

    # Basic customer information
    name = Column(String(255), nullable=False, index=True)
    tax_id = Column(String(50), nullable=True, unique=True)
    currency = Column(String(3), nullable=False, default="USD")

    # Contact information
    email = Column(String(255), nullable=True, unique=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)

    # Financial information
    credit_limit = Column(Numeric(15, 2), nullable=True, default=Decimal('0.00'))
    payment_terms_days = Column(String(10), nullable=True, default="30")

    # Status and metadata
    active = Column(Boolean, nullable=False, default=True, index=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_customer_active_name', 'active', 'name'),
        Index('idx_customer_tax_id', 'tax_id'),
        # Data integrity constraints
        CheckConstraint("name <> ''", name='check_customer_name_not_empty'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='check_customer_currency_format'),
        CheckConstraint(r"CASE WHEN email IS NOT NULL THEN email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' ELSE true END",
                       name='check_customer_email_format'),
        CheckConstraint("credit_limit >= 0", name='check_customer_credit_limit_positive'),
    )

    # Relationships
    ar_invoices = relationship("ARInvoice", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(id={self.id}, name={self.name}, tax_id={self.tax_id})>"

    async def get_used_credit(self, db: AsyncSession) -> Decimal:
        """Calculate total amount of outstanding invoices for this customer."""
        result = await db.execute(
            select(func.coalesce(func.sum(ARInvoice.total_amount), 0))
            .where(
                ARInvoice.customer_id == self.id,
                ARInvoice.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID, PaymentStatus.OVERDUE])
            )
        )
        used_credit = result.scalar() or Decimal('0.00')
        return used_credit

    async def get_available_credit(self, db: AsyncSession) -> Decimal:
        """Calculate available credit for this customer."""
        used_credit = await self.get_used_credit(db)
        credit_limit = self.credit_limit or Decimal('0.00')
        return max(Decimal('0.00'), credit_limit - used_credit)

    def calculate_due_date(self, invoice_date: date) -> date:
        """Calculate due date based on payment terms."""
        try:
            days = int(self.payment_terms_days or 30)
        except (ValueError, TypeError):
            days = 30
        return invoice_date + timedelta(days=days)

    async def get_invoice_count(self, db: AsyncSession) -> int:
        """Get total number of invoices for this customer."""
        result = await db.execute(
            select(func.count(ARInvoice.id))
            .where(ARInvoice.customer_id == self.id)
        )
        return result.scalar() or 0

    async def get_outstanding_balance(self, db: AsyncSession) -> Decimal:
        """Calculate total outstanding balance for this customer."""
        result = await db.execute(
            select(func.coalesce(func.sum(ARInvoice.outstanding_amount), 0))
            .where(
                ARInvoice.customer_id == self.id,
                ARInvoice.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID, PaymentStatus.OVERDUE])
            )
        )
        return result.scalar() or Decimal('0.00')


class ARInvoice(Base, UUIDMixin, TimestampMixin):
    """Accounts Receivable invoice model."""

    __tablename__ = "ar_invoices"

    # Relationships
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    # Invoice identification
    invoice_number = Column(String(100), nullable=False, unique=True, index=True)

    # Invoice dates
    invoice_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)

    # Financial amounts
    currency = Column(String(3), nullable=False, default="USD")
    subtotal = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    tax_amount = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    total_amount = Column(Numeric(15, 2), nullable=False)
    outstanding_amount = Column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))

    # Payment tracking
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_amount = Column(Numeric(15, 2), nullable=True, default=Decimal('0.00'))

    # Collection management
    collection_priority = Column(Enum(CollectionPriority), default=CollectionPriority.MEDIUM, nullable=False)
    last_collection_attempt = Column(DateTime(timezone=True), nullable=True)
    collection_notes = Column(Text, nullable=True)

    # Working capital optimization fields
    early_payment_discount_percent = Column(Numeric(5, 2), nullable=True)
    early_payment_discount_days = Column(String(10), nullable=True)
    expected_payment_date = Column(DateTime(timezone=True), nullable=True)
    working_capital_impact = Column(Numeric(15, 2), nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_ar_invoice_customer_status', 'customer_id', 'status'),
        Index('idx_ar_invoice_due_date', 'due_date'),
        Index('idx_ar_invoice_collection_priority', 'collection_priority', 'status'),
        Index('idx_ar_invoice_dates', 'invoice_date', 'due_date', 'status'),
        # Data integrity constraints
        CheckConstraint("invoice_number <> ''", name='check_ar_invoice_number_not_empty'),
        CheckConstraint("total_amount >= 0", name='check_ar_total_amount_positive'),
        CheckConstraint("outstanding_amount >= 0", name='check_ar_outstanding_amount_positive'),
        CheckConstraint("paid_amount >= 0", name='check_ar_paid_amount_positive'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='check_ar_currency_format'),
        CheckConstraint("total_amount = subtotal + tax_amount", name='check_ar_amount_math'),
        CheckConstraint("due_date >= invoice_date", name='check_ar_due_date_after_invoice'),
    )

    # Relationships
    customer = relationship("Customer", back_populates="ar_invoices")

    def __init__(self, **kwargs):
        """Initialize AR invoice with validation."""
        # Validate total amount is not negative
        if 'total_amount' in kwargs and kwargs['total_amount'] is not None:
            if kwargs['total_amount'] < 0:
                raise ValueError("Total amount cannot be negative")

        super().__init__(**kwargs)

        # Set outstanding_amount to total_amount if not provided
        if self.outstanding_amount is None and self.total_amount is not None:
            self.outstanding_amount = self.total_amount

    def __repr__(self):
        return f"<ARInvoice(id={self.id}, invoice_number={self.invoice_number}, status={self.status}, amount={self.total_amount})>"

    def is_overdue(self) -> bool:
        """Check if the invoice is overdue."""
        if self.status in [PaymentStatus.PAID, PaymentStatus.WRITE_OFF]:
            return False
        return datetime.utcnow() > self.due_date

    def days_overdue(self) -> int:
        """Calculate number of days the invoice is overdue."""
        if not self.is_overdue():
            return 0
        return (datetime.utcnow() - self.due_date).days

    def update_collection_priority(self):
        """Update collection priority based on invoice status and overdue days."""
        days_overdue = self.days_overdue()

        if days_overdue > 90:
            self.collection_priority = CollectionPriority.URGENT
        elif days_overdue > 60:
            self.collection_priority = CollectionPriority.HIGH
        elif days_overdue > 30:
            self.collection_priority = CollectionPriority.MEDIUM
        else:
            self.collection_priority = CollectionPriority.LOW

    def calculate_early_payment_discount(self) -> Decimal:
        """Calculate early payment discount amount."""
        if not self.early_payment_discount_percent or not self.outstanding_amount:
            return Decimal('0.00')

        discount_rate = self.early_payment_discount_percent / Decimal('100')
        return self.outstanding_amount * discount_rate

    def is_early_payment_discount_available(self) -> bool:
        """Check if early payment discount is still available."""
        if not self.early_payment_discount_days:
            return False

        try:
            discount_days = int(self.early_payment_discount_days)
        except (ValueError, TypeError):
            return False

        discount_deadline = self.invoice_date + timedelta(days=discount_days)
        return datetime.utcnow() <= discount_deadline and self.status == PaymentStatus.PENDING

    async def apply_payment(self, amount: Decimal, db: AsyncSession) -> bool:
        """Apply payment to the invoice."""
        if amount <= 0:
            return False

        if amount >= self.outstanding_amount:
            # Full payment
            self.paid_amount = (self.paid_amount or Decimal('0.00')) + amount
            self.outstanding_amount = Decimal('0.00')
            self.status = PaymentStatus.PAID
            self.paid_at = datetime.utcnow()
        else:
            # Partial payment
            self.paid_amount = (self.paid_amount or Decimal('0.00')) + amount
            self.outstanding_amount -= amount
            self.status = PaymentStatus.PARTIALLY_PAID

        await db.commit()
        return True

    @classmethod
    async def calculate_cash_flow(cls, db: AsyncSession, customer_id: Optional[UUID] = None) -> dict:
        """Calculate cash flow forecast for AR invoices."""
        base_query = select(cls).where(cls.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID]))

        if customer_id:
            base_query = base_query.where(cls.customer_id == customer_id)

        result = await db.execute(base_query)
        invoices = result.scalars().all()

        # Initialize forecast structures
        weekly_forecast = {}
        monthly_forecast = {}
        total_outstanding = Decimal('0.00')

        for invoice in invoices:
            total_outstanding += invoice.outstanding_amount

            # Weekly forecast (next 12 weeks)
            week_key = invoice.due_date.isocalendar()[:2]  # (year, week)
            if week_key not in weekly_forecast:
                weekly_forecast[week_key] = Decimal('0.00')
            weekly_forecast[week_key] += invoice.outstanding_amount

            # Monthly forecast (next 12 months)
            month_key = (invoice.due_date.year, invoice.due_date.month)
            if month_key not in monthly_forecast:
                monthly_forecast[month_key] = Decimal('0.00')
            monthly_forecast[month_key] += invoice.outstanding_amount

        return {
            'total_outstanding': total_outstanding,
            'weekly_forecast': weekly_forecast,
            'monthly_forecast': monthly_forecast,
            'invoice_count': len(invoices)
        }

    @classmethod
    async def get_payment_optimization_recommendations(cls, db: AsyncSession) -> list:
        """Get payment optimization recommendations for working capital."""
        # Find invoices eligible for early payment discounts
        result = await db.execute(
            select(cls)
            .where(
                cls.status == PaymentStatus.PENDING,
                cls.early_payment_discount_percent.isnot(None),
                cls.early_payment_discount_days.isnot(None)
            )
            .order_by(cls.early_payment_discount_percent.desc())
        )
        invoices = result.scalars().all()

        recommendations = []
        for invoice in invoices:
            if invoice.is_early_payment_discount_available():
                discount_amount = invoice.calculate_early_payment_discount()
                recommendations.append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'customer_id': invoice.customer_id,
                    'recommendation_type': 'early_payment_discount',
                    'potential_savings': discount_amount,
                    'deadline': invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)),
                    'days_until_deadline': (invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)) - datetime.utcnow()).days,
                    'discount_percent': invoice.early_payment_discount_percent
                })

        return recommendations

    @classmethod
    async def find_early_payment_discount_opportunities(cls, db: AsyncSession) -> list:
        """Find all invoices eligible for early payment discounts."""
        result = await db.execute(
            select(cls)
            .where(
                cls.status == PaymentStatus.PENDING,
                cls.early_payment_discount_percent.isnot(None),
                cls.early_payment_discount_days.isnot(None)
            )
        )
        invoices = result.scalars().all()

        opportunities = []
        for invoice in invoices:
            if invoice.is_early_payment_discount_available():
                discount_amount = invoice.calculate_early_payment_discount()
                opportunities.append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'customer_id': invoice.customer_id,
                    'total_amount': invoice.total_amount,
                    'discount_amount': discount_amount,
                    'discount_percent': invoice.early_payment_discount_percent,
                    'deadline': invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)),
                    'days_until_deadline': (invoice.invoice_date + timedelta(days=int(invoice.early_payment_discount_days)) - datetime.utcnow()).days
                })

        return opportunities

    @classmethod
    async def calculate_collection_efficiency(cls, db: AsyncSession, customer_id: Optional[UUID] = None) -> dict:
        """Calculate collection efficiency metrics."""
        base_query = select(cls)

        if customer_id:
            base_query = base_query.where(cls.customer_id == customer_id)

        result = await db.execute(base_query)
        invoices = result.scalars().all()

        if not invoices:
            return {
                'average_days_to_pay': 0,
                'collection_rate': Decimal('0.00'),
                'overdue_percentage': Decimal('0.00'),
                'total_invoices': 0
            }

        paid_invoices = [inv for inv in invoices if inv.status == PaymentStatus.PAID and inv.paid_at]
        overdue_invoices = [inv for inv in invoices if inv.is_overdue()]

        # Calculate average days to pay
        avg_days_to_pay = 0
        if paid_invoices:
            days_to_pay = [(inv.paid_at - inv.invoice_date).days for inv in paid_invoices]
            avg_days_to_pay = sum(days_to_pay) / len(days_to_pay)

        # Calculate collection rate
        collection_rate = (len(paid_invoices) / len(invoices)) * 100

        # Calculate overdue percentage
        overdue_percentage = (len(overdue_invoices) / len(invoices)) * 100

        return {
            'average_days_to_pay': round(avg_days_to_pay, 2),
            'collection_rate': Decimal(str(round(collection_rate, 2))),
            'overdue_percentage': Decimal(str(round(overdue_percentage, 2))),
            'total_invoices': len(invoices),
            'paid_invoices': len(paid_invoices),
            'overdue_invoices': len(overdue_invoices)
        }

    @classmethod
    async def calculate_working_capital_optimization_score(cls, db: AsyncSession, customer_id: Optional[UUID] = None) -> dict:
        """Calculate working capital optimization score."""
        # Get collection efficiency metrics
        efficiency_metrics = await cls.calculate_collection_efficiency(db, customer_id)

        # Get discount opportunities
        discount_opportunities = await cls.find_early_payment_discount_opportunities(db)
        if customer_id:
            discount_opportunities = [opp for opp in discount_opportunities if opp['customer_id'] == customer_id]

        # Calculate collection efficiency score (0-100)
        collection_score = 100
        if efficiency_metrics['overdue_percentage'] > 20:
            collection_score -= efficiency_metrics['overdue_percentage']
        if efficiency_metrics['average_days_to_pay'] > 45:
            collection_score -= min(50, (efficiency_metrics['average_days_to_pay'] - 45))

        # Calculate discount optimization score (0-100)
        discount_score = 100
        total_discount_amount = sum(opp['discount_amount'] for opp in discount_opportunities)
        if total_discount_amount > 0 and len(discount_opportunities) > 0:
            # Score based on potential savings utilization
            avg_discount_days = sum(opp['days_until_deadline'] for opp in discount_opportunities) / len(discount_opportunities)
            if avg_discount_days < 7:  # Less than a week to use discounts
                discount_score = 30
            elif avg_discount_days < 14:  # Less than 2 weeks
                discount_score = 60
            elif avg_discount_days < 30:  # Less than a month
                discount_score = 80

        # Calculate overall score
        overall_score = (collection_score * 0.7) + (discount_score * 0.3)
        overall_score = max(0, min(100, overall_score))

        # Generate recommendations
        recommendations = []
        if efficiency_metrics['overdue_percentage'] > 20:
            recommendations.append("Implement proactive collection process for overdue invoices")
        if efficiency_metrics['average_days_to_pay'] > 45:
            recommendations.append("Review payment terms and collection procedures")
        if total_discount_amount > 0:
            recommendations.append(f"Utilize early payment discounts for potential savings of ${total_discount_amount:.2f}")

        return {
            'overall_score': Decimal(str(round(overall_score, 2))),
            'collection_efficiency_score': Decimal(str(round(collection_score, 2))),
            'discount_optimization_score': Decimal(str(round(discount_score, 2))),
            'recommendations': recommendations,
            'metrics': efficiency_metrics,
            'discount_opportunities': len(discount_opportunities),
            'potential_savings': total_discount_amount
        }