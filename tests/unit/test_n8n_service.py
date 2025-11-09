"""
Test suite for n8n integration service using TDD approach.
This file tests n8n client functionality, workflow triggers, webhook handlers,
and workflow template management with comprehensive coverage.
"""

import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

# Mock the imports for testing
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Test imports will be mocked
N8nService = None
N8nWorkflowException = None
N8nConnectionException = None
N8nWorkflowExecutionRequest = None
N8nWebhookEvent = None
N8nWorkflowTemplate = None
N8nWorkflowTrigger = None
N8nExecutionStatus = None
N8nWorkflowType = None


class TestN8nService:
    """Test suite for n8n service functionality."""

    @pytest.fixture
    def n8n_service(self):
        """Create n8n service instance for testing."""
        return N8nService()

    @pytest.fixture
    def mock_ap_invoice_data(self):
        """Sample AP invoice data for workflow triggers."""
        return {
            "invoice_id": "test_invoice_123",
            "vendor_id": "vendor_456",
            "amount": 1250.00,
            "due_date": "2024-12-15",
            "status": "processed",
            "extraction_result": {
                "header": {
                    "invoice_number": "INV-2024-001",
                    "vendor_name": "Test Vendor Inc",
                    "total_amount": 1250.00,
                    "invoice_date": "2024-12-01"
                },
                "lines": [
                    {
                        "description": "Professional Services",
                        "quantity": 10,
                        "unit_price": 125.00,
                        "total": 1250.00
                    }
                ]
            },
            "validation_result": {
                "passed": True,
                "confidence_score": 0.95,
                "issues": []
            }
        }

    @pytest.fixture
    def mock_ar_invoice_data(self):
        """Sample AR invoice data for workflow triggers."""
        return {
            "invoice_id": "ar_invoice_789",
            "customer_id": "customer_101",
            "amount": 3500.00,
            "due_date": "2024-12-20",
            "status": "sent",
            "customer_details": {
                "name": "Test Customer LLC",
                "email": "billing@testcustomer.com"
            }
        }

    @pytest.fixture
    def mock_webhook_event(self):
        """Sample webhook event from n8n."""
        return N8nWebhookEvent(
            workflow_id="workflow_123",
            execution_id="execution_456",
            status="success",
            timestamp=datetime.utcnow(),
            data={"result": "processed", "next_step": "export"}
        )

    @pytest.fixture
    def mock_workflow_template(self):
        """Sample workflow template."""
        return N8nWorkflowTemplate(
            id="template_ap_processing",
            name="AP Invoice Processing Workflow",
            description="Automated processing of AP invoices with validation and export",
            workflow_type=N8nWorkflowType.AP_PROCESSING,
            version="1.0.0",
            triggers=[
                N8nWorkflowTrigger(
                    type="webhook",
                    config={"path": "/webhooks/ap-invoice"}
                )
            ],
            nodes=[
                {
                    "id": "validate_invoice",
                    "type": "function",
                    "config": {"operation": "validate_invoice_data"}
                },
                {
                    "id": "export_to_erp",
                    "type": "action",
                    "config": {"system": "quickbooks"}
                }
            ]
        )


