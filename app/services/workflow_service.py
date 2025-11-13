"""
Workflow service that provides a unified interface for workflow execution
using the swappable integration system.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from app.core.config import settings
from app.schemas.integration_schemas import (
    IntegrationType,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowType
)
from app.services.integration_factory import (
    IntegrationFactory,
    get_integration_factory,
    configure_integration_factory
)

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    High-level workflow service that abstracts the complexity of
    the swappable integration system.
    """

    def __init__(self, factory: Optional[IntegrationFactory] = None):
        """Initialize the workflow service."""
        self.factory = factory or get_integration_factory()
        logger.info(f"WorkflowService initialized with factory")

    async def execute_workflow(
        self,
        workflow_type: Union[WorkflowType, str],
        data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None,
        timeout: Optional[int] = None,
        dry_run: bool = False
    ) -> WorkflowExecutionResponse:
        """
        Execute a workflow with automatic provider selection and fallback.

        Args:
            workflow_type: Type of workflow to execute
            data: Workflow input data
            provider_type: Specific provider to use (optional)
            options: Additional execution options
            priority: Execution priority (1-10)
            timeout: Timeout in seconds
            dry_run: Execute in dry-run mode

        Returns:
            Workflow execution response
        """
        # Convert string types to enums
        if isinstance(workflow_type, str):
            workflow_type = WorkflowType(workflow_type)

        if provider_type and isinstance(provider_type, str):
            provider_type = IntegrationType(provider_type)

        # Create execution request
        request = WorkflowExecutionRequest(
            workflow_type=workflow_type,
            data=data,
            provider_type=provider_type,
            options=options or {},
            priority=priority or 5,
            timeout=timeout,
            dry_run=dry_run
        )

        logger.info(f"Executing workflow: {workflow_type} with provider: {provider_type}")

        try:
            # Execute workflow using factory
            response = await self.factory.execute_workflow(provider_type, request)

            logger.info(f"Workflow executed successfully: {response.execution_id}")
            return response

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            raise

    async def process_ap_invoice(
        self,
        invoice_data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResponse:
        """
        Process an AP invoice using the configured workflow provider.

        Args:
            invoice_data: Invoice data to process
            provider_type: Specific provider to use
            options: Additional options

        Returns:
            Workflow execution response
        """
        logger.info(f"Processing AP invoice: {invoice_data.get('invoice_id', 'unknown')}")

        # Prepare invoice data for workflow
        workflow_data = {
            "invoice_data": invoice_data,
            "processing_options": options or {},
            "metadata": {
                "source": "workflow_service",
                "timestamp": "2024-11-12T17:42:00Z"
            }
        }

        return await self.execute_workflow(
            workflow_type=WorkflowType.AP_INVOICE_PROCESSING,
            data=workflow_data,
            provider_type=provider_type,
            priority=5
        )

    async def handle_exception(
        self,
        exception_data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResponse:
        """
        Handle an exception using the configured workflow provider.

        Args:
            exception_data: Exception data to process
            provider_type: Specific provider to use
            options: Additional options

        Returns:
            Workflow execution response
        """
        logger.info(f"Handling exception: {exception_data.get('exception_id', 'unknown')}")

        workflow_data = {
            "exception_data": exception_data,
            "handling_options": options or {},
            "metadata": {
                "source": "workflow_service",
                "handler": "exception_workflow"
            }
        }

        return await self.execute_workflow(
            workflow_type=WorkflowType.EXCEPTION_HANDLING,
            data=workflow_data,
            provider_type=provider_type,
            priority=7  # Higher priority for exceptions
        )

    async def generate_weekly_report(
        self,
        report_data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResponse:
        """
        Generate a weekly report using the configured workflow provider.

        Args:
            report_data: Report configuration and data
            provider_type: Specific provider to use
            options: Additional options

        Returns:
            Workflow execution response
        """
        logger.info(f"Generating weekly report: {report_data.get('report_id', 'unknown')}")

        workflow_data = {
            "report_data": report_data,
            "generation_options": options or {},
            "metadata": {
                "source": "workflow_service",
                "report_type": "weekly"
            }
        }

        return await self.execute_workflow(
            workflow_type=WorkflowType.WEEKLY_REPORT_GENERATION,
            data=workflow_data,
            provider_type=provider_type,
            priority=3  # Lower priority for reports
        )

    async def execute_approval_workflow(
        self,
        approval_data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResponse:
        """
        Execute an approval workflow using the configured provider.

        Args:
            approval_data: Approval request data
            provider_type: Specific provider to use
            options: Additional options

        Returns:
            Workflow execution response
        """
        logger.info(f"Executing approval workflow: {approval_data.get('approval_id', 'unknown')}")

        workflow_data = {
            "approval_data": approval_data,
            "workflow_options": options or {},
            "metadata": {
                "source": "workflow_service",
                "workflow_type": "approval"
            }
        }

        return await self.execute_workflow(
            workflow_type=WorkflowType.APPROVAL_WORKFLOW,
            data=workflow_data,
            provider_type=provider_type,
            priority=6  # High priority for approvals
        )

    async def execute_working_capital_analysis(
        self,
        analysis_data: Dict[str, Any],
        provider_type: Optional[Union[IntegrationType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResponse:
        """
        Execute working capital analysis using the configured provider.

        Args:
            analysis_data: Analysis parameters and data
            provider_type: Specific provider to use
            options: Additional options

        Returns:
            Workflow execution response
        """
        logger.info(f"Executing working capital analysis")

        workflow_data = {
            "analysis_data": analysis_data,
            "analysis_options": options or {},
            "metadata": {
                "source": "workflow_service",
                "analysis_type": "working_capital"
            }
        }

        return await self.execute_workflow(
            workflow_type=WorkflowType.WORKING_CAPITAL_ANALYSIS,
            data=workflow_data,
            provider_type=provider_type,
            priority=4  # Medium priority
        )

    async def get_workflow_status(
        self,
        execution_id: str,
        provider_type: Optional[Union[IntegrationType, str]] = None
    ) -> Dict[str, Any]:
        """
        Get the status of a workflow execution.

        Args:
            execution_id: Workflow execution ID
            provider_type: Provider that executed the workflow

        Returns:
            Execution status information
        """
        # This would typically query the provider for execution status
        # For now, return a mock response
        return {
            "execution_id": execution_id,
            "status": "completed",
            "provider_type": provider_type or "native",
            "timestamp": "2024-11-12T17:42:00Z"
        }

    async def get_factory_status(self) -> Dict[str, Any]:
        """
        Get the current status of the integration factory.

        Returns:
            Factory status information
        """
        try:
            factory_status = await self.factory.health_check_all()
            return factory_status.model_dump()
        except Exception as e:
            logger.error(f"Failed to get factory status: {str(e)}")
            return {
                "error": str(e),
                "status": "unavailable"
            }

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get workflow execution metrics.

        Returns:
            Execution metrics
        """
        try:
            metrics = self.factory.get_metrics()
            return metrics.model_dump()
        except Exception as e:
            logger.error(f"Failed to get metrics: {str(e)}")
            return {
                "error": str(e),
                "status": "unavailable"
            }

    def is_using_swappable_integration(self) -> bool:
        """
        Check if the system is configured to use swappable integration.

        Returns:
            True if swappable integration is enabled
        """
        return settings.USE_SWAPPABLE_INTEGRATION

    def get_default_provider(self) -> str:
        """
        Get the default provider configuration.

        Returns:
            Default provider name
        """
        return settings.INTEGRATION_DEFAULT_PROVIDER

    def is_n8n_enabled(self) -> bool:
        """
        Check if n8n integration is enabled.

        Returns:
            True if n8n is enabled
        """
        return settings.N8N_PROVIDER_ENABLED or settings.USE_N8N

    def configure_provider(
        self,
        provider_type: Union[IntegrationType, str],
        enabled: bool,
        priority: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Configure a provider at runtime.

        Args:
            provider_type: Provider type to configure
            enabled: Whether to enable the provider
            priority: Provider priority (optional)
            config: Provider-specific configuration (optional)
        """
        if isinstance(provider_type, str):
            provider_type = IntegrationType(provider_type)

        updates = {"enabled": enabled}
        if priority is not None:
            updates["priority"] = priority
        if config is not None:
            updates["config"] = config

        self.factory.update_provider_config(provider_type, updates)
        logger.info(f"Updated provider configuration: {provider_type}")


# Global workflow service instance
_workflow_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    """
    Get the global workflow service instance.

    Returns:
        WorkflowService instance
    """
    global _workflow_service

    if _workflow_service is None:
        _workflow_service = WorkflowService()

    return _workflow_service


def configure_workflow_service(factory: IntegrationFactory) -> WorkflowService:
    """
    Configure the workflow service with a custom factory.

    Args:
        factory: Custom integration factory

    Returns:
        Configured WorkflowService instance
    """
    global _workflow_service
    _workflow_service = WorkflowService(factory)
    return _workflow_service