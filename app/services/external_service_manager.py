"""
Enhanced external service manager with production-ready reliability patterns.
Implements circuit breakers, rate limiting, intelligent retries, and cost controls.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
import json
import hashlib
import functools

import httpx
import redis.asyncio as redis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.core.enhanced_config import enhanced_settings
from app.core.exceptions import ExternalServiceException

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class ServiceMetrics:
    """Service metrics for monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_response_time: float = 0.0
    error_rate: float = 0.0
    last_minute_errors: int = 0
    last_minute_requests: int = 0


@dataclass
class CostTracker:
    """Cost tracking for external services."""
    service_name: str
    daily_spend: float = 0.0
    monthly_spend: float = 0.0
    daily_limit: float = 100.0
    monthly_limit: float = 2000.0
    last_reset_date: datetime = field(default_factory=datetime.utcnow)
    last_month_reset: datetime = field(default_factory=datetime.utcnow().replace(day=1))
    requests_today: int = 0
    requests_this_month: int = 0

    def should_allow_request(self, estimated_cost: float = 0.0) -> bool:
        """Check if request should be allowed based on cost limits."""
        self.reset_counters_if_needed()

        # Check daily limit
        if self.daily_spend + estimated_cost > self.daily_limit:
            logger.warning(f"Daily cost limit exceeded for {self.service_name}")
            return False

        # Check monthly limit
        if self.monthly_spend + estimated_cost > self.monthly_limit:
            logger.warning(f"Monthly cost limit exceeded for {self.service_name}")
            return False

        return True

    def record_cost(self, cost: float):
        """Record cost for a request."""
        self.reset_counters_if_needed()
        self.daily_spend += cost
        self.monthly_spend += cost
        self.requests_today += 1
        self.requests_this_month += 1

    def reset_counters_if_needed(self):
        """Reset counters if time period has passed."""
        now = datetime.utcnow()

        # Reset daily counter
        if now.date() > self.last_reset_date.date():
            self.daily_spend = 0.0
            self.requests_today = 0
            self.last_reset_date = now

        # Reset monthly counter
        if now.month != self.last_month_reset.month or now.year != self.last_month_reset.year:
            self.monthly_spend = 0.0
            self.requests_this_month = 0
            self.last_month_reset = now.replace(day=1)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "daily_spend": self.daily_spend,
            "monthly_spend": self.monthly_spend,
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "daily_utilization": self.daily_spend / self.daily_limit,
            "monthly_utilization": self.monthly_spend / self.monthly_limit,
            "requests_today": self.requests_today,
            "requests_this_month": self.requests_this_month
        }


class CircuitBreaker:
    """Circuit breaker implementation for external services."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise ExternalServiceException("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker reset to CLOSED")

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time
        }


class RateLimiter:
    """Token bucket rate limiter implementation."""

    def __init__(self, requests_per_second: int, burst_capacity: int):
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.tokens = burst_capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a token from the bucket."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            tokens_to_add = elapsed * self.requests_per_second
            self.tokens = min(self.burst_capacity, self.tokens + tokens_to_add)
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    async def wait_for_token(self, timeout: float = 30.0) -> bool:
        """Wait for a token to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(0.1)
        return False