class TestN8nClient:
    """Test suite for n8n client functionality."""

    @pytest.mark.asyncio
    async def test_n8n_client_initialization(self, n8n_service):
        """Test n8n client initialization with proper configuration."""
        assert n8n_service.base_url is not None
        assert n8n_service.api_key is not None or n8n_service.username is not None
        assert n8n_service.session is not None

    @pytest.mark.asyncio
    async def test_n8n_connection_success(self, n8n_service):
        """Test successful connection to n8n instance."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {"status": "ok", "version": "1.0.0"}

            result = await n8n_service.test_connection()

            assert result["status"] == "ok"
            assert "version" in result
            mock_request.assert_called_once_with("GET", "/rest/health")

    @pytest.mark.asyncio
    async def test_n8n_connection_failure(self, n8n_service):
        """Test connection failure handling."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.side_effect = N8nConnectionException("Connection failed")

            with pytest.raises(N8nConnectionException):
                await n8n_service.test_connection()

    @pytest.mark.asyncio
    async def test_n8n_authentication_with_api_key(self, n8n_service):
        """Test n8n authentication using API key."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {"authenticated": True}

            result = await n8n_service.authenticate()

            assert result["authenticated"] is True
            # Verify API key is in headers
            call_kwargs = mock_request.call_args[1]
            assert "headers" in call_kwargs

    @pytest.mark.asyncio
    async def test_n8n_authentication_with_credentials(self, n8n_service):
        """Test n8n authentication using username/password."""
        n8n_service.api_key = None
        n8n_service.username = "test_user"
        n8n_service.password = "test_pass"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {"authenticated": True, "token": "jwt_token"}

            result = await n8n_service.authenticate()

            assert result["authenticated"] is True
            assert result["token"] == "jwt_token"

    @pytest.mark.asyncio
    async def test_api_key_rotation(self, n8n_service):
        """Test API key rotation functionality."""
        new_api_key = "new_test_api_key"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {"success": True, "api_key": new_api_key}

            result = await n8n_service.rotate_api_key(new_api_key)

            assert result["success"] is True
            assert n8n_service.api_key == new_api_key

    @pytest.mark.asyncio
    async def test_error_handling_and_retries(self, n8n_service):
        """Test error handling with retry logic."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            # First two calls fail, third succeeds
            mock_request.side_effect = [
                N8nConnectionException("Temporary failure"),
                N8nConnectionException("Temporary failure"),
                {"status": "success"}
            ]

            result = await n8n_service._make_request_with_retry("GET", "/test", max_retries=3)

            assert result["status"] == "success"
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, n8n_service):
        """Test behavior when max retries are exceeded."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.side_effect = N8nConnectionException("Persistent failure")

            with pytest.raises(N8nConnectionException):
                await n8n_service._make_request_with_retry("GET", "/test", max_retries=2)

    @pytest.mark.asyncio
    async def test_request_signature_validation(self, n8n_service):
        """Test webhook signature validation."""
        webhook_secret = "test_webhook_secret"
        payload = {"test": "data"}

        # Mock signature generation
        with patch('hmac.new') as mock_hmac:
            mock_hmac.return_value.hexdigest.return_value = "valid_signature"

            result = n8n_service.validate_webhook_signature(
                payload=payload,
                signature="valid_signature",
                secret=webhook_secret
            )

            assert result is True
            mock_hmac.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_webhook_signature(self, n8n_service):
        """Test rejection of invalid webhook signatures."""
        webhook_secret = "test_webhook_secret"
        payload = {"test": "data"}

        result = n8n_service.validate_webhook_signature(
            payload=payload,
            signature="invalid_signature",
            secret=webhook_secret
        )

        assert result is False


class TestWorkflowTriggers:
    """Test suite for workflow trigger functionality."""

    @pytest.mark.asyncio
    async def test_trigger_ap_invoice_workflow(self, n8n_service, mock_ap_invoice_data):
        """Test triggering AP invoice processing workflow."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_123",
                "status": "running",
                "workflowId": "workflow_ap_123"
            }

            request = N8nWorkflowExecutionRequest(
                workflow_id="workflow_ap_123",
                data=mock_ap_invoice_data
            )

            result = await n8n_service.trigger_workflow(request)

            assert result["executionId"] == "exec_123"
            assert result["status"] == "running"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_ar_invoice_workflow(self, n8n_service, mock_ar_invoice_data):
        """Test triggering AR invoice processing workflow."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_456",
                "status": "running",
                "workflowId": "workflow_ar_456"
            }

            request = N8nWorkflowExecutionRequest(
                workflow_id="workflow_ar_456",
                data=mock_ar_invoice_data
            )

            result = await n8n_service.trigger_workflow(request)

            assert result["executionId"] == "exec_456"
            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_trigger_working_capital_analysis(self, n8n_service):
        """Test triggering daily working capital analysis workflow."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_wcap_123",
                "status": "running"
            }

            result = await n8n_service.trigger_working_capital_analysis()

            assert result["executionId"] == "exec_wcap_123"
            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_trigger_customer_onboarding(self, n8n_service):
        """Test triggering customer onboarding workflow."""
        customer_data = {
            "customer_id": "cust_123",
            "name": "New Customer Inc",
            "email": "contact@newcustomer.com"
        }

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_onboard_123",
                "status": "running"
            }

            result = await n8n_service.trigger_customer_onboarding(customer_data)

            assert result["executionId"] == "exec_onboard_123"
            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_trigger_exception_handling(self, n8n_service):
        """Test triggering exception handling workflow."""
        exception_data = {
            "exception_id": "exc_123",
            "invoice_id": "inv_456",
            "severity": "high",
            "description": "Critical validation failure"
        }

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_exc_123",
                "status": "running"
            }

            result = await n8n_service.trigger_exception_handling(exception_data)

            assert result["executionId"] == "exec_exc_123"

    @pytest.mark.asyncio
    async def test_trigger_weekly_report_generation(self, n8n_service):
        """Test triggering weekly report generation workflow."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_report_123",
                "status": "running"
            }

            result = await n8n_service.trigger_weekly_report_generation()

            assert result["executionId"] == "exec_report_123"

    @pytest.mark.asyncio
    async def test_workflow_trigger_with_invalid_data(self, n8n_service):
        """Test workflow trigger with invalid data."""
        invalid_request = N8nWorkflowExecutionRequest(
            workflow_id="",
            data={}
        )

        with pytest.raises(N8nWorkflowException):
            await n8n_service.trigger_workflow(invalid_request)

    @pytest.mark.asyncio
    async def test_workflow_trigger_nonexistent_workflow(self, n8n_service, mock_ap_invoice_data):
        """Test triggering a non-existent workflow."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.side_effect = N8nWorkflowException("Workflow not found")

            request = N8nWorkflowExecutionRequest(
                workflow_id="nonexistent_workflow",
                data=mock_ap_invoice_data
            )

            with pytest.raises(N8nWorkflowException):
                await n8n_service.trigger_workflow(request)


