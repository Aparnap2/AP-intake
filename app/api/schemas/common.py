"""
Common API schemas.
"""

from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


class BaseResponse(BaseModel):
    """Base response with common fields."""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StandardResponse(BaseModel, Generic[T]):
    """Standard response wrapper for API endpoints."""
    success: bool = True
    message: str
    data: T
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def success_response(cls, data: T, message: str = "Operation successful", details: Optional[Dict[str, Any]] = None) -> "StandardResponse[T]":
        """Create a successful response."""
        return cls(
            success=True,
            message=message,
            data=data,
            timestamp=datetime.utcnow(),
            details=details
        )

    @classmethod
    def error_response(cls, message: str, data: Optional[T] = None, details: Optional[Dict[str, Any]] = None) -> "StandardResponse[T]":
        """Create an error response."""
        return cls(
            success=False,
            message=message,
            data=data,
            timestamp=datetime.utcnow(),
            details=details
        )