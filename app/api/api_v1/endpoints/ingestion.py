"""
Enhanced ingestion API endpoints with comprehensive file handling and deduplication.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.api.schemas import (
    IngestionResponse,
    IngestionListResponse,
    DuplicateGroupResponse,
    SignedUrlResponse,
    DeduplicationRuleCreate,
    DeduplicationRuleUpdate,
)
from app.core.config import settings
from app.core.exceptions import IngestionException, SecurityException
from app.db.session import get_db
from app.models.ingestion import (
    IngestionJob,
    DuplicateRecord,
    SignedUrl,
    DeduplicationRule,
    IngestionStatus,
    DeduplicationStrategy,
    DuplicateResolution,
)
from app.models.reference import Vendor
from app.services.ingestion_service import IngestionService
from app.services.deduplication_service import DeduplicationService
from app.services.signed_url_service import SignedUrlService

logger = logging.getLogger(__name__)
router = APIRouter()


# Initialize services
ingestion_service = IngestionService()
deduplication_service = DeduplicationService()
signed_url_service = SignedUrlService()


@router.post("/upload", response_model=IngestionResponse)
async def upload_file(
    file: UploadFile = File(...),
    vendor_id: Optional[str] = Query(None, description="Optional vendor ID"),
    source_type: str = Query("upload", description="Source type (upload, email, api)"),
    source_reference: Optional[str] = Query(None, description="Source reference ID"),
    uploaded_by: Optional[str] = Query(None, description="User who uploaded the file"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Upload and ingest a file with comprehensive hashing and deduplication.

    This endpoint provides robust file ingestion with:
    - SHA-256 file hashing for content integrity
    - Multiple deduplication strategies
    - Secure storage with signed URLs
    - Comprehensive metadata extraction
    - Background processing queuing
    """
    logger.info(f"Uploading file: {file.filename} (size: {file.size or 'unknown'})")

    try:
        # Validate file upload
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Ingest file with comprehensive processing
        ingestion_result = await ingestion_service.ingest_file(
            file_content=file.file,
            filename=file.filename,
            content_type=file.content_type,
            vendor_id=vendor_id,
            source_type=source_type,
            source_reference=source_reference,
            uploaded_by=uploaded_by,
            user_id=getattr(request.state, 'user_id', None),
            request=request,
        )

        # Transform to response model
        response = IngestionResponse(
            id=ingestion_result["ingestion_job_id"],
            original_filename=file.filename,
            file_size_bytes=ingestion_result["file_size"],
            file_hash_sha256=ingestion_result["file_hash"],
            status=ingestion_result["status"],
            storage_path=ingestion_result["storage_path"],
            duplicate_analysis=ingestion_result.get("duplicate_analysis", {}),
            created_at=datetime.now(timezone.utc),
            estimated_processing_time_seconds=ingestion_result.get("estimated_processing_time", 0),
        )

        logger.info(f"Successfully uploaded file {file.filename} as job {ingestion_result['ingestion_job_id']}")
        return response

    except IngestionException as e:
        logger.error(f"Ingestion error for file {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error uploading file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs", response_model=IngestionListResponse)
