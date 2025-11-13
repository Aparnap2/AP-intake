"""
Tests for the swappable integration factory pattern.
Implements TDD approach for integration provider architecture.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from app.services.integration_factory import (
    IntegrationFactory,
    IntegrationProvider,
    IntegrationType,
    NativeProvider,
    N8nProvider,
    IntegrationConfig
)
from app.schemas.integration_schemas import (
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    ProviderCapabilities
)


class TestIntegrationConfig:
    """Test the IntegrationConfig dataclass."""

    def test_integration_config_creation(self):
        """Test creating an integration configuration."""
        config = IntegrationConfig(
            provider_type=IntegrationType.NATIVE,
            enabled=True,
            priority=1,
            config={"timeout": 30}
        )

        assert config.provider_type == IntegrationType.NATIVE
        assert config.enabled is True
        assert config.priority == 1
        assert config.config["timeout"] == 30

    def test_integration_config_defaults(self):
        """Test integration configuration with defaults."""
        config = IntegrationConfig(provider_type=IntegrationType.N8N)

        assert config.enabled is True  # Default value
        assert config.priority == 10  # Default value
        assert config.config == {}  # Default value


class TestIntegrationProvider:
    """Test the base IntegrationProvider abstract class."""

    def test_provider_interface_methods(self):
        """Test that provider interface defines required methods."""
        # This test ensures the abstract base class has the required methods
        abstract_methods = [
            'execute_workflow',
            'get_capabilities',
            'is_available',
            'get_provider_info'
        ]

        for method in abstract_methods:
            assert hasattr(IntegrationProvider, method), f"Missing method: {method}"


class TestNativeProvider:
    """Test the native workflow provider implementation."""

    @pytest.fixture
    def native_provider(self):
        """Create a native provider instance for testing."""
        config = IntegrationConfig(
            provider_type=IntegrationType.NATIVE,
            enabled=True,
            priority=1
        )
        return NativeProvider(config)

    def test_native_provider_initialization(self, native_provider):
        """Test native provider initialization."""
        assert native_provider.provider_type == IntegrationType.NATIVE
        assert native_provider.enabled is True
        assert native_provider.priority == 1

    @pytest.mark.asyncio
    async def test_native_provider_is_available(self, native_provider):
        """Test native provider availability check."""
        is_available = await native_provider.is_available()
        assert is_available is True  # Native provider should always be available

    def test_native_provider_get_capabilities(self, native_provider):
        """Test native provider capabilities."""
        capabilities = native_provider.get_capabilities()

        assert isinstance(capabilities, ProviderCapabilities)
        assert capabilities.supported_workflows is not None
        assert capabilities.max_concurrent_workflows > 0
        assert capabilities.features is not None

    def test_native_provider_get_provider_info(self, native_provider):
        """Test native provider information."""
        info = native_provider.get_provider_info()

        assert info["provider_type"] == IntegrationType.NATIVE
        assert info["name"] == "Native Workflow Provider"
        assert info["version"] is not None
        assert info["enabled"] is True

    @pytest.mark.asyncio
    async def test_native_provider_execute_workflow(self, native_provider):
        """Test native workflow execution."""
        request = WorkflowExecutionRequest(
            workflow_type="ap_invoice_processing",
            data={"invoice_id": "test_123", "amount": 1000},
            options={"dry_run": True}
        )

        response = await native_provider.execute_workflow(request)

        assert isinstance(response, WorkflowExecutionResponse)
        assert response.execution_id is not None
        assert response.status in ["running", "completed", "failed"]
        assert response.workflow_type == "ap_invoice_processing"
        assert response.provider_type == IntegrationType.NATIVE


class TestN8nProvider:
    """Test the n8n workflow provider implementation."""

    @pytest.fixture
    def n8n_provider(self):
        """Create an n8n provider instance for testing."""
        config = IntegrationConfig(
            provider_type=IntegrationType.N8N,
            enabled=True,
            priority=2,
            config={
                "base_url": "http://localhost:5678",
                "api_key": "test_key"
            }
        )
        return N8nProvider(config)

    def test_n8n_provider_initialization(self, n8n_provider):
        """Test n8n provider initialization."""
        assert n8n_provider.provider_type == IntegrationType.N8N
        assert n8n_provider.enabled is True
        assert n8n_provider.priority == 2
        assert n8n_provider.config["base_url"] == "http://localhost:5678"

    @pytest.mark.asyncio
    async def test_n8n_provider_is_available_success(self, n8n_provider):
        """Test n8n provider availability check when service is up."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock successful health check
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value.__aenter__.return_value = mock_response

            is_available = await n8n_provider.is_available()
            assert is_available is True

    @pytest.mark.asyncio
    async def test_n8n_provider_is_available_failure(self, n8n_provider):
        """Test n8n provider availability check when service is down."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock failed health check
            mock_get.side_effect = Exception("Connection failed")

            is_available = await n8n_provider.is_available()
            assert is_available is False

    def test_n8n_provider_get_capabilities(self, n8n_provider):
        """Test n8n provider capabilities."""
        capabilities = n8n_provider.get_capabilities()

        assert isinstance(capabilities, ProviderCapabilities)
        assert capabilities.supported_workflows is not None
        assert capabilities.max_concurrent_workflows > 0
        assert "webhook_support" in capabilities.features
        assert "visual_workflow_editor" in capabilities.features

    def test_n8n_provider_get_provider_info(self, n8n_provider):
        """Test n8n provider information."""
        info = n8n_provider.get_provider_info()

        assert info["provider_type"] == IntegrationType.N8N
        assert info["name"] == "n8n Workflow Provider"
        assert info["base_url"] == "http://localhost:5678"
        assert info["enabled"] is True

    @pytest.mark.asyncio
    async def test_n8n_provider_execute_workflow(self, n8n_provider):
        """Test n8n workflow execution."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful workflow execution
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "executionId": "exec_123",
                "status": "running"
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            request = WorkflowExecutionRequest(
                workflow_type="ap_invoice_processing",
                data={"invoice_id": "test_123", "amount": 1000}
            )

            response = await n8n_provider.execute_workflow(request)

            assert isinstance(response, WorkflowExecutionResponse)
            assert response.execution_id == "exec_123"
            assert response.status == "running"
            assert response.workflow_type == "ap_invoice_processing"
            assert response.provider_type == IntegrationType.N8N


