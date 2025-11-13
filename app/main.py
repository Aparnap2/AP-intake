"""
FastAPI application entry point for AP Intake & Validation system.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware import Middleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.api_v1.api import api_router
from app.middleware.performance_middleware import PerformanceMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import APIntakeException
from app.db.session import engine, SessionLocal
from app.workers.celery_app import celery_app
from sqlalchemy import text

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy (CSP)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https: blob:",
            "connect-src 'self' ws: wss:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


# Rate Limiting Middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""

    def __init__(self, app, calls: int = 100, period: int = 3600):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}

    async def dispatch(self, request: Request, call_next):
        import time

        # Get client IP
        client_ip = request.client.host
        now = time.time()

        # Clean old entries
        if client_ip in self.clients:
            self.clients[client_ip] = [
                req_time for req_time in self.clients[client_ip]
                if now - req_time < self.period
            ]
        else:
            self.clients[client_ip] = []

        # Check rate limit
        if len(self.clients[client_ip]) >= self.calls:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )

        # Add current request
        self.clients[client_ip].append(now)

        return await call_next(request)


# Initialize Sentry if configured
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info("Starting AP Intake & Validation API")

    # Check database connection (skip for testing without DB)
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("Database connection successful")
    except Exception as e:
        logger.warning(f"Database connection failed: {e} - Continuing without database")

    # Check Celery worker
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats:
            logger.info("Celery workers are available")
        else:
            logger.warning("No Celery workers detected")
    except Exception as e:
        logger.warning(f"Could not check Celery workers: {e}")

    yield

    # Shutdown
    logger.info("Shutting down AP Intake & Validation API")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add performance monitoring middleware
app.add_middleware(
    PerformanceMiddleware,
    enable_detailed_profiling=settings.DEBUG,  # Enable detailed profiling in dev
    enable_memory_tracking=True,
    enable_database_tracking=True,
    enable_response_tracking=True
)

# Add rate limiting (more lenient in development)
if settings.ENVIRONMENT.lower() in ["development", "dev"]:
    app.add_middleware(RateLimitMiddleware, calls=1000, period=3600)  # 1000 requests/hour for dev
else:
    app.add_middleware(RateLimitMiddleware, calls=100, period=3600)   # 100 requests/hour for production

# Add gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware (restrictive in production)
if settings.ENVIRONMENT.lower() in ["development", "dev"]:
    # Allow localhost and common dev origins in development
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]
    allowed_hosts = ["localhost", "127.0.0.1", "*"]
else:
    # Restrictive in production - configure these properly
    allowed_origins = [settings.UI_HOST] if hasattr(settings, 'UI_HOST') and settings.UI_HOST else []
    allowed_hosts = settings.ALLOWED_HOSTS if settings.ALLOWED_HOSTS != ["*"] else ["api.company.com"]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "accept",
        "accept-language",
        "content-language",
        "authorization",
        "content-type",
        "x-api-key",
        "x-requested-with"
    ],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)

# Add HTTPS redirect in production
if settings.ENVIRONMENT.lower() not in ["development", "dev"]:
    app.add_middleware(HTTPSRedirectMiddleware)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests and responses."""
    import time

    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        logger.info(
            f"Request completed: {request.method} {request.url} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )

        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url} "
            f"Error: {str(e)} "
            f"Time: {process_time:.3f}s"
        )
        raise


@app.exception_handler(APIntakeException)
async def ap_intake_exception_handler(request: Request, exc: APIntakeException):
    """Handle custom AP Intake exceptions."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Metrics endpoint for Prometheus
@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.PROJECT_DESCRIPTION,
        "docs_url": f"{settings.API_V1_STR}/docs",
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )