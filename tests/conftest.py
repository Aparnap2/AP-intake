"""
Pytest configuration and fixtures for the AP Intake & Validation system.
"""

import asyncio
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_session(async_engine):
    """Create async session for testing."""
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "name": "Acme Corporation",
        "tax_id": "12-3456789",
        "email": "billing@acme.com",
        "phone": "+1-555-0123",
        "address": "123 Business St, Suite 100, New York, NY 10001",
        "currency": "USD",
        "credit_limit": Decimal("50000.00"),
        "payment_terms_days": "30",
        "active": True,
    }


@pytest.fixture
def sample_ar_invoice_data():
    """Sample AR invoice data for testing."""
    return {
        "invoice_number": "AR-2024-001",
        "invoice_date": datetime.utcnow(),
        "due_date": datetime.utcnow() + timedelta(days=30),
        "currency": "USD",
        "subtotal": Decimal("1000.00"),
        "tax_amount": Decimal("100.00"),
        "total_amount": Decimal("1100.00"),
        "outstanding_amount": Decimal("1100.00"),
        "status": "pending",
        "collection_priority": "medium",
    }