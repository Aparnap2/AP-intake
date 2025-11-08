"""
Enhanced security and monitoring middleware for production deployments.
"""

import time
import logging
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from urllib.parse import urlencode

from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis.asyncio as redis
import prometheus_client as prom
from prometheus_client import Counter, Histogram, Gauge, generate_latest

from app.core.enhanced_config import enhanced_settings
from app.core.exceptions import SecurityException

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

API_REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['service', 'method', 'status']
)

API_RESPONSE_TIME = Histogram(
    'api_response_time_seconds',
    'API response time in seconds',
    ['service', 'method']
)

COST_TRACKER = Gauge(
    'external_service_cost_dollars',
    'External service costs in dollars',
    ['service', 'period']
)

SECURITY_EVENTS = Counter(
    'security_events_total',
    'Total security events',
    ['event_type', 'severity']
)


class SecurityConfig:
    """Security configuration for middleware."""

    def __init__(self):
        self.settings = enhanced_settings.security
        self.failed_attempts = {}  # IP -> list of timestamps
        self.blocked_ips = {}  # IP -> unblock time
        self.api_keys = {}  # API key -> user info
        self.rate_limits = {}  # endpoint -> rate limit info

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked."""
        if ip in self.blocked_ips:
            if datetime.utcnow() > self.blocked_ips[ip]:
                del self.blocked_ips[ip]
                return False
            return True
        return False

    def record_failed_attempt(self, ip: str):
        """Record a failed attempt for rate limiting."""
        now = datetime.utcnow()
        if ip not in self.failed_attempts:
            self.failed_attempts[ip] = []

        # Clean old attempts (older than lockout duration)
        cutoff = now - timedelta(minutes=self.settings.lockout_duration_minutes)
        self.failed_attempts[ip] = [
            attempt for attempt in self.failed_attempts[ip] if attempt > cutoff
        ]

        self.failed_attempts[ip].append(now)

        # Block IP if too many attempts
        if len(self.failed_attempts[ip]) >= self.settings.max_login_attempts:
            unblock_time = now + timedelta(minutes=self.settings.lockout_duration_minutes)
            self.blocked_ips[ip] = unblock_time
            SECURITY_EVENTS.labels(
                event_type='ip_blocked',
                severity='high'
            ).inc()
            return True
        return False

    def generate_api_key(self, user_info: Dict[str, Any]) -> str:
        """Generate a new API key for a user."""
        api_key = secrets.token_urlsafe(32)
        self.api_keys[api_key] = {
            'user_info': user_info,
            'created_at': datetime.utcnow(),
            'last_used': None,
            'request_count': 0
        }
        return api_key

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return user info."""
        if api_key in self.api_keys:
            key_info = self.api_keys[api_key]
            key_info['last_used'] = datetime.utcnow()
            key_info['request_count'] += 1
            return key_info['user_info']
        return None


security_config = SecurityConfig()


