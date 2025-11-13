"""
Vendor API schemas.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, ConfigDict

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
    status: str  # Changed from VendorStatus to str to match database
    active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        # Handle both standard uuid.UUID and asyncpg UUID types
        if hasattr(v, 'hex') or hasattr(v, '__str__'):
            # Check if it's a UUID-like object (standard UUID or asyncpg UUID)
            if isinstance(v, UUID) or 'UUID' in str(type(v)):
                return str(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class VendorListResponse(BaseModel):
    """Response schema for listing vendors."""
    vendors: List[VendorResponse]
    total: int
    skip: int
    limit: int