"""
Enhanced configuration with production-ready security and reliability patterns.
"""
import os
import secrets
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta

from pydantic import validator, Field
from pydantic_settings import BaseSettings


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""
    requests_per_second: int = 10
    burst_capacity: int = 20
    penalty_duration_seconds: int = 60


class CostControlConfig(BaseSettings):
    """Cost control configuration for external services."""
    daily_limit: float = 100.0
    monthly_limit: float = 2000.0
    alert_thresholds: List[float] = [0.5, 0.8, 0.95]
    emergency_shutdown: bool = True


class RetryConfig(BaseSettings):
    """Enhanced retry configuration."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class CircuitBreakerConfig(BaseSettings):
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    expected_exception: str = "Exception"
    recovery_timeout_max: int = 300


class SecurityConfig(BaseSettings):
    """Enhanced security configuration."""
    require_https: bool = True
    allowed_hosts: List[str] = ["*"]
    cors_origins: List[str] = ["*"]
    api_key_rotation_days: int = 90
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15

    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


class GmailAPIConfig(BaseSettings):
    """Enhanced Gmail API configuration."""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    max_emails_per_batch: int = 25
    max_attachment_size_mb: int = 25
    rate_limit: RateLimitConfig = RateLimitConfig(
        requests_per_second=100,  # Conservative Gmail API limit
        burst_capacity=200
    )
    retry_config: RetryConfig = RetryConfig(max_attempts=5)
    quota_per_day: int = 1000000000  # 1B quota units
    cost_per_request: Dict[str, int] = {
        "message_get": 5,
        "message_list": 5,
        "attachment_get": 10
    }
    quota_reset_hours: int = 24
    enable_quota_monitoring: bool = True


class OpenRouterConfig(BaseSettings):
    """Enhanced OpenRouter LLM configuration."""
    api_key: Optional[str] = None
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "z-ai/glm-4.5-air:free"
    max_tokens: int = 1000
    temperature: float = 0.1
    app_name: str = "AP Intake & Validation"
    app_url: str = "https://github.com/ap-team/ap-intake"

    # Enhanced features
    cost_control: CostControlConfig = CostControlConfig()
    rate_limit: RateLimitConfig = RateLimitConfig(
        requests_per_second=20,
        burst_capacity=50
    )
    retry_config: RetryConfig = RetryConfig(max_attempts=3)
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()

    # Model fallback strategy
    fallback_models: List[str] = [
        "z-ai/glm-4.5-air:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemini-flash-1.5:free"
    ]
    enable_model_fallback: bool = True

    # Cost estimation (update with actual pricing)
    cost_per_1k_input: float = 0.001
    cost_per_1k_output: float = 0.002
    enable_cost_tracking: bool = True


class QuickBooksConfig(BaseSettings):
    """Enhanced QuickBooks configuration with security."""
    sandbox_client_id: Optional[str] = Field(None, env="QUICKBOOKS_SANDBOX_CLIENT_ID")
    sandbox_client_secret: Optional[str] = Field(None, env="QUICKBOOKS_SANDBOX_CLIENT_SECRET")
    redirect_uri: Optional[str] = None
    environment: str = "sandbox"  # sandbox or production

    # Enhanced features
    rate_limit: RateLimitConfig = RateLimitConfig(
        requests_per_second=8,  # QuickBooks allows 500/minute
        burst_capacity=20
    )
    retry_config: RetryConfig = RetryConfig(max_attempts=3)
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()

    # Security enhancements
    oauth_state_ttl_minutes: int = 10
    refresh_token_expiry_buffer_days: int = 7
    enable_token_refresh: bool = True

    # Webhook security
    webhook_secret: Optional[str] = None
    webhook_signature_validation: bool = True

    # Connection limits
    max_connections: int = 20
    connection_timeout_seconds: int = 30
    read_timeout_seconds: int = 60


class DoclingConfig(BaseSettings):
    """Enhanced Docling configuration."""
    confidence_threshold: float = 0.85
    max_pages: int = 50
    timeout_seconds: int = 30

    # Enhanced features
    retry_config: RetryConfig = RetryConfig(max_attempts=2)
    enable_caching: bool = True
    cache_ttl_hours: int = 24
    max_file_size_mb: int = 25
    supported_formats: List[str] = ["pdf", "jpeg", "jpg", "png"]

    # Performance tuning
    max_concurrent_jobs: int = 4
    memory_limit_mb: int = 1024

    # Quality control
    min_confidence_for_auto_approval: float = 0.9
    enable_quality_metrics: bool = True


class StorageConfig(BaseSettings):
    """Enhanced storage configuration."""
    storage_type: str = "local"  # local, s3, r2, supabase
    storage_path: str = "./storage"

    # S3 configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket_name: Optional[str] = None
    s3_endpoint_url: Optional[str] = None

    # Enhanced features
    enable_compression: bool = True
    compression_type: str = "gzip"
    compression_threshold_bytes: int = 1024

    # Security features
    enable_encryption_at_rest: bool = True
    enable_integrity_checks: bool = True
    enable_access_logging: bool = True

    # Retention policies
    default_retention_days: int = 90
    archive_retention_days: int = 365
    enable_versioning: bool = True

    # Performance
    multipart_threshold_mb: int = 100
    max_concurrent_uploads: int = 10


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""
    sentry_dsn: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Enhanced monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    health_check_interval_seconds: int = 30
    enable_performance_tracing: bool = True

    # Alerting
    alert_webhook_url: Optional[str] = None
    alert_email_recipients: List[str] = []
    enable_alerting: bool = True

    # Custom metrics
    track_api_usage: bool = True
    track_processing_times: bool = True
    track_error_rates: bool = True
    track_costs: bool = True


class DatabaseConfig(BaseSettings):
    """Enhanced database configuration."""
    database_url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 3600

    # Connection limits
    max_connections: int = 50
    connection_timeout_seconds: int = 10

    # Health checks
    enable_health_checks: bool = True
    health_check_interval_seconds: int = 60


class EnhancedSettings(BaseSettings):
    """Enhanced application settings with production-ready features."""

    # Basic application settings
    project_name: str = "AP Intake & Validation"
    project_description: str = "Transform emailed PDF invoices into validated, structured bills"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_str: str = "/api/v1"

    # Enhanced security
    security: SecurityConfig = SecurityConfig()
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Enhanced service configurations
    gmail: GmailAPIConfig = GmailAPIConfig()
    openrouter: OpenRouterConfig = OpenRouterConfig()
    quickbooks: QuickBooksConfig = QuickBooksConfig()
    docling: DoclingConfig = DoclingConfig()
    storage: StorageConfig = StorageConfig()
    database: DatabaseConfig = DatabaseConfig()
    monitoring: MonitoringConfig = MonitoringConfig()

    # Background processing
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    worker_concurrency: int = 4
    worker_prefetch_multiplier: int = 1
    worker_task_soft_time_limit: int = 300
    worker_task_time_limit: int = 600

    # Email processing
    email_ingestion_enabled: bool = True
    email_monitoring_interval_minutes: int = 60
    email_max_processing_days: int = 7
    email_auto_process_invoices: bool = True

    # File handling
    max_file_size_mb: int = 25
    allowed_file_types: List[str] = ["pdf", "jpeg", "jpg", "png"]

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    enable_structured_logging: bool = True

    # Environment-specific overrides
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment setting."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v.lower()

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @validator("secret_key")
    def validate_secret_key(cls, v):
        """Validate secret key strength."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        if v in ["your-super-secret-key-here-change-in-production", "secret", "test"]:
            raise ValueError("Secret key appears to be a default value. Please generate a secure key.")
        return v

    # Production readiness checks
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def get_database_config(self) -> Dict[str, any]:
        """Get database configuration dictionary."""
        return {
            "url": self.database.database_url,
            "pool_size": self.database.pool_size,
            "max_overflow": self.database.max_overflow,
            "pool_timeout": self.database.pool_timeout_seconds,
            "pool_recycle": self.database.pool_recycle_seconds,
            "max_connections": self.database.max_connections,
            "connection_timeout": self.database.connection_timeout_seconds
        }

    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for production."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if self.security.require_https else "",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }

    def get_rate_limit_config(self, service: str) -> RateLimitConfig:
        """Get rate limit configuration for a specific service."""
        service_configs = {
            "gmail": self.gmail.rate_limit,
            "openrouter": self.openrouter.rate_limit,
            "quickbooks": self.quickbooks.rate_limit,
            "default": RateLimitConfig()
        }
        return service_configs.get(service, service_configs["default"])

    def get_retry_config(self, service: str) -> RetryConfig:
        """Get retry configuration for a specific service."""
        service_configs = {
            "gmail": self.gmail.retry_config,
            "openrouter": self.openrouter.retry_config,
            "quickbooks": self.quickbooks.retry_config,
            "docling": self.docling.retry_config,
            "default": RetryConfig()
        }
        return service_configs.get(service, service_configs["default"])

    def get_circuit_breaker_config(self, service: str) -> CircuitBreakerConfig:
        """Get circuit breaker configuration for a specific service."""
        service_configs = {
            "openrouter": self.openrouter.circuit_breaker,
            "quickbooks": self.quickbooks.circuit_breaker,
            "default": CircuitBreakerConfig()
        }
        return service_configs.get(service, service_configs["default"])

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env

        # Pydantic v2 configuration
        validate_assignment = True
        use_enum_values = True


# Create enhanced settings instance
enhanced_settings = EnhancedSettings()

# Generate secure secret key if needed
def generate_secure_secret_key() -> str:
    """Generate a cryptographically secure secret key."""
    return secrets.token_urlsafe(64)

# Environment-specific setup
def setup_environment():
    """Setup environment-specific configurations."""
    if enhanced_settings.is_production():
        # Production-specific setup
        enhanced_settings.debug = False
        enhanced_settings.log_level = "WARNING"
        enhanced_settings.security.require_https = True
        enhanced_settings.monitoring.enable_metrics = True
        enhanced_settings.monitoring.enable_alerting = True

    # Validate critical configurations
    validate_production_configurations()

def validate_production_configurations():
    """Validate production configurations."""
    if enhanced_settings.is_production():
        # Critical security checks
        if not enhanced_settings.secret_key or len(enhanced_settings.secret_key) < 32:
            raise ValueError("Production requires a secure secret key of at least 32 characters")

        if enhanced_settings.debug:
            raise ValueError("Debug mode must be disabled in production")

        if not enhanced_settings.security.require_https:
            raise ValueError("HTTPS must be required in production")

        # Service-specific validations
        if enhanced_settings.openrouter.api_key and enhanced_settings.openrouter.cost_control.daily_limit > 1000:
            raise ValueError("Daily LLM cost limit should be conservative for production")

# Initialize environment setup
setup_environment()