async def list_ingestion_jobs(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    include_duplicates: bool = Query(False, description="Include duplicate information"),
    db: AsyncSession = Depends(get_db),
):
    """List ingestion jobs with comprehensive filtering and pagination."""
    try:
        # Build base query
        query = select(IngestionJob)
        conditions = []

        # Apply filters
        if status:
            try:
                status_enum = IngestionStatus[status.upper()]
                conditions.append(IngestionJob.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if vendor_id:
            try:
                vendor_uuid = uuid.UUID(vendor_id)
                conditions.append(IngestionJob.vendor_id == vendor_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid vendor_id format")

        if source_type:
            conditions.append(IngestionJob.source_type == source_type)

        if start_date:
            conditions.append(IngestionJob.created_at >= start_date)

        if end_date:
            conditions.append(IngestionJob.created_at <= end_date)

        # Apply conditions
        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(IngestionJob.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(IngestionJob.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        jobs = result.scalars().all()

        # Transform to response format
        job_responses = []
        for job in jobs:
            job_data = {
                "id": str(job.id),
                "original_filename": job.original_filename,
                "file_size_bytes": job.file_size_bytes,
                "file_hash_sha256": job.file_hash_sha256,
                "status": job.status.value,
                "storage_path": job.storage_path,
                "storage_backend": job.storage_backend,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "source_type": job.source_type,
                "processing_started_at": job.processing_started_at,
                "processing_completed_at": job.processing_completed_at,
                "processing_duration_ms": job.processing_duration_ms,
                "error_message": job.error_message,
                "retry_count": job.retry_count,
            }

            # Add duplicate information if requested
            if include_duplicates:
                duplicate_query = select(DuplicateRecord).where(
                    DuplicateRecord.ingestion_job_id == job.id
                )
                duplicate_result = await db.execute(duplicate_query)
                duplicates = duplicate_result.scalars().all()

                job_data["duplicates"] = [
                    {
                        "id": str(dup.id),
                        "strategy": dup.detection_strategy.value,
                        "confidence_score": dup.confidence_score,
                        "resolution_action": dup.resolution_action.value if dup.resolution_action else None,
                        "requires_human_review": dup.requires_human_review,
                    }
                    for dup in duplicates
                ]

            job_responses.append(job_data)

        return IngestionListResponse(
            jobs=job_responses,
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing ingestion jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}", response_model=IngestionResponse)
async def get_ingestion_job(
    job_id: str,
    include_duplicates: bool = Query(False, description="Include duplicate information"),
    include_signed_urls: bool = Query(False, description="Include signed URL information"),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific ingestion job."""
    try:
        job = await ingestion_service.get_ingestion_job(
            job_id=job_id,
            db=db,
            include_duplicates=include_duplicates,
            include_signed_urls=include_signed_urls,
        )

        if not job:
            raise HTTPException(status_code=404, detail="Ingestion job not found")

        # Transform to response format
        response_data = {
            "id": str(job.id),
            "original_filename": job.original_filename,
            "file_size_bytes": job.file_size_bytes,
            "file_hash_sha256": job.file_hash_sha256,
            "status": job.status.value,
            "storage_path": job.storage_path,
            "storage_backend": job.storage_backend,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "source_type": job.source_type,
            "source_reference": job.source_reference,
            "uploaded_by": job.uploaded_by,
            "processing_started_at": job.processing_started_at,
            "processing_completed_at": job.processing_completed_at,
            "processing_duration_ms": job.processing_duration_ms,
            "error_message": job.error_message,
            "error_code": job.error_code,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "extracted_metadata": job.extracted_metadata,
            "is_duplicate": job.is_duplicate,
            "duplicate_group_id": str(job.duplicate_group_id) if job.duplicate_group_id else None,
        }

        # Add duplicate information if requested
        if include_duplicates and hasattr(job, 'duplicate_records'):
            response_data["duplicates"] = [
                {
                    "id": str(dup.id),
                    "strategy": dup.detection_strategy.value,
                    "confidence_score": dup.confidence_score,
                    "similarity_score": dup.similarity_score,
                    "match_criteria": dup.match_criteria,
                    "comparison_details": dup.comparison_details,
                    "resolution_action": dup.resolution_action.value if dup.resolution_action else None,
                    "resolved_by": dup.resolved_by,
                    "resolved_at": dup.resolved_at,
                    "resolution_notes": dup.resolution_notes,
                    "requires_human_review": dup.requires_human_review,
                    "status": dup.status,
                }
                for dup in job.duplicate_records
            ]

        # Add signed URL information if requested
        if include_signed_urls and hasattr(job, 'signed_urls'):
            response_data["signed_urls"] = [
                {
                    "id": str(url.id),
                    "url_token": url.url_token,
                    "expires_at": url.expires_at,
                    "access_count": url.access_count,
                    "max_access_count": url.max_access_count,
                    "is_active": url.is_active,
                    "created_for": url.created_for,
                }
                for url in job.signed_urls
            ]

        return IngestionResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ingestion job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/{job_id}/signed-urls", response_model=SignedUrlResponse)
async def generate_signed_url(
    job_id: str,
    expiry_hours: int = Query(24, ge=1, le=168, description="URL expiry in hours"),
    max_access_count: int = Query(1, ge=1, le=100, description="Maximum access count"),
    allowed_ips: Optional[List[str]] = Query(None, description="Allowed IP addresses"),
    created_for: Optional[str] = Query(None, description="Purpose or user identifier"),
    db: AsyncSession = Depends(get_db),
):
    """Generate a secure signed URL for file access."""
    try:
        signed_url_info = await signed_url_service.generate_signed_url(
            ingestion_job_id=job_id,
            db=db,
            expiry_hours=expiry_hours,
            max_access_count=max_access_count,
            allowed_ip_addresses=allowed_ips,
            created_for=created_for,
        )

        return SignedUrlResponse(
            id=signed_url_info["signed_url_id"],
            url=signed_url_info["url"],
            token=signed_url_info["token"],
            expires_at=signed_url_info["expires_at"],
            expiry_hours=signed_url_info["expiry_hours"],
            max_access_count=signed_url_info["max_access_count"],
            allowed_ip_addresses=signed_url_info["allowed_ip_addresses"],
            filename=signed_url_info["filename"],
            file_size=signed_url_info["file_size"],
            mime_type=signed_url_info["mime_type"],
            security_features=signed_url_info["security_features"],
        )

    except SecurityException as e:
        logger.error(f"Security error generating signed URL for job {job_id}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating signed URL for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/files/{url_token}")
async def access_file_via_signed_url(
    url_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Access file using signed URL token."""
    try:
        # Validate signed URL access
        job, signed_url_record = await signed_url_service.validate_signed_url_access(
            url_token=url_token,
            request=request,
            db=db,
        )

        # Get file content from storage
        file_content = await ingestion_service.storage_service.get_file_content(
            job.storage_path
        )

        # Return file as streaming response
        return StreamingResponse(
            iter([file_content]),
            media_type=job.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={job.original_filename}",
                "Content-Length": str(len(file_content)),
                "X-File-ID": str(job.id),
                "X-Access-Count": str(signed_url_record.access_count),
            }
        )

    except SecurityException as e:
        logger.warning(f"Security error accessing file with token {url_token}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error accessing file with token {url_token}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/duplicates", response_model=List[DuplicateGroupResponse])
async def get_duplicate_groups(
    limit: int = Query(100, ge=1, le=1000, description="Maximum groups to return"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    """Get duplicate groups requiring review and resolution."""
    try:
        duplicate_groups = await deduplication_service.get_duplicate_groups(
            limit=limit,
            vendor_id=vendor_id,
            status=status,
            db=db,
        )

        # Transform to response format
        return [
            DuplicateGroupResponse(
                group_id=group["group_id"],
                duplicate_count=group["duplicate_count"],
                total_confidence=group["total_confidence"],
                strategies_used=group["strategies_used"],
                duplicates=group["duplicates"],
            )
            for group in duplicate_groups
        ]

    except Exception as e:
        logger.error(f"Error getting duplicate groups: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/duplicates/{duplicate_id}/resolve")
async def resolve_duplicate(
    duplicate_id: str,
    resolution: DuplicateResolution,
    resolved_by: str = Query(..., description="User or system resolving the duplicate"),
    resolution_notes: Optional[str] = Query(None, description="Resolution notes"),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a specific duplicate record."""
    try:
        success = await deduplication_service.resolve_duplicate(
            duplicate_id=duplicate_id,
            resolution=resolution,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
            db=db,
        )

        if success:
            return {
                "message": f"Duplicate {duplicate_id} resolved successfully",
                "resolution": resolution.value,
                "resolved_by": resolved_by,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to resolve duplicate")

    except Exception as e:
        logger.error(f"Error resolving duplicate {duplicate_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/duplicates/groups/{group_id}/resolve")
async def resolve_duplicate_group(
    group_id: str,
    resolution: DuplicateResolution,
    resolved_by: str = Query(..., description="User or system resolving the duplicate group"),
    resolution_notes: Optional[str] = Query(None, description="Resolution notes"),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an entire duplicate group."""
    try:
        success = await deduplication_service.resolve_duplicate_group(
            group_id=group_id,
            resolution=resolution,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
            db=db,
        )

        if success:
            return {
                "message": f"Duplicate group {group_id} resolved successfully",
                "group_id": group_id,
                "resolution": resolution.value,
                "resolved_by": resolved_by,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to resolve duplicate group")

    except Exception as e:
        logger.error(f"Error resolving duplicate group {group_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics")
async def get_ingestion_metrics(
    start_date: datetime = Query(..., description="Start date for metrics"),
    end_date: datetime = Query(..., description="End date for metrics"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive ingestion metrics for the specified date range."""
    try:
        # Validate date range
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        # Limit date range to prevent excessive queries
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Date range cannot exceed {max_days} days"
            )

        # Get ingestion metrics
        ingestion_metrics = await ingestion_service.get_ingestion_metrics(
            start_date=start_date,
            end_date=end_date,
            vendor_id=vendor_id,
            db=db,
        )

        # Get signed URL access statistics
        url_metrics = await signed_url_service.get_url_access_statistics(
            start_date=start_date,
            end_date=end_date,
            db=db,
        )

        return {
            "ingestion_metrics": ingestion_metrics,
            "url_access_metrics": url_metrics,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ingestion metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/maintenance/cleanup-expired-urls")
async def cleanup_expired_urls(
    dry_run: bool = Query(False, description="If True, only report what would be cleaned up"),
    db: AsyncSession = Depends(get_db),
):
    """Clean up expired signed URLs (admin/maintenance endpoint)."""
    try:
        cleanup_stats = await signed_url_service.cleanup_expired_urls(db=db, dry_run=dry_run)

        return {
            "message": "Expired URL cleanup completed" if not dry_run else "Expired URL cleanup analysis",
            "dry_run": dry_run,
            "statistics": cleanup_stats,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error during expired URL cleanup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch-signed-urls")
async def generate_batch_signed_urls(
    job_ids: List[str],
    expiry_hours: int = Query(24, ge=1, le=168, description="URL expiry in hours"),
    max_access_count: int = Query(1, ge=1, le=100, description="Maximum access count"),
    created_for: Optional[str] = Query(None, description="Purpose or user identifier"),
    db: AsyncSession = Depends(get_db),
):
    """Generate signed URLs for multiple ingestion jobs."""
    try:
        if len(job_ids) > 100:  # Limit batch size
            raise HTTPException(status_code=400, detail="Batch size cannot exceed 100 jobs")

        batch_results = await signed_url_service.generate_batch_signed_urls(
            ingestion_job_ids=job_ids,
            db=db,
            expiry_hours=expiry_hours,
            max_access_count=max_access_count,
            created_for=created_for,
        )

        successful_urls = [r["signed_url"] for r in batch_results if r["success"]]
        failed_jobs = [r for r in batch_results if not r["success"]]

        return {
            "total_requested": len(job_ids),
            "successful": len(successful_urls),
            "failed": len(failed_jobs),
            "signed_urls": successful_urls,
            "failed_jobs": failed_jobs,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating batch signed URLs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")