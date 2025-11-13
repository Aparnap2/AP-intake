"""
Input validation and sanitization utilities for AP Intake & Validation system.
"""

import re
import html
from typing import Optional, Any, Dict, List
from fastapi import HTTPException, status


class ValidationError(HTTPException):
    """Custom validation error."""
    def __init__(self, message: str, field: Optional[str] = None):
        detail = {"error": "VALIDATION_ERROR", "message": message}
        if field:
            detail["field"] = field
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


def sanitize_string(input_str: Optional[str], max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent XSS attacks.

    Args:
        input_str: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValidationError: If input is invalid
    """
    if input_str is None:
        return ""

    # Type check
    if not isinstance(input_str, str):
        raise ValidationError("Input must be a string")

    # Length check
    if len(input_str) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    # Remove null bytes
    sanitized = input_str.replace('\x00', '')

    # HTML entity encoding (prevent XSS)
    sanitized = html.escape(sanitized)

    # Remove potentially dangerous characters
    # Allow basic text, numbers, spaces, and common punctuation
    dangerous_pattern = r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]'
    sanitized = re.sub(dangerous_pattern, '', sanitized)

    # Normalize whitespace
    sanitized = ' '.join(sanitized.split())

    return sanitized.strip()


def validate_search_query(query: Optional[str], max_length: int = 200) -> str:
    """
    Validate and sanitize search query.

    Args:
        query: Search query string
        max_length: Maximum allowed length

    Returns:
        Sanitized search query

    Raises:
        ValidationError: If query is invalid
    """
    if query is None:
        return ""

    sanitized = sanitize_string(query, max_length)

    # Additional search-specific validation
    if len(sanitized) < 1:
        raise ValidationError("Search query too short")

    # Prevent SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(--|#|/\*|\*/)",
        r"(\bOR\b.*=.*\bOR\b)",
        r"(\bAND\b.*=.*\bAND\b)",
        r"(['\"];?\s*(OR|AND)\s+.+=.+)",
        r"(\.\./|\.\.\\)",
    ]

    for pattern in sql_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            raise ValidationError("Invalid search query characters")

    return sanitized


def validate_uuid(uuid_string: str, field_name: str = "ID") -> str:
    """
    Validate UUID string format.

    Args:
        uuid_string: UUID string to validate
        field_name: Name of the field for error messages

    Returns:
        Validated UUID string

    Raises:
        ValidationError: If UUID is invalid
    """
    import uuid as uuid_lib

    if not isinstance(uuid_string, str):
        raise ValidationError(f"{field_name} must be a string")

    try:
        uuid_lib.UUID(uuid_string)
        return uuid_string
    except ValueError:
        raise ValidationError(f"Invalid {field_name} format")


def validate_email(email: str) -> str:
    """
    Validate email format.

    Args:
        email: Email string to validate

    Returns:
        Validated email string

    Raises:
        ValidationError: If email is invalid
    """
    if not isinstance(email, str):
        raise ValidationError("Email must be a string")

    email = email.strip().lower()

    # Basic email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format")

    return email


def validate_phone_number(phone: str) -> str:
    """
    Validate phone number format.

    Args:
        phone: Phone number string to validate

    Returns:
        Validated phone number string

    Raises:
        ValidationError: If phone number is invalid
    """
    if not isinstance(phone, str):
        raise ValidationError("Phone number must be a string")

    # Remove all non-digit characters
    phone = re.sub(r'[^\d]', '', phone)

    # Check length (basic validation)
    if len(phone) < 10 or len(phone) > 15:
        raise ValidationError("Invalid phone number length")

    return phone


def validate_positive_integer(value: Any, field_name: str = "Value") -> int:
    """
    Validate positive integer.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated integer value

    Raises:
        ValidationError: If value is invalid
    """
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValidationError(f"{field_name} must be positive")
        return int_value
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid positive integer")


def validate_positive_float(value: Any, field_name: str = "Value") -> float:
    """
    Validate positive float.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated float value

    Raises:
        ValidationError: If value is invalid
    """
    try:
        float_value = float(value)
        if float_value <= 0:
            raise ValidationError(f"{field_name} must be positive")
        return float_value
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid positive number")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename

    Raises:
        ValidationError: If filename is invalid
    """
    if not isinstance(filename, str):
        raise ValidationError("Filename must be a string")

    # Remove directory traversal attempts
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')

    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)

    # Check if filename is empty after sanitization
    if not filename.strip():
        raise ValidationError("Invalid filename")

    # Limit length
    if len(filename) > 255:
        raise ValidationError("Filename too long")

    return filename.strip()


def validate_json_dict(data: Any, max_size: int = 1024 * 1024) -> Dict[str, Any]:
    """
    Validate JSON data is a dictionary and within size limits.

    Args:
        data: Data to validate
        max_size: Maximum size in bytes

    Returns:
        Validated dictionary

    Raises:
        ValidationError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError("Data must be a JSON object")

    import json
    try:
        json_str = json.dumps(data)
        if len(json_str.encode('utf-8')) > max_size:
            raise ValidationError(f"Data too large (max {max_size} bytes)")
        return data
    except (TypeError, ValueError):
        raise ValidationError("Invalid JSON data")


class InputValidator:
    """Utility class for input validation."""

    @staticmethod
    def validate_pagination_params(skip: int = 0, limit: int = 100) -> tuple[int, int]:
        """Validate pagination parameters."""
        skip = validate_positive_integer(skip, "skip")
        limit = validate_positive_integer(limit, "limit")

        if limit > 1000:
            raise ValidationError("Maximum limit is 1000")

        return skip, limit

    @staticmethod
    def validate_sort_params(sort_by: Optional[str], sort_order: Optional[str]) -> tuple[str, str]:
        """Validate sorting parameters."""
        if sort_by is None:
            sort_by = "created_at"
        else:
            sort_by = sanitize_string(sort_by, 50)

        if sort_order is None:
            sort_order = "desc"
        else:
            sort_order = sanitize_string(sort_order, 10).lower()
            if sort_order not in ["asc", "desc"]:
                raise ValidationError("sort_order must be 'asc' or 'desc'")

        return sort_by, sort_order