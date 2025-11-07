"""
System status and monitoring endpoints.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.workers.celery_app import celery_app
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get comprehensive system status."""
    try:
        # Invoice statistics
        total_invoices = db.query(Invoice).count()
        status_counts = db.query(
            Invoice.status,
            func.count(Invoice.id).label('count')
        ).group_by(Invoice.status).all()

        invoice_stats = {
            "total": total_invoices,
            "by_status": {status.value: count for status, count in status_counts}
        }

        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_invoices = db.query(Invoice).filter(Invoice.created_at >= yesterday).count()
        recent_processed = db.query(Invoice).filter(
            Invoice.created_at >= yesterday,
            Invoice.status.in_([InvoiceStatus.VALIDATED, InvoiceStatus.READY, InvoiceStatus.STAGED])
        ).count()

        activity_stats = {
            "last_24h": {
                "uploaded": recent_invoices,
                "processed": recent_processed,
                "processing_rate": f"{(recent_processed / max(recent_invoices, 1) * 100):.1f}%"
            }
        }

        # Worker status
        worker_stats = await _get_worker_stats()

        # System health
        health_stats = await _get_health_stats(db)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "invoice_stats": invoice_stats,
            "activity_stats": activity_stats,
            "worker_stats": worker_stats,
            "health_stats": health_stats,
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Failed to retrieve system status",
            "details": str(e),
        }


async def _get_worker_stats() -> Dict[str, Any]:
    """Get Celery worker statistics."""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()

        if stats:
            total_workers = len(stats)
            total_active_tasks = sum(len(tasks) for tasks in active.values()) if active else 0

            return {
                "workers_online": total_workers,
                "active_tasks": total_active_tasks,
                "workers": list(stats.keys()) if stats else [],
                "status": "healthy" if total_workers > 0 else "unhealthy"
            }
        else:
            return {
                "workers_online": 0,
                "active_tasks": 0,
                "workers": [],
                "status": "unhealthy",
                "message": "No workers detected"
            }

    except Exception as e:
        logger.error(f"Error getting worker stats: {e}")
        return {
            "workers_online": 0,
            "active_tasks": 0,
            "workers": [],
            "status": "error",
            "message": f"Failed to get worker stats: {str(e)}"
        }


async def _get_health_stats(db: Session) -> Dict[str, Any]:
    """Get system health statistics."""
    try:
        # Database health
        db_health = {"status": "healthy"}
        try:
            db.execute("SELECT 1")
        except Exception as e:
            db_health = {"status": "unhealthy", "error": str(e)}

        # Error rate (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        error_count = db.query(Invoice).filter(
            Invoice.created_at >= yesterday,
            Invoice.status == InvoiceStatus.EXCEPTION
        ).count()
        total_count = db.query(Invoice).filter(Invoice.created_at >= yesterday).count()

        error_rate = (error_count / max(total_count, 1)) * 100

        return {
            "database": db_health,
            "error_rate_24h": {
                "percentage": f"{error_rate:.1f}%",
                "errors": error_count,
                "total": total_count
            },
            "overall_status": "healthy" if db_health["status"] == "healthy" and error_rate < 10 else "degraded"
        }

    except Exception as e:
        logger.error(f"Error getting health stats: {e}")
        return {
            "database": {"status": "error", "error": str(e)},
            "error_rate_24h": {"percentage": "unknown", "errors": 0, "total": 0},
            "overall_status": "error"
        }


@router.get("/llm")
async def get_llm_status() -> Dict[str, Any]:
    """Get LLM service status and test OpenRouter integration."""
    try:
        llm_service = LLMService()

        # Test connection
        connection_result = await llm_service.test_connection()

        # Get usage statistics
        usage_stats = llm_service.get_usage_stats()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "connection": connection_result,
            "usage_stats": usage_stats,
            "status": "healthy" if connection_result["status"] == "success" else "unhealthy"
        }

    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(e)
        }