"""
Analytics API endpoints for KPI dashboard and metrics.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.deps import get_async_session, get_current_active_user
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/kpi/summary", response_model=Dict[str, Any])
def get_kpi_summary(
    start_date: Optional[str] = Query(None, description="Start date in ISO format (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date in ISO format (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get executive KPI summary for the specified period.

    Args:
        start_date: Start date for analysis period (default: 30 days ago)
        end_date: End date for analysis period (default: today)

    Returns:
        Executive summary with overall health score and key metrics
    """
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        summary = analytics_service.get_executive_summary(start_dt, end_dt)

        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating KPI summary: {str(e)}")


@router.get("/accuracy", response_model=Dict[str, Any])
def get_accuracy_metrics(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get extraction accuracy and validation metrics."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)

        extraction_accuracy = analytics_service.get_extraction_accuracy_metrics(start_dt, end_dt)
        validation_metrics = analytics_service.get_validation_pass_rates(start_dt, end_dt)

        return {
            "success": True,
            "data": {
                "extraction_accuracy": extraction_accuracy,
                "validation_metrics": validation_metrics
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving accuracy metrics: {str(e)}")


@router.get("/exceptions", response_model=Dict[str, Any])
def get_exception_metrics(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get exception analysis and resolution metrics."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        exception_analysis = analytics_service.get_exception_analysis(start_dt, end_dt)

        return {
            "success": True,
            "data": exception_analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving exception metrics: {str(e)}")


@router.get("/cycle-times", response_model=Dict[str, Any])
def get_cycle_time_metrics(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get processing cycle time metrics."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        cycle_metrics = analytics_service.get_cycle_time_metrics(start_dt, end_dt)

        return {
            "success": True,
            "data": cycle_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving cycle time metrics: {str(e)}")


@router.get("/productivity", response_model=Dict[str, Any])
def get_productivity_metrics(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get productivity and efficiency metrics."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        productivity_metrics = analytics_service.get_productivity_metrics(start_dt, end_dt)

        return {
            "success": True,
            "data": productivity_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving productivity metrics: {str(e)}")


@router.get("/reviewers", response_model=Dict[str, Any])
def get_reviewer_performance(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get reviewer performance metrics and rankings."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        reviewer_performance = analytics_service.get_reviewer_performance(start_dt, end_dt)

        return {
            "success": True,
            "data": reviewer_performance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving reviewer performance: {str(e)}")


@router.get("/trends", response_model=Dict[str, Any])
def get_trend_analysis(
    metric: str = Query("all", description="Metric to analyze: volume, accuracy, exceptions, or all"),
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get trend analysis for specified metrics."""
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)
        trend_analysis = analytics_service.get_trend_analysis(start_dt, end_dt, metric)

        return {
            "success": True,
            "data": trend_analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving trend analysis: {str(e)}")


@router.get("/dashboard/finance-ops", response_model=Dict[str, Any])
def get_finance_ops_dashboard(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get finance operations dashboard data.
    Focus on processing efficiency, exception rates, and cycle times.
    """
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)

        # Gather relevant metrics for finance operations
        productivity = analytics_service.get_productivity_metrics(start_dt, end_dt)
        exceptions = analytics_service.get_exception_analysis(start_dt, end_dt)
        cycle_times = analytics_service.get_cycle_time_metrics(start_dt, end_dt)
        trends = analytics_service.get_trend_analysis(start_dt, end_dt, "volume")

        return {
            "success": True,
            "data": {
                "period": {
                    "start_date": start_dt.isoformat(),
                    "end_date": end_dt.isoformat()
                },
                "productivity": productivity,
                "exceptions": exceptions,
                "cycle_times": cycle_times,
                "volume_trends": trends.get("trends", {}).get("volume", []),
                "key_insights": {
                    "processing_efficiency": productivity.get("processing_efficiency", 0),
                    "exception_rate": exceptions.get("exception_rate", 0),
                    "avg_processing_time": cycle_times.get("average_processing_time_hours", 0),
                    "daily_avg_volume": sum(
                        day.get("count", 0) for day in trends.get("trends", {}).get("volume", [])
                    ) / len(trends.get("trends", {}).get("volume", [1])) if trends.get("trends", {}).get("volume") else 0
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving finance ops dashboard: {str(e)}")


@router.get("/dashboard/management", response_model=Dict[str, Any])
def get_management_dashboard(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get management dashboard data.
    Focus on overall performance, health scores, and strategic metrics.
    """
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)

        # Executive summary for management
        executive_summary = analytics_service.get_executive_summary(start_dt, end_dt)
        reviewer_performance = analytics_service.get_reviewer_performance(start_dt, end_dt)
        accuracy_metrics = analytics_service.get_extraction_accuracy_metrics(start_dt, end_dt)

        return {
            "success": True,
            "data": {
                "executive_summary": executive_summary,
                "reviewer_performance": reviewer_performance,
                "accuracy_metrics": accuracy_metrics,
                "period": {
                    "start_date": start_dt.isoformat(),
                    "end_date": end_dt.isoformat()
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving management dashboard: {str(e)}")


@router.get("/dashboard/reviewers", response_model=Dict[str, Any])
def get_reviewer_dashboard(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    reviewer_id: Optional[str] = Query(None, description="Specific reviewer ID (for individual view)"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get reviewer dashboard data.
    Focus on individual performance, workload, and exception resolution.
    """
    try:
        # Parse dates or use defaults
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(days=30)

        analytics_service = AnalyticsService(db)

        # Get reviewer-specific and general reviewer metrics
        reviewer_performance = analytics_service.get_reviewer_performance(start_dt, end_dt)
        exception_analysis = analytics_service.get_exception_analysis(start_dt, end_dt)

        # Filter for specific reviewer if provided
        individual_performance = None
        if reviewer_id and reviewer_id in reviewer_performance.get("reviewer_performance", {}):
            individual_performance = reviewer_performance["reviewer_performance"][reviewer_id]

        return {
            "success": True,
            "data": {
                "period": {
                    "start_date": start_dt.isoformat(),
                    "end_date": end_dt.isoformat()
                },
                "team_performance": reviewer_performance,
                "exception_analysis": exception_analysis,
                "individual_performance": individual_performance,
                "reviewer_ranking": reviewer_performance.get("reviewer_performance", {}),
                "team_summary": {
                    "total_reviewers": reviewer_performance.get("total_reviewers", 0),
                    "total_resolved": reviewer_performance.get("total_resolved_exceptions", 0),
                    "team_avg_resolution_time": sum(
                        perf.get("average_resolution_time_hours", 0)
                        for perf in reviewer_performance.get("reviewer_performance", {}).values()
                    ) / reviewer_performance.get("total_reviewers", 1) if reviewer_performance.get("total_reviewers", 0) > 0 else 0
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving reviewer dashboard: {str(e)}")


@router.get("/real-time", response_model=Dict[str, Any])
def get_real_time_metrics(
    db: AsyncSession = Depends(get_async_session),
    current_user: Any = Depends(get_current_active_user),
):
    """Get real-time system metrics for dashboard monitoring."""
    try:
        from app.models.invoice import Invoice, InvoiceStatus, Exception as InvoiceException
        from sqlalchemy import func

        # Current time
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_24h = now - timedelta(hours=24)
        last_1h = now - timedelta(hours=1)

        # Real-time counts
        invoices_today = db.query(Invoice).filter(Invoice.created_at >= today_start).count()
        invoices_last_24h = db.query(Invoice).filter(Invoice.created_at >= last_24h).count()
        invoices_last_1h = db.query(Invoice).filter(Invoice.created_at >= last_1h).count()

        # Status breakdown
        status_counts = db.query(
            Invoice.status,
            func.count(Invoice.id).label('count')
        ).filter(
            Invoice.created_at >= today_start
        ).group_by(Invoice.status).all()

        # Recent exceptions
        recent_exceptions = db.query(InvoiceException).filter(
            InvoiceException.created_at >= last_24h
        ).count()

        # Pending items
        pending_review = db.query(Invoice).filter(
            Invoice.status == InvoiceStatus.VALIDATED
        ).count()

        pending_resolution = db.query(InvoiceException).filter(
            InvoiceException.resolved_at.is_(None)
        ).count()

        return {
            "success": True,
            "data": {
                "timestamp": now.isoformat(),
                "volume_metrics": {
                    "invoices_today": invoices_today,
                    "invoices_last_24h": invoices_last_24h,
                    "invoices_last_1h": invoices_last_1h,
                    "recent_exceptions": recent_exceptions
                },
                "status_breakdown": {
                    status.value: count for status, count in status_counts
                },
                "pending_items": {
                    "pending_review": pending_review,
                    "pending_resolution": pending_resolution
                },
                "system_health": {
                    "active": True,
                    "last_updated": now.isoformat()
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving real-time metrics: {str(e)}")