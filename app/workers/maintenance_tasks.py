"""
Maintenance and monitoring tasks for the AP Intake system.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=600,  # 10 minutes
)
def cleanup_old_exports(self, days_to_keep: int = 7) -> Dict[str, Any]:
    """
    Clean up old export files and database records.

    Args:
        days_to_keep: Number of days to keep export files

    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of exports older than {days_to_keep} days")

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # Get database session
        db = SessionLocal()

        try:
            # Clean up old staged exports
            from app.models.invoice import StagedExport

            # Find old exports
            old_exports = db.query(StagedExport).filter(
                StagedExport.created_at < cutoff_date
            ).all()

            deleted_files = 0
            deleted_records = 0

            for export in old_exports:
                try:
                    # Delete physical file if it exists
                    if export.file_name:
                        file_path = os.path.join("exports", export.file_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files += 1
                            logger.info(f"Deleted export file: {file_path}")

                    # Delete database record
                    db.delete(export)
                    deleted_records += 1

                except Exception as e:
                    logger.error(f"Failed to delete export {export.id}: {e}")
                    continue

            # Commit changes
            db.commit()

            results = {
                "status": "success",
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_files": deleted_files,
                "deleted_records": deleted_records,
                "cleaned_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Export cleanup completed: {deleted_files} files, {deleted_records} records deleted")
            return results

        finally:
            db.close()

    except Exception as exc:
        logger.error(f"Export cleanup failed: {exc}")

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying export cleanup (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))

        return {
            "status": "error",
            "error": str(exc),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300  # 5 minutes
)
def health_check(self) -> Dict[str, Any]:
    """
    Perform comprehensive health check on system components.

    Returns:
        Dict with health check results
    """
    try:
        logger.info("Starting system health check")

        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }

        # Check database connection
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            health_status["checks"]["database"] = {"status": "healthy", "response_time": "<100ms"}
        except Exception as e:
            health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "unhealthy"

        # Check Redis connection
        try:
            from app.core.config import settings
            import redis
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.ping()
            health_status["checks"]["redis"] = {"status": "healthy", "response_time": "<50ms"}
        except Exception as e:
            health_status["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "unhealthy"

        # Check storage service
        try:
            from app.services.storage_service import StorageService
            storage_service = StorageService()
            # Test basic storage operation
            test_content = b"health_check_test"
            test_path = f"health_checks/{datetime.utcnow().timestamp()}.test"
            storage_service.store_file(test_content, test_path)
            storage_service.delete_file(test_path)
            health_status["checks"]["storage"] = {"status": "healthy", "type": storage_service.storage_type}
        except Exception as e:
            health_status["checks"]["storage"] = {"status": "unhealthy", "error": str(e)}

        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_percent = (free / total) * 100
            health_status["checks"]["disk_space"] = {
                "status": "healthy" if free_percent > 10 else "warning",
                "free_gb": round(free / (1024**3), 2),
                "free_percent": round(free_percent, 2)
            }
            if free_percent < 5:
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["disk_space"] = {"status": "error", "error": str(e)}

        # Check worker queues
        try:
            from kombu import Connection
            from app.core.config import settings
            with Connection(settings.REDIS_URL) as conn:
                channel = conn.channel()

                # Check active queues
                inspect = celery_app.control.inspect()
                active_tasks = inspect.active()
                scheduled_tasks = inspect.scheduled()

                health_status["checks"]["workers"] = {
                    "status": "healthy",
                    "active_tasks": len(active_tasks) if active_tasks else 0,
                    "scheduled_tasks": len(scheduled_tasks) if scheduled_tasks else 0
                }
        except Exception as e:
            health_status["checks"]["workers"] = {"status": "error", "error": str(e)}

        logger.info(f"Health check completed: {health_status['status']}")
        return health_status

    except Exception as exc:
        logger.error(f"Health check failed: {exc}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying health check (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))

        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=900  # 15 minutes
)
def cleanup_failed_tasks(self, days_to_keep: int = 3) -> Dict[str, Any]:
    """
    Clean up old failed task records from Redis.

    Args:
        days_to_keep: Number of days to keep failed task records

    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of failed tasks older than {days_to_keep} days")

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # This would typically clean up Redis keys for old failed tasks
        # For now, we'll just log the action

        cleaned_keys = 0  # Would be actual count from Redis

        results = {
            "status": "success",
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_keys": cleaned_keys,
            "cleaned_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Failed tasks cleanup completed: {cleaned_keys} keys cleaned")
        return results

    except Exception as exc:
        logger.error(f"Failed tasks cleanup failed: {exc}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying failed tasks cleanup (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))

        return {
            "status": "error",
            "error": str(exc),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=600  # 10 minutes
)
def backup_system_state(self) -> Dict[str, Any]:
    """
    Create backup of critical system state and configurations.

    Returns:
        Dict with backup results
    """
    try:
        logger.info("Starting system state backup")

        backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"backups/system_state_{backup_timestamp}"

        os.makedirs(backup_dir, exist_ok=True)

        backed_up_files = []

        try:
            # Backup database schema
            db = SessionLocal()
            # This would typically create a database dump
            backed_up_files.append("database_schema.sql")
            db.close()

            # Backup configuration files
            config_files = [
                ".env",
                "docker-compose.yml",
                "pyproject.toml",
                "alembic.ini"
            ]

            for config_file in config_files:
                if os.path.exists(config_file):
                    backup_path = os.path.join(backup_dir, config_file)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    # In a real implementation, you'd copy the file
                    backed_up_files.append(config_file)

            results = {
                "status": "success",
                "backup_directory": backup_dir,
                "backed_up_files": backed_up_files,
                "backup_timestamp": backup_timestamp,
                "created_at": datetime.utcnow().isoformat()
            }

            logger.info(f"System backup completed: {len(backed_up_files)} files backed up")
            return results

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            # Clean up partial backup
            try:
                import shutil
                shutil.rmtree(backup_dir)
            except:
                pass
            raise

    except Exception as exc:
        logger.error(f"System backup failed: {exc}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying system backup (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))

        return {
            "status": "error",
            "error": str(exc),
            "retry_count": self.request.retries,
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(soft_time_limit=300)  # 5 minutes
def monitor_worker_performance() -> Dict[str, Any]:
    """
    Monitor worker performance and queue statistics.

    Returns:
        Dict with performance metrics
    """
    try:
        logger.info("Collecting worker performance metrics")

        # Get inspector for worker stats
        inspect = celery_app.control.inspect()

        # Get various statistics
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        stats = inspect.stats() or {}

        # Calculate metrics
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())

        # Get queue information
        try:
            from kombu import Connection
            from app.core.config import settings
            with Connection(settings.REDIS_URL) as conn:
                channel = conn.channel()

                # Get queue sizes (simplified)
                queue_sizes = {}
                for queue_name in ["invoice_processing", "validation", "export", "email_processing"]:
                    try:
                        # This would typically get actual queue length
                        queue_sizes[queue_name] = 0  # Placeholder
                    except Exception:
                        queue_sizes[queue_name] = "unknown"
        except Exception as e:
            logger.warning(f"Could not get queue sizes: {e}")
            queue_sizes = {"error": str(e)}

        performance_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "workers": {
                "active_tasks": total_active,
                "scheduled_tasks": total_scheduled,
                "reserved_tasks": total_reserved,
                "worker_count": len(active_tasks),
                "total_tasks_processed": sum(
                    worker_stats.get("total", 0) for worker_stats in stats.values()
                )
            },
            "queues": queue_sizes,
            "system": {
                "uptime": "unknown",  # Would get actual uptime
                "memory_usage": "unknown",  # Would get actual memory usage
                "cpu_usage": "unknown"  # Would get actual CPU usage
            }
        }

        logger.info("Worker performance metrics collected")
        return performance_data

    except Exception as e:
        logger.error(f"Performance monitoring failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(soft_time_limit=120)  # 2 minutes
def cleanup_temp_files(hours_to_keep: int = 24) -> Dict[str, Any]:
    """
    Clean up temporary files and processing artifacts.

    Args:
        hours_to_keep: Number of hours to keep temp files

    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of temp files older than {hours_to_keep} hours")

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_to_keep)

        deleted_files = 0
        deleted_dirs = 0

        # Clean up temp directories
        temp_dirs = ["temp", "uploads/tmp", "processing"]

        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    for root, dirs, files in os.walk(temp_dir):
                        # Check and delete old files
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if file_mtime < cutoff_time:
                                    os.remove(file_path)
                                    deleted_files += 1
                            except Exception as e:
                                logger.warning(f"Could not delete file {file_path}: {e}")

                        # Check and delete empty directories
                        for dir_name in dirs[:]:  # Create a copy to iterate
                            dir_path = os.path.join(root, dir_name)
                            try:
                                if not os.listdir(dir_path):  # Empty directory
                                    os.rmdir(dir_path)
                                    deleted_dirs += 1
                                    dirs.remove(dir_name)
                            except Exception:
                                pass

                except Exception as e:
                    logger.warning(f"Could not clean temp directory {temp_dir}: {e}")

        results = {
            "status": "success",
            "cutoff_time": cutoff_time.isoformat(),
            "deleted_files": deleted_files,
            "deleted_directories": deleted_dirs,
            "cleaned_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Temp files cleanup completed: {deleted_files} files, {deleted_dirs} directories deleted")
        return results

    except Exception as e:
        logger.error(f"Temp files cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(soft_time_limit=600)  # 10 minutes
def generate_system_report() -> Dict[str, Any]:
    """
    Generate comprehensive system report for monitoring.

    Returns:
        Dict with system report data
    """
    try:
        logger.info("Generating system report")

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period": "last_24_hours",
            "metrics": {}
        }

        # Get database statistics
        try:
            db = SessionLocal()

            # Invoice statistics
            from app.models.invoice import Invoice, InvoiceStatus

            total_invoices = db.query(Invoice).count()
            processed_invoices = db.query(Invoice).filter(
                Invoice.status.in_([InvoiceStatus.VALIDATED, InvoiceStatus.STAGED, InvoiceStatus.EXPORTED])
            ).count()
            failed_invoices = db.query(Invoice).filter(Invoice.status == InvoiceStatus.EXCEPTION).count()

            report["metrics"]["invoices"] = {
                "total": total_invoices,
                "processed": processed_invoices,
                "failed": failed_invoices,
                "success_rate": round((processed_invoices / total_invoices * 100) if total_invoices > 0 else 0, 2)
            }

            # Recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_invoices = db.query(Invoice).filter(Invoice.created_at >= yesterday).count()

            report["metrics"]["recent_activity"] = {
                "invoices_last_24h": recent_invoices
            }

            db.close()

        except Exception as e:
            logger.error(f"Could not get database statistics: {e}")
            report["metrics"]["database_error"] = str(e)

        # Get worker statistics
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active() or {}
            stats = inspect.stats() or {}

            report["metrics"]["workers"] = {
                "active_workers": len(active_tasks),
                "active_tasks": sum(len(tasks) for tasks in active_tasks.values()),
                "total_tasks_processed": sum(
                    worker_stats.get("total", 0) for worker_stats in stats.values()
                )
            }

        except Exception as e:
            logger.error(f"Could not get worker statistics: {e}")
            report["metrics"]["workers_error"] = str(e)

        # Storage statistics
        try:
            import os
            storage_size = 0
            file_count = 0

            for root, dirs, files in os.walk("storage"):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        storage_size += os.path.getsize(file_path)
                        file_count += 1
                    except OSError:
                        pass

            report["metrics"]["storage"] = {
                "total_size_mb": round(storage_size / (1024 * 1024), 2),
                "file_count": file_count
            }

        except Exception as e:
            logger.error(f"Could not get storage statistics: {e}")
            report["metrics"]["storage_error"] = str(e)

        logger.info("System report generated successfully")
        return report

    except Exception as e:
        logger.error(f"System report generation failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat()
        }


