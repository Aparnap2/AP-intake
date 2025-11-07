"""
Invoice management endpoints.
"""

import hashlib
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.schemas import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceListResponse,
)
from app.core.config import settings
from app.core.exceptions import APIntakeException, StorageException
from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.services.storage_service import StorageService
from app.workers.invoice_tasks import process_invoice_task

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=InvoiceResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process an invoice file."""
    logger.info(f"Uploading invoice file: {file.filename}")

    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in settings.ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_extension}' not allowed. Allowed types: {settings.ALLOWED_FILE_TYPES}"
            )

        # Validate file size
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File size {file_size_mb:.1f}MB exceeds maximum {settings.MAX_FILE_SIZE_MB}MB"
            )

        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Check for duplicate files
        result = await db.execute(select(Invoice).where(Invoice.file_hash == file_hash))
        existing_invoice = result.scalar_one_or_none()
        if existing_invoice:
            logger.warning(f"Duplicate file detected: {file.filename} (hash: {file_hash})")
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate file detected. Existing invoice ID: {existing_invoice.id}"
            )

        # Store file
        storage_service = StorageService()
        storage_info = await storage_service.store_file(
            content,
            file.filename,
            content_type=file.content_type
        )

        # Create invoice record
        invoice = Invoice(
            vendor_id=None,  # Will be determined from extraction during processing
            file_url=storage_info["file_path"],
            file_hash=file_hash,
            file_name=file.filename,
            file_size=f"{file_size_mb:.1f}MB",
            status=InvoiceStatus.RECEIVED,
            workflow_state="uploaded",
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        # Queue processing task
        process_invoice_task.delay(
            str(invoice.id),
            storage_info["file_path"],
            file_hash
        )

        logger.info(f"Successfully uploaded and queued invoice {invoice.id}")
        return InvoiceResponse.from_orm(invoice)

    except HTTPException:
        raise
    except StorageException as e:
        logger.error(f"Storage error during upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=InvoiceListResponse)
async def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List invoices with optional filtering."""
    try:
        # Build the base query
        query = select(Invoice)

        # Apply filters
        conditions = []
        if status:
            try:
                status_enum = InvoiceStatus[status.upper()]
                conditions.append(Invoice.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if vendor_id:
            try:
                vendor_uuid = uuid.UUID(vendor_id)
                conditions.append(Invoice.vendor_id == vendor_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid vendor_id format")

        # Apply conditions to query
        if conditions:
            query = query.where(*conditions)

        # Get total count
        count_query = select(func.count(Invoice.id))
        if conditions:
            count_query = count_query.where(*conditions)

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        invoices = result.scalars().all()

        return InvoiceListResponse(
            invoices=[InvoiceResponse.model_validate(invoice) for invoice in invoices],
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing invoices: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get invoice details by ID."""
    try:
        invoice_uuid = uuid.UUID(invoice_id)
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_uuid))
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        return InvoiceResponse.model_validate(invoice)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{invoice_id}/review", response_model=InvoiceResponse)
async def review_invoice(
    invoice_id: str,
    invoice_update: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update invoice after human review."""
    try:
        invoice_uuid = uuid.UUID(invoice_id)
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_uuid))
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Update invoice fields
        update_data = invoice_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(invoice, field):
                setattr(invoice, field, value)

        await db.commit()
        await db.refresh(invoice)

        logger.info(f"Invoice {invoice_id} updated after review")
        return InvoiceResponse.model_validate(invoice)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Approve invoice and stage for export."""
    try:
        invoice_uuid = uuid.UUID(invoice_id)
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_uuid))
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if invoice.status != InvoiceStatus.READY:
            raise HTTPException(
                status_code=400,
                detail=f"Invoice must be in 'ready' status to approve. Current status: {invoice.status}"
            )

        # Update invoice status
        invoice.status = InvoiceStatus.STAGED
        invoice.workflow_state = "approved"
        await db.commit()

        # Queue export task
        from app.workers.invoice_tasks import export_invoice_task
        export_invoice_task.delay(str(invoice.id))

        logger.info(f"Invoice {invoice_id} approved and queued for export")
        return {
            "message": "Invoice approved and queued for export",
            "invoice_id": invoice_id,
            "status": invoice.status.value,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")