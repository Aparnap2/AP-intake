"""
Reports API endpoints for weekly reporting system.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.api.deps import get_async_session, get_current_user
from app.models.reports import (
    WeeklyReport, ReportType, ReportStatus, DeliveryStatus,
    ReportSubscription, SLOMetric, WeeklyCostAnalysis,
    ExceptionAnalysis, ProcessingMetric
)
from app.models.user import User
from app.services.weekly_report_service import WeeklyReportService, CFODigestService
from app.services.email_report_service import EmailReportService
from app.services.analytics_engine import AnalyticsEngine
from app.services.n8n_service import N8nService
from app.core.logging import get_logger
from app.api.schemas.digest import (
    CFODigestRequest, CFODigestResponse, CFODigestListResponse,
    CFODigestScheduleRequest, CFODigestScheduleResponse,
    DigestPriority, BusinessImpactLevel
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("/weekly/generate")
async def generate_weekly_report(
    week_start: Optional[str] = Query(None, description="ISO format date for week start"),
    template_id: Optional[str] = Query(None, description="Report template ID"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate a new weekly report."""
    try:
        # Parse week start date
        if week_start:
            try:
                week_start_dt = datetime.fromisoformat(week_start.replace('Z', '+00:00'))
                if week_start_dt.tzinfo is None:
                    week_start_dt = week_start_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        else:
            # Default to last week
            today = datetime.now(timezone.utc).date()
            days_since_monday = today.weekday()
            week_start_dt = datetime.combine(
                today - timedelta(days=days_since_monday + 7),
                datetime.min.time(),
                tzinfo=timezone.utc
            )

        # Generate report
        report_service = WeeklyReportService(session)
        report = await report_service.generate_weekly_report(
            week_start=week_start_dt,
            template_id=template_id,
            generated_by=current_user.email
        )

        return {
            "report_id": str(report.id),
            "title": report.title,
            "week_start": report.week_start.isoformat(),
            "week_end": report.week_end.isoformat(),
            "status": report.status.value,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            "message": "Weekly report generated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate weekly report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly/list")
