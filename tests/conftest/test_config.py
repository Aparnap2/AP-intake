"""
Comprehensive test configuration for AP Intake system.
Provides shared fixtures, mocks, and test utilities.
"""

import asyncio
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.db.session import get_db, Base
from app.models.invoice import Invoice, InvoiceStatus
from app.models.reference import Vendor
from app.services.docling_service import DoclingService
from app.services.validation_service import ValidationService
from app.services.storage_service import StorageService
from app.services.export_service import ExportService
from app.services.llm_service import LLMService
from app.workflows.invoice_processor import InvoiceProcessor

# Test database settings
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    return engine


@pytest.fixture(scope="session")
def test_engine_sync():
    """Create synchronous test database engine for migrations."""
    engine = create_engine(
        TEST_DATABASE_URL_SYNC,
        echo=False,
        future=True,
    )
    return engine


@pytest.fixture(scope="session")
async def db_session_factory(test_engine):
    """Create test database session factory."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with db_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_client(db_session) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def temp_file() -> Generator[Path, None, None]:
    """Create temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        temp_path = Path(temp.name)
        # Write some test content
        temp.write(b"%PDF-1.4\n%fake pdf content for testing")
        yield temp_path
        temp_path.unlink(missing_ok=True)


@pytest.fixture
def sample_invoice_data() -> Dict[str, Any]:
    """Sample invoice extraction data for testing."""
    return {
        "header": {
            "vendor_name": "Test Vendor Inc",
            "invoice_no": "INV-2024-001",
            "invoice_date": "2024-01-15",
            "due_date": "2024-02-15",
            "po_no": "PO-2024-001",
            "currency": "USD",
            "subtotal": 1000.00,
            "tax": 100.00,
            "total": 1100.00,
        },
        "lines": [
            {
                "description": "Test Product 1",
                "quantity": 2,
                "unit_price": 500.00,
                "amount": 1000.00,
                "sku": "PROD-001"
            }
        ],
        "confidence": {
            "header": {
                "vendor_name": 0.95,
                "invoice_no": 0.98,
                "invoice_date": 0.92,
                "total": 0.97,
                "overall": 0.95
            },
            "lines": [0.90],
            "overall": 0.93
        },
        "overall_confidence": 0.93,
        "metadata": {
            "file_path": "/tmp/test_invoice.pdf",
            "file_hash": "test_hash_123",
            "file_size": 1024,
            "pages_processed": 1,
            "extracted_at": datetime.utcnow().isoformat(),
            "parser_version": "docling-2.60.1"
        }
    }


@pytest.fixture
def sample_vendor() -> Dict[str, Any]:
    """Sample vendor data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Vendor Inc",
        "tax_id": "12-3456789",
        "currency": "USD",
        "credit_limit": 10000.0,
        "active": True,
        "status": "active",
        "payment_terms": "NET30",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


@pytest_asyncio.fixture
async def sample_vendor_record(db_session, sample_vendor) -> Vendor:
    """Create sample vendor record in database."""
    vendor = Vendor(**sample_vendor)
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


@pytest_asyncio.fixture
async def sample_invoice_record(db_session, sample_vendor_record) -> Invoice:
    """Create sample invoice record in database."""
    invoice = Invoice(
        id=str(uuid.uuid4()),
        vendor_id=sample_vendor_record.id,
        file_path="/tmp/test_invoice.pdf",
        file_hash="test_hash_123",
        status=InvoiceStatus.RECEIVED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)
    return invoice


@pytest.fixture
def mock_docling_service() -> MagicMock:
    """Mock DoclingService for testing."""
    mock = AsyncMock(spec=DoclingService)
    mock.extract_from_content.return_value = {
        "header": {"vendor_name": "Test Vendor", "invoice_no": "INV-001"},
        "lines": [{"description": "Test Item", "amount": 100.0}],
        "overall_confidence": 0.95
    }
    return mock


@pytest.fixture
def mock_validation_service() -> MagicMock:
    """Mock ValidationService for testing."""
    mock = AsyncMock(spec=ValidationService)
    mock.validate_invoice.return_value = {
        "passed": True,
        "confidence_score": 0.95,
        "total_issues": 0,
        "error_count": 0,
        "warning_count": 0,
        "issues": [],
        "check_results": {
            "structure_check": True,
            "header_fields_check": True,
            "line_items_check": True,
            "math_check": True,
            "business_rules_check": True,
            "duplicate_check": True,
            "vendor_policy_check": True,
            "matching_check": True
        }
    }
    return mock


@pytest.fixture
def mock_storage_service() -> MagicMock:
    """Mock StorageService for testing."""
    mock = AsyncMock(spec=StorageService)
    mock.file_exists.return_value = True
    mock.get_file_content.return_value = b"fake pdf content"
    mock.store_file.return_value = "/tmp/stored_file.pdf"
    return mock


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Mock LLMService for testing."""
    mock = AsyncMock(spec=LLMService)
    mock.patch_low_confidence_fields.return_value = {
        "header": {"vendor_name": "Enhanced Vendor", "invoice_no": "INV-001"},
        "lines": [{"description": "Enhanced Item", "amount": 100.0}],
        "overall_confidence": 0.98
    }
    return mock


@pytest.fixture
def mock_export_service() -> MagicMock:
    """Mock ExportService for testing."""
    mock = AsyncMock(spec=ExportService)
    mock.export_to_json.return_value = '{"test": "json_export"}'
    mock.export_to_csv.return_value = "test_csv_content"
    mock.export_for_erp.return_value = '{"erp_format": "test"}'
    return mock


