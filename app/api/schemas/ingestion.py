"""
API schemas for ingestion system with comprehensive validation and serialization.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# Base schemas
class IngestionBase(BaseModel):
    """Base ingestion schema with common fields."""
    original_filename: str = Field(..., min_length=1, max_length=500, description="Original filename")
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    file_hash_sha256: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash")
    status: str = Field(..., description="Ingestion status")
    storage_path: str = Field(..., description="Storage file path")
    storage_backend: str = Field(..., description="Storage backend type")


class DuplicateAnalysis(BaseModel):
    """Duplicate detection analysis results."""
    strategies_applied: List[str] = Field(default_factory=list, description="Deduplication strategies applied")
    duplicates_found: List[Dict[str, Any]] = Field(default_factory=list, description="Found duplicates")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence scores by strategy")


class SecurityFeatures(BaseModel):
    """Security features of signed URLs."""
    token_length: int = Field(..., description="Length of security token")
    url_expires: bool = Field(..., description="Whether URL expires")
    access_limited: bool = Field(..., description="Whether access is limited")
    ip_restricted: bool = Field(..., description="Whether IP restrictions apply")


# Request schemas
class IngestionUploadRequest(BaseModel):
    """Request schema for file ingestion."""
    vendor_id: Optional[str] = Field(None, description="Optional vendor ID")
    source_type: str = Field("upload", description="Source type (upload, email, api)")
    source_reference: Optional[str] = Field(None, description="Source reference ID")
    uploaded_by: Optional[str] = Field(None, description="User who uploaded the file")
    processing_priority: int = Field(5, ge=1, le=10, description="Processing priority (1-10)")

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v):
        allowed_types = ['upload', 'email', 'api', 'batch']
        if v not in allowed_types:
            raise ValueError(f"Source type must be one of: {', '.join(allowed_types)}")
        return v


class SignedUrlCreateRequest(BaseModel):
    """Request schema for creating signed URLs."""
    expiry_hours: int = Field(24, ge=1, le=168, description="URL expiry in hours")
    max_access_count: int = Field(1, ge=1, le=100, description="Maximum access count")
    allowed_ip_addresses: Optional[List[str]] = Field(None, description="Allowed IP addresses")
    created_for: Optional[str] = Field(None, description="Purpose or user identifier")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")


class DuplicateResolutionRequest(BaseModel):
    """Request schema for resolving duplicates."""
    resolution: str = Field(..., description="Resolution action")
    resolved_by: str = Field(..., description="User or system resolving the duplicate")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")

    @field_validator('resolution')
    @classmethod
    def validate_resolution(cls, v):
        allowed_resolutions = ['auto_ignore', 'auto_merge', 'manual_review', 'replace_existing', 'archive_existing']
        if v not in allowed_resolutions:
            raise ValueError(f"Resolution must be one of: {', '.join(allowed_resolutions)}")
        return v


class BatchSignedUrlRequest(BaseModel):
    """Request schema for batch signed URL generation."""
    job_ids: List[str] = Field(..., min_items=1, max_items=100, description="Ingestion job IDs")
    expiry_hours: int = Field(24, ge=1, le=168, description="URL expiry in hours")
    max_access_count: int = Field(1, ge=1, le=100, description="Maximum access count")
    created_for: Optional[str] = Field(None, description="Purpose or user identifier")

    @field_validator('job_ids')
    @classmethod
    def validate_job_ids(cls, v):
        if len(v) > 100:
            raise ValueError("Cannot process more than 100 job IDs at once")
        return v


# Response schemas
class IngestionResponse(IngestionBase):
    """Response schema for ingestion job."""
    id: str = Field(..., description="Ingestion job ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    source_type: str = Field(..., description="Source type")
    source_reference: Optional[str] = Field(None, description="Source reference")
    uploaded_by: Optional[str] = Field(None, description="Upload user")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    processing_duration_ms: Optional[int] = Field(None, description="Processing duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code")
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(3, description="Maximum retry attempts")
    extracted_metadata: Optional[Dict[str, Any]] = Field(None, description="Extracted file metadata")
    is_duplicate: bool = Field(False, description="Whether file is a duplicate")
    duplicate_group_id: Optional[str] = Field(None, description="Duplicate group ID")
    duplicate_analysis: Optional[DuplicateAnalysis] = Field(None, description="Duplicate analysis results")
    duplicates: Optional[List[Dict[str, Any]]] = Field(None, description="Duplicate records")
    signed_urls: Optional[List[Dict[str, Any]]] = Field(None, description="Signed URLs")
    estimated_processing_time_seconds: int = Field(0, description="Estimated processing time")

    model_config = ConfigDict(from_attributes=True)


class IngestionListResponse(BaseModel):
    """Response schema for listing ingestion jobs."""
    jobs: List[IngestionResponse] = Field(..., description="List of ingestion jobs")
    total: int = Field(..., description="Total number of jobs")
    skip: int = Field(..., description="Number of jobs skipped")
    limit: int = Field(..., description="Maximum number of jobs returned")


class DuplicateRecordResponse(BaseModel):
    """Response schema for duplicate records."""
    id: str = Field(..., description="Duplicate record ID")
    ingestion_job_id: str = Field(..., description="Associated ingestion job ID")
    strategy: str = Field(..., description="Detection strategy used")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity score")
    match_criteria: Dict[str, Any] = Field(..., description="Match criteria details")
    comparison_details: Optional[Dict[str, Any]] = Field(None, description="Field-by-field comparison")
    resolution_action: Optional[str] = Field(None, description="Resolution action taken")
    resolved_by: Optional[str] = Field(None, description="Who resolved the duplicate")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")
    requires_human_review: bool = Field(..., description="Whether human review is required")
    status: str = Field(..., description="Duplicate status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class DuplicateGroupResponse(BaseModel):
    """Response schema for duplicate groups."""
    group_id: str = Field(..., description="Duplicate group ID")
    duplicate_count: int = Field(..., description="Number of duplicates in group")
    total_confidence: float = Field(..., description="Total confidence score")
    strategies_used: List[str] = Field(..., description="Strategies that found duplicates")
    duplicates: List[Dict[str, Any]] = Field(..., description="Duplicate records in group")


class SignedUrlResponse(BaseModel):
    """Response schema for signed URLs."""
    id: str = Field(..., description="Signed URL ID")
    url: str = Field(..., description="Signed URL")
    token: str = Field(..., description="URL token")
    expires_at: str = Field(..., description="Expiration timestamp")
    expiry_hours: int = Field(..., description="Expiry in hours")
    max_access_count: int = Field(..., description="Maximum access count")
    allowed_ip_addresses: Optional[List[str]] = Field(None, description="Allowed IP addresses")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    security_features: SecurityFeatures = Field(..., description="Security features")

    model_config = ConfigDict(from_attributes=True)


class BatchSignedUrlResponse(BaseModel):
    """Response schema for batch signed URL generation."""
    total_requested: int = Field(..., description="Total URLs requested")
    successful: int = Field(..., description="Successfully generated URLs")
    failed: int = Field(..., description="Failed URL generations")
    signed_urls: List[SignedUrlResponse] = Field(..., description="Generated signed URLs")
    failed_jobs: List[Dict[str, Any]] = Field(..., description="Failed job details")
    generated_at: str = Field(..., description="Generation timestamp")


class IngestionMetricsResponse(BaseModel):
    """Response schema for ingestion metrics."""
    period: Dict[str, str] = Field(..., description="Metrics period")
    total_jobs: int = Field(..., description="Total ingestion jobs")
    status_breakdown: Dict[str, int] = Field(..., description="Jobs by status")
    duplicate_breakdown: Dict[str, int] = Field(..., description="Duplicates by strategy")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    file_size_metrics: Dict[str, Any] = Field(..., description="File size metrics")
    generated_at: str = Field(..., description="Metrics generation timestamp")


class UrlAccessMetricsResponse(BaseModel):
    """Response schema for URL access metrics."""
    period: Dict[str, str] = Field(..., description="Metrics period")
    total_urls: int = Field(..., description="Total signed URLs")
    accessed_urls: int = Field(..., description="Accessed URLs")
    expired_urls: int = Field(..., description="Expired URLs")
    revoked_urls: int = Field(..., description="Revoked URLs")
    total_accesses: int = Field(..., description="Total accesses")
    avg_accesses_per_url: float = Field(..., description="Average accesses per URL")
    access_rate: float = Field(..., description="Access rate percentage")
    by_purpose: Dict[str, Dict[str, int]] = Field(..., description="Metrics by purpose")
    generated_at: str = Field(..., description="Metrics generation timestamp")


class DeduplicationRuleBase(BaseModel):
    """Base deduplication rule schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    strategy: str = Field(..., description="Deduplication strategy")
    configuration: Dict[str, Any] = Field(..., description="Rule configuration")
    is_active: bool = Field(True, description="Whether rule is active")
    priority: int = Field(5, ge=1, le=10, description="Rule priority")

    @field_validator('strategy')
    @classmethod
    def validate_strategy(cls, v):
        allowed_strategies = ['file_hash', 'business_rules', 'temporal', 'fuzzy_matching', 'composite']
        if v not in allowed_strategies:
            raise ValueError(f"Strategy must be one of: {', '.join(allowed_strategies)}")
        return v


