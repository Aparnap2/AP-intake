"""
Background tasks for ingestion processing with comprehensive error handling and retry logic.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List

from celery import Task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ingestion import (
    IngestionJob,
    DuplicateRecord,
    IngestionStatus,
    DeduplicationStrategy,
    DuplicateResolution,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.services.ingestion_service import IngestionService
from app.services.deduplication_service import DeduplicationService
from app.services.docling_service import DoclingService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class IngestionTask(Task):
    """Base task with enhanced database session and error handling for ingestion."""

    def __init__(self):
        self.db = None
        self.ingestion_service = None
        self.deduplication_service = None
        self.docling_service = None

    def on_success(self, retval, task_id, args, kwargs):
        """Cleanup after successful task completion."""
        if self.db:
            self.db.close()
            self.db = None
        logger.info(f"Ingestion task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Enhanced cleanup and error logging after task failure."""
        if self.db:
            self.db.close()
            self.db = None
        logger.error(f"Ingestion task {task_id} failed: {exc}", exc_info=einfo)

    def get_db(self) -> Session:
        """Get database session for this task."""
        if not self.db:
            self.db = SessionLocal()
        return self.db

    def get_services(self):
        """Initialize service instances."""
        if not self.ingestion_service:
            self.ingestion_service = IngestionService()
        if not self.deduplication_service:
            self.deduplication_service = DeduplicationService()
        if not self.docling_service:
            self.docling_service = DoclingService()


