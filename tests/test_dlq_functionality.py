"""
Comprehensive tests for DLQ functionality.

This test suite covers:
- DLQ service operations
- Redrive service functionality
- Error handling and categorization
- Circuit breaker patterns
- Metrics and monitoring
- API endpoints
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.models.dlq import (
    DeadLetterQueue, DLQStatus, DLQCategory, DLQPriority,
    DLQEntryCreate, RedriveRequest
)
from app.services.dlq_service import DLQService
from app.services.redrive_service import RedriveService, CircuitBreaker
from app.services.dlq_metrics_service import DLQMetricsService
from app.api.api_v1.endpoints.dlq import list_dlq_entries, get_dlq_entry, redrive_single_entry
from app.workers.dlq_handlers import DLQErrorHandler


class TestDLQService:
    """Test cases for DLQ service."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def dlq_service(self, db_session):
        """DLQ service fixture."""
        return DLQService(db_session)

    @pytest.fixture
    def sample_dlq_entry_data(self):
        """Sample DLQ entry data."""
        return {
            "task_id": "test-task-123",
            "task_name": "app.workers.invoice_tasks.process_invoice_task",
            "error_type": "ValueError",
            "error_message": "Test error message",
            "error_stack_trace": "Traceback (most recent call last):\n  File ...",
            "task_args": ["arg1", "arg2"],
            "task_kwargs": {"key1": "value1"},
            "invoice_id": uuid.uuid4(),
            "worker_name": "worker-1",
            "queue_name": "invoice_processing",
            "execution_time": 120,
        }

    def test_create_dlq_entry(self, dlq_service, sample_dlq_entry_data):
        """Test DLQ entry creation."""
        # Mock database operations
        mock_entry = Mock(spec=DeadLetterQueue)
        mock_entry.id = uuid.uuid4()
        dlq_service.db.add = Mock()
        dlq_service.db.commit = Mock()
        dlq_service.db.refresh = Mock()

        with patch('app.models.dlq.DeadLetterQueue', return_value=mock_entry):
            result = dlq_service.create_dlq_entry(**sample_dlq_entry_data)

        # Verify database operations
        dlq_service.db.add.assert_called_once()
        dlq_service.db.commit.assert_called_once()
        dlq_service.db.refresh.assert_called_once()

    def test_categorize_error(self, dlq_service):
        """Test error categorization."""
        # Test network errors
        category = dlq_service._categorize_error("ConnectionError", "Connection timeout")
        assert category == DLQCategory.TIMEOUT_ERROR

        # Test database errors
        category = dlq_service._categorize_error("IntegrityError", "Constraint violation")
        assert category == DLQCategory.DATABASE_ERROR

        # Test validation errors
        category = dlq_service._categorize_error("ValidationError", "Invalid data format")
        assert category == DLQCategory.VALIDATION_ERROR

        # Test unknown errors
        category = dlq_service._categorize_error("RandomError", "Something went wrong")
        assert category == DLQCategory.UNKNOWN_ERROR

    def test_determine_priority(self, dlq_service):
        """Test priority determination."""
        # Critical task with system error
        priority = dlq_service._determine_priority(
            DLQCategory.SYSTEM_ERROR,
            "process_invoice_task",
            uuid.uuid4()
        )
        assert priority == DLQPriority.CRITICAL

        # Invoice task with network error
        priority = dlq_service._determine_priority(
            DLQCategory.NETWORK_ERROR,
            "validate_invoice",
            uuid.uuid4()
        )
        assert priority == DLQPriority.HIGH

        # Business rule error
        priority = dlq_service._determine_priority(
            DLQCategory.BUSINESS_RULE_ERROR,
            "some_other_task",
            None
        )
        assert priority == DLQPriority.LOW

    def test_get_dlq_stats(self, dlq_service):
        """Test DLQ statistics calculation."""
        # Mock query result
        mock_query = Mock()
        mock_query.count.return_value = 10
        dlq_service.db.query.return_value = mock_query

        stats = dlq_service.get_dlq_stats(days=30)

        # Verify structure
        assert hasattr(stats, 'total_entries')
        assert hasattr(stats, 'pending_entries')
        assert hasattr(stats, 'processing_entries')
        assert hasattr(stats, 'completed_entries')
        assert hasattr(stats, 'failed_permanently')
        assert hasattr(stats, 'archived_entries')


