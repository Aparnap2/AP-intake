"""
Enhanced ingestion API endpoints with comprehensive file handling and deduplication.
"""

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response, BackgroundTasks
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
from app.services.idempotency_service import IdempotencyService, IdempotencyOperationType

logger = logging.getLogger(__name__)
router = APIRouter()


# Initialize services
ingestion_service = IngestionService()
deduplication_service = DeduplicationService()
signed_url_service = SignedUrlService()
idempotency_service = IdempotencyService()


@router.post("/upload", response_model=IngestionResponse)
async def upload_file(
    file: UploadFile = File(...),
    vendor_id: Optional[str] = Query(None, description="Optional vendor ID"),
    source_type: str = Query("upload", description="Source type (upload, email, api)"),
    source_reference: Optional[str] = Query(None, description="Source reference ID"),
    uploaded_by: Optional[str] = Query(None, description="User who uploaded the file"),
    idempotency_key: Optional[str] = Query(None, description="Client-provided idempotency key"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Upload and ingest a file with comprehensive hashing, deduplication, and idempotency.

    This endpoint provides robust file ingestion with:
    - SHA-256 file hashing for content integrity
    - Multiple deduplication strategies
    - Secure storage with signed URLs
    - Comprehensive metadata extraction
    - Background processing queuing
    - Idempotency to prevent duplicate uploads
    """
    logger.info(f"Uploading file: {file.filename} (size: {file.size or 'unknown'})")

    try:
        # Validate file upload
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Read file content for hashing and idempotency key generation
        file_content = await file.read()
        await file.seek(0)  # Reset file pointer for later processing

        # Calculate file hash for idempotency
        import hashlib
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = idempotency_service.generate_idempotency_key(
                operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
                vendor_id=vendor_id,
                file_hash=file_hash,
                user_id=uploaded_by,
                additional_context={
                    "filename": file.filename,
                    "source_type": source_type,
                }
            )

        # Check for existing idempotency record
        existing_record, is_new = await idempotency_service.check_and_create_idempotency_record(
            db=db,
            idempotency_key=idempotency_key,
            operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
            operation_data={
                "filename": file.filename,
                "vendor_id": vendor_id,
                "source_type": source_type,
                "source_reference": source_reference,
                "uploaded_by": uploaded_by,
                "file_hash": file_hash,
            },
            user_id=uploaded_by,
            client_ip=request.client.host if request else None,
        )

        if not is_new:
            # Return existing operation result
            if existing_record.operation_status.value == "completed":
                logger.info(f"Returning existing ingestion result for idempotency key: {idempotency_key}")
                return IngestionResponse(**existing_record.result_data)
            elif existing_record.operation_status.value == "in_progress":
                raise HTTPException(
                    status_code=409,
                    detail="File upload is already in progress with the same idempotency key"
                )
            else:
                # Check if we can retry failed operation
                if existing_record.execution_count < existing_record.max_executions:
                    await idempotency_service.mark_operation_started(db, idempotency_key)
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=f"File upload with idempotency key has failed and exceeded retry limit"
                    )
        else:
            # Mark new operation as started
            await idempotency_service.mark_operation_started(db, idempotency_key)

        # Ingest file with comprehensive processing
        ingestion_result = await ingestion_service.ingest_file(
            file_content=file_content,
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
        response_data = {
            "id": ingestion_result["ingestion_job_id"],
            "original_filename": file.filename,
            "file_size_bytes": ingestion_result["file_size"],
            "file_hash_sha256": ingestion_result["file_hash"],
            "status": ingestion_result["status"],
            "storage_path": ingestion_result["storage_path"],
            "duplicate_analysis": ingestion_result.get("duplicate_analysis", {}),
            "created_at": datetime.now(timezone.utc),
            "estimated_processing_time_seconds": ingestion_result.get("estimated_processing_time", 0),
            "idempotency_key": idempotency_key,
        }

        response = IngestionResponse(**response_data)

        # Mark operation as completed
        await idempotency_service.mark_operation_completed(db, idempotency_key, response_data)

        logger.info(f"Successfully uploaded file {file.filename} as job {ingestion_result['ingestion_job_id']}")
        return response

    except HTTPException:
        # Mark operation as failed if we have an idempotency key
        if 'idempotency_key' in locals():
            await idempotency_service.mark_operation_failed(
                db, idempotency_key, {"error": str(e.detail)}
            )
        raise
    except IngestionException as e:
        # Mark operation as failed
        if 'idempotency_key' in locals():
            await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        logger.error(f"Ingestion error for file {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Mark operation as failed
        if 'idempotency_key' in locals():
            await idempotency_service.mark_operation_failed(db, idempotency_key, {"error": str(e)})
        logger.error(f"Unexpected error uploading file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch-upload")
async def batch_upload_files(
    files: List[UploadFile] = File(...),
    vendor_id: Optional[str] = Query(None, description="Optional vendor ID for all files"),
    source_type: str = Query("batch_upload", description="Source type"),
    source_reference: Optional[str] = Query(None, description="Source reference ID"),
    uploaded_by: Optional[str] = Query(None, description="User who uploaded the files"),
    idempotency_key: Optional[str] = Query(None, description="Client-provided idempotency key"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Batch upload multiple files for invoice processing.

    This endpoint provides efficient batch processing of multiple files with:
    - Concurrent file processing for better performance
    - Comprehensive validation and error handling
    - Duplicate detection across all files
    - Partial success handling with detailed status reporting
    - Idempotency to prevent duplicate batch operations

    Returns:
        - 200: All files processed successfully
        - 207: Partial success (some files failed)
        - 400: Validation errors or no files provided
        - 500: Internal server error
    """
    logger.info(f"Starting batch upload of {len(files)} files")

    start_time = time.time()

    # Validate batch size
    MAX_BATCH_SIZE = 50
    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_SIZE} files allowed per batch"
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Validate individual files
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_TYPES = {
        "application/pdf": [".pdf"],
        "image/png": [".png"],
        "image/jpeg": [".jpg", ".jpeg"],
        "image/tiff": [".tiff", ".tif"],
    }

    validated_files = []
    total_file_size = 0
    duplicate_count = 0

    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="All files must have filenames")

        # Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} size exceeds {MAX_FILE_SIZE / 1024 / 1024}MB limit"
            )

        # Check file type
        is_valid_type = False
        if file.content_type in ALLOWED_TYPES:
            is_valid_type = True
        else:
            for ext in ALLOWED_TYPES.values():
                if any(file.filename.lower().endswith(e) for e in ext):
                    is_valid_type = True
                    break

        if not is_valid_type:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} has unsupported type. Supported types: PDF, PNG, JPG, JPEG, TIFF"
            )

        validated_files.append(file)
        total_file_size += file.size or 0

    if not validated_files:
        raise HTTPException(status_code=400, detail="No valid files provided")

    # Generate batch idempotency key if not provided
    if not idempotency_key:
        file_hashes = []
        for file in validated_files:
            content = await file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            file_hashes.append(file_hash[:8])  # Use first 8 chars for batch key
            await file.seek(0)  # Reset file pointer

        batch_hash = hashlib.sha256("".join(sorted(file_hashes)).encode()).hexdigest()[:16]
        idempotency_key = f"batch_{batch_hash}_{int(time.time())}"

    # Check for existing batch idempotency record
    existing_record, is_new = await idempotency_service.check_and_create_idempotency_record(
        db=db,
        idempotency_key=idempotency_key,
        operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
        operation_data={
            "batch_upload": True,
            "file_count": len(validated_files),
            "total_size": total_file_size,
            "vendor_id": vendor_id,
            "source_type": source_type,
            "source_reference": source_reference,
            "uploaded_by": uploaded_by,
        },
        user_id=uploaded_by,
        client_ip=request.client.host if request else None,
    )

    if not is_new:
        # Return existing batch result
        if existing_record.operation_status.value == "completed":
            logger.info(f"Returning existing batch result for idempotency key: {idempotency_key}")
            return existing_record.result_data
        elif existing_record.operation_status.value == "in_progress":
            raise HTTPException(
                status_code=409,
                detail="Batch upload is already in progress with the same idempotency key"
            )
        else:
            # Check if we can retry failed batch operation
            if existing_record.execution_count < existing_record.max_executions:
                await idempotency_service.mark_operation_started(db, idempotency_key)
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"Batch upload with idempotency key has failed and exceeded retry limit"
                )
    else:
        # Mark new batch operation as started
        await idempotency_service.mark_operation_started(db, idempotency_key)

    # Process files concurrently
    batch_id = str(uuid.uuid4())
    results = []
    successful_uploads = 0
    failed_uploads = 0

    async def process_single_file(file: UploadFile) -> Dict[str, Any]:
        """Process a single file in the batch."""
        try:
            # Read file content
            file_content = await file.read()
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Generate file-specific idempotency key
            file_idempotency_key = idempotency_service.generate_idempotency_key(
                operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
                vendor_id=vendor_id,
                file_hash=file_hash,
                user_id=uploaded_by,
                additional_context={
                    "filename": file.filename,
                    "source_type": source_type,
                    "batch_id": batch_id,
                }
            )

            # Check for existing file idempotency record
            file_existing_record, file_is_new = await idempotency_service.check_and_create_idempotency_record(
                db=db,
                idempotency_key=file_idempotency_key,
                operation_type=IdempotencyOperationType.INVOICE_UPLOAD,
                operation_data={
                    "filename": file.filename,
                    "vendor_id": vendor_id,
                    "source_type": source_type,
                    "source_reference": source_reference,
                    "uploaded_by": uploaded_by,
                    "file_hash": file_hash,
                    "batch_id": batch_id,
                },
                user_id=uploaded_by,
                client_ip=request.client.host if request else None,
            )

            if not file_is_new:
                if file_existing_record.operation_status.value == "completed":
                    logger.info(f"Returning existing file result for {file.filename}")
                    return {
                        "success": True,
                        "is_duplicate": True,
                        "result": file_existing_record.result_data
                    }
                else:
                    return {
                        "success": False,
                        "error": f"File {file.filename} has existing operation with status: {file_existing_record.operation_status.value}"
                    }

            # Mark file operation as started
            await idempotency_service.mark_operation_started(db, file_idempotency_key)

            # Ingest file
            ingestion_result = await ingestion_service.ingest_file(
                file_content=file_content,
                filename=file.filename,
                content_type=file.content_type,
                vendor_id=vendor_id,
                source_type=source_type,
                source_reference=source_reference,
                uploaded_by=uploaded_by,
                user_id=getattr(request.state, 'user_id', None),
                request=request,
            )

            # Transform to response format
            response_data = {
                "id": ingestion_result["ingestion_job_id"],
                "original_filename": file.filename,
                "file_size_bytes": ingestion_result["file_size"],
                "file_hash_sha256": ingestion_result["file_hash"],
                "status": ingestion_result["status"],
                "storage_path": ingestion_result["storage_path"],
                "duplicate_analysis": ingestion_result.get("duplicate_analysis", {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "estimated_processing_time_seconds": ingestion_result.get("estimated_processing_time", 0),
                "idempotency_key": file_idempotency_key,
                "batch_id": batch_id,
            }

            # Mark file operation as completed
            await idempotency_service.mark_operation_completed(db, file_idempotency_key, response_data)

            return {
                "success": True,
                "is_duplicate": False,
                "result": response_data
            }

        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Reset file pointer
            await file.seek(0)

    # Process all files concurrently with limited concurrency
    MAX_CONCURRENT_UPLOADS = 10
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    async def process_with_semaphore(file):
        async with semaphore:
            return await process_single_file(file)

    # Run concurrent processing
    processing_tasks = [process_with_semaphore(file) for file in validated_files]
    processing_results = await asyncio.gather(*processing_tasks, return_exceptions=True)

    # Process results
    file_results = []
    for i, result in enumerate(processing_results):
        filename = validated_files[i].filename

        if isinstance(result, Exception):
            file_results.append({
                "success": False,
                "error": f"Processing error: {str(result)}",
                "original_filename": filename,
                "status": "error"
            })
            failed_uploads += 1
        elif result["success"]:
            file_results.append(result["result"])
            successful_uploads += 1
            if result["is_duplicate"]:
                duplicate_count += 1
        else:
            file_results.append({
                "success": False,
                "error": result["error"],
                "original_filename": filename,
                "status": "error"
            })
            failed_uploads += 1

    # Create batch response
    processing_time = time.time() - start_time
    batch_response = {
        "batch_id": batch_id,
        "results": file_results,
        "summary": {
            "total_files": len(validated_files),
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "total_file_size_bytes": total_file_size,
            "duplicates_detected": duplicate_count,
            "success_rate": successful_uploads / len(validated_files) if validated_files else 0,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": round(processing_time, 2),
        "idempotency_key": idempotency_key,
    }

    # Mark batch operation as completed
    await idempotency_service.mark_operation_completed(db, idempotency_key, batch_response)

    logger.info(
        f"Batch upload completed: {successful_uploads}/{len(validated_files)} files successful, "
        f"duplicates: {duplicate_count}, processing time: {processing_time:.2f}s"
    )

    # Determine appropriate HTTP status code
    if failed_uploads == 0:
        status_code = 200  # All successful
    elif successful_uploads == 0:
        status_code = 500  # All failed
    else:
        status_code = 207  # Partial success (Multi-Status)

    return Response(
        content=batch_response,
        status_code=status_code,
        media_type="application/json"
    )


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