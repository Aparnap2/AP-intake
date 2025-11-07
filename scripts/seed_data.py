"""
Script to seed the database with sample data.
"""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, sync_engine
from app.models.reference import Vendor, PurchaseOrder, GoodsReceiptNote, POStatus
from app.models.invoice import Invoice, InvoiceStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_vendors(db: Session) -> None:
    """Create sample vendors."""
    vendors_data = [
        {
            "name": "Acme Corporation Inc.",
            "tax_id": "12-3456789",
            "currency": "USD",
            "email": "billing@acme.com",
            "phone": "+1-555-0101",
            "address": "123 Business St, Suite 100, New York, NY 10001",
            "payment_terms_days": "30",
            "credit_limit": "50000.00",
        },
        {
            "name": "Tech Solutions LLC",
            "tax_id": "98-7654321",
            "currency": "USD",
            "email": "accounts@techsolutions.com",
            "phone": "+1-555-0102",
            "address": "456 Innovation Ave, Palo Alto, CA 94301",
            "payment_terms_days": "45",
            "credit_limit": "75000.00",
        },
        {
            "name": "Global Supplies Ltd",
            "tax_id": "45-6789012",
            "currency": "USD",
            "email": "finance@globalsupplies.com",
            "phone": "+1-555-0103",
            "address": "789 Commerce Blvd, Chicago, IL 60601",
            "payment_terms_days": "60",
            "credit_limit": "100000.00",
        },
        {
            "name": "European Hardware GmbH",
            "tax_id": "EU-123456789",
            "currency": "EUR",
            "email": "rechnung@eurohardware.de",
            "phone": "+49-30-1234567",
            "address": "Friedrichstrasse 123, 10117 Berlin, Germany",
            "payment_terms_days": "30",
            "credit_limit": "25000.00",
        },
        {
            "name": "Asia Pacific Trading Co.",
            "tax_id": "SG-987654321",
            "currency": "SGD",
            "email": "accounts@apacific.sg",
            "phone": "+65-6234-5678",
            "address": "1 Raffles Place, #12-00, Singapore 048616",
            "payment_terms_days": "90",
            "credit_limit": "200000.00",
        },
    ]

    for vendor_data in vendors_data:
        # Check if vendor already exists
        existing = db.query(Vendor).filter(Vendor.tax_id == vendor_data["tax_id"]).first()
        if not existing:
            vendor = Vendor(**vendor_data)
            db.add(vendor)
            logger.info(f"Created vendor: {vendor.name}")
        else:
            logger.info(f"Vendor already exists: {existing.name}")

    db.commit()


def create_sample_purchase_orders(db: Session) -> None:
    """Create sample purchase orders."""
    vendors = db.query(Vendor).all()
    if not vendors:
        logger.warning("No vendors found, skipping PO creation")
        return

    pos_data = [
        {
            "vendor": vendors[0],  # Acme Corporation
            "po_no": "PO-2024-001",
            "lines_json": [
                {"description": "Office Supplies", "quantity": 10, "unit_price": 25.50, "amount": 255.00, "sku": "OFF-001"},
                {"description": "Computer Equipment", "quantity": 2, "unit_price": 1200.00, "amount": 2400.00, "sku": "TECH-002"},
                {"description": "Printer Paper", "quantity": 5, "unit_price": 45.00, "amount": 225.00, "sku": "SUP-003"},
            ],
            "total_amount": "2880.00",
            "currency": "USD",
            "order_date": datetime(2024, 1, 15),
            "expected_date": datetime(2024, 1, 30),
            "status": POStatus.SENT,
            "created_by": "john.doe@company.com",
        },
        {
            "vendor": vendors[1],  # Tech Solutions
            "po_no": "PO-2024-002",
            "lines_json": [
                {"description": "Software License", "quantity": 1, "unit_price": 500.00, "amount": 500.00, "sku": "LIC-001"},
                {"description": "Technical Support", "quantity": 12, "unit_price": 150.00, "amount": 1800.00, "sku": "SUP-001"},
                {"description": "Cloud Storage", "quantity": 1, "unit_price": 200.00, "amount": 200.00, "sku": "CLOUD-001"},
            ],
            "total_amount": "2500.00",
            "currency": "USD",
            "order_date": datetime(2024, 1, 20),
            "expected_date": datetime(2024, 2, 15),
            "status": POStatus.SENT,
            "created_by": "mary.smith@company.com",
        },
        {
            "vendor": vendors[2],  # Global Supplies
            "po_no": "PO-2024-003",
            "lines_json": [
                {"description": "Industrial Tools", "quantity": 15, "unit_price": 89.99, "amount": 1349.85, "sku": "TOOLS-001"},
                {"description": "Safety Equipment", "quantity": 20, "unit_price": 35.50, "amount": 710.00, "sku": "SAFE-001"},
            ],
            "total_amount": "2059.85",
            "currency": "USD",
            "order_date": datetime(2024, 2, 1),
            "expected_date": datetime(2024, 2, 28),
            "status": POStatus.PARTIAL,
            "created_by": "bob.wilson@company.com",
        },
        {
            "vendor": vendors[3],  # European Hardware
            "po_no": "PO-2024-004",
            "lines_json": [
                {"description": "Precision Instruments", "quantity": 8, "unit_price": 450.00, "amount": 3600.00, "sku": "INST-001"},
                {"description": "Calibration Services", "quantity": 2, "unit_price": 750.00, "amount": 1500.00, "sku": "CAL-001"},
            ],
            "total_amount": "5100.00",
            "currency": "EUR",
            "order_date": datetime(2024, 2, 5),
            "expected_date": datetime(2024, 3, 15),
            "status": POStatus.SENT,
            "created_by": "alice.brown@company.com",
        },
        {
            "vendor": vendors[4],  # Asia Pacific Trading
            "po_no": "PO-2024-005",
            "lines_json": [
                {"description": "Electronic Components", "quantity": 100, "unit_price": 12.50, "amount": 1250.00, "sku": "ELEC-001"},
                {"description": "Circuit Boards", "quantity": 25, "unit_price": 45.00, "amount": 1125.00, "sku": "BOARD-001"},
            ],
            "total_amount": "2375.00",
            "currency": "SGD",
            "order_date": datetime(2024, 2, 10),
            "expected_date": datetime(2024, 3, 20),
            "status": POStatus.DRAFT,
            "created_by": "charlie.chen@company.com",
        },
    ]

    for po_data in pos_data:
        # Check if PO already exists
        existing = db.query(PurchaseOrder).filter(PurchaseOrder.po_no == po_data["po_no"]).first()
        if not existing:
            po = PurchaseOrder(
                po_no=po_data["po_no"],
                vendor_id=po_data["vendor"].id,
                lines_json=po_data["lines_json"],
                total_amount=po_data["total_amount"],
                currency=po_data["currency"],
                order_date=po_data["order_date"],
                expected_date=po_data["expected_date"],
                status=po_data["status"],
                created_by=po_data["created_by"],
            )
            db.add(po)
            logger.info(f"Created PO: {po.po_no}")
        else:
            logger.info(f"PO already exists: {existing.po_no}")

    db.commit()


