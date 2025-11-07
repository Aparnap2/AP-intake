"""
Email API schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmailAuthorizationRequest(BaseModel):
    """Request for Gmail authorization."""
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    state: Optional[str] = Field(None, description="OAuth state parameter")


class EmailAuthorizationResponse(BaseModel):
    """Response with Gmail authorization URL."""
    authorization_url: str = Field(..., description="Authorization URL for user")
    state: str = Field(..., description="OAuth state parameter")
    expires_at: datetime = Field(..., description="Authorization URL expiration")


class EmailCredentialsCreate(BaseModel):
    """Request to create email credentials."""
    user_id: str = Field(..., description="User ID")
    authorization_code: str = Field(..., description="OAuth authorization code")
    redirect_uri: str = Field(..., description="OAuth redirect URI")


class EmailCredentialsResponse(BaseModel):
    """Email credentials response."""
    id: str = Field(..., description="Credentials ID")
    provider: str = Field(..., description="Email provider")
    provider_email: str = Field(..., description="Provider email address")
    is_active: bool = Field(..., description="Whether credentials are active")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_validated: Optional[datetime] = Field(None, description="Last validation timestamp")


class EmailMonitoringConfigCreate(BaseModel):
    """Request to create monitoring configuration."""
    user_id: str = Field(..., description="User ID")
    credentials_id: str = Field(..., description="Credentials ID to use")
    is_active: bool = Field(True, description="Whether monitoring is active")
    monitoring_interval_minutes: int = Field(60, description="Monitoring interval in minutes")
    days_back_to_process: int = Field(7, description="Days back to process emails")
    max_emails_per_run: int = Field(50, description="Maximum emails per run")
    email_filters: Optional[List[str]] = Field(None, description="Email search filters")
    trusted_senders: Optional[List[str]] = Field(None, description="Trusted sender domains")
    blocked_senders: Optional[List[str]] = Field(None, description="Blocked sender domains")
    auto_process_invoices: bool = Field(True, description="Auto-process found invoices")
    security_validation_enabled: bool = Field(True, description="Enable security validation")


class EmailMonitoringConfigResponse(BaseModel):
    """Email monitoring configuration response."""
    id: str = Field(..., description="Configuration ID")
    user_id: str = Field(..., description="User ID")
    is_active: bool = Field(..., description="Whether monitoring is active")
    monitoring_interval_minutes: int = Field(..., description="Monitoring interval in minutes")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_run_at: Optional[datetime] = Field(None, description="Last run timestamp")
    next_run_at: Optional[datetime] = Field(None, description="Next scheduled run")


class EmailIngestionRequest(BaseModel):
    """Request for email ingestion."""
    credentials_id: str = Field(..., description="Credentials ID to use")
    days_back: int = Field(7, description="Days back to process")
    max_emails: int = Field(50, description="Maximum emails to process")
    auto_process: bool = Field(True, description="Auto-process found invoices")


class EmailIngestionResponse(BaseModel):
    """Email ingestion response."""
    task_id: str = Field(..., description="Background task ID")
    status: str = Field(..., description="Ingestion status")
    user_id: str = Field(..., description="User ID")
    estimated_emails: int = Field(..., description="Estimated number of emails")
    started_at: datetime = Field(..., description="Start timestamp")


class EmailSearchRequest(BaseModel):
    """Email search request."""
    query: Optional[str] = Field(None, description="Search query")
    limit: int = Field(50, ge=1, le=100, description="Maximum results")
    offset: int = Field(0, ge=0, description="Results offset")


class EmailSearchResponse(BaseModel):
    """Email search response."""
    emails: List[Dict[str, Any]] = Field(..., description="Found emails")
    total: int = Field(..., description="Total number of results")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Results offset")


class EmailStatisticsResponse(BaseModel):
    """Email processing statistics."""
    user_id: str = Field(..., description="User ID")
    period_days: int = Field(..., description="Statistics period in days")
    total_emails: int = Field(..., description="Total emails processed")
    processed_emails: int = Field(..., description="Successfully processed emails")
    failed_emails: int = Field(..., description="Failed email processing")
    blocked_emails: int = Field(..., description="Blocked due to security")
    total_attachments: int = Field(..., description="Total attachments found")
    pdf_attachments: int = Field(..., description="PDF attachments found")
    processed_attachments: int = Field(..., description="Processed attachments")
    avg_processing_time_ms: int = Field(..., description="Average processing time in milliseconds")
    success_rate: float = Field(..., description="Processing success rate percentage")
    generated_at: datetime = Field(..., description="Statistics generation timestamp")


class EmailMessage(BaseModel):
    """Email message model."""
    id: str = Field(..., description="Message ID")
    thread_id: str = Field(..., description="Thread ID")
    subject: str = Field(..., description="Email subject")
    from_email: str = Field(..., description="Sender email")
    to_emails: List[str] = Field(..., description="Recipient emails")
    date: datetime = Field(..., description="Email date")
    body: str = Field(..., description="Email body text")
    attachments: List[Dict[str, Any]] = Field(..., description="Email attachments")
    labels: List[str] = Field(..., description="Email labels")
    snippet: str = Field(..., description="Email snippet")


class EmailAttachment(BaseModel):
    """Email attachment model."""
    filename: str = Field(..., description="Attachment filename")
    content_type: str = Field(..., description="MIME content type")
    size: int = Field(..., description="Attachment size in bytes")
    content_hash: str = Field(..., description="SHA-256 content hash")
    is_pdf: bool = Field(..., description="Whether attachment is PDF")
    storage_path: Optional[str] = Field(None, description="Storage file path")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted invoice data")


class EmailProcessingLog(BaseModel):
    """Email processing log entry."""
    step: str = Field(..., description="Processing step")
    status: str = Field(..., description="Processing status")
    message: Optional[str] = Field(None, description="Log message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    started_at: datetime = Field(..., description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    duration_ms: Optional[int] = Field(None, description="Step duration in milliseconds")
    error_type: Optional[str] = Field(None, description="Error type if failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class EmailSecurityRule(BaseModel):
    """Email security rule."""
    name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")
    rule_pattern: str = Field(..., description="Rule pattern")
    rule_action: str = Field(..., description="Rule action")
    is_active: bool = Field(True, description="Whether rule is active")
    priority: int = Field(100, description="Rule priority")
    description: Optional[str] = Field(None, description="Rule description")


class EmailHealthCheck(BaseModel):
    """Email service health check."""
    status: str = Field(..., description="Overall health status")
    services: Dict[str, Any] = Field(..., description="Individual service statuses")
    timestamp: datetime = Field(..., description="Health check timestamp")


class TaskStatus(BaseModel):
    """Background task status."""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    user_id: str = Field(..., description="User ID")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Task error if failed")
    progress: Optional[float] = Field(None, description="Task progress percentage")


class EmailFilter(BaseModel):
    """Email filter configuration."""
    name: str = Field(..., description="Filter name")
    query: str = Field(..., description="Gmail search query")
    is_active: bool = Field(True, description="Whether filter is active")
    priority: int = Field(100, description="Filter priority")


class BatchProcessRequest(BaseModel):
    """Batch email processing request."""
    email_ids: List[str] = Field(..., description="Email IDs to process")
    user_id: str = Field(..., description="User ID")
    credentials_id: str = Field(..., description="Credentials ID to use")
    auto_process: bool = Field(True, description="Auto-process found invoices")


class BatchProcessResponse(BaseModel):
    """Batch processing response."""
    task_id: str = Field(..., description="Background task ID")
    total_emails: int = Field(..., description="Total emails to process")
    status: str = Field(..., description="Batch processing status")
    started_at: datetime = Field(..., description="Start timestamp")