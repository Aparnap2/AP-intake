"""
Pydantic models for structured invoice data validation.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ValidationInfo, ValidationError, model_validator
from pydantic.types import condecimal, constr


# Invoice line item validation
class InvoiceLineItem(BaseModel):
    """Structured line item for invoice data."""
    description: str = Field(..., min_length=1, max_length=500)
    quantity: condecimal(gt=0, decimal_places=2) = Field(..., description="Quantity must be positive")
    unit_price: condecimal(gt=0, decimal_places=2) = Field(..., description="Unit price must be positive")
    total_amount: condecimal(ge=0, decimal_places=2) = Field(..., description="Total amount (quantity × unit price)")
    line_number: Optional[int] = Field(None, ge=1, description="Line number on invoice")
    item_code: Optional[str] = Field(None, max_length=50, description="Product/service code")

    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        """Ensure total_amount equals quantity × unit_price."""
        quantity = info.data.get('quantity') if isinstance(info.data, dict) else None
        unit_price = info.data.get('unit_price') if isinstance(info.data, dict) else None
        if isinstance(quantity, Decimal) and isinstance(unit_price, Decimal):
            expected = quantity * unit_price
            if abs(v - expected) > Decimal('0.01'):  # Allow small rounding differences
                raise ValueError(f"Total amount {v} does not match quantity×unit_price {expected}")
        return v


# Invoice header validation
class InvoiceHeader(BaseModel):
    """Structured header information for invoice data."""
    invoice_number: Optional[str] = Field(None, max_length=50, description="Invoice number as shown on document")
    invoice_date: Optional[Union[datetime, date]] = Field(None, description="Invoice date")
    due_date: Optional[Union[datetime, date]] = Field(None, description="Due date for payment")
    vendor_name: Optional[str] = Field(None, min_length=1, max_length=200, description="Vendor/Company name")
    vendor_address: Optional[Dict[str, Any]] = Field(None, description="Vendor address information")
    vendor_tax_id: Optional[str] = Field(None, max_length=50, description="Vendor tax ID/ABN")

    # Financial totals
    subtotal_amount: Optional[condecimal(ge=0, decimal_places=2)] = Field(None, description="Subtotal before tax")
    tax_amount: Optional[condecimal(ge=0, decimal_places=2)] = Field(None, description="Total tax amount")
    total_amount: Optional[condecimal(ge=0, decimal_places=2)] = Field(None, description="Grand total amount")

    # Currency information
    currency: Optional[str] = Field("USD", max_length=3, description="3-letter currency code")

    @field_validator('due_date')
    @classmethod
    def validate_due_date_after_invoice_date(cls, v: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        """Ensure due date is after invoice date."""
        if v is not None:
            invoice_date = info.data.get('invoice_date') if isinstance(info.data, dict) else None
            if isinstance(invoice_date, datetime) and v <= invoice_date:
                raise ValueError("Due date must be after invoice date")
        return v


# Confidence scoring validation
class ConfidenceScores(BaseModel):
    """Confidence scores for extraction results."""
    overall: condecimal(ge=0, le=1, decimal_places=3) = Field(..., description="Overall confidence score (0-1)")

    # Field-specific confidence scores
    invoice_number_confidence: condecimal(ge=0, le=1, decimal_places=3) = Field(0.0, description="Invoice number confidence")
    vendor_confidence: condecimal(ge=0, le=1, decimal_places=3) = Field(0.0, description="Vendor name confidence")
    date_confidence: condecimal(ge=0, le=1, decimal_places=3) = Field(0.0, description="Date confidence")
    amounts_confidence: condecimal(ge=0, le=1, decimal_places=3) = Field(0.0, description="Amount values confidence")
    line_items_confidence: condecimal(ge=0, le=1, decimal_places=3) = Field(0.0, description="Line items confidence")

    @field_validator('overall')
    @classmethod
    def validate_overall_range(cls, v: Decimal) -> Decimal:
        """Ensure overall confidence is between 0 and 1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Overall confidence must be between 0 and 1")
        return v


