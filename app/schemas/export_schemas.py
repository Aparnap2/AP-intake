"""
Export-related Pydantic schemas for request/response validation.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ExportFormat(str, Enum):
    """Export format options."""
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    EXCEL = "excel"
    PDF = "pdf"


class ExportStatus(str, Enum):
    """Export processing status."""
    PENDING = "pending"
    PREPARING = "preparing"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportDestination(str, Enum):
    """Export destination options."""
    DOWNLOAD = "download"
    FILE_STORAGE = "file_storage"
    API_ENDPOINT = "api_endpoint"
    EMAIL = "email"
    FTP = "ftp"


class FieldType(str, Enum):
    """Field type for mapping and validation."""
    STRING = "string"
    NUMBER = "number"
    DECIMAL = "decimal"
    DATE = "date"
    BOOLEAN = "boolean"
    JSON = "json"


class ExportFieldMapping(BaseModel):
    """Field mapping configuration for exports."""
    source_field: str = Field(..., description="Source field name from invoice data")
    target_field: str = Field(..., description="Target field name in export")
    field_type: FieldType = Field(..., description="Data type of the field")
    required: bool = Field(True, description="Whether this field is required")
    default_value: Optional[Any] = Field(None, description="Default value if source is empty")
    format_string: Optional[str] = Field(None, description="Format string for date/number formatting")
    transform_function: Optional[str] = Field(None, description="Transform function name")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class ExportTemplate(BaseModel):
    """Export template configuration."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    format: ExportFormat = Field(..., description="Export format")
    field_mappings: List[ExportFieldMapping] = Field(..., description="Field mappings")
    header_config: Optional[Dict[str, Any]] = Field(None, description="Header configuration")
    footer_config: Optional[Dict[str, Any]] = Field(None, description="Footer configuration")
    compression: bool = Field(False, description="Whether to compress the export")
    encryption: bool = Field(False, description="Whether to encrypt the export")
    is_active: bool = Field(True, description="Whether template is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExportConfig(BaseModel):
    """Export configuration for a specific export job."""
    template_id: uuid.UUID = Field(..., description="Export template ID")
    destination: ExportDestination = Field(..., description="Export destination")
    destination_config: Dict[str, Any] = Field(..., description="Destination-specific configuration")
    filters: Optional[Dict[str, Any]] = Field(None, description="Export filters")
    batch_size: int = Field(1000, description="Batch size for processing")
    notify_on_completion: bool = Field(False, description="Send notification on completion")
    notification_config: Optional[Dict[str, Any]] = Field(None, description="Notification configuration")


class ExportValidationRule(BaseModel):
    """Validation rule for export data."""
    field_path: str = Field(..., description="JSON path to field")
    rule_type: str = Field(..., description="Type of validation rule")
    rule_config: Dict[str, Any] = Field(..., description="Rule configuration")
    error_message: str = Field(..., description="Error message if validation fails")
    severity: str = Field("error", description="Severity level: error, warning, info")


class ExportRequest(BaseModel):
    """Export request schema."""
    invoice_ids: Optional[List[uuid.UUID]] = Field(None, description="Specific invoice IDs to export")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters for invoice selection")
    export_config: ExportConfig = Field(..., description="Export configuration")
    priority: int = Field(5, description="Export priority (1-10)")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule export for later")


class ExportResponse(BaseModel):
    """Export response schema."""
    export_id: uuid.UUID = Field(..., description="Export job ID")
    status: ExportStatus = Field(..., description="Export status")
    message: str = Field(..., description="Status message")
    estimated_records: Optional[int] = Field(None, description="Estimated number of records")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    download_url: Optional[str] = Field(None, description="Download URL if available")


class ExportProgress(BaseModel):
    """Export progress information."""
    export_id: uuid.UUID = Field(..., description="Export job ID")
    status: ExportStatus = Field(..., description="Current status")
    total_records: int = Field(..., description="Total records to process")
    processed_records: int = Field(0, description="Records processed so far")
    failed_records: int = Field(0, description="Records that failed")
    progress_percentage: float = Field(0.0, description="Progress percentage")
    current_stage: str = Field(..., description="Current processing stage")
    error_message: Optional[str] = Field(None, description="Current error message")
    started_at: Optional[datetime] = Field(None, description="Export start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion")


class ExportAuditLog(BaseModel):
    """Export audit log entry."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    export_id: uuid.UUID = Field(..., description="Export job ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str = Field(..., description="Event type")
    event_data: Dict[str, Any] = Field(..., description="Event data")
    user_id: Optional[str] = Field(None, description="User who initiated the action")
    ip_address: Optional[str] = Field(None, description="IP address of the request")
    user_agent: Optional[str] = Field(None, description="User agent string")


class ExportMetrics(BaseModel):
    """Export metrics and statistics."""
    export_id: uuid.UUID = Field(..., description="Export job ID")
    total_records: int = Field(..., description="Total records processed")
    successful_records: int = Field(..., description="Successfully processed records")
    failed_records: int = Field(..., description="Failed records")
    processing_time_seconds: float = Field(..., description="Total processing time")
    file_size_bytes: int = Field(..., description="Generated file size")
    format: ExportFormat = Field(..., description="Export format")
    destination: ExportDestination = Field(..., description="Export destination")
    created_at: datetime = Field(..., description="Export creation time")
    completed_at: Optional[datetime] = Field(None, description="Export completion time")


class BatchExportRequest(BaseModel):
    """Batch export request schema."""
    export_requests: List[ExportRequest] = Field(..., description="List of export requests")
    global_config: Optional[Dict[str, Any]] = Field(None, description="Global configuration overrides")
    priority: int = Field(5, description="Overall batch priority")
    max_parallel_jobs: int = Field(3, description="Maximum parallel export jobs")


class BatchExportResponse(BaseModel):
    """Batch export response schema."""
    batch_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    export_responses: List[ExportResponse] = Field(..., description="Individual export responses")
    total_exports: int = Field(..., description="Total number of exports")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated batch completion")


# Request/Response schemas for API endpoints
class ExportTemplateCreate(BaseModel):
    """Schema for creating export templates."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    format: ExportFormat
    field_mappings: List[ExportFieldMapping]
    header_config: Optional[Dict[str, Any]] = None
    footer_config: Optional[Dict[str, Any]] = None
    compression: bool = False
    encryption: bool = False


class ExportTemplateUpdate(BaseModel):
    """Schema for updating export templates."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    field_mappings: Optional[List[ExportFieldMapping]] = None
    header_config: Optional[Dict[str, Any]] = None
    footer_config: Optional[Dict[str, Any]] = None
    compression: Optional[bool] = None
    encryption: Optional[bool] = None
    is_active: Optional[bool] = None


class ExportFilter(BaseModel):
    """Schema for export filters."""
    vendor_ids: Optional[List[uuid.UUID]] = None
    status: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    total_min: Optional[float] = None
    total_max: Optional[float] = None
    currency: Optional[str] = None
    has_exceptions: Optional[bool] = None
    custom_filters: Optional[Dict[str, Any]] = None


class ExportDestinationConfig(BaseModel):
    """Schema for export destination configuration."""
    destination: ExportDestination
    config: Dict[str, Any] = Field(..., description="Destination-specific configuration")

    @field_validator('config')
    @classmethod
    def validate_destination_config(cls, v, info):
        """Validate destination-specific configuration."""
        destination = info.data.get('destination')
        if destination == ExportDestination.FILE_STORAGE:
            required_fields = ['path', 'filename_pattern']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Missing required field '{field}' for file storage destination")
        elif destination == ExportDestination.API_ENDPOINT:
            required_fields = ['url', 'auth_method']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Missing required field '{field}' for API endpoint destination")
        elif destination == ExportDestination.EMAIL:
            required_fields = ['recipients', 'subject']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Missing required field '{field}' for email destination")
        return v


class ExportJob(BaseModel):
    """Export job model for API responses."""
    id: uuid.UUID = Field(..., description="Export job ID")
    name: str = Field(..., description="Export job name")
    description: Optional[str] = Field(None, description="Export job description")
    template_id: uuid.UUID = Field(..., description="Export template ID")
    format: ExportFormat = Field(..., description="Export format")
    destination: ExportDestination = Field(..., description="Export destination")
    destination_config: Dict[str, Any] = Field(..., description="Destination configuration")
    filters: Optional[Dict[str, Any]] = Field(None, description="Export filters")
    invoice_ids: Optional[List[uuid.UUID]] = Field(None, description="Specific invoice IDs")
    status: ExportStatus = Field(..., description="Export job status")
    total_records: Optional[int] = Field(None, description="Total records to process")
    processed_records: int = Field(0, description="Records processed so far")
    failed_records: int = Field(0, description="Records that failed")
    file_path: Optional[str] = Field(None, description="Generated file path")
    file_size: Optional[int] = Field(None, description="Generated file size in bytes")
    error_message: Optional[str] = Field(None, description="Current error message")
    started_at: Optional[datetime] = Field(None, description="Export start time")
    completed_at: Optional[datetime] = Field(None, description="Export completion time")
    created_at: datetime = Field(..., description="Export creation time")
    updated_at: datetime = Field(..., description="Export last update time")

    model_config = ConfigDict(from_attributes=True)