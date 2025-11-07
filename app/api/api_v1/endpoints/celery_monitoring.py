"""
API endpoints for Celery task monitoring and management.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=Dict[str, Any])
async def get_celery_status() -> Dict[str, Any]:
    """
    Get Celery worker status and statistics.
    """
    try:
        # Get inspector for worker stats
        inspect = celery_app.control.inspect()

        # Get various statistics
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        stats = inspect.stats() or {}
        registered_tasks = inspect.registered() or {}

        # Calculate metrics
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())

        return {
            "status": "healthy",
            "workers": {
                "count": len(active_tasks),
                "active_tasks": total_active,
                "scheduled_tasks": total_scheduled,
                "reserved_tasks": total_reserved,
                "registered_tasks": len(registered_tasks),
                "details": {
                    "active": active_tasks,
                    "scheduled": scheduled_tasks,
                    "reserved": reserved_tasks,
                    "stats": stats,
                    "registered": registered_tasks
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get Celery status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Celery status: {str(e)}")


@router.get("/tasks", response_model=Dict[str, Any])
async def get_task_info(
    task_id: Optional[str] = Query(None, description="Specific task ID to check"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of tasks to return")
) -> Dict[str, Any]:
    """
    Get information about Celery tasks.
    """
    try:
        inspect = celery_app.control.inspect()

        if task_id:
            # Get specific task information
            result = celery_app.AsyncResult(task_id)
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
                "date_done": str(result.date_done) if result.date_done else None,
            }
        else:
            # Get recent tasks from all workers
            active_tasks = inspect.active() or {}
            scheduled_tasks = inspect.scheduled() or {}
            reserved_tasks = inspect.reserved() or {}

            # Combine and limit tasks
            all_tasks = []

            # Add active tasks
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task["worker"] = worker
                    task["state"] = "active"
                    all_tasks.append(task)

            # Add scheduled tasks
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    task["worker"] = worker
                    task["state"] = "scheduled"
                    all_tasks.append(task)

            # Add reserved tasks
            for worker, tasks in reserved_tasks.items():
                for task in tasks:
                    task["worker"] = worker
                    task["state"] = "reserved"
                    all_tasks.append(task)

            # Sort by timestamp (newest first) and limit
            all_tasks.sort(
                key=lambda x: x.get("time_start", 0),
                reverse=True
            )

            return {
                "tasks": all_tasks[:limit],
                "total_count": len(all_tasks),
                "limit": limit
            }

    except Exception as e:
        logger.error(f"Failed to get task information: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task information: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """
    Cancel a running Celery task.
    """
    try:
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)

        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Task cancellation requested"
        }

    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@router.get("/queues", response_model=Dict[str, Any])
async def get_queue_info() -> Dict[str, Any]:
    """
    Get information about Celery queues.
    """
    try:
        from kombu import Connection
        from app.core.config import settings

        queue_info = {}
        queue_names = ["invoice_processing", "validation", "export", "email_processing", "celery"]

        with Connection(settings.REDIS_URL) as conn:
            channel = conn.channel()

            for queue_name in queue_names:
                try:
                    # Get queue information
                    queue = channel.queue_declare(queue_name, passive=True)
                    queue_info[queue_name] = {
                        "name": queue_name,
                        "message_count": queue.message_count,
                        "consumer_count": queue.consumer_count,
                        "status": "active"
                    }
                except Exception as e:
                    queue_info[queue_name] = {
                        "name": queue_name,
                        "status": "error",
                        "error": str(e)
                    }

        return {
            "queues": queue_info,
            "broker_url": settings.REDIS_URL
        }

    except Exception as e:
        logger.error(f"Failed to get queue information: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue information: {str(e)}")


@router.get("/workers", response_model=Dict[str, Any])
async def get_worker_info() -> Dict[str, Any]:
    """
    Get detailed information about Celery workers.
    """
    try:
        inspect = celery_app.control.inspect()

        # Get worker statistics
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}

        worker_info = {}

        for worker_name, worker_stats in stats.items():
            worker_info[worker_name] = {
                "name": worker_name,
                "stats": worker_stats,
                "active_tasks": len(active_tasks.get(worker_name, [])),
                "total_tasks": worker_stats.get("total", 0),
                "pool": worker_stats.get("pool", {}),
                "clock": worker_stats.get("clock", 0),
                "timestamp": worker_stats.get("timestamp", 0)
            }

        return {
            "workers": worker_info,
            "total_workers": len(worker_info)
        }

    except Exception as e:
        logger.error(f"Failed to get worker information: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker information: {str(e)}")


@router.post("/workers/scale")
async def scale_workers(
    worker_type: str = Query(..., description="Type of worker to scale"),
    concurrency: int = Query(..., ge=1, le=20, description="Number of concurrent processes")
) -> Dict[str, Any]:
    """
    Scale the number of worker processes.
    Note: This is a simplified implementation. In production, you'd use process managers.
    """
    try:
        # This is a placeholder for worker scaling
        # In a real implementation, you'd use process managers like supervisord
        # or Kubernetes to scale workers

        logger.info(f"Scale request received: {worker_type} workers to {concurrency}")

        return {
            "worker_type": worker_type,
            "target_concurrency": concurrency,
            "status": "requested",
            "message": "Worker scaling requested. Please use your process manager to apply changes."
        }

    except Exception as e:
        logger.error(f"Failed to scale workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to scale workers: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_celery_metrics() -> Dict[str, Any]:
    """
    Get Celery performance metrics.
    """
    try:
        inspect = celery_app.control.inspect()

        # Get task statistics
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        stats = inspect.stats() or {}

        # Calculate metrics
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())

        # Get total tasks processed
        total_processed = sum(
            worker_stats.get("total", 0) for worker_stats in stats.values()
        )

        return {
            "timestamp": "now",
            "tasks": {
                "active": total_active,
                "scheduled": total_scheduled,
                "reserved": total_reserved,
                "total_processed": total_processed
            },
            "workers": {
                "count": len(active_tasks),
                "details": {
                    name: {
                        "active_tasks": len(tasks),
                        "stats": stats.get(name, {})
                    }
                    for name, tasks in active_tasks.items()
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get Celery metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Celery metrics: {str(e)}")


@router.post("/maintenance/cleanup")
async def trigger_maintenance_cleanup(
    cleanup_type: str = Query("exports", description="Type of cleanup: exports, tasks, temp"),
    days_to_keep: int = Query(7, ge=1, le=365, description="Days to keep data")
) -> Dict[str, Any]:
    """
    Trigger maintenance cleanup tasks.
    """
    try:
        from app.workers.maintenance_tasks import (
            cleanup_old_exports,
            cleanup_failed_tasks,
            cleanup_temp_files
        )

        # Map cleanup types to tasks
        cleanup_tasks = {
            "exports": cleanup_old_exports,
            "tasks": cleanup_failed_tasks,
            "temp": cleanup_temp_files
        }

        if cleanup_type not in cleanup_tasks:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cleanup type. Must be one of: {list(cleanup_tasks.keys())}"
            )

        # Trigger the cleanup task
        task = cleanup_tasks[cleanup_type].delay(days_to_keep=days_to_keep)

        return {
            "task_id": task.id,
            "cleanup_type": cleanup_type,
            "days_to_keep": days_to_keep,
            "status": "triggered",
            "message": f"Maintenance cleanup task triggered: {task.id}"
        }

    except Exception as e:
        logger.error(f"Failed to trigger maintenance cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger maintenance cleanup: {str(e)}")


@router.post("/maintenance/health-check")
async def trigger_health_check() -> Dict[str, Any]:
    """
    Trigger system health check.
    """
    try:
        from app.workers.maintenance_tasks import health_check

        # Trigger health check task
        task = health_check.delay()

        return {
            "task_id": task.id,
            "status": "triggered",
            "message": f"Health check task triggered: {task.id}"
        }

    except Exception as e:
        logger.error(f"Failed to trigger health check: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger health check: {str(e)}")


@router.get("/beat/schedule", response_model=Dict[str, Any])
async def get_beat_schedule() -> Dict[str, Any]:
    """
    Get current Celery Beat schedule.
    """
    try:
        from app.workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        return {
            "schedule": schedule,
            "total_tasks": len(schedule)
        }

    except Exception as e:
        logger.error(f"Failed to get Beat schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Beat schedule: {str(e)}")