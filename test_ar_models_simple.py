#!/usr/bin/env python3
"""
Simple test script to verify AR models work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

# Test imports and basic functionality
try:
    from app.models.ar_invoice import Customer, ARInvoice, PaymentStatus, CollectionPriority
    print("✓ Successfully imported AR models")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test Customer creation
try:
    customer = Customer(
        name="Test Customer",
        currency="USD",
        credit_limit=Decimal("10000.00"),
        payment_terms_days="30",
        active=True
    )
    print(f"✓ Customer created: {customer.name}")
except Exception as e:
    print(f"✗ Customer creation failed: {e}")
    sys.exit(1)

# Test AR Invoice creation
try:
    ar_invoice = ARInvoice(
        customer_id=uuid4(),
        invoice_number="AR-001",
        total_amount=Decimal("1000.00"),
        currency="USD",
        invoice_date=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=30),
        subtotal=Decimal("909.09"),
        tax_amount=Decimal("90.91"),
        status=PaymentStatus.PENDING,
        collection_priority=CollectionPriority.MEDIUM
    )
    print(f"✓ AR Invoice created: {ar_invoice.invoice_number}")
    print(f"  - Status: {ar_invoice.status}")
    print(f"  - Collection Priority: {ar_invoice.collection_priority}")
    print(f"  - Outstanding Amount: {ar_invoice.outstanding_amount}")
except Exception as e:
    print(f"✗ AR Invoice creation failed: {e}")
    sys.exit(1)

# Test AR Invoice methods
try:
    print(f"✓ Is overdue: {ar_invoice.is_overdue()}")
    print(f"✓ Days overdue: {ar_invoice.days_overdue()}")

    # Test early payment discount
    ar_invoice.early_payment_discount_percent = Decimal("2.0")
    discount = ar_invoice.calculate_early_payment_discount()
    print(f"✓ Early payment discount: {discount}")
except Exception as e:
    print(f"✗ AR Invoice methods failed: {e}")
    sys.exit(1)

print("\n🎉 All AR model tests passed!")