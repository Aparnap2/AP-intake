"""
n8n integration service for workflow automation with the AP/AR system.
This service provides comprehensive integration with n8n for triggering workflows,
handling webhooks, managing templates, and providing robust error handling
with retry logic and security features.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import aiohttp
import backoff
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.n8n_schemas import (
    N8nApiResponse,
    N8nConnectionInfo,
    N8nCustomerOnboardingRequest,
    N8nExceptionHandlingRequest,
    N8nExecutionStatus,
    N8nWeeklyReportRequest,
    N8nWorkingCapitalRequest,
    N8nWorkflowExecutionRequest,
    N8nWorkflowExecutionResponse,
    N8nWorkflowMetrics,
    N8nWorkflowTemplate,
    N8nWebhookEvent,
)

logger = logging.getLogger(__name__)


class N8nWorkflowException(Exception):
    """Exception raised for n8n workflow-related errors."""
    pass


class N8nConnectionException(Exception):
    """Exception raised for n8n connection errors."""
    pass


class N8nAuthenticationException(Exception):
    """Exception raised for n8n authentication errors."""
    pass


class N8nService:
    """
    Comprehensive n8n integration service for workflow automation.

    This service provides:
    - n8n client with authentication and API integration
    - Workflow triggers for AP/AR processing
    - Webhook handlers for n8n callbacks
    - Workflow template management
    - Error handling and retry logic
    - Security features (signature validation, encryption)
    """

    def __init__(self):
        """Initialize the n8n service with configuration."""
        self.base_url = settings.N8N_BASE_URL
        self.api_key = settings.N8N_API_KEY
        self.username = settings.N8N_USERNAME
        self.password = settings.N8N_PASSWORD
        self.webhook_secret = settings.N8N_WEBHOOK_SECRET
        self.timeout = settings.N8N_TIMEOUT if hasattr(settings, 'N8N_TIMEOUT') else 30
        self.max_retries = settings.N8N_MAX_RETRIES if hasattr(settings, 'N8N_MAX_RETRIES') else 3
        self.retry_delay = settings.N8N_RETRY_DELAY if hasattr(settings, 'N8N_RETRY_DELAY') else 1.0

        # Initialize encryption for sensitive data
        self.encryption_key = settings.N8N_ENCRYPTION_KEY if hasattr(settings, 'N8N_ENCRYPTION_KEY') else None
        self.cipher = Fernet(self.encryption_key.encode()) if self.encryption_key else None

        # Initialize HTTP session
        self.session = None
        self._token = None
        self._token_expires = None

        logger.info(f"Initialized n8n service for {self.base_url}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _ensure_session(self):
        """Ensure HTTP session is initialized."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for n8n API requests."""
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            # Use API key authentication
            headers["X-N8N-API-KEY"] = self.api_key
        elif self._token:
            # Use Bearer token authentication
            headers["Authorization"] = f"Bearer {self._token}"
        elif self.username and self.password:
            # Basic authentication (not recommended, use API key or token)
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        return headers

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        base=1,
        max_value=10
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to n8n API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            N8nConnectionException: For connection errors
            N8nWorkflowException: For workflow errors
        """
        await self._ensure_session()

        url = f"{self.base_url.rstrip('/')}/rest{endpoint}"
        headers = self._get_auth_headers()

        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            ) as response:
                response_data = await response.json()

                if response.status == 401:
                    raise N8nAuthenticationException("Authentication failed")
                elif response.status == 404:
                    raise N8nWorkflowException("Resource not found")
                elif response.status >= 400:
                    error_msg = response_data.get("error", f"HTTP {response.status}")
                    raise N8nWorkflowException(error_msg)

                return response_data

        except aiohttp.ClientError as e:
            logger.error(f"Connection error to n8n API: {e}")
            raise N8nConnectionException(f"Connection error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from n8n API: {e}")
            raise N8nWorkflowException(f"Invalid response format: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in n8n API request: {e}")
            raise N8nWorkflowException(f"Unexpected error: {str(e)}")

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to n8n instance.

        Returns:
            Connection status and n8n version information
        """
        try:
            response = await self._make_request("GET", "/health")
            return {
                "status": "ok",
                "connected": True,
                "version": response.get("version", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"n8n connection test failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with n8n and obtain access token.

        Returns:
            Authentication status and token information
        """
        if self.api_key:
            # API key authentication, just test connection
            test_result = await self.test_connection()
            return {"authenticated": test_result["connected"], "method": "api_key"}

        # Token-based authentication
        if not self.username or not self.password:
            raise N8nAuthenticationException("Missing authentication credentials")

        try:
            token_data = await self._make_request(
                "POST",
                "/login",
                data={"email": self.username, "password": self.password}
            )

            self._token = token_data.get("token")
            self._token_expires = datetime.utcnow() + timedelta(hours=1)

            return {
                "authenticated": True,
                "token": self._token,
                "expires_at": self._token_expires.isoformat(),
                "method": "token"
            }

        except Exception as e:
            logger.error(f"n8n authentication failed: {e}")
            raise N8nAuthenticationException(f"Authentication failed: {str(e)}")

    async def trigger_workflow(self, request: N8nWorkflowExecutionRequest) -> Dict[str, Any]:
        """
        Trigger n8n workflow execution.

        Args:
            request: Workflow execution request

        Returns:
            Execution response with execution ID and status
        """
        try:
            logger.info(f"Triggering n8n workflow {request.workflow_id}")

            execution_data = {
                "workflowData": request.data,
                "runData": {}
            }

            if request.start_node:
                execution_data["startNode"] = request.start_node

            response = await self._make_request(
                "POST",
                f"/workflows/{request.workflow_id}/execute",
                data=execution_data
            )

            logger.info(f"n8n workflow {request.workflow_id} triggered successfully")
            return {
                "execution_id": response.get("executionId"),
                "status": response.get("status", "running"),
                "workflow_id": request.workflow_id,
                "started_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to trigger n8n workflow {request.workflow_id}: {e}")
            raise N8nWorkflowException(f"Workflow trigger failed: {str(e)}")

    async def trigger_ap_invoice_processing(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger AP invoice processing workflow.

        Args:
            invoice_data: AP invoice data

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_AP_WORKFLOW_ID', 'ap_invoice_processing')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "ap_invoice_processed",
                "invoice_data": invoice_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def trigger_ar_invoice_processing(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger AR invoice processing workflow.

        Args:
            invoice_data: AR invoice data

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_AR_WORKFLOW_ID', 'ar_invoice_processing')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "ar_invoice_processed",
                "invoice_data": invoice_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def trigger_working_capital_analysis(self) -> Dict[str, Any]:
        """
        Trigger daily working capital analysis workflow.

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_WORKING_CAPITAL_WORKFLOW_ID', 'working_capital_analysis')

        analysis_request = N8nWorkingCapitalRequest(
            analysis_date=datetime.utcnow(),
            period_days=30,
            include_projections=True
        )

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "working_capital_analysis",
                "analysis_data": analysis_request.model_dump(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def trigger_customer_onboarding(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger customer onboarding workflow.

        Args:
            customer_data: Customer onboarding data

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_CUSTOMER_ONBOARDING_WORKFLOW_ID', 'customer_onboarding')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "customer_onboarding",
                "customer_data": customer_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def trigger_exception_handling(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger exception handling workflow.

        Args:
            exception_data: Exception handling data

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_EXCEPTION_HANDLING_WORKFLOW_ID', 'exception_handling')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "exception_raised",
                "exception_data": exception_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def trigger_weekly_report_generation(self) -> Dict[str, Any]:
        """
        Trigger weekly report generation workflow.

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_WEEKLY_REPORT_WORKFLOW_ID', 'weekly_report_generation')

        # Calculate week dates
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        report_request = N8nWeeklyReportRequest(
            report_date=today,
            week_start=week_start,
            week_end=week_end,
            include_charts=True,
            report_format="pdf"
        )

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "weekly_report_generation",
                "report_data": report_request.model_dump(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return await self.trigger_workflow(request)

    async def schedule_monday_digest(self, digest_request) -> Dict[str, Any]:
        """
        Schedule Monday 9am CFO digest delivery with enhanced workflow triggers.

        Args:
            digest_request: N8nCFODigestRequest with digest data

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_CFO_DIGEST_WORKFLOW_ID', 'cfo_monday_digest')

        # Calculate next Monday 9am delivery time
        next_monday_9am = self._calculate_next_monday_9am()

        # Prepare enhanced workflow data
        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "cfo_monday_digest",
                "digest_data": digest_request.model_dump(),
                "schedule_info": {
                    "scheduled_for": next_monday_9am.isoformat(),
                    "delivery_time": "09:00 UTC",
                    "day_of_week": "monday",
                    "recurrence": "weekly"
                },
                "priority": digest_request.delivery_priority,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Scheduling Monday CFO digest for {next_monday_9am.isoformat()}")
        return await self.trigger_workflow(request)

    async def trigger_monday_digest_generation(self, week_start: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Trigger immediate Monday digest generation workflow.

        Args:
            week_start: Optional week start date (defaults to last week)

        Returns:
            Workflow execution response
        """
        workflow_id = getattr(settings, 'N8N_CFO_DIGEST_GENERATION_WORKFLOW_ID', 'cfo_digest_generation')

        # Calculate week dates
        if week_start is None:
            today = datetime.utcnow()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday + 7)

        week_end = week_start + timedelta(days=6)

        # Prepare digest generation request
        digest_request = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "include_working_capital_analysis": True,
            "include_action_items": True,
            "include_evidence_links": True,
            "priority_threshold": "medium",
            "business_impact_threshold": "moderate",
            "delivery_time": "09:00",
            "schedule_delivery": True
        }

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "cfo_digest_generation",
                "digest_request": digest_request,
                "generation_metadata": {
                    "trigger_type": "scheduled",
                    "requested_at": datetime.utcnow().isoformat(),
                    "target_delivery": "Monday 9:00 AM"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Triggering Monday CFO digest generation for week {week_start.date()} to {week_end.date()}")
        return await self.trigger_workflow(request)

    async def setup_monday_digest_schedule(self, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Setup recurring Monday 9am CFO digest schedule.

        Args:
            schedule_config: Configuration for the schedule

        Returns:
            Schedule setup response
        """
        workflow_id = getattr(settings, 'N8N_CFO_DIGEST_SCHEDULE_WORKFLOW_ID', 'cfo_digest_schedule')

        # Default schedule configuration
        default_config = {
            "is_active": True,
            "delivery_day": "monday",
            "delivery_time": "09:00",
            "timezone": "UTC",
            "priority_threshold": "medium",
            "business_impact_threshold": "moderate",
            "include_working_capital_analysis": True,
            "include_action_items": True,
            "recipients": ["cfo@company.com", "finance-team@company.com"]
        }

        # Merge with provided config
        merged_config = {**default_config, **schedule_config}

        # Calculate next delivery time
        next_delivery = self._calculate_next_monday_9am(
            merged_config.get("delivery_time", "09:00")
        )

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "setup_cfo_digest_schedule",
                "schedule_config": merged_config,
                "schedule_metadata": {
                    "next_delivery": next_delivery.isoformat(),
                    "setup_at": datetime.utcnow().isoformat(),
                    "schedule_type": "recurring_weekly"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Setting up Monday CFO digest schedule: {merged_config}")
        return await self.trigger_workflow(request)

    def _calculate_next_monday_9am(self, delivery_time: str = "09:00") -> datetime:
        """Calculate next Monday 9am in specified timezone."""
        today = datetime.utcnow()

        # Parse delivery time
        hour, minute = map(int, delivery_time.split(':'))

        # Find next Monday
        days_until_monday = (7 - today.weekday()) % 7 or 7  # Next Monday (0 = Monday)
        next_monday = today + timedelta(days=days_until_monday)

        # Set delivery time
        next_monday_delivery = next_monday.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        return next_monday_delivery

    async def update_cfo_digest_recipients(self, digest_id: str, recipients: List[str]) -> Dict[str, Any]:
        """
        Update CFO digest recipients for scheduled delivery.

        Args:
            digest_id: ID of the digest
            recipients: List of recipient email addresses

        Returns:
            Update response
        """
        workflow_id = getattr(settings, 'N8N_CFO_DIGEST_UPDATE_WORKFLOW_ID', 'cfo_digest_update')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "update_cfo_digest_recipients",
                "digest_id": digest_id,
                "new_recipients": recipients,
                "update_metadata": {
                    "updated_at": datetime.utcnow().isoformat(),
                    "update_type": "recipients"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Updating CFO digest {digest_id} recipients: {recipients}")
        return await self.trigger_workflow(request)

    async def cancel_monday_digest(self, digest_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel scheduled Monday CFO digest.

        Args:
            digest_id: ID of the digest to cancel
            reason: Optional cancellation reason

        Returns:
            Cancellation response
        """
        workflow_id = getattr(settings, 'N8N_CFO_DIGEST_CANCEL_WORKFLOW_ID', 'cfo_digest_cancel')

        request = N8nWorkflowExecutionRequest(
            workflow_id=workflow_id,
            data={
                "event_type": "cancel_cfo_digest",
                "digest_id": digest_id,
                "cancellation_reason": reason or "Cancelled by user",
                "cancellation_metadata": {
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "cancellation_type": "manual"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Cancelling Monday CFO digest {digest_id}. Reason: {reason}")
        return await self.trigger_workflow(request)

    def validate_webhook_signature(
        self,
        payload: Dict[str, Any],
        signature: str,
        secret: str
    ) -> bool:
        """
        Validate webhook signature for security.

        Args:
            payload: Webhook payload data
            signature: Webhook signature from request headers
            secret: Webhook secret key

        Returns:
            True if signature is valid, False otherwise
        """
        if not signature or not secret:
            logger.warning("Missing webhook signature or secret")
            return False

        try:
            # Create expected signature
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            expected_signature = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()

            # Compare signatures (timing-attack resistant)
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False

    async def process_webhook_event(self, event: N8nWebhookEvent) -> Dict[str, Any]:
        """
        Process incoming webhook event from n8n.

        Args:
            event: Webhook event data

        Returns:
            Processing result
        """
        try:
            logger.info(f"Processing n8n webhook event {event.execution_id}")

            # Validate webhook signature if provided
            if event.signature and self.webhook_secret:
                if not self.validate_webhook_signature(
                    event.data,
                    event.signature,
                    self.webhook_secret
                ):
                    raise N8nWorkflowException("Invalid webhook signature")

            # Process the event based on status
            if event.status == N8nExecutionStatus.SUCCESS:
                result = await self._handle_successful_execution(event)
            elif event.status == N8nExecutionStatus.ERROR:
                result = await self._handle_failed_execution(event)
            else:
                result = await self._handle_pending_execution(event)

            logger.info(f"Processed n8n webhook event {event.execution_id}")
            return {
                "status": "processed",
                "execution_id": event.execution_id,
                "workflow_id": event.workflow_id,
                "event_status": event.status,
                "processed_at": datetime.utcnow().isoformat(),
                **result
            }

        except Exception as e:
            logger.error(f"Failed to process n8n webhook event {event.execution_id}: {e}")
            raise N8nWorkflowException(f"Webhook processing failed: {str(e)}")

    async def _handle_successful_execution(self, event: N8nWebhookEvent) -> Dict[str, Any]:
        """Handle successful workflow execution."""
        return {
            "result": "success",
            "execution_data": event.data,
            "next_actions": event.data.get("next_actions", [])
        }

    async def _handle_failed_execution(self, event: N8nWebhookEvent) -> Dict[str, Any]:
        """Handle failed workflow execution."""
        error_info = event.data.get("error", {})
        return {
            "result": "error",
            "error_info": error_info,
            "retry_recommended": error_info.get("retryable", False)
        }

    async def _handle_pending_execution(self, event: N8nWebhookEvent) -> Dict[str, Any]:
        """Handle pending workflow execution."""
        return {
            "result": "pending",
            "status": event.status,
            "estimated_completion": event.data.get("estimated_completion")
        }

    async def create_workflow_template(self, template: N8nWorkflowTemplate) -> Dict[str, Any]:
        """
        Create new workflow template in n8n.

        Args:
            template: Workflow template definition

        Returns:
            Created template information
        """
        try:
            # Convert template to n8n format
            n8n_template = self._convert_template_to_n8n_format(template)

            response = await self._make_request(
                "POST",
                "/workflows",
                data=n8n_template
            )

            logger.info(f"Created n8n workflow template {template.name}")
            return {
                "id": response.get("id"),
                "name": template.name,
                "status": "created",
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create n8n workflow template {template.name}: {e}")
            raise N8nWorkflowException(f"Template creation failed: {str(e)}")

    async def update_workflow_template(self, template: N8nWorkflowTemplate) -> Dict[str, Any]:
        """
        Update existing workflow template in n8n.

        Args:
            template: Updated workflow template definition

        Returns:
            Updated template information
        """
        try:
            if not template.id:
                raise N8nWorkflowException("Template ID is required for updates")

            n8n_template = self._convert_template_to_n8n_format(template)

            response = await self._make_request(
                "PUT",
                f"/workflows/{template.id}",
                data=n8n_template
            )

            logger.info(f"Updated n8n workflow template {template.name}")
            return {
                "id": template.id,
                "name": template.name,
                "version": template.version,
                "status": "updated",
                "updated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to update n8n workflow template {template.name}: {e}")
            raise N8nWorkflowException(f"Template update failed: {str(e)}")

    async def list_workflow_templates(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        List workflow templates in n8n.

        Args:
            limit: Maximum number of templates to return
            offset: Number of templates to skip

        Returns:
            List of workflow templates
        """
        try:
            params = {"limit": limit, "offset": offset}
            response = await self._make_request("GET", "/workflows", params=params)

            return {
                "templates": response.get("data", []),
                "total": response.get("total", 0),
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            logger.error(f"Failed to list n8n workflow templates: {e}")
            raise N8nWorkflowException(f"Template listing failed: {str(e)}")

    async def get_workflow_template(self, template_id: str) -> Dict[str, Any]:
        """
        Get specific workflow template from n8n.

        Args:
            template_id: Template ID

        Returns:
            Workflow template details
        """
        try:
            response = await self._make_request("GET", f"/workflows/{template_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to get n8n workflow template {template_id}: {e}")
            raise N8nWorkflowException(f"Template retrieval failed: {str(e)}")

    async def delete_workflow_template(self, template_id: str) -> Dict[str, Any]:
        """
        Delete workflow template from n8n.

        Args:
            template_id: Template ID

        Returns:
            Deletion status
        """
        try:
            await self._make_request("DELETE", f"/workflows/{template_id}")

            logger.info(f"Deleted n8n workflow template {template_id}")
            return {
                "id": template_id,
                "status": "deleted",
                "deleted_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to delete n8n workflow template {template_id}: {e}")
            raise N8nWorkflowException(f"Template deletion failed: {str(e)}")

    async def activate_workflow_template(self, template_id: str) -> Dict[str, Any]:
        """
        Activate workflow template in n8n.

        Args:
            template_id: Template ID

        Returns:
            Activation status
        """
        try:
            await self._make_request("POST", f"/workflows/{template_id}/activate")

            logger.info(f"Activated n8n workflow template {template_id}")
            return {
                "id": template_id,
                "status": "active",
                "active": True,
                "activated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to activate n8n workflow template {template_id}: {e}")
            raise N8nWorkflowException(f"Template activation failed: {str(e)}")

    async def deactivate_workflow_template(self, template_id: str) -> Dict[str, Any]:
        """
        Deactivate workflow template in n8n.

        Args:
            template_id: Template ID

        Returns:
            Deactivation status
        """
        try:
            await self._make_request("POST", f"/workflows/{template_id}/deactivate")

            logger.info(f"Deactivated n8n workflow template {template_id}")
            return {
                "id": template_id,
                "status": "inactive",
                "active": False,
                "deactivated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to deactivate n8n workflow template {template_id}: {e}")
            raise N8nWorkflowException(f"Template deactivation failed: {str(e)}")

    async def get_workflow_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[N8nExecutionStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get workflow executions from n8n.

        Args:
            workflow_id: Filter by workflow ID
            status: Filter by execution status
            limit: Maximum number of executions to return
            offset: Number of executions to skip

        Returns:
            List of workflow executions
        """
        try:
            params = {"limit": limit, "offset": offset}

            if workflow_id:
                params["workflowId"] = workflow_id
            if status:
                params["status"] = status.value

            response = await self._make_request("GET", "/executions", params=params)

            return {
                "executions": response.get("data", []),
                "total": response.get("total", 0),
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            logger.error(f"Failed to get n8n workflow executions: {e}")
            raise N8nWorkflowException(f"Execution retrieval failed: {str(e)}")

    async def get_workflow_metrics(self, days: int = 7) -> N8nWorkflowMetrics:
        """
        Get workflow performance metrics.

        Args:
            days: Number of days to analyze

        Returns:
            Workflow performance metrics
        """
        try:
            # Get executions for the specified period
            since = datetime.utcnow() - timedelta(days=days)
            executions_response = await self.get_workflow_executions(limit=1000)
            executions = executions_response["executions"]

            # Calculate metrics
            total_executions = len(executions)
            successful_executions = len([e for e in executions if e.get("status") == "success"])
            failed_executions = len([e for e in executions if e.get("status") == "error"])

            success_rate = successful_executions / total_executions if total_executions > 0 else 0.0
            error_rate = failed_executions / total_executions if total_executions > 0 else 0.0

            # Calculate average execution time
            execution_times = [
                e.get("runtime", 0) for e in executions
                if e.get("runtime") is not None
            ]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0

            return N8nWorkflowMetrics(
                workflow_id="all",
                workflow_name="All Workflows",
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_execution_time_ms=avg_execution_time,
                success_rate=success_rate,
                error_rate=error_rate,
                last_execution=datetime.utcnow() if executions else None
            )

        except Exception as e:
            logger.error(f"Failed to get n8n workflow metrics: {e}")
            raise N8nWorkflowException(f"Metrics retrieval failed: {str(e)}")

    def _convert_template_to_n8n_format(self, template: N8nWorkflowTemplate) -> Dict[str, Any]:
        """Convert workflow template to n8n API format."""
        n8n_template = {
            "name": template.name,
            "description": template.description,
            "active": template.active,
            "nodes": [],
            "connections": template.connections or {}
        }

        # Convert nodes
        for node in template.nodes:
            n8n_node = {
                "id": node.id,
                "name": node.name,
                "type": node.type,
                "typeVersion": 1,
                "position": node.position or {"x": 100, "y": 100},
                "parameters": node.parameters or {}
            }

            if node.credentials:
                n8n_node["credentials"] = node.credentials

            n8n_template["nodes"].append(n8n_node)

        return n8n_template

    def _sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize request data to remove malicious content."""
        if not isinstance(data, dict):
            return data

        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Remove potential script tags and SQL injection attempts
                sanitized_value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
                sanitized_value = re.sub(r'(drop|delete|insert|update|create|alter)\s+', '', sanitized_value, flags=re.IGNORECASE)
                sanitized[key] = sanitized_value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request_data(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_request_data(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_error_message(self, error_message: str) -> str:
        """Sanitize error messages to remove sensitive information."""
        # Remove potential secrets and credentials
        sanitized = re.sub(r'(api[_-]?key|token|password|secret)[\'\"]?\s*[:=]\s*[\'\"]?[\w\-_\.]+',
                          r'\1: [REDACTED]', error_message, flags=re.IGNORECASE)
        return sanitized

    def _encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key for secure storage."""
        if not self.cipher:
            raise N8nWorkflowException("Encryption not configured")

        return self.cipher.encrypt(api_key.encode()).decode()

    def _decrypt_api_key(self, encrypted_api_key: str) -> str:
        """Decrypt API key for use."""
        if not self.cipher:
            raise N8nWorkflowException("Encryption not configured")

        return self.cipher.decrypt(encrypted_api_key.encode()).decode()

    async def rotate_api_key(self, new_api_key: str) -> Dict[str, Any]:
        """
        Rotate API key for n8n authentication.

        Args:
            new_api_key: New API key to use

        Returns:
            Rotation status
        """
        try:
            # Store old API key for rollback
            old_api_key = self.api_key

            # Update API key
            self.api_key = new_api_key

            # Test new API key
            test_result = await self.test_connection()

            if test_result["connected"]:
                logger.info("n8n API key rotation successful")
                return {
                    "status": "success",
                    "message": "API key rotated successfully",
                    "tested_at": test_result["timestamp"]
                }
            else:
                # Rollback on failure
                self.api_key = old_api_key
                raise N8nWorkflowException("New API key validation failed")

        except Exception as e:
            logger.error(f"n8n API key rotation failed: {e}")
            raise N8nWorkflowException(f"API key rotation failed: {str(e)}")