class TestWebhookHandlers:
    """Test suite for webhook handler functionality."""

    @pytest.mark.asyncio
    async def test_process_webhook_event_success(self, n8n_service, mock_webhook_event):
        """Test successful processing of webhook events."""
        with patch.object(n8n_service, 'validate_webhook_signature') as mock_validate:
            mock_validate.return_value = True

            result = await n8n_service.process_webhook_event(mock_webhook_event)

            assert result["status"] == "processed"
            assert result["execution_id"] == mock_webhook_event.execution_id

    @pytest.mark.asyncio
    async def test_process_webhook_event_invalid_signature(self, n8n_service, mock_webhook_event):
        """Test rejection of webhook events with invalid signatures."""
        with patch.object(n8n_service, 'validate_webhook_signature') as mock_validate:
            mock_validate.return_value = False

            with pytest.raises(N8nWorkflowException):
                await n8n_service.process_webhook_event(mock_webhook_event)

    @pytest.mark.asyncio
    async def test_process_webhook_event_with_response_data(self, n8n_service):
        """Test processing webhook events that include response data."""
        webhook_event = N8nWebhookEvent(
            workflow_id="workflow_123",
            execution_id="execution_456",
            status="success",
            timestamp=datetime.utcnow(),
            data={
                "invoice_id": "inv_123",
                "export_result": {"status": "success", "erp_id": "erp_456"},
                "next_actions": ["send_notification", "update_status"]
            }
        )

        with patch.object(n8n_service, 'validate_webhook_signature') as mock_validate:
            mock_validate.return_value = True

            result = await n8n_service.process_webhook_event(webhook_event)

            assert result["status"] == "processed"
            assert "export_result" in result
            assert "next_actions" in result

    @pytest.mark.asyncio
    async def test_process_webhook_event_error_handling(self, n8n_service):
        """Test error handling in webhook processing."""
        webhook_event = N8nWebhookEvent(
            workflow_id="workflow_123",
            execution_id="execution_456",
            status="error",
            timestamp=datetime.utcnow(),
            data={"error": "Processing failed", "details": "Invalid data format"}
        )

        with patch.object(n8n_service, 'validate_webhook_signature') as mock_validate:
            mock_validate.return_value = True

            result = await n8n_service.process_webhook_event(webhook_event)

            assert result["status"] == "error_processed"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_webhook_timeout_handling(self, n8n_service, mock_webhook_event):
        """Test webhook timeout handling."""
        with patch.object(n8n_service, 'validate_webhook_signature') as mock_validate:
            mock_validate.return_value = True

            with patch('asyncio.wait_for') as mock_wait_for:
                mock_wait_for.side_effect = asyncio.TimeoutError()

                with pytest.raises(N8nWorkflowException):
                    await n8n_service.process_webhook_event(mock_webhook_event)


