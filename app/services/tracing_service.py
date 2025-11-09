"""
Distributed tracing service using OpenTelemetry for comprehensive observability.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from dataclasses import dataclass, field

from opentelemetry import trace, baggage, context
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace import Status, StatusCode, SpanKind

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SpanMetadata:
    """Metadata for tracing spans."""
    component: str
    operation: str
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    invoice_id: Optional[str] = None
    additional_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostTracking:
    """Cost tracking for operations."""
    operation_cost: float = 0.0
    llm_tokens_used: int = 0
    llm_cost: float = 0.0
    storage_cost: float = 0.0
    compute_cost: float = 0.0
    currency: str = "USD"


class TracingService:
    """Comprehensive distributed tracing service with cost tracking."""

    def __init__(self):
        """Initialize the tracing service."""
        self.logger = logging.getLogger(__name__)
        self.tracer_provider = None
        self.tracer = None
        self._cost_tracking_enabled = True
        self._setup_tracing()

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": settings.PROJECT_NAME,
                "service.version": settings.VERSION,
                "service.environment": settings.ENVIRONMENT,
                "deployment.environment": settings.ENVIRONMENT,
            })

            # Initialize tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(self.tracer_provider)

            # Setup exporters based on configuration
            if hasattr(settings, 'JAEGER_ENDPOINT') and settings.JAEGER_ENDPOINT:
                jaeger_exporter = JaegerExporter(
                    endpoint=settings.JAEGER_ENDPOINT,
                    collector_endpoint=settings.JAEGER_ENDPOINT,
                )
                span_processor = BatchSpanProcessor(jaeger_exporter)
                self.tracer_provider.add_span_processor(span_processor)
                self.logger.info("Jaeger tracing initialized")

            elif hasattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT') and settings.OTEL_EXPORTER_OTLP_ENDPOINT:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                )
                span_processor = BatchSpanProcessor(otlp_exporter)
                self.tracer_provider.add_span_processor(span_processor)
                self.logger.info("OTLP tracing initialized")

            else:
                # Console exporter for development
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                console_exporter = ConsoleSpanExporter()
                span_processor = BatchSpanProcessor(console_exporter)
                self.tracer_provider.add_span_processor(span_processor)
                self.logger.info("Console tracing initialized for development")

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Set global propagator
            set_global_textmap({})

            self.logger.info("Distributed tracing service initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize tracing service: {e}")
            # Create a no-op tracer for fallback
            self.tracer = trace.get_tracer(__name__)

    @asynccontextmanager
    async def trace_span(
        self,
        name: str,
        metadata: SpanMetadata,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create a traced span with comprehensive metadata and cost tracking.

        Args:
            name: Span name
            metadata: Span metadata
            kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)

        Yields:
            Dictionary containing span context and cost tracking
        """
        if not self.tracer:
            # Fallback if tracer is not available
            yield {"trace_id": str(uuid.uuid4()), "span_id": str(uuid.uuid4())}
            return

        # Create span attributes
        attributes = {
            "component": metadata.component,
            "operation": metadata.operation,
            "service.name": settings.PROJECT_NAME,
            "service.version": settings.VERSION,
        }

        # Add optional attributes
        if metadata.resource_id:
            attributes["resource.id"] = metadata.resource_id
        if metadata.user_id:
            attributes["user.id"] = metadata.user_id
        if metadata.workflow_id:
            attributes["workflow.id"] = metadata.workflow_id
        if metadata.invoice_id:
            attributes["invoice.id"] = metadata.invoice_id

        # Add additional attributes
        attributes.update(metadata.additional_attributes)

        try:
            with self.tracer.start_as_current_span(
                name,
                kind=kind,
                attributes=attributes,
            ) as span:
                start_time = time.time()
                cost_tracking = CostTracking()

                # Create span context for yield
                span_context = {
                    "trace_id": format(span.get_trace_context().trace_id, "032x"),
                    "span_id": format(span.get_span_context().span_id, "016x"),
                    "span": span,
                    "start_time": start_time,
                    "cost_tracking": cost_tracking,
                }

                try:
                    yield span_context
                except Exception as e:
                    # Record exception on span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    # Calculate duration and add to span
                    duration = time.time() - start_time
                    span.set_attribute("duration_seconds", duration)

                    # Add cost tracking if enabled
                    if self._cost_tracking_enabled:
                        span.set_attribute("cost.total", cost_tracking.operation_cost)
                        span.set_attribute("cost.llm_tokens", cost_tracking.llm_tokens_used)
                        span.set_attribute("cost.llm", cost_tracking.llm_cost)
                        span.set_attribute("cost.storage", cost_tracking.storage_cost)
                        span.set_attribute("cost.compute", cost_tracking.compute_cost)
                        span.set_attribute("cost.currency", cost_tracking.currency)

                    # Set success status if not already set
                    if span.status.status_code == StatusCode.UNSET:
                        span.set_status(Status(StatusCode.OK))

        except Exception as e:
            self.logger.error(f"Failed to create trace span '{name}': {e}")
            # Fallback context
            yield {"trace_id": str(uuid.uuid4()), "span_id": str(uuid.uuid4())}

    def add_event(
        self,
        span_context: Dict[str, Any],
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an event to the current span."""
        try:
            span = span_context.get("span")
            if not span:
                return

            event_attributes = attributes or {}
            if timestamp:
                event_attributes["timestamp"] = timestamp.isoformat()

            span.add_event(event_name, attributes=event_attributes)

        except Exception as e:
            self.logger.error(f"Failed to add event '{event_name}' to span: {e}")

    def set_attribute(
        self,
        span_context: Dict[str, Any],
        key: str,
        value: Union[str, int, float, bool, List[str]],
    ) -> None:
        """Set an attribute on the current span."""
        try:
            span = span_context.get("span")
            if not span:
                return

            span.set_attribute(key, value)

        except Exception as e:
            self.logger.error(f"Failed to set attribute '{key}' on span: {e}")

    def track_cost(
        self,
        span_context: Dict[str, Any],
        operation_cost: float = 0.0,
        llm_tokens: int = 0,
        llm_cost: float = 0.0,
        storage_cost: float = 0.0,
        compute_cost: float = 0.0,
    ) -> None:
        """Track operation costs."""
        if not self._cost_tracking_enabled:
            return

        try:
            cost_tracking = span_context.get("cost_tracking")
            if not cost_tracking:
                return

            cost_tracking.operation_cost += operation_cost
            cost_tracking.llm_tokens_used += llm_tokens
            cost_tracking.llm_cost += llm_cost
            cost_tracking.storage_cost += storage_cost
            cost_tracking.compute_cost += compute_cost

            # Update span attributes in real-time
            span = span_context.get("span")
            if span:
                span.set_attribute("cost.total", cost_tracking.operation_cost)
                span.set_attribute("cost.llm_tokens", cost_tracking.llm_tokens_used)
                span.set_attribute("cost.llm", cost_tracking.llm_cost)

        except Exception as e:
            self.logger.error(f"Failed to track cost: {e}")

    def trace_workflow_step(
        self,
        workflow_id: str,
        step_name: str,
        invoice_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Trace a workflow step with standardized metadata.

        Args:
            workflow_id: Workflow identifier
            step_name: Name of the workflow step
            invoice_id: Optional invoice identifier
            **kwargs: Additional metadata

        Yields:
            Span context for the workflow step
        """
        metadata = SpanMetadata(
            component="workflow",
            operation=step_name,
            workflow_id=workflow_id,
            invoice_id=invoice_id,
            additional_attributes=kwargs,
        )

        span_name = f"workflow.{step_name}"
        return self.trace_span(span_name, metadata, kind=SpanKind.INTERNAL)

    def trace_api_request(
        self,
        method: str,
        endpoint: str,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Trace an API request with standardized metadata.

        Args:
            method: HTTP method
            endpoint: API endpoint
            user_id: Optional user identifier
            **kwargs: Additional metadata

        Yields:
            Span context for the API request
        """
        metadata = SpanMetadata(
            component="api",
            operation=f"{method} {endpoint}",
            user_id=user_id,
            additional_attributes={
                "http.method": method,
                "http.route": endpoint,
                **kwargs
            },
        )

        span_name = f"api.{method.lower()}.{endpoint.replace('/', '_').strip('_')}"
        return self.trace_span(span_name, metadata, kind=SpanKind.SERVER)

    def trace_external_service(
        self,
        service_name: str,
        operation: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Trace an external service call.

        Args:
            service_name: Name of the external service
            operation: Operation being performed
            **kwargs: Additional metadata

        Yields:
            Span context for the external service call
        """
        metadata = SpanMetadata(
            component="external_service",
            operation=f"{service_name}.{operation}",
            additional_attributes={
                "external.service": service_name,
                "external.operation": operation,
                **kwargs
            },
        )

        span_name = f"external.{service_name}.{operation}"
        return self.trace_span(span_name, metadata, kind=SpanKind.CLIENT)

    def trace_database_operation(
        self,
        operation: str,
        table: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Trace a database operation.

        Args:
            operation: Database operation (query, insert, update, delete)
            table: Optional table name
            **kwargs: Additional metadata

        Yields:
            Span context for the database operation
        """
        metadata = SpanMetadata(
            component="database",
            operation=operation,
            additional_attributes={
                "db.operation": operation,
                **({"db.table": table} if table else {}),
                **kwargs
            },
        )

        span_name = f"db.{operation}"
        return self.trace_span(span_name, metadata, kind=SpanKind.CLIENT)

    def get_trace_context(self) -> Dict[str, str]:
        """Get current trace context for propagation."""
        try:
            current_span = trace.get_current_span()
            if current_span:
                context = current_span.get_span_context()
                return {
                    "trace_id": format(context.trace_id, "032x"),
                    "span_id": format(context.span_id, "016x"),
                    "trace_flags": format(context.trace_flags, "02x"),
                }
        except Exception as e:
            self.logger.error(f"Failed to get trace context: {e}")

        return {}

    def inject_context(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into headers for propagation."""
        try:
            # This would integrate with your propagator
            # For now, return headers unchanged
            return headers
        except Exception as e:
            self.logger.error(f"Failed to inject trace context: {e}")
            return headers

    def extract_context(self, headers: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract trace context from headers."""
        try:
            # This would integrate with your propagator
            # For now, return None
            return None
        except Exception as e:
            self.logger.error(f"Failed to extract trace context: {e}")
            return None

    async def shutdown(self) -> None:
        """Shutdown the tracing service."""
        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()
                self.logger.info("Tracing service shutdown completed")
        except Exception as e:
            self.logger.error(f"Failed to shutdown tracing service: {e}")


# Singleton instance
tracing_service = TracingService()