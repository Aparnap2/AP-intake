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


class DuplicateSeedInvoiceFactory(InvoiceFactory):
    """Factory for generating seed invoices for duplicate testing."""

    class Params:
        duplicate_type = "exact"
        base_invoice = None

    # Enhanced data for duplicate scenarios
    extracted_data = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": fake.company(),
            "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
            "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
            "due_date": fake.date_between().strftime("%Y-%m-%d"),
            "total": str(Decimal(fake.random_int(100, 10000)) / 100),
            "currency": "USD",
            "po_number": f"PO-{fake.random_int(10000, 99999)}",
            "payment_terms": random.choice(["NET 30", "NET 60", "NET 90"]),
        },
        "lines": [
            {
                "description": fake.catch_phrase(),
                "quantity": fake.random_int(1, 10),
                "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                "amount": str(Decimal(fake.random_int(100, 1000)) / 100),
                "sku": fake.ean(length=8),
                "tax_rate": str(Decimal(fake.random_int(0, 10)) / 100),
            }
            for _ in range(fake.random_int(1, 5))
        ],
        "footer": {
            "subtotal": str(Decimal(fake.random_int(100, 10000)) / 100),
            "tax_amount": str(Decimal(fake.random_int(10, 1000)) / 100),
            "total_amount": str(Decimal(fake.random_int(100, 10000)) / 100),
        }
    })

    confidence_score = factory.Faker('pyfloat', min_value=0.8, max_value=0.95)
    processing_errors = []
    status = InvoiceStatus.READY
    workflow_state = 'validated'


class ExactDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating exact duplicates."""

    class Params:
        duplicate_type = "exact"

    @classmethod
    def create_from_base(cls, base_invoice):
        """Create exact duplicate from base invoice."""
        return cls(
            file_name=f"copy_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/copy_{base_invoice.file_name}",
            file_hash=base_invoice.file_hash,  # Same hash
            file_size=base_invoice.file_size,
            vendor_id=base_invoice.vendor_id,
            extracted_data=base_invoice.extracted_data,  # Identical data
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class AmountShiftDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating duplicates with amount variations."""

    class Params:
        duplicate_type = "amount_shift"
        amount_variation = 0.05  # 5% variation by default

    @classmethod
    def create_from_base(cls, base_invoice, amount_variation=None):
        """Create duplicate with amount shift from base invoice."""
        if amount_variation is None:
            amount_variation = random.uniform(-0.05, 0.05)

        # Modify extracted data with amount variation
        modified_data = base_invoice.extracted_data.copy()

        # Vary line item amounts
        if "lines" in modified_data:
            for line in modified_data["lines"]:
                original_amount = Decimal(line["amount"])
                variation = original_amount * Decimal(str(amount_variation))
                line["amount"] = str(original_amount + variation)

                # Also vary unit price proportionally
                if "unit_price" in line:
                    original_price = Decimal(line["unit_price"])
                    price_variation = original_price * Decimal(str(amount_variation))
                    line["unit_price"] = str(original_price + price_variation)

        # Vary total amounts
        if "header" in modified_data and "total" in modified_data["header"]:
            original_total = Decimal(modified_data["header"]["total"])
            total_variation = original_total * Decimal(str(amount_variation))
            modified_data["header"]["total"] = str(original_total + total_variation)

        if "footer" in modified_data:
            for field in ["subtotal", "tax_amount", "total_amount"]:
                if field in modified_data["footer"]:
                    original_amount = Decimal(modified_data["footer"][field])
                    variation = original_amount * Decimal(str(amount_variation))
                    modified_data["footer"][field] = str(original_amount + variation)

        return cls(
            file_name=f"amount_shift_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/amount_shift_{base_invoice.file_name}",
            vendor_id=base_invoice.vendor_id,
            extracted_data=modified_data,
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class DateShiftDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating duplicates with date variations."""

    class Params:
        duplicate_type = "date_shift"
        date_shift_days = 3  # 3 days shift by default

    @classmethod
    def create_from_base(cls, base_invoice, date_shift_days=None):
        """Create duplicate with date shift from base invoice."""
        if date_shift_days is None:
            date_shift_days = random.randint(-7, 7)

        # Modify extracted data with date variation
        modified_data = base_invoice.extracted_data.copy()

        if "header" in modified_data:
            # Shift invoice date
            if "invoice_date" in modified_data["header"]:
                original_date = datetime.strptime(modified_data["header"]["invoice_date"], "%Y-%m-%d")
                shifted_date = original_date + timedelta(days=date_shift_days)
                modified_data["header"]["invoice_date"] = shifted_date.strftime("%Y-%m-%d")

            # Shift due date by same amount
            if "due_date" in modified_data["header"]:
                original_due_date = datetime.strptime(modified_data["header"]["due_date"], "%Y-%m-%d")
                shifted_due_date = original_due_date + timedelta(days=date_shift_days)
                modified_data["header"]["due_date"] = shifted_due_date.strftime("%Y-%m-%d")

        return cls(
            file_name=f"date_shift_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/date_shift_{base_invoice.file_name}",
            vendor_id=base_invoice.vendor_id,
            extracted_data=modified_data,
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class FormatChangeDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating duplicates with format variations."""

    class Params:
        duplicate_type = "format_change"

    @classmethod
    def create_from_base(cls, base_invoice):
        """Create duplicate with format changes from base invoice."""
        modified_data = base_invoice.extracted_data.copy()

        if "lines" in modified_data:
            # Reorder line items
            lines = modified_data["lines"].copy()
            random.shuffle(lines)
            modified_data["lines"] = lines

            # Add format variations to descriptions
            for line in modified_data["lines"]:
                if "description" in line:
                    original_desc = line["description"]
                    variations = [
                        original_desc,
                        f"Rev: {original_desc}",
                        f"{original_desc} (Updated)",
                        f"{original_desc} - Revised",
                    ]
                    line["description"] = random.choice(variations)

        # Add formatting variations to vendor name
        if "header" in modified_data and "vendor_name" in modified_data["header"]:
            vendor_variations = [
                modified_data["header"]["vendor_name"],
                modified_data["header"]["vendor_name"].upper(),
                modified_data["header"]["vendor_name"].lower(),
                f"{modified_data['header']['vendor_name']} Inc.",
                f"{modified_data['header']['vendor_name']} LLC",
            ]
            modified_data["header"]["vendor_name"] = random.choice(vendor_variations)

        return cls(
            file_name=f"format_change_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/format_change_{base_invoice.file_name}",
            vendor_id=base_invoice.vendor_id,
            extracted_data=modified_data,
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class VendorVariationDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating duplicates with vendor name variations."""

    class Params:
        duplicate_type = "vendor_variation"

    @classmethod
    def create_from_base(cls, base_invoice):
        """Create duplicate with vendor name variation from base invoice."""
        modified_data = base_invoice.extracted_data.copy()

        if "header" in modified_data and "vendor_name" in modified_data["header"]:
            original_vendor = modified_data["header"]["vendor_name"]

            # Generate vendor name variations
            vendor_variations = [
                f"{original_vendor} Inc.",
                f"{original_vendor} LLC",
                f"{original_vendor} Corp.",
                f"The {original_vendor} Company",
                f"{original_vendor} Services",
                original_vendor.replace("Inc.", "").replace("LLC", "").strip(),
                f"{original_vendor} dba {fake.company()}",
            ]

            modified_data["header"]["vendor_name"] = random.choice(vendor_variations)

        return cls(
            file_name=f"vendor_variation_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/vendor_variation_{base_invoice.file_name}",
            vendor_id=base_invoice.vendor_id,  # Keep same vendor_id to simulate same vendor
            extracted_data=modified_data,
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class InvoiceNumberVariationDuplicateFactory(DuplicateSeedInvoiceFactory):
    """Factory for generating duplicates with invoice number variations."""

    class Params:
        duplicate_type = "invoice_number_variation"

    @classmethod
    def create_from_base(cls, base_invoice):
        """Create duplicate with invoice number variation from base invoice."""
        modified_data = base_invoice.extracted_data.copy()

        if "header" in modified_data and "invoice_no" in modified_data["header"]:
            original_number = modified_data["header"]["invoice_no"]

            # Generate invoice number variations
            number_variations = [
                f"{original_number}-R",
                f"R-{original_number}",
                f"{original_number}REV",
                f"{original_number} Revision",
                f"{original_number[:-1]}{random.randint(0, 9)}" if len(original_number) > 1 else original_number,
                f"{original_number}/{random.randint(1, 9)}",
                f"CORR-{original_number}",
            ]

            modified_data["header"]["invoice_no"] = random.choice(number_variations)

        return cls(
            file_name=f"inv_num_variation_{base_invoice.file_name}",
            file_path=f"/tmp/invoices/inv_num_variation_{base_invoice.file_name}",
            vendor_id=base_invoice.vendor_id,
            extracted_data=modified_data,
            status=base_invoice.status,
            workflow_state=base_invoice.workflow_state,
        )


class SeedExceptionInvoiceFactory(InvoiceFactory):
    """Factory for generating seed invoices for exception testing."""

    class Params:
        exception_type = "math_error"
        severity = "medium"

    # Enhanced data for exception scenarios
    extracted_data = factory.LazyAttribute(lambda obj: {
        "header": {
            "vendor_name": fake.company(),
            "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
            "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
            "due_date": fake.date_between().strftime("%Y-%m-%d"),
            "total": str(Decimal(fake.random_int(100, 10000)) / 100),
            "currency": "USD",
            "po_number": f"PO-{fake.random_int(10000, 99999)}",
            "payment_terms": random.choice(["NET 30", "NET 60", "NET 90"]),
            "vendor_tax_id": fake.ssn(),
            "approval_code": fake.bothify(text="APR-###"),
        },
        "lines": [
            {
                "description": fake.catch_phrase(),
                "quantity": fake.random_int(1, 10),
                "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                "amount": str(Decimal(fake.random_int(100, 1000)) / 100),
                "sku": fake.ean(length=8),
                "tax_rate": str(Decimal(fake.random_int(0, 10)) / 100),
                "gl_account": fake.bothify(text="####-##"),
            }
            for _ in range(fake.random_int(1, 5))
        ],
        "footer": {
            "subtotal": str(Decimal(fake.random_int(100, 10000)) / 100),
            "tax_amount": str(Decimal(fake.random_int(10, 1000)) / 100),
            "total_amount": str(Decimal(fake.random_int(100, 10000)) / 100),
            "payment_instructions": fake.bs(),
        }
    })

    @classmethod
    def create_with_math_error(cls, base_invoice=None):
        """Create invoice with math calculation error."""
        data = {
            "header": {
                "vendor_name": fake.company(),
                "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
                "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
                "due_date": fake.date_between().strftime("%Y-%m-%d"),
                "total": str(Decimal(fake.random_int(100, 10000)) / 100),
                "currency": "USD",
            },
            "lines": [
                {
                    "description": fake.catch_phrase(),
                    "quantity": 2,
                    "unit_price": "100.00",
                    "amount": "200.00",  # Correct calculation
                },
                {
                    "description": fake.catch_phrase(),
                    "quantity": 3,
                    "unit_price": "50.00",
                    "amount": "150.00",  # Correct calculation
                }
            ],
            "footer": {
                "subtotal": "350.00",  # Correct: 200 + 150
                "tax_amount": "35.00",  # 10% tax
                "total_amount": "370.00",  # Incorrect: should be 385.00
            }
        }

        return cls(
            extracted_data=data,
            status=InvoiceStatus.REVIEW,
            workflow_state="validation_failed",
            processing_errors=[
                {
                    "step": "validation",
                    "error": "Math calculation error: total amount mismatch",
                    "severity": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {
                        "calculated_total": "385.00",
                        "provided_total": "370.00",
                        "difference": "15.00"
                    }
                }
            ]
        )

    @classmethod
    def create_with_missing_fields(cls, missing_fields=None):
        """Create invoice with missing required fields."""
        if missing_fields is None:
            missing_fields = random.choice([
                ["po_number"],
                ["vendor_tax_id"],
                ["approval_code"],
                ["po_number", "approval_code"],
                ["vendor_tax_id", "gl_account"]
            ])

        data = {
            "header": {
                "vendor_name": fake.company(),
                "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
                "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
                "due_date": fake.date_between().strftime("%Y-%m-%d"),
                "total": str(Decimal(fake.random_int(100, 10000)) / 100),
                "currency": "USD",
            },
            "lines": [
                {
                    "description": fake.catch_phrase(),
                    "quantity": fake.random_int(1, 10),
                    "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                    "amount": str(Decimal(fake.random_int(100, 1000)) / 100),
                }
            ]
        }

        # Conditionally include/exclude fields
        if "po_number" not in missing_fields:
            data["header"]["po_number"] = f"PO-{fake.random_int(10000, 99999)}"
        if "vendor_tax_id" not in missing_fields:
            data["header"]["vendor_tax_id"] = fake.ssn()
        if "approval_code" not in missing_fields:
            data["header"]["approval_code"] = fake.bothify(text="APR-###")

        return cls(
            extracted_data=data,
            status=InvoiceStatus.REVIEW,
            workflow_state="validation_failed",
            processing_errors=[
                {
                    "step": "validation",
                    "error": f"Missing required field: {field}",
                    "severity": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "field": field
                }
                for field in missing_fields
            ]
        )

    @classmethod
    def create_with_invalid_format(cls, invalid_formats=None):
        """Create invoice with invalid data formats."""
        if invalid_formats is None:
            invalid_formats = random.choice([
                {"field": "invoice_date", "value": "31/12/2023", "format": "should be YYYY-MM-DD"},
                {"field": "total", "value": "not-a-number", "format": "should be numeric"},
                {"field": "due_date", "value": "2023-99-99", "format": "invalid date"},
            ])

        data = {
            "header": {
                "vendor_name": fake.company(),
                "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
                "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
                "due_date": fake.date_between().strftime("%Y-%m-%d"),
                "total": str(Decimal(fake.random_int(100, 10000)) / 100),
                "currency": "USD",
            },
            "lines": [
                {
                    "description": fake.catch_phrase(),
                    "quantity": fake.random_int(1, 10),
                    "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                    "amount": str(Decimal(fake.random_int(100, 1000)) / 100),
                }
            ]
        }

        # Apply invalid formats
        for format_error in invalid_formats:
            field_name = format_error["field"]
            if field_name in data["header"]:
                data["header"][field_name] = format_error["value"]

        return cls(
            extracted_data=data,
            status=InvoiceStatus.REVIEW,
            workflow_state="validation_failed",
            processing_errors=[
                {
                    "step": "validation",
                    "error": f"Invalid format for {fmt['field']}: {fmt['format']}",
                    "severity": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "field": fmt["field"],
                    "invalid_value": fmt["value"],
                    "expected_format": fmt["format"]
                }
                for fmt in invalid_formats
            ]
        )

    @classmethod
    def create_with_business_rule_violation(cls, violation_type=None):
        """Create invoice with business rule violations."""
        if violation_type is None:
            violation_type = random.choice([
                "invoice_limit_exceeded",
                "unapproved_vendor",
                "missing_approval",
                "payment_terms_violation",
                "budget_exceeded"
            ])

        data = {
            "header": {
                "vendor_name": fake.company(),
                "invoice_no": f"INV-{fake.random_int(1000, 9999)}",
                "invoice_date": fake.date_between().strftime("%Y-%m-%d"),
                "due_date": fake.date_between().strftime("%Y-%m-%d"),
                "total": str(Decimal(fake.random_int(50000, 100000)) / 100),  # High amount
                "currency": "USD",
                "payment_terms": "NET 90",  # Extended terms
            },
            "lines": [
                {
                    "description": fake.catch_phrase(),
                    "quantity": fake.random_int(1, 10),
                    "unit_price": str(Decimal(fake.random_int(50, 500)) / 100),
                    "amount": str(Decimal(fake.random_int(100, 1000)) / 100),
                }
            ]
        }

        violation_messages = {
            "invoice_limit_exceeded": "Invoice amount exceeds authorized limit of $10,000",
            "unapproved_vendor": "Vendor is not in approved vendor list",
            "missing_approval": "Invoice requires managerial approval for amount",
            "payment_terms_violation": "Payment terms exceed maximum allowed 60 days",
            "budget_exceeded": "Invoice exceeds department budget allocation"
        }

        return cls(
            extracted_data=data,
            status=InvoiceStatus.REVIEW,
            workflow_state="validation_failed",
            processing_errors=[
                {
                    "step": "business_rules",
                    "error": violation_messages[violation_type],
                    "severity": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "violation_type": violation_type,
                    "rule violated": "Business policy violation"
                }
            ]
        )