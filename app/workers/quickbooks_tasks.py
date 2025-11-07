"""
Celery tasks for QuickBooks integration.

This module provides background tasks for:
- Invoice export to QuickBooks
- Batch export processing
- Webhook processing
- Token refresh
- Error handling and retries
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.quickbooks import QuickBooksConnection, QuickBooksExport, QuickBooksConnectionStatus
from app.models.invoice import Invoice, InvoiceExtraction
from app.services.quickbooks_service import QuickBooksService, QuickBooksServiceException
from app.core.exceptions import ExportException

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def export_invoice_to_quickbooks(
    self,
    invoice_id: str,
    user_id: str,
    dry_run: bool = False,
    connection_id: Optional[str] = None
):
    """
    Export an invoice to QuickBooks in the background.

    Args:
        invoice_id: UUID of the invoice to export
        user_id: UUID of the user who owns the invoice
        dry_run: If True, validate without creating
        connection_id: Optional specific connection ID to use
    """
    task_id = self.request.id
    logger.info(f"Starting QuickBooks export task {task_id} for invoice {invoice_id}")

    db = SessionLocal()
    try:
        # Get or validate connection
        if connection_id:
            connection = db.query(QuickBooksConnection).filter(
                QuickBooksConnection.id == uuid.UUID(connection_id),
                QuickBooksConnection.status == QuickBooksConnectionStatus.CONNECTED
            ).first()
        else:
            connection = db.query(QuickBooksConnection).filter(
                QuickBooksConnection.user_id == uuid.UUID(user_id),
                QuickBooksConnection.status == QuickBooksConnectionStatus.CONNECTED
            ).first()

        if not connection:
            raise ExportException("No active QuickBooks connection found")

        # Check if token is expired and refresh if needed
        if connection.is_token_expired:
            try:
                async def refresh_token():
                    async with QuickBooksService() as qb_service:
                        return await qb_service.refresh_access_token(
                            connection.refresh_token,
                            connection.realm_id
                        )

                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    token_response = loop.run_until_complete(refresh_token())
                finally:
                    loop.close()

                # Update connection with new tokens
                connection.access_token = token_response["access_token"]
                connection.refresh_token = token_response["refresh_token"]
                connection.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=token_response["expires_in"]
                )
                db.commit()

            except Exception as e:
                logger.error(f"Failed to refresh QuickBooks token: {str(e)}")
                connection.status = QuickBooksConnectionStatus.EXPIRED
                connection.last_error = f"Token refresh failed: {str(e)}"
                db.commit()
                raise ExportException("QuickBooks token expired and refresh failed")

        # Get invoice data
        invoice_uuid = uuid.UUID(invoice_id)
        invoice = db.query(Invoice).filter(Invoice.id == invoice_uuid).first()

        if not invoice:
            raise ExportException(f"Invoice {invoice_id} not found")

        extraction = db.query(InvoiceExtraction).filter(
            InvoiceExtraction.invoice_id == invoice_uuid
        ).order_by(InvoiceExtraction.created_at.desc()).first()

        if not extraction:
            raise ExportException(f"No extraction found for invoice {invoice_id}")

        # Prepare invoice data for QuickBooks
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

        # Create export record
        export_record = QuickBooksExport(
            connection_id=connection.id,
            invoice_id=invoice_uuid,
            export_type="bill",
            status="processing",
            dry_run=dry_run,
            request_payload=invoice_data
        )
        db.add(export_record)
        db.commit()
        db.refresh(export_record)

        # Export to QuickBooks
        async def export_to_qb():
            async with QuickBooksService() as qb_service:
                return await qb_service.create_bill(
                    connection.access_token,
                    connection.realm_id,
                    invoice_data,
                    dry_run
                )

        start_time = datetime.utcnow()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(export_to_qb())
        finally:
            loop.close()
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Update export record
        export_record.quickbooks_bill_id = result.get("Id") if not dry_run else None
        export_record.status = "success" if result.get("Bill") or dry_run else "failed"
        export_record.response_payload = result
        export_record.processing_time_ms = str(int(processing_time))
        export_record.last_sync_at = datetime.utcnow()
        db.commit()

        logger.info(f"QuickBooks export task {task_id} completed successfully for invoice {invoice_id}")
        return {
            "task_id": task_id,
            "invoice_id": invoice_id,
            "export_id": str(export_record.id),
            "bill_id": result.get("Id"),
            "status": export_record.status,
            "dry_run": dry_run
        }

    except ExportException as e:
        logger.error(f"Export task {task_id} failed: {str(e)}")

        # Update export record if it exists
        if 'export_record' in locals():
            export_record.status = "failed"
            export_record.error_message = str(e)
            export_record.retry_count = str(self.request.retries)
            export_record.next_retry_at = datetime.utcnow() + timedelta(minutes=5 * (self.request.retries + 1))
            db.commit()

        # Retry if available
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying export task {task_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))

        return {
            "task_id": task_id,
            "invoice_id": invoice_id,
            "status": "failed",
            "error": str(e),
            "retries_exhausted": True
        }

    except Exception as e:
        logger.error(f"Unexpected error in export task {task_id}: {str(e)}")

        # Update export record if it exists
        if 'export_record' in locals():
            export_record.status = "failed"
            export_record.error_message = f"Unexpected error: {str(e)}"
            export_record.retry_count = str(self.request.retries)
            db.commit()

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying export task {task_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))

        return {
            "task_id": task_id,
            "invoice_id": invoice_id,
            "status": "failed",
            "error": f"Unexpected error: {str(e)}",
            "retries_exhausted": True
        }

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def batch_export_invoices_to_quickbooks(
    self,
    invoice_ids: List[str],
    user_id: str,
    dry_run: bool = False,
    connection_id: Optional[str] = None
):
    """
    Export multiple invoices to QuickBooks in a batch.

    Args:
        invoice_ids: List of invoice UUIDs to export
        user_id: UUID of the user who owns the invoices
        dry_run: If True, validate without creating
        connection_id: Optional specific connection ID to use
    """
    task_id = self.request.id
    logger.info(f"Starting QuickBooks batch export task {task_id} for {len(invoice_ids)} invoices")

    db = SessionLocal()
    try:
        # Get connection
        if connection_id:
            connection = db.query(QuickBooksConnection).filter(
                QuickBooksConnection.id == uuid.UUID(connection_id),
                QuickBooksConnection.status == QuickBooksConnectionStatus.CONNECTED
            ).first()
        else:
            connection = db.query(QuickBooksConnection).filter(
                QuickBooksConnection.user_id == uuid.UUID(user_id),
                QuickBooksConnection.status == QuickBooksConnectionStatus.CONNECTED
            ).first()

        if not connection:
            raise ExportException("No active QuickBooks connection found")

        # Check if token is expired and refresh if needed
        if connection.is_token_expired:
            async def refresh_token():
                async with QuickBooksService() as qb_service:
                    return await qb_service.refresh_access_token(
                        connection.refresh_token,
                        connection.realm_id
                    )

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                token_response = loop.run_until_complete(refresh_token())
            finally:
                loop.close()

            # Update connection with new tokens
            connection.access_token = token_response["access_token"]
            connection.refresh_token = token_response["refresh_token"]
            connection.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_response["expires_in"]
            )
            db.commit()

        # Get invoice data for all invoices
        invoices_data = []
        valid_invoice_ids = []

        for invoice_id in invoice_ids:
            try:
                invoice_uuid = uuid.UUID(invoice_id)
                invoice = db.query(Invoice).filter(Invoice.id == invoice_uuid).first()

                if not invoice:
                    logger.warning(f"Invoice {invoice_id} not found, skipping")
                    continue

                extraction = db.query(InvoiceExtraction).filter(
                    InvoiceExtraction.invoice_id == invoice_uuid
                ).order_by(InvoiceExtraction.created_at.desc()).first()

                if not extraction:
                    logger.warning(f"No extraction found for invoice {invoice_id}, skipping")
                    continue

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
                invoices_data.append(invoice_data)
                valid_invoice_ids.append(invoice_id)

            except Exception as e:
                logger.warning(f"Error preparing invoice {invoice_id}: {str(e)}")
                continue

        if not invoices_data:
            raise ExportException("No valid invoices found for export")

        # Export to QuickBooks using batch operation
        async def batch_export_to_qb():
            async with QuickBooksService() as qb_service:
                return await qb_service.export_multiple_bills(
                    connection.access_token,
                    connection.realm_id,
                    invoices_data,
                    dry_run
                )

        start_time = datetime.utcnow()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(batch_export_to_qb())
        finally:
            loop.close()
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Create export records for successful exports
        for success_item in result.get("created_bills", []):
            export_record = QuickBooksExport(
                connection_id=connection.id,
                invoice_id=uuid.UUID(success_item["invoice_id"]),
                quickbooks_bill_id=success_item["bill_id"],
                export_type="bill",
                status="success",
                dry_run=dry_run,
                request_payload={"invoice_id": success_item["invoice_id"]},
                response_payload={"bill_id": success_item["bill_id"]},
                processing_time_ms=str(int(processing_time))
            )
            db.add(export_record)

        # Create export records for failed exports
        for error_item in result.get("errors", []):
            export_record = QuickBooksExport(
                connection_id=connection.id,
                invoice_id=uuid.UUID(error_item["invoice_id"]),
                export_type="bill",
                status="failed",
                dry_run=dry_run,
                request_payload={"invoice_id": error_item["invoice_id"]},
                error_message=error_item["error"]
            )
            db.add(export_record)

        db.commit()

        logger.info(f"QuickBooks batch export task {task_id} completed: {result['success']} success, {result['failed']} failed")
        return {
            "task_id": task_id,
            "total_invoices": len(invoice_ids),
            "valid_invoices": len(valid_invoice_ids),
            "result": result,
            "processing_time_ms": int(processing_time)
        }

    except ExportException as e:
        logger.error(f"Batch export task {task_id} failed: {str(e)}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying batch export task {task_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=120 * (2 ** self.request.retries))

        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "retries_exhausted": True
        }

    except Exception as e:
        logger.error(f"Unexpected error in batch export task {task_id}: {str(e)}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying batch export task {task_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=120 * (2 ** self.request.retries))

        return {
            "task_id": task_id,
            "status": "failed",
            "error": f"Unexpected error: {str(e)}",
            "retries_exhausted": True
        }

    finally:
        db.close()


@celery_app.task
def process_quickbooks_webhook(webhook_data: Dict[str, Any], signature: Optional[str] = None):
    """
    Process QuickBooks webhook notifications.

    Args:
        webhook_data: Webhook payload from QuickBooks
        signature: Optional HMAC signature for verification
    """
    task_id = webhook_data.get("webhook_id", "unknown")
    logger.info(f"Processing QuickBooks webhook task {task_id}")

    try:
        async def process_webhook():
            async with QuickBooksService() as qb_service:
                return await qb_service.handle_webhook(webhook_data, signature)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(process_webhook())
        finally:
            loop.close()

        logger.info(f"QuickBooks webhook task {task_id} completed successfully")
        return {
            "webhook_id": task_id,
            "status": "processed",
            "result": result
        }

    except Exception as e:
        logger.error(f"Error processing QuickBooks webhook {task_id}: {str(e)}")
        return {
            "webhook_id": task_id,
            "status": "failed",
            "error": str(e)
        }


@celery_app.task
def refresh_quickbooks_tokens():
    """
    Refresh expired QuickBooks tokens for all active connections.

    This task runs periodically to ensure tokens remain valid.
    """
    logger.info("Starting QuickBooks token refresh task")

    db = SessionLocal()
    try:
        # Find connections that need token refresh
        expiring_soon = datetime.utcnow() + timedelta(hours=1)
        connections = db.query(QuickBooksConnection).filter(
            QuickBooksConnection.status == QuickBooksConnectionStatus.CONNECTED,
            QuickBooksConnection.token_expires_at <= expiring_soon
        ).all()

        refreshed_count = 0
        failed_count = 0

        for connection in connections:
            try:
                async def refresh_token():
                    async with QuickBooksService() as qb_service:
                        return await qb_service.refresh_access_token(
                            connection.refresh_token,
                            connection.realm_id
                        )

                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    token_response = loop.run_until_complete(refresh_token())
                finally:
                    loop.close()

                # Update connection with new tokens
                connection.access_token = token_response["access_token"]
                connection.refresh_token = token_response["refresh_token"]
                connection.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=token_response["expires_in"]
                )
                connection.last_sync_at = datetime.utcnow()
                connection.last_error = None
                db.commit()

                refreshed_count += 1
                logger.info(f"Refreshed token for connection {connection.id} (realm: {connection.realm_id})")

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to refresh token for connection {connection.id}: {str(e)}")

                # Mark connection as expired if refresh fails
                connection.status = QuickBooksConnectionStatus.EXPIRED
                connection.last_error = f"Token refresh failed: {str(e)}"
                db.commit()

        logger.info(f"QuickBooks token refresh task completed: {refreshed_count} refreshed, {failed_count} failed")
        return {
            "refreshed": refreshed_count,
            "failed": failed_count,
            "total_processed": len(connections)
        }

    except Exception as e:
        logger.error(f"Unexpected error in token refresh task: {str(e)}")
        return {
            "status": "failed",
            "error": str(e)
        }

    finally:
        db.close()


# Schedule periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup periodic Celery tasks for QuickBooks integration.
    """
    # Refresh tokens every 30 minutes
    sender.add_periodic_task(
        1800,  # 30 minutes in seconds
        refresh_quickbooks_tokens.s(),
        name='refresh-quickbooks-tokens'
    )

    logger.info("QuickBooks periodic tasks scheduled")