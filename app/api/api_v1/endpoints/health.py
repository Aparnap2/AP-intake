"""
Health check endpoints.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.workers.celery_app import celery_app
from app.services.prometheus_service import prometheus_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with system status."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "services": {}
    }

    # Check database
    try:
        db.execute("SELECT 1")
        health_status["services"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        health_status["status"] = "unhealthy"

    # Check Celery workers
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats:
            worker_count = len(stats)
            health_status["services"]["celery"] = {
                "status": "healthy",
                "message": f"{worker_count} worker(s) available",
                "workers": list(stats.keys())
            }
        else:
            health_status["services"]["celery"] = {
                "status": "warning",
                "message": "No Celery workers detected"
            }
    except Exception as e:
        health_status["services"]["celery"] = {
            "status": "unhealthy",
            "message": f"Celery check failed: {str(e)}"
        }
        health_status["status"] = "unhealthy"

    return health_status


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    # Update metrics before serving
    await prometheus_service.update_system_metrics()
    await prometheus_service.update_from_database()

    return prometheus_service.get_metrics_response()