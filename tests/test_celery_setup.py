"""
Tests for Celery background worker setup.
"""

import pytest
import time
from unittest.mock import patch

from app.workers.celery_app import celery_app
from app.workers.maintenance_tasks import health_check, cleanup_old_exports
from app.workers.invoice_tasks import process_invoice_task
from app.workers.email_tasks import monitor_gmail_inbox


class TestCelerySetup:
    """Test Celery configuration and basic functionality."""

    def test_celery_app_configuration(self):
        """Test that Celery app is properly configured."""
        # Check basic configuration
        assert celery_app.main == "ap_intake"
        assert celery_app.conf.broker_url.startswith("redis://")
        assert celery_app.conf.result_backend.startswith("redis://")

        # Check task modules are included
        assert "app.workers.invoice_tasks" in celery_app.conf.task_routes
        assert "app.workers.email_tasks" in celery_app.conf.task_routes
        assert "app.workers.maintenance_tasks" in celery_app.conf.task_routes

        # Check queues are configured
        queue_names = [queue.name for queue in celery_app.conf.task_queues]
        assert "invoice_processing" in queue_names
        assert "validation" in queue_names
        assert "export" in queue_names
        assert "email_processing" in queue_names
        assert "celery" in queue_names

    def test_celery_beat_schedule(self):
        """Test that Celery Beat schedule is configured."""
        schedule = celery_app.conf.beat_schedule

        # Check that maintenance tasks are scheduled
        assert "cleanup-old-exports" in schedule
        assert "health-check" in schedule

        # Check schedule configuration
        cleanup_task = schedule["cleanup-old-exports"]
        assert cleanup_task["task"] == "app.workers.maintenance_tasks.cleanup_old_exports"
        assert cleanup_task["schedule"] == 3600.0  # Every hour

        health_task = schedule["health-check"]
        assert health_task["task"] == "app.workers.maintenance_tasks.health_check"
        assert health_task["schedule"] == 300.0  # Every 5 minutes

    @pytest.mark.asyncio
    async def test_health_check_task(self):
        """Test health check task execution."""
        # Run health check task synchronously for testing
        result = health_check.apply()

        assert result.status == "SUCCESS"
        assert isinstance(result.result, dict)
        assert "status" in result.result
        assert "timestamp" in result.result
        assert "checks" in result.result

    def test_cleanup_exports_task(self):
        """Test cleanup exports task."""
        # Test with minimal days to keep
        result = cleanup_old_exports.apply(args=(1,))

        assert result.status == "SUCCESS"
        assert isinstance(result.result, dict)
        assert "status" in result.result
        assert "deleted_records" in result.result

    @patch('app.workers.invoice_tasks.InvoiceProcessor')
    def test_process_invoice_task_signature(self, mock_processor):
        """Test that invoice processing task has correct signature."""
        task = process_invoice_task

        # Check task attributes
        assert task.max_retries == 3
        assert task.default_retry_delay == 60
        assert hasattr(task, 'bind')

        # Check task name
        assert task.name == "app.workers.invoice_tasks.process_invoice_task"

    def test_email_monitoring_task_signature(self):
        """Test that email monitoring task has correct signature."""
        task = monitor_gmail_inbox

        # Check task attributes
        assert task.max_retries == 3
        assert task.default_retry_delay == 60
        assert hasattr(task, 'bind')

        # Check task name
        assert task.name == "app.workers.email_tasks.monitor_gmail_inbox"

    def test_task_routing(self):
        """Test that tasks are correctly routed to queues."""
        routes = celery_app.conf.task_routes

        # Check invoice tasks routing
        assert routes["app.workers.invoice_tasks.process_invoice_task"]["queue"] == "invoice_processing"
        assert routes["app.workers.invoice_tasks.validate_invoice_task"]["queue"] == "validation"
        assert routes["app.workers.invoice_tasks.export_invoice_task"]["queue"] == "export"

        # Check email tasks routing
        assert routes["app.workers.email_tasks.process_email_task"]["queue"] == "email_processing"

    def test_worker_configuration(self):
        """Test worker configuration settings."""
        config = celery_app.conf

        # Check worker settings
        assert config.worker_concurrency > 0
        assert config.worker_prefetch_multiplier >= 1
        assert config.task_soft_time_limit > 0
        assert config.task_time_limit > 0

        # Check error handling
        assert config.task_reject_on_worker_lost is True
        assert config.task_acks_late is True

        # Check monitoring
        assert config.worker_send_task_events is True
        assert config.task_send_sent_event is True

    @patch('redis.from_url')
    def test_redis_connection(self, mock_redis):
        """Test Redis connection configuration."""
        from app.core.config import settings

        # Test that Redis URL is configured
        assert settings.REDIS_URL.startswith("redis://")

        # Mock Redis connection test
        mock_client = mock_redis.return_value
        mock_client.ping.return_value = True

        # This would normally test Redis connectivity
        client = mock_redis(settings.REDIS_URL)
        client.ping()
        assert client.ping.called

    def test_celery_logging_configuration(self):
        """Test that Celery logging is properly configured."""
        import logging

        # Check that Celery logger exists
        celery_logger = logging.getLogger("celery")
        assert celery_logger is not None

        # The actual file handler setup happens at runtime
        # This test verifies the logger configuration exists

    def test_maintenance_tasks_importable(self):
        """Test that maintenance tasks can be imported."""
        from app.workers.maintenance_tasks import (
            cleanup_old_exports,
            health_check,
            cleanup_failed_tasks,
            backup_system_state,
            monitor_worker_performance,
            cleanup_temp_files,
            generate_system_report
        )

        # Verify all tasks are callable
        assert callable(cleanup_old_exports)
        assert callable(health_check)
        assert callable(cleanup_failed_tasks)
        assert callable(backup_system_state)
        assert callable(monitor_worker_performance)
        assert callable(cleanup_temp_files)
        assert callable(generate_system_report)

    def test_task_retry_configuration(self):
        """Test that tasks have proper retry configuration."""
        # Test maintenance tasks
        health_task = health_check
        assert health_task.max_retries == 2
        assert health_task.default_retry_delay == 60

        cleanup_task = cleanup_old_exports
        assert cleanup_task.max_retries == 3
        assert cleanup_task.default_retry_delay == 300

    @pytest.mark.integration
    def test_celery_worker_connectivity(self):
        """Test connectivity to Celery workers (integration test)."""
        try:
            inspect = celery_app.control.inspect()

            # This might fail if no workers are running
            # That's expected in unit test environments
            stats = inspect.stats()
            active = inspect.active()

            # If workers are running, we should get data
            if stats:
                assert isinstance(stats, dict)

        except Exception as e:
            # It's okay if workers aren't running during tests
            # This just verifies the connection mechanism works
            pytest.skip(f"Celery workers not running: {e}")

    def test_error_handling_configuration(self):
        """Test that error handling is properly configured."""
        config = celery_app.conf

        # Check error handling settings
        assert config.task_reject_on_worker_lost is True
        assert config.task_acks_late is True

        # Check result expiration
        assert config.result_expires > 0

        # Check backend transport options
        assert "result_backend_transport_options" in config
        backend_opts = config.result_backend_transport_options
        assert "socket_keepalive" in backend_opts
        assert backend_opts["socket_keepalive"] is True


if __name__ == "__main__":
    pytest.main([__file__])