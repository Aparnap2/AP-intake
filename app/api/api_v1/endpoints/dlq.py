"""
DLQ API endpoints for managing dead letter queue entries.

This module provides comprehensive REST API endpoints for:
- Listing and filtering DLQ entries
- Redriving failed tasks
- DLQ statistics and monitoring
- DLQ entry management
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.api_v1 import deps
from app.core.config import settings
from app.models.dlq import (
    DeadLetterQueue, DLQStatus, DLQCategory, DLQPriority,
    DLQEntry, DLQStats, RedriveRequest, RedriveResponse
)
from app.models.user import User
from app.services.dlq_service import DLQService
from app.services.redrive_service import RedriveService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_dlq_service(db: Session = Depends(deps.get_db)) -> DLQService:
    """Get DLQ service instance."""
    return DLQService(db)


def get_redrive_service(db: Session = Depends(deps.get_db)) -> RedriveService:
    """Get redrive service instance."""
    return RedriveService(db)


@router.get("/entries", response_model=Dict[str, Any])
async def list_dlq_entries(
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
    status: Optional[DLQStatus] = Query(None, description="Filter by DLQ status"),
    category: Optional[DLQCategory] = Query(None, description="Filter by error category"),
    priority: Optional[DLQPriority] = Query(None, description="Filter by priority"),
    task_name: Optional[str] = Query(None, description="Filter by task name"),
    invoice_id: Optional[str] = Query(None, description="Filter by invoice ID"),
    queue_name: Optional[str] = Query(None, description="Filter by queue name"),
    worker_name: Optional[str] = Query(None, description="Filter by worker name"),
    idempotency_key: Optional[str] = Query(None, description="Filter by idempotency key"),
    created_after: Optional[datetime] = Query(None, description="Filter entries created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter entries created before this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of entries per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
) -> Dict[str, Any]:
    """
    List DLQ entries with filtering and pagination.

    This endpoint provides a comprehensive interface to browse and filter
    dead letter queue entries.
    """
    try:
        # Convert invoice_id string to UUID if provided
        invoice_uuid = None
        if invoice_id:
            try:
                from uuid import UUID
                invoice_uuid = UUID(invoice_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid invoice ID format"
                )

        # Get entries
        entries, total = dlq_service.list_dlq_entries(
            status=status,
            category=category,
            priority=priority,
            task_name=task_name,
            invoice_id=invoice_uuid,
            queue_name=queue_name,
            worker_name=worker_name,
            idempotency_key=idempotency_key,
            created_after=created_after,
            created_before=created_before,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Convert to response format
        entries_data = [DLQEntry.from_orm(entry).dict() for entry in entries]

        return {
            "entries": entries_data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
            "filters": {
                "status": status.value if status else None,
                "category": category.value if category else None,
                "priority": priority.value if priority else None,
                "task_name": task_name,
                "invoice_id": invoice_id,
                "queue_name": queue_name,
                "worker_name": worker_name,
                "idempotency_key": idempotency_key,
                "created_after": created_after.isoformat() if created_after else None,
                "created_before": created_before.isoformat() if created_before else None,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing DLQ entries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list DLQ entries"
        )


@router.get("/entries/{dlq_id}", response_model=DLQEntry)
async def get_dlq_entry(
    dlq_id: str,
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> DLQEntry:
    """
    Get a specific DLQ entry by ID.

    This endpoint retrieves detailed information about a single
    dead letter queue entry including error details and history.
    """
    try:
        from uuid import UUID
        dlq_uuid = UUID(dlq_id)

        entry = dlq_service.get_dlq_entry(dlq_uuid)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found"
            )

        return DLQEntry.from_orm(entry)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DLQ entry ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting DLQ entry {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DLQ entry"
        )


@router.get("/entries/task/{task_id}", response_model=DLQEntry)
async def get_dlq_entry_by_task_id(
    task_id: str,
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> DLQEntry:
    """
    Get a DLQ entry by task ID.

    This endpoint retrieves DLQ entry information using the original
    Celery task ID.
    """
    try:
        entry = dlq_service.get_dlq_entry_by_task_id(task_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found for this task ID"
            )

        return DLQEntry.from_orm(entry)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting DLQ entry for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DLQ entry by task ID"
        )


@router.post("/entries/{dlq_id}/redrive", response_model=Dict[str, Any])
async def redrive_single_entry(
    dlq_id: str,
    *,
    db: Session = Depends(deps.get_db),
    redrive_service: RedriveService = Depends(get_redrive_service),
    current_user: User = Depends(deps.get_current_active_user),
    force: bool = Query(False, description="Force redrive even if max retries exceeded"),
    modify_args: Optional[Dict[str, Any]] = None,
    priority_override: Optional[DLQPriority] = Query(None, description="Optional priority override"),
) -> Dict[str, Any]:
    """
    Redrive a single DLQ entry.

    This endpoint attempts to retry a failed task from the DLQ.
    """
    try:
        from uuid import UUID
        dlq_uuid = UUID(dlq_id)

        success, message = redrive_service.redrive_single_entry(
            dlq_id=dlq_uuid,
            force=force,
            modify_args=modify_args,
            priority_override=priority_override
        )

        return {
            "success": success,
            "message": message,
            "dlq_id": dlq_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DLQ entry ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redriving DLQ entry {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to redrive DLQ entry"
        )


@router.post("/bulk-redrive", response_model=RedriveResponse)
async def bulk_redrive_entries(
    request: RedriveRequest,
    *,
    db: Session = Depends(deps.get_db),
    redrive_service: RedriveService = Depends(get_redrive_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> RedriveResponse:
    """
    Redrive multiple DLQ entries in bulk.

    This endpoint allows batch redrive operations on multiple DLQ entries.
    """
    try:
        response = redrive_service.redrive_bulk_entries(request)
        return response

    except Exception as e:
        logger.error(f"Error in bulk redrive: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk redrive"
        )


@router.get("/stats", response_model=DLQStats)
async def get_dlq_stats(
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to consider for stats"),
) -> DLQStats:
    """
    Get DLQ statistics.

    This endpoint provides comprehensive statistics about the DLQ including
    entry counts by status, category, and priority.
    """
    try:
        stats = dlq_service.get_dlq_stats(days=days)
        return stats

    except Exception as e:
        logger.error(f"Error getting DLQ stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DLQ statistics"
        )


@router.get("/health", response_model=Dict[str, Any])
async def get_dlq_health(
    *,
    db: Session = Depends(deps.get_db),
    redrive_service: RedriveService = Depends(get_redrive_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get DLQ health and circuit breaker status.

    This endpoint provides health information about the DLQ system
    including circuit breaker states.
    """
    try:
        # Get circuit breaker status
        circuit_breaker_status = redrive_service.get_circuit_breaker_status()

        # Get basic stats
        dlq_service = DLQService(db)
        stats = dlq_service.get_dlq_stats(days=1)

        # Calculate health indicators
        health_score = 100

        # Deduct points for issues
        if stats.pending_entries > 50:
            health_score -= 10
        if stats.critical_entries > 5:
            health_score -= 20
        if stats.failed_permanently > 10:
            health_score -= 15

        # Check circuit breakers
        open_breakers = [
            name for name, status in circuit_breaker_status.items()
            if status["is_open"]
        ]
        if open_breakers:
            health_score -= 30

        # Determine overall health
        if health_score >= 90:
            health_status = "healthy"
        elif health_score >= 70:
            health_status = "warning"
        else:
            health_status = "critical"

        return {
            "status": health_status,
            "health_score": max(0, health_score),
            "circuit_breakers": circuit_breaker_status,
            "open_circuit_breakers": open_breakers,
            "recent_stats": stats.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting DLQ health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DLQ health status"
        )


