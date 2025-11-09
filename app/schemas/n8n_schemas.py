"""
Pydantic schemas for n8n integration data validation and serialization.
This module defines the data structures used for n8n workflow management,
webhook events, and integration with the AP/AR system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator


class N8nWorkflowType(str, Enum):
    """Enumeration of supported n8n workflow types."""
    AP_PROCESSING = "ap_processing"
    AR_PROCESSING = "ar_processing"
    WORKING_CAPITAL_ANALYSIS = "working_capital_analysis"
    CUSTOMER_ONBOARDING = "customer_onboarding"
    EXCEPTION_HANDLING = "exception_handling"
    WEEKLY_REPORT_GENERATION = "weekly_report_generation"
    CUSTOM = "custom"


class N8nExecutionStatus(str, Enum):
    """Enumeration of n8n workflow execution statuses."""
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    WAITING = "waiting"
    CRASHED = "crashed"


class N8nTriggerType(str, Enum):
    """Enumeration of n8n trigger types."""
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    EMAIL = "email"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"


class N8nWebhookEvent(BaseModel):
    """Schema for n8n webhook events."""
    workflow_id: str = Field(..., description="ID of the workflow that triggered the event")
    execution_id: str = Field(..., description="ID of the workflow execution")
    status: N8nExecutionStatus = Field(..., description="Status of the workflow execution")
    timestamp: datetime = Field(..., description="Timestamp when the event occurred")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data payload")
    signature: Optional[str] = Field(None, description="Webhook signature for validation")
    workflow_type: Optional[N8nWorkflowType] = Field(None, description="Type of workflow")

    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp is not in the future."""
        if v > datetime.utcnow():
            raise ValueError("Timestamp cannot be in the future")
        return v


class N8nWorkflowTrigger(BaseModel):
    """Schema for n8n workflow trigger configuration."""
    type: N8nTriggerType = Field(..., description="Type of trigger")
    config: Dict[str, Any] = Field(..., description="Trigger configuration")
    name: Optional[str] = Field(None, description="Trigger name")
    position: Optional[Dict[str, int]] = Field(None, description="Position in workflow diagram")

    @validator('config')
    def validate_config(cls, v, values):
        """Validate trigger configuration based on trigger type."""
        trigger_type = values.get('type')

        if trigger_type == N8nTriggerType.WEBHOOK:
            if 'path' not in v:
                raise ValueError("Webhook trigger requires 'path' in config")
        elif trigger_type == N8nTriggerType.SCHEDULE:
            if 'interval' not in v and 'cron' not in v:
                raise ValueError("Schedule trigger requires 'interval' or 'cron' in config")

        return v


