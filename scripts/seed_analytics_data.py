"""
Script to seed sample analytics data for dashboard testing and demonstration.
"""

import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceExtraction, InvoiceStatus, Validation, Exception, StagedExport, ExportFormat, ExportStatus
from app.models.reference import Vendor


def generate_sample_date_range(days: int = 30) -> tuple[datetime, datetime]:
    """Generate a date range for sample data."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def create_sample_vendors(db: Session, count: int = 10) -> list[Vendor]:
    """Create sample vendors for testing."""
    vendors = []
    vendor_names = [
        "Acme Corp Manufacturing",
        "Global Supplies Inc",
        "Tech Solutions Ltd",
        "Office Depot",
        "Cleaning Services Co",
        "Industrial Equipment LLC",
        "Marketing Agency Pro",
        "Software Solutions Inc",
        "Facility Management Co",
        "Professional Services Ltd"
    ]

    for i in range(min(count, len(vendor_names))):
        # Check if vendor already exists
        existing_vendor = db.query(Vendor).filter(Vendor.name == vendor_names[i]).first()
        if existing_vendor:
            vendors.append(existing_vendor)
            continue

        vendor = Vendor(
            id=uuid.uuid4(),
            name=vendor_names[i],
            code=f"VEN-{1000 + i}",
            email=f"billing@{vendor_names[i].lower().replace(' ', '')}.com",
            phone=f"+1-555-{1000 + i:04d}",
            address=f"{100 + i} Business Ave, Suite {i + 1}, Commerce City, ST 12345",
            payment_terms=f"Net {30 + (i % 3) * 15}",
            tax_id=f"12-345678{i}",
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 365)),
            updated_at=datetime.utcnow()
        )
        db.add(vendor)
        vendors.append(vendor)

    db.commit()
    return vendors


def create_sample_invoices(db: Session, vendors: list[Vendor], count: int = 500) -> list[Invoice]:
    """Create sample invoices for analytics testing."""
    invoices = []
    start_date, end_date = generate_sample_date_range(30)

    status_weights = [
        (InvoiceStatus.RECEIVED, 0.05),
        (InvoiceStatus.PARSED, 0.10),
        (InvoiceStatus.VALIDATED, 0.15),
        (InvoiceStatus.EXCEPTION, 0.08),
        (InvoiceStatus.READY, 0.12),
        (InvoiceStatus.STAGED, 0.15),
        (InvoiceStatus.DONE, 0.35)
    ]

    for i in range(count):
        # Generate random creation date within range
        creation_date = start_date + timedelta(
            seconds=random.randint(0, int((end_date - start_date).total_seconds()))
        )

        # Random status based on weights
        status = random.choices([s for s, w in status_weights], weights=[w for s, w in status_weights])[0]

        # Calculate processing times based on status
        updated_at = creation_date
        if status != InvoiceStatus.RECEIVED:
            # Add processing time based on workflow complexity
            processing_hours = random.uniform(0.5, 24)
            updated_at = creation_date + timedelta(hours=processing_hours)

        invoice = Invoice(
            id=uuid.uuid4(),
            vendor_id=random.choice(vendors).id,
            file_url=f"/invoices/sample_invoice_{i}.pdf",
            file_hash=f"hash_{i}_{random.randint(1000, 9999)}",
            file_name=f"INV-{2024}-{i:05d}.pdf",
            file_size=f"{random.randint(100, 5000)}KB",
            status=status,
            workflow_state=status.value,
            workflow_data={
                "timestamps": {
                    "received": creation_date,
                    "parsed": creation_date + timedelta(hours=random.uniform(0.1, 2)) if status != InvoiceStatus.RECEIVED else None,
                    "validated": creation_date + timedelta(hours=random.uniform(2, 4)) if status not in [InvoiceStatus.RECEIVED, InvoiceStatus.PARSED] else None,
                    "staged": creation_date + timedelta(hours=random.uniform(4, 6)) if status in [InvoiceStatus.STAGED, InvoiceStatus.DONE] else None,
                    "done": creation_date + timedelta(hours=random.uniform(6, 8)) if status == InvoiceStatus.DONE else None
                }
            },
            created_at=creation_date,
            updated_at=updated_at
        )
        db.add(invoice)
        invoices.append(invoice)

    db.commit()
    return invoices


def create_sample_extractions(db: Session, invoices: list[Invoice]) -> list[InvoiceExtraction]:
    """Create sample extraction results."""
    extractions = []

    for invoice in invoices:
        if invoice.status == InvoiceStatus.RECEIVED:
            continue  # No extraction for received invoices

        # Generate realistic confidence scores
        base_confidence = random.uniform(0.65, 0.98)
        confidence_data = {
            "overall": base_confidence,
            "invoice_number": random.uniform(0.8, 0.99),
            "vendor_name": random.uniform(0.85, 0.99),
            "total_amount": random.uniform(0.75, 0.98),
            "invoice_date": random.uniform(0.8, 0.95),
            "due_date": random.uniform(0.7, 0.9),
            "line_items": random.uniform(0.6, 0.95)
        }

        # Add some random variation
        for key in confidence_data:
            if random.random() < 0.2:  # 20% chance of lower confidence
                confidence_data[key] *= random.uniform(0.7, 0.9)

        extraction = InvoiceExtraction(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            header_json={
                "invoice_number": f"INV-{2024}-{random.randint(10000, 99999)}",
                "vendor_name": "Sample Vendor Corp",
                "total_amount": round(random.uniform(100, 50000), 2),
                "invoice_date": (invoice.created_at - timedelta(days=random.randint(1, 30))).isoformat(),
                "due_date": (invoice.created_at + timedelta(days=random.randint(15, 60))).isoformat()
            },
            lines_json=[
                {
                    "line_number": i + 1,
                    "description": f"Sample product/service {i + 1}",
                    "quantity": random.randint(1, 10),
                    "unit_price": round(random.uniform(10, 1000), 2),
                    "total": round(random.uniform(10, 5000), 2)
                }
                for i in range(random.randint(1, 5))
            ],
            confidence_json=confidence_data,
            parser_version="v2.1.0",
            processing_time_ms=str(random.randint(500, 5000)),
            page_count=str(random.randint(1, 5)),
            created_at=invoice.created_at + timedelta(minutes=random.randint(1, 30))
        )
        db.add(extraction)
        extractions.append(extraction)

    db.commit()
    return extractions


def create_sample_validations(db: Session, invoices: list[Invoice]) -> list[Validation]:
    """Create sample validation results."""
    validations = []

    for invoice in invoices:
        if invoice.status in [InvoiceStatus.RECEIVED, InvoiceStatus.PARSED]:
            continue  # No validation for early stage invoices

        # Determine if validation passes (higher chance for processed invoices)
        pass_probability = 0.85 if invoice.status in [InvoiceStatus.DONE, InvoiceStatus.STAGED] else 0.7
        passed = random.random() < pass_probability

        # Generate validation check results
        checks = {
            "vendor_exists": {"passed": True, "message": "Vendor found in database"},
            "invoice_amount_valid": {"passed": random.random() < 0.9, "message": "Amount within expected range"},
            "invoice_date_valid": {"passed": random.random() < 0.95, "message": "Invoice date is valid"},
            "due_date_valid": {"passed": random.random() < 0.9, "message": "Due date is reasonable"},
            "duplicate_check": {"passed": random.random() < 0.98, "message": "No duplicate invoice found"}
        }

        # Overall validation passes if most checks pass
        passed_checks = sum(1 for check in checks.values() if check["passed"])
        passed = passed_checks >= 3

        validation = Validation(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            passed=passed,
            checks_json=checks,
            rules_version="v1.5.2",
            validator_version="v2.0.1",
            processing_time_ms=str(random.randint(200, 2000)),
            created_at=invoice.created_at + timedelta(minutes=random.randint(30, 60))
        )
        db.add(validation)
        validations.append(validation)

    db.commit()
    return validations


def create_sample_exceptions(db: Session, invoices: list[Invoice]) -> list[Exception]:
    """Create sample exceptions for testing."""
    exceptions = []
    exception_reasons = [
        "amount_mismatch",
        "vendor_not_found",
        "missing_fields",
        "duplicate_invoice",
        "invalid_date",
        "low_confidence",
        "validation_failed",
        "format_error"
    ]

    for invoice in invoices:
        # Create exceptions for invoices in exception status
        if invoice.status == InvoiceStatus.EXCEPTION:
            reason = random.choice(exception_reasons)
            exception = Exception(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                reason_code=reason,
                details_json={
                    "description": f"Exception details for {reason}",
                    "severity": random.choice(["low", "medium", "high"]),
                    "affected_fields": random.sample(["invoice_number", "amount", "vendor", "date"], random.randint(1, 3))
                },
                # Some exceptions are resolved
                resolved_by=random.choice(["john.doe", "jane.smith", None]) if random.random() < 0.6 else None,
                resolved_at=invoice.created_at + timedelta(hours=random.randint(1, 24)) if random.random() < 0.6 else None,
                resolution_notes="Exception resolved successfully" if random.random() < 0.6 else None,
                created_at=invoice.created_at + timedelta(hours=random.uniform(0.5, 2))
            )
            db.add(exception)
            exceptions.append(exception)

        # Also create some exceptions for other statuses
        elif random.random() < 0.1:  # 10% chance
            reason = random.choice(exception_reasons)
            exception = Exception(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                reason_code=reason,
                details_json={
                    "description": f"Exception details for {reason}",
                    "severity": random.choice(["low", "medium"]),
                    "affected_fields": random.sample(["invoice_number", "amount"], 1)
                },
                resolved_by=random.choice(["john.doe", "jane.smith"]) if random.random() < 0.8 else None,
                resolved_at=invoice.created_at + timedelta(hours=random.randint(2, 48)) if random.random() < 0.8 else None,
                created_at=invoice.created_at + timedelta(hours=random.uniform(1, 4))
            )
            db.add(exception)
            exceptions.append(exception)

    db.commit()
    return exceptions


def create_sample_exports(db: Session, invoices: list[Invoice]) -> list[StagedExport]:
    """Create sample export records."""
    exports = []

    for invoice in invoices:
        if invoice.status in [InvoiceStatus.STAGED, InvoiceStatus.DONE]:
            # Create export record
            export = StagedExport(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                payload_json={
                    "invoice_id": str(invoice.id),
                    "vendor_name": "Sample Vendor",
                    "amount": 1250.50,
                    "export_date": datetime.utcnow().isoformat()
                },
                format=random.choice([ExportFormat.CSV, ExportFormat.JSON]),
                status=random.choice([ExportStatus.PREPARED, ExportStatus.SENT, ExportStatus.FAILED]),
                destination="quickbooks",
                export_job_id=f"export_job_{random.randint(10000, 99999)}",
                file_name=f"export_{invoice.id}.csv",
                file_size=f"{random.randint(10, 100)}KB",
                error_message=None if random.random() < 0.9 else "Export failed: Connection timeout",
                created_at=invoice.created_at + timedelta(hours=random.uniform(8, 12))
            )
            db.add(export)
            exports.append(export)

    db.commit()
    return exports


def main():
    """Main function to seed analytics data."""
    print("Starting analytics data seeding...")

    db = SessionLocal()
    try:
        # Create sample data
        print("Creating sample vendors...")
        vendors = create_sample_vendors(db, 10)

        print("Creating sample invoices...")
        invoices = create_sample_invoices(db, vendors, 500)

        print("Creating sample extractions...")
        extractions = create_sample_extractions(db, invoices)

        print("Creating sample validations...")
        validations = create_sample_validations(db, invoices)

        print("Creating sample exceptions...")
        exceptions = create_sample_exceptions(db, invoices)

        print("Creating sample exports...")
        exports = create_sample_exports(db, invoices)

        print("\nData seeding completed successfully!")
        print(f"Created {len(vendors)} vendors")
        print(f"Created {len(invoices)} invoices")
        print(f"Created {len(extractions)} extractions")
        print(f"Created {len(validations)} validations")
        print(f"Created {len(exceptions)} exceptions")
        print(f"Created {len(exports)} exports")

        # Print some analytics
        total_invoices = len(invoices)
        done_invoices = len([inv for inv in invoices if inv.status == InvoiceStatus.DONE])
        exception_invoices = len([inv for inv in invoices if inv.status == InvoiceStatus.EXCEPTION])

        print(f"\nAnalytics Overview:")
        print(f"Total invoices: {total_invoices}")
        print(f"Completion rate: {done_invoices / total_invoices * 100:.1f}%")
        print(f"Exception rate: {exception_invoices / total_invoices * 100:.1f}%")

    except Exception as e:
        print(f"Error during data seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()