"""
Enhanced ingestion service for robust file handling, hashing, and deduplication.
"""

import asyncio
import hashlib
import logging
import uuid
import magic
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, BinaryIO
from urllib.parse import urlparse

import aiofiles
from fastapi import Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.core.config import settings
from app.core.exceptions import IngestionException, StorageException
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
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class IngestionService:
    """Enhanced ingestion service with comprehensive deduplication."""

    def __init__(self):
        """Initialize the ingestion service."""
        self.storage_service = StorageService()
        self.allowed_file_types = {
            'application/pdf': 'pdf',
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/tiff': 'tiff',
            'image/webp': 'webp',
            'text/plain': 'txt',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        }
        self.max_file_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    async def ingest_file(
        self,
        file_content: Union[bytes, BinaryIO],
        filename: str,
        content_type: Optional[str] = None,
        vendor_id: Optional[str] = None,
        source_type: str = "upload",
        source_reference: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a file with comprehensive hashing, storage, and deduplication.

        Args:
            file_content: Raw file content or file-like object
            filename: Original filename
            content_type: MIME type (auto-detected if not provided)
            vendor_id: Optional vendor UUID
            source_type: Source of the file (upload, email, api)
            source_reference: Source reference ID
            uploaded_by: User who uploaded the file
            user_id: User ID for access control
            request: FastAPI request object

        Returns:
            Dictionary with ingestion job details and status
        """
        logger.info(f"Starting ingestion for file: {filename}")

        try:
            # Convert file content to bytes if needed
            if hasattr(file_content, 'read'):
                file_bytes = await file_content.read()
            else:
                file_bytes = file_content

            # Validate file content
            await self._validate_file_content(file_bytes, filename, content_type)

            # Calculate file hashes
            file_hash = await self._calculate_file_hash(file_bytes)
            mime_type = await self._detect_mime_type(file_bytes, content_type)

            # Extract file metadata
            file_metadata = await self._extract_file_metadata(
                file_bytes, filename, mime_type, file_hash
            )

            # Check for existing ingestion jobs
            existing_job = await self._check_existing_ingestion(file_hash)
            if existing_job:
                logger.warning(f"Duplicate file detected: {filename} (hash: {file_hash})")
                return await self._handle_duplicate_file(existing_job, filename, source_reference)

            # Store file with enhanced metadata
            storage_info = await self.storage_service.store_file(
                file_content=file_bytes,
                filename=filename,
                content_type=mime_type,
                user_id=user_id,
                request=request,
                organization_path=None,  # Will be extracted from file if available
                vendor_name=None,  # Will be extracted from file if available
                invoice_date=None  # Will be extracted from file if available
            )

            # Create ingestion job
            ingestion_job = await self._create_ingestion_job(
                filename=filename,
                file_bytes=file_bytes,
                file_hash=file_hash,
                mime_type=mime_type,
                storage_info=storage_info,
                vendor_id=vendor_id,
                source_type=source_type,
                source_reference=source_reference,
                uploaded_by=uploaded_by,
                metadata=file_metadata
            )

            # Run deduplication analysis
            duplicate_analysis = await self._run_deduplication_analysis(
                ingestion_job, file_bytes, file_metadata
            )

            # Queue processing task
            await self._queue_processing_task(ingestion_job, storage_info)

            logger.info(f"Successfully ingested file {filename} as job {ingestion_job.id}")

            return {
                "ingestion_job_id": str(ingestion_job.id),
                "status": ingestion_job.status.value,
                "filename": filename,
                "file_hash": file_hash,
                "file_size": len(file_bytes),
                "storage_path": storage_info["file_path"],
                "duplicate_analysis": duplicate_analysis,
                "created_at": ingestion_job.created_at,
                "estimated_processing_time": self._estimate_processing_time(file_bytes, mime_type),
            }

        except Exception as e:
            logger.error(f"Failed to ingest file {filename}: {e}")
            raise IngestionException(f"Ingestion failed: {str(e)}")

    async def get_ingestion_job(
        self,
        job_id: str,
        db: AsyncSession,
        include_duplicates: bool = False,
        include_signed_urls: bool = False,
    ) -> Optional[IngestionJob]:
        """Get ingestion job by ID with optional related data."""
        try:
            job_uuid = uuid.UUID(job_id)
            query = select(IngestionJob).where(IngestionJob.id == job_uuid)

            if include_duplicates:
                query = query.options(selectinload(IngestionJob.duplicate_records))
            if include_signed_urls:
                query = query.options(selectinload(IngestionJob.signed_urls))

            result = await db.execute(query)
            return result.scalar_one_or_none()

        except ValueError:
            logger.warning(f"Invalid job ID format: {job_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get ingestion job {job_id}: {e}")
            return None

    async def generate_signed_url(
        self,
        job_id: str,
        db: AsyncSession,
        expiration_hours: int = 24,
        max_access_count: int = 1,
        allowed_ips: Optional[List[str]] = None,
        created_for: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a signed URL for secure file access."""
        try:
            # Get ingestion job
            job = await self.get_ingestion_job(job_id, db)
            if not job:
                raise IngestionException(f"Ingestion job {job_id} not found")

            # Check if file exists
            if not await self.storage_service.file_exists(job.storage_path):
                raise IngestionException(f"File not found: {job.storage_path}")

            # Generate unique token
            url_token = await self._generate_url_token(job_id)

            # Calculate expiry
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

            # Generate signed URL based on storage backend
            if job.storage_backend == "s3":
                signed_url = await self.storage_service.generate_presigned_url(
                    job.storage_path, expiration_hours * 3600
                )
            else:
                # Generate local signed URL
                signed_url = await self._generate_local_signed_url(job, url_token, expires_at)

            # Create signed URL record
            signed_url_record = SignedUrl(
                ingestion_job_id=job.id,
                url_token=url_token,
                signed_url=signed_url,
                expires_at=expires_at,
                max_access_count=max_access_count,
                allowed_ip_addresses=allowed_ips,
                created_for=created_for,
                is_active=True,
            )
            db.add(signed_url_record)
            await db.commit()

            logger.info(f"Generated signed URL for job {job_id}, expires {expires_at}")
            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate signed URL for job {job_id}: {e}")
            raise IngestionException(f"Failed to generate signed URL: {str(e)}")

    async def resolve_duplicate(
        self,
        duplicate_id: str,
        resolution: DuplicateResolution,
        resolved_by: str,
        resolution_notes: Optional[str] = None,
        db: AsyncSession,
    ) -> bool:
        """Resolve a duplicate record with specified action."""
        try:
            duplicate_uuid = uuid.UUID(duplicate_id)
            result = await db.execute(
                select(DuplicateRecord).where(DuplicateRecord.id == duplicate_uuid)
            )
            duplicate = result.scalar_one_or_none()

            if not duplicate:
                raise IngestionException(f"Duplicate record {duplicate_id} not found")

            # Update duplicate record
            duplicate.resolution_action = resolution
            duplicate.resolved_by = resolved_by
            duplicate.resolved_at = datetime.now(timezone.utc)
            duplicate.resolution_notes = resolution_notes
            duplicate.status = "resolved"

            # Apply resolution action
            await self._apply_duplicate_resolution(duplicate, resolution, db)

            await db.commit()
            logger.info(f"Resolved duplicate {duplicate_id} with action: {resolution}")
            return True

        except ValueError:
            raise IngestionException(f"Invalid duplicate ID format: {duplicate_id}")
        except Exception as e:
            logger.error(f"Failed to resolve duplicate {duplicate_id}: {e}")
            await db.rollback()
            raise IngestionException(f"Failed to resolve duplicate: {str(e)}")

    async def get_ingestion_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        vendor_id: Optional[str] = None,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get ingestion metrics for the specified date range."""
        try:
            # Build base query
            conditions = [
                IngestionJob.created_at >= start_date,
                IngestionJob.created_at <= end_date,
            ]

            if vendor_id:
                try:
                    vendor_uuid = uuid.UUID(vendor_id)
                    conditions.append(IngestionJob.vendor_id == vendor_uuid)
                except ValueError:
                    raise IngestionException(f"Invalid vendor ID format: {vendor_id}")

            # Get basic counts
            total_query = select(func.count(IngestionJob.id)).where(and_(*conditions))
            total_result = await db.execute(total_query)
            total_jobs = total_result.scalar()

            # Get status breakdown
            status_query = (
                select(IngestionJob.status, func.count(IngestionJob.id))
                .where(and_(*conditions))
                .group_by(IngestionJob.status)
            )
            status_result = await db.execute(status_query)
            status_breakdown = {status.value: count for status, count in status_result}

            # Get duplicate breakdown
            duplicate_query = (
                select(DuplicateRecord.detection_strategy, func.count(DuplicateRecord.id))
                .join(IngestionJob, DuplicateRecord.ingestion_job_id == IngestionJob.id)
                .where(and_(*conditions))
                .group_by(DuplicateRecord.detection_strategy)
            )
            duplicate_result = await db.execute(duplicate_query)
            duplicate_breakdown = {
                strategy.value: count for strategy, count in duplicate_result
            }

            # Get average processing time
            processing_time_query = (
                select(func.avg(IngestionJob.processing_duration_ms))
                .where(and_(*conditions, IngestionJob.processing_duration_ms.isnot(None)))
            )
            processing_time_result = await db.execute(processing_time_query)
            avg_processing_time = processing_time_result.scalar()

            # Get file size statistics
            file_size_query = (
                select(
                    func.sum(IngestionJob.file_size_bytes),
                    func.avg(IngestionJob.file_size_bytes),
                    func.max(IngestionJob.file_size_bytes),
                    func.min(IngestionJob.file_size_bytes),
                )
                .where(and_(*conditions))
            )
            file_size_result = await db.execute(file_size_query)
            total_size, avg_size, max_size, min_size = file_size_result.first()

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "total_jobs": total_jobs,
                "status_breakdown": status_breakdown,
                "duplicate_breakdown": duplicate_breakdown,
                "processing_metrics": {
                    "avg_processing_time_ms": int(avg_processing_time) if avg_processing_time else None,
                },
                "file_size_metrics": {
                    "total_size_bytes": total_size or 0,
                    "avg_size_bytes": int(avg_size) if avg_size else None,
                    "max_size_bytes": max_size,
                    "min_size_bytes": min_size,
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get ingestion metrics: {e}")
            raise IngestionException(f"Failed to get metrics: {str(e)}")

    async def _validate_file_content(
        self, file_bytes: bytes, filename: str, content_type: Optional[str]
    ) -> None:
        """Validate file content against allowed types and sizes."""
        # Check file size
        if len(file_bytes) > self.max_file_size:
            raise IngestionException(
                f"File size {len(file_bytes)} bytes exceeds maximum {self.max_file_size} bytes"
            )

        # Detect MIME type if not provided
        if not content_type:
            content_type = await self._detect_mime_type(file_bytes)

        # Check if file type is allowed
        if content_type not in self.allowed_file_types:
            allowed_types = ", ".join(self.allowed_file_types.keys())
            raise IngestionException(
                f"File type '{content_type}' not allowed. Allowed types: {allowed_types}"
            )

        # Validate filename
        if not filename or len(filename.strip()) == 0:
            raise IngestionException("Filename is required")

        if len(filename) > 500:
            raise IngestionException("Filename too long (max 500 characters)")

    async def _detect_mime_type(self, file_bytes: bytes, content_type: Optional[str] = None) -> str:
        """Detect MIME type using python-magic library."""
        try:
            # Use python-magic for accurate MIME type detection
            mime = magic.Magic(mime=True)
            detected_type = mime.from_buffer(file_bytes)

            # Fallback to provided content_type if detection fails
            if detected_type == "application/octet-stream" and content_type:
                return content_type

            return detected_type

        except Exception as e:
            logger.warning(f"MIME type detection failed: {e}")
            # Fallback to provided content_type or default
            return content_type or "application/octet-stream"

    async def _calculate_file_hash(self, file_bytes: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_bytes).hexdigest()

    async def _extract_file_metadata(
        self, file_bytes: bytes, filename: str, mime_type: str, file_hash: str
    ) -> Dict[str, Any]:
        """Extract metadata from file content."""
        metadata = {
            "filename": filename,
            "file_hash": file_hash,
            "mime_type": mime_type,
            "file_size_bytes": len(file_bytes),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Extract additional metadata based on file type
            if mime_type == "application/pdf":
                metadata.update(await self._extract_pdf_metadata(file_bytes))
            elif mime_type.startswith("image/"):
                metadata.update(await self._extract_image_metadata(file_bytes))

        except Exception as e:
            logger.warning(f"Failed to extract file metadata: {e}")

        return metadata

    async def _extract_pdf_metadata(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract metadata from PDF files."""
        # This is a placeholder - implement PDF metadata extraction
        # using libraries like PyPDF2 or pdfplumber
        return {
            "file_type": "pdf",
            "pages": None,  # Would be extracted from PDF
            "title": None,
            "author": None,
            "creator": None,
            "producer": None,
            "creation_date": None,
            "modification_date": None,
        }

    async def _extract_image_metadata(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract metadata from image files."""
        # This is a placeholder - implement image metadata extraction
        # using libraries like Pillow (PIL)
        return {
            "file_type": "image",
            "width": None,  # Would be extracted from image
            "height": None,
            "format": None,
            "mode": None,
        }

    async def _check_existing_ingestion(self, file_hash: str) -> Optional[IngestionJob]:
        """Check if file with same hash has been ingested before."""
        # This would require a database session - for now, return None
        # In a full implementation, this would query the database
        return None

    async def _handle_duplicate_file(
        self, existing_job: IngestionJob, filename: str, source_reference: Optional[str]
    ) -> Dict[str, Any]:
        """Handle duplicate file detection."""
        return {
            "ingestion_job_id": str(existing_job.id),
            "status": IngestionStatus.DUPLICATE_DETECTED.value,
            "filename": filename,
            "file_hash": existing_job.file_hash_sha256,
            "original_job": {
                "id": str(existing_job.id),
                "status": existing_job.status.value,
                "created_at": existing_job.created_at.isoformat(),
                "original_filename": existing_job.original_filename,
            },
            "duplicate_detected": True,
            "message": "Duplicate file detected - original job found",
        }

    async def _create_ingestion_job(
        self,
        filename: str,
        file_bytes: bytes,
        file_hash: str,
        mime_type: str,
        storage_info: Dict[str, Any],
        vendor_id: Optional[str],
        source_type: str,
        source_reference: Optional[str],
        uploaded_by: Optional[str],
        metadata: Dict[str, Any],
    ) -> IngestionJob:
        """Create ingestion job record."""
        # This would require a database session
        # For now, create a mock job object
        job = IngestionJob(
            id=uuid.uuid4(),
            original_filename=filename,
            file_extension=Path(filename).suffix.lower(),
            file_size_bytes=len(file_bytes),
            file_hash_sha256=file_hash,
            mime_type=mime_type,
            storage_path=storage_info["file_path"],
            storage_backend=storage_info.get("storage_type", "local"),
            status=IngestionStatus.PENDING,
            extracted_metadata=metadata,
            vendor_id=uuid.UUID(vendor_id) if vendor_id else None,
            source_type=source_type,
            source_reference=source_reference,
            uploaded_by=uploaded_by,
        )

        # In a full implementation, this would save to database
        return job

    async def _run_deduplication_analysis(
        self, job: IngestionJob, file_bytes: bytes, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run comprehensive deduplication analysis."""
        analysis = {
            "strategies_applied": [],
            "duplicates_found": [],
            "confidence_scores": {},
        }

        # Run different deduplication strategies
        strategies = [
            DeduplicationStrategy.FILE_HASH,
            DeduplicationStrategy.BUSINESS_RULES,
            DeduplicationStrategy.TEMPORAL,
            DeduplicationStrategy.FUZZY_MATCHING,
        ]

        for strategy in strategies:
            try:
                strategy_result = await self._apply_deduplication_strategy(
                    strategy, job, file_bytes, metadata
                )
                analysis["strategies_applied"].append(strategy.value)
                analysis["confidence_scores"][strategy.value] = strategy_result.get("confidence", 0.0)

                if strategy_result.get("duplicates"):
                    analysis["duplicates_found"].extend(strategy_result["duplicates"])

            except Exception as e:
                logger.warning(f"Deduplication strategy {strategy.value} failed: {e}")

        return analysis

    async def _apply_deduplication_strategy(
        self,
        strategy: DeduplicationStrategy,
        job: IngestionJob,
        file_bytes: bytes,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply a specific deduplication strategy."""
        # This is a placeholder implementation
        # Each strategy would have its own logic for detecting duplicates

        if strategy == DeduplicationStrategy.FILE_HASH:
            # File hash deduplication is already handled in _check_existing_ingestion
            return {"confidence": 1.0, "duplicates": []}

        elif strategy == DeduplicationStrategy.BUSINESS_RULES:
            # Check for duplicates based on vendor + amount + date
            return await self._business_rules_deduplication(job, metadata)

        elif strategy == DeduplicationStrategy.TEMPORAL:
            # Check for duplicates within time windows
            return await self._temporal_deduplication(job, metadata)

        elif strategy == DeduplicationStrategy.FUZZY_MATCHING:
            # Check for similar content using fuzzy matching
            return await self._fuzzy_matching_deduplication(job, file_bytes)

        return {"confidence": 0.0, "duplicates": []}

    async def _business_rules_deduplication(
        self, job: IngestionJob, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Business rules deduplication based on vendor + amount + date."""
        # Placeholder implementation
        # Would extract vendor, amount, and date from metadata and check database
        return {"confidence": 0.0, "duplicates": []}

    async def _temporal_deduplication(
        self, job: IngestionJob, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Temporal deduplication within time windows."""
        # Placeholder implementation
        # Would check for similar files uploaded within specified time windows
        return {"confidence": 0.0, "duplicates": []}

    async def _fuzzy_matching_deduplication(
        self, job: IngestionJob, file_bytes: bytes
    ) -> Dict[str, Any]:
        """Fuzzy matching based on content similarity."""
        # Placeholder implementation
        # Would use text similarity algorithms or content hashing
        return {"confidence": 0.0, "duplicates": []}

    async def _queue_processing_task(self, job: IngestionJob, storage_info: Dict[str, Any]) -> None:
        """Queue background processing task."""
        # This would integrate with Celery or similar task queue
        # For now, just log the action
        logger.info(f"Would queue processing task for job {job.id}")

    def _estimate_processing_time(self, file_bytes: bytes, mime_type: str) -> int:
        """Estimate processing time in seconds based on file size and type."""
        base_time = 2  # Base processing time
        size_factor = len(file_bytes) / (1024 * 1024)  # Size in MB

        if mime_type == "application/pdf":
            return int(base_time + size_factor * 5)
        elif mime_type.startswith("image/"):
            return int(base_time + size_factor * 2)
        else:
            return int(base_time + size_factor * 3)

    async def _generate_url_token(self, job_id: str) -> str:
        """Generate unique signed URL token."""
        # Generate cryptographically secure token
        token_data = f"{job_id}:{datetime.now(timezone.utc).isoformat()}:{uuid.uuid4()}"
        return hashlib.sha256(token_data.encode()).hexdigest()

    async def _generate_local_signed_url(
        self, job: IngestionJob, url_token: str, expires_at: datetime
    ) -> str:
        """Generate signed URL for local storage."""
        # This would generate a URL with authentication parameters
        # For now, return a placeholder URL
        base_url = settings.BASE_URL or "http://localhost:8000"
        return f"{base_url}/api/v1/ingestion/files/{url_token}"

    async def _apply_duplicate_resolution(
        self, duplicate: DuplicateRecord, resolution: DuplicateResolution, db: AsyncSession
    ) -> None:
        """Apply the specified duplicate resolution action."""
        # This would implement the logic for each resolution type
        if resolution == DuplicateResolution.AUTO_IGNORE:
            # Mark ingestion job as ignored
            pass
        elif resolution == DuplicateResolution.AUTO_MERGE:
            # Merge data from duplicate with existing
            pass
        elif resolution == DuplicateResolution.REPLACE_EXISTING:
            # Replace existing record with new one
            pass
        elif resolution == DuplicateResolution.ARCHIVE_EXISTING:
            # Archive existing record and process new one
            pass
        # MANUAL_REVIEW requires no automatic action