class N8nWorkflowNode(BaseModel):
    """Schema for n8n workflow node configuration."""
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type (e.g., 'function', 'action', 'trigger')")
    name: str = Field(..., description="Node name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Node configuration")
    position: Optional[Dict[str, int]] = Field(None, description="Position in workflow diagram")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Node parameters")
    credentials: Optional[Dict[str, str]] = Field(None, description="Node credentials reference")

    @validator('id')
    def validate_node_id(cls, v):
        """Validate node ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Node ID must be a non-empty string")
        return v


class N8nWorkflowTemplate(BaseModel):
    """Schema for n8n workflow template."""
    id: Optional[str] = Field(None, description="Template ID (auto-generated for new templates)")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    workflow_type: N8nWorkflowType = Field(..., description="Type of workflow")
    version: str = Field(default="1.0.0", description="Template version")
    active: bool = Field(default=True, description="Whether the template is active")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    triggers: List[N8nWorkflowTrigger] = Field(default_factory=list, description="Workflow triggers")
    nodes: List[N8nWorkflowNode] = Field(default_factory=list, description="Workflow nodes")
    connections: Optional[Dict[str, Any]] = Field(None, description="Node connections")
    settings: Optional[Dict[str, Any]] = Field(None, description="Workflow settings")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @validator('version')
    def validate_version(cls, v):
        """Validate semantic version format."""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError("Version must follow semantic versioning (e.g., '1.0.0')")
        return v


class N8nWorkflowExecutionRequest(BaseModel):
    """Schema for n8n workflow execution requests."""
    workflow_id: str = Field(..., description="ID of the workflow to execute")
    data: Dict[str, Any] = Field(..., description="Data to pass to the workflow")
    start_node: Optional[str] = Field(None, description="Specific node to start execution from")
    execution_mode: Optional[str] = Field(default="sync", description="Execution mode (sync/async)")
    priority: Optional[int] = Field(default=0, description="Execution priority")
    retry_on_failure: Optional[bool] = Field(default=False, description="Whether to retry on failure")
    max_retries: Optional[int] = Field(default=3, description="Maximum retry attempts")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds")

    @validator('workflow_id')
    def validate_workflow_id(cls, v):
        """Validate workflow ID is not empty."""
        if not v or not isinstance(v, str):
            raise ValueError("Workflow ID must be a non-empty string")
        return v

    @validator('execution_mode')
    def validate_execution_mode(cls, v):
        """Validate execution mode."""
        if v not in ['sync', 'async']:
            raise ValueError("Execution mode must be 'sync' or 'async'")
        return v


class N8nWorkflowExecutionResponse(BaseModel):
    """Schema for n8n workflow execution responses."""
    execution_id: str = Field(..., description="Workflow execution ID")
    workflow_id: str = Field(..., description="Workflow ID")
    status: N8nExecutionStatus = Field(..., description="Execution status")
    started_at: datetime = Field(..., description="Execution start time")
    finished_at: Optional[datetime] = Field(None, description="Execution finish time")
    data: Optional[Dict[str, Any]] = Field(None, description="Execution result data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details if execution failed")
    runtime_ms: Optional[int] = Field(None, description="Execution runtime in milliseconds")
    node_results: Optional[Dict[str, Any]] = Field(None, description="Results from individual nodes")
    logs: Optional[List[str]] = Field(None, description="Execution logs")

    @validator('runtime_ms')
    def validate_runtime(cls, v, values):
        """Validate runtime is reasonable."""
        if v is not None and (v < 0 or v > 86400000):  # Max 24 hours
            raise ValueError("Runtime must be between 0 and 86400000 milliseconds")
        return v


class N8nAPInvoiceData(BaseModel):
    """Schema for AP invoice data passed to n8n workflows."""
    invoice_id: str = Field(..., description="Invoice ID")
    vendor_id: str = Field(..., description="Vendor ID")
    vendor_name: str = Field(..., description="Vendor name")
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: datetime = Field(..., description="Invoice date")
    due_date: datetime = Field(..., description="Due date")
    total_amount: float = Field(..., description="Total invoice amount")
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(..., description="Invoice status")
    line_items: List[Dict[str, Any]] = Field(default_factory=list, description="Invoice line items")
    extraction_confidence: Optional[float] = Field(None, description="Extraction confidence score")
    validation_passed: Optional[bool] = Field(None, description="Whether validation passed")
    validation_issues: Optional[List[Dict[str, Any]]] = Field(None, description="Validation issues")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator('total_amount')
    def validate_total_amount(cls, v):
        """Validate total amount is non-negative."""
        if v < 0:
            raise ValueError("Total amount must be non-negative")
        return v


class N8nARInvoiceData(BaseModel):
    """Schema for AR invoice data passed to n8n workflows."""
    invoice_id: str = Field(..., description="Invoice ID")
    customer_id: str = Field(..., description="Customer ID")
    customer_name: str = Field(..., description="Customer name")
    customer_email: str = Field(..., description="Customer email")
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: datetime = Field(..., description="Invoice date")
    due_date: datetime = Field(..., description="Due date")
    total_amount: float = Field(..., description="Total invoice amount")
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(..., description="Invoice status")
    line_items: List[Dict[str, Any]] = Field(default_factory=list, description="Invoice line items")
    payment_terms: Optional[str] = Field(None, description="Payment terms")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator('customer_email')
    def validate_customer_email(cls, v):
        """Validate customer email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid customer email format")
        return v


class N8nWorkingCapitalRequest(BaseModel):
    """Schema for working capital analysis requests."""
    analysis_date: datetime = Field(..., description="Date for analysis")
    period_days: int = Field(default=30, description="Analysis period in days")
    include_projections: bool = Field(default=True, description="Whether to include projections")
    customer_segments: Optional[List[str]] = Field(None, description="Customer segments to analyze")
    vendor_categories: Optional[List[str]] = Field(None, description="Vendor categories to analyze")

    @validator('period_days')
    def validate_period_days(cls, v):
        """Validate analysis period."""
        if v < 1 or v > 365:
            raise ValueError("Period days must be between 1 and 365")
        return v