class ExternalServiceManager(ABC):
    """Base class for external service managers with enhanced reliability patterns."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = ServiceMetrics()
        self.cost_tracker = CostTracker(
            service_name=service_name,
            daily_limit=getattr(enhanced_settings, service_name, {}).get("cost_control", {}).get("daily_limit", 100.0),
            monthly_limit=getattr(enhanced_settings, service_name, {}).get("cost_control", {}).get("monthly_limit", 2000.0)
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(enhanced_settings, service_name, {}).get("circuit_breaker", {}).get("failure_threshold", 5),
            recovery_timeout=getattr(enhanced_settings, service_name, {}).get("circuit_breaker", {}).get("recovery_timeout_seconds", 60)
        )
        self.rate_limiter = RateLimiter(
            requests_per_second=getattr(enhanced_settings, service_name, {}).get("rate_limit", {}).get("requests_per_second", 10),
            burst_capacity=getattr(enhanced_settings, service_name, {}).get("rate_limit", {}).get("burst_capacity", 20)
        )
        self.redis_client: Optional[redis.Redis] = None

    async def initialize(self):
        """Initialize the service manager."""
        try:
            self.redis_client = redis.from_url(enhanced_settings.redis_url)
            await self.redis_client.ping()
            logger.info(f"Connected to Redis for {self.service_name} service manager")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory caching only.")

    @abstractmethod
    async def _make_request(self, method: str, url: str, **kwargs) -> Any:
        """Make actual HTTP request to external service."""
        pass

    async def _estimate_request_cost(self, method: str, url: str, **kwargs) -> float:
        """Estimate cost of the request. Override in subclasses."""
        return 0.0

    async def call_api(
        self,
        method: str,
        url: str,
        cost_estimate: Optional[float] = None,
        retry_on_failure: bool = True,
        **kwargs
    ) -> Any:
        """Make API call with all reliability patterns applied."""
        start_time = time.time()

        # Check cost limits
        if cost_estimate is None:
            cost_estimate = await self._estimate_request_cost(method, url, **kwargs)

        if not self.cost_tracker.should_allow_request(cost_estimate):
            raise ExternalServiceException(f"Cost limit exceeded for {self.service_name}")

        # Apply rate limiting
        if not await self.rate_limiter.wait_for_token():
            raise ExternalServiceException(f"Rate limit exceeded for {self.service_name}")

        # Update metrics
        self.metrics.total_requests += 1
        self.metrics.last_minute_requests += 1

        try:
            # Make request through circuit breaker
            result = await self.circuit_breaker.call(
                self._execute_with_retry if retry_on_failure else self._execute_without_retry,
                method, url, **kwargs
            )

            # Record success
            response_time = time.time() - start_time
            self._record_success(response_time)

            # Record cost
            actual_cost = await self._calculate_actual_cost(result, cost_estimate)
            self.cost_tracker.record_cost(actual_cost)

            return result

        except Exception as e:
            # Record failure
            response_time = time.time() - start_time
            self._record_failure(e, response_time)
            raise

    async def _execute_with_retry(self, method: str, url: str, **kwargs) -> Any:
        """Execute request with retry logic."""
        retry_config = enhanced_settings.get_retry_config(self.service_name)

        @retry(
            stop=stop_after_attempt(retry_config.max_attempts),
            wait=wait_exponential(
                multiplier=retry_config.base_delay_seconds,
                max=retry_config.max_delay_seconds,
                exp_base=retry_config.exponential_base
            ),
            retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO)
        )
        async def _request_with_retry():
            return await self._make_request(method, url, **kwargs)

        return await _request_with_retry()

    async def _execute_without_retry(self, method: str, url: str, **kwargs) -> Any:
        """Execute request without retry."""
        return await self._make_request(method, url, **kwargs)

    async def _calculate_actual_cost(self, response: Any, estimated_cost: float) -> float:
        """Calculate actual cost from response. Override in subclasses."""
        return estimated_cost

    def _record_success(self, response_time: float):
        """Record successful request metrics."""
        self.metrics.successful_requests += 1
        self.metrics.last_success = datetime.utcnow()

        # Update average response time
        if self.metrics.total_requests > 0:
            self.metrics.average_response_time = (
                (self.metrics.average_response_time * (self.metrics.successful_requests - 1) + response_time) /
                self.metrics.successful_requests
            )

        # Update error rate
        self.metrics.error_rate = self.metrics.failed_requests / self.metrics.total_requests

    def _record_failure(self, error: Exception, response_time: float):
        """Record failed request metrics."""
        self.metrics.failed_requests += 1
        self.metrics.last_failure = datetime.utcnow()
        self.metrics.last_minute_errors += 1

        # Update error rate
        self.metrics.error_rate = self.metrics.failed_requests / self.metrics.total_requests

        # Log error with context
        logger.error(f"Service {self.service_name} request failed: {error}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        circuit_state = self.circuit_breaker.get_state()
        cost_stats = self.cost_tracker.get_usage_stats()

        return {
            "service": self.service_name,
            "status": "healthy" if self.metrics.error_rate < 0.1 else "degraded",
            "circuit_breaker": circuit_state,
            "rate_limiter": {
                "tokens_remaining": self.rate_limiter.tokens,
                "capacity": self.rate_limiter.burst_capacity
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "success_rate": (self.metrics.successful_requests / max(self.metrics.total_requests, 1)) * 100,
                "error_rate": self.metrics.error_rate * 100,
                "average_response_time": self.metrics.average_response_time,
                "last_minute_errors": self.metrics.last_minute_errors,
                "last_minute_requests": self.metrics.last_minute_requests
            },
            "cost_tracking": cost_stats,
            "last_success": self.metrics.last_success.isoformat() if self.metrics.last_success else None,
            "last_failure": self.metrics.last_failure.isoformat() if self.metrics.last_failure else None
        }

    async def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = ServiceMetrics()
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.state = CircuitState.CLOSED
        logger.info(f"Reset metrics for {self.service_name}")

    async def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            await self.redis_client.close()


class LLMServiceManager(ExternalServiceManager):
    """Enhanced LLM service manager with cost controls and fallback strategies."""

    def __init__(self):
        super().__init__("openrouter")
        self.config = enhanced_settings.openrouter
        self.fallback_models = self.config.fallback_models
        self.current_model_index = 0

    async def _make_request(self, method: str, url: str, **kwargs) -> Any:
        """Make request to OpenRouter API."""
        headers = kwargs.get("headers", {})
        headers.update({
            "HTTP-Referer": self.config.app_url,
            "X-Title": self.config.app_name,
            "Authorization": f"Bearer {self.config.api_key}"
        })
        kwargs["headers"] = headers

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    async def _estimate_request_cost(self, method: str, url: str, **kwargs) -> float:
        """Estimate cost based on token usage."""
        try:
            # Extract token usage from request
            data = kwargs.get("json", {})
            messages = data.get("messages", [])

            # Rough estimation
            prompt_tokens = sum(len(msg.get("content", "")) // 4 for msg in messages)  # 1 token ≈ 4 chars
            completion_tokens = self.config.max_tokens  # Max allowed

            input_cost = (prompt_tokens / 1000) * self.config.cost_per_1k_input
            output_cost = (completion_tokens / 1000) * self.config.cost_per_1k_output

            return input_cost + output_cost
        except Exception:
            return 0.01  # Default small cost if estimation fails

    async def _calculate_actual_cost(self, response: Dict[str, Any], estimated_cost: float) -> float:
        """Calculate actual cost from API response."""
        try:
            usage = response.get("usage", {})
            if usage:
                input_cost = (usage.get("prompt_tokens", 0) / 1000) * self.config.cost_per_1k_input
                output_cost = (usage.get("completion_tokens", 0) / 1000) * self.config.cost_per_1k_output
                return input_cost + output_cost
        except Exception:
            pass
        return estimated_cost

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute chat completion with fallback strategy."""
        models_to_try = [model] if model else []
        if self.config.enable_model_fallback:
            models_to_try.extend(self.fallback_models)

        last_error = None

        for attempt_model in models_to_try:
            try:
                payload = {
                    "model": attempt_model,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                    "temperature": kwargs.get("temperature", self.config.temperature)
                }

                result = await self.call_api(
                    "POST",
                    f"{self.config.base_url}/chat/completions",
                    json=payload,
                    cost_estimate=await self._estimate_request_cost("POST", "", json=payload)
                )

                logger.info(f"Successfully used model: {attempt_model}")
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Model {attempt_model} failed: {e}")
                continue

        # All models failed
        raise ExternalServiceException(f"All models failed. Last error: {last_error}")


# Factory function for service managers
def create_service_manager(service_name: str) -> ExternalServiceManager:
    """Create appropriate service manager based on service name."""
    managers = {
        "openrouter": LLMServiceManager,
        # Add other service managers as needed
    }

    manager_class = managers.get(service_name)
    if not manager_class:
        raise ValueError(f"No service manager available for {service_name}")

    return manager_class()


# Decorator for easy service management
def with_external_service(service_name: str):
    """Decorator to add external service management to functions."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            manager = create_service_manager(service_name)
            await manager.initialize()
            try:
                # Inject manager into function if it accepts it
                if 'service_manager' in func.__code__.co_varnames:
                    kwargs['service_manager'] = manager
                return await func(*args, **kwargs)
            finally:
                await manager.cleanup()
        return wrapper
    return decorator