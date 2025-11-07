"""
Invoice-related database models.
"""

import enum
import uuid
from typing import Optional

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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice processing status."""

    RECEIVED = "received"
    PARSED = "parsed"
    VALIDATED = "validated"
    EXCEPTION = "exception"
    READY = "ready"
    STAGED = "staged"
    DONE = "done"


class ExportFormat(str, enum.Enum):
    """Export format options."""

    CSV = "csv"
    JSON = "json"


class ExportStatus(str, enum.Enum):
    """Export processing status."""

    PREPARED = "prepared"
    SENT = "sent"
    FAILED = "failed"


class Invoice(Base, UUIDMixin, TimestampMixin):
    """Main invoice record."""

    __tablename__ = "invoices"

    # Invoice metadata
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True, index=True)
    file_url = Column(Text, nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_size = Column(String(20), nullable=False)  # Human-readable size

    # Processing status
    status = Column(
        Enum(InvoiceStatus), default=InvoiceStatus.RECEIVED, nullable=False, index=True
    )

    # Workflow tracking
    workflow_state = Column(String(50), nullable=True, index=True)
    workflow_data = Column(JSON, nullable=True)

    # Additional performance indexes
    __table_args__ = (
        Index('idx_vendor_status', 'vendor_id', 'status'),
        Index('idx_created_status', 'created_at', 'status'),
        Index('idx_workflow_status', 'workflow_state', 'status'),
        # Constraints for data integrity
        CheckConstraint("file_size <> ''", name='check_file_size_not_empty'),
        CheckConstraint("file_name <> ''", name='check_file_name_not_empty'),
    )

    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    extractions = relationship("InvoiceExtraction", back_populates="invoice", cascade="all, delete-orphan")
    validations = relationship("Validation", back_populates="invoice", cascade="all, delete-orphan")
    exceptions = relationship("Exception", back_populates="invoice", cascade="all, delete-orphan")
    staged_exports = relationship("StagedExport", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Invoice(id={self.id}, vendor_id={self.vendor_id}, status={self.status})>"


class InvoiceExtraction(Base, UUIDMixin, TimestampMixin):
    """Document extraction results."""

    __tablename__ = "invoice_extractions"

    # Relationships
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Extraction data
    header_json = Column(JSON, nullable=False)
    lines_json = Column(JSON, nullable=False)
    confidence_json = Column(JSON, nullable=False)

    # Metadata
    parser_version = Column(String(50), nullable=False)
    processing_time_ms = Column(String(20), nullable=True)
    page_count = Column(String(10), nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="extractions")

    def __repr__(self):
        return f"<InvoiceExtraction(id={self.id}, invoice_id={self.invoice_id})>"


class Validation(Base, UUIDMixin, TimestampMixin):
    """Validation results for invoices."""

    __tablename__ = "validations"

    # Relationships
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Validation results
    passed = Column(Boolean, nullable=False, default=False, index=True)
    checks_json = Column(JSON, nullable=False)
    rules_version = Column(String(50), nullable=False)

    # Validation metadata
    validator_version = Column(String(50), nullable=False)
    processing_time_ms = Column(String(20), nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="validations")

    def __repr__(self):
        return f"<Validation(id={self.id}, invoice_id={self.invoice_id}, passed={self.passed})>"


class Exception(Base, UUIDMixin, TimestampMixin):
    """Exception records for failed validations with comprehensive tracking."""

    __tablename__ = "exceptions"

    # Relationships
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    # Exception details
    reason_code = Column(String(50), nullable=False, index=True)
    details_json = Column(JSON, nullable=False)

    # Resolution tracking
    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_exception_invoice_status', 'invoice_id', 'resolved_at'),
        Index('idx_exception_reason_created', 'reason_code', 'created_at'),
        Index('idx_exception_resolved_by', 'resolved_by', 'resolved_at'),
        Index('idx_exception_created_at', 'created_at'),
        Index('idx_exception_resolved_at', 'resolved_at'),
        # Constraints for data integrity
        CheckConstraint("reason_code <> ''", name='check_exception_reason_code_not_empty'),
        CheckConstraint("details_json IS NOT NULL", name='check_exception_details_not_null'),
    )

    # Relationships
    invoice = relationship("Invoice", back_populates="exceptions")

    def __repr__(self):
        return f"<Exception(id={self.id}, reason_code={self.reason_code}, resolved={self.resolved_at})>"


class StagedExport(Base, UUIDMixin, TimestampMixin):
    """Staged export records for approved invoices."""

    __tablename__ = "staged_exports"

    # Relationships
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)

    # Export data
    payload_json = Column(JSON, nullable=False)
    format = Column(Enum(ExportFormat), nullable=False)
    status = Column(Enum(ExportStatus), default=ExportStatus.PREPARED, nullable=False)

    # Destination details
    destination = Column(String(255), nullable=False)
    export_job_id = Column(String(100), nullable=True)

    # Export metadata
    file_name = Column(String(255), nullable=True)
    file_size = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="staged_exports")

    def __repr__(self):
        return f"<StagedExport(id={self.id}, format={self.format}, status={self.status})>"