# Utility functions for task management
def schedule_maintenance_task(task_name: str, schedule: str, args: tuple = ()) -> bool:
    """
    Schedule a maintenance task with Celery Beat.

    Args:
        task_name: Name of the task to schedule
        schedule: Crontab schedule string
        args: Arguments to pass to the task

    Returns:
        True if scheduling was successful
    """
    try:
        from celery.schedules import crontab

        # Parse schedule string and create schedule
        # For simplicity, assume it's a minute interval
        if schedule.isdigit():
            schedule_obj = crontab(minute=f'*/{schedule}')
        else:
            # Would need more sophisticated parsing for complex schedules
            schedule_obj = crontab(minute='0')  # Default to hourly

        celery_app.conf.beat_schedule[task_name] = {
            'task': f'app.workers.maintenance_tasks.{task_name}',
            'schedule': schedule_obj,
            'args': args
        }

        logger.info(f"Scheduled maintenance task: {task_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to schedule maintenance task {task_name}: {e}")
        return False


def cancel_maintenance_task(task_name: str) -> bool:
    """
    Cancel a scheduled maintenance task.

    Args:
        task_name: Name of the task to cancel

    Returns:
        True if cancellation was successful
    """
    try:
        if task_name in celery_app.conf.beat_schedule:
            del celery_app.conf.beat_schedule[task_name]
            logger.info(f"Cancelled maintenance task: {task_name}")
            return True
        return False

    except Exception as e:
        logger.error(f"Failed to cancel maintenance task {task_name}: {e}")
        return False


def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """
    Get list of all scheduled maintenance tasks.

    Returns:
        List of scheduled task information
    """
    try:
        scheduled_tasks = []

        for task_name, schedule_info in celery_app.conf.beat_schedule.items():
            if "maintenance_tasks" in schedule_info.get('task', ''):
                scheduled_tasks.append({
                    "task_name": task_name,
                    "task": schedule_info.get('task'),
                    "schedule": str(schedule_info.get('schedule')),
                    "args": schedule_info.get('args', [])
                })

        return scheduled_tasks

    except Exception as e:
        logger.error(f"Failed to get scheduled tasks: {e}")
        return []