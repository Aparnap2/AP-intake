"""
Celery background tasks for export processing, staged exports, and approvals.
"""

import logging
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.models.export_models import ExportJob, ExportStatus, ExportSchedule
from app.models.invoice import Invoice, InvoiceExtraction, StagedExport
from app.models.approval_models import ApprovalRequest, ApprovalStatus
from app.services.export_service import ExportService
from app.services.approval_service import ApprovalService
from app.services.erp_adapter_service import ERPAdapterService
from app.services.storage_service import StorageService
from app.services.notification_service import NotificationService

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

        finally:
            db.close()

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


@celery_app.task(bind=True)
def process_staged_export_approval(self, approval_request_id: str):
    """Process a staged export after approval."""
    logger.info(f"Processing staged export approval: {approval_request_id}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Get approval request
            approval_request = db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_request_id
            ).first()

            if not approval_request:
                logger.error(f"Approval request not found: {approval_request_id}")
                return {"status": "error", "message": "Approval request not found"}

            if approval_request.entity_type != "staged_export":
                logger.error(f"Invalid entity type: {approval_request.entity_type}")
                return {"status": "error", "message": "Invalid entity type"}

            # Get staged export
            staged_export = db.query(StagedExport).filter(
                StagedExport.id == approval_request.entity_id
            ).first()

            if not staged_export:
                logger.error(f"Staged export not found: {approval_request.entity_id}")
                return {"status": "error", "message": "Staged export not found"}

            # Generate final export file
            export_service = ExportService(db=db)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Get invoice data
                invoice = db.query(Invoice).filter(Invoice.id == staged_export.invoice_id).first()
                if not invoice:
                    raise Exception(f"Invoice not found: {staged_export.invoice_id}")

                extraction = db.query(InvoiceExtraction).filter(
                    InvoiceExtraction.invoice_id == invoice.id
                ).order_by(InvoiceExtraction.created_at.desc()).first()

                if not extraction:
                    raise Exception(f"No extraction found for invoice: {invoice.id}")

                # Prepare invoice data
                invoice_data = {
                    "header": extraction.header_json,
                    "lines": extraction.lines_json,
                    "metadata": {
                        "invoice_id": str(invoice.id),
                        "export_id": str(staged_export.id),
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                        "approved_by": approval_request.requested_by
                    }
                }

                # Generate export content
                if staged_export.format == "csv":
                    content = loop.run_until_complete(export_service.export_to_csv(invoice_data))
                    filename = f"approved_export_{staged_export.id}.csv"
                elif staged_export.format == "json":
                    content = loop.run_until_complete(export_service.export_to_json(invoice_data))
                    filename = f"approved_export_{staged_export.id}.json"
                else:
                    raise Exception(f"Unsupported export format: {staged_export.format}")

                # Save export file
                storage_service = StorageService()
                file_path = f"exports/approved/{filename}"
                loop.run_until_complete(storage_service.upload_file(file_path, content.encode('utf-8')))

                # Update staged export
                staged_export.status = "exported"
                staged_export.file_name = file_path
                staged_export.export_job_id = f"approved_{staged_export.id}"
                db.commit()

                # Send notification
                notification_service = NotificationService()
                loop.run_until_complete(notification_service.send_export_completion_notification(
                    approval_request.requested_by,
                    staged_export.id,
                    file_path
                ))

                logger.info(f"Successfully processed staged export approval: {approval_request_id}")
                return {
                    "status": "completed",
                    "approval_request_id": approval_request_id,
                    "staged_export_id": str(staged_export.id),
                    "file_path": file_path
                }

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error processing staged export approval {approval_request_id}: {e}")
            return {"status": "error", "message": str(e)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Fatal error in staged export approval processing: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True)