async def list_weekly_reports(
    limit: int = Query(12, ge=1, le=52, description="Number of weeks to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List weekly reports."""
    try:
        # Build query
        query = select(WeeklyReport).where(
            WeeklyReport.report_type == ReportType.WEEKLY
        ).order_by(desc(WeeklyReport.week_start)).limit(limit)

        if status:
            query = query.where(WeeklyReport.status == status)

        result = await session.execute(query)
        reports = result.scalars().all()

        return {
            "reports": [
                {
                    "id": str(report.id),
                    "title": report.title,
                    "week_start": report.week_start.isoformat(),
                    "week_end": report.week_end.isoformat(),
                    "status": report.status.value,
                    "generated_at": report.generated_at.isoformat() if report.generated_at else None,
                    "generated_by": report.generated_by,
                    "summary": report.summary[:200] + "..." if report.summary and len(report.summary) > 200 else report.summary,
                    "has_content": report.content_json is not None,
                    "delivery_count": len(report.deliveries) if report.deliveries else 0
                }
                for report in reports
            ],
            "total": len(reports)
        }

    except Exception as e:
        logger.error(f"Failed to list weekly reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly/{report_id}")
async def get_weekly_report(
    report_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific weekly report."""
    try:
        report_service = WeeklyReportService(session)
        report = await report_service.get_report_by_id(report_id)

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Get delivery information
        deliveries = await session.execute(
            select(ReportDelivery).where(ReportDelivery.report_id == report_id)
        )
        delivery_list = deliveries.scalars().all()

        return {
            "report": {
                "id": str(report.id),
                "title": report.title,
                "description": report.description,
                "week_start": report.week_start.isoformat(),
                "week_end": report.week_end.isoformat(),
                "status": report.status.value,
                "generated_at": report.generated_at.isoformat() if report.generated_at else None,
                "generated_by": report.generated_by,
                "version": report.version,
                "summary": report.summary,
                "content": report.content_json,
                "insights": report.insights,
                "tags": report.tags
            },
            "deliveries": [
                {
                    "id": str(delivery.id),
                    "recipient_email": delivery.recipient_email,
                    "recipient_group": delivery.recipient_group,
                    "status": delivery.status.value,
                    "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
                    "delivery_attempts": delivery.delivery_attempts,
                    "error_message": delivery.error_message
                }
                for delivery in delivery_list
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get weekly report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly/{report_id}/download")
async def download_weekly_report(
    report_id: str,
    format: str = Query("pdf", description="Export format: pdf, json, csv"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download weekly report in specified format."""
    try:
        report_service = WeeklyReportService(session)
        report = await report_service.get_report_by_id(report_id)

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if format.lower() == "pdf":
            if report.pdf_file_path:
                return FileResponse(
                    report.pdf_file_path,
                    media_type="application/pdf",
                    filename=f"Weekly_Report_{report.week_start.strftime('%Y%m%d')}.pdf"
                )
            else:
                # Generate PDF on demand
                pdf_content = await report_service._generate_pdf_attachment(report)
                # For now, return JSON as fallback
                return JSONResponse(
                    content=report.content_json or {},
                    headers={
                        "Content-Disposition": f"attachment; filename=Weekly_Report_{report.week_start.strftime('%Y%m%d')}.json"
                    }
                )
        elif format.lower() == "json":
            return JSONResponse(
                content=report.content_json or {},
                headers={
                    "Content-Disposition": f"attachment; filename=Weekly_Report_{report.week_start.strftime('%Y%m%d')}.json"
                }
            )
        elif format.lower() == "csv":
            # Generate CSV format
            csv_data = await _generate_csv_export(report)
            return JSONResponse(
                content=csv_data,
                headers={
                    "Content-Disposition": f"attachment; filename=Weekly_Report_{report.week_start.strftime('%Y%m%d')}.csv"
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use pdf, json, or csv.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download weekly report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weekly/{report_id}/send")
async def send_weekly_report(
    report_id: str,
    recipient_groups: List[str] = Query(["executive", "operations", "finance"]),
    additional_recipients: Optional[List[str]] = Query(None),
    include_pdf: bool = Query(True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send weekly report via email."""
    try:
        email_service = EmailReportService(session)

        # Send report in background
        background_tasks.add_task(
            email_service.send_weekly_report,
            report_id=report_id,
            recipient_groups=recipient_groups,
            additional_recipients=additional_recipients or [],
            include_pdf=include_pdf
        )

        return {
            "message": "Report delivery initiated",
            "report_id": report_id,
            "recipient_groups": recipient_groups,
            "additional_recipients": additional_recipients or [],
            "include_pdf": include_pdf
        }

    except Exception as e:
        logger.error(f"Failed to send weekly report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weekly/{report_id}/send-custom")
async def send_custom_report(
    report_id: str,
    recipient_email: str,
    subject: Optional[str] = None,
    custom_message: Optional[str] = None,
    include_pdf: bool = Query(True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send report to a specific recipient with custom message."""
    try:
        email_service = EmailReportService(session)

        # Send custom report
        delivery = await email_service.send_custom_report(
            report_id=report_id,
            recipient_email=recipient_email,
            subject=subject,
            custom_message=custom_message,
            include_pdf=include_pdf
        )

        return {
            "message": "Custom report sent successfully",
            "delivery_id": str(delivery.id),
            "recipient_email": recipient_email,
            "status": delivery.status.value
        }

    except Exception as e:
        logger.error(f"Failed to send custom report {report_id} to {recipient_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deliveries")
async def list_deliveries(
    report_id: Optional[str] = Query(None, description="Filter by report ID"),
    status: Optional[str] = Query(None, description="Filter by delivery status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List report deliveries."""
    try:
        # Build query
        query = select(ReportDelivery).order_by(desc(ReportDelivery.created_at))

        if report_id:
            query = query.where(ReportDelivery.report_id == report_id)
        if status:
            query = query.where(ReportDelivery.status == status)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        deliveries = result.scalars().all()

        # Get total count
        count_query = select(func.count(ReportDelivery.id))
        if report_id:
            count_query = count_query.where(ReportDelivery.report_id == report_id)
        if status:
            count_query = count_query.where(ReportDelivery.status == status)

        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        return {
            "deliveries": [
                {
                    "id": str(delivery.id),
                    "report_id": str(delivery.report_id),
                    "recipient_email": delivery.recipient_email,
                    "recipient_group": delivery.recipient_group,
                    "delivery_method": delivery.delivery_method,
                    "status": delivery.status.value,
                    "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
                    "delivery_attempts": delivery.delivery_attempts,
                    "error_message": delivery.error_message,
                    "opened_at": delivery.opened_at.isoformat() if delivery.opened_at else None,
                    "clicked_at": delivery.clicked_at.isoformat() if delivery.clicked_at else None
                }
                for delivery in deliveries
            ],
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(deliveries) < total_count
            }
        }

    except Exception as e:
        logger.error(f"Failed to list deliveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retry a failed delivery."""
    try:
        email_service = EmailReportService(session)

        # Get delivery
        delivery_query = select(ReportDelivery).where(ReportDelivery.id == delivery_id)
        delivery_result = await session.execute(delivery_query)
        delivery = delivery_result.scalar_one_or_none()

        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")

        if delivery.status != DeliveryStatus.FAILED:
            raise HTTPException(status_code=400, detail="Only failed deliveries can be retried")

        # Get report for retry
        report_query = select(WeeklyReport).where(WeeklyReport.id == delivery.report_id)
        report_result = await session.execute(report_query)
        report = report_result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Associated report not found")

        # Retry delivery
        await email_service._retry_delivery(delivery, report)

        return {
            "message": "Delivery retry initiated",
            "delivery_id": delivery_id,
            "new_status": delivery.status.value,
            "attempts": delivery.delivery_attempts
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry delivery {delivery_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/cost")
async def get_cost_analytics(
    weeks: int = Query(4, ge=1, le=52, description="Number of weeks to analyze"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get cost analytics for recent weeks."""
    try:
        analytics_engine = AnalyticsEngine(session)

        # Get cost data for recent weeks
        cost_analytics = []

        for week_offset in range(weeks):
            week_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_end - timedelta(days=week_end.weekday())
            week_start = week_end - timedelta(days=7)

            # Shift back by week_offset
            week_start = week_start - timedelta(weeks=week_offset)
            week_end = week_end - timedelta(weeks=week_offset)

            try:
                cost_analysis = await analytics_engine.calculate_weekly_cost_analysis(week_start, week_end)
                cost_analytics.append({
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "cost_per_invoice": cost_analysis.cost_per_invoice,
                    "total_cost": cost_analysis.total_processing_cost,
                    "total_invoices": cost_analysis.total_invoices_processed,
                    "cost_savings": cost_analysis.cost_savings_vs_manual,
                    "efficiency_score": cost_analysis.cost_efficiency_score
                })
            except Exception as e:
                logger.warning(f"Failed to get cost analysis for week {week_start}: {e}")
                continue

        # Calculate trends
        if len(cost_analytics) >= 2:
            latest_cost = cost_analytics[0]["cost_per_invoice"]
            previous_cost = cost_analytics[1]["cost_per_invoice"]
            cost_trend = ((latest_cost - previous_cost) / previous_cost * 100) if previous_cost > 0 else 0
        else:
            cost_trend = 0

        return {
            "cost_analytics": cost_analytics,
            "summary": {
                "weeks_analyzed": len(cost_analytics),
                "current_cost_per_invoice": cost_analytics[0]["cost_per_invoice"] if cost_analytics else 0,
                "cost_trend_percentage": cost_trend,
                "average_efficiency_score": sum(ca["efficiency_score"] for ca in cost_analytics) / len(cost_analytics) if cost_analytics else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get cost analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/exceptions")
async def get_exception_analytics(
    weeks: int = Query(4, ge=1, le=52, description="Number of weeks to analyze"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get exception analytics for recent weeks."""
    try:
        analytics_engine = AnalyticsEngine(session)

        # Get exception data for recent weeks
        exception_analytics = []

        for week_offset in range(weeks):
            week_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_end - timedelta(days=week_end.weekday())
            week_start = week_end - timedelta(days=7)

            # Shift back by week_offset
            week_start = week_start - timedelta(weeks=week_offset)
            week_end = week_end - timedelta(weeks=week_offset)

            try:
                exception_analysis = await analytics_engine.calculate_exception_analysis(week_start, week_end)
                exception_analytics.append({
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "total_exceptions": exception_analysis.total_exceptions,
                    "resolution_rate": exception_analysis.resolution_rate_percentage,
                    "avg_resolution_time": exception_analysis.average_resolution_time_hours,
                    "business_impact": exception_analysis.business_impact_score,
                    "top_exception_types": exception_analysis.top_exception_types[:3]
                })
            except Exception as e:
                logger.warning(f"Failed to get exception analysis for week {week_start}: {e}")
                continue

        # Calculate trends
        if len(exception_analytics) >= 2:
            latest_resolution_rate = exception_analytics[0]["resolution_rate"]
            previous_resolution_rate = exception_analytics[1]["resolution_rate"]
            resolution_trend = ((latest_resolution_rate - previous_resolution_rate) / previous_resolution_rate * 100) if previous_resolution_rate > 0 else 0
        else:
            resolution_trend = 0

        return {
            "exception_analytics": exception_analytics,
            "summary": {
                "weeks_analyzed": len(exception_analytics),
                "current_resolution_rate": exception_analytics[0]["resolution_rate"] if exception_analytics else 0,
                "resolution_trend_percentage": resolution_trend,
                "total_exceptions_this_week": exception_analytics[0]["total_exceptions"] if exception_analytics else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get exception analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/slo")
async def get_slo_analytics(
    weeks: int = Query(4, ge=1, le=52, description="Number of weeks to analyze"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get SLO analytics for recent weeks."""
    try:
        # Get SLO metrics for recent weeks
        slo_analytics = []

        for week_offset in range(weeks):
            week_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_end - timedelta(days=week_end.weekday())
            week_start = week_end - timedelta(days=7)

            # Shift back by week_offset
            week_start = week_start - timedelta(weeks=week_offset)
            week_end = week_end - timedelta(weeks=week_offset)

            try:
                slo_query = select(SLOMetric).where(
                    and_(
                        SLOMetric.week_start == week_start,
                        SLOMetric.week_end == week_end
                    )
                )
                slo_result = await session.execute(slo_query)
                slo_metrics = slo_result.scalars().all()

                week_slos = {
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "slos": [
                        {
                            "name": slo.slo_name,
                            "category": slo.slo_category.value,
                            "attainment": slo.attainment_percentage,
                            "target": slo.target_value,
                            "actual": slo.actual_value,
                            "error_budget_remaining": slo.error_budget_remaining
                        }
                        for slo in slo_metrics
                    ],
                    "overall_attainment": sum(slo.attainment_percentage for slo in slo_metrics) / len(slo_metrics) if slo_metrics else 0
                }
                slo_analytics.append(week_slos)

            except Exception as e:
                logger.warning(f"Failed to get SLO analysis for week {week_start}: {e}")
                continue

        return {
            "slo_analytics": slo_analytics,
            "summary": {
                "weeks_analyzed": len(slo_analytics),
                "current_overall_attainment": slo_analytics[0]["overall_attainment"] if slo_analytics else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get SLO analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions")
async def create_subscription(
    user_email: str,
    delivery_methods: List[str],
    recipient_groups: List[str],
    preferred_day_of_week: int = Query(1, ge=1, le=7),
    preferred_time: str = Query("09:00"),
    timezone: str = Query("UTC"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new report subscription."""
    try:
        email_service = EmailReportService(session)

        subscription = await email_service.create_subscription(
            user_id=str(current_user.id),
            user_email=user_email,
            delivery_methods=delivery_methods,
            recipient_groups=recipient_groups,
            preferred_day_of_week=preferred_day_of_week,
            preferred_time=preferred_time,
            timezone=timezone
        )

        return {
            "subscription_id": str(subscription.id),
            "user_email": subscription.user_email,
            "delivery_methods": subscription.delivery_methods,
            "recipient_groups": subscription.recipient_groups,
            "preferred_day_of_week": subscription.preferred_day_of_week,
            "preferred_time": subscription.preferred_time,
            "timezone": subscription.timezone,
            "is_active": subscription.is_active,
            "message": "Subscription created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def list_subscriptions(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List user's report subscriptions."""
    try:
        query = select(ReportSubscription).where(
            and_(
                ReportSubscription.user_id == str(current_user.id),
                ReportSubscription.is_active == True
            )
        ).order_by(desc(ReportSubscription.created_at))

        result = await session.execute(query)
        subscriptions = result.scalars().all()

        return {
            "subscriptions": [
                {
                    "id": str(sub.id),
                    "user_email": sub.user_email,
                    "report_type": sub.report_type.value,
                    "delivery_methods": sub.delivery_methods,
                    "recipient_groups": sub.recipient_groups,
                    "preferred_day_of_week": sub.preferred_day_of_week,
                    "preferred_time": sub.preferred_time,
                    "timezone": sub.timezone,
                    "include_pdf_attachment": sub.include_pdf_attachment,
                    "include_raw_data": sub.include_raw_data,
                    "last_delivered_at": sub.last_delivered_at.isoformat() if sub.last_delivered_at else None,
                    "delivery_count": sub.delivery_count,
                    "failed_delivery_count": sub.failed_delivery_count
                }
                for sub in subscriptions
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    preferences: Dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update subscription preferences."""
    try:
        email_service = EmailReportService(session)

        subscription = await email_service.update_subscription_preferences(
            subscription_id=subscription_id,
            preferences=preferences
        )

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return {
            "message": "Subscription updated successfully",
            "subscription_id": subscription_id,
            "updated_fields": list(preferences.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def unsubscribe(
    subscription_id: str,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Unsubscribe from reports."""
    try:
        email_service = EmailReportService(session)

        # Verify subscription belongs to current user
        query = select(ReportSubscription).where(
            and_(
                ReportSubscription.id == subscription_id,
                ReportSubscription.user_id == str(current_user.id)
            )
        )
        result = await session.execute(query)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Unsubscribe user
        success = await email_service.unsubscribe_user(
            user_id=str(current_user.id),
            reason=reason
        )

        if success:
            return {
                "message": "Successfully unsubscribed from reports",
                "subscription_id": subscription_id,
                "reason": reason
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to unsubscribe")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unsubscribe {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_csv_export(report: WeeklyReport) -> Dict[str, Any]:
    """Generate CSV export data for a report."""
    try:
        if not report.content_json:
            return {"error": "No content available for export"}

        content = report.content_json

        # Extract key metrics for CSV
        csv_data = {
            "report_metadata": {
                "title": report.title,
                "week_start": report.week_start.isoformat(),
                "week_end": report.week_end.isoformat(),
                "generated_at": report.generated_at.isoformat() if report.generated_at else None
            },
            "summary_metrics": {
                "total_invoices": content.get("performance_overview", {}).get("volume_metrics", {}).get("total_invoices", 0),
                "success_rate": content.get("performance_overview", {}).get("volume_metrics", {}).get("success_rate", 0),
                "cost_per_invoice": content.get("cost_analysis", {}).get("weekly_costs", {}).get("cost_per_invoice", 0),
                "total_exceptions": content.get("exception_analysis", {}).get("exception_summary", {}).get("total_exceptions", 0),
                "resolution_rate": content.get("exception_analysis", {}).get("exception_summary", {}).get("resolution_rate_percentage", 0)
            }
        }

        return csv_data

    except Exception as e:
        logger.error(f"Failed to generate CSV export: {e}")
        return {"error": "Failed to generate CSV export"}


# CFO Digest Endpoints

@router.post("/cfo-digest/generate", response_model=CFODigestResponse)
async def generate_cfo_digest(
    request: CFODigestRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CFODigestResponse:
    """Generate Monday 9am CFO Digest with executive insights and evidence links."""
    try:
        logger.info(f"Generating CFO digest for user: {current_user.email}")

        # Initialize services
        cfo_digest_service = CFODigestService(session)
        n8n_service = N8nService()

        # Generate digest
        digest = await cfo_digest_service.generate_monday_digest(
            request=request,
            generated_by=current_user.email
        )

        # Save digest to database
        digest_id = await cfo_digest_service.save_digest_to_database(digest)

        # Schedule delivery if requested
        if request.schedule_delivery and request.recipients:
            n8n_request = await cfo_digest_service.create_n8n_workflow_request(digest)

            # Schedule background task for N8n workflow
            background_tasks.add_task(
                n8n_service.schedule_monday_digest,
                n8n_request
            )

        return CFODigestResponse(
            success=True,
            digest_id=digest_id,
            message="Monday CFO Digest generated successfully",
            data={
                "title": digest.title,
                "week_start": digest.week_start.isoformat(),
                "week_end": digest.week_end.isoformat(),
                "delivery_scheduled_at": digest.delivery_scheduled_at.isoformat() if digest.delivery_scheduled_at else None,
                "total_metrics": len(digest.key_metrics),
                "total_action_items": len(digest.action_items)
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate CFO digest: {e}")
        return CFODigestResponse(
            success=False,
            message=f"Failed to generate CFO digest: {str(e)}",
            errors=[str(e)]
        )


@router.get("/cfo-digest/schedule", response_model=CFODigestScheduleResponse)
async def get_cfo_digest_schedule(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CFODigestScheduleResponse:
    """Get current Monday CFO Digest schedule configuration."""
    try:
        # This would retrieve from database - placeholder implementation
        schedule_data = {
            "is_active": True,
            "delivery_day": "monday",
            "delivery_time": "09:00",
            "recipients": ["cfo@company.com", "finance-team@company.com"],
            "priority_threshold": "medium",
            "business_impact_threshold": "moderate"
        }

        # Calculate next delivery
        today = datetime.now(timezone.utc)
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_delivery = today + timedelta(days=days_until_monday)
        next_monday_9am = next_delivery.replace(hour=9, minute=0, second=0, microsecond=0)

        return CFODigestScheduleResponse(
            success=True,
            schedule_id="default_schedule",
            message="Monday CFO Digest schedule retrieved successfully",
            next_delivery=next_monday_9am.isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to get CFO digest schedule: {e}")
        return CFODigestScheduleResponse(
            success=False,
            message=f"Failed to get schedule: {str(e)}"
        )


@router.post("/cfo-digest/schedule", response_model=CFODigestScheduleResponse)
async def update_cfo_digest_schedule(
    request: CFODigestScheduleRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CFODigestScheduleResponse:
    """Update Monday CFO Digest schedule configuration."""
    try:
        logger.info(f"Updating CFO digest schedule for user: {current_user.email}")

        # Initialize N8n service
        n8n_service = N8nService()

        # Setup schedule with N8n workflow
        schedule_config = request.model_dump()
        schedule_response = await n8n_service.setup_monday_digest_schedule(schedule_config)

        # Calculate next delivery
        today = datetime.now(timezone.utc)
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_delivery = today + timedelta(days=days_until_monday)
        next_monday_9am = next_delivery.replace(hour=9, minute=0, second=0, microsecond=0)

        return CFODigestScheduleResponse(
            success=True,
            schedule_id="updated_schedule",
            message="Monday CFO Digest schedule updated successfully",
            next_delivery=next_monday_9am.isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to update CFO digest schedule: {e}")
        return CFODigestScheduleResponse(
            success=False,
            message=f"Failed to update schedule: {str(e)}"
        )


@router.get("/cfo-digest/{digest_id}")
async def get_cfo_digest(
    digest_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific CFO digest by ID."""
    try:
        logger.info(f"Retrieving CFO digest: {digest_id}")

        # Initialize service
        cfo_digest_service = CFODigestService(session)

        # Get digest
        digest = await cfo_digest_service.get_digest_by_id(digest_id)
        if not digest:
            raise HTTPException(status_code=404, detail="CFO Digest not found")

        return {
            "success": True,
            "data": digest.model_dump(),
            "message": "CFO Digest retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CFO digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo-digest", response_model=CFODigestListResponse)
async def list_cfo_digests(
    limit: int = Query(10, ge=1, le=52, description="Number of digests to return"),
    page: int = Query(1, ge=1, description="Page number"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CFODigestListResponse:
    """List recent CFO digests."""
    try:
        logger.info(f"Listing CFO digests for user: {current_user.email}")

        # Initialize service
        cfo_digest_service = CFODigestService(session)

        # Get digests
        digests = await cfo_digest_service.list_recent_digests(limit)

        # Pagination logic
        page_size = limit
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_digests = digests[start_idx:end_idx]

        return CFODigestListResponse(
            digests=paginated_digests,
            total_count=len(digests),
            page=page,
            page_size=page_size,
            has_more=end_idx < len(digests)
        )

    except Exception as e:
        logger.error(f"Failed to list CFO digests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cfo-digest/{digest_id}/schedule-delivery")
async def schedule_cfo_digest_delivery(
    digest_id: str,
    recipients: List[str] = Query(..., description="List of recipient email addresses"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Schedule delivery of an existing CFO digest."""
    try:
        logger.info(f"Scheduling delivery for CFO digest: {digest_id}")

        # Initialize services
        cfo_digest_service = CFODigestService(session)
        n8n_service = N8nService()

        # Get digest
        digest = await cfo_digest_service.get_digest_by_id(digest_id)
        if not digest:
            raise HTTPException(status_code=404, detail="CFO Digest not found")

        # Update recipients and schedule delivery
        digest.recipients = recipients
        n8n_request = await cfo_digest_service.create_n8n_workflow_request(digest)

        # Schedule background task
        background_tasks.add_task(
            n8n_service.schedule_monday_digest,
            n8n_request
        )

        return {
            "success": True,
            "message": f"CFO Digest {digest_id} scheduled for delivery",
            "recipients": recipients,
            "scheduled_for": "Monday 9:00 AM"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule CFO digest delivery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cfo-digest/{digest_id}/cancel")
async def cancel_cfo_digest(
    digest_id: str,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel scheduled CFO digest."""
    try:
        logger.info(f"Cancelling CFO digest: {digest_id}")

        # Initialize N8n service
        n8n_service = N8nService()

        # Cancel digest in background
        background_tasks.add_task(
            n8n_service.cancel_monday_digest,
            digest_id,
            reason
        )

        return {
            "success": True,
            "message": f"CFO Digest {digest_id} cancellation requested",
            "reason": reason or "No reason provided"
        }

    except Exception as e:
        logger.error(f"Failed to cancel CFO digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cfo-digest/trigger")
async def trigger_cfo_digest_generation(
    week_start: Optional[str] = Query(None, description="ISO format date for week start"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Trigger immediate CFO digest generation."""
    try:
        logger.info(f"Triggering CFO digest generation for user: {current_user.email}")

        # Parse week start date
        week_start_dt = None
        if week_start:
            try:
                week_start_dt = datetime.fromisoformat(week_start.replace('Z', '+00:00'))
                if week_start_dt.tzinfo is None:
                    week_start_dt = week_start_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

        # Initialize N8n service
        n8n_service = N8nService()

        # Trigger generation in background
        background_tasks.add_task(
            n8n_service.trigger_monday_digest_generation,
            week_start_dt
        )

        return {
            "success": True,
            "message": "CFO Digest generation triggered successfully",
            "week_start": week_start_dt.isoformat() if week_start_dt else "Last week",
            "delivery_target": "Monday 9:00 AM"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger CFO digest generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))