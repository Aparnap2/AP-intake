"""
Approval-related Pydantic schemas for request/response validation.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ApprovalStatus(str, Enum):
    """Approval status options."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalAction(str, Enum):
    """Approval action types."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"
    ESCALATE = "escalate"


class ApprovalRole(str, Enum):
    """Approval role types."""
    AP_CLERK = "ap_clerk"
    AP_MANAGER = "ap_manager"
    CONTROLLER = "controller"
    CFO = "cfo"
    FINANCE_DIRECTOR = "finance_director"
    AUDITOR = "auditor"
    SYSTEM_ADMIN = "system_admin"


class WorkflowType(str, Enum):
    """Workflow types."""
    INVOICE_EXPORT = "invoice_export"
    BULK_EXPORT = "bulk_export"
    PAYMENT_APPROVAL = "payment_approval"
    VENDOR_APPROVAL = "vendor_approval"
    EXCEPTION_APPROVAL = "exception_approval"
    SYSTEM_CONFIG = "system_config"


class ApprovalStepConfig(BaseModel):
    """Configuration for an approval step."""
    step_name: str = Field(..., description="Name of the approval step")
    approval_role: ApprovalRole = Field(..., description="Role required for this step")
    required_approvers: int = Field(1, ge=1, description="Number of approvers required")
    is_parallel: bool = Field(False, description="Whether approvals are parallel or sequential")
    timeout_hours: Optional[int] = Field(None, ge=1, description="Timeout in hours for this step")
    auto_approve_conditions: Optional[Dict[str, Any]] = Field(None, description="Conditions for auto-approval")
    reject_conditions: Optional[Dict[str, Any]] = Field(None, description="Conditions for auto-rejection")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Additional step configuration")


class ApprovalWorkflowCreate(BaseModel):
    """Schema for creating approval workflows."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    workflow_type: WorkflowType
    steps: List[ApprovalStepConfig] = Field(..., min_items=1)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(True)


class ApprovalWorkflowUpdate(BaseModel):
    """Schema for updating approval workflows."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    steps: Optional[List[ApprovalStepConfig]] = None
    configuration: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ApprovalWorkflowResponse(BaseModel):
    """Response schema for approval workflows."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    workflow_type: WorkflowType
    configuration: Dict[str, Any]
    is_active: bool
    default_timeout_hours: int
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestCreate(BaseModel):
    """Schema for creating approval requests."""
    workflow_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: uuid.UUID
    priority: int = Field(5, ge=1, le=10)
    context_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ApprovalRequestUpdate(BaseModel):
    """Schema for updating approval requests."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    priority: Optional[int] = Field(None, ge=1, le=10)
    context_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ApprovalDecisionCreate(BaseModel):
    """Schema for creating approval decisions."""
    approval_request_id: uuid.UUID
    action: ApprovalAction
    comments: Optional[str] = Field(None, max_length=2000)
    decision_data: Optional[Dict[str, Any]] = None

    @field_validator('comments')
    @classmethod
    def validate_comments(cls, v, info):
        """Validate comments based on action."""
        values = info.data if hasattr(info, 'data') else {}
        action = values.get('action')
        if action == ApprovalAction.REJECT and not v:
            raise ValueError("Comments are required for rejection")
        if action == ApprovalAction.REQUEST_CHANGES and not v:
            raise ValueError("Comments are required when requesting changes")
        return v


class ApprovalDecisionResponse(BaseModel):
    """Response schema for approval decisions."""
    id: uuid.UUID
    approval_request_id: uuid.UUID
    step_id: uuid.UUID
    approver_id: str
    action: ApprovalAction
    comments: Optional[str]
    decision_data: Optional[Dict[str, Any]]
    decision_time: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalStepResponse(BaseModel):
    """Response schema for approval steps."""
    id: uuid.UUID
    workflow_id: uuid.UUID
    step_name: str
    step_order: int
    approval_role: ApprovalRole
    required_approvers: int
    is_parallel: bool
    timeout_hours: Optional[int]
    configuration: Dict[str, Any]
    description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestResponse(BaseModel):
    """Response schema for approval requests."""
    id: uuid.UUID
    workflow_id: uuid.UUID
    title: str
    description: Optional[str]
    entity_type: str
    entity_id: uuid.UUID
    priority: int
    status: ApprovalStatus
    current_step: int
    requested_by: str
    expires_at: Optional[datetime]
    completed_at: Optional[datetime]
    context_data: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApproverAssignmentResponse(BaseModel):
    """Response schema for approver assignments."""
    id: uuid.UUID
    approval_request_id: uuid.UUID
    step_id: uuid.UUID
    user_id: str
    status: str
    delegated_to: Optional[str]
    assigned_at: datetime
    acknowledged_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ApprovalAuditLogResponse(BaseModel):
    """Response schema for approval audit logs."""
    id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    approval_request_id: Optional[uuid.UUID]
    event_type: str
    event_data: Dict[str, Any]
    user_id: Optional[str]
    user_agent: Optional[str]
    ip_address: Optional[str]
    session_id: Optional[str]
    correlation_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalTemplateCreate(BaseModel):
    """Schema for creating approval templates."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., min_length=1, max_length=100)
    workflow_config: Dict[str, Any] = Field(...)
    steps_config: List[ApprovalStepConfig] = Field(..., min_items=1)
    is_active: bool = Field(True)
    is_public: bool = Field(False)


