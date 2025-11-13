"""
Reference data models (vendors, POs, GRNs).
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class VendorStatus(str, enum.Enum):
    """Vendor status options."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class POStatus(str, enum.Enum):
    """Purchase order status options."""

    DRAFT = "draft"
    SENT = "sent"
    PARTIAL = "partial"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Vendor(Base, UUIDMixin, TimestampMixin):
    """Vendor master data."""

    __tablename__ = "vendors"

    # Basic vendor information
    name = Column(String(255), nullable=False, index=True)
    tax_id = Column(String(50), nullable=True, unique=True)
    currency = Column(String(3), nullable=False, default="USD")

    # Contact information
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)

    # Status and metadata
    active = Column(Boolean, nullable=False, default=True, index=True)
    status = Column(String(20), default="active", nullable=False)

    # Vendor-specific rules
    payment_terms_days = Column(String(10), nullable=True, default="30")
    credit_limit = Column(String(20), nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_vendor_active_status', 'active', 'status'),
        Index('idx_vendor_name_active', 'name', 'active'),
        # Data integrity constraints
        CheckConstraint("name <> ''", name='check_vendor_name_not_empty'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='check_currency_format'),
        CheckConstraint(r"CASE WHEN email IS NOT NULL THEN email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' ELSE true END",
                       name='check_email_format'),
    )

    # Relationships
    invoices = relationship("Invoice", back_populates="vendor")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    ingestion_jobs = relationship("IngestionJob", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor(id={self.id}, name={self.name}, status={self.status})>"


class PurchaseOrder(Base, UUIDMixin, TimestampMixin):
    """Purchase order master data."""

    __tablename__ = "purchase_orders"

    # PO identification
    po_no = Column(String(100), nullable=False, unique=True, index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)

    # PO details
    lines_json = Column(JSON, nullable=False)
    total_amount = Column(String(20), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Status and dates
    status = Column(Enum(POStatus), default=POStatus.DRAFT, nullable=False, index=True)
    order_date = Column(DateTime(timezone=True), nullable=True)
    expected_date = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_by = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_po_vendor_status', 'vendor_id', 'status'),
        Index('idx_po_status_date', 'status', 'order_date'),
        Index('idx_po_expected_date', 'expected_date'),
        # Data integrity constraints
        CheckConstraint("po_no <> ''", name='check_po_no_not_empty'),
        CheckConstraint("total_amount <> ''", name='check_total_amount_not_empty'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='check_po_currency_format'),
        CheckConstraint('expected_date IS NULL OR expected_date >= order_date',
                       name='check_expected_date_after_order'),
    )

    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    goods_receipt_notes = relationship("GoodsReceiptNote", back_populates="purchase_order")

    def __repr__(self):
        return f"<PurchaseOrder(po_no={self.po_no}, status={self.status})>"


class GoodsReceiptNote(Base, UUIDMixin, TimestampMixin):
    """Goods receipt note master data."""

    __tablename__ = "goods_receipt_notes"

    # GRN identification
    grn_no = Column(String(100), nullable=False, unique=True, index=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)

    # Receipt details
    lines_json = Column(JSON, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)

    # Additional information
    carrier = Column(String(255), nullable=True)
    tracking_no = Column(String(100), nullable=True)
    received_by = Column(String(255), nullable=True)

    # Performance indexes and constraints
    __table_args__ = (
        Index('idx_grn_po_received', 'po_id', 'received_at'),
        Index('idx_grn_received_date', 'received_at'),
        Index('idx_grn_carrier', 'carrier'),
        # Data integrity constraints
        CheckConstraint("grn_no <> ''", name='check_grn_no_not_empty'),
        CheckConstraint("received_by <> ''", name='check_received_by_not_empty'),
    )

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipt_notes")

    def __repr__(self):
        return f"<GoodsReceiptNote(grn_no={self.grn_no}, received_at={self.received_at})>"