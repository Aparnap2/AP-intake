"""
Main API router for v1 endpoints.
"""

from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    health,
    invoices,
    vendors,
    exports,
    status,
    exceptions,
    # emails,  # Temporarily commented out due to missing email tables
    celery_monitoring,
    quickbooks,
    analytics,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exports"])
api_router.include_router(status.router, prefix="/status", tags=["System Status"])
api_router.include_router(exceptions.router, prefix="/exceptions", tags=["Exception Management"])
# api_router.include_router(emails.router, prefix="/emails", tags=["Email Ingestion"])  # Temporarily commented out
api_router.include_router(celery_monitoring.router, prefix="/celery", tags=["Celery Monitoring"])
api_router.include_router(quickbooks.router, prefix="/quickbooks", tags=["QuickBooks Integration"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & KPIs"])