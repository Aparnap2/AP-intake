"""
Pydantic schemas for integration provider system.
Defines data structures for swappable integration architecture.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class IntegrationType(str, Enum):
    """Enumeration of supported integration types."""
    NATIVE = "native"
    N8N = "n8n"
    QUICKBOOKS = "quickbooks"
    CUSTOM = "custom"


class WorkflowType(str, Enum):
    """Enumeration of supported workflow types."""
    AP_INVOICE_PROCESSING = "ap_invoice_processing"
    AR_INVOICE_PROCESSING = "ar_invoice_processing"
    EXCEPTION_HANDLING = "exception_handling"
    WEEKLY_REPORT_GENERATION = "weekly_report_generation"
    APPROVAL_WORKFLOW = "approval_workflow"
    WORKING_CAPITAL_ANALYSIS = "working_capital_analysis"
    CUSTOM_WORKFLOW = "custom_workflow"


class WorkflowStatus(str, Enum):
    """Enumeration of workflow execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ProviderCapability(str, Enum):
    """Enumeration of provider capabilities."""
    WEBHOOK_SUPPORT = "webhook_support"
    VISUAL_WORKFLOW_EDITOR = "visual_workflow_editor"
    BATCH_PROCESSING = "batch_processing"
    PARALLEL_EXECUTION = "parallel_execution"
    RETRY_LOGIC = "retry_logic"
    ERROR_HANDLING = "error_handling"
    MONITORING = "monitoring"
    DRY_RUN = "dry_run"


class WorkflowExecutionRequest(BaseModel):
    """Schema for workflow execution requests."""
    workflow_type: WorkflowType = Field(..., description="Type of workflow to execute")
    data: Dict[str, Any] = Field(..., description="Workflow input data")
    provider_type: Optional[IntegrationType] = Field(None, description="Specific provider to use")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Execution options")
    priority: Optional[int] = Field(default=5, description="Execution priority (1-10)")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")
    dry_run: Optional[bool] = Field(False, description="Execute in dry-run mode")
    async_execution: Optional[bool] = Field(False, description="Execute asynchronously")
    callback_url: Optional[str] = Field(None, description="Webhook callback URL")
    retry_count: Optional[int] = Field(default=0, description="Number of retry attempts")
    max_retries: Optional[int] = Field(default=3, description="Maximum retry attempts")

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        """Validate priority is within valid range."""
        if v is not None and (v < 1 or v > 10):
            raise ValueError("Priority must be between 1 and 10")
        return v

    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout is reasonable."""
        if v is not None and (v < 1 or v > 3600):
            raise ValueError("Timeout must be between 1 and 3600 seconds")
        return v


class WorkflowExecutionResponse(BaseModel):
    """Schema for workflow execution responses."""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_type: WorkflowType = Field(..., description="Type of workflow executed")
    provider_type: IntegrationType = Field(..., description="Provider that executed the workflow")
    status: WorkflowStatus = Field(..., description="Execution status")
    started_at: datetime = Field(..., description="Execution start time")
    finished_at: Optional[datetime] = Field(None, description="Execution finish time")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution result data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details if execution failed")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    provider_details: Optional[Dict[str, Any]] = Field(None, description="Provider-specific details")
    logs: Optional[List[str]] = Field(None, description="Execution logs")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator('duration_ms')
    @classmethod
    def validate_duration(cls, v):
        """Validate duration is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Duration must be non-negative")
        return v


class ProviderCapabilities(BaseModel):
    """Schema for provider capabilities."""
    supported_workflows: List[WorkflowType] = Field(..., description="Supported workflow types")
    max_concurrent_workflows: int = Field(..., description="Maximum concurrent workflows")
    max_execution_time: Optional[int] = Field(None, description="Maximum execution time in seconds")
    features: List[ProviderCapability] = Field(..., description="Supported features")
    limitations: Optional[List[str]] = Field(None, description="Known limitations")
    performance_metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics")

    @field_validator('max_concurrent_workflows')
    @classmethod
    def validate_concurrent_workflows(cls, v):
        """Validate concurrent workflows limit is reasonable."""
        if v < 1 or v > 1000:
            raise ValueError("Max concurrent workflows must be between 1 and 1000")
        return v


