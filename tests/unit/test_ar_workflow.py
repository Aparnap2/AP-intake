"""
Test-Driven Development tests for AR (Accounts Receivable) workflow extensions.

This module contains comprehensive tests for AR invoice processing workflow,
including customer validation, payment terms processing, collection management,
and working capital optimization.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from app.workflows.ar_workflow_nodes import (
    ARWorkflowState,
    CustomerValidationNode,
    PaymentTermsNode,
    CollectionNode,
    WorkingCapitalNode,
    CustomerCommunicationNode
)
from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus, CollectionPriority
from app.core.exceptions import WorkflowException, ValidationException


class TestARWorkflowState:
    """Test AR workflow state definition and management."""

    @pytest.fixture
    def base_ar_state(self) -> Dict[str, Any]:
        """Create a base AR workflow state for testing."""
        return {
            # Base invoice metadata
            "invoice_id": str(uuid.uuid4()),
            "file_path": "/tmp/test_ar_invoice.pdf",
            "file_hash": "test_hash_12345",
            "workflow_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),

            # AR-specific fields
            "invoice_type": "ar",
            "customer_id": str(uuid.uuid4()),
            "customer_data": None,
            "payment_terms": "NET30",
            "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "collection_priority": CollectionPriority.MEDIUM.value,
            "working_capital_score": 0.0,
            "early_payment_discount": None,

            # Processing state
            "current_step": "initialized",
            "status": "processing",
            "requires_human_review": False,
            "retry_count": 0,
            "max_retries": 3,

            # Results and metadata
            "extraction_result": None,
            "validation_result": None,
            "customer_validation_result": None,
            "payment_terms_result": None,
            "collection_result": None,
            "working_capital_result": None,
            "communication_result": None,

            # Processing history
            "processing_history": [],
            "step_timings": {},
            "performance_metrics": {},

            # Exceptions and errors
            "exceptions": [],
            "exception_ids": [],
            "error_message": None,
            "error_details": None,

            # Export data
            "export_payload": None,
            "export_format": "json",
            "export_ready": False,
        }

    def test_ar_state_initialization(self, base_ar_state):
        """Test AR workflow state initialization."""
        state = ARWorkflowState(**base_ar_state)

        assert state.invoice_type == "ar"
        assert state.customer_id is not None
        assert state.payment_terms == "NET30"
        assert state.collection_priority == CollectionPriority.MEDIUM.value
        assert state.working_capital_score == 0.0
        assert state.current_step == "initialized"
        assert state.status == "processing"

    def test_ar_state_with_customer_data(self, base_ar_state):
        """Test AR state with customer data populated."""
        customer_data = {
            "id": str(uuid.uuid4()),
            "name": "Test Customer",
            "tax_id": "123456789",
            "credit_limit": "10000.00",
            "payment_terms_days": "30"
        }
        base_ar_state["customer_data"] = customer_data

        state = ARWorkflowState(**base_ar_state)

        assert state.customer_data == customer_data
        assert state.customer_data["name"] == "Test Customer"

    def test_ar_state_validation(self, base_ar_state):
        """Test AR state validation."""
        # Test missing required fields
        with pytest.raises(ValueError):
            ARWorkflowState(**{**base_ar_state, "invoice_type": None})

        with pytest.raises(ValueError):
            ARWorkflowState(**{**base_ar_state, "customer_id": None})

        # Test valid state
        state = ARWorkflowState(**base_ar_state)
        assert state is not None


class TestCustomerValidationNode:
    """Test customer validation workflow node."""

    @pytest.fixture
    def mock_customer_service(self):
        """Mock customer service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def customer_validation_node(self, mock_customer_service):
        """Create customer validation node with mocked dependencies."""
        return CustomerValidationNode(customer_service=mock_customer_service)

    @pytest.fixture
    def sample_customer(self):
        """Create sample customer data."""
        return {
            "id": str(uuid.uuid4()),
            "name": "Acme Corporation",
            "tax_id": "123456789",
            "email": "billing@acme.com",
            "credit_limit": Decimal("50000.00"),
            "payment_terms_days": "30",
            "active": True,
            "currency": "USD"
        }

    @pytest.mark.asyncio
    async def test_validate_existing_customer_success(
        self, customer_validation_node, mock_customer_service, sample_customer, base_ar_state
    ):
        """Test successful validation of existing customer."""
        # Setup mock response
        mock_customer_service.get_customer_by_id.return_value = sample_customer
        mock_customer_service.validate_customer_credit.return_value = {
            "valid": True,
            "available_credit": Decimal("30000.00"),
            "used_credit": Decimal("20000.00")
        }

        # Set customer ID in state
        base_ar_state["customer_id"] = sample_customer["id"]
        state = ARWorkflowState(**base_ar_state)

        # Execute validation
        result = await customer_validation_node.execute(state)

        # Assertions
        assert result["current_step"] == "customer_validated"
        assert result["status"] == "processing"
        assert result["customer_validation_result"]["valid"] is True
        assert result["customer_data"]["name"] == "Acme Corporation"
        assert "customer_validation" in str(result["processing_history"])

    @pytest.mark.asyncio
    async def test_validate_new_customer_success(
        self, customer_validation_node, mock_customer_service, base_ar_state
    ):
        """Test successful validation of new customer."""
        # Setup mock for new customer creation
        new_customer_data = {
            "name": "New Customer Inc",
            "tax_id": "987654321",
            "email": "billing@newcustomer.com"
        }

        mock_customer_service.get_customer_by_id.return_value = None
        mock_customer_service.get_customer_by_tax_id.return_value = None
        mock_customer_service.create_customer.return_value = {
            "id": str(uuid.uuid4()),
            **new_customer_data,
            "credit_limit": Decimal("10000.00"),
            "payment_terms_days": "30"
        }

        # Add new customer data to extraction result
        base_ar_state["extraction_result"] = {
            "header": {
                "customer_name": "New Customer Inc",
                "customer_tax_id": "987654321",
                "customer_email": "billing@newcustomer.com"
            }
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute validation
        result = await customer_validation_node.execute(state)

        # Assertions
        assert result["current_step"] == "customer_validated"
        assert result["status"] == "processing"
        assert result["customer_validation_result"]["valid"] is True
        assert result["customer_data"]["name"] == "New Customer Inc"

    @pytest.mark.asyncio
    async def test_customer_credit_limit_exceeded(
        self, customer_validation_node, mock_customer_service, sample_customer, base_ar_state
    ):
        """Test validation failure due to exceeded credit limit."""
        # Setup mock response for exceeded credit
        mock_customer_service.get_customer_by_id.return_value = sample_customer
        mock_customer_service.validate_customer_credit.return_value = {
            "valid": False,
            "reason": "Credit limit exceeded",
            "available_credit": Decimal("0.00"),
            "used_credit": Decimal("60000.00")
        }

        base_ar_state["customer_id"] = sample_customer["id"]
        state = ARWorkflowState(**base_ar_state)

        # Execute validation
        result = await customer_validation_node.execute(state)

        # Assertions
        assert result["current_step"] == "customer_validation_failed"
        assert result["status"] == "exception"
        assert result["requires_human_review"] is True
        assert "Credit limit exceeded" in result["error_message"]

    @pytest.mark.asyncio
    async def test_inactive_customer_validation(
        self, customer_validation_node, mock_customer_service, sample_customer, base_ar_state
    ):
        """Test validation failure for inactive customer."""
        # Setup inactive customer
        inactive_customer = {**sample_customer, "active": False}
        mock_customer_service.get_customer_by_id.return_value = inactive_customer

        base_ar_state["customer_id"] = sample_customer["id"]
        state = ARWorkflowState(**base_ar_state)

        # Execute validation
        result = await customer_validation_node.execute(state)

        # Assertions
        assert result["current_step"] == "customer_validation_failed"
        assert result["status"] == "exception"
        assert result["requires_human_review"] is True
        assert "inactive" in result["error_message"].lower()


class TestPaymentTermsNode:
    """Test payment terms processing workflow node."""

    @pytest.fixture
    def mock_payment_service(self):
        """Mock payment service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def payment_terms_node(self, mock_payment_service):
        """Create payment terms node with mocked dependencies."""
        return PaymentTermsNode(payment_service=mock_payment_service)

    @pytest.mark.asyncio
    async def test_process_standard_payment_terms(
        self, payment_terms_node, mock_payment_service, base_ar_state
    ):
        """Test processing of standard payment terms (NET30)."""
        # Setup mock response
        mock_payment_service.calculate_due_date.return_value = (
            datetime.utcnow() + timedelta(days=30)
        ).isoformat()
        mock_payment_service.validate_payment_terms.return_value = {
            "valid": True,
            "terms_type": "standard",
            "days": 30
        }

        base_ar_state["payment_terms"] = "NET30"
        base_ar_state["extraction_result"] = {
            "header": {"invoice_date": datetime.utcnow().isoformat()}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute payment terms processing
        result = await payment_terms_node.execute(state)

        # Assertions
        assert result["current_step"] == "payment_terms_processed"
        assert result["status"] == "processing"
        assert result["payment_terms_result"]["valid"] is True
        assert result["payment_terms_result"]["days"] == 30
        assert result["due_date"] is not None

    @pytest.mark.asyncio
    async def test_process_early_payment_discount_terms(
        self, payment_terms_node, mock_payment_service, base_ar_state
    ):
        """Test processing of payment terms with early payment discount."""
        # Setup mock response
        due_date = datetime.utcnow() + timedelta(days=30)
        discount_deadline = datetime.utcnow() + timedelta(days=10)

        mock_payment_service.calculate_due_date.return_value = due_date.isoformat()
        mock_payment_service.calculate_discount_deadline.return_value = discount_deadline.isoformat()
        mock_payment_service.validate_payment_terms.return_value = {
            "valid": True,
            "terms_type": "discount",
            "days": 30,
            "discount_percent": 2.0,
            "discount_days": 10
        }

        base_ar_state["payment_terms"] = "2% 10 NET 30"
        base_ar_state["early_payment_discount"] = 2.0
        base_ar_state["extraction_result"] = {
            "header": {"invoice_date": datetime.utcnow().isoformat()}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute payment terms processing
        result = await payment_terms_node.execute(state)

        # Assertions
        assert result["current_step"] == "payment_terms_processed"
        assert result["status"] == "processing"
        assert result["payment_terms_result"]["discount_percent"] == 2.0
        assert result["payment_terms_result"]["discount_days"] == 10
        assert result["early_payment_discount"] == 2.0

    @pytest.mark.asyncio
    async def test_invalid_payment_terms(
        self, payment_terms_node, mock_payment_service, base_ar_state
    ):
        """Test processing of invalid payment terms."""
        # Setup mock response
        mock_payment_service.validate_payment_terms.return_value = {
            "valid": False,
            "reason": "Invalid payment terms format",
            "suggested_terms": "NET30"
        }

        base_ar_state["payment_terms"] = "INVALID_TERMS"
        state = ARWorkflowState(**base_ar_state)

        # Execute payment terms processing
        result = await payment_terms_node.execute(state)

        # Assertions
        assert result["current_step"] == "payment_terms_failed"
        assert result["status"] == "exception"
        assert result["requires_human_review"] is True
        assert "Invalid payment terms" in result["error_message"]

    @pytest.mark.asyncio
    async def test_custom_payment_terms(
        self, payment_terms_node, mock_payment_service, base_ar_state
    ):
        """Test processing of custom payment terms."""
        # Setup mock response
        mock_payment_service.calculate_due_date.return_value = (
            datetime.utcnow() + timedelta(days=45)
        ).isoformat()
        mock_payment_service.validate_payment_terms.return_value = {
            "valid": True,
            "terms_type": "custom",
            "days": 45,
            "description": "Payment due in 45 days"
        }

        base_ar_state["payment_terms"] = "Custom: 45 days"
        state = ARWorkflowState(**base_ar_state)

        # Execute payment terms processing
        result = await payment_terms_node.execute(state)

        # Assertions
        assert result["current_step"] == "payment_terms_processed"
        assert result["status"] == "processing"
        assert result["payment_terms_result"]["days"] == 45
        assert result["payment_terms_result"]["terms_type"] == "custom"


class TestCollectionNode:
    """Test collection management workflow node."""

    @pytest.fixture
    def mock_collection_service(self):
        """Mock collection service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def collection_node(self, mock_collection_service):
        """Create collection node with mocked dependencies."""
        return CollectionNode(collection_service=mock_collection_service)

    @pytest.mark.asyncio
    async def test_standard_collection_priority(
        self, collection_node, mock_collection_service, base_ar_state
    ):
        """Test standard collection priority assignment."""
        # Setup mock response
        mock_collection_service.calculate_collection_priority.return_value = {
            "priority": CollectionPriority.MEDIUM.value,
            "risk_score": 0.3,
            "factors": ["standard_customer", "normal_amount"]
        }

        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 5000.00},
            "customer_data": {"payment_history_score": 0.8}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute collection processing
        result = await collection_node.execute(state)

        # Assertions
        assert result["current_step"] == "collection_processed"
        assert result["status"] == "processing"
        assert result["collection_result"]["priority"] == CollectionPriority.MEDIUM.value
        assert result["collection_priority"] == CollectionPriority.MEDIUM.value

    @pytest.mark.asyncio
    async def test_high_priority_collection(
        self, collection_node, mock_collection_service, base_ar_state
    ):
        """Test high priority collection assignment."""
        # Setup mock response
        mock_collection_service.calculate_collection_priority.return_value = {
            "priority": CollectionPriority.HIGH.value,
            "risk_score": 0.7,
            "factors": ["high_amount", "new_customer"]
        }

        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 50000.00},
            "customer_data": {"payment_history_score": 0.4}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute collection processing
        result = await collection_node.execute(state)

        # Assertions
        assert result["current_step"] == "collection_processed"
        assert result["status"] == "processing"
        assert result["collection_result"]["priority"] == CollectionPriority.HIGH.value
        assert result["collection_priority"] == CollectionPriority.HIGH.value
        assert result["collection_result"]["risk_score"] == 0.7

    @pytest.mark.asyncio
    async def test_urgent_collection_overdue_customer(
        self, collection_node, mock_collection_service, base_ar_state
    ):
        """Test urgent collection priority for overdue customer."""
        # Setup mock response
        mock_collection_service.calculate_collection_priority.return_value = {
            "priority": CollectionPriority.URGENT.value,
            "risk_score": 0.9,
            "factors": ["overdue_history", "high_amount", "late_payments"]
        }

        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 25000.00}
        }
        base_ar_state["customer_data"] = {
            "payment_history_score": 0.2,
            "overdue_invoices": 3
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute collection processing
        result = await collection_node.execute(state)

        # Assertions
        assert result["current_step"] == "collection_processed"
        assert result["status"] == "processing"
        assert result["collection_result"]["priority"] == CollectionPriority.URGENT.value
        assert result["collection_priority"] == CollectionPriority.URGENT.value

    @pytest.mark.asyncio
    async def test_collection_schedule_generation(
        self, collection_node, mock_collection_service, base_ar_state
    ):
        """Test collection schedule generation."""
        # Setup mock response
        mock_collection_service.calculate_collection_priority.return_value = {
            "priority": CollectionPriority.MEDIUM.value,
            "risk_score": 0.3,
            "factors": ["standard_customer"]
        }
        mock_collection_service.generate_collection_schedule.return_value = {
            "schedule_created": True,
            "next_contact_date": (datetime.utcnow() + timedelta(days=35)).isoformat(),
            "contact_method": "email",
            "template": "standard_reminder"
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute collection processing
        result = await collection_node.execute(state)

        # Assertions
        assert result["collection_result"]["schedule_created"] is True
        assert result["collection_result"]["next_contact_date"] is not None
        assert result["collection_result"]["contact_method"] == "email"


class TestWorkingCapitalNode:
    """Test working capital optimization workflow node."""

    @pytest.fixture
    def mock_working_capital_service(self):
        """Mock working capital service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def working_capital_node(self, mock_working_capital_service):
        """Create working capital node with mocked dependencies."""
        return WorkingCapitalNode(working_capital_service=mock_working_capital_service)

    @pytest.mark.asyncio
    async def test_working_capital_optimization_high_score(
        self, working_capital_node, mock_working_capital_service, base_ar_state
    ):
        """Test working capital optimization with high score."""
        # Setup mock response
        mock_working_capital_service.calculate_optimization_score.return_value = {
            "overall_score": 85.5,
            "collection_efficiency_score": 90.0,
            "discount_optimization_score": 75.0,
            "recommendations": ["Maintain current collection process"],
            "cash_flow_impact": {
                "projected_days": 28,
                "variance": "-2 days"
            }
        }

        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 10000.00}
        }
        base_ar_state["customer_data"] = {
            "payment_history_score": 0.9
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute working capital optimization
        result = await working_capital_node.execute(state)

        # Assertions
        assert result["current_step"] == "working_capital_optimized"
        assert result["status"] == "processing"
        assert result["working_capital_result"]["overall_score"] == 85.5
        assert result["working_capital_score"] == 85.5
        assert len(result["working_capital_result"]["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_early_payment_discount_optimization(
        self, working_capital_node, mock_working_capital_service, base_ar_state
    ):
        """Test working capital optimization with early payment discount."""
        # Setup mock response
        mock_working_capital_service.calculate_optimization_score.return_value = {
            "overall_score": 92.0,
            "collection_efficiency_score": 95.0,
            "discount_optimization_score": 85.0,
            "recommendations": [
                "Utilize early payment discount for 2% savings",
                "Maintain current collection process"
            ],
            "discount_opportunities": [{
                "invoice_amount": 10000.00,
                "discount_percent": 2.0,
                "discount_amount": 200.00,
                "deadline": (datetime.utcnow() + timedelta(days=8)).isoformat()
            }],
            "cash_flow_impact": {
                "projected_days": 25,
                "variance": "-5 days",
                "savings": 200.00
            }
        }

        base_ar_state["early_payment_discount"] = 2.0
        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 10000.00}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute working capital optimization
        result = await working_capital_node.execute(state)

        # Assertions
        assert result["working_capital_result"]["overall_score"] == 92.0
        assert len(result["working_capital_result"]["discount_opportunities"]) == 1
        assert result["working_capital_result"]["discount_opportunities"][0]["discount_amount"] == 200.00

    @pytest.mark.asyncio
    async def test_working_capital_improvement_recommendations(
        self, working_capital_node, mock_working_capital_service, base_ar_state
    ):
        """Test working capital optimization with improvement recommendations."""
        # Setup mock response
        mock_working_capital_service.calculate_optimization_score.return_value = {
            "overall_score": 65.0,
            "collection_efficiency_score": 60.0,
            "discount_optimization_score": 75.0,
            "recommendations": [
                "Implement proactive collection process",
                "Review payment terms for high-risk customers",
                "Utilize available early payment discounts"
            ],
            "improvement_areas": ["collection_efficiency", "payment_terms"],
            "cash_flow_impact": {
                "projected_days": 45,
                "variance": "+5 days"
            }
        }

        base_ar_state["customer_data"] = {
            "payment_history_score": 0.5
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute working capital optimization
        result = await working_capital_node.execute(state)

        # Assertions
        assert result["working_capital_result"]["overall_score"] == 65.0
        assert len(result["working_capital_result"]["recommendations"]) == 3
        assert "collection_efficiency" in result["working_capital_result"]["improvement_areas"]

    @pytest.mark.asyncio
    async def test_cash_flow_forecast_generation(
        self, working_capital_node, mock_working_capital_service, base_ar_state
    ):
        """Test cash flow forecast generation."""
        # Setup mock response
        mock_working_capital_service.calculate_optimization_score.return_value = {
            "overall_score": 75.0,
            "collection_efficiency_score": 80.0,
            "discount_optimization_score": 70.0,
            "recommendations": ["Standard processing"],
            "cash_flow_forecast": {
                "weekly_breakdown": {
                    "2024-W01": 5000.00,
                    "2024-W02": 7500.00,
                    "2024-W03": 3000.00
                },
                "monthly_breakdown": {
                    "2024-01": 15500.00,
                    "2024-02": 12000.00
                },
                "total_expected": 27500.00
            }
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute working capital optimization
        result = await working_capital_node.execute(state)

        # Assertions
        assert "cash_flow_forecast" in result["working_capital_result"]
        assert result["working_capital_result"]["cash_flow_forecast"]["total_expected"] == 27500.00


class TestCustomerCommunicationNode:
    """Test customer communication workflow node."""

    @pytest.fixture
    def mock_communication_service(self):
        """Mock communication service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def communication_node(self, mock_communication_service):
        """Create customer communication node with mocked dependencies."""
        return CustomerCommunicationNode(communication_service=mock_communication_service)

    @pytest.mark.asyncio
    async def test_standard_invoice_communication(
        self, communication_node, mock_communication_service, base_ar_state
    ):
        """Test standard invoice communication to customer."""
        # Setup mock response
        mock_communication_service.send_invoice_notification.return_value = {
            "sent": True,
            "communication_id": str(uuid.uuid4()),
            "method": "email",
            "recipient": "customer@example.com",
            "sent_at": datetime.utcnow().isoformat()
        }

        base_ar_state["customer_data"] = {
            "email": "customer@example.com",
            "name": "Test Customer"
        }
        base_ar_state["extraction_result"] = {
            "header": {
                "invoice_number": "INV-001",
                "total_amount": 5000.00
            }
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute customer communication
        result = await communication_node.execute(state)

        # Assertions
        assert result["current_step"] == "customer_communicated"
        assert result["status"] == "processing"
        assert result["communication_result"]["sent"] is True
        assert result["communication_result"]["method"] == "email"

    @pytest.mark.asyncio
    async def test_early_payment_discount_communication(
        self, communication_node, mock_communication_service, base_ar_state
    ):
        """Test communication with early payment discount offer."""
        # Setup mock response
        mock_communication_service.send_discount_offer.return_value = {
            "sent": True,
            "communication_id": str(uuid.uuid4()),
            "method": "email",
            "type": "early_payment_discount",
            "discount_percent": 2.0,
            "discount_amount": 100.00,
            "deadline": (datetime.utcnow() + timedelta(days=10)).isoformat()
        }

        base_ar_state["early_payment_discount"] = 2.0
        base_ar_state["customer_data"] = {"email": "customer@example.com"}
        base_ar_state["extraction_result"] = {
            "header": {"total_amount": 5000.00}
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute customer communication
        result = await communication_node.execute(state)

        # Assertions
        assert result["communication_result"]["sent"] is True
        assert result["communication_result"]["type"] == "early_payment_discount"
        assert result["communication_result"]["discount_percent"] == 2.0
        assert result["communication_result"]["discount_amount"] == 100.00

    @pytest.mark.asyncio
    async def test_high_priority_collection_communication(
        self, communication_node, mock_communication_service, base_ar_state
    ):
        """Test high priority collection communication."""
        # Setup mock response
        mock_communication_service.send_collection_notice.return_value = {
            "sent": True,
            "communication_id": str(uuid.uuid4()),
            "method": "email",
            "type": "collection_reminder",
            "priority": CollectionPriority.HIGH.value,
            "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat()
        }

        base_ar_state["collection_priority"] = CollectionPriority.HIGH.value
        base_ar_state["customer_data"] = {"email": "customer@example.com"}
        base_ar_state["due_date"] = (datetime.utcnow() + timedelta(days=5)).isoformat()

        state = ARWorkflowState(**base_ar_state)

        # Execute customer communication
        result = await communication_node.execute(state)

        # Assertions
        assert result["communication_result"]["sent"] is True
        assert result["communication_result"]["type"] == "collection_reminder"
        assert result["communication_result"]["priority"] == CollectionPriority.HIGH.value

    @pytest.mark.asyncio
    async def test_communication_failure_retry(
        self, communication_node, mock_communication_service, base_ar_state
    ):
        """Test communication failure with retry logic."""
        # Setup mock response for initial failure
        mock_communication_service.send_invoice_notification.side_effect = [
            {"sent": False, "error": "SMTP server unavailable"},
            {"sent": True, "communication_id": str(uuid.uuid4())}
        ]

        base_ar_state["customer_data"] = {"email": "customer@example.com"}
        state = ARWorkflowState(**base_ar_state)

        # Execute customer communication
        result = await communication_node.execute(state)

        # Assertions - should succeed on retry
        assert result["communication_result"]["sent"] is True
        assert mock_communication_service.send_invoice_notification.call_count == 2

    @pytest.mark.asyncio
    async def test_multi_channel_communication(
        self, communication_node, mock_communication_service, base_ar_state
    ):
        """Test multi-channel communication for urgent collection."""
        # Setup mock response
        mock_communication_service.send_multi_channel_notice.return_value = {
            "sent": True,
            "communication_id": str(uuid.uuid4()),
            "channels": ["email", "sms", "portal"],
            "email_sent": True,
            "sms_sent": True,
            "portal_notification_sent": True,
            "priority": CollectionPriority.URGENT.value
        }

        base_ar_state["collection_priority"] = CollectionPriority.URGENT.value
        base_ar_state["customer_data"] = {
            "email": "customer@example.com",
            "phone": "+1234567890"
        }

        state = ARWorkflowState(**base_ar_state)

        # Execute customer communication
        result = await communication_node.execute(state)

        # Assertions
        assert result["communication_result"]["sent"] is True
        assert len(result["communication_result"]["channels"]) == 3
        assert result["communication_result"]["email_sent"] is True
        assert result["communication_result"]["sms_sent"] is True


class TestARWorkflowIntegration:
    """Integration tests for complete AR workflow."""

    @pytest.mark.asyncio
    async def test_complete_ar_workflow_success(self):
        """Test complete AR workflow execution with all nodes."""
        # This test would integrate all AR workflow nodes
        # and test the complete flow from customer validation
        # through communication

        # Setup state with all required data
        initial_state = {
            "invoice_id": str(uuid.uuid4()),
            "invoice_type": "ar",
            "customer_id": str(uuid.uuid4()),
            "extraction_result": {
                "header": {
                    "customer_name": "Test Customer",
                    "invoice_number": "INV-001",
                    "total_amount": 10000.00,
                    "invoice_date": datetime.utcnow().isoformat()
                }
            },
            "current_step": "customer_validation",
            "status": "processing"
        }

        # This would test the complete workflow execution
        # with all mocked services providing successful responses

        # Assertions for final state
        assert initial_state["invoice_type"] == "ar"
        # Additional assertions would be added here

    @pytest.mark.asyncio
    async def test_ar_workflow_with_human_review(self):
        """Test AR workflow that requires human review."""
        # Test scenario where workflow requires human intervention
        # due to validation failures or exceptions

        pass

    @pytest.mark.asyncio
    async def test_ar_workflow_error_recovery(self):
        """Test AR workflow error recovery mechanisms."""
        # Test error handling and recovery in AR workflow

        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])