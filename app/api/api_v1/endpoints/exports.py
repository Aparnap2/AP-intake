"""
Enhanced export management endpoints.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.export_models import ExportStatus

from app.api.api_v1.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.invoice import Invoice, StagedExport, ExportFormat
from app.models.export_models import ExportJob as ExportJobModel, ExportTemplate
from app.services.export_service import ExportService
from app.services.storage_service import StorageService
from app.schemas.export_schemas import (
    ExportRequest, ExportResponse, ExportProgress, ExportTemplate as ExportTemplateSchema,
    ExportTemplateCreate, ExportTemplateUpdate, ExportFilter, ExportDestinationConfig,
    BatchExportRequest, BatchExportResponse, ExportMetrics as ExportMetricsSchema,
    ExportJob
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Template Management Endpoints
@router.post("/templates", response_model=ExportTemplateSchema)
async def create_export_template(
    template_data: ExportTemplateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new export template."""
    try:
        template = ExportTemplate(
            name=template_data.name,
            description=template_data.description,
            format=template_data.format,
            field_mappings=[m.model_dump() for m in template_data.field_mappings],
            header_config=template_data.header_config,
            footer_config=template_data.footer_config,
            compression=template_data.compression,
            encryption=template_data.encryption,
            created_by=current_user.get("sub")
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        logger.info(f"Created export template: {template.name}")
        return template

    except Exception as e:
        logger.error(f"Failed to create export template: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates", response_model=List[ExportTemplateSchema])
async def list_export_templates(
    format: Optional[ExportFormat] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List export templates."""
    query = db.query(ExportTemplate)

    if format:
        query = query.filter(ExportTemplate.format == format)
    if is_active is not None:
        query = query.filter(ExportTemplate.is_active == is_active)

    templates = query.order_by(ExportTemplate.name).offset(offset).limit(limit).all()
    return templates


@router.get("/templates/{template_id}", response_model=ExportTemplateSchema)
async def get_export_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific export template."""
    template = db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Export template not found")
    return template


@router.put("/templates/{template_id}", response_model=ExportTemplateSchema)
async def update_export_template(
    template_id: str,
    template_data: ExportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an export template."""
    template = db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Export template not found")

    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "field_mappings" and value:
            setattr(template, field, [m.model_dump() for m in value])
        else:
            setattr(template, field, value)

    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)

    logger.info(f"Updated export template: {template.name}")
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete an export template."""
    template = db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Export template not found")

    # Check if template is in use
    active_jobs = db.query(ExportJob).filter(
        ExportJob.template_id == template_id,
        ExportJob.status.in_(['pending', 'preparing', 'processing'])
    ).count()

    if active_jobs > 0:
        raise HTTPException(status_code=400, detail="Cannot delete template with active export jobs")

    db.delete(template)
    db.commit()

    logger.info(f"Deleted export template: {template.name}")


# Export Job Management Endpoints
@router.post("/jobs", response_model=ExportResponse)
async def create_export_job(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create and start an export job."""
    try:
        export_service = ExportService(db=db)
        response = await export_service.create_export_job(
            request=export_request,
            user_id=current_user.get("sub")
        )

        logger.info(f"Created export job: {response.export_id}")
        return response

    except Exception as e:
        logger.error(f"Failed to create export job: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/batch", response_model=BatchExportResponse)
async def create_batch_export_jobs(
    batch_request: BatchExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create multiple export jobs in a batch."""
    try:
        export_service = ExportService(db=db)
        responses = []

        for export_request in batch_request.export_requests:
            response = await export_service.create_export_job(
                request=export_request,
                user_id=current_user.get("sub")
            )
            responses.append(response)

        batch_response = BatchExportResponse(
            export_responses=responses,
            total_exports=len(responses)
        )

        logger.info(f"Created batch export jobs: {len(responses)} jobs")
        return batch_response

    except Exception as e:
        logger.error(f"Failed to create batch export jobs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=List[ExportJob])
async def list_export_jobs(
    status: Optional[str] = None,
    format: Optional[ExportFormat] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List export jobs."""
    query = db.query(ExportJob)

    # Filter by user unless admin
    if current_user.get("role") != "admin":
        query = query.filter(ExportJob.user_id == current_user.get("sub"))

    if status:
        query = query.filter(ExportJob.status == status)
    if format:
        query = query.filter(ExportJob.format == format)

    jobs = query.order_by(ExportJob.created_at.desc()).offset(offset).limit(limit).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=ExportJob)
async def get_export_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific export job."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Check permissions
    if current_user.get("role") != "admin" and job.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    return job


@router.get("/jobs/{job_id}/progress", response_model=ExportProgress)
async def get_export_progress(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get export job progress."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Check permissions
    if current_user.get("role") != "admin" and job.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    export_service = ExportService(db=db)
    return export_service.get_export_progress(job_id)


@router.post("/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_export_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cancel an export job."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Check permissions
    if current_user.get("role") != "admin" and job.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        export_service = ExportService(db=db)
        success = export_service.cancel_export_job(job_id, current_user.get("sub"))
        return {"success": success, "message": "Export job cancelled successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/download")
async def download_export_file(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Download export file."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Check permissions
    if current_user.get("role") != "admin" and job.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    if job.status != ExportStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Export job not completed")

    if not job.file_path:
        raise HTTPException(status_code=404, detail="Export file not available")

    try:
        # Get file from storage
        storage_service = StorageService()
        file_content = await storage_service.get_file_content(job.file_path)

        # Determine media type
        if job.file_path.endswith('.json'):
            media_type = "application/json"
        elif job.file_path.endswith('.csv'):
            media_type = "text/csv"
        elif job.file_path.endswith('.gz'):
            media_type = "application/gzip"
        else:
            media_type = "application/octet-stream"

        # Generate filename
        filename = job.file_path.split('/')[-1]
        if not filename:
            filename = f"export_{job_id}.{job.format.value}"

        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Failed to download export file {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download export file")


@router.get("/jobs/{job_id}/metrics", response_model=ExportMetricsSchema)
async def get_export_metrics(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get export job metrics."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Check permissions
    if current_user.get("role") != "admin" and job.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    metrics = db.query(ExportMetrics).filter(ExportMetrics.export_job_id == job_id).first()
    if not metrics:
        raise HTTPException(status_code=404, detail="Export metrics not found")

    return metrics


# Legacy Single Invoice Export Endpoints (for backward compatibility)
@router.get("/{invoice_id}/csv")
async def export_invoice_csv(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """Export invoice as CSV file (legacy endpoint)."""
    try:
        invoice_uuid = uuid.UUID(invoice_id)
        invoice = db.query(Invoice).filter(Invoice.id == invoice_uuid).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Get latest extraction
        from app.models.invoice import InvoiceExtraction
        extraction = db.query(InvoiceExtraction).filter(
            InvoiceExtraction.invoice_id == invoice_uuid
        ).order_by(InvoiceExtraction.created_at.desc()).first()

        if not extraction:
            raise HTTPException(status_code=404, detail="No extraction found for this invoice")

        # Prepare invoice data
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

        # Generate CSV export using legacy method
        export_service = ExportService(db=db)
        csv_content = await export_service.export_to_csv(invoice_data)

        # Generate filename
        from datetime import datetime
        filename = f"invoice_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Return CSV file
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting invoice {invoice_id} as CSV: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{invoice_id}/json")
async def export_invoice_json(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """Export invoice as JSON file (legacy endpoint)."""
    try:
        invoice_uuid = uuid.UUID(invoice_id)
        invoice = db.query(Invoice).filter(Invoice.id == invoice_uuid).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Get latest extraction
        from app.models.invoice import InvoiceExtraction
        extraction = db.query(InvoiceExtraction).filter(
            InvoiceExtraction.invoice_id == invoice_uuid
        ).order_by(InvoiceExtraction.created_at.desc()).first()

        if not extraction:
            raise HTTPException(status_code=404, detail="No extraction found for this invoice")

        # Prepare invoice data
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

        # Generate JSON export using legacy method
        export_service = ExportService(db=db)
        json_content = await export_service.export_to_json(invoice_data)

        # Generate filename
        from datetime import datetime
        filename = f"invoice_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Return JSON file
        return StreamingResponse(
            iter([json_content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting invoice {invoice_id} as JSON: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/staged/{export_id}/download")
async def download_staged_export(
    export_id: str,
    db: Session = Depends(get_db),
):
    """Download a staged export file (legacy endpoint)."""
    try:
        export_uuid = uuid.UUID(export_id)
        staged_export = db.query(StagedExport).filter(StagedExport.id == export_uuid).first()

        if not staged_export:
            raise HTTPException(status_code=404, detail="Staged export not found")

        if not staged_export.file_name:
            raise HTTPException(status_code=404, detail="No file available for this export")

        # Get file from storage
        storage_service = StorageService()
        file_content = await storage_service.get_file_content(staged_export.file_name)

        # Determine media type
        media_type = "application/json" if staged_export.format == ExportFormat.JSON else "text/csv"

        # Return file
        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={staged_export.file_name}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid export_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading staged export {export_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")