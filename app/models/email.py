"""
Email ingestion and tracking models.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class EmailProvider(str, enum.Enum):
    """Email provider types."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class EmailStatus(str, enum.Enum):
    """Email processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    BLOCKED = "blocked"


class EmailSecurityFlag(str, enum.Enum):
    """Email security flag types."""
    MALICIOUS_PATTERN = "malicious_pattern"
    UNTRUSTED_SENDER = "untrusted_sender"
    EXCESSIVE_URLS = "excessive_urls"
    EXCESSIVE_ATTACHMENTS = "excessive_attachments"
    SUSPICIOUS_CONTENT = "suspicious_content"


class Email(Base):
    """Email tracking model."""
    __tablename__ = "emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    provider = Column(String(20), nullable=False, default=EmailProvider.GMAIL)
    provider_message_id = Column(String(255), nullable=False)
    thread_id = Column(String(255), nullable=True)

    # Email metadata
    subject = Column(Text, nullable=False)
    from_email = Column(String(255), nullable=False)
    to_emails = Column(JSON, nullable=False)  # List of email addresses
    cc_emails = Column(JSON, nullable=True)   # List of email addresses
    bcc_emails = Column(JSON, nullable=True)  # List of email addresses
    date_sent = Column(DateTime(timezone=True), nullable=False)

    # Email content
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)

    # Processing status
    status = Column(String(20), nullable=False, default=EmailStatus.PENDING)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Security
    security_flags = Column(JSON, nullable=True)  # List of security flags
    is_trusted_sender = Column(Boolean, default=False)
    security_score = Column(Integer, default=100)  # 0-100, higher is better

    # Metadata
    labels = Column(JSON, nullable=True)  # Gmail labels or similar
    email_metadata = Column(JSON, nullable=True)  # Additional provider-specific metadata

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    attachments = relationship("EmailAttachment", back_populates="email", cascade="all, delete-orphan")
    processing_logs = relationship("EmailProcessingLog", back_populates="email", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        {'schema': 'public'}
    )

    def __repr__(self):
        return f"<Email(id={self.id}, subject='{self.subject[:50]}...', status={self.status})>"


class EmailAttachment(Base):
    """Email attachment model."""
    __tablename__ = "email_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)

    # Attachment metadata
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash

    # Storage
    storage_type = Column(String(20), nullable=False, default="local")  # local, s3, etc.
    storage_path = Column(String(500), nullable=False)
    storage_metadata = Column(JSON, nullable=True)

    # Processing
    is_pdf = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Invoice extraction (if applicable)
    extraction_confidence = Column(Integer, nullable=True)  # 0-100
    vendor_name = Column(String(255), nullable=True)
    invoice_date = Column(DateTime(timezone=True), nullable=True)
    invoice_amount = Column(Integer, nullable=True)  # Store in cents

    # Security
    is_scanned = Column(Boolean, default=False)
    scan_result = Column(String(20), nullable=True)  # safe, malicious, suspicious
    scan_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    email = relationship("Email", back_populates="attachments")

    def __repr__(self):
        return f"<EmailAttachment(id={self.id}, filename='{self.filename}', size={self.size_bytes})>"


class EmailProcessingLog(Base):
    """Email processing log model."""
    __tablename__ = "email_processing_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)

    # Processing details
    step = Column(String(50), nullable=False)  # ingestion, validation, extraction, etc.
    status = Column(String(20), nullable=False)  # started, completed, failed
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional processing details

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Error handling
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Relationships
    email = relationship("Email", back_populates="processing_logs")

    def __repr__(self):
        return f"<EmailProcessingLog(id={self.id}, step='{self.step}', status='{self.status}')>"


class EmailCredentials(Base):
    """Stored email credentials model."""
    __tablename__ = "email_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    provider = Column(String(20), nullable=False, default=EmailProvider.GMAIL)

    # OAuth credentials (encrypted in production)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)

    # Provider-specific
    provider_user_id = Column(String(255), nullable=False)  # Gmail user ID, etc.
    provider_email = Column(String(255), nullable=False)

    # Status
    is_active = Column(Boolean, default=True)
    is_valid = Column(Boolean, default=True)
    last_validated = Column(DateTime(timezone=True), nullable=True)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Usage limits
    daily_quota_used = Column(Integer, default=0)
    quota_reset_date = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<EmailCredentials(id={self.id}, provider='{self.provider}', email='{self.provider_email}')>"


class EmailMonitoringConfig(Base):
    """Email monitoring configuration model."""
    __tablename__ = "email_monitoring_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    credentials_id = Column(UUID(as_uuid=True), ForeignKey("email_credentials.id"), nullable=False)

    # Monitoring settings
    is_active = Column(Boolean, default=True)
    monitoring_interval_minutes = Column(Integer, default=60)
    days_back_to_process = Column(Integer, default=7)
    max_emails_per_run = Column(Integer, default=50)

    # Filtering
    email_filters = Column(JSON, nullable=True)  # Search filters
    trusted_senders = Column(JSON, nullable=True)  # List of trusted email domains
    blocked_senders = Column(JSON, nullable=True)  # List of blocked email domains

    # Processing options
    auto_process_invoices = Column(Boolean, default=True)
    auto_approve_threshold = Column(Integer, default=90)  # Confidence threshold
    security_validation_enabled = Column(Boolean, default=True)

    # Notification settings
    notify_on_success = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)
    notify_on_security_issues = Column(Boolean, default=True)

    # Statistics
    total_emails_processed = Column(Integer, default=0)
    total_invoices_found = Column(Integer, default=0)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    credentials = relationship("EmailCredentials")

    def __repr__(self):
        return f"<EmailMonitoringConfig(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class EmailSecurityRule(Base):
    """Custom email security rules model."""
    __tablename__ = "email_security_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Rule definition
    rule_type = Column(String(50), nullable=False)  # sender_domain, subject_pattern, attachment_type, etc.
    rule_pattern = Column(String(500), nullable=False)
    rule_action = Column(String(50), nullable=False)  # block, warn, allow

    # Rule properties
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=100)  # Lower number = higher priority
    description = Column(Text, nullable=True)

    # Statistics
    times_matched = Column(Integer, default=0)
    last_matched = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<EmailSecurityRule(id={self.id}, name='{self.name}', action='{self.rule_action}')>"