class DeduplicationRuleCreate(DeduplicationRuleBase):
    """Schema for creating deduplication rules."""
    pass


class DeduplicationRuleUpdate(BaseModel):
    """Schema for updating deduplication rules."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    strategy: Optional[str] = Field(None, description="Deduplication strategy")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Rule configuration")
    is_active: Optional[bool] = Field(None, description="Whether rule is active")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Rule priority")

    @field_validator('strategy')
    @classmethod
    def validate_strategy(cls, v):
        if v is not None:
            allowed_strategies = ['file_hash', 'business_rules', 'temporal', 'fuzzy_matching', 'composite']
            if v not in allowed_strategies:
                raise ValueError(f"Strategy must be one of: {', '.join(allowed_strategies)}")
        return v


class DeduplicationRuleResponse(DeduplicationRuleBase):
    """Response schema for deduplication rules."""
    id: str = Field(..., description="Rule ID")
    match_count: int = Field(0, description="Number of matches")
    false_positive_count: int = Field(0, description="Number of false positives")
    last_matched_at: Optional[datetime] = Field(None, description="Last match timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class CleanupStatsResponse(BaseModel):
    """Response schema for cleanup statistics."""
    total_expired: int = Field(..., description="Total expired URLs")
    already_inactive: int = Field(..., description="Already inactive URLs")
    to_deactivate: int = Field(..., description="URLs to deactivate")
    cutoff_time: str = Field(..., description="Cleanup cutoff time")
    dry_run: bool = Field(..., description="Whether this was a dry run")


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")


class SuccessResponse(BaseModel):
    """Standard success response schema."""
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")