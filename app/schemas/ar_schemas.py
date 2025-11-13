"""
Pydantic schemas for AR (Accounts Receivable) API endpoints.

These schemas provide data validation and serialization for AR customers and invoices.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator, ConfigDict


class CustomerBase(BaseModel):
    """Base schema for customer data."""
    name: str = Field(..., min_length=1, max_length=255, description="Customer name")
    tax_id: Optional[str] = Field(None, max_length=50, description="Tax identification number")
    email: Optional[EmailStr] = Field(None, description="Customer email address")
    phone: Optional[str] = Field(None, max_length=50, description="Customer phone number")
    address: Optional[str] = Field(None, description="Customer address")
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$", description="Customer currency")
    credit_limit: Optional[Decimal] = Field(0, ge=0, description="Credit limit")
    payment_terms_days: int = Field(30, ge=0, le=365, description="Payment terms in days")
    active: bool = Field(True, description="Whether customer is active")


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response data."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    outstanding_balance: Decimal = Field(0, description="Total outstanding balance")
    available_credit: Decimal = Field(0, description="Available credit")
    invoice_count: int = Field(0, description="Total number of invoices")

    model_config = ConfigDict(from_attributes=True)


class PaymentStatus(str):
    """Payment status enum."""
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITE_OFF = "write_off"
    DISPUTED = "disputed"


class CollectionPriority(str):
    """Collection priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ARInvoiceBase(BaseModel):
    """Base schema for AR invoice data."""
    invoice_number: str = Field(..., min_length=1, max_length=100, description="Invoice number")
    invoice_date: datetime = Field(..., description="Invoice date")
    due_date: datetime = Field(..., description="Due date")
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$", description="Invoice currency")
    subtotal: Decimal = Field(..., ge=0, description="Invoice subtotal")
    tax_amount: Decimal = Field(..., ge=0, description="Tax amount")
    total_amount: Decimal = Field(..., gt=0, description="Total amount")
    early_payment_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100, description="Early payment discount percentage")
    early_payment_discount_days: Optional[int] = Field(None, ge=0, description="Early payment discount days")
    expected_payment_date: Optional[datetime] = Field(None, description="Expected payment date")
    working_capital_impact: Optional[Decimal] = Field(None, ge=0, description="Working capital impact")
    collection_notes: Optional[str] = Field(None, description="Collection notes")

    @field_validator('due_date')
    @classmethod
    def due_date_must_be_after_invoice_date(cls, v, info):
        values = info.data if hasattr(info, 'data') else {}
        if 'invoice_date' in values and v <= values['invoice_date']:
            raise ValueError('Due date must be after invoice date')
        return v

    @model_validator(mode='before')
    @classmethod
    def validate_amounts(cls, values):
        """Validate that total equals subtotal + tax."""
        if all(k in values for k in ['subtotal', 'tax_amount', 'total_amount']):
            expected_total = values['subtotal'] + values['tax_amount']
            tolerance = Decimal('0.01')  # 1 cent tolerance
            if abs(values['total_amount'] - expected_total) > tolerance:
                raise ValueError(f'Total amount must equal subtotal + tax amount ({expected_total})')
        return values

    @field_validator('early_payment_discount_days')
    @classmethod
    def validate_discount_period(cls, v, info):
        values = info.data if hasattr(info, 'data') else {}
        if v is not None and 'due_date' in values and 'invoice_date' in values:
            discount_deadline = values['invoice_date'] + timedelta(days=v)
            if discount_deadline > values['due_date']:
                raise ValueError('Early payment discount deadline cannot be after due date')
        return v


class ARInvoiceCreate(ARInvoiceBase):
    """Schema for creating a new AR invoice."""
    customer_id: UUID = Field(..., description="Customer ID")


class ARInvoiceUpdate(BaseModel):
    """Schema for updating an existing AR invoice."""
    invoice_number: Optional[str] = Field(None, min_length=1, max_length=100)
    due_date: Optional[datetime] = None
    early_payment_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    early_payment_discount_days: Optional[int] = Field(None, ge=0)
    expected_payment_date: Optional[datetime] = None
    working_capital_impact: Optional[Decimal] = Field(None, ge=0)
    collection_notes: Optional[str] = None
    collection_priority: Optional[CollectionPriority] = None


