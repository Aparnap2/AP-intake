"""
Celery background tasks for export processing.
"""

import logging
import uuid
from datetime import datetime, timedelta

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.models.export_models import ExportJob, ExportStatus
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "export_tasks",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True)
def process_export_job(self, job_id: str):
    """Process an export job in the background."""
    logger.info(f"Starting background export job processing: {job_id}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Get export job
            job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not job:
                logger.error(f"Export job not found: {job_id}")
                return {"status": "error", "message": "Export job not found"}

            # Update job status
            job.status = ExportStatus.PREPARING
            job.started_at = datetime.utcnow()
            db.commit()

            # Create export service and process
            export_service = ExportService(db=db)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(export_service._execute_export_job(job_id))
            finally:
                loop.close()

            return {"status": "completed", "job_id": job_id}

        except Exception as e:
            logger.error(f"Error processing export job {job_id}: {e}")
            # Mark job as failed
            job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if job:
                job.status = ExportStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                job.retry_count += 1
                db.commit()
            return {"status": "error", "message": str(e)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Fatal error in export job processing: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_old_exports():
    """Clean up old export files and completed jobs."""
    logger.info("Starting cleanup of old exports")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Find completed jobs older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            old_jobs = db.query(ExportJob).filter(
                ExportJob.status == ExportStatus.COMPLETED,
                ExportJob.completed_at < cutoff_date
            ).all()

            for job in old_jobs:
                # Clean up files if they exist
                if job.file_path:
                    try:
                        import os
                        if os.path.exists(job.file_path):
                            os.remove(job.file_path)
                            logger.info(f"Removed old export file: {job.file_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove export file {job.file_path}: {e}")

                # Mark job as cleaned up
                job.status = ExportStatus.CANCELLED  # Use cancelled as cleanup status
                db.commit()

            logger.info(f"Cleaned up {len(old_jobs)} old export jobs")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during export cleanup: {e}")


@celery_app.task
def retry_failed_exports():
    """Retry failed export jobs with exponential backoff."""
    logger.info("Starting retry of failed exports")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Find failed jobs that haven't exceeded max retries
            failed_jobs = db.query(ExportJob).filter(
                ExportJob.status == ExportStatus.FAILED,
                ExportJob.retry_count < ExportJob.max_retries
            ).all()

            for job in failed_jobs:
                # Calculate delay based on retry count (exponential backoff)
                delay = (2 ** job.retry_count) * 60  # 1min, 2min, 4min, 8min

                # Schedule retry
                process_export_job.apply_async(
                    args=[str(job.id)],
                    countdown=delay,
                    retry=True,
                    retry_policy={
                        'max_retries': 3,
                        'interval_start': 60,
                        'interval_step': 60,
                        'interval_max': 300,
                    }
                )

                logger.info(f"Scheduled retry for export job {job.id} in {delay} seconds")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during export retry: {e}")


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-old-exports': {
        'task': 'app.workers.export_tasks.cleanup_old_exports',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'retry-failed-exports': {
        'task': 'app.workers.export_tasks.retry_failed_exports',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}