def export_to_erp_system(self, invoice_id: str, erp_system_type: str, environment: str = "sandbox"):
    """Export invoice to ERP system."""
    logger.info(f"Exporting invoice {invoice_id} to {erp_system_type}")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Get invoice and extraction data
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise Exception(f"Invoice not found: {invoice_id}")

            extraction = db.query(InvoiceExtraction).filter(
                InvoiceExtraction.invoice_id == invoice_id
            ).order_by(InvoiceExtraction.created_at.desc()).first()

            if not extraction:
                raise Exception(f"No extraction found for invoice: {invoice_id}")

            # Prepare invoice data
            invoice_data = {
                "header": extraction.header_json,
                "lines": extraction.lines_json,
                "metadata": {
                    "invoice_id": str(invoice.id),
                    "export_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            # Export to ERP
            erp_service = ERPAdapterService(db=db)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                from app.services.erp_adapter_service import ERPSystemType, ERPEnvironment, ERPAction

                result = loop.run_until_complete(erp_service.export_invoice_to_erp(
                    invoice_data,
                    ERPSystemType(erp_system_type),
                    ERPEnvironment(environment),
                    ERPAction.CREATE_VENDOR_BILL
                ))

                if result.success:
                    # Create export record
                    export_record = StagedExport(
                        invoice_id=invoice.id,
                        payload_json=invoice_data,
                        format=erp_system_type,
                        status="exported",
                        destination=f"{erp_system_type}_{environment}",
                        export_job_id=result.external_id
                    )
                    db.add(export_record)
                    db.commit()

                    logger.info(f"Successfully exported invoice {invoice_id} to {erp_system_type}")
                    return {
                        "status": "completed",
                        "invoice_id": invoice_id,
                        "erp_system": erp_system_type,
                        "external_id": result.external_id,
                        "message": result.message
                    }
                else:
                    logger.error(f"ERP export failed: {result.message}")
                    return {
                        "status": "error",
                        "invoice_id": invoice_id,
                        "erp_system": erp_system_type,
                        "error_message": result.message
                    }

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error exporting invoice {invoice_id} to {erp_system_type}: {e}")
            return {"status": "error", "message": str(e)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Fatal error in ERP export: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True)
def schedule_recurring_exports(self):
    """Schedule and process recurring export jobs."""
    logger.info("Processing recurring export schedules")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Get export schedules
            now = datetime.now(timezone.utc)
            due_schedules = db.query(ExportSchedule).filter(
                ExportSchedule.is_active == True,
                ExportSchedule.next_run_at <= now
            ).all()

            processed_schedules = []
            failed_schedules = []

            for schedule in due_schedules:
                try:
                    # Create export job from schedule
                    from app.schemas.export_schemas import ExportRequest, ExportConfig, ExportDestination

                    export_request = ExportRequest(
                        export_config=ExportConfig(
                            template_id=schedule.template_id,
                            destination=ExportDestination.FILE_STORAGE,
                            destination_config=schedule.destination_config,
                            batch_size=1000,
                            notify_on_completion=True,
                            notification_config=schedule.notification_config
                        ),
                        filters=schedule.filters,
                        priority=5
                    )

                    # Create export job
                    export_service = ExportService(db=db)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        response = loop.run_until_complete(export_service.create_export_job(
                            request=export_request,
                            user_id="system_scheduler"
                        ))

                        # Update schedule next run time
                        from celery.schedules import crontab
                        cron = crontab(schedule.cron_expression)
                        schedule.next_run_at = cron.now().astimezone(timezone.utc)
                        schedule.total_runs += 1
                        schedule.last_run_at = now
                        db.commit()

                        processed_schedules.append({
                            "schedule_id": str(schedule.id),
                            "name": schedule.name,
                            "export_job_id": str(response.export_id)
                        })

                    finally:
                        loop.close()

                except Exception as e:
                    logger.error(f"Failed to process schedule {schedule.id}: {e}")
                    failed_schedules.append({
                        "schedule_id": str(schedule.id),
                        "name": schedule.name,
                        "error": str(e)
                    })

            logger.info(f"Processed {len(processed_schedules)} schedules, {len(failed_schedules)} failed")
            return {
                "status": "completed",
                "processed_count": len(processed_schedules),
                "failed_count": len(failed_schedules)
            }

        except Exception as e:
            logger.error(f"Error processing recurring exports: {e}")
            return {"status": "error", "message": str(e)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Fatal error in recurring exports: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task
def generate_export_report(report_type: str = "daily"):
    """Generate export usage reports."""
    logger.info(f"Generating {report_type} export report")

    try:
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Calculate date range
            now = datetime.now(timezone.utc)
            if report_type == "daily":
                start_date = now - timedelta(days=1)
            elif report_type == "weekly":
                start_date = now - timedelta(weeks=1)
            elif report_type == "monthly":
                start_date = now - timedelta(days=30)
            else:
                raise Exception(f"Unsupported report type: {report_type}")

            # Get export statistics
            exports = db.query(ExportJob).filter(
                ExportJob.created_at >= start_date,
                ExportJob.created_at <= now
            ).all()

            # Calculate statistics
            total_exports = len(exports)
            successful_exports = len([e for e in exports if e.status == ExportStatus.COMPLETED])
            failed_exports = len([e for e in exports if e.status == ExportStatus.FAILED])

            total_records = sum(e.record_count or 0 for e in exports)
            total_file_size = sum(e.file_size or 0 for e in exports)

            # Group by format
            exports_by_format = {}
            for export in exports:
                format_key = export.format.value
                if format_key not in exports_by_format:
                    exports_by_format[format_key] = 0
                exports_by_format[format_key] += 1

            report_data = {
                "report_type": report_type,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": now.isoformat()
                },
                "summary": {
                    "total_exports": total_exports,
                    "successful_exports": successful_exports,
                    "failed_exports": failed_exports,
                    "success_rate": (successful_exports / total_exports * 100) if total_exports > 0 else 0,
                    "total_records": total_records,
                    "total_file_size_mb": total_file_size / (1024 * 1024)
                },
                "by_format": exports_by_format,
                "generated_at": now.isoformat()
            }

            # Save report to storage
            storage_service = StorageService()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                import json
                report_filename = f"export_report_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.json"
                report_path = f"reports/{report_filename}"
                report_content = json.dumps(report_data, indent=2)

                loop.run_until_complete(storage_service.upload_file(report_path, report_content.encode('utf-8')))

                logger.info(f"Generated {report_type} export report: {report_path}")
                return {
                    "status": "completed",
                    "report_type": report_type,
                    "report_path": report_path
                }

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error generating {report_type} export report: {e}")
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
    'schedule-recurring-exports': {
        'task': 'app.workers.export_tasks.schedule_recurring_exports',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    'generate-daily-report': {
        'task': 'app.workers.export_tasks.generate_export_report',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        'args': ('daily',),
    },
    'generate-weekly-report': {
        'task': 'app.workers.export_tasks.generate_export_report',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Monday at 4 AM
        'args': ('weekly',),
    },
}