class ApprovalTemplateResponse(BaseModel):
    """Response schema for approval templates."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    category: str
    workflow_config: Dict[str, Any]
    steps_config: List[ApprovalStepConfig]
    is_active: bool
    is_public: bool
    usage_count: int
    last_used_at: Optional[datetime]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalNotificationResponse(BaseModel):
    """Response schema for approval notifications."""
    id: uuid.UUID
    approval_request_id: uuid.UUID
    user_id: str
    notification_type: str
    subject: str
    message: str
    delivery_method: str
    recipient_address: str
    status: str
    sent_at: Optional[datetime]
    read_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalStatusResponse(BaseModel):
    """Schema for detailed approval status."""
    request: ApprovalRequestResponse
    workflow: ApprovalWorkflowResponse
    steps: List[ApprovalStepResponse]
    step_decisions: Dict[str, Any]
    current_step: Optional[ApprovalStepResponse]
    progress: Dict[str, Any]


class ApprovalProgressResponse(BaseModel):
    """Schema for approval progress tracking."""
    approval_request_id: uuid.UUID
    total_steps: int
    completed_steps: int
    current_step: int
    progress_percentage: float
    status: str
    estimated_completion: Optional[datetime]


class BulkApprovalRequest(BaseModel):
    """Schema for bulk approval requests."""
    approval_request_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=50)
    action: ApprovalAction
    comments: Optional[str] = Field(None, max_length=2000)
    decision_data: Optional[Dict[str, Any]] = None


class BulkApprovalResponse(BaseModel):
    """Response schema for bulk approval operations."""
    successful_approvals: List[uuid.UUID]
    failed_approvals: List[Dict[str, Any]]
    total_processed: int
    success_count: int
    failure_count: int


class ApprovalStatisticsResponse(BaseModel):
    """Schema for approval statistics."""
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    expired_requests: int
    average_approval_time_hours: float
    approval_rate_percentage: float
    requests_by_type: Dict[str, int]
    requests_by_priority: Dict[str, int]


class ApprovalFilter(BaseModel):
    """Schema for filtering approval requests."""
    status: Optional[List[ApprovalStatus]] = None
    entity_type: Optional[str] = None
    priority: Optional[List[int]] = None
    requested_by: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    workflow_type: Optional[WorkflowType] = None


class StagedExportCreate(BaseModel):
    """Schema for creating staged exports."""
    invoice_id: uuid.UUID
    export_format: str = Field(..., pattern="^(csv|json|xml|xlsx)$")
    export_data: Dict[str, Any]
    workflow_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None


class StagedExportResponse(BaseModel):
    """Response schema for staged exports."""
    id: uuid.UUID
    invoice_id: uuid.UUID
    export_format: str
    status: str
    destination: str
    export_job_id: Optional[str]
    file_name: Optional[str]
    file_size: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExportApprovalRequest(BaseModel):
    """Schema for export approval requests."""
    staged_export_id: uuid.UUID
    workflow_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: int = Field(5, ge=1, le=10)
    context_data: Optional[Dict[str, Any]] = None


class DiffComparisonResponse(BaseModel):
    """Response schema for diff comparisons."""
    comparison_id: uuid.UUID
    original_data: Dict[str, Any]
    modified_data: Dict[str, Any]
    changes: List[Dict[str, Any]]
    summary: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowStepAction(BaseModel):
    """Schema for workflow step actions."""
    step_id: uuid.UUID
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionRequest(BaseModel):
    """Schema for workflow execution requests."""
    workflow_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    initiator_context: Dict[str, Any]
    execution_parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResponse(BaseModel):
    """Response schema for workflow execution."""
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    current_step: Optional[int]
    completed_steps: List[int]
    error_message: Optional[str]
    execution_data: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)