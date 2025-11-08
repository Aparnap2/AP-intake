#!/usr/bin/env python3
"""
Test script to verify the upload fix works by testing the model creation.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.db.session import get_db_session
from app.models.invoice import Invoice, InvoiceStatus
import uuid


async def test_invoice_creation():
    """Test creating an invoice with nullable vendor_id."""
    print("Testing invoice creation with nullable vendor_id...")

    # Get a database session
    async with get_db_session() as db:
        try:
            # Create an invoice with vendor_id=None (simulating the upload process)
            invoice = Invoice(
                vendor_id=None,  # This should work now
                file_url="/test/path/invoice.pdf",
                file_hash="test_hash_12345",
                file_name="test_invoice.pdf",
                file_size="1.5MB",
                status=InvoiceStatus.RECEIVED,
                workflow_state="uploaded",
            )

            # Add to database
            db.add(invoice)
            await db.commit()
            await db.refresh(invoice)

            print(f"✅ Successfully created invoice: {invoice.id}")
            print(f"   Vendor ID: {invoice.vendor_id}")
            print(f"   Status: {invoice.status}")

            # Clean up
            await db.delete(invoice)
            await db.commit()
            print("✅ Cleaned up test invoice")

            return True

        except Exception as e:
            print(f"❌ Error creating invoice: {e}")
            return False


async def main():
    """Main test function."""
    print("🔧 Testing upload fix for AP Intake system")
    print("=" * 50)

    success = await test_invoice_creation()

    if success:
        print("\n✅ All tests passed! The upload fix should work.")
    else:
        print("\n❌ Tests failed. The upload fix needs more work.")

    return success


if __name__ == "__main__":
    asyncio.run(main())