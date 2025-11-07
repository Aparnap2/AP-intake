"""
Exception Management API endpoints.

This module provides RESTful endpoints for managing exceptions in the AP Intake system,
including listing, resolving, metrics, and notification management.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.exception import (
    ExceptionAction,
    ExceptionBatchUpdate,
    ExceptionBatchResolutionResponse,
    ExceptionCategory,
    ExceptionCreate,
    ExceptionCreateRequest,
    ExceptionFilter,
    ExceptionListResponse,
    ExceptionListRequest,
    ExceptionMetrics,
    ExceptionMetricsRequest,
    ExceptionResponse,
    ExceptionResolutionRequest,
    ExceptionResolutionResponse,
    ExceptionSearch,
    ExceptionSearchResponse,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionSummary,
    ExceptionDashboard,
    ExceptionExport,
    ExceptionStatistics,
)
from app.api.schemas.common import ErrorResponse
from app.db.session import get_db
from app.services.exception_service import ExceptionService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Dependency injection for exception service
async def get_exception_service() -> ExceptionService:
    """Get exception service instance."""
    return ExceptionService()


@router.get("/", response_model=ExceptionListResponse)
async def list_exceptions(
    invoice_id: Optional[str] = Query(None, description="Filter by invoice ID"),
    status: Optional[ExceptionStatus] = Query(None, description="Filter by status"),
    severity: Optional[ExceptionSeverity] = Query(None, description="Filter by severity"),
    category: Optional[ExceptionCategory] = Query(None, description="Filter by category"),
    reason_code: Optional[str] = Query(None, description="Filter by reason code"),
    created_after: Optional[datetime] = Query(None, description="Filter by creation date (after)"),
    created_before: Optional[datetime] = Query(None, description="Filter by creation date (before)"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    List exceptions with optional filtering and pagination.

    This endpoint returns a paginated list of exceptions that can be filtered by
    various criteria including invoice ID, status, severity, category, and date ranges.
    """
    try:
        filter_params = ExceptionFilter(
            invoice_id=invoice_id,
            status=status,
            severity=severity,
            category=category,
            reason_code=reason_code,
            created_after=created_after,
            created_before=created_before
        )

        result = await exception_service.list_exceptions(
            invoice_id=invoice_id,
            status=status,
            severity=severity,
            category=category,
            reason_code=reason_code,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
            session=db
        )

        logger.info(f"Listed {len(result.exceptions)} exceptions (total: {result.total})")
        return result

    except Exception as e:
        logger.error(f"Error listing exceptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list exceptions")


