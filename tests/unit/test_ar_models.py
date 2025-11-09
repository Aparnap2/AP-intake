"""
Unit tests for AR (Accounts Receivable) models following TDD methodology.

This test file is written first before implementing the AR models.
Tests will fail initially, then drive the implementation of the AR models.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, AsyncMock

from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus, CollectionPriority
from app.models.invoice import Invoice, InvoiceStatus
from app.db.session import Base
from uuid import UUID


class TestCustomerModel:
    """Test suite for Customer model - TDD approach."""

    @pytest.mark.asyncio
    async def test_create_customer_success(self, async_session: AsyncSession):
        """Test successful customer creation with valid data."""
        # This test will fail until Customer model is implemented
        customer_data = {
            "name": "Acme Corporation",
            "tax_id": "12-3456789",
            "email": "billing@acme.com",
            "phone": "+1-555-0123",
            "address": "123 Business St, Suite 100, New York, NY 10001",
            "currency": "USD",
            "credit_limit": Decimal("50000.00"),
            "payment_terms_days": 30,
            "active": True,
        }

        # This should fail initially - Customer model doesn't exist yet
        customer = Customer(**customer_data)
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Assertions that will drive implementation
        assert customer.id is not None
        assert customer.name == "Acme Corporation"
        assert customer.tax_id == "12-3456789"
        assert customer.email == "billing@acme.com"
        assert customer.currency == "USD"
        assert customer.credit_limit == Decimal("50000.00")
        assert customer.payment_terms_days == 30
        assert customer.active is True
        assert customer.created_at is not None
        assert customer.updated_at is not None

    @pytest.mark.asyncio
    async def test_customer_validation_required_fields(self, async_session: AsyncSession):
        """Test customer validation with missing required fields."""
        # Test missing name (should fail)
        with pytest.raises(IntegrityError):
            customer = Customer(
                name="",  # Empty name should violate constraint
                currency="USD"
            )
            async_session.add(customer)
            await async_session.commit()

    @pytest.mark.asyncio
    async def test_customer_credit_limit_management(self, async_session: AsyncSession):
        """Test customer credit limit functionality."""
        customer = Customer(
            name="Test Customer",
            credit_limit=Decimal("10000.00"),
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Test credit limit property
        assert customer.credit_limit == Decimal("10000.00")

        # Test available credit calculation (will drive implementation)
        # This assumes we have a method to calculate used credit
        used_credit = await customer.get_used_credit(async_session)
        available_credit = customer.credit_limit - used_credit
        assert available_credit == Decimal("10000.00")  # No invoices yet

    @pytest.mark.asyncio
    async def test_customer_payment_terms_handling(self, async_session: AsyncSession):
        """Test customer payment terms validation and calculation."""
        customer = Customer(
            name="Test Customer",
            payment_terms_days=45,
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Test payment terms
        assert customer.payment_terms_days == 45

        # Test due date calculation (will drive implementation)
        invoice_date = datetime.utcnow().date()
        expected_due_date = customer.calculate_due_date(invoice_date)
        assert expected_due_date == invoice_date + timedelta(days=45)

    @pytest.mark.asyncio
    async def test_customer_invoice_relationship_tracking(self, async_session: AsyncSession):
        """Test customer-invoice relationship and invoice tracking."""
        # Create customer
        customer = Customer(
            name="Test Customer",
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Test relationship with AR invoices (will drive implementation)
        assert hasattr(customer, 'ar_invoices')

        # Test invoice counting method (will drive implementation)
        invoice_count = await customer.get_invoice_count(async_session)
        assert invoice_count == 0  # No invoices yet

        # Test outstanding balance calculation (will drive implementation)
        outstanding_balance = await customer.get_outstanding_balance(async_session)
        assert outstanding_balance == Decimal('0.00')

    @pytest.mark.asyncio
    async def test_customer_unique_constraints(self, async_session: AsyncSession):
        """Test customer unique constraints for tax_id and email."""
        # Create first customer
        customer1 = Customer(
            name="Customer One",
            tax_id="12-3456789",
            email="billing@customer.com",
            currency="USD"
        )
        async_session.add(customer1)
        await async_session.commit()

        # Create second customer with same tax_id (should fail)
        with pytest.raises(IntegrityError):
            customer2 = Customer(
                name="Customer Two",
                tax_id="12-3456789",  # Same tax_id
                currency="USD"
            )
            async_session.add(customer2)
            await async_session.commit()

    def test_customer_currency_validation(self):
        """Test customer currency format validation."""
        # Valid currencies (will drive constraint implementation)
        valid_currencies = ["USD", "EUR", "GBP", "CAD"]

        for currency in valid_currencies:
            customer = Customer(name="Test", currency=currency)
            assert customer.currency == currency

    @pytest.mark.asyncio
    async def test_customer_soft_delete_functionality(self, async_session: AsyncSession):
        """Test customer soft delete via active flag."""
        customer = Customer(
            name="Test Customer",
            active=True,
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Test soft delete
        customer.active = False
        await async_session.commit()
        await async_session.refresh(customer)

        assert customer.active is False
        assert customer.created_at is not None  # Timestamps preserved

    def test_customer_string_representation(self):
        """Test customer __repr__ method."""
        customer = Customer(
            name="Test Customer",
            tax_id="12-3456789"
        )

        # Test __repr__ implementation
        result = repr(customer)
        assert "Customer" in result
        assert "Test Customer" in result
        assert "12-3456789" in result


class TestARInvoiceModel:
    """Test suite for AR Invoice model - TDD approach."""

    @pytest.mark.asyncio
    async def test_create_ar_invoice_success(self, async_session: AsyncSession):
        """Test successful AR invoice creation with valid data."""
        # Create customer first
        customer = Customer(
            name="Test Customer",
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create AR invoice
        ar_invoice_data = {
            "customer_id": customer.id,
            "invoice_number": "AR-2024-001",
            "invoice_date": datetime.utcnow().date(),
            "due_date": (datetime.utcnow() + timedelta(days=30)).date(),
            "currency": "USD",
            "subtotal": Decimal("1000.00"),
            "tax_amount": Decimal("100.00"),
            "total_amount": Decimal("1100.00"),
            "status": PaymentStatus.PENDING,
            "collection_priority": CollectionPriority.MEDIUM,
        }

        # This will fail initially - ARInvoice model doesn't exist yet
        ar_invoice = ARInvoice(**ar_invoice_data)
        async_session.add(ar_invoice)
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        # Assertions that will drive implementation
        assert ar_invoice.id is not None
        assert ar_invoice.customer_id == customer.id
        assert ar_invoice.invoice_number == "AR-2024-001"
        assert ar_invoice.total_amount == Decimal("1100.00")
        assert ar_invoice.status == PaymentStatus.PENDING
        assert ar_invoice.collection_priority == CollectionPriority.MEDIUM
        assert ar_invoice.created_at is not None
        assert ar_invoice.updated_at is not None

    @pytest.mark.asyncio
    async def test_ar_invoice_customer_linking(self, async_session: AsyncSession):
        """Test AR invoice linking to customer with validation."""
        # Create customer
        customer = Customer(
            name="Test Customer",
            currency="USD"
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create AR invoice linked to customer
        ar_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            currency="USD"
        )
        async_session.add(ar_invoice)
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        # Test relationship (will drive implementation)
        assert hasattr(ar_invoice, 'customer')
        assert ar_invoice.customer.id == customer.id
        assert ar_invoice.customer.name == "Test Customer"

    @pytest.mark.asyncio
    async def test_ar_invoice_payment_status_tracking(self, async_session: AsyncSession):
        """Test AR invoice payment status transitions."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create invoice with PENDING status
        ar_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            status=PaymentStatus.PENDING,
            currency="USD"
        )
        async_session.add(ar_invoice)
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        assert ar_invoice.status == PaymentStatus.PENDING

        # Test status transition to PAID
        ar_invoice.status = PaymentStatus.PAID
        ar_invoice.paid_at = datetime.utcnow()
        ar_invoice.paid_amount = Decimal("1000.00")
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        assert ar_invoice.status == PaymentStatus.PAID
        assert ar_invoice.paid_at is not None
        assert ar_invoice.paid_amount == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_ar_invoice_due_date_and_collection_priority(self, async_session: AsyncSession):
        """Test AR invoice due date calculation and collection priority logic."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create overdue invoice
        past_date = datetime.utcnow() - timedelta(days=10)
        ar_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            invoice_date=past_date.date(),
            due_date=past_date.date(),
            total_amount=Decimal("1000.00"),
            currency="USD"
        )
        async_session.add(ar_invoice)
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        # Test overdue calculation (will drive implementation)
        assert ar_invoice.is_overdue() is True

        # Test days overdue calculation
        days_overdue = ar_invoice.days_overdue()
        assert days_overdue >= 10

        # Test collection priority update (will drive implementation)
        ar_invoice.update_collection_priority()
        assert ar_invoice.collection_priority == CollectionPriority.HIGH

    @pytest.mark.asyncio
    async def test_ar_invoice_working_capital_fields(self, async_session: AsyncSession):
        """Test AR invoice working capital optimization fields."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        ar_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            currency="USD",
            # Working capital fields (will drive implementation)
            early_payment_discount_percent=Decimal("2.0"),
            early_payment_discount_days=10,
            expected_payment_date=datetime.utcnow() + timedelta(days=30),
            working_capital_impact=Decimal("1000.00")
        )
        async_session.add(ar_invoice)
        await async_session.commit()
        await async_session.refresh(ar_invoice)

        # Test early payment discount calculation
        discount_amount = ar_invoice.calculate_early_payment_discount()
        assert discount_amount == Decimal("20.00")  # 2% of 1000

        # Test working capital impact
        assert ar_invoice.working_capital_impact == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_ar_invoice_unique_constraints(self, async_session: AsyncSession):
        """Test AR invoice unique constraints for invoice number."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create first invoice
        ar_invoice1 = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            currency="USD"
        )
        async_session.add(ar_invoice1)
        await async_session.commit()

        # Create second invoice with same number (should fail)
        with pytest.raises(IntegrityError):
            ar_invoice2 = ARInvoice(
                customer_id=customer.id,
                invoice_number="AR-001",  # Same invoice number
                total_amount=Decimal("2000.00"),
                currency="USD"
            )
            async_session.add(ar_invoice2)
            await async_session.commit()

    @pytest.mark.asyncio
    async def test_ar_invoice_amount_validation(self, async_session: AsyncSession):
        """Test AR invoice amount validation and business rules."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Test negative amounts (should fail validation)
        with pytest.raises(ValueError):
            ARInvoice(
                customer_id=customer.id,
                invoice_number="AR-001",
                total_amount=Decimal("-100.00"),  # Negative amount
                currency="USD"
            )

    def test_ar_invoice_string_representation(self):
        """Test AR invoice __repr__ method."""
        ar_invoice = ARInvoice(
            customer_id=UUID('12345678-1234-5678-9abc-123456789abc'),
            invoice_number="AR-001",
            total_amount=Decimal("1000.00")
        )

        # Test __repr__ implementation
        result = repr(ar_invoice)
        assert "ARInvoice" in result
        assert "AR-001" in result
        assert "PENDING" in result
        assert "1000.00" in result


