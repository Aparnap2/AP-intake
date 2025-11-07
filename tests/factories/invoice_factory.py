"""
Factory for generating Invoice test data.
"""

import factory
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker

from app.models.invoice import Invoice, InvoiceStatus

fake = Faker()


class InvoiceFactory(factory.Factory):
    """Factory for generating Invoice model instances."""

    class Meta:
        model = Invoice
        sqlalchemy_session_persistence = "flush"

    # Basic invoice information
    file_name = factory.Faker('file_name', extension='pdf')
    file_path = factory.LazyAttribute(lambda obj: f"/tmp/invoices/{obj.file_name}")
    file_hash = factory.Faker('sha256')
    file_size = factory.Faker('random_int', min=100, max=10000)

    # Vendor relationship
    vendor_id = factory.Faker('uuid4')

    # Status and workflow
    status = factory.Iterator(InvoiceStatus)
    workflow_state = factory.Iterator([
        'uploaded', 'parsing', 'validating', 'patching',
        'validated', 'review', 'approved', 'staged', 'exported'
    ])

    # Processing data
    extracted_data = factory.LazyAttribute(lambda _: {
        "header": {
            "vendor_name": fake.company(),
            "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
            "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
            "due_date": fake.date_between().strftime("%Y-%m-%d"),
            "total": str(Decimal(fake.random_int(100, 10000)) / 100),
            "currency": "USD"
        },
        "lines": [
            {
                "description": fake.catch_phrase(),
                "quantity": fake.random_int(1, 10),
                "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                "amount": str(Decimal(fake.random_int(100, 1000)) / 100)
            }
        ]
    })

    confidence_score = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    processing_errors = factory.LazyFunction(list)

    # Metadata
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
    processed_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(minutes=fake.random_int(1, 60))
        if obj.status != InvoiceStatus.RECEIVED else None
    )

    # Review information
    reviewed_by = factory.LazyAttribute(
        lambda obj: fake.user_name() if obj.status in [
            InvoiceStatus.REVIEW, InvoiceStatus.READY, InvoiceStatus.STAGED
        ] else None
    )
    reviewed_at = factory.LazyAttribute(
        lambda obj: datetime.utcnow() - timedelta(hours=fake.random_int(1, 24))
        if obj.reviewed_by else None
    )


class InvoiceLineFactory(factory.Factory):
    """Factory for generating invoice line items."""

    class Meta:
        model = dict  # Using dict since lines are stored as JSON

    description = factory.Faker('catch_phrase')
    quantity = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    unit_price = factory.Faker('pydecimal', left_digits=5, right_digits=2, positive=True)
    amount = factory.LazyAttribute(
        lambda obj: str(Decimal(str(obj.quantity)) * Decimal(str(obj.unit_price)))
    )
    sku = factory.Faker('ean', length=8)
    tax_rate = factory.Faker('pydecimal', left_digits=2, right_digits=3, positive=True)
    discount = factory.Faker('pydecimal', left_digits=1, right_digits=2, positive=False)


class ProcessedInvoiceFactory(InvoiceFactory):
    """Factory for generating fully processed invoices."""

    status = InvoiceStatus.READY
    workflow_state = 'validated'
    confidence_score = factory.Faker('pyfloat', min_value=0.85, max_value=0.98)
    processing_errors = []
    processed_at = factory.LazyFunction(datetime.utcnow)


class HighValueInvoiceFactory(InvoiceFactory):
    """Factory for generating high-value invoices."""

    file_size = factory.Faker('random_int', min=5000, max=50000)
    extracted_data = factory.LazyAttribute(lambda _: {
        "header": {
            "vendor_name": fake.company(),
            "invoice_no": f"INV-{fake.random_int(10000, 99999)}",
            "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
            "due_date": fake.date_between().strftime("%Y-%m-%d"),
            "total": str(Decimal(fake.random_int(10000, 100000)) / 100),
            "currency": "USD"
        },
        "lines": [
            {
                "description": fake.catch_phrase(),
                "quantity": fake.random_int(10, 100),
                "unit_price": str(Decimal(fake.random_int(100, 1000)) / 100),
                "amount": str(Decimal(fake.random_int(1000, 10000)) / 100)
            }
            for _ in range(fake.random_int(5, 20))
        ]
    })


class ErrorInvoiceFactory(InvoiceFactory):
    """Factory for generating invoices with processing errors."""

    status = InvoiceStatus.ERROR
    workflow_state = 'error'
    confidence_score = factory.Faker('pyfloat', min_value=0.0, max_value=0.5)
    processing_errors = factory.LazyAttribute(lambda _: [
        {
            "step": "validation",
            "error": "Missing required field: vendor_name",
            "severity": "error",
            "timestamp": datetime.utcnow().isoformat()
        },
        {
            "step": "extraction",
            "error": "Low confidence score for line items",
            "severity": "warning",
            "timestamp": datetime.utcnow().isoformat()
        }
    ])


class ReviewRequiredInvoiceFactory(InvoiceFactory):
    """Factory for generating invoices requiring manual review."""

    status = InvoiceStatus.REVIEW
    workflow_state = 'review_required'
    confidence_score = factory.Faker('pyfloat', min_value=0.6, max_value=0.8)
    processing_errors = factory.LazyAttribute(lambda _: [
        {
            "step": "validation",
            "error": "Vendor not found in database",
            "severity": "warning",
            "timestamp": datetime.utcnow().isoformat()
        }
    ])


class StagedInvoiceFactory(InvoiceFactory):
    """Factory for generating staged invoices ready for export."""

    status = InvoiceStatus.STAGED
    workflow_state = 'approved'
    confidence_score = factory.Faker('pyfloat', min_value=0.9, max_value=0.98)
    processing_errors = []
    reviewed_by = factory.Faker('user_name')
    reviewed_at = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(hours=fake.random_int(1, 12))
    )