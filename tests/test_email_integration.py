"""
Tests for email integration functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.gmail_service import GmailService, GmailCredentials
from app.services.email_ingestion_service import EmailIngestionService
from app.core.config import settings


class TestGmailService:
    """Test Gmail API service."""

    @pytest.fixture
    def gmail_service(self):
        """Create Gmail service instance."""
        return GmailService()

    @pytest.mark.asyncio
    async def test_get_authorization_url(self, gmail_service):
        """Test getting authorization URL."""
        with patch.object(gmail_service, 'client_id', 'test_client_id'), \
             patch.object(gmail_service, 'client_secret', 'test_client_secret'):

            authorization_url, state = await gmail_service.get_authorization_url(
                redirect_uri="http://localhost:8000/callback",
                state="test_state"
            )

            assert authorization_url is not None
            assert "accounts.google.com" in authorization_url
            assert state == "test_state"

    @pytest.mark.asyncio
    async def test_build_service(self, gmail_service):
        """Test building Gmail service."""
        credentials = GmailCredentials(
            token="test_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )

        with patch('app.services.gmail_service.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            await gmail_service.build_service(credentials)

            assert gmail_service.service == mock_service
            mock_build.assert_called_once_with('gmail', 'v1', credentials=pytest.ANY)

    @pytest.mark.asyncio
    async def test_get_user_info(self, gmail_service):
        """Test getting user information."""
        mock_service = MagicMock()
        gmail_service.service = mock_service

        mock_profile = {
            "emailAddress": "test@example.com",
            "historyId": "12345",
            "messagesTotal": 100,
            "threadsTotal": 50
        }
        mock_service.users().getProfile().execute.return_value = mock_profile

        user_info = await gmail_service.get_user_info()

        assert user_info["email_address"] == "test@example.com"
        assert user_info["messages_total"] == 100


class TestEmailIngestionService:
    """Test email ingestion service."""

    @pytest.fixture
    def ingestion_service(self):
        """Create email ingestion service instance."""
        return EmailIngestionService()

    def test_validate_email_security(self, ingestion_service):
        """Test email security validation."""
        # Create mock message with malicious content
        mock_message = MagicMock()
        mock_message.subject = "URGENT: Click here now!"
        mock_message.body = "You have won bitcoin! Click here: http://malicious.com"
        mock_message.from_email = "attacker@malicious.com"
        mock_message.attachments = [MagicMock() for _ in range(15)]  # Too many attachments

        security_flags = ingestion_service._validate_email_security(mock_message)

        assert "malicious_pattern" in " ".join(security_flags)
        assert "untrusted_sender" in " ".join(security_flags)
        assert "excessive_attachments" in " ".join(security_flags)

    def test_is_email_blocked(self, ingestion_service):
        """Test email blocking logic."""
        # Email with critical flags should be blocked
        critical_flags = ["malicious_pattern: urgent", "excessive_urls"]
        assert ingestion_service._is_email_blocked(critical_flags) is True

        # Email with non-critical flags should not be blocked
        safe_flags = ["untrusted_sender"]
        assert ingestion_service._is_email_blocked(safe_flags) is False

    def test_extract_vendor_name(self, ingestion_service):
        """Test vendor name extraction."""
        subject = "Invoice from Acme Corporation for services"
        filename = "acme_invoice_123.pdf"

        vendor = ingestion_service._extract_vendor_name(subject, filename)

        assert vendor is not None
        assert "Acme" in vendor

    def test_generate_email_hash(self, ingestion_service):
        """Test email hash generation."""
        mock_message = MagicMock()
        mock_message.from_email = "sender@example.com"
        mock_message.subject = "Test Invoice"
        mock_message.date = "2024-01-01"

        email_hash = ingestion_service._generate_email_hash(mock_message)

        assert email_hash is not None
        assert len(email_hash) == 64  # SHA-256 hash length

    @pytest.mark.asyncio
    async def test_health_check(self, ingestion_service):
        """Test health check functionality."""
        health_status = await ingestion_service.health_check()

        assert "status" in health_status
        assert "gmail_service_configured" in health_status
        assert "storage_service_available" in health_status
        assert "timestamp" in health_status


class TestEmailIntegration:
    """Test end-to-end email integration."""

    @pytest.mark.asyncio
    async def test_full_email_processing_flow(self):
        """Test complete email processing flow."""
        # This would be a comprehensive integration test
        # For now, just test the service creation
        ingestion_service = EmailIngestionService()
        gmail_service = GmailService()

        assert ingestion_service is not None
        assert gmail_service is not None

        # Test configuration
        assert settings.GMAIL_CLIENT_ID is not None
        assert settings.GMAIL_CLIENT_SECRET is not None
        assert settings.EMAIL_INGESTION_ENABLED is True

    def test_email_filters_creation(self):
        """Test email filter creation."""
        ingestion_service = EmailIngestionService()
        filters = ingestion_service.create_email_filters()

        assert isinstance(filters, list)
        assert len(filters) > 0
        assert any("invoice" in f.lower() for f in filters)

    def test_trusted_domains_pattern(self):
        """Test trusted domain patterns."""
        ingestion_service = EmailIngestionService()

        # Test trusted domain matching
        for pattern in ingestion_service.trusted_domains:
            import re
            assert re.match(pattern, "quickbooks.com") is not None or \
                   re.match(pattern, "xero.com") is not None


class TestEmailTasks:
    """Test email background tasks."""

    @pytest.mark.asyncio
    async def test_email_monitoring_task_creation(self):
        """Test email monitoring task creation."""
        from app.workers.email_tasks import monitor_gmail_inbox

        # Test task creation (not execution)
        task = monitor_gmail_inbox.s(
            user_id="test_user",
            credentials_data={
                "token": "test_token",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
            },
            days_back=7,
            max_emails=25,
            auto_process=True
        )

        assert task is not None
        assert task.args[0] == "test_user"
        assert task.args[2] == 7  # days_back

    def test_task_management_functions(self):
        """Test task management utility functions."""
        from app.workers.email_tasks import (
            get_email_monitoring_task_status,
            cancel_email_monitoring,
            get_active_email_tasks
        )

        # These functions should not raise exceptions
        status = get_email_monitoring_task_status("test_user")
        assert status is None  # No active task for test user

        cancelled = cancel_email_monitoring("test_user")
        assert cancelled is False  # No active task to cancel

        active_tasks = get_active_email_tasks()
        assert isinstance(active_tasks, list)


if __name__ == "__main__":
    pytest.main([__file__])