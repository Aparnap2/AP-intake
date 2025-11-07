"""
Vendor API schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.reference import VendorStatus


class VendorBase(BaseModel):
    """Base vendor schema."""
    name: str
    tax_id: Optional[str] = None
    currency: str = "USD"
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms_days: Optional[str] = "30"
    credit_limit: Optional[str] = None


class VendorCreate(VendorBase):
    """Schema for creating vendors."""
    pass


class VendorResponse(VendorBase):
    """Vendor response schema."""
    id: str
    status: VendorStatus
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VendorListResponse(BaseModel):
    """Response schema for listing vendors."""
    vendors: List[VendorResponse]
    total: int
    skip: int
    limit: int