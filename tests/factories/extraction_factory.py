"""
Factory for generating document extraction test data.
"""

import factory
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker

fake = Faker()


class ExtractionHeaderFactory(factory.Factory):
    """Factory for generating extraction header data."""

    class Meta:
        model = dict

    # Basic invoice information
    vendor_name = factory.Faker('company')
    invoice_no = factory.LazyAttribute(lambda _: f"INV-{fake.random_int(1000, 9999)}")
    invoice_date = factory.LazyAttribute(
        lambda _: fake.date_between(start_date='-30d', end_date='today').strftime("%Y-%m-%d")
    )
    due_date = factory.LazyAttribute(
        lambda obj: (
            fake.date_between(
                start_date=obj.invoice_date,
                end_date='+90d'
            ).strftime("%Y-%m-%d") if obj.invoice_date else
            fake.date_between().strftime("%Y-%m-%d")
        )
    )

    # Purchase order information
    po_no = factory.LazyAttribute(
        lambda _: f"PO-{fake.random_int(10000, 99999)}" if fake.boolean() else None
    )

    # Financial information
    subtotal = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    tax = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    total = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    currency = factory.Iterator(['USD', 'EUR', 'GBP', 'CAD'])

    # Optional fields
    discount = factory.LazyAttribute(
        lambda _: Decimal(str(fake.random_int(0, 500))) / 100 if fake.boolean() else None
    )
    shipping = factory.LazyAttribute(
        lambda _: Decimal(str(fake.random_int(0, 200))) / 100 if fake.boolean() else None
    )
    notes = factory.LazyAttribute(
        lambda _: fake.sentence(nb_words=10) if fake.boolean() else None
    )


class ExtractionLineFactory(factory.Factory):
    """Factory for generating extraction line items."""

    class Meta:
        model = dict

    description = factory.Faker('catch_phrase')
    quantity = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    unit_price = factory.Faker('pydecimal', left_digits=5, right_digits=2, positive=True)
    amount = factory.LazyAttribute(
        lambda obj: str(Decimal(str(obj.quantity)) * Decimal(str(obj.unit_price)))
    )

    # Optional fields
    sku = factory.LazyAttribute(
        lambda _: f"SKU-{fake.random_int(10000, 99999)}" if fake.boolean() else None
    )
    product_code = factory.LazyAttribute(
        lambda _: f"PROD-{fake.random_int(1000, 9999)}" if fake.boolean() else None
    )
    discount = factory.LazyAttribute(
        lambda _: Decimal(str(fake.random_int(0, 20))) / 100 if fake.boolean() else None
    )
    tax_rate = factory.LazyAttribute(
        lambda _: Decimal(str(fake.random_int(0, 15))) / 100 if fake.boolean() else None
    )


class ExtractionDataFactory(factory.Factory):
    """Factory for generating complete extraction data."""

    class Meta:
        model = dict

    # Header information
    header = factory.SubFactory(ExtractionHeaderFactory)

    # Line items
    lines = factory.LazyAttribute(lambda _: [
        factory.build(dict, FACTORY_CLASS=ExtractionLineFactory)
        for _ in range(fake.random_int(1, 10))
    ])

    # Confidence scores
    confidence = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": fake.pyfloat(min_value=0.8, max_value=0.99),
            "invoice_no": fake.pyfloat(min_value=0.9, max_value=0.99),
            "invoice_date": fake.pyfloat(min_value=0.85, max_value=0.95),
            "due_date": fake.pyfloat(min_value=0.8, max_value=0.95),
            "total": fake.pyfloat(min_value=0.9, max_value=0.99),
            "overall": fake.pyfloat(min_value=0.85, max_value=0.95)
        },
        "lines": [
            fake.pyfloat(min_value=0.7, max_value=0.95)
            for _ in range(len(obj.lines))
        ],
        "overall": fake.pyfloat(min_value=0.8, max_value=0.95)
    })

    overall_confidence = factory.LazyAttribute(
        lambda obj: obj.confidence.get("overall", 0.85)
    )

    # Metadata
    metadata = factory.LazyAttribute(lambda _: {
        "file_path": f"/tmp/test_invoice_{fake.random_int(1000, 9999)}.pdf",
        "file_hash": fake.sha256(),
        "file_size": fake.random_int(1000, 50000),
        "pages_processed": fake.random_int(1, 5),
        "extracted_at": datetime.utcnow().isoformat(),
        "parser_version": "docling-2.60.1",
        "processing_time_ms": fake.random_int(500, 3000)
    })


