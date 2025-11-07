"""
Celery tasks for invoice processing.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from celery import Task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.invoice import Invoice, InvoiceExtraction, Validation, InvoiceStatus
from app.services.storage_service import StorageService
from app.workflows.invoice_processor import InvoiceProcessor
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    def __init__(self):
        self.db = None

    def on_success(self, retval, task_id, args, kwargs):
        """Cleanup after successful task completion."""
        if self.db:
            self.db.close()
            self.db = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Cleanup after task failure."""
        if self.db:
            self.db.close()
            self.db = None
        logger.error(f"Task {task_id} failed: {exc}")

    def get_db(self) -> Session:
        """Get database session for this task."""
        if not self.db:
            self.db = SessionLocal()
        return self.db


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def process_invoice_task(
    self, invoice_id: str, file_path: str, file_hash: str, **kwargs
) -> Dict[str, Any]:
    """Process an invoice through the complete workflow."""
    logger.info(f"Processing invoice {invoice_id} (task: {self.request.id})")

    try:
        # Get database session
        db = self.get_db()

        # Update invoice status to processing
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        invoice.status = InvoiceStatus.PARSED
        invoice.workflow_state = "processing"
        db.commit()

        # Initialize invoice processor
        processor = InvoiceProcessor()

        # Process the invoice (run async function in event loop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                processor.process_invoice(
                    invoice_id=invoice_id,
                    file_path=file_path,
                    file_hash=file_hash,
                    **kwargs
                )
            )
        finally:
            loop.close()

        # Update database with results
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_update_invoice_database(db, invoice, result))
        finally:
            loop.close()

        logger.info(f"Successfully processed invoice {invoice_id}")
        return {
            "invoice_id": invoice_id,
            "status": result.get("status"),
            "workflow_state": result.get("current_step"),
            "requires_human_review": result.get("requires_human_review", False),
            "processed_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Failed to process invoice {invoice_id}: {exc}")

        # Update invoice status on failure
        try:
            db = self.get_db()
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                invoice.status = InvoiceStatus.EXCEPTION
                invoice.workflow_state = "processing_failed"
                db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to update invoice status: {db_exc}")

        # Retry task if possible
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying invoice processing {invoice_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            raise exc


@celery_app.task(bind=True, base=DatabaseTask, max_retries=2, default_retry_delay=30)
def validate_invoice_task(self, invoice_id: str, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate extracted invoice data."""
    logger.info(f"Validating invoice {invoice_id} (task: {self.request.id})")

    try:
        from app.services.validation_service import ValidationService

        # Get database session
        db = self.get_db()

        # Initialize validation service
        validation_service = ValidationService()

        # Run validation (run async function in event loop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            validation_result = loop.run_until_complete(
                validation_service.validate_invoice(
                    extraction_result, invoice_id=invoice_id
                )
            )
        finally:
            loop.close()

        # Update invoice status
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            if validation_result.get("passed", False):
                invoice.status = InvoiceStatus.VALIDATED
                invoice.workflow_state = "validation_passed"
            else:
                invoice.status = InvoiceStatus.EXCEPTION
                invoice.workflow_state = "validation_failed"

            # Create validation record
            validation = Validation(
                invoice_id=invoice_id,
                passed=validation_result.get("passed", False),
                checks_json=validation_result.get("checks", {}),
                rules_version=validation_result.get("metadata", {}).get("rules_version", "1.0.0"),
                validator_version="1.0.0",
            )
            db.add(validation)

            # Create exception record if validation failed
            if not validation_result.get("passed", False):
                from app.models.invoice import Exception as InvoiceException
                for error in validation_result.get("errors", []):
                    exception = InvoiceException(
                        invoice_id=invoice_id,
                        reason_code=error.get("code", "VALIDATION_ERROR"),
                        details_json=error,
                    )
                    db.add(exception)

            db.commit()

        logger.info(f"Validation completed for invoice {invoice_id}: {validation_result.get('passed')}")
        return {
            "invoice_id": invoice_id,
            "validation_passed": validation_result.get("passed", False),
            "errors_count": len(validation_result.get("errors", [])),
            "warnings_count": len(validation_result.get("warnings", [])),
            "validated_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Failed to validate invoice {invoice_id}: {exc}")

        # Update invoice status on failure
        try:
            db = self.get_db()
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                invoice.status = InvoiceStatus.EXCEPTION
                invoice.workflow_state = "validation_failed"
                db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to update invoice status: {db_exc}")

        # Retry task if possible
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        else:
            raise exc


@celery_app.task(bind=True, base=DatabaseTask, max_retries=2, default_retry_delay=30)
def export_invoice_task(
    self, invoice_id: str, export_format: str = "json", destination: str = "default"
) -> Dict[str, Any]:
    """Export processed invoice data."""
    logger.info(f"Exporting invoice {invoice_id} as {export_format} (task: {self.request.id})")

    try:
        from app.services.export_service import ExportService

        # Get database session
        db = self.get_db()

        # Get invoice data
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get latest extraction
        extraction = db.query(InvoiceExtraction).filter(
            InvoiceExtraction.invoice_id == invoice_id
        ).order_by(InvoiceExtraction.created_at.desc()).first()

        if not extraction:
            raise ValueError(f"No extraction found for invoice {invoice_id}")

        # Prepare invoice data for export
        invoice_data = {
            "header": extraction.header_json,
            "lines": extraction.lines_json,
            "metadata": {
                "invoice_id": invoice_id,
                "vendor_id": str(invoice.vendor_id),
                "processed_at": invoice.updated_at.isoformat(),
                "confidence": extraction.confidence_json,
            }
        }

        # Initialize export service
        export_service = ExportService()

        # Generate export content (run async functions in event loop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if export_format.lower() == "csv":
                export_content = loop.run_until_complete(
                    export_service.export_to_csv(invoice_data)
                )
                content_type = "text/csv"
            else:
                export_content = loop.run_until_complete(
                    export_service.export_to_json(invoice_data)
                )
                content_type = "application/json"

            # Store export content
            storage_service = StorageService()
            export_filename = loop.run_until_complete(
                export_service.generate_export_filename(
                    invoice_id, export_format, datetime.utcnow()
                )
            )

            # Store export file
            storage_info = loop.run_until_complete(
                storage_service.store_file(
                    export_content.encode("utf-8"),
                    export_filename,
                    content_type=content_type
                )
            )
        finally:
            loop.close()

        # Create export record
        from app.models.invoice import StagedExport, ExportFormat, ExportStatus
        staged_export = StagedExport(
            invoice_id=invoice_id,
            payload_json=invoice_data,
            format=ExportFormat[export_format.upper()],
            status=ExportStatus.PREPARED,
            destination=destination,
            file_name=export_filename,
            file_size=str(len(export_content)),
        )
        db.add(staged_export)

        # Update invoice status
        invoice.status = InvoiceStatus.STAGED
        invoice.workflow_state = "export_staged"
        db.commit()

        logger.info(f"Successfully exported invoice {invoice_id} to {export_filename}")
        return {
            "invoice_id": invoice_id,
            "export_format": export_format,
            "file_name": export_filename,
            "file_size": len(export_content),
            "storage_url": storage_info.get("url"),
            "exported_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Failed to export invoice {invoice_id}: {exc}")

        # Update invoice status on failure
        try:
            db = self.get_db()
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                invoice.status = InvoiceStatus.EXCEPTION
                invoice.workflow_state = "export_failed"
                db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to update invoice status: {db_exc}")

        # Retry task if possible
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        else:
            raise exc


def _update_invoice_database(
    db: Session, invoice: Invoice, result: Dict[str, Any]
) -> None:
    """Update invoice database with processing results."""
    try:
        # Update invoice status and workflow state
        invoice.status = InvoiceStatus[result.get("status", "RECEIVED").upper()]
        invoice.workflow_state = result.get("current_step", "unknown")
        invoice.workflow_data = result

        # Create extraction record
        if result.get("extraction_result"):
            extraction = InvoiceExtraction(
                invoice_id=invoice.id,
                header_json=result["extraction_result"].get("header", {}),
                lines_json=result["extraction_result"].get("lines", []),
                confidence_json=result["extraction_result"].get("confidence", {}),
                parser_version="docling-0.1.0",
                processing_time_ms=str(1000),  # Placeholder
                page_count=str(1),  # Placeholder
            )
            db.add(extraction)

        db.commit()
        logger.info(f"Updated database for invoice {invoice.id}")

    except Exception as e:
        logger.error(f"Failed to update database for invoice {invoice.id}: {e}")
        db.rollback()
        raise