@router.get("/entries/{dlq_id}/recommendations", response_model=Dict[str, Any])
async def get_redrive_recommendations(
    dlq_id: str,
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    redrive_service: RedriveService = Depends(get_redrive_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get redrive recommendations for a DLQ entry.

    This endpoint provides intelligent recommendations about whether
    a DLQ entry should be redriven and how.
    """
    try:
        from uuid import UUID
        dlq_uuid = UUID(dlq_id)

        # Get DLQ entry
        entry = dlq_service.get_dlq_entry(dlq_uuid)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found"
            )

        # Get recommendations
        recommendations = redrive_service.get_redrive_recommendations(entry)

        # Check if entry is ready for retry
        should_redrive = redrive_service.should_redrive_entry(entry)

        return {
            "dlq_id": dlq_id,
            "task_name": entry.task_name,
            "error_category": entry.error_category.value,
            "retry_count": entry.retry_count,
            "max_retries": entry.max_retries,
            "should_redrive": should_redrive,
            "recommendations": recommendations,
            "last_retry_at": entry.last_retry_at.isoformat() if entry.last_retry_at else None,
            "next_retry_at": entry.next_retry_at.isoformat() if entry.next_retry_at else None,
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DLQ entry ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendations for DLQ entry {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get redrive recommendations"
        )


@router.delete("/entries/{dlq_id}", response_model=Dict[str, Any])
async def delete_dlq_entry(
    dlq_id: str,
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Delete a DLQ entry.

    This endpoint permanently removes a DLQ entry from the system.
    """
    try:
        from uuid import UUID
        dlq_uuid = UUID(dlq_id)

        success = dlq_service.delete_dlq_entry(dlq_uuid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found"
            )

        return {
            "success": True,
            "message": "DLQ entry deleted successfully",
            "dlq_id": dlq_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DLQ entry ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting DLQ entry {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete DLQ entry"
        )


@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_old_entries(
    *,
    db: Session = Depends(deps.get_db),
    dlq_service: DLQService = Depends(get_dlq_service),
    current_user: User = Depends(deps.get_current_active_user),
    days: int = Query(90, ge=1, le=365, description="Age in days to delete entries"),
    status: Optional[DLQStatus] = Query(None, description="Optional status filter"),
) -> Dict[str, Any]:
    """
    Clean up old DLQ entries.

    This endpoint removes old DLQ entries based on age and optional status filter.
    """
    try:
        count = dlq_service.cleanup_old_entries(days=days, status=status)

        return {
            "success": True,
            "message": f"Cleaned up {count} old DLQ entries",
            "deleted_count": count,
            "criteria": {
                "days": days,
                "status": status.value if status else None
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up old DLQ entries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old DLQ entries"
        )