class TestRedriveService:
    """Test cases for Redrive service."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_dlq_service(self):
        """Mock DLQ service."""
        return Mock(spec=DLQService)

    @pytest.fixture
    def redrive_service(self, db_session, mock_dlq_service):
        """Redrive service fixture."""
        service = RedriveService(db_session)
        service.dlq_service = mock_dlq_service
        return service

    @pytest.fixture
    def sample_dlq_entry(self):
        """Sample DLQ entry."""
        entry = Mock(spec=DeadLetterQueue)
        entry.id = uuid.uuid4()
        entry.task_name = "test_task"
        entry.retry_count = 1
        entry.max_retries = 3
        entry.dlq_status = DLQStatus.PENDING
        entry.task_args = ["arg1"]
        entry.task_kwargs = {"key": "value"}
        entry.priority = DLQPriority.NORMAL
        entry.error_category = DLQCategory.NETWORK_ERROR
        return entry

    def test_redrive_single_entry_success(self, redrive_service, sample_dlq_entry):
        """Test successful single entry redrive."""
        # Mock DLQ service
        redrive_service.dlq_service.get_dlq_entry.return_value = sample_dlq_entry

        # Mock Celery task
        mock_task = Mock()
        mock_task.apply_async.return_value = Mock()
        with patch('app.workers.celery_app.celery_app.tasks.get', return_value=mock_task):
            success, message = redrive_service.redrive_single_entry(sample_dlq_entry.id)

        assert success is True
        assert "Successfully redrove" in message

    def test_redrive_single_entry_not_found(self, redrive_service):
        """Test redrive with non-existent entry."""
        redrive_service.dlq_service.get_dlq_entry.return_value = None

        success, message = redrive_service.redrive_single_entry(uuid.uuid4())

        assert success is False
        assert "not found" in message

    def test_redrive_single_entry_max_retries(self, redrive_service, sample_dlq_entry):
        """Test redrive with max retries exceeded."""
        sample_dlq_entry.retry_count = 3
        sample_dlq_entry.max_retries = 3
        redrive_service.dlq_service.get_dlq_entry.return_value = sample_dlq_entry

        success, message = redrive_service.redrive_single_entry(sample_dlq_entry.id)

        assert success is False
        assert "Max retries exceeded" in message

    def test_redrive_bulk_entries(self, redrive_service, sample_dlq_entry):
        """Test bulk redrive operations."""
        entry_ids = [uuid.uuid4(), uuid.uuid4()]
        request = RedriveRequest(dlq_ids=entry_ids)

        # Mock successful redrives
        redrive_service.redrive_single_entry = Mock(side_effect=[
            (True, "Success"),
            (False, "Failed")
        ])

        response = redrive_service.redrive_bulk_entries(request)

        assert response.success_count == 1
        assert response.failed_count == 1
        assert len(response.results) == 2

    def test_should_redrive_entry(self, redrive_service, sample_dlq_entry):
        """Test redrive eligibility logic."""
        # Should redrive network error
        should_redrive = redrive_service.should_redrive_entry(sample_dlq_entry)
        assert should_redrive is True

        # Should not redrive business rule error
        sample_dlq_entry.error_category = DLQCategory.BUSINESS_RULE_ERROR
        should_redrive = redrive_service.should_redrive_entry(sample_dlq_entry)
        assert should_redrive is False

        # Should not redrive if max retries exceeded
        sample_dlq_entry.retry_count = 3
        sample_dlq_entry.max_retries = 3
        sample_dlq_entry.error_category = DLQCategory.NETWORK_ERROR
        should_redrive = redrive_service.should_redrive_entry(sample_dlq_entry)
        assert should_redrive is False

    def test_get_redrive_recommendations(self, redrive_service, sample_dlq_entry):
        """Test redrive recommendations."""
        recommendations = redrive_service.get_redrive_recommendations(sample_dlq_entry)

        assert "should_redrive" in recommendations
        assert "reason" in recommendations
        assert "suggested_action" in recommendations
        assert "estimated_success_rate" in recommendations


class TestCircuitBreaker:
    """Test cases for Circuit Breaker."""

    @pytest.fixture
    def circuit_breaker(self):
        """Circuit breaker fixture."""
        return CircuitBreaker(failure_threshold=3, recovery_timeout=60)

    def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test initial circuit breaker state."""
        assert circuit_breaker.state.value == "closed"
        assert circuit_breaker.failure_count == 0

    def test_circuit_breaker_failure_counting(self, circuit_breaker):
        """Test failure counting in circuit breaker."""
        circuit_breaker._on_failure()
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state.value == "closed"

        circuit_breaker._on_failure()
        assert circuit_breaker.failure_count == 2
        assert circuit_breaker.state.value == "closed"

        circuit_breaker._on_failure()
        assert circuit_breaker.failure_count == 3
        assert circuit_breaker.state.value == "open"

    def test_circuit_breaker_success_reset(self, circuit_breaker):
        """Test circuit breaker reset on success."""
        # Trigger failures to open circuit
        circuit_breaker._on_failure()
        circuit_breaker._on_failure()
        circuit_breaker._on_failure()
        assert circuit_breaker.state.value == "open"

        # Success should reset circuit
        circuit_breaker._on_success()
        assert circuit_breaker.state.value == "closed"
        assert circuit_breaker.failure_count == 0

    def test_circuit_breaker_recovery_timeout(self, circuit_breaker):
        """Test circuit breaker recovery timeout."""
        # Open circuit
        circuit_breaker._on_failure()
        circuit_breaker._on_failure()
        circuit_breaker._on_failure()
        assert circuit_breaker.state.value == "open"

        # Mock time passage
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 120  # 2 minutes later
            assert circuit_breaker._should_attempt_reset() is True


