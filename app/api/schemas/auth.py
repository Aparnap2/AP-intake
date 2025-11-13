"""
Authentication schemas for AP Intake & Validation system.
"""

from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    is_active: bool = True
    is_admin: bool = False


class UserCreate(UserBase):
    """User creation schema."""
    password: str


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema."""
    id: str

    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """User as stored in database."""
    hashed_password: str


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str
    expires_in: int
    user: dict


class TokenData(BaseModel):
    """Token data schema."""
    user_id: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


class PasswordChange(BaseModel):
    """Password change request schema."""
    current_password: str
    new_password: str


class PasswordReset(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str