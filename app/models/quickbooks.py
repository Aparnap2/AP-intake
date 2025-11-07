"""
QuickBooks integration models for storing authentication and connection data.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
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


class QuickBooksConnectionStatus(str, enum.Enum):
    """QuickBooks connection status."""

    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"


class QuickBooksConnection(Base, UUIDMixin, TimestampMixin):
    """QuickBooks OAuth connection and token storage."""

    __tablename__ = "quickbooks_connections"

    # Connection metadata
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    realm_id = Column(String(50), nullable=False, index=True)  # QuickBooks company ID
    company_name = Column(String(255), nullable=True)

    # OAuth tokens
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)

    # Connection status
    status = Column(
        Enum(QuickBooksConnectionStatus),
        default=QuickBooksConnectionStatus.PENDING,
        nullable=False,
        index=True
    )

    # User and company info from QuickBooks
    user_info = Column(JSON, nullable=True)
    company_info = Column(JSON, nullable=True)

    # Configuration and preferences
    default_expense_account_id = Column(String(50), nullable=True)
    auto_export_enabled = Column(Boolean, default=False, nullable=False)
    webhook_enabled = Column(Boolean, default=False, nullable=False)

    # Error handling
    last_error = Column(Text, nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Unique constraint: one connection per user per company
    __table_args__ = (
        UniqueConstraint('user_id', 'realm_id', name='uq_user_realm'),
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_realm_status', 'realm_id', 'status'),
        Index('idx_token_expiry', 'token_expires_at', 'status'),
    )

    def __repr__(self):
        return f"<QuickBooksConnection(id={self.id}, realm_id={self.realm_id}, status={self.status})>"

    @property
    def is_token_expired(self) -> bool:
        """Check if the access token is expired."""
        return datetime.now(timezone.utc) >= self.token_expires_at

    @property
    def is_connected(self) -> bool:
        """Check if the connection is active and valid."""
        return (self.status == QuickBooksConnectionStatus.CONNECTED
                and not self.is_token_expired)


class QuickBooksExport(Base, UUIDMixin, TimestampMixin):
    """QuickBooks export tracking and audit log."""

    __tablename__ = "quickbooks_exports"

    # Relationships
    connection_id = Column(UUID(as_uuid=True), ForeignKey("quickbooks_connections.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), nullable=False)

    # Export details
    quickbooks_bill_id = Column(String(50), nullable=True, index=True)  # QuickBooks entity ID
    export_type = Column(String(20), default="bill", nullable=False)  # bill, invoice, etc.

    # Export status
    status = Column(String(20), default="pending", nullable=False, index=True)
    dry_run = Column(Boolean, default=False, nullable=False)

    # Data tracking
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(String(5), default="0", nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Performance metrics
    processing_time_ms = Column(String(20), nullable=True)

    # Relationships
    connection = relationship("QuickBooksConnection", backref="exports")

    __table_args__ = (
        Index('idx_connection_status', 'connection_id', 'status'),
        Index('idx_invoice_export', 'invoice_id', 'status'),
        Index('idx_quickbooks_bill', 'quickbooks_bill_id'),
        Index('idx_export_type_status', 'export_type', 'status'),
        Index('idx_retry_queue', 'next_retry_at', 'status'),
    )

    def __repr__(self):
        return f"<QuickBooksExport(id={self.id}, invoice_id={self.invoice_id}, status={self.status})>"


class QuickBooksWebhook(Base, UUIDMixin, TimestampMixin):
    """QuickBooks webhook event tracking."""

    __tablename__ = "quickbooks_webhooks"

    # Webhook metadata
    webhook_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    operation = Column(String(20), nullable=False)

    # Payload tracking
    raw_payload = Column(JSON, nullable=False)
    processed_payload = Column(JSON, nullable=True)

    # Processing status
    status = Column(String(20), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # Processing metadata
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_attempts = Column(String(5), default="0", nullable=False)

    __table_args__ = (
        Index('idx_webhook_event', 'webhook_id', 'event_type'),
        Index('idx_entity_operation', 'entity_type', 'entity_id', 'operation'),
        Index('idx_webhook_status', 'status', 'created_at'),
    )

    def __repr__(self):
        return f"<QuickBooksWebhook(id={self.id}, event_type={self.event_type}, entity_id={self.entity_id})>"


class QuickBooksVendorMapping(Base, UUIDMixin, TimestampMixin):
    """Mapping between local vendor data and QuickBooks vendor IDs."""

    __tablename__ = "quickbooks_vendor_mappings"

    # Relationships
    connection_id = Column(UUID(as_uuid=True), ForeignKey("quickbooks_connections.id"), nullable=False)
    local_vendor_id = Column(UUID(as_uuid=True), nullable=False)

    # QuickBooks reference
    quickbooks_vendor_id = Column(String(50), nullable=False, index=True)
    quickbooks_vendor_name = Column(String(255), nullable=False)

    # Mapping status
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Sync data
    local_data = Column(JSON, nullable=True)
    quickbooks_data = Column(JSON, nullable=True)

    # Relationships
    connection = relationship("QuickBooksConnection", backref="vendor_mappings")

    __table_args__ = (
        UniqueConstraint('connection_id', 'local_vendor_id', name='uq_connection_local_vendor'),
        UniqueConstraint('connection_id', 'quickbooks_vendor_id', name='uq_connection_qb_vendor'),
        Index('idx_local_vendor', 'local_vendor_id'),
        Index('idx_qb_vendor_name', 'quickbooks_vendor_name'),
    )

    def __repr__(self):
        return f"<QuickBooksVendorMapping(id={self.id}, local_vendor_id={self.local_vendor_id}, qb_vendor_id={self.quickbooks_vendor_id})>"


class QuickBooksAccountMapping(Base, UUIDMixin, TimestampMixin):
    """Mapping for expense accounts and chart of accounts."""

    __tablename__ = "quickbooks_account_mappings"

    # Relationships
    connection_id = Column(UUID(as_uuid=True), ForeignKey("quickbooks_connections.id"), nullable=False)

    # Account details
    quickbooks_account_id = Column(String(50), nullable=False, index=True)
    quickbooks_account_name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)  # Expense, Cost of Goods Sold, etc.
    account_subtype = Column(String(50), nullable=True)

    # Default mappings
    is_default_expense = Column(Boolean, default=False, nullable=False)
    is_default_cogs = Column(Boolean, default=False, nullable=False)

    # Usage tracking
    usage_count = Column(String(10), default="0", nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Account data
    quickbooks_data = Column(JSON, nullable=True)

    # Relationships
    connection = relationship("QuickBooksConnection", backref="account_mappings")

    __table_args__ = (
        UniqueConstraint('connection_id', 'quickbooks_account_id', name='uq_connection_qb_account'),
        Index('idx_account_type', 'account_type', 'is_default_expense'),
        Index('idx_account_name', 'quickbooks_account_name'),
    )

    def __repr__(self):
        return f"<QuickBooksAccountMapping(id={self.id}, account_name={self.quickbooks_account_name}, type={self.account_type})>"