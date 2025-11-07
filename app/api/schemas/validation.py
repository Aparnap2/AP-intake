"""
Validation API schemas and data models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCode(str, Enum):
    """Standardized validation error codes."""

    # Structural validation
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_FORMAT = "INVALID_FIELD_FORMAT"
    INVALID_DATA_STRUCTURE = "INVALID_DATA_STRUCTURE"
    NO_LINE_ITEMS = "NO_LINE_ITEMS"

    # Math validation
    SUBTOTAL_MISMATCH = "SUBTOTAL_MISMATCH"
    TOTAL_MISMATCH = "TOTAL_MISMATCH"
    LINE_MATH_MISMATCH = "LINE_MATH_MISMATCH"
    INVALID_AMOUNT = "INVALID_AMOUNT"

    # Business rule validation
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    EXCESSIVE_AMOUNT = "EXCESSIVE_AMOUNT"
    OLD_INVOICE = "OLD_INVOICE"
    INACTIVE_VENDOR = "INACTIVE_VENDOR"

    # Matching validation
    PO_NOT_FOUND = "PO_NOT_FOUND"
    PO_MISMATCH = "PO_MISMATCH"
    PO_AMOUNT_MISMATCH = "PO_AMOUNT_MISMATCH"
    PO_QUANTITY_MISMATCH = "PO_QUANTITY_MISMATCH"
    GRN_NOT_FOUND = "GRN_NOT_FOUND"
    GRN_MISMATCH = "GRN_MISMATCH"
    GRN_QUANTITY_MISMATCH = "GRN_QUANTITY_MISMATCH"

    # Vendor policy validation
    INVALID_CURRENCY = "INVALID_CURRENCY"
    INVALID_TAX_ID = "INVALID_TAX_ID"
    SPEND_LIMIT_EXCEEDED = "SPEND_LIMIT_EXCEEDED"
    PAYMENT_TERMS_VIOLATION = "PAYMENT_TERMS_VIOLATION"

    # System validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


class ValidationIssue(BaseModel):
    """Individual validation issue."""
    code: ValidationCode
    message: str
    severity: ValidationSeverity
    field: Optional[str] = None
    line_number: Optional[int] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class MathValidationResult(BaseModel):
    """Math validation result."""
    lines_total: float
    subtotal_match: Optional[bool] = None
    subtotal_difference: Optional[float] = None
    total_match: Optional[bool] = None
    total_difference: Optional[float] = None
    tax_amount: float
    line_item_validation: List[Dict[str, Any]]


class MatchingResult(BaseModel):
    """Purchase order and goods receipt matching result."""
    po_found: bool
    po_number: Optional[str] = None
    po_status: Optional[str] = None
    po_amount_match: Optional[bool] = None
    po_amount_difference: Optional[float] = None
    grn_found: bool = False
    grn_number: Optional[str] = None
    grn_status: Optional[str] = None
    quantity_match: Optional[bool] = None
    quantity_difference: Optional[float] = None
    matching_type: str  # "2_way", "3_way", or "none"


class VendorPolicyResult(BaseModel):
    """Vendor policy validation result."""
    vendor_active: bool
    currency_valid: bool
    tax_id_valid: Optional[bool] = None
    spend_limit_ok: Optional[bool] = None
    current_spend: Optional[float] = None
    spend_limit: Optional[float] = None
    payment_terms_ok: bool
    vendor_policy_issues: List[ValidationIssue]


class DuplicateCheckResult(BaseModel):
    """Duplicate invoice check result."""
    is_duplicate: bool
    duplicate_invoices: List[Dict[str, Any]] = []
    match_criteria: Dict[str, Any] = {}
    confidence: float = 0.0


class ValidationCheckResult(BaseModel):
    """Detailed validation check results."""
    structure_check: bool
    header_fields_check: bool
    line_items_check: bool
    math_check: bool
    business_rules_check: bool
    duplicate_check: bool
    vendor_policy_check: bool
    matching_check: bool


class ValidationResult(BaseModel):
    """Complete validation result."""
    passed: bool
    confidence_score: float
    total_issues: int
    error_count: int
    warning_count: int
    info_count: int

    # Detailed results
    issues: List[ValidationIssue]
    math_validation: Optional[MathValidationResult] = None
    matching_result: Optional[MatchingResult] = None
    vendor_policy_result: Optional[VendorPolicyResult] = None
    duplicate_check_result: Optional[DuplicateCheckResult] = None
    check_results: ValidationCheckResult

    # Metadata
    validated_at: datetime
    rules_version: str
    validator_version: str
    processing_time_ms: Optional[str] = None

    # Extracted data reference
    header_summary: Dict[str, Any]
    lines_summary: Dict[str, Any]


class ValidationRule(BaseModel):
    """Configurable validation rule."""
    name: str
    description: str
    enabled: bool = True
    severity: ValidationSeverity
    parameters: Dict[str, Any] = {}
    conditions: Dict[str, Any] = {}


class ValidationRulesConfig(BaseModel):
    """Complete validation rules configuration."""
    version: str
    rules: List[ValidationRule]
    thresholds: Dict[str, float] = Field(default_factory=lambda: {
        "max_invoice_age_days": 365,
        "max_total_amount": 1000000,
        "min_line_amount": 0.01,
        "max_line_amount": 100000,
        "duplicate_confidence_threshold": 0.95,
        "po_amount_tolerance_percent": 5.0,
        "grn_quantity_tolerance_percent": 10.0,
        "math_tolerance_cents": 1,
    })
    required_fields: Dict[str, List[str]] = Field(default_factory=lambda: {
        "header": ["vendor_name", "invoice_no", "invoice_date", "total"],
        "lines": ["description", "amount"],
    })


class ValidationRequest(BaseModel):
    """Request for validation service."""
    invoice_id: Optional[str] = None
    extraction_result: Dict[str, Any]
    vendor_id: Optional[str] = None
    rules_config: Optional[ValidationRulesConfig] = None
    strict_mode: bool = False


class ValidationResponse(BaseModel):
    """Validation service response."""
    success: bool
    validation_result: ValidationResult
    processing_time_ms: str
    applied_rules: List[str]


class ValidationSummary(BaseModel):
    """Summary of validation results for reporting."""
    total_invoices: int
    passed_invoices: int
    failed_invoices: int
    auto_approved: int
    human_review_required: int

    # Issue breakdown
    common_issues: List[Dict[str, Any]]
    issue_categories: Dict[str, int]

    # Performance metrics
    average_processing_time_ms: float
    confidence_distribution: Dict[str, int]

    # Matching statistics
    po_match_rate: float
    grn_match_rate: float
    duplicate_detection_rate: float

    generated_at: datetime


class ValidationExport(BaseModel):
    """Validation data export format."""
    invoice_id: str
    vendor_name: str
    invoice_number: str
    invoice_date: str
    total_amount: float
    currency: str

    validation_passed: bool
    confidence_score: float
    error_count: int
    warning_count: int

    # Key validation results
    math_passed: bool
    duplicate_found: bool
    po_matched: bool
    grn_matched: bool
    vendor_policy_passed: bool

    # Top issues
    top_issues: List[str]

    validated_at: datetime


class ValidationErrorDetail(BaseModel):
    """Detailed error information for debugging."""
    invoice_id: str
    error_code: ValidationCode
    error_message: str
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = {}
    suggestions: List[str] = []
    related_documentation: List[str] = []