class N8nCustomerOnboardingRequest(BaseModel):
    """Schema for customer onboarding requests."""
    customer_id: str = Field(..., description="Customer ID")
    customer_name: str = Field(..., description="Customer name")
    customer_email: str = Field(..., description="Customer email")
    billing_address: Dict[str, str] = Field(..., description="Billing address")
    payment_terms: str = Field(..., description="Payment terms")
    credit_limit: Optional[float] = Field(None, description="Credit limit")
    industry: Optional[str] = Field(None, description="Customer industry")
    contact_person: Optional[Dict[str, str]] = Field(None, description="Primary contact person")
    requirements: Optional[List[str]] = Field(None, description="Special requirements")

    @validator('credit_limit')
    def validate_credit_limit(cls, v):
        """Validate credit limit is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Credit limit must be non-negative")
        return v


class N8nExceptionHandlingRequest(BaseModel):
    """Schema for exception handling requests."""
    exception_id: str = Field(..., description="Exception ID")
    invoice_id: Optional[str] = Field(None, description="Related invoice ID")
    exception_type: str = Field(..., description="Exception type")
    severity: str = Field(..., description="Exception severity")
    description: str = Field(..., description="Exception description")
    auto_resolution_possible: bool = Field(default=False, description="Whether auto-resolution is possible")
    suggested_actions: Optional[List[str]] = Field(None, description="Suggested resolution actions")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Additional context data")
    assignee: Optional[str] = Field(None, description="Assigned user/team")

    @validator('severity')
    def validate_severity(cls, v):
        """Validate severity level."""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if v not in valid_severities:
            raise ValueError(f"Severity must be one of {valid_severities}")
        return v


class N8nWeeklyReportRequest(BaseModel):
    """Schema for weekly report generation requests."""
    report_date: datetime = Field(..., description="Report date (usually week end)")
    week_start: datetime = Field(..., description="Week start date")
    week_end: datetime = Field(..., description="Week end date")
    include_charts: bool = Field(default=True, description="Whether to include charts")
    recipients: List[str] = Field(default_factory=list, description="Report recipients")
    report_format: str = Field(default="pdf", description="Report format")
    custom_metrics: Optional[List[str]] = Field(None, description="Custom metrics to include")

    @validator('week_end')
    def validate_week_dates(cls, v, values):
        """Validate week dates are logical."""
        week_start = values.get('week_start')
        if week_start and v <= week_start:
            raise ValueError("Week end must be after week start")
        return v

    @validator('report_format')
    def validate_report_format(cls, v):
        """Validate report format."""
        valid_formats = ['pdf', 'excel', 'csv', 'json']
        if v not in valid_formats:
            raise ValueError(f"Report format must be one of {valid_formats}")
        return v


class N8nWorkflowMetrics(BaseModel):
    """Schema for workflow performance metrics."""
    workflow_id: str = Field(..., description="Workflow ID")
    workflow_name: str = Field(..., description="Workflow name")
    total_executions: int = Field(..., description="Total number of executions")
    successful_executions: int = Field(..., description="Number of successful executions")
    failed_executions: int = Field(..., description="Number of failed executions")
    average_execution_time_ms: float = Field(..., description="Average execution time in milliseconds")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")
    error_rate: float = Field(..., description="Error rate (0.0 to 1.0)")
    last_execution: Optional[datetime] = Field(None, description="Last execution timestamp")
    most_common_errors: Optional[List[Dict[str, Any]]] = Field(None, description="Most common errors")
    performance_trend: Optional[List[Dict[str, Any]]] = Field(None, description="Performance trend data")

    @validator('success_rate')
    def validate_success_rate(cls, v):
        """Validate success rate range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
        return v

    @validator('error_rate')
    def validate_error_rate(cls, v):
        """Validate error rate range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Error rate must be between 0.0 and 1.0")
        return v


class N8nConnectionInfo(BaseModel):
    """Schema for n8n connection information."""
    base_url: str = Field(..., description="n8n base URL")
    version: str = Field(..., description="n8n version")
    status: str = Field(..., description="Connection status")
    authenticated: bool = Field(..., description="Whether authentication succeeded")
    user_info: Optional[Dict[str, Any]] = Field(None, description="Authenticated user information")
    available_workflows: Optional[int] = Field(None, description="Number of available workflows")
    active_workflows: Optional[int] = Field(None, description="Number of active workflows")
    system_info: Optional[Dict[str, Any]] = Field(None, description="System information")

    @validator('base_url')
    def validate_base_url(cls, v):
        """Validate base URL format."""
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid base URL format")
        return v


class N8nApiResponse(BaseModel):
    """Generic schema for n8n API responses."""
    success: bool = Field(..., description="Whether the API call was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")
    message: Optional[str] = Field(None, description="Additional message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }