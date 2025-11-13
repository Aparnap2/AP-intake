"""
Main API router for v1 endpoints.
"""

from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    auth,
    health,
    invoices,
    vendors,
    exports,
    status,
    exceptions,
    ingestion,
    # staging,  # Temporarily commented out due to SQLAlchemy table conflicts
    # emails,  # Temporarily commented out due to missing email tables
    celery_monitoring,
    quickbooks,
    analytics,
    metrics,
    dlq,
    # observability,  # Temporarily disabled due to import issues
    # ar,  # Temporarily disabled due to Pydantic compatibility issues
    n8n_webhooks,
    performance,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exports"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Ingestion"])
# api_router.include_router(staging.router, prefix="/staging", tags=["Export Staging"])  # Temporarily commented out
api_router.include_router(status.router, prefix="/status", tags=["System Status"])
api_router.include_router(exceptions.router, prefix="/exceptions", tags=["Exception Management"])
# api_router.include_router(emails.router, prefix="/emails", tags=["Email Ingestion"])  # Temporarily commented out
api_router.include_router(celery_monitoring.router, prefix="/celery", tags=["Celery Monitoring"])
api_router.include_router(quickbooks.router, prefix="/quickbooks", tags=["QuickBooks Integration"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & KPIs"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["SLOs & Metrics"])
api_router.include_router(performance.router, prefix="/performance", tags=["Performance Monitoring"])
api_router.include_router(dlq.router, prefix="/dlq", tags=["Dead Letter Queue"])
# api_router.include_router(observability.router, prefix="/observability", tags=["Observability & Runbooks"])  # Temporarily disabled
# api_router.include_router(ar.router, prefix="/ar", tags=["Accounts Receivable"])  # Temporarily disabled
api_router.include_router(n8n_webhooks.router, prefix="/webhook", tags=["n8n Webhooks"])