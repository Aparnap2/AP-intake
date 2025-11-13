"""
Swappable integration factory using Strategy + Factory pattern.
Provides a unified interface for multiple workflow providers with runtime switching.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type
from enum import Enum

import aiohttp
from fastapi import HTTPException

from app.schemas.integration_schemas import (
    IntegrationConfig,
    IntegrationType,
    WorkflowType,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowStatus,
    ProviderCapabilities,
    ProviderCapability,
    ProviderInfo,
    FactoryConfig,
    HealthCheckResponse,
    FactoryStatusResponse,
    ExecutionMetrics,
    FactoryMetrics
)
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for provider health monitoring."""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    next_attempt_time: Optional[datetime] = None


class IntegrationProvider(ABC):
    """Abstract base class for all integration providers."""

    def __init__(self, config: IntegrationConfig):
        """Initialize the provider with configuration."""
        self.provider_type = config.provider_type
        self.enabled = config.enabled
        self.priority = config.priority
        self.config = config.config
        self.metadata = config.metadata or {}
        self.circuit_breaker = CircuitBreakerState()
        self._last_health_check = None
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time_ms": 0,
            "last_execution": None
        }

    @abstractmethod
    async def execute_workflow(
        self,
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """Execute a workflow using this provider."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is currently available."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get the provider's capabilities."""
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the provider."""
        pass

    async def health_check(self) -> HealthCheckResponse:
        """Perform a health check on the provider."""
        start_time = time.time()

        try:
            # Check circuit breaker state
            if self.circuit_breaker.state == "OPEN":
                if datetime.utcnow() < self.circuit_breaker.next_attempt_time:
                    return HealthCheckResponse(
                        provider_type=self.provider_type,
                        healthy=False,
                        error="Circuit breaker is open",
                        timestamp=datetime.utcnow()
                    )
                else:
                    # Move to half-open state
                    self.circuit_breaker.state = "HALF_OPEN"

            # Check if provider is enabled
            if not self.enabled:
                return HealthCheckResponse(
                    provider_type=self.provider_type,
                    healthy=False,
                    error="Provider is disabled",
                    timestamp=datetime.utcnow()
                )

            # Perform availability check
            is_available = await self.is_available()
            response_time_ms = int((time.time() - start_time) * 1000)

            if is_available:
                # Reset circuit breaker on success
                self.circuit_breaker.failure_count = 0
                self.circuit_breaker.state = "CLOSED"
                self._last_health_check = datetime.utcnow()

                return HealthCheckResponse(
                    provider_type=self.provider_type,
                    healthy=True,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.utcnow()
                )
            else:
                return HealthCheckResponse(
                    provider_type=self.provider_type,
                    healthy=False,
                    error="Provider is not available",
                    response_time_ms=response_time_ms,
                    timestamp=datetime.utcnow()
                )

        except Exception as e:
            # Record failure and potentially open circuit breaker
            self.circuit_breaker.failure_count += 1
            self.circuit_breaker.last_failure_time = datetime.utcnow()

            # Open circuit breaker if threshold exceeded
            if (self.circuit_breaker.failure_count >= 5 and
                self.circuit_breaker.state != "OPEN"):
                self.circuit_breaker.state = "OPEN"
                self.circuit_breaker.next_attempt_time = (
                    datetime.utcnow() + timedelta(minutes=5)
                )

            return HealthCheckResponse(
                provider_type=self.provider_type,
                healthy=False,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000),
                timestamp=datetime.utcnow()
            )

    def record_execution(
        self,
        success: bool,
        execution_time_ms: int
    ) -> None:
        """Record execution metrics."""
        self._metrics["total_executions"] += 1
        self._metrics["total_execution_time_ms"] += execution_time_ms
        self._metrics["last_execution"] = datetime.utcnow()

        if success:
            self._metrics["successful_executions"] += 1
            # Reset circuit breaker on success
            if self.circuit_breaker.state == "HALF_OPEN":
                self.circuit_breaker.state = "CLOSED"
                self.circuit_breaker.failure_count = 0
        else:
            self._metrics["failed_executions"] += 1
            # Record failure for circuit breaker
            self.circuit_breaker.failure_count += 1
            self.circuit_breaker.last_failure_time = datetime.utcnow()

            # Open circuit breaker if threshold exceeded
            if (self.circuit_breaker.failure_count >= 5 and
                self.circuit_breaker.state != "OPEN"):
                self.circuit_breaker.state = "OPEN"
                self.circuit_breaker.next_attempt_time = (
                    datetime.utcnow() + timedelta(minutes=5)
                )

    def get_metrics(self) -> Dict[str, Any]:
        """Get provider execution metrics."""
        total = self._metrics["total_executions"]

        if total == 0:
            return {
                "provider_type": self.provider_type,
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time_ms": 0.0,
                "total_execution_time_ms": 0.0,  # Added missing key
                "success_rate": 0.0,
                "error_rate": 0.0,
                "last_execution": None
            }

        return {
            "provider_type": self.provider_type,
            "total_executions": total,
            "successful_executions": self._metrics["successful_executions"],
            "failed_executions": self._metrics["failed_executions"],
            "average_execution_time_ms": (
                self._metrics["total_execution_time_ms"] / total
            ),
            "total_execution_time_ms": self._metrics["total_execution_time_ms"],  # Added missing key
            "success_rate": self._metrics["successful_executions"] / total,
            "error_rate": self._metrics["failed_executions"] / total,
            "last_execution": self._metrics["last_execution"]
        }


class NativeProvider(IntegrationProvider):
    """Native workflow provider implementation."""

    def __init__(self, config: IntegrationConfig):
        """Initialize the native provider."""
        super().__init__(config)
        self._name = "Native Workflow Provider"
        self._version = "1.0.0"

    async def execute_workflow(
        self,
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """Execute a workflow using native implementation."""
        execution_id = f"native_{int(time.time() * 1000)}"
        start_time = time.time()

        try:
            logger.info(f"Executing native workflow: {request.workflow_type}")

            # Simulate workflow execution based on type
            if request.workflow_type == "ap_invoice_processing":
                result = await self._execute_ap_invoice_processing(request.data)
            elif request.workflow_type == "exception_handling":
                result = await self._execute_exception_handling(request.data)
            elif request.workflow_type == "weekly_report_generation":
                result = await self._execute_weekly_report(request.data)
            else:
                result = await self._execute_generic_workflow(request.data)

            execution_time_ms = int((time.time() - start_time) * 1000)
            self.record_execution(True, execution_time_ms)

            return WorkflowExecutionResponse(
                execution_id=execution_id,
                workflow_type=request.workflow_type,
                provider_type=self.provider_type,
                status=WorkflowStatus.COMPLETED,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                result=result,
                duration_ms=execution_time_ms,
                provider_details={
                    "provider": "native",
                    "execution_mode": "direct"
                }
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            self.record_execution(False, execution_time_ms)

            logger.error(f"Native workflow execution failed: {str(e)}")
            return WorkflowExecutionResponse(
                execution_id=execution_id,
                workflow_type=request.workflow_type,
                provider_type=self.provider_type,
                status=WorkflowStatus.FAILED,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                error={
                    "message": str(e),
                    "type": "native_execution_error"
                },
                duration_ms=execution_time_ms,
                provider_details={
                    "provider": "native",
                    "execution_mode": "direct"
                }
            )

    async def is_available(self) -> bool:
        """Native provider is always available."""
        return True

    def get_capabilities(self) -> ProviderCapabilities:
        """Get native provider capabilities."""
        return ProviderCapabilities(
            supported_workflows=[
                "ap_invoice_processing",
                "ar_invoice_processing",
                "exception_handling",
                "weekly_report_generation",
                "approval_workflow",
                "working_capital_analysis",
                "custom_workflow"
            ],
            max_concurrent_workflows=100,
            max_execution_time=3600,
            features=[
                ProviderCapability.BATCH_PROCESSING,
                ProviderCapability.PARALLEL_EXECUTION,
                ProviderCapability.ERROR_HANDLING,
                ProviderCapability.MONITORING,
                ProviderCapability.DRY_RUN,
                ProviderCapability.RETRY_LOGIC
            ],
            limitations=["No visual workflow editor", "Limited external integrations"],
            performance_metrics={
                "average_response_time_ms": 50,
                "throughput_per_second": 20,
                "memory_usage_mb": 512
            }
        )

    def get_provider_info(self) -> Dict[str, Any]:
        """Get native provider information."""
        return {
            "provider_type": self.provider_type,
            "name": self._name,
            "version": self._version,
            "description": "Built-in workflow execution engine",
            "enabled": self.enabled,
            "available": True,
            "last_health_check": self._last_health_check,
            "configuration": {
                "max_concurrent_workflows": 100,
                "default_timeout": 300
            },
            "capabilities": self.get_capabilities().model_dump()
        }

    async def _execute_ap_invoice_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute AP invoice processing workflow."""
        # Simulate processing time
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "invoice_id": data.get("invoice_id"),
            "processing_result": "approved",
            "amount_processed": data.get("total_amount", 0),
            "validation_passed": True,
            "export_ready": True
        }

    async def _execute_exception_handling(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute exception handling workflow."""
        await asyncio.sleep(0.05)

        return {
            "status": "resolved",
            "exception_id": data.get("exception_id"),
            "resolution_type": "auto_resolved",
            "actions_taken": ["data_correction", "validation_update"]
        }

    async def _execute_weekly_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weekly report generation workflow."""
        await asyncio.sleep(0.2)

        return {
            "status": "generated",
            "report_id": f"report_{int(time.time())}",
            "period": data.get("period", "current_week"),
            "formats": ["pdf", "excel"],
            "recipients": ["finance@company.com"]
        }

    async def _execute_generic_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a generic workflow."""
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "workflow_type": "generic",
            "processed_data": data,
            "output": {"message": "Generic workflow completed successfully"}
        }


class N8nProvider(IntegrationProvider):
    """n8n workflow provider implementation."""

    def __init__(self, config: IntegrationConfig):
        """Initialize the n8n provider."""
        super().__init__(config)
        self._name = "n8n Workflow Provider"
        self._version = "2.0.0"
        self.base_url = self.config.get("base_url", "http://localhost:5678")
        self.api_key = self.config.get("api_key")

    async def execute_workflow(
        self,
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """Execute a workflow using n8n."""
        execution_id = f"n8n_{int(time.time() * 1000)}"
        start_time = time.time()

        try:
            logger.info(f"Executing n8n workflow: {request.workflow_type}")

            # Get workflow ID for the requested type
            workflow_id = self._get_workflow_id(request.workflow_type)
            if not workflow_id:
                raise ValueError(f"No workflow configured for {request.workflow_type}")

            # Execute workflow via n8n API
            result = await self._trigger_n8n_workflow(workflow_id, request.data)

            execution_time_ms = int((time.time() - start_time) * 1000)
            self.record_execution(True, execution_time_ms)

            return WorkflowExecutionResponse(
                execution_id=execution_id,
                workflow_type=request.workflow_type,
                provider_type=self.provider_type,
                status=WorkflowStatus.RUNNING,
                started_at=datetime.utcnow(),
                result=result,
                duration_ms=execution_time_ms,
                provider_details={
                    "provider": "n8n",
                    "workflow_id": workflow_id,
                    "execution_mode": "remote"
                }
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            self.record_execution(False, execution_time_ms)

            logger.error(f"n8n workflow execution failed: {str(e)}")
            return WorkflowExecutionResponse(
                execution_id=execution_id,
                workflow_type=request.workflow_type,
                provider_type=self.provider_type,
                status=WorkflowStatus.FAILED,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                error={
                    "message": str(e),
                    "type": "n8n_execution_error"
                },
                duration_ms=execution_time_ms,
                provider_details={
                    "provider": "n8n",
                    "execution_mode": "remote"
                }
            )

    async def is_available(self) -> bool:
        """Check if n8n service is available."""
        try:
            if not self.api_key:
                return False

            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"X-N8N-API-KEY": self.api_key}
                async with session.get(
                    f"{self.base_url}/rest/healthz",
                    headers=headers
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.warning(f"n8n health check failed: {str(e)}")
            return False

    def get_capabilities(self) -> ProviderCapabilities:
        """Get n8n provider capabilities."""
        return ProviderCapabilities(
            supported_workflows=[
                "ap_invoice_processing",
                "exception_handling",
                "weekly_report_generation"
            ],
            max_concurrent_workflows=50,
            max_execution_time=1800,
            features=[
                ProviderCapability.WEBHOOK_SUPPORT,
                ProviderCapability.VISUAL_WORKFLOW_EDITOR,
                ProviderCapability.ERROR_HANDLING,
                ProviderCapability.MONITORING,
                ProviderCapability.DRY_RUN
            ],
            limitations=["Depends on external service", "Limited to configured workflows"],
            performance_metrics={
                "average_response_time_ms": 200,
                "throughput_per_second": 5,
                "memory_usage_mb": 256
            }
        )

    def get_provider_info(self) -> Dict[str, Any]:
        """Get n8n provider information."""
        return {
            "provider_type": self.provider_type,
            "name": self._name,
            "version": self._version,
            "description": "External n8n workflow automation platform",
            "enabled": self.enabled,
            "available": None,  # Will be determined by health check
            "last_health_check": self._last_health_check,
            "configuration": {
                "base_url": self.base_url,
                "api_key_configured": bool(self.api_key)
            },
            "capabilities": self.get_capabilities().model_dump()
        }

    def _get_workflow_id(self, workflow_type: str) -> Optional[str]:
        """Get n8n workflow ID for a given workflow type."""
        workflow_mappings = {
            "ap_invoice_processing": self.config.get("ap_workflow_id"),
            "exception_handling": self.config.get("exception_workflow_id"),
            "weekly_report_generation": self.config.get("report_workflow_id"),
        }
        return workflow_mappings.get(workflow_type)

    async def _trigger_n8n_workflow(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger workflow execution in n8n."""
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "X-N8N-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "workflowData": data,
                "runData": {}
            }

            async with session.post(
                f"{self.base_url}/rest/workflows/{workflow_id}/execute",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"n8n API error: {response.status} - {error_text}")

                return await response.json()