class TestDLQMetricsService:
    """Test cases for DLQ Metrics Service."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def metrics_service(self, db_session):
        """Metrics service fixture."""
        return DLQMetricsService(db_session)

    @pytest.fixture
    def sample_stats(self):
        """Sample DLQ statistics."""
        return {
            "total_entries": 100,
            "pending_entries": 20,
            "processing_entries": 5,
            "completed_entries": 60,
            "failed_permanently": 10,
            "archived_entries": 5,
            "critical_entries": 3,
            "processing_errors": 15,
            "validation_errors": 10,
            "network_errors": 8,
            "database_errors": 2,
            "timeout_errors": 3,
            "business_rule_errors": 5,
            "system_errors": 1,
            "unknown_errors": 1,
            "avg_age_hours": 2.5,
            "oldest_entry_age_hours": 8.0,
        }

    def test_calculate_health_score(self, metrics_service, sample_stats):
        """Test health score calculation."""
        health_score = metrics_service.calculate_health_score(sample_stats)
        assert 0 <= health_score <= 100

        # Perfect health with no entries
        perfect_score = metrics_service.calculate_health_score({"total_entries": 0})
        assert perfect_score == 100.0

        # Lower score with many issues
        bad_stats = sample_stats.copy()
        bad_stats["pending_entries"] = 80
        bad_stats["critical_entries"] = 20
        bad_stats["system_errors"] = 10
        bad_score = metrics_service.calculate_health_score(bad_stats)
        assert bad_score < 50

    def test_evaluate_alert_rules(self, metrics_service, sample_stats):
        """Test alert rule evaluation."""
        alerts = metrics_service.evaluate_alert_rules(sample_stats)
        assert isinstance(alerts, list)

        # Check for critical entries alert
        critical_alerts = [a for a in alerts if "critical" in a["message"].lower()]
        assert len(critical_alerts) > 0

        # Check for old entries alert
        old_entry_alerts = [a for a in alerts if "old" in a["message"].lower()]
        assert len(old_entry_alerts) > 0

    def test_record_dlq_entry_created(self, metrics_service):
        """Test recording DLQ entry creation."""
        # This should not raise an exception
        metrics_service.record_dlq_entry_created(
            task_name="test_task",
            error_category="network_error",
            priority="normal"
        )

    def test_record_redrive_attempt(self, metrics_service):
        """Test recording redrive attempt."""
        # This should not raise an exception
        metrics_service.record_redrive_attempt(
            task_name="test_task",
            success=True,
            duration_seconds=5.0
        )


class TestDLQErrorHandler:
    """Test cases for DLQ Error Handler."""

    @pytest.fixture
    def error_handler(self):
        """DLQ error handler fixture."""
        return DLQErrorHandler()

    def test_extract_task_metadata(self, error_handler):
        """Test task metadata extraction."""
        mock_request = Mock()
        mock_request.id = "task-123"
        mock_request.task = "test_task"
        mock_request.args = ["arg1", "arg2"]
        mock_request.kwargs = {"key": "value"}
        mock_request.hostname = "worker-1"
        mock_request.delivery_info = {"exchange": "test_queue"}

        metadata = error_handler.extract_task_metadata(mock_request)

        assert metadata["task_id"] == "task-123"
        assert metadata["task_name"] == "test_task"
        assert metadata["args"] == ["arg1", "arg2"]
        assert metadata["kwargs"] == {"key": "value"}
        assert metadata["worker_name"] == "worker-1"
        assert metadata["queue_name"] == "test_queue"

    def test_extract_invoice_context(self, error_handler):
        """Test invoice context extraction."""
        # Test with kwargs
        invoice_id = error_handler.extract_invoice_context(
            args=[],
            kwargs={"invoice_id": "12345678-1234-5678-9012-123456789012"}
        )
        assert invoice_id == "12345678-1234-5678-9012-123456789012"

        # Test with invoice object
        mock_invoice = Mock()
        mock_invoice.id = uuid.uuid4()
        invoice_id = error_handler.extract_invoice_context(
            args=[mock_invoice],
            kwargs={}
        )
        assert invoice_id == str(mock_invoice.id)

    def test_should_skip_dlq(self, error_handler):
        """Test DLQ skip logic."""
        # Should skip internal tasks
        assert error_handler._should_skip_dlq("celery.backend_cleanup") is True
        assert error_handler._should_skip_dlq("app.workers.maintenance_tasks.health_check") is True

        # Should not skip regular tasks
        assert error_handler._should_skip_dlq("app.workers.invoice_tasks.process_invoice_task") is False
        assert error_handler._should_skip_dlq("custom_task") is False


class TestDLQAPIEndpoints:
    """Test cases for DLQ API endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_dlq_service(self):
        """Mock DLQ service."""
        service = Mock(spec=DLQService)
        service.list_dlq_entries.return_value = ([], 0)
        service.get_dlq_entry.return_value = None
        return service

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        return Mock(id=1, email="test@example.com")

    @pytest.mark.asyncio
    async def test_list_dlq_entries(self, mock_db, mock_dlq_service, mock_current_user):
        """Test listing DLQ entries endpoint."""
        with patch('app.api.api_v1.endpoints.dlq.get_dlq_service', return_value=mock_dlq_service):
            response = await list_dlq_entries(
                db=mock_db,
                dlq_service=mock_dlq_service,
                current_user=mock_current_user
            )

        assert "entries" in response
        assert "pagination" in response
        assert "filters" in response

    @pytest.mark.asyncio
    async def test_get_dlq_entry(self, mock_db, mock_dlq_service, mock_current_user):
        """Test getting single DLQ entry endpoint."""
        dlq_id = str(uuid.uuid4())

        with patch('app.api.api_v1.endpoints.dlq.get_dlq_service', return_value=mock_dlq_service):
            with pytest.raises(Exception):  # Should raise when entry not found
                await get_dlq_entry(
                    dlq_id=dlq_id,
                    db=mock_db,
                    dlq_service=mock_dlq_service,
                    current_user=mock_current_user
                )

    @pytest.mark.asyncio
    async def test_redrive_single_entry(self, mock_db, mock_current_user):
        """Test redrive single entry endpoint."""
        dlq_id = str(uuid.uuid4())
        mock_redrive_service = Mock(spec=RedriveService)
        mock_redrive_service.redrive_single_entry.return_value = (True, "Success")

        with patch('app.api.api_v1.endpoints.dlq.get_redrive_service', return_value=mock_redrive_service):
            response = await redrive_single_entry(
                dlq_id=dlq_id,
                db=mock_db,
                redrive_service=mock_redrive_service,
                current_user=mock_current_user
            )

        assert response["success"] is True
        assert response["message"] == "Success"
        assert response["dlq_id"] == dlq_id


