"""
Invoice API schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

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
    """Invoice response schema."""
    id: str
    status: InvoiceStatus
    file_hash: str
    file_url: str
    workflow_state: Optional[str] = None
    requires_human_review: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

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
    id: str
    invoice_id: str
    header: dict
    lines: List[dict]
    confidence: dict
    parser_version: str
    created_at: datetime

    class Config:
        from_attributes = True


class ValidationResponse(BaseModel):
    """Validation response."""
    id: str
    invoice_id: str
    passed: bool
    checks: dict
    rules_version: str
    created_at: datetime

    class Config:
        from_attributes = True