class LowConfidenceExtractionFactory(ExtractionDataFactory):
    """Factory for generating low confidence extraction data."""

    confidence = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": fake.pyfloat(min_value=0.3, max_value=0.7),
            "invoice_no": fake.pyfloat(min_value=0.4, max_value=0.7),
            "invoice_date": fake.pyfloat(min_value=0.3, max_value=0.6),
            "due_date": fake.pyfloat(min_value=0.2, max_value=0.6),
            "total": fake.pyfloat(min_value=0.4, max_value=0.7),
            "overall": fake.pyfloat(min_value=0.3, max_value=0.6)
        },
        "lines": [
            fake.pyfloat(min_value=0.3, max_value=0.6)
            for _ in range(fake.random_int(1, 5))
        ],
        "overall": fake.pyfloat(min_value=0.4, max_value=0.65)
    })

    overall_confidence = factory.LazyAttribute(
        lambda obj: obj.confidence.get("overall", 0.5)
    )


class HighConfidenceExtractionFactory(ExtractionDataFactory):
    """Factory for generating high confidence extraction data."""

    confidence = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": fake.pyfloat(min_value=0.95, max_value=0.99),
            "invoice_no": fake.pyfloat(min_value=0.98, max_value=0.99),
            "invoice_date": fake.pyfloat(min_value=0.95, max_value=0.99),
            "due_date": fake.pyfloat(min_value=0.95, max_value=0.99),
            "total": fake.pyfloat(min_value=0.97, max_value=0.99),
            "overall": fake.pyfloat(min_value=0.96, max_value=0.99)
        },
        "lines": [
            fake.pyfloat(min_value=0.9, max_value=0.98)
            for _ in range(fake.random_int(1, 8))
        ],
        "overall": fake.pyfloat(min_value=0.95, max_value=0.98)
    })

    overall_confidence = factory.LazyAttribute(
        lambda obj: obj.confidence.get("overall", 0.96)
    )


class LargeInvoiceExtractionFactory(ExtractionDataFactory):
    """Factory for generating large invoice extraction data."""

    lines = factory.LazyAttribute(lambda _: [
        factory.build(dict, FACTORY_CLASS=ExtractionLineFactory)
        for _ in range(fake.random_int(20, 100))
    ])

    header = factory.SubFactory(ExtractionHeaderFactory,
        subtotal=factory.Faker('pydecimal', left_digits=6, right_digits=2, positive=True),
        total=factory.Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    )

    metadata = factory.LazyAttribute(lambda _: {
        "file_path": f"/tmp/large_invoice_{fake.random_int(1000, 9999)}.pdf",
        "file_hash": fake.sha256(),
        "file_size": fake.random_int(50000, 500000),
        "pages_processed": fake.random_int(5, 20),
        "extracted_at": datetime.utcnow().isoformat(),
        "parser_version": "docling-2.60.1",
        "processing_time_ms": fake.random_int(5000, 15000)
    })


class CorruptedExtractionFactory(ExtractionDataFactory):
    """Factory for generating corrupted/incomplete extraction data."""

    header = factory.LazyAttribute(lambda _: {
        # Missing required fields
        "vendor_name": "",  # Empty vendor name
        "invoice_no": None,  # Missing invoice number
        "invoice_date": "invalid-date",  # Invalid date format
        "total": -100.0,  # Negative amount
        "currency": "USD"
    })

    lines = factory.LazyAttribute(lambda _: [
        {
            "description": "",  # Empty description
            "quantity": 0,  # Zero quantity
            "unit_price": 0.0,  # Zero price
            "amount": 0.0  # Zero amount
        }
    ])

    confidence = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": 0.1,  # Very low confidence
            "invoice_no": 0.0,  # No confidence
            "invoice_date": 0.0,  # Invalid date
            "total": 0.05,  # Very low confidence
            "overall": 0.05
        },
        "lines": [0.1],  # Low confidence for lines
        "overall": 0.08  # Very low overall confidence
    })

    overall_confidence = 0.08