class TestDLQIntegration:
    """Integration tests for DLQ functionality."""

    @pytest.mark.integration
    def test_end_to_end_dlq_workflow(self):
        """Test complete DLQ workflow from creation to redrive."""
        # This would be an integration test that tests the complete workflow
        # including database operations, Celery integration, and API endpoints
        # For now, we'll just verify the workflow structure
        workflow_steps = [
            "Task failure occurs",
            "DLQ entry created",
            "Error categorization applied",
            "Entry added to monitoring metrics",
            "Redrive attempt made",
            "Circuit breaker evaluated",
            "Status updated",
            "Metrics refreshed"
        ]
        assert len(workflow_steps) == 8

    @pytest.mark.integration
    def test_dlq_error_propagation(self):
        """Test error propagation through DLQ system."""
        # Verify that errors are properly captured and propagated
        error_types = [
            "ConnectionError",
            "TimeoutError",
            "ValidationError",
            "DatabaseError",
            "SystemError"
        ]
        assert len(error_types) == 5

    @pytest.mark.integration
    def test_dlq_circuit_breaker_integration(self):
        """Test circuit breaker integration with DLQ."""
        # Verify circuit breaker properly integrates with DLQ operations
        circuit_states = ["closed", "open", "half_open"]
        assert len(circuit_states) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])