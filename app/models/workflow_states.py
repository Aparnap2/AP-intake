"""
Extended workflow state definitions for AP and AR invoice processing.

This module defines state management for both Accounts Payable (AP) and
Accounts Receivable (AR) workflows, with proper typing, validation,
and state persistence capabilities.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, TypedDict, Union

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, DateTime, JSON, Float
from sqlalchemy.ext.declarative import declarative_base

from app.models.ar_invoice import PaymentStatus, CollectionPriority

Base = declarative_base()


class InvoiceType(str, enum.Enum):
    """Invoice type enumeration."""
    AP = "ap"  # Accounts Payable (vendor invoices)
    AR = "ar"  # Accounts Receivable (customer invoices)


class WorkflowStep(str, enum.Enum):
    """Workflow step enumeration for both AP and AR workflows."""
    INITIALIZED = "initialized"
    RECEIVED = "received"
    PARSED = "parsed"
    ENHANCED = "enhanced"
    VALIDATED = "validated"
    TRIAGED = "triaged"
    EXPORT_STAGED = "staged"
    COMPLETED = "completed"
    FAILED = "failed"

    # AR-specific steps
    CUSTOMER_VALIDATED = "customer_validated"
    PAYMENT_TERMS_PROCESSED = "payment_terms_processed"
    COLLECTION_PROCESSED = "collection_processed"
    WORKING_CAPITAL_OPTIMIZED = "working_capital_optimized"
    CUSTOMER_COMMUNICATED = "customer_communicated"


class WorkflowStatus(str, enum.Enum):
    """Workflow status enumeration."""
    PROCESSING = "processing"
    READY = "ready"
    EXCEPTION = "exception"
    HUMAN_REVIEW = "human_review"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseInvoiceState(TypedDict):
    """Base invoice state shared between AP and AR workflows."""

    # Core metadata
    invoice_id: str
    file_path: str
    file_hash: str
    workflow_id: str
    created_at: str
    updated_at: str

    # Workflow management
    current_step: str
    status: str
    previous_step: Optional[str]
    retry_count: int
    max_retries: int

    # Processing results
    extraction_result: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    confidence_score: Optional[float]

    # Exception management
    exceptions: List[Dict[str, Any]]
    exception_ids: List[str]
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]

    # Human review
    requires_human_review: bool
    human_review_reason: Optional[str]
    human_review_data: Optional[Dict[str, Any]]

    # Processing metadata
    processing_history: List[Dict[str, Any]]
    step_timings: Dict[str, Any]
    performance_metrics: Dict[str, Any]

    # Export data
    export_payload: Optional[Dict[str, Any]]
    export_format: str
    export_ready: bool


class APInvoiceState(BaseInvoiceState):
    """AP (Accounts Payable) invoice state."""

    # AP-specific fields
    invoice_type: str  # Will be "ap"
    vendor_id: Optional[str]
    vendor_data: Optional[Dict[str, Any]]
    purchase_order_number: Optional[str]

    # AP processing results
    vendor_validation_result: Optional[Dict[str, Any]]
    matching_result: Optional[Dict[str, Any]]
    approval_result: Optional[Dict[str, Any]]


class ARInvoiceState(BaseInvoiceState):
    """AR (Accounts Receivable) invoice state."""

    # AR-specific fields
    invoice_type: str  # Will be "ar"
    customer_id: Optional[str]
    customer_data: Optional[Dict[str, Any]]
    payment_terms: Optional[str]
    due_date: Optional[str]
    collection_priority: str
    working_capital_score: float
    early_payment_discount: Optional[float]

    # AR processing results
    customer_validation_result: Optional[Dict[str, Any]]
    payment_terms_result: Optional[Dict[str, Any]]
    collection_result: Optional[Dict[str, Any]]
    working_capital_result: Optional[Dict[str, Any]]
    communication_result: Optional[Dict[str, Any]]

    # AR workflow step tracking
    ar_step: str
    ar_processing_history: List[Dict[str, Any]]


class WorkflowStatePersistence(Base):
    """Database model for workflow state persistence."""

    __tablename__ = "workflow_states"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Workflow identifiers
    workflow_id = Column(String(36), nullable=False, index=True)
    invoice_id = Column(String(36), nullable=False, index=True)
    invoice_type = Column(String(10), nullable=False, index=True)  # "ap" or "ar"

    # Current state
    current_step = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, index=True)

    # State data (JSON)
    state_data = Column(JSON, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Performance metrics
    total_processing_time_ms = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Error tracking
    error_count = Column(Float, nullable=False, default=0)
    last_error = Column(String(500), nullable=True)

    # Indexes for performance
    __table_args__ = (
        {"schema": None}
    )


class ARWorkflowStateModel(BaseModel):
    """
    Pydantic model for AR workflow state with validation.

    This provides structured validation and serialization for AR workflow states.
    """

    # Core metadata
    invoice_id: str = Field(..., description="Unique invoice identifier")
    file_path: str = Field(..., description="Path to invoice file")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of file")
    workflow_id: str = Field(..., description="Unique workflow identifier")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    # AR-specific fields
    invoice_type: str = Field(default="ar", description="Invoice type (always 'ar' for this model)")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    customer_data: Optional[Dict[str, Any]] = Field(None, description="Customer information")
    payment_terms: Optional[str] = Field(default="NET30", description="Payment terms")
    due_date: Optional[str] = Field(None, description="Due date in ISO format")
    collection_priority: str = Field(default=CollectionPriority.MEDIUM.value, description="Collection priority")
    working_capital_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Working capital optimization score")
    early_payment_discount: Optional[float] = Field(None, ge=0.0, le=100.0, description="Early payment discount percentage")

    # Workflow state
    current_step: str = Field(default="initialized", description="Current workflow step")
    status: str = Field(default=WorkflowStatus.PROCESSING.value, description="Current workflow status")
    previous_step: Optional[str] = Field(None, description="Previous workflow step")
    ar_step: str = Field(default="initialized", description="AR-specific current step")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum allowed retries")

    # Processing results
    extraction_result: Optional[Dict[str, Any]] = Field(None, description="Document extraction results")
    validation_result: Optional[Dict[str, Any]] = Field(None, description="Validation results")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Overall confidence score")

    # AR processing results
    customer_validation_result: Optional[Dict[str, Any]] = Field(None, description="Customer validation results")
    payment_terms_result: Optional[Dict[str, Any]] = Field(None, description="Payment terms processing results")
    collection_result: Optional[Dict[str, Any]] = Field(None, description="Collection management results")
    working_capital_result: Optional[Dict[str, Any]] = Field(None, description="Working capital optimization results")
    communication_result: Optional[Dict[str, Any]] = Field(None, description="Customer communication results")

    # Exception and error handling
    exceptions: List[Dict[str, Any]] = Field(default_factory=list, description="List of exceptions")
    exception_ids: List[str] = Field(default_factory=list, description="List of exception IDs")
    error_message: Optional[str] = Field(None, description="Current error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")

    # Human review
    requires_human_review: bool = Field(default=False, description="Whether human review is required")
    human_review_reason: Optional[str] = Field(None, description="Reason for human review")
    human_review_data: Optional[Dict[str, Any]] = Field(None, description="Human review context data")

    # Processing metadata
    processing_history: List[Dict[str, Any]] = Field(default_factory=list, description="Processing history")
    ar_processing_history: List[Dict[str, Any]] = Field(default_factory=list, description="AR-specific processing history")
    step_timings: Dict[str, Any] = Field(default_factory=dict, description="Step timing information")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")

    # Export data
    export_payload: Optional[Dict[str, Any]] = Field(None, description="Export payload data")
    export_format: str = Field(default="json", description="Export format")
    export_ready: bool = Field(default=False, description="Whether export is ready")

    @validator('invoice_type')
    def validate_invoice_type(cls, v):
        """Validate that invoice type is 'ar'."""
        if v != InvoiceType.AR.value:
            raise ValueError(f"invoice_type must be '{InvoiceType.AR.value}' for ARWorkflowStateModel")
        return v

    @validator('collection_priority')
    def validate_collection_priority(cls, v):
        """Validate collection priority."""
        try:
            return CollectionPriority(v).value
        except ValueError:
            raise ValueError(f"Invalid collection priority: {v}. Must be one of {[p.value for p in CollectionPriority]}")

    @validator('status')
    def validate_status(cls, v):
        """Validate workflow status."""
        try:
            return WorkflowStatus(v).value
        except ValueError:
            raise ValueError(f"Invalid status: {v}. Must be one of {[s.value for s in WorkflowStatus]}")

    @validator('due_date')
    def validate_due_date(cls, v):
        """Validate due date format."""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid due date format: {v}. Must be ISO format")
        return v

    @validator('created_at', 'updated_at')
    def validate_timestamps(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}. Must be ISO format")
        return v

    def update_step(self, step: str, status: str = None, error_message: str = None):
        """Update the current step and optionally status."""
        self.previous_step = self.current_step
        self.current_step = step
        self.ar_step = step

        if status:
            self.status = status

        if error_message:
            self.error_message = error_message

        self.updated_at = datetime.utcnow().isoformat()

    def add_processing_history_entry(
        self, step: str, status: str, metadata: Dict[str, Any] = None
    ):
        """Add an entry to the processing history."""
        entry = {
            "step": step,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self.processing_history.append(entry)

        # Also add to AR-specific history
        if step.startswith("customer_") or step.startswith("payment_") or step.startswith("collection_") or step.startswith("working_capital_") or step.startswith("customer_communicat"):
            self.ar_processing_history.append(entry)

        self.updated_at = datetime.utcnow().isoformat()

    def add_exception(self, exception_id: str, exception_data: Dict[str, Any]):
        """Add an exception to the state."""
        self.exceptions.append(exception_data)
        self.exception_ids.append(exception_id)
        self.updated_at = datetime.utcnow().isoformat()

    def set_human_review_required(self, reason: str, context_data: Dict[str, Any] = None):
        """Mark workflow as requiring human review."""
        self.requires_human_review = True
        self.human_review_reason = reason
        self.human_review_data = context_data
        self.status = WorkflowStatus.HUMAN_REVIEW.value
        self.updated_at = datetime.utcnow().isoformat()

    def calculate_processing_metrics(self) -> Dict[str, Any]:
        """Calculate processing metrics from history."""
        if not self.processing_history:
            return {}

        # Calculate total processing time
        total_time_ms = sum(
            entry.get("metadata", {}).get("duration_ms", 0)
            for entry in self.processing_history
        )

        # Calculate success rate (no errors = 100%)
        error_count = len([
            entry for entry in self.processing_history
            if entry.get("status") == "error" or entry.get("status") == "failed"
        ])

        success_rate = max(0, 100 - (error_count / len(self.processing_history) * 100))

        # Get completed steps
        completed_steps = [
            entry["step"] for entry in self.processing_history
            if entry.get("status") in ["completed", "skipped"]
        ]

        return {
            "total_processing_time_ms": total_time_ms,
            "total_steps": len(self.processing_history),
            "completed_steps": len(completed_steps),
            "success_rate": round(success_rate, 2),
            "error_count": error_count,
            "average_step_time_ms": total_time_ms // max(len(self.processing_history), 1),
            "current_confidence": self.confidence_score or 0.0,
            "working_capital_score": self.working_capital_score
        }

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "allow"  # Allow additional fields for flexibility


class APWorkflowStateModel(BaseModel):
    """
    Pydantic model for AP workflow state with validation.

    This provides structured validation and serialization for AP workflow states.
    """

    # Core metadata
    invoice_id: str = Field(..., description="Unique invoice identifier")
    file_path: str = Field(..., description="Path to invoice file")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of file")
    workflow_id: str = Field(..., description="Unique workflow identifier")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    # AP-specific fields
    invoice_type: str = Field(default="ap", description="Invoice type (always 'ap' for this model)")
    vendor_id: Optional[str] = Field(None, description="Vendor identifier")
    vendor_data: Optional[Dict[str, Any]] = Field(None, description="Vendor information")
    purchase_order_number: Optional[str] = Field(None, description="Purchase order number")

    # Workflow state
    current_step: str = Field(default="initialized", description="Current workflow step")
    status: str = Field(default=WorkflowStatus.PROCESSING.value, description="Current workflow status")
    previous_step: Optional[str] = Field(None, description="Previous workflow step")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum allowed retries")

    # Processing results
    extraction_result: Optional[Dict[str, Any]] = Field(None, description="Document extraction results")
    validation_result: Optional[Dict[str, Any]] = Field(None, description="Validation results")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Overall confidence score")

    # AP processing results
    vendor_validation_result: Optional[Dict[str, Any]] = Field(None, description="Vendor validation results")
    matching_result: Optional[Dict[str, Any]] = Field(None, description="PO matching results")
    approval_result: Optional[Dict[str, Any]] = Field(None, description="Approval workflow results")

    # Exception and error handling
    exceptions: List[Dict[str, Any]] = Field(default_factory=list, description="List of exceptions")
    exception_ids: List[str] = Field(default_factory=list, description="List of exception IDs")
    error_message: Optional[str] = Field(None, description="Current error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")

    # Human review
    requires_human_review: bool = Field(default=False, description="Whether human review is required")
    human_review_reason: Optional[str] = Field(None, description="Reason for human review")
    human_review_data: Optional[Dict[str, Any]] = Field(None, description="Human review context data")

    # Processing metadata
    processing_history: List[Dict[str, Any]] = Field(default_factory=list, description="Processing history")
    step_timings: Dict[str, Any] = Field(default_factory=dict, description="Step timing information")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")

    # Export data
    export_payload: Optional[Dict[str, Any]] = Field(None, description="Export payload data")
    export_format: str = Field(default="json", description="Export format")
    export_ready: bool = Field(default=False, description="Whether export is ready")

    @validator('invoice_type')
    def validate_invoice_type(cls, v):
        """Validate that invoice type is 'ap'."""
        if v != InvoiceType.AP.value:
            raise ValueError(f"invoice_type must be '{InvoiceType.AP.value}' for APWorkflowStateModel")
        return v

    @validator('status')
    def validate_status(cls, v):
        """Validate workflow status."""
        try:
            return WorkflowStatus(v).value
        except ValueError:
            raise ValueError(f"Invalid status: {v}. Must be one of {[s.value for s in WorkflowStatus]}")

    @validator('created_at', 'updated_at')
    def validate_timestamps(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}. Must be ISO format")
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "allow"  # Allow additional fields for flexibility


# State factory functions
def create_ar_workflow_state(
    invoice_id: str,
    file_path: str,
    customer_id: Optional[str] = None,
    **kwargs
) -> ARWorkflowStateModel:
    """Create a new AR workflow state."""
    return ARWorkflowStateModel(
        invoice_id=invoice_id,
        file_path=file_path,
        workflow_id=str(uuid.uuid4()),
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        customer_id=customer_id,
        **kwargs
    )


def create_ap_workflow_state(
    invoice_id: str,
    file_path: str,
    vendor_id: Optional[str] = None,
    **kwargs
) -> APWorkflowStateModel:
    """Create a new AP workflow state."""
    return APWorkflowStateModel(
        invoice_id=invoice_id,
        file_path=file_path,
        workflow_id=str(uuid.uuid4()),
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        vendor_id=vendor_id,
        **kwargs
    )


# State validation functions
def validate_workflow_state(state: Union[ARWorkflowStateModel, APWorkflowStateModel]) -> bool:
    """Validate a workflow state model."""
    try:
        # Pydantic validation occurs automatically on model creation
        # Additional business logic validation can be added here

        # Check that required timestamps are valid
        if isinstance(state, (ARWorkflowStateModel, APWorkflowStateModel)):
            created_at = datetime.fromisoformat(state.created_at.replace('Z', '+00:00'))
            updated_at = datetime.fromisoformat(state.updated_at.replace('Z', '+00:00'))

            if updated_at < created_at:
                return False

        return True
    except Exception:
        return False


def merge_workflow_states(
    base_state: Union[ARWorkflowStateModel, APWorkflowStateModel],
    update_data: Dict[str, Any]
) -> Union[ARWorkflowStateModel, APWorkflowStateModel]:
    """Merge update data into a workflow state."""
    # Create a copy of the state to avoid mutation
    state_dict = base_state.dict()

    # Update with new data
    state_dict.update(update_data)
    state_dict['updated_at'] = datetime.utcnow().isoformat()

    # Recreate the model with updated data
    if isinstance(base_state, ARWorkflowStateModel):
        return ARWorkflowStateModel(**state_dict)
    elif isinstance(base_state, APWorkflowStateModel):
        return APWorkflowStateModel(**state_dict)
    else:
        raise ValueError(f"Unsupported state type: {type(base_state)}")


# State serialization utilities
def serialize_workflow_state(state: Union[ARWorkflowStateModel, APWorkflowStateModel]) -> Dict[str, Any]:
    """Serialize a workflow state to a dictionary."""
    return state.dict()


def deserialize_workflow_state(
    state_data: Dict[str, Any], invoice_type: str
) -> Union[ARWorkflowStateModel, APWorkflowStateModel]:
    """Deserialize a workflow state from a dictionary."""
    if invoice_type == InvoiceType.AR.value:
        return ARWorkflowStateModel(**state_data)
    elif invoice_type == InvoiceType.AP.value:
        return APWorkflowStateModel(**state_data)
    else:
        raise ValueError(f"Unknown invoice type: {invoice_type}")


# Workflow state transition validation
def validate_state_transition(
    current_step: str, next_step: str, invoice_type: str
) -> bool:
    """Validate that a workflow state transition is allowed."""
    # Define valid transitions for AR workflow
    ar_transitions = {
        WorkflowStep.INITIALIZED.value: [
            WorkflowStep.RECEIVED.value,
            "customer_validation"
        ],
        "customer_validation": [
            WorkflowStep.VALIDATED.value,
            "payment_terms_processed",
            WorkflowStep.FAILED.value
        ],
        "payment_terms_processed": [
            "collection_processed",
            WorkflowStep.VALIDATED.value,
            WorkflowStep.FAILED.value
        ],
        "collection_processed": [
            "working_capital_optimized",
            WorkflowStep.TRIAGED.value,
            WorkflowStep.FAILED.value
        ],
        "working_capital_optimized": [
            "customer_communicated",
            WorkflowStep.TRIAGED.value,
            WorkflowStep.FAILED.value
        ],
        "customer_communicated": [
            WorkflowStep.EXPORT_STAGED.value,
            WorkflowStep.TRIAGED.value,
            WorkflowStep.COMPLETED.value
        ],
        WorkflowStep.VALIDATED.value: [
            WorkflowStep.TRIAGED.value,
            "payment_terms_processed",
            "collection_processed"
        ],
        WorkflowStep.TRIAGED.value: [
            WorkflowStep.EXPORT_STAGED.value,
            WorkflowStep.HUMAN_REVIEW.value,
            WorkflowStep.ESCALATED.value
        ],
        WorkflowStep.EXPORT_STAGED.value: [
            WorkflowStep.COMPLETED.value
        ]
    }

    # Define valid transitions for AP workflow
    ap_transitions = {
        WorkflowStep.INITIALIZED.value: [WorkflowStep.RECEIVED.value],
        WorkflowStep.RECEIVED.value: [WorkflowStep.PARSED.value],
        WorkflowStep.PARSED.value: [WorkflowStep.ENHANCED.value, WorkflowStep.VALIDATED.value],
        WorkflowStep.ENHANCED.value: [WorkflowStep.VALIDATED.value],
        WorkflowStep.VALIDATED.value: [WorkflowStep.TRIAGED.value],
        WorkflowStep.TRIAGED.value: [
            WorkflowStep.EXPORT_STAGED.value,
            WorkflowStep.HUMAN_REVIEW.value,
            WorkflowStep.ESCALATED.value
        ],
        WorkflowStep.EXPORT_STAGED.value: [WorkflowStep.COMPLETED.value]
    }

    # Get appropriate transitions
    transitions = ar_transitions if invoice_type == InvoiceType.AR.value else ap_transitions

    # Check if transition is valid
    allowed_next_steps = transitions.get(current_step, [])
    return next_step in allowed_next_steps