@pytest.fixture
def mock_invoice_processor() -> MagicMock:
    """Mock InvoiceProcessor for testing."""
    mock = AsyncMock(spec=InvoiceProcessor)
    mock.process_invoice.return_value = {
        "invoice_id": str(uuid.uuid4()),
        "status": "staged",
        "export_ready": True,
        "processing_history": [
            {"step": "receive", "status": "completed", "duration_ms": 100}
        ]
    }
    return mock


@pytest.fixture
def invalid_invoice_data() -> Dict[str, Any]:
    """Invalid invoice data for negative testing."""
    return {
        "header": {
            "vendor_name": "",  # Missing required field
            "invoice_no": None,  # Missing required field
            "invoice_date": "invalid-date",  # Invalid format
            "total": -100.0,  # Invalid amount
        },
        "lines": [],  # No line items
        "confidence": {"overall": 0.3},  # Low confidence
        "overall_confidence": 0.3
    }


@pytest.fixture
def large_invoice_data() -> Dict[str, Any]:
    """Large invoice data for performance testing."""
    lines = []
    for i in range(100):
        lines.append({
            "description": f"Test Product {i+1}",
            "quantity": i + 1,
            "unit_price": 10.0 * (i + 1),
            "amount": 10.0 * (i + 1) * (i + 1),
            "sku": f"PROD-{i+1:03d}"
        })

    return {
        "header": {
            "vendor_name": "Large Test Vendor Inc",
            "invoice_no": "LARGE-INV-001",
            "invoice_date": "2024-01-15",
            "total": sum(line["amount"] for line in lines),
            "currency": "USD"
        },
        "lines": lines,
        "confidence": {"overall": 0.95},
        "overall_confidence": 0.95
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_celery_app():
    """Mock Celery app for testing."""
    from unittest.mock import patch
    with patch('app.workers.celery_app.celery_app') as mock:
        mock.send_task.return_value = AsyncMock(id="test-task-id")
        yield mock


@pytest.fixture
def mock_langfuse():
    """Mock Langfuse client for testing."""
    with patch('app.workflows.invoice_processor.Langfuse') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    from unittest.mock import patch
    with patch('boto3.client') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        mock_instance.upload_fileobj.return_value = {"Key": "test-key"}
        mock_instance.download_fileobj.return_value = None
        yield mock_instance


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    from unittest.mock import patch
    with patch('app.services.gmail_service.GmailService') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        mock_instance.fetch_invoices.return_value = []
        mock_instance.send_notification.return_value = True
        yield mock_instance


@pytest.fixture
def mock_quickbooks_service():
    """Mock QuickBooks service for testing."""
    from unittest.mock import patch
    with patch('app.services.quickbooks_service.QuickBooksService') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        mock_instance.create_invoice.return_value = {"Id": "qb-123"}
        mock_instance.get_vendor.return_value = {"Id": "vendor-123"}
        yield mock_instance


# Test utilities
class TestDataGenerator:
    """Utility class for generating test data."""

    @staticmethod
    def create_invoice_data(
        vendor_name: str = "Test Vendor",
        invoice_total: float = 1000.0,
        line_items: int = 3,
        confidence: float = 0.95
    ) -> Dict[str, Any]:
        """Generate invoice test data with specified parameters."""
        lines = []
        for i in range(line_items):
            amount = invoice_total / line_items
            lines.append({
                "description": f"Test Product {i+1}",
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
                "sku": f"PROD-{i+1:03d}"
            })

        return {
            "header": {
                "vendor_name": vendor_name,
                "invoice_no": f"INV-{uuid.uuid4().hex[:8]}",
                "invoice_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "due_date": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "currency": "USD",
                "subtotal": invoice_total * 0.9,
                "tax": invoice_total * 0.1,
                "total": invoice_total,
            },
            "lines": lines,
            "confidence": {"overall": confidence},
            "overall_confidence": confidence,
            "metadata": {
                "extracted_at": datetime.utcnow().isoformat(),
                "parser_version": "docling-2.60.1-test"
            }
        }

    @staticmethod
    def create_vendor_data(
        name: str = "Test Vendor",
        currency: str = "USD",
        credit_limit: float = 10000.0,
        active: bool = True
    ) -> Dict[str, Any]:
        """Generate vendor test data."""
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "tax_id": f"12-{uuid.uuid4().hex[:8]}",
            "currency": currency,
            "credit_limit": credit_limit,
            "active": active,
            "status": "active" if active else "inactive",
            "payment_terms": "NET30",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }


@pytest.fixture
def test_data_generator():
    """Provide test data generator instance."""
    return TestDataGenerator()


# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    import time
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class Metric:
        name: str
        duration_ms: float
        memory_mb: float
        timestamp: datetime

    class PerformanceMonitor:
        def __init__(self):
            self.metrics: List[Metric] = []
            self.start_time: Optional[float] = None
            self.current_test: Optional[str] = None

        def start_test(self, test_name: str):
            """Start monitoring a test."""
            self.current_test = test_name
            self.start_time = time.time()

        def end_test(self):
            """End monitoring and record metrics."""
            if self.start_time and self.current_test:
                duration_ms = (time.time() - self.start_time) * 1000
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                except ImportError:
                    memory_mb = 0.0

                metric = Metric(
                    name=self.current_test,
                    duration_ms=duration_ms,
                    memory_mb=memory_mb,
                    timestamp=datetime.utcnow()
                )
                self.metrics.append(metric)

                self.start_time = None
                self.current_test = None

        def get_metrics(self) -> List[Metric]:
            """Get all recorded metrics."""
            return self.metrics.copy()

    return PerformanceMonitor()