class ProviderInfo(BaseModel):
    """Schema for provider information."""
    provider_type: IntegrationType = Field(..., description="Type of provider")
    name: str = Field(..., description="Human-readable provider name")
    version: str = Field(..., description="Provider version")
    description: Optional[str] = Field(None, description="Provider description")
    enabled: bool = Field(..., description="Whether the provider is enabled")
    available: Optional[bool] = Field(None, description="Whether the provider is currently available")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Provider configuration (sanitized)")
    capabilities: Optional[ProviderCapabilities] = Field(None, description="Provider capabilities")


class IntegrationConfig(BaseModel):
    """Schema for integration configuration."""
    provider_type: IntegrationType = Field(..., description="Type of integration provider")
    enabled: bool = Field(default=True, description="Whether this provider is enabled")
    priority: int = Field(default=10, description="Provider priority for fallback (lower = higher priority)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")
    capabilities: Optional[ProviderCapabilities] = Field(None, description="Provider capabilities")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        """Validate priority is within valid range."""
        if v < 1 or v > 100:
            raise ValueError("Priority must be between 1 and 100")
        return v


class FactoryConfig(BaseModel):
    """Schema for integration factory configuration."""
    default_provider: IntegrationType = Field(..., description="Default provider type")
    providers: List[IntegrationConfig] = Field(..., description="List of provider configurations")
    fallback_enabled: bool = Field(default=True, description="Whether fallback is enabled")
    auto_failover: bool = Field(default=False, description="Whether to automatically failover on errors")
    health_check_interval: int = Field(default=60, description="Health check interval in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed executions")
    circuit_breaker_enabled: bool = Field(default=True, description="Whether circuit breaker is enabled")
    circuit_breaker_threshold: int = Field(default=5, description="Circuit breaker failure threshold")
    circuit_breaker_timeout: int = Field(default=300, description="Circuit breaker timeout in seconds")

    @field_validator('providers')
    @classmethod
    def validate_providers(cls, v):
        """Validate providers list contains the default provider."""
        if not v:
            raise ValueError("At least one provider must be configured")
        return v


class HealthCheckResponse(BaseModel):
    """Schema for provider health check responses."""
    provider_type: IntegrationType = Field(..., description="Provider type")
    healthy: bool = Field(..., description="Whether the provider is healthy")
    response_time_ms: Optional[int] = Field(None, description="Health check response time")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health check details")


class FactoryStatusResponse(BaseModel):
    """Schema for factory status response."""
    default_provider: IntegrationType = Field(..., description="Current default provider")
    total_providers: int = Field(..., description="Total configured providers")
    enabled_providers: int = Field(..., description="Number of enabled providers")
    available_providers: int = Field(..., description="Number of available providers")
    fallback_enabled: bool = Field(..., description="Whether fallback is enabled")
    auto_failover: bool = Field(..., description="Whether auto failover is enabled")
    provider_health: List[HealthCheckResponse] = Field(..., description="Health status of all providers")
    last_health_check: datetime = Field(..., description="Last factory-wide health check")


class ExecutionMetrics(BaseModel):
    """Schema for execution metrics."""
    provider_type: IntegrationType = Field(..., description="Provider type")
    workflow_type: WorkflowType = Field(..., description="Workflow type")
    total_executions: int = Field(..., description="Total number of executions")
    successful_executions: int = Field(..., description="Number of successful executions")
    failed_executions: int = Field(..., description="Number of failed executions")
    average_execution_time_ms: float = Field(..., description="Average execution time in milliseconds")
    last_execution: Optional[datetime] = Field(None, description="Last execution timestamp")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")
    error_rate: float = Field(..., description="Error rate (0.0 to 1.0)")

    @field_validator('success_rate', 'error_rate')
    @classmethod
    def validate_rates(cls, v):
        """Validate rates are within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Rate must be between 0.0 and 1.0")
        return v


class FactoryMetrics(BaseModel):
    """Schema for factory-wide metrics."""
    total_executions: int = Field(..., description="Total executions across all providers")
    total_successes: int = Field(..., description="Total successful executions")
    total_failures: int = Field(..., description="Total failed executions")
    overall_success_rate: float = Field(..., description="Overall success rate")
    provider_metrics: List[ExecutionMetrics] = Field(..., description="Metrics per provider")
    most_used_provider: IntegrationType = Field(..., description="Most frequently used provider")
    average_execution_time_ms: float = Field(..., description="Average execution time across all providers")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last metrics update")