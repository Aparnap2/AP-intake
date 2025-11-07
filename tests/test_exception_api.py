"""
Tests for the Exception Management API endpoints.

This module tests the RESTful API endpoints for exception management,
including listing, resolving, searching, and metrics retrieval.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.api_v1.endpoints.exceptions import router
from app.api.schemas.exception import (
    ExceptionAction,
    ExceptionCategory,
    ExceptionResponse,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionResolutionRequest,
    ExceptionBatchUpdate,
    ExceptionMetrics,
    ExceptionListResponse,
)
from app.services.exception_service import ExceptionService


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/exceptions")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_exception_service():
    """Create mock exception service."""
    service = AsyncMock(spec=ExceptionService)
    return service


@pytest.fixture
def sample_exception_response():
    """Create sample exception response for testing."""
    return ExceptionResponse(
        id=str(uuid4()),
        invoice_id=str(uuid4()),
        reason_code="SUBTOTAL_MISMATCH",
        category=ExceptionCategory.MATH,
        severity=ExceptionSeverity.ERROR,
        status=ExceptionStatus.OPEN,
        message="Line items total doesn't match subtotal",
        details={
            "field": "subtotal",
            "actual_value": "100.50",
            "expected_value": "100.00",
            "difference": 0.50
        },
        auto_resolution_possible=True,
        suggested_actions=[ExceptionAction.MANUAL_ADJUST, ExceptionAction.RECALCULATE],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_exception_metrics():
    """Create sample exception metrics for testing."""
    return ExceptionMetrics(
        total_exceptions=100,
        resolved_exceptions=80,
        open_exceptions=20,
        resolution_rate=80.0,
        avg_resolution_hours=4.5,
        by_category={"MATH": 40, "MATCHING": 30, "DATA_QUALITY": 30},
        by_severity={"ERROR": 60, "WARNING": 40},
        top_reason_codes={"SUBTOTAL_MISMATCH": 25, "PO_NOT_FOUND": 20},
        period_days=30,
        generated_at=datetime.utcnow()
    )


class TestExceptionListEndpoint:
    """Test the exception list endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_list_exceptions_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful exception listing."""
        # Setup mocks
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        # Mock service response
        mock_list_response = ExceptionListResponse(
            exceptions=[sample_exception_response],
            total=1,
            limit=50,
            offset=0
        )
        mock_exception_service.list_exceptions.return_value = mock_list_response

        # Make request
        response = client.get("/api/v1/exceptions/")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["exceptions"]) == 1
        assert data["exceptions"][0]["id"] == sample_exception_response.id
        assert data["exceptions"][0]["reason_code"] == "SUBTOTAL_MISMATCH"

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_list_exceptions_with_filters(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test exception listing with filters."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.list_exceptions.return_value = ExceptionListResponse(
            exceptions=[],
            total=0,
            limit=50,
            offset=0
        )

        # Make request with filters
        response = client.get(
            "/api/v1/exceptions/?"
            "status=open&"
            "severity=error&"
            "category=MATH&"
            "limit=10&"
            "offset=0"
        )

        assert response.status_code == 200
        mock_exception_service.list_exceptions.assert_called_once()

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_list_exceptions_service_error(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test exception listing with service error."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.list_exceptions.side_effect = Exception("Database error")

        response = client.get("/api/v1/exceptions/")

        assert response.status_code == 500
        assert "Failed to list exceptions" in response.json()["detail"]


class TestExceptionDetailEndpoint:
    """Test the exception detail endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_get_exception_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful exception retrieval."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.get_exception.return_value = sample_exception_response

        response = client.get(f"/api/v1/exceptions/{sample_exception_response.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_exception_response.id
        assert data["reason_code"] == "SUBTOTAL_MISMATCH"
        assert data["category"] == "MATH"
        assert data["severity"] == "ERROR"

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_get_exception_not_found(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test exception retrieval with non-existent ID."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.get_exception.return_value = None

        response = client.get("/api/v1/exceptions/non-existent-id")

        assert response.status_code == 404
        assert "Exception not found" in response.json()["detail"]


class TestExceptionResolutionEndpoint:
    """Test the exception resolution endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_resolve_exception_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful exception resolution."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        # Create resolved exception response
        resolved_exception = ExceptionResponse(
            id=sample_exception_response.id,
            invoice_id=sample_exception_response.invoice_id,
            reason_code=sample_exception_response.reason_code,
            category=sample_exception_response.category,
            severity=sample_exception_response.severity,
            status=ExceptionStatus.RESOLVED,
            message="Exception resolved successfully",
            created_at=sample_exception_response.created_at,
            updated_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
            resolved_by="test_user"
        )

        # Setup mocks
        mock_exception_service.get_exception.return_value = sample_exception_response
        mock_exception_service.resolve_exception.return_value = resolved_exception

        # Resolution request
        resolution_data = {
            "action": "MANUAL_ADJUST",
            "resolved_by": "test_user",
            "notes": "Adjusted subtotal to match line items",
            "resolution_data": {"adjustment_amount": 0.50},
            "auto_approve_invoice": False
        }

        response = client.post(
            f"/api/v1/exceptions/{sample_exception_response.id}/resolve",
            json=resolution_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["exception"]["status"] == "resolved"
        assert data["exception"]["resolved_by"] == "test_user"
        assert data["invoice_auto_approved"] is False

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_resolve_exception_with_auto_approval(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test exception resolution with auto-approval."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        resolved_exception = ExceptionResponse(
            id=sample_exception_response.id,
            invoice_id=sample_exception_response.invoice_id,
            reason_code=sample_exception_response.reason_code,
            category=sample_exception_response.category,
            severity=sample_exception_response.severity,
            status=ExceptionStatus.RESOLVED,
            message="Exception resolved and invoice auto-approved",
            created_at=sample_exception_response.created_at,
            updated_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
            resolved_by="test_user"
        )

        mock_exception_service.get_exception.return_value = sample_exception_response
        mock_exception_service.resolve_exception.return_value = resolved_exception

        resolution_data = {
            "action": "MANUAL_ADJUST",
            "resolved_by": "test_user",
            "notes": "Adjusted and approved",
            "auto_approve_invoice": True
        }

        response = client.post(
            f"/api/v1/exceptions/{sample_exception_response.id}/resolve",
            json=resolution_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["invoice_auto_approved"] is True

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_resolve_exception_invalid_action(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test exception resolution with invalid action."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.get_exception.return_value = sample_exception_response
        mock_exception_service.resolve_exception.side_effect = ValueError("Invalid resolution")

        resolution_data = {
            "action": "INVALID_ACTION",
            "resolved_by": "test_user",
            "notes": "This should fail"
        }

        response = client.post(
            f"/api/v1/exceptions/{sample_exception_response.id}/resolve",
            json=resolution_data
        )

        assert response.status_code == 400
        assert "Invalid resolution" in response.json()["detail"]


class TestBatchResolutionEndpoint:
    """Test the batch resolution endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_batch_resolve_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test successful batch exception resolution."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        # Create mock resolved exceptions
        resolved_exceptions = [
            ExceptionResponse(
                id=str(uuid4()),
                invoice_id=str(uuid4()),
                reason_code="SUBTOTAL_MISMATCH",
                category=ExceptionCategory.MATH,
                severity=ExceptionSeverity.ERROR,
                status=ExceptionStatus.RESOLVED,
                message="Bulk resolved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                resolved_at=datetime.utcnow(),
                resolved_by="supervisor_user"
            ) for _ in range(3)
        ]

        mock_exception_service.batch_resolve_exceptions.return_value = resolved_exceptions

        batch_data = {
            "exception_ids": [exc.id for exc in resolved_exceptions],
            "action": "MANUAL_REVIEW",
            "resolved_by": "supervisor_user",
            "notes": "Bulk approval for similar issues",
            "auto_approve_invoices": True
        }

        response = client.post("/api/v1/exceptions/batch-resolve", json=batch_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 3
        assert data["error_count"] == 0
        assert len(data["resolved_exceptions"]) == 3
        assert len(data["invoices_auto_approved"]) == 3


class TestExceptionMetricsEndpoint:
    """Test the exception metrics endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_get_metrics_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_metrics,
        mock_exception_service
    ):
        """Test successful metrics retrieval."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.get_exception_metrics.return_value = sample_exception_metrics

        response = client.get("/api/v1/exceptions/metrics/summary?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["total_exceptions"] == 100
        assert data["resolved_exceptions"] == 80
        assert data["open_exceptions"] == 20
        assert data["resolution_rate"] == 80.0
        assert data["period_days"] == 30
        assert "MATH" in data["by_category"]
        assert "ERROR" in data["by_severity"]

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_get_metrics_custom_period(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test metrics retrieval with custom period."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.get_exception_metrics.return_value = ExceptionMetrics(
            total_exceptions=50,
            resolved_exceptions=40,
            open_exceptions=10,
            resolution_rate=80.0,
            avg_resolution_hours=2.0,
            by_category={},
            by_severity={},
            top_reason_codes={},
            period_days=7,
            generated_at=datetime.utcnow()
        )

        response = client.get("/api/v1/exceptions/metrics/summary?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
        mock_exception_service.get_exception_metrics.assert_called_once_with(days=7)


class TestExceptionDashboardEndpoint:
    """Test the exception dashboard endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_get_dashboard_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful dashboard data retrieval."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        # Mock service responses
        current_metrics = ExceptionMetrics(
            total_exceptions=10,
            resolved_exceptions=8,
            open_exceptions=2,
            resolution_rate=80.0,
            avg_resolution_hours=3.0,
            by_category={"MATH": 5, "MATCHING": 5},
            by_severity={"ERROR": 6, "WARNING": 4},
            top_reason_codes={"SUBTOTAL_MISMATCH": 3},
            period_days=7,
            generated_at=datetime.utcnow()
        )

        monthly_metrics = ExceptionMetrics(
            total_exceptions=50,
            resolved_exceptions=40,
            open_exceptions=10,
            resolution_rate=80.0,
            avg_resolution_hours=4.0,
            by_category={"MATH": 25, "MATCHING": 25},
            by_severity={"ERROR": 30, "WARNING": 20},
            top_reason_codes={"SUBTOTAL_MISMATCH": 15},
            period_days=30,
            generated_at=datetime.utcnow()
        )

        mock_list_response = ExceptionListResponse(
            exceptions=[sample_exception_response],
            total=1,
            limit=10,
            offset=0
        )

        mock_exception_service.get_exception_metrics.side_effect = [current_metrics, monthly_metrics]
        mock_exception_service.list_exceptions.return_value = mock_list_response

        response = client.get("/api/v1/exceptions/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "metrics" in data
        assert "recent_exceptions" in data
        assert data["summary"]["total_exceptions"] == 10
        assert data["metrics"]["period_days"] == 30
        assert len(data["recent_exceptions"]) == 1


class TestExceptionExportEndpoint:
    """Test the exception export endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_export_exceptions_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful exception export."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_list_response = ExceptionListResponse(
            exceptions=[sample_exception_response],
            total=1,
            limit=1000,
            offset=0
        )
        mock_exception_service.list_exceptions.return_value = mock_list_response

        response = client.get("/api/v1/exceptions/export")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["exception_id"] == sample_exception_response.id
        assert data[0]["reason_code"] == "SUBTOTAL_MISMATCH"

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_export_exceptions_with_filters(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test exception export with filters."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_exception_service.list_exceptions.return_value = ExceptionListResponse(
            exceptions=[],
            total=0,
            limit=1000,
            offset=0
        )

        response = client.get(
            "/api/v1/exceptions/export?"
            "severity=ERROR&"
            "category=MATH&"
            "limit=500"
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)
        mock_exception_service.list_exceptions.assert_called_once()


class TestExceptionSearchEndpoint:
    """Test the exception search endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_search_exceptions_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        sample_exception_response,
        mock_exception_service
    ):
        """Test successful exception search."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        mock_list_response = ExceptionListResponse(
            exceptions=[sample_exception_response],
            total=1,
            limit=50,
            offset=0
        )
        mock_exception_service.list_exceptions.return_value = mock_list_response

        response = client.get("/api/v1/exceptions/search?query=subtotal")

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "subtotal"
        assert len(data["results"]) == 1
        assert data["total"] == 1

    def test_search_exceptions_missing_query(self, client):
        """Test exception search with missing query parameter."""
        response = client.get("/api/v1/exceptions/search")

        # FastAPI should validate the required query parameter
        assert response.status_code == 422  # Validation error


class TestExceptionCreationEndpoint:
    """Test the manual exception creation endpoint."""

    @patch('app.api.api_v1.endpoints.exceptions.get_exception_service')
    @patch('app.api.api_v1.endpoints.exceptions.get_db')
    def test_create_manual_exception_success(
        self,
        mock_get_db,
        mock_get_service,
        client,
        mock_exception_service
    ):
        """Test successful manual exception creation."""
        mock_get_service.return_value = mock_exception_service
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        exception_data = {
            "invoice_id": str(uuid4()),
            "reason_code": "SUBTOTAL_MISMATCH",
            "category": "MATH",
            "severity": "ERROR",
            "message": "Manual math exception",
            "details": {"field": "subtotal"},
            "auto_resolution_possible": True,
            "suggested_actions": ["MANUAL_ADJUST"]
        }

        response = client.post("/api/v1/exceptions/", json=exception_data)

        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == exception_data["invoice_id"]
        assert data["reason_code"] == "SUBTOTAL_MISMATCH"
        assert data["category"] == "MATH"
        assert data["severity"] == "ERROR"

    def test_create_manual_exception_invalid_data(self, client):
        """Test manual exception creation with invalid data."""
        invalid_data = {
            "invoice_id": "not-a-uuid",
            "reason_code": "INVALID_CODE",
            "category": "INVALID_CATEGORY",
            "severity": "INVALID_SEVERITY",
            "message": ""
        }

        response = client.post("/api/v1/exceptions/", json=invalid_data)

        # FastAPI should validate the request body
        assert response.status_code == 422  # Validation error