class TestIntegrationFactory:
    """Test the IntegrationFactory class."""

    @pytest.fixture
    def factory_config(self):
        """Create factory configuration for testing."""
        return {
            "default_provider": IntegrationType.NATIVE,
            "providers": [
                IntegrationConfig(
                    provider_type=IntegrationType.NATIVE,
                    enabled=True,
                    priority=1
                ),
                IntegrationConfig(
                    provider_type=IntegrationType.N8N,
                    enabled=False,  # Disabled for testing
                    priority=2,
                    config={"base_url": "http://localhost:5678"}
                )
            ],
            "fallback_enabled": True,
            "auto_failover": True
        }

    @pytest.fixture
    def integration_factory(self, factory_config):
        """Create an IntegrationFactory instance for testing."""
        return IntegrationFactory(factory_config)

    def test_factory_initialization(self, integration_factory, factory_config):
        """Test factory initialization with configuration."""
        assert integration_factory.default_provider == IntegrationType.NATIVE
        assert len(integration_factory.providers) == 2
        assert integration_factory.fallback_enabled is True
        assert integration_factory.auto_failover is True

    def test_factory_get_provider_success(self, integration_factory):
        """Test getting a provider successfully."""
        provider = integration_factory.get_provider(IntegrationType.NATIVE)
        assert isinstance(provider, NativeProvider)
        assert provider.enabled is True

    def test_factory_get_provider_disabled(self, integration_factory):
        """Test getting a disabled provider."""
        provider = integration_factory.get_provider(IntegrationType.N8N)
        assert provider is None  # Should return None for disabled provider

    def test_factory_get_provider_not_found(self, integration_factory):
        """Test getting a provider that doesn't exist."""
        provider = integration_factory.get_provider(IntegrationType.QUICKBOOKS)
        assert provider is None

    def test_factory_get_default_provider(self, integration_factory):
        """Test getting the default provider."""
        provider = integration_factory.get_default_provider()
        assert isinstance(provider, NativeProvider)
        assert provider.provider_type == IntegrationType.NATIVE

    def test_factory_get_available_providers(self, integration_factory):
        """Test getting all available providers."""
        providers = integration_factory.get_available_providers()

        assert len(providers) == 1  # Only native provider is enabled
        assert all(provider.enabled for provider in providers)

    @pytest.mark.asyncio
    async def test_factory_execute_workflow_success(self, integration_factory):
        """Test successful workflow execution through factory."""
        request = WorkflowExecutionRequest(
            workflow_type="ap_invoice_processing",
            data={"invoice_id": "test_123"}
        )

        response = await integration_factory.execute_workflow(
            provider_type=IntegrationType.NATIVE,
            request=request
        )

        assert isinstance(response, WorkflowExecutionResponse)
        assert response.provider_type == IntegrationType.NATIVE
        assert response.execution_id is not None

    @pytest.mark.asyncio
    async def test_factory_execute_workflow_with_fallback(self, integration_factory):
        """Test workflow execution with fallback."""
        # Configure factory for fallback testing
        integration_factory.fallback_enabled = True
        integration_factory.auto_failover = True

        request = WorkflowExecutionRequest(
            workflow_type="ap_invoice_processing",
            data={"invoice_id": "test_123"}
        )

        response = await integration_factory.execute_workflow(
            provider_type=IntegrationType.N8N,  # Disabled provider
            request=request
        )

        assert isinstance(response, WorkflowExecutionResponse)
        assert response.provider_type == IntegrationType.NATIVE  # Should fallback to native

    @pytest.mark.asyncio
    async def test_factory_execute_workflow_no_fallback(self, integration_factory):
        """Test workflow execution when fallback is disabled."""
        integration_factory.fallback_enabled = False

        request = WorkflowExecutionRequest(
            workflow_type="ap_invoice_processing",
            data={"invoice_id": "test_123"}
        )

        with pytest.raises(ValueError, match="No available provider"):
            await integration_factory.execute_workflow(
                provider_type=IntegrationType.N8N,
                request=request
            )

    def test_factory_register_provider(self, integration_factory):
        """Test registering a new provider."""
        new_config = IntegrationConfig(
            provider_type=IntegrationType.QUICKBOOKS,
            enabled=True,
            priority=3,
            config={"api_key": "test_key"}
        )

        integration_factory.register_provider(new_config)

        assert len(integration_factory.providers) == 3
        provider = integration_factory.get_provider(IntegrationType.QUICKBOOKS)
        assert provider is not None
        assert provider.enabled is True

    def test_factory_unregister_provider(self, integration_factory):
        """Test unregistering a provider."""
        integration_factory.unregister_provider(IntegrationType.NATIVE)

        assert len(integration_factory.providers) == 1
        provider = integration_factory.get_provider(IntegrationType.NATIVE)
        assert provider is None

    def test_factory_update_provider_config(self, integration_factory):
        """Test updating provider configuration."""
        new_config = {
            "enabled": False,
            "priority": 5,
            "config": {"timeout": 60}
        }

        integration_factory.update_provider_config(
            IntegrationType.NATIVE,
            new_config
        )

        provider = integration_factory.get_provider(IntegrationType.NATIVE)
        assert provider is None  # Should be None since disabled

        # Re-enable for other tests
        integration_factory.update_provider_config(
            IntegrationType.NATIVE,
            {"enabled": True, "priority": 1}
        )


class TestIntegrationType:
    """Test the IntegrationType enum."""

    def test_integration_type_values(self):
        """Test integration type enum values."""
        assert IntegrationType.NATIVE.value == "native"
        assert IntegrationType.N8N.value == "n8n"
        assert IntegrationType.QUICKBOOKS.value == "quickbooks"

    def test_integration_type_creation(self):
        """Test creating integration types."""
        native = IntegrationType.NATIVE
        assert native == "native"

        # Test creation from string
        native_from_string = IntegrationType("native")
        assert native_from_string == IntegrationType.NATIVE