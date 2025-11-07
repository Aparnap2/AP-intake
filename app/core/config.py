"""
Application configuration settings.
"""

import os
from typing import List, Optional

from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Basic application settings
    PROJECT_NAME: str = "AP Intake & Validation"
    PROJECT_DESCRIPTION: str = "Transform emailed PDF invoices into validated, structured bills"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOWED_HOSTS: List[str] = ["*"]

    @validator("ALLOWED_HOSTS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Storage
    STORAGE_TYPE: str = "local"  # local, s3, r2, supabase
    STORAGE_PATH: str = "./storage"

    # Enhanced Local Storage Configuration
    STORAGE_COMPRESSION_ENABLED: bool = True
    STORAGE_COMPRESSION_TYPE: str = "gzip"  # gzip, lz4, none
    STORAGE_COMPRESSION_THRESHOLD: int = 1024  # bytes

    # AWS S3 configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None

    # Docling configuration
    DOCLING_CONFIDENCE_THRESHOLD: float = 0.85
    DOCLING_MAX_PAGES: int = 50
    DOCLING_TIMEOUT: int = 30

    # LangGraph configuration
    LANGGRAPH_PERSIST_PATH: str = "./langgraph_storage"
    LANGGRAPH_STATE_TTL: int = 3600

    # LLM configuration for low-confidence patching
    OPENAI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "openrouter"  # openai, openrouter
    LLM_MODEL: str = "z-ai/glm-4.5-air:free"  # Default to OpenRouter model
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.1
    # OpenRouter app identification headers
    OPENROUTER_APP_NAME: str = "AP Intake & Validation"
    OPENROUTER_APP_URL: str = "https://github.com/ap-team/ap-intake"

    # Email configuration
    GMAIL_CLIENT_ID: Optional[str] = "your-gmail-client-id.apps.googleusercontent.com"
    GMAIL_CLIENT_SECRET: Optional[str] = "your-gmail-client-secret"
    GRAPH_TENANT_ID: Optional[str] = None
    GRAPH_CLIENT_ID: Optional[str] = None
    GRAPH_CLIENT_SECRET: Optional[str] = None

    # Email ingestion configuration
    EMAIL_INGESTION_ENABLED: bool = True
    EMAIL_MONITORING_INTERVAL_MINUTES: int = 60
    EMAIL_MAX_PROCESSING_DAYS: int = 7
    EMAIL_SECURITY_VALIDATION_ENABLED: bool = True
    EMAIL_AUTO_PROCESS_INVOICES: bool = True

    # Export configuration
    EXPORT_PATH: str = "./exports"
    QUICKBOOKS_SANDBOX_CLIENT_ID: Optional[str] = "ABks36hUKi4CnTlqhEKeztfPxZC083pJ4kH7vqPPtTXbNhTwRy"
    QUICKBOOKS_SANDBOX_CLIENT_SECRET: Optional[str] = "tNca9AST3GahKyxVWYziia6vyODid81CV3CEQey7"
    QUICKBOOKS_REDIRECT_URI: Optional[str] = "http://localhost:8000/api/v1/quickbooks/callback"
    QUICKBOOKS_ENVIRONMENT: str = "sandbox"  # sandbox or production
    XERO_SANDBOX_CLIENT_ID: Optional[str] = None
    XERO_SANDBOX_CLIENT_SECRET: Optional[str] = None

    # File handling
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_FILE_TYPES: List[str] = ["pdf", "jpeg", "jpg", "png"]

    @validator("ALLOWED_FILE_TYPES", pre=True)
    def parse_file_types(cls, v):
        """Parse allowed file types from comma-separated string."""
        if isinstance(v, str):
            return [i.strip().lower() for i in v.split(",")]
        return v

    # Background worker configuration
    WORKER_CONCURRENCY: int = 4
    WORKER_PREFETCH_MULTIPLIER: int = 1
    WORKER_TASK_SOFT_TIME_LIMIT: int = 300
    WORKER_TASK_TIME_LIMIT: int = 600

    # Observability
    SENTRY_DSN: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Logging
    LOG_LEVEL: str = "INFO"

    @validator("LOG_LEVEL", pre=True)
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    # UI configuration
    UI_HOST: str = "http://localhost:3000"
    API_HOST: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


# Create settings instance
settings = Settings()