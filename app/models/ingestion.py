"""
Ingestion-related database models for robust file handling and deduplication.
"""

import enum
import hashlib
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Integer,
    Float,
    ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class IngestionStatus(str, enum.Enum):
    """Ingestion processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE_DETECTED = "duplicate_detected"
    REQUIRE_REVIEW = "require_review"


class DeduplicationStrategy(str, enum.Enum):
    """Deduplication strategy types."""

    FILE_HASH = "file_hash"  # SHA-256 content hashing
    BUSINESS_RULES = "business_rules"  # vendor_id + amount + date
    TEMPORAL = "temporal"  # time window detection
    FUZZY_MATCHING = "fuzzy_matching"  # content similarity
    COMPOSITE = "composite"  # multiple strategies combined


class DuplicateResolution(str, enum.Enum):
    """Duplicate resolution actions."""

    AUTO_IGNORE = "auto_ignore"  # Automatically ignore duplicate
    AUTO_MERGE = "auto_merge"  # Automatically merge data
    MANUAL_REVIEW = "manual_review"  # Require human review
    REPLACE_EXISTING = "replace_existing"  # Replace existing record
    ARCHIVE_EXISTING = "archive_existing"  # Archive existing record


class IngestionJob(Base, UUIDMixin, TimestampMixin):
    """Main ingestion job record with comprehensive tracking."""

    __tablename__ = "ingestion_jobs"

    # File information
    original_filename = Column(String(500), nullable=False, index=True)
    file_extension = Column(String(10), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False, unique=True, index=True)
    mime_type = Column(String(100), nullable=True)

    # Storage information
    storage_path = Column(Text, nullable=False)
    storage_backend = Column(String(50), nullable=False, default="local")
    signed_url = Column(Text, nullable=True)  # Temporary access URL
    signed_url_expiry = Column(DateTime(timezone=True), nullable=True)

    # Processing status
    status = Column(
        Enum(IngestionStatus),
        default=IngestionStatus.PENDING,
        nullable=False,
        index=True
    )

    # Metadata extracted during ingestion
    extracted_metadata = Column(JSONB, nullable=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True, index=True)
    processing_priority = Column(Integer, nullable=False, default=5)  # 1-10 priority

    # Deduplication information
    deduplication_strategy = Column(
        Enum(DeduplicationStrategy),
        default=DeduplicationStrategy.COMPOSITE,
        nullable=False
    )
    duplicate_group_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    is_duplicate = Column(Boolean, nullable=False, default=False, index=True)

    # Processing metrics
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_duration_ms = Column(Integer, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Source information
    source_type = Column(String(50), nullable=False, default="upload")  # upload, email, api
    source_reference = Column(String(500), nullable=True)  # Email ID, API request ID, etc.
    uploaded_by = Column(String(255), nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_ingestion_status_priority', 'status', 'processing_priority'),
        Index('idx_ingestion_created_status', 'created_at', 'status'),
        Index('idx_ingestion_vendor_status', 'vendor_id', 'status'),
        Index('idx_ingestion_file_hash', 'file_hash_sha256'),
        Index('idx_ingestion_duplicate_group', 'duplicate_group_id'),
        Index('idx_ingestion_processing_window', 'processing_started_at', 'status'),
        Index('idx_ingestion_error_code', 'error_code', 'created_at'),
        # Unique constraints for data integrity
        UniqueConstraint('file_hash_sha256', name='uq_ingestion_file_hash'),
        # Check constraints
        CheckConstraint("original_filename <> ''", name='check_original_filename_not_empty'),
        CheckConstraint("file_extension <> ''", name='check_file_extension_not_empty'),
        CheckConstraint("file_size_bytes > 0", name='check_file_size_positive'),
        CheckConstraint("processing_priority >= 1 AND processing_priority <= 10",
                       name='check_processing_priority_range'),
        CheckConstraint("retry_count >= 0", name='check_retry_count_non_negative'),
        CheckConstraint("max_retries >= 0", name='check_max_retries_non_negative'),
    )

    # Relationships
    vendor = relationship("Vendor", back_populates="ingestion_jobs")
    duplicate_records = relationship("DuplicateRecord", back_populates="ingestion_job")
    signed_urls = relationship("SignedUrl", back_populates="ingestion_job")

    def __repr__(self):
        return f"<IngestionJob(id={self.id}, filename={self.original_filename}, status={self.status})>"


class DuplicateRecord(Base, UUIDMixin, TimestampMixin):
    """Duplicate detection and resolution records."""

    __tablename__ = "duplicate_records"

    # Link to ingestion job
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False)
    original_invoice_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to existing invoice

    # Duplicate detection information
    detection_strategy = Column(Enum(DeduplicationStrategy), nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0.0-1.0 confidence that it's a duplicate
    similarity_score = Column(Float, nullable=True)   # For fuzzy matching

    # Matching criteria details
    match_criteria = Column(JSONB, nullable=False)  # Details of what matched
    comparison_details = Column(JSONB, nullable=True)  # Field-by-field comparison

    # Resolution information
    resolution_action = Column(Enum(DuplicateResolution), nullable=True)
    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(50), nullable=False, default="detected", index=True)
    requires_human_review = Column(Boolean, nullable=False, default=False, index=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_duplicate_ingestion_strategy', 'ingestion_job_id', 'detection_strategy'),
        Index('idx_duplicate_confidence', 'confidence_score', 'status'),
        Index('idx_duplicate_resolution', 'resolution_action', 'resolved_at'),
        Index('idx_duplicate_review_required', 'requires_human_review', 'status'),
        Index('idx_duplicate_original_invoice', 'original_invoice_id'),
        # Check constraints
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0",
                       name='check_confidence_score_range'),
        CheckConstraint("similarity_score IS NULL OR (similarity_score >= 0.0 AND similarity_score <= 1.0)",
                       name='check_similarity_score_range'),
    )

    # Relationships
    ingestion_job = relationship("IngestionJob", back_populates="duplicate_records")

    def __repr__(self):
        return f"<DuplicateRecord(id={self.id}, job={self.ingestion_job_id}, strategy={self.detection_strategy})>"


class SignedUrl(Base, UUIDMixin, TimestampMixin):
    """Signed URL management for secure file access."""

    __tablename__ = "signed_urls"

    # Link to ingestion job
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False)

    # URL information
    url_token = Column(String(255), nullable=False, unique=True, index=True)
    signed_url = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Access control
    access_count = Column(Integer, nullable=False, default=0)
    max_access_count = Column(Integer, nullable=False, default=1)
    allowed_ip_addresses = Column(ARRAY(String), nullable=True)

    # Usage tracking
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    created_for = Column(String(255), nullable=True)  # User or purpose

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(255), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_signed_url_token', 'url_token', 'is_active'),
        Index('idx_signed_url_expires', 'expires_at', 'is_active'),
        Index('idx_signed_url_ingestion', 'ingestion_job_id', 'created_at'),
        # Check constraints
        CheckConstraint("signed_url <> ''", name='check_signed_url_not_empty'),
        CheckConstraint("url_token <> ''", name='check_url_token_not_empty'),
        CheckConstraint("access_count >= 0", name='check_access_count_non_negative'),
        CheckConstraint("max_access_count > 0", name='check_max_access_count_positive'),
    )

    # Relationships
    ingestion_job = relationship("IngestionJob", back_populates="signed_urls")

    def __repr__(self):
        return f"<SignedUrl(id={self.id}, token={self.url_token}, expires={self.expires_at})>"


class DeduplicationRule(Base, UUIDMixin, TimestampMixin):
    """Configurable deduplication rules and strategies."""

    __tablename__ = "deduplication_rules"

    # Rule definition
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    strategy = Column(Enum(DeduplicationStrategy), nullable=False)

    # Rule configuration (JSON schema for different strategies)
    configuration = Column(JSONB, nullable=False)

    # Rule status and priority
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, higher = more priority

    # Applicability constraints
    vendor_filter = Column(JSONB, nullable=True)  # Apply to specific vendors
    file_type_filter = Column(ARRAY(String), nullable=True)  # Apply to specific file types
    date_range_filter = Column(JSONB, nullable=True)  # Apply to specific date ranges

    # Performance tracking
    match_count = Column(Integer, nullable=False, default=0)
    false_positive_count = Column(Integer, nullable=False, default=0)
    last_matched_at = Column(DateTime(timezone=True), nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_dedup_rule_active_priority', 'is_active', 'priority'),
        Index('idx_dedup_rule_strategy', 'strategy', 'is_active'),
        Index('idx_dedup_rule_performance', 'match_count', 'last_matched_at'),
        # Check constraints
        CheckConstraint("name <> ''", name='check_rule_name_not_empty'),
        CheckConstraint("priority >= 1 AND priority <= 10", name='check_rule_priority_range'),
        CheckConstraint("match_count >= 0", name='check_match_count_non_negative'),
        CheckConstraint("false_positive_count >= 0", name='check_false_positive_count_non_negative'),
    )

    def __repr__(self):
        return f"<DeduplicationRule(id={self.id}, name={self.name}, strategy={self.strategy})>"


class IngestionMetrics(Base, UUIDMixin, TimestampMixin):
    """Daily metrics for ingestion system performance."""

    __tablename__ = "ingestion_metrics"

    # Metric date and scope
    metric_date = Column(DateTime(timezone=True), nullable=False, index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)

    # Ingestion counts
    total_ingestion_jobs = Column(Integer, nullable=False, default=0)
    completed_ingestions = Column(Integer, nullable=False, default=0)
    failed_ingestions = Column(Integer, nullable=False, default=0)
    duplicate_detected = Column(Integer, nullable=False, default=0)

    # Processing metrics
    avg_processing_time_ms = Column(Integer, nullable=True)
    total_file_size_mb = Column(Integer, nullable=False, default=0)

    # Duplicate breakdown by strategy
    duplicates_by_strategy = Column(JSONB, nullable=True)

    # Performance indexes
    __table_args__ = (
        Index('idx_metrics_date_vendor', 'metric_date', 'vendor_id'),
        Index('idx_metrics_date', 'metric_date'),
        # Check constraints
        CheckConstraint("total_ingestion_jobs >= 0", name='check_total_ingestion_jobs_non_negative'),
        CheckConstraint("completed_ingestions >= 0", name='check_completed_ingestions_non_negative'),
        CheckConstraint("failed_ingestions >= 0", name='check_failed_ingestions_non_negative'),
        CheckConstraint("duplicate_detected >= 0", name='check_duplicate_detected_non_negative'),
        CheckConstraint("avg_processing_time_ms >= 0", name='check_avg_processing_time_non_negative'),
    )

    # Relationships
    vendor = relationship("Vendor")

    def __repr__(self):
        return f"<IngestionMetrics(id={self.id}, date={self.metric_date}, total={self.total_ingestion_jobs})>"