class IntegrationFactory:
    """Factory class for managing integration providers."""

    def __init__(self, config: FactoryConfig):
        """Initialize the integration factory."""
        self.config = config
        self.default_provider = config.default_provider
        self.providers: Dict[IntegrationType, IntegrationProvider] = {}
        self.fallback_enabled = config.fallback_enabled
        self.auto_failover = config.auto_failover
        self._circuit_breaker_enabled = config.circuit_breaker_enabled

        # Initialize providers
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all configured providers."""
        for provider_config in self.config.providers:
            try:
                provider = self._create_provider(provider_config)
                self.providers[provider_config.provider_type] = provider
                logger.info(f"Initialized provider: {provider_config.provider_type}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_config.provider_type}: {str(e)}")

    def _create_provider(self, config: IntegrationConfig) -> IntegrationProvider:
        """Create a provider instance based on configuration."""
        provider_classes = {
            IntegrationType.NATIVE: NativeProvider,
            IntegrationType.N8N: N8nProvider,
        }

        provider_class = provider_classes.get(config.provider_type)
        if not provider_class:
            raise ValueError(f"Unknown provider type: {config.provider_type}")

        return provider_class(config)

    def get_provider(self, provider_type: IntegrationType) -> Optional[IntegrationProvider]:
        """Get a specific provider by type."""
        provider = self.providers.get(provider_type)
        return provider if provider and provider.enabled else None

    def get_default_provider(self) -> Optional[IntegrationProvider]:
        """Get the default provider."""
        return self.get_provider(self.default_provider)

    def get_available_providers(self) -> List[IntegrationProvider]:
        """Get all available (enabled and healthy) providers."""
        return [provider for provider in self.providers.values() if provider.enabled]

    async def execute_workflow(
        self,
        provider_type: Optional[IntegrationType],
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """Execute a workflow using specified or default provider with fallback."""
        # Determine which provider to use
        if provider_type:
            primary_provider = self.get_provider(provider_type)
        else:
            primary_provider = self.get_default_provider()

        if not primary_provider:
            raise ValueError("No available provider found")

        # Try primary provider first
        try:
            # Check if provider is available
            if await primary_provider.is_available():
                logger.info(f"Executing workflow with provider: {primary_provider.provider_type}")
                return await primary_provider.execute_workflow(request)
            else:
                logger.warning(f"Primary provider {primary_provider.provider_type} is not available")

        except Exception as e:
            logger.error(f"Primary provider failed: {str(e)}")

            # Check if auto failover is enabled
            if not self.auto_failover:
                raise

        # Fallback to other providers if enabled
        if self.fallback_enabled:
            return await self._execute_with_fallback(primary_provider.provider_type, request)

        raise ValueError("No available provider and fallback is disabled")

    async def _execute_with_fallback(
        self,
        failed_provider_type: IntegrationType,
        request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """Execute workflow with fallback to other available providers."""
        available_providers = [
            provider for provider in self.get_available_providers()
            if provider.provider_type != failed_provider_type
        ]

        # Sort by priority
        available_providers.sort(key=lambda p: p.priority)

        for provider in available_providers:
            try:
                if await provider.is_available():
                    logger.info(f"Falling back to provider: {provider.provider_type}")
                    return await provider.execute_workflow(request)
            except Exception as e:
                logger.warning(f"Fallback provider {provider.provider_type} also failed: {str(e)}")
                continue

        raise ValueError("All providers failed and no fallback available")

    async def health_check_all(self) -> FactoryStatusResponse:
        """Perform health check on all providers."""
        health_responses = []
        available_count = 0

        for provider in self.providers.values():
            health_response = await provider.health_check()
            health_responses.append(health_response)

            if health_response.healthy:
                available_count += 1

        enabled_providers = [
            provider for provider in self.providers.values()
            if provider.enabled
        ]

        return FactoryStatusResponse(
            default_provider=self.default_provider,
            total_providers=len(self.providers),
            enabled_providers=len(enabled_providers),
            available_providers=available_count,
            fallback_enabled=self.fallback_enabled,
            auto_failover=self.auto_failover,
            provider_health=health_responses,
            last_health_check=datetime.utcnow()
        )

    def register_provider(self, config: IntegrationConfig) -> None:
        """Register a new provider."""
        try:
            provider = self._create_provider(config)
            self.providers[config.provider_type] = provider
            logger.info(f"Registered new provider: {config.provider_type}")
        except Exception as e:
            logger.error(f"Failed to register provider {config.provider_type}: {str(e)}")
            raise

    def unregister_provider(self, provider_type: IntegrationType) -> None:
        """Unregister a provider."""
        if provider_type in self.providers:
            del self.providers[provider_type]
            logger.info(f"Unregistered provider: {provider_type}")

    def update_provider_config(
        self,
        provider_type: IntegrationType,
        updates: Dict[str, Any]
    ) -> None:
        """Update configuration for an existing provider."""
        provider = self.providers.get(provider_type)
        if not provider:
            # If provider doesn't exist, check if we should create it
            if "enabled" in updates and updates["enabled"]:
                logger.info(f"Creating new provider {provider_type}")
                self.register_provider(IntegrationConfig(
                    provider_type=provider_type,
                    enabled=updates["enabled"],
                    priority=updates.get("priority", 10),
                    config=updates.get("config", {})
                ))
                provider = self.providers.get(provider_type)
            else:
                raise ValueError(f"Provider {provider_type} not found")

        # Update configuration
        for key, value in updates.items():
            if hasattr(provider, key):
                setattr(provider, key, value)
            elif key in provider.config:
                provider.config[key] = value

        logger.info(f"Updated configuration for provider: {provider_type}")

    def get_metrics(self) -> FactoryMetrics:
        """Get factory-wide metrics."""
        provider_metrics = []
        total_executions = 0
        total_successes = 0
        total_failures = 0
        most_used_provider = None
        max_executions = 0
        total_execution_time = 0

        for provider in self.providers.values():
            metrics = provider.get_metrics()
            # Use CUSTOM_WORKFLOW for aggregated metrics across all workflow types
            provider_metrics.append(ExecutionMetrics(
                provider_type=metrics["provider_type"],
                workflow_type=WorkflowType.CUSTOM_WORKFLOW,  # Aggregated across all workflows
                total_executions=metrics["total_executions"],
                successful_executions=metrics["successful_executions"],
                failed_executions=metrics["failed_executions"],
                average_execution_time_ms=metrics["average_execution_time_ms"],
                last_execution=metrics["last_execution"],
                success_rate=metrics["success_rate"],
                error_rate=metrics["error_rate"]
            ))

            total_executions += metrics["total_executions"]
            total_successes += metrics["successful_executions"]
            total_failures += metrics["failed_executions"]
            total_execution_time += metrics["total_execution_time_ms"]

            if metrics["total_executions"] > max_executions:
                max_executions = metrics["total_executions"]
                most_used_provider = metrics["provider_type"]

        overall_success_rate = (
            total_successes / total_executions if total_executions > 0 else 0.0
        )

        average_execution_time = (
            total_execution_time / total_executions if total_executions > 0 else 0.0
        )

        return FactoryMetrics(
            total_executions=total_executions,
            total_successes=total_successes,
            total_failures=total_failures,
            overall_success_rate=overall_success_rate,
            provider_metrics=provider_metrics,
            most_used_provider=most_used_provider or self.default_provider,
            average_execution_time_ms=average_execution_time,
            last_updated=datetime.utcnow()
        )


# Global factory instance
_integration_factory: Optional[IntegrationFactory] = None


def get_integration_factory() -> IntegrationFactory:
    """Get the global integration factory instance."""
    global _integration_factory

    if _integration_factory is None:
        # Create default configuration
        config = FactoryConfig(
            default_provider=getattr(settings, 'INTEGRATION_DEFAULT_PROVIDER', 'native'),
            providers=[
                IntegrationConfig(
                    provider_type='native',
                    enabled=True,
                    priority=1
                ),
                IntegrationConfig(
                    provider_type='n8n',
                    enabled=getattr(settings, 'USE_N8N', False),
                    priority=2,
                    config={
                        'base_url': getattr(settings, 'N8N_BASE_URL', 'http://localhost:5678'),
                        'api_key': getattr(settings, 'N8N_API_KEY', None)
                    }
                )
            ],
            fallback_enabled=getattr(settings, 'INTEGRATION_FALLBACK_ENABLED', True),
            auto_failover=getattr(settings, 'INTEGRATION_AUTO_FAILOVER', True)
        )

        _integration_factory = IntegrationFactory(config)

    return _integration_factory


def configure_integration_factory(config: FactoryConfig) -> None:
    """Configure the global integration factory."""
    global _integration_factory
    _integration_factory = IntegrationFactory(config)