class SecurityMonitoringMiddleware(BaseHTTPMiddleware):
    """Enhanced security and monitoring middleware."""

    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.security_config = security_config

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security and monitoring."""
        start_time = time.time()
        client_ip = self._get_client_ip(request)

        try:
            # Security checks
            await self._perform_security_checks(request, client_ip)

            # Execute request
            response = await call_next(request)

            # Record metrics
            await self._record_metrics(request, response, start_time)

            # Add security headers
            response = self._add_security_headers(response)

            return response

        except HTTPException as e:
            # Record security events
            if e.status_code == status.HTTP_401_UNAUTHORIZED:
                self.security_config.record_failed_attempt(client_ip)
                SECURITY_EVENTS.labels(
                    event_type='unauthorized_access',
                    severity='medium'
                ).inc()

            # Record failed request metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(e.status_code)
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            raise

        except Exception as e:
            # Record unexpected errors
            SECURITY_EVENTS.labels(
                event_type='unexpected_error',
                severity='high'
            ).inc()
            logger.error(f"Unexpected error in security middleware: {e}")
            raise

    async def _perform_security_checks(self, request: Request, client_ip: str):
        """Perform comprehensive security checks."""
        # IP blocking check
        if self.security_config.is_ip_blocked(client_ip):
            SECURITY_EVENTS.labels(
                event_type='blocked_ip_access_attempt',
                severity='high'
            ).inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address is blocked"
            )

        # HTTPS enforcement in production
        if (enhanced_settings.is_production() and
            self.security_config.require_https and
            request.url.scheme != "https"):
            SECURITY_EVENTS.labels(
                event_type='http_access_attempt',
                severity='medium'
            ).inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTPS is required"
            )

        # Request size validation
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > enhanced_settings.max_file_size_mb * 1024 * 1024:
            SECURITY_EVENTS.labels(
                event_type='oversized_request',
                severity='medium'
            ).inc()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request entity too large"
            )

        # API key validation for protected endpoints
        if self._requires_api_key(request.url.path):
            await self._validate_api_key(request)

    def _requires_api_key(self, path: str) -> bool:
        """Check if endpoint requires API key authentication."""
        protected_paths = [
            "/api/v1/invoices",
            "/api/v1/exports",
            "/api/v1/webhooks"
        ]
        return any(path.startswith(protected_path) for protected_path in protected_paths)

    async def _validate_api_key(self, request: Request):
        """Validate API key from request headers."""
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"}
            )

        user_info = self.security_config.validate_api_key(api_key)
        if not user_info:
            SECURITY_EVENTS.labels(
                event_type='invalid_api_key',
                severity='high'
            ).inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        # Add user info to request state
        request.state.user = user_info

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        headers = enhanced_settings.get_security_headers()

        for header, value in headers.items():
            if value:  # Only add non-empty headers
                response.headers[header] = value

        # Add custom security headers
        response.headers["X-API-Version"] = enhanced_settings.version
        response.headers["X-Environment"] = enhanced_settings.environment
        response.headers["X-Powered-By"] = "AP Intake & Validation System"

        # Remove server information
        if "Server" in response.headers:
            del response.headers["Server"]

        return response

    async def _record_metrics(self, request: Request, response: Response, start_time: float):
        """Record Prometheus metrics for the request."""
        duration = time.time() - start_time

        # General HTTP metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=str(response.status_code)
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        # API-specific metrics for external service calls
        if hasattr(request.state, 'external_service_calls'):
            for call in request.state.external_service_calls:
                API_REQUEST_COUNT.labels(
                    service=call['service'],
                    method=call['method'],
                    status=call['status']
                ).inc()

                API_RESPONSE_TIME.labels(
                    service=call['service'],
                    method=call['method']
                ).observe(call['duration'])

        # Cost tracking (if available)
        if hasattr(request.state, 'cost_tracking'):
            for service, cost in request.state.cost_tracking.items():
                COST_TRACKER.labels(
                    service=service,
                    period='daily'
                ).set(cost['daily'])

                COST_TRACKER.labels(
                    service=service,
                    period='monthly'
                ).set(cost['monthly'])


class APIKeyAuthenticator:
    """API key authentication and management."""

    def __init__(self):
        self.security_config = security_config

    async def generate_api_key(self, user_id: str, permissions: List[str]) -> Dict[str, str]:
        """Generate a new API key for a user."""
        user_info = {
            'user_id': user_id,
            'permissions': permissions,
            'created_by': 'system'
        }

        api_key = self.security_config.generate_api_key(user_info)

        return {
            'api_key': api_key,
            'user_id': user_id,
            'permissions': permissions,
            'created_at': datetime.utcnow().isoformat()
        }

    async def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        if api_key in self.security_config.api_keys:
            del self.security_config.api_keys[api_key]
            SECURITY_EVENTS.labels(
                event_type='api_key_revoked',
                severity='medium'
            ).inc()
            return True
        return False

    async def rotate_api_key(self, old_api_key: str) -> Optional[Dict[str, str]]:
        """Rotate an existing API key."""
        if old_api_key not in self.security_config.api_keys:
            return None

        old_key_info = self.security_config.api_keys[old_api_key]
        user_info = old_key_info['user_info']

        # Generate new key
        new_api_key = self.security_config.generate_api_key(user_info)

        # Revoke old key
        del self.security_config.api_keys[old_api_key]

        SECURITY_EVENTS.labels(
            event_type='api_key_rotated',
            severity='low'
        ).inc()

        return {
            'api_key': new_api_key,
            'user_id': user_info['user_id'],
            'permissions': user_info['permissions'],
            'rotated_at': datetime.utcnow().isoformat()
        }

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        keys = []
        for api_key, key_info in self.security_config.api_keys.items():
            if key_info['user_info']['user_id'] == user_id:
                keys.append({
                    'api_key_prefix': api_key[:8] + "...",
                    'created_at': key_info['created_at'].isoformat(),
                    'last_used': key_info['last_used'].isoformat() if key_info['last_used'] else None,
                    'request_count': key_info['request_count'],
                    'permissions': key_info['user_info']['permissions']
                })
        return keys


class WebhookSignatureValidator:
    """Webhook signature validation for external services."""

    @staticmethod
    def validate_signature(
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = 'sha256'
    ) -> bool:
        """Validate webhook signature."""
        try:
            expected_signature = hmac.new(
                secret.encode(),
                payload,
                algorithm
            ).hexdigest()

            # Compare signatures securely
            return hmac.compare_digest(
                signature.replace(f'{algorithm}=', ''),
                expected_signature
            )
        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return False

    @staticmethod
    def generate_signature(payload: bytes, secret: str, algorithm: str = 'sha256') -> str:
        """Generate webhook signature for testing."""
        signature = hmac.new(
            secret.encode(),
            payload,
            algorithm
        ).hexdigest()
        return f'{algorithm}={signature}'


class MetricsCollector:
    """Enhanced metrics collection for monitoring."""

    def __init__(self):
        self.custom_metrics = {}

    def register_custom_metric(self, name: str, metric_type: str, description: str, labels: List[str] = None):
        """Register a custom metric."""
        if metric_type == 'counter':
            self.custom_metrics[name] = Counter(name, description, labels or [])
        elif metric_type == 'gauge':
            self.custom_metrics[name] = Gauge(name, description, labels or [])
        elif metric_type == 'histogram':
            self.custom_metrics[name] = Histogram(name, description, labels or [])

    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        if name in self.custom_metrics:
            if labels:
                self.custom_metrics[name].labels(**labels).inc(value)
            else:
                self.custom_metrics[name].inc(value)

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        if name in self.custom_metrics:
            if labels:
                self.custom_metrics[name].labels(**labels).set(value)
            else:
                self.custom_metrics[name].set(value)

    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observe a histogram metric value."""
        if name in self.custom_metrics:
            if labels:
                self.custom_metrics[name].labels(**labels).observe(value)
            else:
                self.custom_metrics[name].observe(value)

    def get_metrics_export(self) -> str:
        """Get all metrics in Prometheus format."""
        return generate_latest().decode('utf-8')


# Global instances
api_key_authenticator = APIKeyAuthenticator()
webhook_validator = WebhookSignatureValidator()
metrics_collector = MetricsCollector()

# Initialize custom metrics
metrics_collector.register_custom_metric(
    'external_service_errors_total',
    'counter',
    'Total external service errors',
    ['service', 'error_type']
)

metrics_collector.register_custom_metric(
    'processing_queue_size',
    'gauge',
    'Current processing queue size',
    ['queue_name']
)

metrics_collector.register_custom_metric(
    'document_processing_time_seconds',
    'histogram',
    'Document processing time in seconds',
    ['document_type', 'processing_stage']
)