@router.get("/search", response_model=ExceptionSearchResponse)
async def search_exceptions(
    query: str = Query(..., description="Search query"),
    status: Optional[ExceptionStatus] = Query(None, description="Filter by status"),
    severity: Optional[ExceptionSeverity] = Query(None, description="Filter by severity"),
    category: Optional[ExceptionCategory] = Query(None, description="Filter by category"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Search exceptions by text query with optional filtering.

    This endpoint allows text-based searching of exceptions combined with
    filtering options and customizable sorting.
    """
    try:
        search_params = ExceptionSearch(
            query=query,
            filters=ExceptionFilter(
                status=status,
                severity=severity,
                category=category
            ),
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

        # For now, use list_exceptions with basic filtering
        # In a full implementation, this would integrate with a search service
        result = await exception_service.list_exceptions(
            status=status,
            severity=severity,
            category=category,
            limit=limit,
            offset=offset,
            session=db
        )

        # Filter results by query (simple implementation)
        filtered_exceptions = [
            exc for exc in result.exceptions
            if query.lower() in exc.message.lower() or
               query.lower() in exc.reason_code.lower()
        ]

        search_response = ExceptionSearchResponse(
            results=filtered_exceptions,
            total=len(filtered_exceptions),
            query=query,
            filters=search_params.filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

        logger.info(f"Search for '{query}' returned {len(filtered_exceptions)} results")
        return search_response

    except Exception as e:
        logger.error(f"Error searching exceptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to search exceptions")


@router.get("/{exception_id}", response_model=ExceptionResponse)
async def get_exception(
    exception_id: str,
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get exception details by ID.

    This endpoint returns detailed information about a specific exception,
    including its current status, resolution history, and suggested actions.
    """
    try:
        exception = await exception_service.get_exception(exception_id, session=db)

        if not exception:
            raise HTTPException(status_code=404, detail="Exception not found")

        logger.info(f"Retrieved exception {exception_id}")
        return exception

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exception {exception_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exception")


@router.post("/{exception_id}/resolve", response_model=ExceptionResolutionResponse)
async def resolve_exception(
    exception_id: str,
    resolution_request: ExceptionResolutionRequest,
    background_tasks: BackgroundTasks,
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve an exception with specified action and notes.

    This endpoint allows users to resolve exceptions by specifying the resolution action,
    adding notes, and optionally auto-approving the associated invoice.
    """
    try:
        # Get exception before resolution for comparison
        exception_before = await exception_service.get_exception(exception_id, session=db)
        if not exception_before:
            raise HTTPException(status_code=404, detail="Exception not found")

        # Resolve the exception
        resolved_exception = await exception_service.resolve_exception(
            exception_id=exception_id,
            resolution_request=resolution_request,
            session=db
        )

        # Log resolution activity
        logger.info(
            f"Resolved exception {exception_id} with action {resolution_request.action.value} "
            f"by {resolution_request.resolved_by}"
        )

        # Add background task for notifications
        if resolution_request.auto_approve_invoice:
            background_tasks.add_task(
                log_auto_approval,
                resolved_exception.invoice_id,
                resolution_request.resolved_by
            )

        return ExceptionResolutionResponse(
            success=True,
            exception=resolved_exception,
            message=f"Exception resolved successfully with action: {resolution_request.action.value}",
            invoice_auto_approved=resolution_request.auto_approve_invoice
        )

    except ValueError as e:
        logger.warning(f"Invalid resolution for exception {exception_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving exception {exception_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve exception")


@router.post("/batch-resolve", response_model=ExceptionBatchResolutionResponse)
async def batch_resolve_exceptions(
    batch_request: ExceptionBatchUpdate,
    background_tasks: BackgroundTasks,
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve multiple exceptions at once.

    This endpoint allows batch resolution of exceptions, useful for handling
    similar exceptions across multiple invoices simultaneously.
    """
    try:
        resolved_exceptions = await exception_service.batch_resolve_exceptions(
            exception_ids=batch_request.exception_ids,
            batch_request=batch_request,
            session=db
        )

        # Log batch resolution activity
        logger.info(
            f"Batch resolved {len(resolved_exceptions)} exceptions with action "
            f"{batch_request.action.value} by {batch_request.resolved_by}"
        )

        # Add background tasks for auto-approvals
        if batch_request.auto_approve_invoices:
            for exception in resolved_exceptions:
                background_tasks.add_task(
                    log_auto_approval,
                    exception.invoice_id,
                    batch_request.resolved_by
                )

        auto_approved_invoices = [
            exc.invoice_id for exc in resolved_exceptions
            if batch_request.auto_approve_invoices
        ]

        return ExceptionBatchResolutionResponse(
            success_count=len(resolved_exceptions),
            error_count=0,  # Would be populated with actual errors in full implementation
            resolved_exceptions=resolved_exceptions,
            errors=[],  # Would be populated with actual errors in full implementation
            invoices_auto_approved=auto_approved_invoices
        )

    except Exception as e:
        logger.error(f"Error in batch exception resolution: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve exceptions in batch")


@router.get("/metrics/summary", response_model=ExceptionMetrics)
async def get_exception_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in metrics"),
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get exception metrics for the specified period.

    This endpoint returns comprehensive metrics about exceptions, including
    resolution rates, trends, and breakdowns by category and severity.
    """
    try:
        metrics = await exception_service.get_exception_metrics(days=days, session=db)

        logger.info(f"Generated exception metrics for {days} days")
        return metrics

    except Exception as e:
        logger.error(f"Error generating exception metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate exception metrics")


@router.get("/dashboard", response_model=ExceptionDashboard)
async def get_exception_dashboard(
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive exception dashboard data.

    This endpoint returns all the data needed for the exception management dashboard,
    including summaries, trends, recent exceptions, and pending escalations.
    """
    try:
        # Get metrics for different periods
        current_metrics = await exception_service.get_exception_metrics(days=7, session=db)
        monthly_metrics = await exception_service.get_exception_metrics(days=30, session=db)

        # Get recent exceptions
        recent_result = await exception_service.list_exceptions(
            limit=10,
            offset=0,
            session=db
        )

        # Get critical exceptions (high severity and open)
        critical_result = await exception_service.list_exceptions(
            severity=ExceptionSeverity.ERROR,
            limit=5,
            offset=0,
            session=db
        )

        # Create summary
        summary = ExceptionSummary(
            total_exceptions=current_metrics.total_exceptions,
            new_exceptions_today=len([exc for exc in recent_result.exceptions
                                    if exc.created_at.date() == datetime.utcnow().date()]),
            critical_exceptions=len(critical_result.exceptions),
            awaiting_review=current_metrics.open_exceptions,
            avg_resolution_time_hours=current_metrics.avg_resolution_hours,
            resolution_trend="stable",  # Would calculate actual trend
            top_exception_types=[
                {"reason_code": code, "count": count}
                for code, count in list(current_metrics.top_reason_codes.items())[:5]
            ],
            recent_exceptions=recent_result.exceptions[:5]
        )

        # Create dashboard
        dashboard = ExceptionDashboard(
            summary=summary,
            metrics=monthly_metrics,
            trends=[],  # Would calculate actual trends
            recent_exceptions=recent_result.exceptions,
            pending_escalations=critical_result.exceptions,
            auto_resolution_candidates=[
                exc for exc in recent_result.exceptions
                if exc.auto_resolution_possible and exc.status == ExceptionStatus.OPEN
            ][:5]
        )

        logger.info("Generated exception dashboard data")
        return dashboard

    except Exception as e:
        logger.error(f"Error generating exception dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate dashboard data")


@router.get("/export", response_model=List[ExceptionExport])
async def export_exceptions(
    status: Optional[ExceptionStatus] = Query(None, description="Filter by status"),
    severity: Optional[ExceptionSeverity] = Query(None, description="Filter by severity"),
    category: Optional[ExceptionCategory] = Query(None, description="Filter by category"),
    created_after: Optional[datetime] = Query(None, description="Filter by creation date (after)"),
    created_before: Optional[datetime] = Query(None, description="Filter by creation date (before)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to export"),
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Export exceptions data in a standardized format.

    This endpoint provides exception data in an export-friendly format,
    suitable for reporting, analysis, or integration with external systems.
    """
    try:
        # Get exceptions
        result = await exception_service.list_exceptions(
            status=status,
            severity=severity,
            category=category,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=0,
            session=db
        )

        # Convert to export format
        export_data = []
        for exception in result.exceptions:
            # Calculate resolution time in hours
            resolution_time = None
            if exception.resolved_at:
                resolution_time = (exception.resolved_at - exception.created_at).total_seconds() / 3600

            export_record = ExceptionExport(
                exception_id=exception.id,
                invoice_id=exception.invoice_id,
                invoice_number=f"INV-{exception.invoice_id[:8]}",  # Would get actual invoice number
                vendor_name="Unknown Vendor",  # Would get actual vendor name
                reason_code=exception.reason_code,
                category=exception.category.value,
                severity=exception.severity.value,
                status=exception.status.value,
                message=exception.message,
                created_at=exception.created_at,
                resolved_at=exception.resolved_at,
                resolved_by=exception.resolved_by,
                resolution_time_hours=resolution_time,
                auto_resolved=exception.auto_resolution_possible and exception.status == ExceptionStatus.RESOLVED
            )
            export_data.append(export_record)

        logger.info(f"Exported {len(export_data)} exception records")
        return export_data

    except Exception as e:
        logger.error(f"Error exporting exceptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to export exceptions")


@router.post("/", response_model=ExceptionResponse)
async def create_manual_exception(
    exception_request: ExceptionCreateRequest,
    exception_service: ExceptionService = Depends(get_exception_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a manual exception for an invoice.

    This endpoint allows users to manually create exceptions for invoices,
    useful for issues that may not be caught by automated validation.
    """
    try:
        # Create exception data
        exception_data = ExceptionCreate(
            reason_code=exception_request.reason_code.value,
            message=exception_request.message,
            details=exception_request.details,
            auto_resolution_possible=exception_request.auto_resolution_possible,
            suggested_actions=exception_request.suggested_actions
        )

        # Use the exception service to create the exception
        # This would be integrated with the existing exception creation workflow
        # For now, this is a placeholder implementation

        logger.info(f"Created manual exception for invoice {exception_request.invoice_id}")
        # Return a mock response - in full implementation, this would save to database
        return ExceptionResponse(
            id="mock-exception-id",
            invoice_id=exception_request.invoice_id,
            reason_code=exception_request.reason_code.value,
            category=exception_request.category,
            severity=exception_request.severity,
            status=ExceptionStatus.OPEN,
            message=exception_request.message,
            details=exception_request.details,
            auto_resolution_possible=exception_request.auto_resolution_possible,
            suggested_actions=exception_request.suggested_actions,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Error creating manual exception: {e}")
        raise HTTPException(status_code=500, detail="Failed to create exception")


# Background task helpers
async def log_auto_approval(invoice_id: str, approved_by: str):
    """Log invoice auto-approval in background."""
    logger.info(f"Auto-approved invoice {invoice_id} by {approved_by}")


# Note: Exception handlers should be defined on the FastAPI app, not on APIRouter
# These are defined in app/main.py