@celery_app.task(bind=True, base=IngestionTask, max_retries=5, default_retry_delay=60)
def process_ingestion_task(
    self, ingestion_job_id: str, **kwargs
) -> Dict[str, Any]:
    """
    Process an ingestion job through the complete pipeline.

    This task handles:
    - File validation and metadata extraction
    - Duplicate detection and resolution
    - Document parsing with Docling
    - Business validation
    - Invoice creation and workflow initiation
    """
    logger.info(f"Processing ingestion job {ingestion_job_id} (task: {self.request.id})")

    try:
        # Get database session and services
        db = self.get_db()
        self.get_services()

        # Get ingestion job
        job = db.query(IngestionJob).filter(IngestionJob.id == ingestion_job_id).first()
        if not job:
            raise ValueError(f"Ingestion job {ingestion_job_id} not found")

        # Update job status
        job.status = IngestionStatus.PROCESSING
        job.processing_started_at = datetime.now(timezone.utc)
        db.commit()

        # Run the ingestion pipeline in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _process_ingestion_pipeline(job, db, self.ingestion_service,
                                          self.deduplication_service, self.docling_service)
            )
        finally:
            loop.close()

        # Update job completion status
        job.processing_completed_at = datetime.now(timezone.utc)
        if job.processing_started_at:
            duration = job.processing_completed_at - job.processing_started_at
            job.processing_duration_ms = int(duration.total_seconds() * 1000)

        db.commit()

        logger.info(f"Successfully processed ingestion job {ingestion_job_id}")
        return {
            "ingestion_job_id": ingestion_job_id,
            "status": job.status.value,
            "processing_duration_ms": job.processing_duration_ms,
            "invoice_id": result.get("invoice_id"),
            "duplicates_found": result.get("duplicates_found", 0),
            "requires_human_review": result.get("requires_human_review", False),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(f"Failed to process ingestion job {ingestion_job_id}: {exc}")

        # Update job status on failure
        try:
            db = self.get_db()
            job = db.query(IngestionJob).filter(IngestionJob.id == ingestion_job_id).first()
            if job:
                job.status = IngestionStatus.FAILED
                job.error_message = str(exc)
                job.retry_count = self.request.retries

                # Mark for retry if possible
                if self.request.retries < self.max_retries:
                    retry_delay = 60 * (2 ** self.request.retries)  # Exponential backoff
                    logger.info(f"Retrying ingestion job {ingestion_job_id} in {retry_delay}s")
                    raise self.retry(countdown=retry_delay, exc=exc)
                else:
                    job.error_code = "MAX_RETRIES_EXCEEDED"
                    logger.error(f"Max retries exceeded for ingestion job {ingestion_job_id}")

                db.commit()

        except Exception as db_exc:
            logger.error(f"Failed to update ingestion job status: {db_exc}")

        raise exc


@celery_app.task(bind=True, base=IngestionTask, max_retries=3, default_retry_delay=30)
def resolve_duplicates_task(
    self, ingestion_job_id: str, duplicate_group_id: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """
    Resolve duplicates for an ingestion job automatically or prepare for manual review.
    """
    logger.info(f"Resolving duplicates for ingestion job {ingestion_job_id}")

    try:
        db = self.get_db()
        self.get_services()

        # Get ingestion job
        job = db.query(IngestionJob).filter(IngestionJob.id == ingestion_job_id).first()
        if not job:
            raise ValueError(f"Ingestion job {ingestion_job_id} not found")

        # Get duplicate records
        duplicates = db.query(DuplicateRecord).filter(
            DuplicateRecord.ingestion_job_id == ingestion_job_id
        ).all()

        if not duplicates:
            logger.info(f"No duplicates found for job {ingestion_job_id}")
            return {"ingestion_job_id": ingestion_job_id, "duplicates_resolved": 0}

        # Run duplicate resolution logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            resolution_result = loop.run_until_complete(
                _resolve_duplicate_group(job, duplicates, db, self.deduplication_service)
            )
        finally:
            loop.close()

        logger.info(f"Resolved {resolution_result['resolved_count']} duplicates for job {ingestion_job_id}")
        return {
            "ingestion_job_id": ingestion_job_id,
            "duplicates_resolved": resolution_result["resolved_count"],
            "auto_resolved": resolution_result["auto_resolved"],
            "manual_review_required": resolution_result["manual_review_required"],
            "resolution_summary": resolution_result["summary"],
        }

    except Exception as exc:
        logger.error(f"Failed to resolve duplicates for job {ingestion_job_id}: {exc}")

        # Retry task if possible
        if self.request.retries < self.max_retries:
            retry_delay = 30 * (2 ** self.request.retries)
            raise self.retry(countdown=retry_delay, exc=exc)
        else:
            raise exc


@celery_app.task(bind=True, base=IngestionTask, max_retries=2, default_retry_delay=15)
def cleanup_expired_ingestion_data_task(self, days_to_keep: int = 90, **kwargs) -> Dict[str, Any]:
    """
    Clean up old ingestion data to maintain system performance.
    """
    logger.info(f"Starting cleanup of ingestion data older than {days_to_keep} days")

    try:
        db = self.get_db()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        # Clean up old ingestion jobs
        old_jobs = db.query(IngestionJob).filter(
            IngestionJob.created_at < cutoff_date,
            IngestionJob.status.in_([IngestionStatus.COMPLETED, IngestionStatus.FAILED])
        ).all()

        cleanup_stats = {
            "total_jobs_checked": len(old_jobs),
            "jobs_deleted": 0,
            "duplicates_deleted": 0,
            "storage_freed_bytes": 0,
            "cutoff_date": cutoff_date.isoformat(),
        }

        for job in old_jobs:
            try:
                # Delete associated duplicate records
                duplicates = db.query(DuplicateRecord).filter(
                    DuplicateRecord.ingestion_job_id == job.id
                ).all()
                for dup in duplicates:
                    db.delete(dup)
                    cleanup_stats["duplicates_deleted"] += 1

                # Delete storage files if possible
                try:
                    # This would integrate with storage service to delete files
                    storage_freed = job.file_size_bytes
                    cleanup_stats["storage_freed_bytes"] += storage_freed
                except Exception as storage_exc:
                    logger.warning(f"Failed to delete storage file for job {job.id}: {storage_exc}")

                # Delete the job
                db.delete(job)
                cleanup_stats["jobs_deleted"] += 1

            except Exception as job_exc:
                logger.error(f"Failed to cleanup job {job.id}: {job_exc}")

        db.commit()

        logger.info(f"Cleanup completed: {cleanup_stats}")
        return {
            "task": "cleanup_expired_ingestion_data",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "statistics": cleanup_stats,
        }

    except Exception as exc:
        logger.error(f"Cleanup task failed: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=15 * (2 ** self.request.retries), exc=exc)
        else:
            raise exc


async def _process_ingestion_pipeline(
    job: IngestionJob,
    db: Session,
    ingestion_service: IngestionService,
    deduplication_service: DeduplicationService,
    docling_service: DoclingService,
) -> Dict[str, Any]:
    """Process the complete ingestion pipeline for a job."""
    result = {
        "duplicates_found": 0,
        "requires_human_review": False,
        "invoice_id": None,
    }

    try:
        # Step 1: Retrieve file content
        file_content = await ingestion_service.storage_service.get_file_content(job.storage_path)

        # Step 2: Extract metadata if not already done
        if not job.extracted_metadata:
            metadata = await ingestion_service._extract_file_metadata(
                file_content, job.original_filename, job.mime_type, job.file_hash_sha256
            )
            job.extracted_metadata = metadata
            db.commit()

        # Step 3: Run deduplication analysis
        duplicate_analysis = await deduplication_service.analyze_for_duplicates(
            ingestion_job=job,
            file_content=file_content,
            extracted_metadata=job.extracted_metadata,
            db=db,
        )
        result["duplicates_found"] = len(duplicate_analysis)

        # Step 4: Determine if human review is needed
        high_confidence_duplicates = [
            dup for dup in duplicate_analysis
            if dup["confidence_score"] >= 0.95
        ]

        if high_confidence_duplicates:
            # Likely duplicates - require review
            job.status = IngestionStatus.REQUIRE_REVIEW
            job.is_duplicate = True
            result["requires_human_review"] = True

            # Set duplicate group ID
            if high_confidence_duplicates:
                import uuid
                job.duplicate_group_id = uuid.uuid4()

            db.commit()
            return result

        # Step 5: Extract document data with Docling
        extraction_result = await docling_service.extract_from_content(
            file_content=file_content,
            file_path=job.storage_path
        )

        # Step 6: Create invoice record
        from app.models.invoice import Invoice

        invoice = Invoice(
            vendor_id=job.vendor_id,
            file_url=job.storage_path,
            file_hash=job.file_hash_sha256,
            file_name=job.original_filename,
            file_size=f"{job.file_size_bytes / (1024*1024):.1f}MB",
            status=InvoiceStatus.RECEIVED,
            workflow_state="ingested",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        # Step 7: Create extraction record
        from app.models.invoice import InvoiceExtraction

        extraction = InvoiceExtraction(
            invoice_id=invoice.id,
            header_json=extraction_result.header.model_dump(),
            lines_json=[line.model_dump() for line in extraction_result.lines],
            confidence_json=extraction_result.confidence.model_dump(),
            parser_version=extraction_result.metadata.parser_version,
            processing_time_ms=str(extraction_result.metadata.processing_time_ms),
            page_count=str(extraction_result.metadata.page_count),
        )
        db.add(extraction)

        # Step 8: Update job status
        job.status = IngestionStatus.COMPLETED
        result["invoice_id"] = str(invoice.id)

        db.commit()

        # Step 9: Queue standard invoice processing
        from app.workers.invoice_tasks import process_invoice_task
        process_invoice_task.delay(
            str(invoice.id),
            job.storage_path,
            job.file_hash_sha256
        )

        return result

    except Exception as e:
        logger.error(f"Ingestion pipeline failed for job {job.id}: {e}")
        job.status = IngestionStatus.FAILED
        job.error_message = str(e)
        db.commit()
        raise


async def _resolve_duplicate_group(
    job: IngestionJob,
    duplicates: List[DuplicateRecord],
    db: Session,
    deduplication_service: DeduplicationService,
) -> Dict[str, Any]:
    """Resolve a group of duplicates automatically or prepare for manual review."""
    result = {
        "resolved_count": 0,
        "auto_resolved": 0,
        "manual_review_required": 0,
        "summary": [],
    }

    for duplicate in duplicates:
        try:
            # Determine resolution action based on confidence and strategy
            if duplicate.confidence_score >= 0.98:
                # Very high confidence - auto-ignore
                resolution = DuplicateResolution.AUTO_IGNORE
                duplicate.resolution_action = resolution
                duplicate.resolved_by = "system_auto"
                duplicate.resolved_at = datetime.now(timezone.utc)
                duplicate.status = "resolved"
                result["auto_resolved"] += 1
                result["summary"].append(f"Auto-ignored duplicate (confidence: {duplicate.confidence_score:.3f})")

            elif duplicate.confidence_score >= 0.90:
                # High confidence - mark for manual review
                duplicate.requires_human_review = True
                result["manual_review_required"] += 1
                result["summary"].append(f"Marked for manual review (confidence: {duplicate.confidence_score:.3f})")

            else:
                # Lower confidence - mark for manual review
                duplicate.requires_human_review = True
                result["manual_review_required"] += 1
                result["summary"].append(f"Low confidence - manual review required (confidence: {duplicate.confidence_score:.3f})")

            result["resolved_count"] += 1

        except Exception as e:
            logger.error(f"Failed to resolve duplicate {duplicate.id}: {e}")
            result["summary"].append(f"Failed to resolve duplicate {duplicate.id}: {str(e)}")

    # Update job status based on resolution results
    if result["manual_review_required"] > 0:
        job.status = IngestionStatus.REQUIRE_REVIEW
        job.is_duplicate = True
    else:
        job.status = IngestionStatus.COMPLETED

    db.commit()
    return result


# Schedule periodic cleanup task
@celery_app.task
def schedule_periodic_cleanup():
    """Schedule periodic cleanup of old ingestion data."""
    cleanup_expired_ingestion_data_task.delay(days_to_keep=90)


# Configure periodic task (this would typically be in celery beat configuration)
# This is just a placeholder for the configuration
CELERYBEAT_SCHEDULE = {
    'cleanup-ingestion-data': {
        'task': 'app.workers.ingestion_tasks.schedule_periodic_cleanup',
        'schedule': timedelta(hours=24),  # Run daily
    },
}