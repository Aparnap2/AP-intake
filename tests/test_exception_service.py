"""
Tests for the Exception Management Service.

This module tests the comprehensive exception management functionality,
including classification, resolution workflows, and metrics.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.exception_service import ExceptionService, MathExceptionHandler
from app.api.schemas.exception import (
    ExceptionAction,
    ExceptionCategory,
    ExceptionResponse,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionResolutionRequest,
    ExceptionBatchUpdate,
    ExceptionMetrics,
)
from app.api.schemas.validation import (
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationRulesConfig,
)
from app.models.invoice import Invoice, Exception as ExceptionModel
from app.models.reference import Vendor


@pytest.fixture
def exception_service():
    """Create exception service instance."""
    return ExceptionService()


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_validation_issues():
    """Create sample validation issues for testing."""
    return [
        ValidationIssue(
            code=ValidationCode.SUBTOTAL_MISMATCH,
            message="Line items total doesn't match subtotal",
            severity=ValidationSeverity.ERROR,
            field="subtotal",
            actual_value="100.50",
            expected_value="100.00",
            details={"difference": 0.50}
        ),
        ValidationIssue(
            code=ValidationCode.PO_NOT_FOUND,
            message="Purchase Order not found",
            severity=ValidationSeverity.WARNING,
            field="po_number",
            actual_value="PO12345"
        )
    ]


@pytest.fixture
def sample_invoice():
    """Create sample invoice for testing."""
    return Invoice(
        id=uuid4(),
        vendor_id=uuid4(),
        file_url="test://invoice.pdf",
        file_hash="abc123",
        file_name="test_invoice.pdf",
        file_size="1.2MB",
        status="received"
    )


class TestExceptionService:
    """Test the main ExceptionService class."""

    @pytest.mark.asyncio
    async def test_create_exception_from_validation(
        self,
        exception_service,
        sample_validation_issues,
        mock_session,
        sample_invoice
    ):
        """Test creating exceptions from validation issues."""
        # Mock database queries
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_invoice
        mock_session.execute.return_value = mock_result

        with patch.object(exception_service, '_process_validation_exceptions') as mock_process:
            mock_process.return_value = [
                ExceptionResponse(
                    id=str(uuid4()),
                    invoice_id=str(sample_invoice.id),
                    reason_code=ValidationCode.SUBTOTAL_MISMATCH.value,
                    category=ExceptionCategory.MATH,
                    severity=ExceptionSeverity.ERROR,
                    status=ExceptionStatus.OPEN,
                    message="Test exception",
                    details={},
                    auto_resolution_possible=True,
                    suggested_actions=[ExceptionAction.MANUAL_ADJUST],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            ]

            result = await exception_service.create_exception_from_validation(
                invoice_id=str(sample_invoice.id),
                validation_issues=sample_validation_issues,
                session=mock_session
            )

            assert len(result) == 1
            assert result[0].category == ExceptionCategory.MATH
            assert result[0].severity == ExceptionSeverity.ERROR
            mock_process.assert_called_once()

    def test_classify_exception_category(self, exception_service):
        """Test exception classification by category."""
        # Math exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.SUBTOTAL_MISMATCH
        ) == ExceptionCategory.MATH

        # Duplicate exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.DUPLICATE_INVOICE
        ) == ExceptionCategory.DUPLICATE

        # Matching exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.PO_NOT_FOUND
        ) == ExceptionCategory.MATCHING

        # Vendor policy exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.INACTIVE_VENDOR
        ) == ExceptionCategory.VENDOR_POLICY

        # Data quality exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.MISSING_REQUIRED_FIELD
        ) == ExceptionCategory.DATA_QUALITY

        # System exceptions
        assert exception_service._classify_exception_category(
            ValidationCode.VALIDATION_ERROR
        ) == ExceptionCategory.SYSTEM

    def test_determine_exception_severity(self, exception_service):
        """Test exception severity determination."""
        # Error severity
        error_issues = [
            ValidationIssue(
                code=ValidationCode.SUBTOTAL_MISMATCH,
                message="Test error",
                severity=ValidationSeverity.ERROR
            )
        ]
        assert exception_service._determine_exception_severity(error_issues) == ExceptionSeverity.ERROR

        # Warning severity
        warning_issues = [
            ValidationIssue(
                code=ValidationCode.PO_NOT_FOUND,
                message="Test warning",
                severity=ValidationSeverity.WARNING
            )
        ]
        assert exception_service._determine_exception_severity(warning_issues) == ExceptionSeverity.WARNING

        # Info severity
        info_issues = [
            ValidationIssue(
                code=ValidationCode.MISSING_REQUIRED_FIELD,
                message="Test info",
                severity=ValidationSeverity.INFO
            )
        ]
        assert exception_service._determine_exception_severity(info_issues) == ExceptionSeverity.INFO

    def test_group_related_issues(self, exception_service):
        """Test grouping of related validation issues."""
        issues = [
            ValidationIssue(
                code=ValidationCode.SUBTOTAL_MISMATCH,
                message="Math error 1",
                severity=ValidationSeverity.ERROR,
                field="subtotal"
            ),
            ValidationIssue(
                code=ValidationCode.SUBTOTAL_MISMATCH,
                message="Math error 2",
                severity=ValidationSeverity.ERROR,
                field="subtotal"
            ),
            ValidationIssue(
                code=ValidationCode.PO_NOT_FOUND,
                message="PO error",
                severity=ValidationSeverity.WARNING,
                field="po_number"
            )
        ]

        grouped = exception_service._group_related_issues(issues)

        # Should group math errors together
        assert len(grouped) == 2
        assert len(grouped[0]) == 2  # Math errors
        assert len(grouped[1]) == 1  # PO error
        assert grouped[0][0].field == "subtotal"

    @pytest.mark.asyncio
    async def test_get_exception(self, exception_service, mock_session):
        """Test retrieving an exception by ID."""
        exception_id = str(uuid4())
        mock_db_exception = ExceptionModel(
            id=uuid4(),
            invoice_id=uuid4(),
            reason_code="SUBTOTAL_MISMATCH",
            details_json={
                "category": "MATH",
                "severity": "ERROR",
                "message": "Test exception"
            }
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_exception
        mock_session.execute.return_value = mock_result

        result = await exception_service.get_exception(exception_id, session=mock_session)

        assert result is not None
        assert result.reason_code == "SUBTOTAL_MISMATCH"
        assert result.category == ExceptionCategory.MATH
        assert result.severity == ExceptionSeverity.ERROR

    @pytest.mark.asyncio
    async def test_resolve_exception(self, exception_service, mock_session):
        """Test resolving an exception."""
        exception_id = str(uuid4())
        resolved_by = "test_user"
        resolution_request = ExceptionResolutionRequest(
            action=ExceptionAction.MANUAL_ADJUST,
            resolved_by=resolved_by,
            notes="Test resolution",
            resolution_data={"adjustment_amount": 0.50}
        )

        mock_db_exception = ExceptionModel(
            id=uuid4(),
            invoice_id=uuid4(),
            reason_code="SUBTOTAL_MISMATCH",
            details_json={
                "category": "MATH",
                "severity": "ERROR",
                "message": "Test exception"
            }
        )

        # Mock getting the exception
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_exception
        mock_session.execute.return_value = mock_result

        # Mock validation
        with patch.object(exception_service.exception_handlers[ExceptionCategory.MATH], 'validate_resolution') as mock_validate:
            mock_validate.return_value = {"valid": True}

            with patch.object(exception_service, '_convert_to_response') as mock_convert:
                mock_convert.return_value = ExceptionResponse(
                    id=exception_id,
                    invoice_id=str(mock_db_exception.invoice_id),
                    reason_code="SUBTOTAL_MISMATCH",
                    category=ExceptionCategory.MATH,
                    severity=ExceptionSeverity.ERROR,
                    status=ExceptionStatus.RESOLVED,
                    message="Test exception resolved",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    resolved_at=datetime.utcnow(),
                    resolved_by=resolved_by
                )

                result = await exception_service.resolve_exception(
                    exception_id=exception_id,
                    resolution_request=resolution_request,
                    session=mock_session
                )

                assert result.status == ExceptionStatus.RESOLVED
                assert result.resolved_by == resolved_by
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_exception_metrics(self, exception_service, mock_session):
        """Test generating exception metrics."""
        days = 30

        # Mock database queries for metrics
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100  # Total exceptions
        mock_resolved_result = MagicMock()
        mock_resolved_result.scalar.return_value = 80  # Resolved exceptions
        mock_open_result = MagicMock()
        mock_open_result.scalar.return_value = 20  # Open exceptions
        mock_avg_time_result = MagicMock()
        mock_avg_time_result.scalar.return_value = 14400  # 4 hours in seconds
        mock_category_result = MagicMock()
        mock_category_result.all.return_value = [("MATH", 40), ("MATCHING", 30)]
        mock_severity_result = MagicMock()
        mock_severity_result.all.return_value = [("ERROR", 60), ("WARNING", 40)]
        mock_reason_code_result = MagicMock()
        mock_reason_code_result.all.return_value = [("SUBTOTAL_MISMATCH", 25), ("PO_NOT_FOUND", 20)]

        def mock_execute_side_effect(query):
            if "func.count(ExceptionModel.id)" in str(query):
                return mock_count_result
            elif "resolved_at.isnot(None)" in str(query):
                return mock_resolved_result
            elif "resolved_at.is_(None)" in str(query):
                return mock_open_result
            elif "avg(" in str(query):
                return mock_avg_time_result
            elif "category" in str(query):
                return mock_category_result
            elif "severity" in str(query):
                return mock_severity_result
            elif "reason_code" in str(query):
                return mock_reason_code_result
            return MagicMock()

        mock_session.execute.side_effect = mock_execute_side_effect

        result = await exception_service.get_exception_metrics(days=days, session=mock_session)

        assert result.total_exceptions == 100
        assert result.resolved_exceptions == 80
        assert result.open_exceptions == 20
        assert result.resolution_rate == 80.0
        assert result.avg_resolution_hours == 4.0
        assert "MATH" in result.by_category
        assert "ERROR" in result.by_severity
        assert len(result.top_reason_codes) > 0


class TestMathExceptionHandler:
    """Test the MathExceptionHandler class."""

    @pytest.fixture
    def math_handler(self):
        """Create math exception handler."""
        return MathExceptionHandler()

    @pytest.mark.asyncio
    async def test_create_math_exception(self, math_handler, mock_session):
        """Test creating a math exception."""
        invoice_id = str(uuid4())
        issues = [
            ValidationIssue(
                code=ValidationCode.SUBTOTAL_MISMATCH,
                message="Line items total doesn't match subtotal",
                severity=ValidationSeverity.ERROR,
                field="subtotal",
                actual_value="100.50",
                expected_value="100.00",
                details={"difference": 0.50}
            )
        ]

        result = await math_handler.create_exception(invoice_id, issues, mock_session)

        assert result.reason_code == "SUBTOTAL_MISMATCH"
        assert "Mathematical discrepancy" in result.message
        assert result.auto_resolution_possible is True
        assert ExceptionAction.RECALCULATE in result.suggested_actions
        assert ExceptionAction.MANUAL_ADJUST in result.suggested_actions

    @pytest.mark.asyncio
    async def test_validate_math_resolution(self, math_handler, mock_session):
        """Test validating math exception resolution."""
        db_exception = ExceptionModel(
            id=uuid4(),
            invoice_id=uuid4(),
            reason_code="SUBTOTAL_MISMATCH",
            details_json={}
        )

        # Valid manual adjustment
        resolution_request = ExceptionResolutionRequest(
            action=ExceptionAction.MANUAL_ADJUST,
            resolved_by="test_user",
            resolution_data={"adjustment_amount": 0.50}
        )

        result = await math_handler.validate_resolution(db_exception, resolution_request, mock_session)
        assert result["valid"] is True

        # Invalid large adjustment
        large_adjustment_request = ExceptionResolutionRequest(
            action=ExceptionAction.MANUAL_ADJUST,
            resolved_by="test_user",
            resolution_data={"adjustment_amount": 50000.00}
        )

        result = await math_handler.validate_resolution(db_exception, large_adjustment_request, mock_session)
        assert result["valid"] is False
        assert "too large" in result["message"]


class TestExceptionIntegration:
    """Test exception service integration scenarios."""

    @pytest.mark.asyncio
    async def test_exception_workflow_integration(self, exception_service, mock_session):
        """Test complete exception workflow integration."""
        invoice_id = str(uuid4())

        # Create validation issues
        validation_issues = [
            ValidationIssue(
                code=ValidationCode.SUBTOTAL_MISMATCH,
                message="Line items total doesn't match subtotal",
                severity=ValidationSeverity.ERROR,
                field="subtotal",
                actual_value="100.50",
                expected_value="100.00"
            )
        ]

        # Mock exception creation
        with patch.object(exception_service, '_process_validation_exceptions') as mock_process:
            mock_exception = ExceptionResponse(
                id=str(uuid4()),
                invoice_id=invoice_id,
                reason_code=ValidationCode.SUBTOTAL_MISMATCH.value,
                category=ExceptionCategory.MATH,
                severity=ExceptionSeverity.ERROR,
                status=ExceptionStatus.OPEN,
                message="Math discrepancy detected",
                auto_resolution_possible=True,
                suggested_actions=[ExceptionAction.MANUAL_ADJUST],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            mock_process.return_value = [mock_exception]

            # Step 1: Create exception from validation
            exceptions = await exception_service.create_exception_from_validation(
                invoice_id=invoice_id,
                validation_issues=validation_issues,
                session=mock_session
            )
            assert len(exceptions) == 1
            assert exceptions[0].status == ExceptionStatus.OPEN

            # Step 2: Resolve exception
            resolution_request = ExceptionResolutionRequest(
                action=ExceptionAction.MANUAL_ADJUST,
                resolved_by="accountant_user",
                notes="Adjusted subtotal to match line items"
            )

            # Mock getting and resolving exception
            mock_db_exception = ExceptionModel(
                id=uuid4(),
                invoice_id=uuid4(),
                reason_code="SUBTOTAL_MISMATCH",
                details_json={}
            )

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_db_exception
            mock_session.execute.return_value = mock_result

            with patch.object(exception_service.exception_handlers[ExceptionCategory.MATH], 'validate_resolution') as mock_validate:
                mock_validate.return_value = {"valid": True}

                with patch.object(exception_service, '_convert_to_response') as mock_convert:
                    resolved_exception = ExceptionResponse(
                        id=mock_exception.id,
                        invoice_id=invoice_id,
                        reason_code=ValidationCode.SUBTOTAL_MISMATCH.value,
                        category=ExceptionCategory.MATH,
                        severity=ExceptionSeverity.ERROR,
                        status=ExceptionStatus.RESOLVED,
                        message="Math discrepancy resolved",
                        resolved_at=datetime.utcnow(),
                        resolved_by="accountant_user"
                    )
                    mock_convert.return_value = resolved_exception

                    result = await exception_service.resolve_exception(
                        exception_id=mock_exception.id,
                        resolution_request=resolution_request,
                        session=mock_session
                    )

                    assert result.status == ExceptionStatus.RESOLVED
                    assert result.resolved_by == "accountant_user"

    @pytest.mark.asyncio
    async def test_batch_exception_resolution(self, exception_service, mock_session):
        """Test batch resolution of multiple exceptions."""
        exception_ids = [str(uuid4()) for _ in range(3)]
        batch_request = ExceptionBatchUpdate(
            exception_ids=exception_ids,
            action=ExceptionAction.MANUAL_REVIEW,
            resolved_by="supervisor_user",
            notes="Bulk approval for similar issues"
        )

        # Mock exceptions and resolution
        with patch.object(exception_service, '_process_exception_resolution') as mock_resolve:
            def side_effect(exception_id, resolution_request, session):
                return ExceptionResponse(
                    id=exception_id,
                    invoice_id=str(uuid4()),
                    reason_code="TEST_CODE",
                    category=ExceptionCategory.DATA_QUALITY,
                    severity=ExceptionSeverity.WARNING,
                    status=ExceptionStatus.RESOLVED,
                    message="Bulk resolved",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    resolved_at=datetime.utcnow(),
                    resolved_by=resolution_request.resolved_by
                )

            mock_resolve.side_effect = side_effect

            result = await exception_service.batch_resolve_exceptions(
                exception_ids=exception_ids,
                batch_request=batch_request,
                session=mock_session
            )

            assert len(result.resolved_exceptions) == 3
            assert result.success_count == 3
            assert all(exc.resolved_by == "supervisor_user" for exc in result.resolved_exceptions)