class TestWorkflowTemplateManagement:
    """Test suite for workflow template management."""

    @pytest.mark.asyncio
    async def test_create_workflow_template(self, n8n_service, mock_workflow_template):
        """Test creating a new workflow template."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": "template_123",
                "name": mock_workflow_template.name,
                "status": "created"
            }

            result = await n8n_service.create_workflow_template(mock_workflow_template)

            assert result["id"] == "template_123"
            assert result["name"] == mock_workflow_template.name

    @pytest.mark.asyncio
    async def test_update_workflow_template(self, n8n_service, mock_workflow_template):
        """Test updating an existing workflow template."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": mock_workflow_template.id,
                "version": "1.1.0",
                "status": "updated"
            }

            result = await n8n_service.update_workflow_template(mock_workflow_template)

            assert result["id"] == mock_workflow_template.id
            assert result["version"] == "1.1.0"

    @pytest.mark.asyncio
    async def test_list_workflow_templates(self, n8n_service):
        """Test listing workflow templates."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "templates": [
                    {"id": "template_1", "name": "AP Processing", "type": "ap_processing"},
                    {"id": "template_2", "name": "AR Processing", "type": "ar_processing"}
                ],
                "total": 2
            }

            result = await n8n_service.list_workflow_templates()

            assert len(result["templates"]) == 2
            assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_delete_workflow_template(self, n8n_service):
        """Test deleting a workflow template."""
        template_id = "template_123"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {"status": "deleted"}

            result = await n8n_service.delete_workflow_template(template_id)

            assert result["status"] == "deleted"
            mock_request.assert_called_once_with("DELETE", f"/rest/workflows/{template_id}")

    @pytest.mark.asyncio
    async def test_get_workflow_template(self, n8n_service):
        """Test retrieving a specific workflow template."""
        template_id = "template_123"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": template_id,
                "name": "AP Processing Template",
                "nodes": [{"id": "node1", "type": "trigger"}]
            }

            result = await n8n_service.get_workflow_template(template_id)

            assert result["id"] == template_id
            assert "nodes" in result

    @pytest.mark.asyncio
    async def test_activate_workflow_template(self, n8n_service):
        """Test activating a workflow template."""
        template_id = "template_123"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": template_id,
                "status": "active",
                "active": True
            }

            result = await n8n_service.activate_workflow_template(template_id)

            assert result["active"] is True

    @pytest.mark.asyncio
    async def test_deactivate_workflow_template(self, n8n_service):
        """Test deactivating a workflow template."""
        template_id = "template_123"

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": template_id,
                "status": "inactive",
                "active": False
            }

            result = await n8n_service.deactivate_workflow_template(template_id)

            assert result["active"] is False


class TestN8nIntegration:
    """Integration tests for n8n service with existing system."""

    @pytest.mark.asyncio
    async def test_integration_with_invoice_processing(self, n8n_service, mock_ap_invoice_data):
        """Test integration with existing invoice processing workflow."""
        # Mock the invoice processor integration
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_integration_123",
                "status": "running"
            }

            # Test that n8n service can trigger workflow with invoice data
            result = await n8n_service.trigger_workflow(
                N8nWorkflowExecutionRequest(
                    workflow_id="ap_invoice_processing",
                    data=mock_ap_invoice_data
                )
            )

            assert result["executionId"] == "exec_integration_123"

    @pytest.mark.asyncio
    async def test_integration_with_metrics_service(self, n8n_service):
        """Test integration with metrics service for workflow tracking."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executions": [
                    {
                        "id": "exec_1",
                        "workflowId": "workflow_ap",
                        "status": "success",
                        "startedAt": datetime.utcnow().isoformat(),
                        "stoppedAt": datetime.utcnow().isoformat()
                    }
                ],
                "total": 1
            }

            result = await n8n_service.get_workflow_executions(
                workflow_id="workflow_ap",
                limit=10
            )

            assert len(result["executions"]) == 1
            assert result["executions"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_integration_with_exception_management(self, n8n_service):
        """Test integration with exception management for automated handling."""
        exception_data = {
            "exception_id": "exc_123",
            "workflow_step": "validation",
            "auto_resolution_possible": True
        }

        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "executionId": "exec_exception_123",
                "status": "running"
            }

            result = await n8n_service.trigger_exception_handling(exception_data)

            assert result["executionId"] == "exec_exception_123"

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, n8n_service):
        """Test collection of workflow performance metrics."""
        with patch.object(n8n_service, '_make_request') as mock_request:
            mock_request.return_value = {
                "metrics": {
                    "totalExecutions": 100,
                    "successRate": 0.95,
                    "averageExecutionTime": 2500,
                    "errorRate": 0.05
                }
            }

            result = await n8n_service.get_workflow_metrics()

            assert result["metrics"]["totalExecutions"] == 100
            assert result["metrics"]["successRate"] == 0.95