def create_sample_grns(db: Session) -> None:
    """Create sample goods receipt notes."""
    pos = db.query(PurchaseOrder).all()
    if not pos:
        logger.warning("No POs found, skipping GRN creation")
        return

    # Create GRNs for only SENT and PARTIAL POs
    eligible_pos = [po for po in pos if po.status in [POStatus.SENT, POStatus.PARTIAL]]

    for i, po in enumerate(eligible_pos):
        # Check if GRN already exists - use full PO number to ensure uniqueness
        grn_no = f"GRN-{po.po_no.replace('PO-', '')}-001"
        logger.info(f"Processing PO: {po.po_no}, creating GRN: {grn_no}")
        existing = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.grn_no == grn_no).first()
        if not existing:
            # Create realistic GRN data
            if po.po_no == "PO-2024-001":  # Full delivery
                grn_lines = po.lines_json
                carrier = "FedEx"
                received_by = "warehouse.staff@company.com"
                received_date = datetime(2024, 1, 28, 14, 30)
            elif po.po_no == "PO-2024-002":  # Full delivery
                grn_lines = po.lines_json
                carrier = "UPS"
                received_by = "receiving.team@company.com"
                received_date = datetime(2024, 2, 12, 10, 15)
            elif po.po_no == "PO-2024-003":  # Partial delivery
                # Deliver only first item
                grn_lines = [po.lines_json[0]]
                carrier = "DHL Express"
                received_by = "logistics.supervisor@company.com"
                received_date = datetime(2024, 2, 18, 9, 45)
            elif po.po_no == "PO-2024-004":  # Full delivery
                grn_lines = po.lines_json
                carrier = "DB Schenker"
                received_by = "import.team@company.com"
                received_date = datetime(2024, 3, 8, 16, 20)
            else:
                grn_lines = po.lines_json
                carrier = "Local Carrier"
                received_by = "staff@company.com"
                received_date = datetime.now()

            grn = GoodsReceiptNote(
                grn_no=grn_no,
                po_id=po.id,
                lines_json=grn_lines,
                received_at=received_date,
                received_by=received_by,
                carrier=carrier,
                tracking_no=f"TRACK-{uuid4().hex[:12].upper()}",
            )
            db.add(grn)
            logger.info(f"Created GRN: {grn.grn_no} for PO: {po.po_no}")
        else:
            logger.info(f"GRN already exists: {existing.grn_no}")

    db.commit()


def main():
    """Main seeding function."""
    logger.info("Starting database seeding...")

    # Create all tables
    from app.db.session import Base
    Base.metadata.create_all(bind=sync_engine)

    db = SessionLocal()
    try:
        create_sample_vendors(db)
        create_sample_purchase_orders(db)
        create_sample_grns(db)
        logger.info("Database seeding completed successfully!")
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()