class ARInvoiceResponse(ARInvoiceBase):
    """Schema for AR invoice response data."""
    id: UUID
    customer_id: UUID
    status: PaymentStatus
    collection_priority: CollectionPriority
    outstanding_amount: Decimal
    paid_amount: Optional[Decimal]
    paid_at: Optional[datetime]
    last_collection_attempt: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    days_overdue: Optional[int] = Field(None, description="Days overdue")
    is_overdue: bool = Field(False, description="Whether invoice is overdue")
    early_payment_discount_available: bool = Field(False, description="Whether early payment discount is available")
    early_payment_discount_amount: Optional[Decimal] = Field(None, description="Early payment discount amount")

    model_config = ConfigDict(from_attributes=True)


class PaymentApply(BaseModel):
    """Schema for applying payment to an invoice."""
    payment_amount: Decimal = Field(..., gt=0, description="Payment amount")
    payment_date: Optional[datetime] = Field(None, description="Payment date (defaults to now)")
    payment_notes: Optional[str] = Field(None, description="Payment notes")


class WorkingCapitalSummary(BaseModel):
    """Schema for working capital summary."""
    total_outstanding: Decimal
    invoice_count: int
    overdue_count: int
    overdue_percentage: float
    average_days_outstanding: float
    working_capital_impact: Decimal


class CollectionRecommendation(BaseModel):
    """Schema for collection recommendation."""
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    days_overdue: int
    amount: Decimal
    recommendation: str
    priority: str


class CashFlowForecast(BaseModel):
    """Schema for cash flow forecast."""
    period_start: date
    period_end: date
    expected_amount: Decimal
    invoice_count: int


class EarlyPaymentDiscountOpportunity(BaseModel):
    """Schema for early payment discount opportunity."""
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    total_amount: Decimal
    discount_amount: Decimal
    discount_percent: Decimal
    deadline: datetime
    days_until_deadline: int


class WorkingCapitalOptimizationScore(BaseModel):
    """Schema for working capital optimization score."""
    overall_score: Decimal = Field(..., ge=0, le=100)
    collection_efficiency_score: Decimal = Field(..., ge=0, le=100)
    discount_optimization_score: Decimal = Field(..., ge=0, le=100)
    recommendations: List[str]
    metrics: dict
    discount_opportunities: int
    potential_savings: Decimal


class CollectionEfficiencyMetrics(BaseModel):
    """Schema for collection efficiency metrics."""
    average_days_to_pay: float
    collection_rate: Decimal
    overdue_percentage: Decimal
    total_invoices: int
    paid_invoices: int
    overdue_invoices: int


class CustomerOutstandingInvoices(BaseModel):
    """Schema for customer outstanding invoices summary."""
    customer_id: UUID
    customer_name: str
    total_outstanding: Decimal
    invoice_count: int
    overdue_invoices: List[ARInvoiceResponse]


class BulkPaymentApplication(BaseModel):
    """Schema for bulk payment application."""
    payments: List[PaymentApply] = Field(..., description="List of payments to apply")
    apply_date: Optional[datetime] = Field(None, description="Date to apply payments")
    notes: Optional[str] = Field(None, description="Bulk payment notes")


class PaymentApplicationResult(BaseModel):
    """Schema for payment application result."""
    payment_id: UUID
    invoice_id: UUID
    invoice_number: str
    amount_applied: Decimal
    success: bool
    error_message: Optional[str] = None
    new_outstanding_amount: Optional[Decimal] = None
    new_status: Optional[PaymentStatus] = None


class BulkPaymentApplicationResult(BaseModel):
    """Schema for bulk payment application result."""
    total_payments: int
    successful_payments: int
    failed_payments: int
    total_amount_applied: Decimal
    results: List[PaymentApplicationResult]