class TestN8nSecurity:
    """Test suite for n8n security features."""

    @pytest.mark.asyncio
    async def test_webhook_signature_validation_security(self, n8n_service):
        """Test webhook signature validation security."""
        # Test with malformed signature
        with pytest.raises(N8nWorkflowException):
            n8n_service.validate_webhook_signature(
                payload={"test": "data"},
                signature="",
                secret="test_secret"
            )

    @pytest.mark.asyncio
    async def test_request_sanitization(self, n8n_service):
        """Test request data sanitization."""
        malicious_data = {
            "invoice_id": "test",
            "script": "<script>alert('xss')</script>",
            "sql": "DROP TABLE users;"
        }

        sanitized = n8n_service._sanitize_request_data(malicious_data)

        # Ensure malicious content is removed or escaped
        assert "<script>" not in str(sanitized)
        assert "DROP TABLE" not in str(sanitized)

    @pytest.mark.asyncio
    async def test_api_key_encryption_storage(self, n8n_service):
        """Test API key encryption for secure storage."""
        api_key = "sensitive_api_key_123"

        # Mock encryption
        with patch('cryptography.fernet.Fernet.encrypt') as mock_encrypt:
            mock_encrypt.return_value = b"encrypted_key"

            encrypted = n8n_service._encrypt_api_key(api_key)

            assert encrypted != api_key
            mock_encrypt.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_sanitization(self, n8n_service):
        """Test error message sanitization."""
        error_with_secrets = N8nWorkflowException(
            "Error with API key: secret_123 and password: pass_456"
        )

        sanitized_error = n8n_service._sanitize_error_message(str(error_with_secrets))

        # Ensure secrets are removed from error messages
        assert "secret_123" not in sanitized_error
        assert "pass_456" not in sanitized_error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])