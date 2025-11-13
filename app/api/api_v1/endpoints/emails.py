"""
API endpoints for email ingestion and management.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1 import deps
from app.api.schemas.email import (
    EmailAuthorizationRequest,
    EmailAuthorizationResponse,
    EmailCredentialsCreate,
    EmailCredentialsResponse,
    EmailMonitoringConfigCreate,
    EmailMonitoringConfigResponse,
    EmailSearchRequest,
    EmailSearchResponse,
    EmailIngestionRequest,
    EmailIngestionResponse,
    EmailStatisticsResponse,
)
from app.models.email import Email, EmailCredentials, EmailMonitoringConfig
from app.services.email_ingestion_service import EmailIngestionService
from app.services.gmail_service import GmailService
from app.workers.email_tasks import (
    monitor_gmail_inbox,
    schedule_email_monitoring,
    get_email_monitoring_task_status,
    cancel_email_monitoring,
    get_active_email_tasks,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/authorize/gmail", response_model=EmailAuthorizationResponse)
async def authorize_gmail(
    request: EmailAuthorizationRequest,
    db: AsyncSession = Depends(deps.get_db),
) -> EmailAuthorizationResponse:
    """Get Gmail OAuth authorization URL."""
    try:
        gmail_service = GmailService()
        authorization_url, state = await gmail_service.get_authorization_url(
            redirect_uri=request.redirect_uri,
            state=request.state
        )

        return EmailAuthorizationResponse(
            authorization_url=authorization_url,
            state=state,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

    except Exception as e:
        logger.error(f"Gmail authorization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.post("/credentials/gmail", response_model=EmailCredentialsResponse)
async def store_gmail_credentials(
    request: EmailCredentialsCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> EmailCredentialsResponse:
    """Store Gmail OAuth credentials."""
    try:
        gmail_service = GmailService()

        # Exchange authorization code for credentials
        credentials = await gmail_service.exchange_code_for_credentials(
            authorization_code=request.authorization_code,
            redirect_uri=request.redirect_uri
        )

        # Build service to validate credentials and get user info
        await gmail_service.build_service(credentials)
        user_info = await gmail_service.get_user_info()

        # Create credentials record
        # In a real implementation, you would encrypt the credentials
        db_credentials = EmailCredentials(
            user_id=request.user_id,
            provider="gmail",
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=credentials.expiry,
            provider_user_id=user_info["email_address"],
            provider_email=user_info["email_address"],
            last_validated=datetime.utcnow()
        )

        db.add(db_credentials)
        await db.commit()
        await db.refresh(db_credentials)

        return EmailCredentialsResponse(
            id=str(db_credentials.id),
            provider="gmail",
            provider_email=user_info["email_address"],
            is_active=True,
            created_at=db_credentials.created_at,
            last_validated=db_credentials.last_validated
        )

    except Exception as e:
        logger.error(f"Failed to store Gmail credentials: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to store credentials: {str(e)}"
        )


@router.post("/ingest/gmail", response_model=EmailIngestionResponse)
async def ingest_gmail_emails(
    request: EmailIngestionRequest,
    db: AsyncSession = Depends(deps.get_db),
) -> EmailIngestionResponse:
    """Manually trigger Gmail email ingestion."""
    try:
        # Get credentials from database
        credentials = await db.get(EmailCredentials, request.credentials_id)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credentials not found"
            )

        # Convert to GmailCredentials format
        from app.services.gmail_service import GmailCredentials
        gmail_creds = GmailCredentials(
            token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            client_id="",  # These would come from settings
            client_secret="",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )

        # Trigger background task
        task = monitor_gmail_inbox.delay(
            user_id=str(credentials.user_id),
            credentials_data=gmail_creds.model_dump(),
            days_back=request.days_back,
            max_emails=request.max_emails,
            auto_process=request.auto_process
        )

        return EmailIngestionResponse(
            task_id=task.id,
            status="started",
            user_id=str(credentials.user_id),
            estimated_emails=request.max_emails,
            started_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/monitoring/config", response_model=EmailMonitoringConfigResponse)
async def create_monitoring_config(
    request: EmailMonitoringConfigCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> EmailMonitoringConfigResponse:
    """Create email monitoring configuration."""
    try:
        # Validate credentials exist
        credentials = await db.get(EmailCredentials, request.credentials_id)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credentials not found"
            )

        # Create monitoring config
        config = EmailMonitoringConfig(
            user_id=request.user_id,
            credentials_id=request.credentials_id,
            is_active=request.is_active,
            monitoring_interval_minutes=request.monitoring_interval_minutes,
            days_back_to_process=request.days_back_to_process,
            max_emails_per_run=request.max_emails_per_run,
            email_filters=request.email_filters,
            trusted_senders=request.trusted_senders,
            blocked_senders=request.blocked_senders,
            auto_process_invoices=request.auto_process_invoices,
            security_validation_enabled=request.security_validation_enabled
        )

        db.add(config)
        await db.commit()
        await db.refresh(config)

        # Schedule monitoring task if active
        if request.is_active:
            from app.services.gmail_service import GmailCredentials
            gmail_creds = GmailCredentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                client_id="",
                client_secret="",
                scopes=["https://www.googleapis.com/auth/gmail.readonly"]
            )

            schedule_task = schedule_email_monitoring.delay(
                user_id=str(request.user_id),
                credentials_data=gmail_creds.model_dump(),
                schedule_minutes=request.monitoring_interval_minutes
            )

            logger.info(f"Scheduled monitoring task {schedule_task.id} for user {request.user_id}")

        return EmailMonitoringConfigResponse(
            id=str(config.id),
            user_id=str(config.user_id),
            is_active=config.is_active,
            monitoring_interval_minutes=config.monitoring_interval_minutes,
            created_at=config.created_at,
            last_run_at=config.last_run_at,
            next_run_at=config.next_run_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create monitoring config: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create monitoring config: {str(e)}"
        )


@router.get("/monitoring/status/{user_id}")
async def get_monitoring_status(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Get monitoring status for a user."""
    try:
        # Get task status
        task_status = get_email_monitoring_task_status(user_id)

        # Get monitoring configs
        result = await db.execute(
            "SELECT * FROM email_monitoring_configs WHERE user_id = :user_id",
            {"user_id": user_id}
        )
        configs = result.fetchall()

        return {
            "user_id": user_id,
            "task_status": task_status,
            "monitoring_configs": len(configs),
            "active_configs": sum(1 for c in configs if c.is_active),
            "checked_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitoring status: {str(e)}"
        )