class TestWorkingCapitalAnalytics:
    """Test suite for Working Capital Analytics functionality - TDD approach."""

    @pytest.mark.asyncio
    async def test_cash_flow_calculation(self, async_session: AsyncSession):
        """Test cash flow calculation for AR portfolio."""
        # Create test data
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create multiple AR invoices with different due dates
        invoices = []
        for i in range(3):
            invoice = ARInvoice(
                customer_id=customer.id,
                invoice_number=f"AR-{i+1:003}",
                total_amount=Decimal(f"{1000 * (i+1)}.00"),
                due_date=datetime.utcnow() + timedelta(days=30*(i+1)),
                currency="USD"
            )
            invoices.append(invoice)
            async_session.add(invoice)

        await async_session.commit()

        # Test cash flow calculation (will drive implementation)
        cash_flow = await ARInvoice.calculate_cash_flow(async_session, customer.id)

        assert "weekly_forecast" in cash_flow
        assert "monthly_forecast" in cash_flow
        assert "total_outstanding" in cash_flow
        assert cash_flow["total_outstanding"] == Decimal("6000.00")  # 1000+2000+3000

    @pytest.mark.asyncio
    async def test_payment_optimization_recommendations(self, async_session: AsyncSession):
        """Test payment optimization recommendations for working capital."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create invoice with early payment discount
        invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            early_payment_discount_percent=Decimal("2.0"),
            early_payment_discount_days=10,
            due_date=datetime.utcnow() + timedelta(days=30),
            currency="USD"
        )
        async_session.add(invoice)
        await async_session.commit()

        # Test optimization recommendations (will drive implementation)
        recommendations = await ARInvoice.get_payment_optimization_recommendations(async_session)

        assert isinstance(recommendations, list)
        if recommendations:  # If there are recommendations
            recommendation = recommendations[0]
            assert "invoice_id" in recommendation
            assert "recommendation_type" in recommendation
            assert "potential_savings" in recommendation

    @pytest.mark.asyncio
    async def test_early_payment_discount_identification(self, async_session: AsyncSession):
        """Test identification of invoices eligible for early payment discounts."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create invoice with early payment discount
        invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-001",
            total_amount=Decimal("1000.00"),
            early_payment_discount_percent=Decimal("2.0"),
            early_payment_discount_days=10,
            due_date=datetime.utcnow() + timedelta(days=30),
            currency="USD"
        )
        async_session.add(invoice)
        await async_session.commit()

        # Test early payment discount identification (will drive implementation)
        discount_opportunities = await ARInvoice.find_early_payment_discount_opportunities(async_session)

        assert isinstance(discount_opportunities, list)
        if discount_opportunities:
            opportunity = discount_opportunities[0]
            assert opportunity["invoice_id"] == invoice.id
            assert opportunity["discount_amount"] == Decimal("20.00")  # 2% of 1000
            assert opportunity["deadline"] is not None

    @pytest.mark.asyncio
    async def test_collection_efficiency_metrics(self, async_session: AsyncSession):
        """Test collection efficiency metrics calculation."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create paid and unpaid invoices
        paid_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-PAID",
            total_amount=Decimal("1000.00"),
            status=PaymentStatus.PAID,
            paid_at=datetime.utcnow() - timedelta(days=5),
            invoice_date=datetime.utcnow() - timedelta(days=35),
            due_date=datetime.utcnow() - timedelta(days=30),
            currency="USD"
        )

        unpaid_invoice = ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-UNPAID",
            total_amount=Decimal("1000.00"),
            status=PaymentStatus.OVERDUE,
            invoice_date=datetime.utcnow() - timedelta(days=40),
            due_date=datetime.utcnow() - timedelta(days=10),
            currency="USD"
        )

        async_session.add_all([paid_invoice, unpaid_invoice])
        await async_session.commit()

        # Test collection efficiency metrics (will drive implementation)
        metrics = await ARInvoice.calculate_collection_efficiency(async_session, customer.id)

        assert "average_days_to_pay" in metrics
        assert "collection_rate" in metrics
        assert "overdue_percentage" in metrics
        assert metrics["collection_rate"] == Decimal("50.00")  # 1 out of 2 invoices paid

    @pytest.mark.asyncio
    async def test_working_capital_optimization_score(self, async_session: AsyncSession):
        """Test working capital optimization score calculation."""
        customer = Customer(name="Test Customer", currency="USD")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # Create diverse portfolio of invoices
        invoices = []
        # Current invoice
        invoices.append(ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-CURRENT",
            total_amount=Decimal("1000.00"),
            due_date=datetime.utcnow() + timedelta(days=30),
            currency="USD"
        ))

        # Overdue invoice
        invoices.append(ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-OVERDUE",
            total_amount=Decimal("500.00"),
            due_date=datetime.utcnow() - timedelta(days=10),
            status=PaymentStatus.OVERDUE,
            currency="USD"
        ))

        # Discount opportunity
        invoices.append(ARInvoice(
            customer_id=customer.id,
            invoice_number="AR-DISCOUNT",
            total_amount=Decimal("2000.00"),
            early_payment_discount_percent=Decimal("2.0"),
            early_payment_discount_days=5,
            due_date=datetime.utcnow() + timedelta(days=30),
            currency="USD"
        ))

        for invoice in invoices:
            async_session.add(invoice)
        await async_session.commit()

        # Test optimization score (will drive implementation)
        optimization_score = await ARInvoice.calculate_working_capital_optimization_score(async_session, customer.id)

        assert "overall_score" in optimization_score
        assert "collection_efficiency_score" in optimization_score
        assert "discount_optimization_score" in optimization_score
        assert "recommendations" in optimization_score
        assert 0 <= optimization_score["overall_score"] <= 100