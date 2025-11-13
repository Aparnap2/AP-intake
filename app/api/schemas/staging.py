"""
Pydantic schemas for staging API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator

from app.models.staging import StagingStatus, ExportFormat


class StagedExportBase(BaseModel):
    """Base schema for staged export data."""

    invoice_id: str = Field(..., description="Invoice ID")
    export_format: ExportFormat = Field(..., description="Export format")
    destination_system: str = Field(..., description="Destination system")
    priority: int = Field(5, ge=1, le=10, description="Priority level (1-10)")
    business_unit: Optional[str] = Field(None, description="Business unit")
    cost_center: Optional[str] = Field(None, description="Cost center")
    compliance_flags: Optional[List[str]] = Field(None, description="Compliance flags")


class StagingApprovalRequest(BaseModel):
    """Request schema for approving staged export."""

    approved_by: str = Field(..., description="User ID approving the export")
    approved_data: Optional[Dict[str, Any]] = Field(None, description="Modified export data")
    change_reason: Optional[str] = Field(None, description="Business reason for changes")
    approval_comments: Optional[str] = Field(None, description="Approval comments")


class StagingRejectionRequest(BaseModel):
    """Request schema for rejecting staged export."""

    rejected_by: str = Field(..., description="User ID rejecting the export")
    rejection_reason: str = Field(..., description="Reason for rejection")


class StagingPostRequest(BaseModel):
    """Request schema for posting staged export."""

    posted_by: str = Field(..., description="User ID posting the export")
    external_reference: Optional[str] = Field(None, description="Reference in destination system")
    export_filename: Optional[str] = Field(None, description="Generated export filename")
    export_file_size: Optional[int] = Field(None, description="Export file size")


class StagingRollbackRequest(BaseModel):
    """Request schema for rolling back staged export."""

    rolled_back_by: str = Field(..., description="User ID performing the rollback")
    rollback_reason: str = Field(..., description="Reason for rollback")


class StagedExportResponse(BaseModel):
    """Response schema for staged export operations."""

    id: str = Field(..., description="Staged export ID")
    invoice_id: str = Field(..., description="Invoice ID")
    export_format: str = Field(..., description="Export format")
    destination_system: str = Field(..., description="Destination system")
    staging_status: str = Field(..., description="Current staging status")
    prepared_at: datetime = Field(..., description="Preparation timestamp")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    posted_at: Optional[datetime] = Field(None, description="Posting timestamp")
    rejected_at: Optional[datetime] = Field(None, description="Rejection timestamp")
    prepared_by: Optional[str] = Field(None, description="User who prepared the export")
    approved_by: Optional[str] = Field(None, description="User who approved the export")
    posted_by: Optional[str] = Field(None, description="User who posted the export")
    rejected_by: Optional[str] = Field(None, description="User who rejected the export")
    quality_score: Optional[int] = Field(None, description="Quality score (0-100)")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors")
    field_changes: Optional[Dict[str, Any]] = Field(None, description="Field-level changes")
    change_reason: Optional[str] = Field(None, description="Business reason for changes")
    reviewer_comments: Optional[str] = Field(None, description="Reviewer comments")
    external_reference: Optional[str] = Field(None, description="Reference in destination system")
    export_job_id: Optional[str] = Field(None, description="Export job ID")
    export_filename: Optional[str] = Field(None, description="Export filename")
    export_file_size: Optional[int] = Field(None, description="Export file size")
    batch_id: Optional[str] = Field(None, description="Batch ID")
    priority: int = Field(..., description="Priority level")
    business_unit: Optional[str] = Field(None, description="Business unit")
    cost_center: Optional[str] = Field(None, description="Cost center")
    compliance_flags: Optional[List[str]] = Field(None, description="Compliance flags")
    audit_notes: Optional[str] = Field(None, description="Audit notes")
    audit_trail: Optional[List[Dict[str, Any]]] = Field(None, description="Audit trail entries")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StagedExportListResponse(BaseModel):
    """Response schema for staged export list."""

    staged_exports: List[StagedExportResponse] = Field(..., description="List of staged exports")
    total: int = Field(..., description="Total number of records")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum number of records returned")


class FieldChangeDetail(BaseModel):
    """Schema for field change details."""

    field_name: str = Field(..., description="Field name")
    original_value: Any = Field(..., description="Original value")
    modified_value: Any = Field(..., description="Modified value")
    change_type: str = Field(..., description="Type of change (added, removed, modified)")


class DiffSummary(BaseModel):
    """Schema for diff summary."""

    total_fields_in_data1: int = Field(..., description="Total fields in first data set")
    total_fields_in_data2: int = Field(..., description="Total fields in second data set")
    fields_added: int = Field(..., description="Number of fields added")
    fields_removed: int = Field(..., description="Number of fields removed")
    fields_modified: int = Field(..., description="Number of fields modified")


class ComprehensiveDiff(BaseModel):
    """Schema for comprehensive diff between data sets."""

    added_fields: Dict[str, Any] = Field(..., description="Fields added")
    removed_fields: Dict[str, Any] = Field(..., description="Fields removed")
    modified_fields: Dict[str, FieldChangeDetail] = Field(..., description="Fields modified")
    summary: DiffSummary = Field(..., description="Diff summary")


class StagedExportDiffResponse(BaseModel):
    """Response schema for staged export diff."""

    staged_export_id: str = Field(..., description="Staged export ID")
    invoice_id: str = Field(..., description="Invoice ID")
    destination_system: str = Field(..., description="Destination system")
    export_format: str = Field(..., description="Export format")
    original_to_prepared: ComprehensiveDiff = Field(..., description="Diff from original to prepared")
    prepared_to_approved: Optional[ComprehensiveDiff] = Field(None, description="Diff from prepared to approved")
    field_changes: Optional[Dict[str, Any]] = Field(None, description="Field-level changes")
    change_reason: Optional[str] = Field(None, description="Business reason for changes")
    quality_score: Optional[int] = Field(None, description="Quality score")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors")
    audit_trail_count: int = Field(..., description="Number of audit trail entries")


class StagingBatchCreate(BaseModel):
    """Schema for creating staging batch."""

    batch_name: str = Field(..., description="Batch name")
    batch_description: Optional[str] = Field(None, description="Batch description")
    batch_type: str = Field(..., description="Batch type (daily, weekly, monthly, ad_hoc)")
    created_by: str = Field(..., description="User creating the batch")


class StagingBatchResponse(BaseModel):
    """Response schema for staging batch."""

    id: str = Field(..., description="Batch ID")
    batch_name: str = Field(..., description="Batch name")
    batch_description: Optional[str] = Field(None, description="Batch description")
    batch_type: str = Field(..., description="Batch type")
    batch_status: str = Field(..., description="Batch status")
    total_exports: int = Field(..., description="Total exports in batch")
    prepared_exports: int = Field(..., description="Prepared exports")
    approved_exports: int = Field(..., description="Approved exports")
    posted_exports: int = Field(..., description="Posted exports")
    failed_exports: int = Field(..., description="Failed exports")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    estimated_completion_at: Optional[datetime] = Field(None, description="Estimated completion time")
    avg_quality_score: Optional[int] = Field(None, description="Average quality score")
    total_validation_errors: int = Field(..., description="Total validation errors")
    total_validation_warnings: int = Field(..., description="Total validation warnings")
    created_by: Optional[str] = Field(None, description="User who created the batch")
    approved_by: Optional[str] = Field(None, description="User who approved the batch")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StagingMetricsResponse(BaseModel):
    """Response schema for staging metrics."""

    period: Dict[str, str] = Field(..., description="Time period for metrics")
    total_staged: int = Field(..., description="Total exports staged")
    total_approved: int = Field(..., description="Total exports approved")
    total_posted: int = Field(..., description="Total exports posted")
    total_rejected: int = Field(..., description="Total exports rejected")
    avg_quality_score: Optional[float] = Field(None, description="Average quality score")
    avg_processing_time_hours: Optional[float] = Field(None, description="Average processing time")
    status_breakdown: Dict[str, int] = Field(..., description="Breakdown by status")
    destination_breakdown: Dict[str, int] = Field(..., description="Breakdown by destination system")
    business_unit_breakdown: Dict[str, int] = Field(..., description="Breakdown by business unit")
    compliance_flags_summary: Dict[str, int] = Field(..., description="Summary of compliance flags")
    generated_at: str = Field(..., description="Generation timestamp")


class AuditTrailEntry(BaseModel):
    """Schema for audit trail entry."""

    id: str = Field(..., description="Audit entry ID")
    action: str = Field(..., description="Action performed")
    action_by: str = Field(..., description="User who performed the action")
    created_at: datetime = Field(..., description="Timestamp of action")
    action_reason: Optional[str] = Field(None, description="Reason for action")
    business_event: Optional[str] = Field(None, description="Business event type")
    impact_assessment: Optional[str] = Field(None, description="Impact assessment (low, medium, high)")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }