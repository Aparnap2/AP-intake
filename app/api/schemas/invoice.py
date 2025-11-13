"""
Invoice API schemas.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer
from decimal import Decimal

from app.models.invoice import InvoiceStatus


class InvoiceBase(BaseModel):
    """Base invoice schema."""
    vendor_id: Optional[str] = None
    file_name: str
    file_size: str


class InvoiceCreate(InvoiceBase):
    """Schema for creating invoices."""
    pass


class InvoiceResponse(InvoiceBase):
    """Invoice response schema with rich extraction data."""
    id: UUID
    status: InvoiceStatus
    file_hash: str
    file_url: str
    workflow_state: Optional[str] = None
    requires_human_review: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    # Rich extraction data fields
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_id: Optional[str] = None  # Add vendor_id for frontend compatibility
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = "USD"
    confidence: Optional[float] = 0.0
    validation_issues: Optional[int] = 0
    priority: Optional[str] = "medium"
    amount: Optional[float] = None  # Add amount alias for frontend compatibility
    uploaded_at: Optional[datetime] = None  # Add uploaded_at alias

    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer('vendor_id')
    def serialize_vendor_id(self, value: Optional[str]) -> Optional[str]:
        return str(value) if value else None

    @field_serializer('total_amount')
    def serialize_total_amount(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value is not None else None

    @field_serializer('confidence')
    def serialize_confidence(self, value: Optional[float]) -> Optional[float]:
        # Convert to percentage format for frontend
        return round(value * 100, 1) if value is not None else 0.0

    @field_serializer('invoice_date')
    def serialize_invoice_date(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('due_date')
    def serialize_due_date(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('uploaded_at')
    def serialize_uploaded_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('updated_at')
    def serialize_updated_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer('status')
    def serialize_status(self, value: InvoiceStatus) -> str:
        return value.value

    class Config:
        from_attributes = True


class InvoiceUpdate(BaseModel):
    """Schema for updating invoices."""
    status: Optional[InvoiceStatus] = None
    workflow_state: Optional[str] = None
    requires_human_review: Optional[bool] = None


class InvoiceListResponse(BaseModel):
    """Response schema for listing invoices."""
    invoices: List[InvoiceResponse]
    total: int
    skip: int
    limit: int


class InvoiceExtractionResponse(BaseModel):
    """Invoice extraction response."""
    id: UUID
    invoice_id: UUID
    header: dict
    lines: List[dict]
    confidence: dict
    parser_version: str
    created_at: datetime

    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer('invoice_id')
    def serialize_invoice_id(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True


class ValidationResponse(BaseModel):
    """Validation response."""
    id: UUID
    invoice_id: UUID
    passed: bool
    checks: dict
    rules_version: str
    created_at: datetime

    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer('invoice_id')
    def serialize_invoice_id(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True