@router.delete("/monitoring/{user_id}")
async def stop_monitoring(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Stop email monitoring for a user."""
    try:
        # Cancel scheduled task
        cancelled = cancel_email_monitoring(user_id)

        # Deactivate monitoring configs
        await db.execute(
            "UPDATE email_monitoring_configs SET is_active = false WHERE user_id = :user_id",
            {"user_id": user_id}
        )
        await db.commit()

        return {
            "user_id": user_id,
            "cancelled": cancelled,
            "stopped_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop monitoring: {str(e)}"
        )


@router.get("/search", response_model=EmailSearchResponse)
async def search_emails(
    user_id: str = Query(..., description="User ID"),
    query: str = Query(None, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(deps.get_db),
) -> EmailSearchResponse:
    """Search for processed emails."""
    try:
        # Build search query
        sql = """
            SELECT e.*, COUNT(a.id) as attachment_count
            FROM emails e
            LEFT JOIN email_attachments a ON e.id = a.email_id
            WHERE e.user_id = :user_id
        """
        params = {"user_id": user_id}

        if query:
            sql += " AND (e.subject ILIKE :query OR e.from_email ILIKE :query)"
            params["query"] = f"%{query}%"

        sql += " GROUP BY e.id ORDER BY e.date_sent DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        result = await db.execute(sql, params)
        emails = result.fetchall()

        # Get total count
        count_sql = "SELECT COUNT(*) FROM emails WHERE user_id = :user_id"
        if query:
            count_sql += " AND (subject ILIKE :query OR from_email ILIKE :query)"

        count_result = await db.execute(count_sql, params)
        total = count_result.scalar()

        return EmailSearchResponse(
            emails=[{
                "id": str(email.id),
                "subject": email.subject,
                "from_email": email.from_email,
                "date_sent": email.date_sent,
                "status": email.status,
                "attachment_count": email.attachment_count,
                "security_flags": email.security_flags
            } for email in emails],
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Email search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/statistics/{user_id}", response_model=EmailStatisticsResponse)
async def get_email_statistics(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: AsyncSession = Depends(deps.get_db),
) -> EmailStatisticsResponse:
    """Get email processing statistics."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get statistics
        stats_sql = """
            SELECT
                COUNT(*) as total_emails,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_emails,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_emails,
                COUNT(CASE WHEN status = 'blocked' THEN 1 END) as blocked_emails,
                AVG(CASE WHEN status = 'processed' THEN
                    EXTRACT(EPOCH FROM (processed_at - created_at)) * 1000
                END) as avg_processing_time_ms
            FROM emails
            WHERE user_id = :user_id AND created_at >= :cutoff_date
        """

        result = await db.execute(stats_sql, {"user_id": user_id, "cutoff_date": cutoff_date})
        stats = result.fetchone()

        # Get attachment statistics
        attachment_sql = """
            SELECT
                COUNT(*) as total_attachments,
                COUNT(CASE WHEN is_pdf THEN 1 END) as pdf_attachments,
                COUNT(CASE WHEN is_processed THEN 1 END) as processed_attachments
            FROM email_attachments a
            JOIN emails e ON a.email_id = e.id
            WHERE e.user_id = :user_id AND a.created_at >= :cutoff_date
        """

        attachment_result = await db.execute(attachment_sql, {"user_id": user_id, "cutoff_date": cutoff_date})
        attachment_stats = attachment_result.fetchone()

        return EmailStatisticsResponse(
            user_id=user_id,
            period_days=days,
            total_emails=stats.total_emails or 0,
            processed_emails=stats.processed_emails or 0,
            failed_emails=stats.failed_emails or 0,
            blocked_emails=stats.blocked_emails or 0,
            total_attachments=attachment_stats.total_attachments or 0,
            pdf_attachments=attachment_stats.pdf_attachments or 0,
            processed_attachments=attachment_stats.processed_attachments or 0,
            avg_processing_time_ms=int(stats.avg_processing_time_ms or 0),
            success_rate=(
                (stats.processed_emails / stats.total_emails * 100) if stats.total_emails > 0 else 0
            ),
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Failed to get email statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get("/health")
async def email_health_check() -> Dict[str, Any]:
    """Health check for email services."""
    try:
        ingestion_service = EmailIngestionService()
        health_status = await ingestion_service.health_check()

        return {
            "status": "healthy",
            "services": health_status,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Email health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/tasks/active")
async def get_active_tasks() -> Dict[str, Any]:
    """Get list of active email monitoring tasks."""
    try:
        active_tasks = get_active_email_tasks()

        return {
            "active_tasks": active_tasks,
            "total_active": len(active_tasks),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active tasks: {str(e)}"
        )