# Extraction metadata
class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process."""
    parser_version: str = Field(..., description="Version of the parser used")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")
    page_count: int = Field(..., ge=1, description="Number of pages processed")
    file_size_bytes: int = Field(..., ge=0, description="Original file size in bytes")

    # Extraction quality metrics
    completeness_score: Optional[condecimal(ge=0, le=1, decimal_places=3)] = Field(None, description="Data completeness score")
    accuracy_score: Optional[condecimal(ge=0, le=1, decimal_places=3)] = Field(None, description="Extraction accuracy score")

    @field_validator('processing_time_ms')
    @classmethod
    def validate_processing_time(cls, v: int) -> int:
        """Ensure processing time is reasonable."""
        if v < 0:
            raise ValueError("Processing time must be non-negative")
        return v


# Main extraction result
class InvoiceExtractionResult(BaseModel):
    """Structured invoice extraction result with validation."""

    # Extracted data
    header: InvoiceHeader = Field(..., description="Invoice header information")
    lines: List[InvoiceLineItem] = Field(..., min_items=0, description="Line items")

    # Quality metrics
    confidence: ConfidenceScores = Field(..., description="Confidence scores for each field")

    # Metadata
    metadata: ExtractionMetadata = Field(..., description="Extraction metadata")

    # Processing status
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_notes: Optional[List[str]] = Field(default=None, description="Notes about processing issues")

    @model_validator(mode='after')
    def validate_data_consistency(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate internal consistency of extracted data."""
        header = values.get('header')
        lines = values.get('lines', [])

        # Validate that total amounts match line item totals
        if header and isinstance(header, InvoiceHeader) and lines:
            line_total = sum(item.total_amount for item in lines)
            header_total = header.total_amount

            if header_total is not None and abs(line_total - header_total) > Decimal('0.05'):
                raise ValueError(
                    f"Line item total ({line_total}) doesn't match header total ({header_total}). "
                    "Discrepancy > $0.05 indicates extraction error."
                )

        return values

    def get_display_amount(self) -> str:
        """Get formatted total amount for display."""
        if self.header.total_amount is not None:
            return f"${self.header.total_amount:.2f}"
        return "$0.00"

    def get_display_vendor(self) -> str:
        """Get vendor name for display."""
        return self.header.vendor_name or "Unknown Vendor"

    def get_display_invoice_number(self) -> str:
        """Get invoice number for display."""
        return self.header.invoice_number or "No Invoice Number"

    def get_display_date(self) -> str:
        """Get formatted invoice date for display."""
        if self.header.invoice_date:
            if isinstance(self.header.invoice_date, datetime):
                return self.header.invoice_date.strftime("%Y-%m-%d")
            elif isinstance(self.header.invoice_date, date):
                return self.header.invoice_date.isoformat()
        return "No Date"

    def get_confidence_percentage(self) -> str:
        """Get confidence score as percentage."""
        return f"{float(self.confidence.overall * 100):.1f}%"


# Validation result for business rules
class BusinessRuleValidation(BaseModel):
    """Business rule validation results."""

    validation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    rules_version: str = Field("1.0.0", description="Version of validation rules applied")

    # Validation checks
    required_fields_present: bool = Field(..., description="All required fields are present")
    vendor_recognized: bool = Field(..., description="Vendor is in database")
    amounts_positive: bool = Field(..., description="All monetary amounts are positive")
    dates_logical: bool = Field(..., description="Dates are logical (due_date > invoice_date)")

    # Validation issues
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="Validation issues found")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="Non-critical issues found")

    # Overall assessment
    passed: bool = Field(..., description="Validation passed")
    requires_human_review: bool = Field(..., description="Requires human review")
    auto_approval_eligible: bool = Field(..., description="Eligible for automatic processing")

    def get_severity_counts(self) -> Dict[str, int]:
        """Get counts by severity level."""
        errors = len([i for i in self.issues if i.get('severity') == 'error'])
        warnings = len([i for i in self.issues if i.get('severity') == 'warning'])
        return {"errors": errors, "warnings": warnings}