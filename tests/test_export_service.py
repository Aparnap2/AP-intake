"""
Tests for the export service.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.api_v1.endpoints.exports import router
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.models.export_models import ExportTemplate, ExportJob, ExportFormat, ExportStatus, ExportDestination
from app.models.invoice import Invoice, InvoiceExtraction, InvoiceStatus
from app.services.export_service import ExportService, ExportFieldTransformer, ExportValidator
from app.schemas.export_schemas import ExportFieldMapping, ExportRequest, ExportConfig


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "header": {
            "vendor_name": "Test Vendor",
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "due_date": "2024-02-15",
            "po_no": "PO-001",
            "currency": "USD",
            "subtotal": 1000.00,
            "tax": 80.00,
            "total": 1080.00
        },
        "lines": [
            {
                "description": "Test Item 1",
                "quantity": 2,
                "unit_price": 500.00,
                "amount": 1000.00
            }
        ],
        "metadata": {
            "invoice_id": str(uuid.uuid4()),
            "vendor_id": str(uuid.uuid4()),
            "processed_at": datetime.utcnow().isoformat(),
            "confidence": {"overall": 0.95},
            "status": "validated"
        }
    }


@pytest.fixture
def export_template(db_session):
    """Create a sample export template."""
    field_mappings = [
        {
            "source_field": "header.vendor_name",
            "target_field": "Vendor Name",
            "field_type": "string",
            "required": True
        },
        {
            "source_field": "header.invoice_no",
            "target_field": "Invoice Number",
            "field_type": "string",
            "required": True
        },
        {
            "source_field": "header.total",
            "target_field": "Total",
            "field_type": "decimal",
            "required": True,
            "transform_function": "currency_format"
        }
    ]

    template = ExportTemplate(
        name="Test Template",
        description="Test export template",
        format=ExportFormat.CSV,
        field_mappings=field_mappings,
        header_config={"title": "Test Export"},
        footer_config={"include_totals": True},
        compression=False,
        encryption=False
    )

    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


class TestExportFieldTransformer:
    """Test the export field transformer."""

    def test_basic_transform(self, sample_invoice_data):
        """Test basic field transformation."""
        field_mappings = [
            ExportFieldMapping(
                source_field="header.vendor_name",
                target_field="Vendor",
                field_type="string",
                required=True
            ),
            ExportFieldMapping(
                source_field="header.total",
                target_field="Amount",
                field_type="decimal",
                required=True
            )
        ]

        transformer = ExportFieldTransformer(field_mappings)
        result = transformer.transform_record(sample_invoice_data)

        assert result["Vendor"] == "Test Vendor"
        assert result["Amount"] == 1080.00

    def test_nested_field_transform(self, sample_invoice_data):
        """Test nested field transformation."""
        field_mappings = [
            ExportFieldMapping(
                source_field="metadata.confidence.overall",
                target_field="Confidence",
                field_type="decimal",
                required=False
            )
        ]

        transformer = ExportFieldTransformer(field_mappings)
        result = transformer.transform_record(sample_invoice_data)

        assert result["Confidence"] == 0.95

    def test_default_value_transform(self, sample_invoice_data):
        """Test default value assignment."""
        # Remove PO number from data
        sample_invoice_data["header"].pop("po_no", None)

        field_mappings = [
            ExportFieldMapping(
                source_field="header.po_no",
                target_field="PO Number",
                field_type="string",
                required=False,
                default_value="N/A"
            )
        ]

        transformer = ExportFieldTransformer(field_mappings)
        result = transformer.transform_record(sample_invoice_data)

        assert result["PO Number"] == "N/A"

    def test_transform_functions(self, sample_invoice_data):
        """Test transformation functions."""
        field_mappings = [
            ExportFieldMapping(
                source_field="header.vendor_name",
                target_field="Vendor",
                field_type="string",
                transform_function="uppercase"
            ),
            ExportFieldMapping(
                source_field="header.total",
                target_field="Amount",
                field_type="decimal",
                transform_function="currency_format"
            )
        ]

        transformer = ExportFieldTransformer(field_mappings)
        result = transformer.transform_record(sample_invoice_data)

        assert result["Vendor"] == "TEST VENDOR"
        assert result["Amount"] == "$1080.00"

    def test_required_field_validation(self, sample_invoice_data):
        """Test required field validation."""
        field_mappings = [
            ExportFieldMapping(
                source_field="header.nonexistent",
                target_field="Missing",
                field_type="string",
                required=True
            )
        ]

        transformer = ExportFieldTransformer(field_mappings)
        with pytest.raises(Exception):  # Should raise ValidationException
            transformer.transform_record(sample_invoice_data)


class TestExportValidator:
    """Test the export validator."""

    def test_required_validation(self):
        """Test required field validation."""
        validation_rules = [
            {
                "field_path": "vendor_name",
                "rule_type": "required",
                "rule_config": {},
                "error_message": "Vendor name is required",
                "severity": "error"
            }
        ]

        validator = ExportValidator(validation_rules)

        # Test valid data
        valid_data = {"vendor_name": "Test Vendor"}
        errors = validator.validate_record(valid_data)
        assert len(errors) == 0

        # Test invalid data
        invalid_data = {"vendor_name": ""}
        errors = validator.validate_record(invalid_data)
        assert len(errors) == 1
        assert errors[0]["field"] == "vendor_name"

    def test_pattern_validation(self):
        """Test pattern validation."""
        validation_rules = [
            {
                "field_path": "invoice_number",
                "rule_type": "pattern",
                "rule_config": {"pattern": r"^INV-\d{4}$"},
                "error_message": "Invoice number must be in format INV-####",
                "severity": "error"
            }
        ]

        validator = ExportValidator(validation_rules)

        # Test valid data
        valid_data = {"invoice_number": "INV-1234"}
        errors = validator.validate_record(valid_data)
        assert len(errors) == 0

        # Test invalid data
        invalid_data = {"invoice_number": "INVALID"}
        errors = validator.validate_record(invalid_data)
        assert len(errors) == 1

    def test_numeric_range_validation(self):
        """Test numeric range validation."""
        validation_rules = [
            {
                "field_path": "amount",
                "rule_type": "numeric_range",
                "rule_config": {"min": 0, "max": 10000},
                "error_message": "Amount must be between 0 and 10000",
                "severity": "error"
            }
        ]

        validator = ExportValidator(validation_rules)

        # Test valid data
        valid_data = {"amount": 1000}
        errors = validator.validate_record(valid_data)
        assert len(errors) == 0

        # Test invalid data
        invalid_data = {"amount": 15000}
        errors = validator.validate_record(invalid_data)
        assert len(errors) == 1


class TestExportService:
    """Test the export service."""

    def test_create_export_job(self, db_session, export_template):
        """Test creating an export job."""
        export_service = ExportService(db=db_session)

        export_request = ExportRequest(
            export_config=ExportConfig(
                template_id=str(export_template.id),
                destination=ExportDestination.DOWNLOAD,
                destination_config={"description": "Test export"}
            )
        )

        response = export_service.create_export_job(export_request)

        assert response.export_id is not None
        assert response.status == ExportStatus.PREPARING
        assert response.message == "Export job created successfully"

    def test_csv_export_generation(self, db_session, export_template, sample_invoice_data):
        """Test CSV export generation."""
        export_service = ExportService(db=db_session)

        # Create context for export
        from app.services.export_service import ExportContext
        context = ExportContext(
            job_id=str(uuid.uuid4()),
            template=export_template,
            batch_size=1000
        )

        file_path, file_size = export_service._export_to_csv_enhanced([sample_invoice_data], context)

        assert os.path.exists(file_path)
        assert file_size > 0

        # Check file content
        with open(file_path, 'r') as f:
            content = f.read()
            assert "Vendor Name" in content
            assert "Test Vendor" in content
            assert "Invoice Number" in content

        # Cleanup
        os.unlink(file_path)

    def test_json_export_generation(self, db_session, export_template, sample_invoice_data):
        """Test JSON export generation."""
        # Update template format to JSON
        export_template.format = ExportFormat.JSON
        db_session.commit()

        export_service = ExportService(db=db_session)

        # Create context for export
        from app.services.export_service import ExportContext
        context = ExportContext(
            job_id=str(uuid.uuid4()),
            template=export_template,
            batch_size=1000
        )

        file_path, file_size = export_service._export_to_json_enhanced([sample_invoice_data], context)

        assert os.path.exists(file_path)
        assert file_size > 0

        # Check file content
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert "export_metadata" in data
            assert "invoices" in data
            assert len(data["invoices"]) == 1

        # Cleanup
        os.unlink(file_path)

    def test_get_invoices_for_export(self, db_session, export_template):
        """Test getting invoices for export with filters."""
        # Create test invoice and extraction
        invoice = Invoice(
            vendor_id=uuid.uuid4(),
            file_url="test.pdf",
            file_hash="testhash",
            file_name="test.pdf",
            file_size="1MB",
            status=InvoiceStatus.VALIDATED
        )
        db_session.add(invoice)
        db_session.flush()

        extraction = InvoiceExtraction(
            invoice_id=invoice.id,
            header_json={"vendor_name": "Test Vendor", "invoice_no": "INV-001"},
            lines_json=[{"description": "Test Item", "amount": 100}],
            confidence_json={"overall": 0.95},
            parser_version="1.0"
        )
        db_session.add(extraction)
        db_session.commit()

        export_service = ExportService(db=db_session)

        # Create job with filters
        job = ExportJob(
            name="Test Export",
            template_id=export_template.id,
            format=ExportFormat.CSV,
            destination=ExportDestination.DOWNLOAD,
            destination_config={},
            filters={"status": ["validated"]}
        )
        db_session.add(job)
        db_session.commit()

        invoices = export_service._get_invoices_for_export(job)
        assert len(invoices) == 1
        assert invoices[0]["header"]["vendor_name"] == "Test Vendor"

    def test_export_progress_tracking(self, db_session, export_template):
        """Test export progress tracking."""
        export_service = ExportService(db=db_session)

        # Create a job
        job = ExportJob(
            name="Test Export",
            template_id=export_template.id,
            format=ExportFormat.CSV,
            destination=ExportDestination.DOWNLOAD,
            destination_config={},
            total_records=100,
            processed_records=50,
            status=ExportStatus.PROCESSING
        )
        db_session.add(job)
        db_session.commit()

        progress = export_service.get_export_progress(str(job.id))

        assert progress.export_id == job.id
        assert progress.total_records == 100
        assert progress.processed_records == 50
        assert progress.progress_percentage == 50.0

    def test_cancel_export_job(self, db_session, export_template):
        """Test cancelling an export job."""
        export_service = ExportService(db=db_session)

        # Create a running job
        job = ExportJob(
            name="Test Export",
            template_id=export_template.id,
            format=ExportFormat.CSV,
            destination=ExportDestination.DOWNLOAD,
            destination_config={},
            status=ExportStatus.PROCESSING
        )
        db_session.add(job)
        db_session.commit()

        success = export_service.cancel_export_job(str(job.id))
        assert success is True

        # Check job status
        db_session.refresh(job)
        assert job.status == ExportStatus.CANCELLED

    @patch('app.services.export_service.StorageService')
    def test_file_compression(self, mock_storage, db_session, export_template, sample_invoice_data):
        """Test file compression functionality."""
        # Update template to enable compression
        export_template.compression = True
        db_session.commit()

        export_service = ExportService(db=db_session)

        # Create context for export
        from app.services.export_service import ExportContext
        context = ExportContext(
            job_id=str(uuid.uuid4()),
            template=export_template,
            batch_size=1000
        )

        file_path, file_size = export_service._export_to_csv_enhanced([sample_invoice_data], context)

        # Should be a compressed file
        assert file_path.endswith('.gz')
        assert os.path.exists(file_path)

        # Cleanup
        os.unlink(file_path)


class TestExportAPI:
    """Test the export API endpoints."""

    def test_create_export_template_endpoint(self, db_session):
        """Test creating export template via API."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/exports")

        client = TestClient(app)

        template_data = {
            "name": "API Test Template",
            "description": "Test template via API",
            "format": "csv",
            "field_mappings": [
                {
                    "source_field": "header.vendor_name",
                    "target_field": "Vendor Name",
                    "field_type": "string",
                    "required": True
                }
            ]
        }

        # Mock authentication
        with patch('app.api.api_v1.endpoints.exports.get_current_user') as mock_auth:
            mock_auth.return_value = {"sub": "test-user"}

            response = client.post("/api/v1/exports/templates", json=template_data)
            assert response.status_code == 200

            data = response.json()
            assert data["name"] == "API Test Template"
            assert data["format"] == "csv"

    def test_list_export_templates_endpoint(self, db_session, export_template):
        """Test listing export templates via API."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/exports")

        client = TestClient(app)

        response = client.get("/api/v1/exports/templates")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        assert any(t["name"] == "Test Template" for t in data)

    def test_create_export_job_endpoint(self, db_session, export_template):
        """Test creating export job via API."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/exports")

        client = TestClient(app)

        job_data = {
            "export_config": {
                "template_id": str(export_template.id),
                "destination": "download",
                "destination_config": {"description": "API test export"}
            }
        }

        # Mock authentication
        with patch('app.api.api_v1.endpoints.exports.get_current_user') as mock_auth:
            mock_auth.return_value = {"sub": "test-user"}

            response = client.post("/api/v1/exports/jobs", json=job_data)
            assert response.status_code == 200

            data = response.json()
            assert "export_id" in data
            assert "status" in data


if __name__ == "__main__":
    pytest.main([__file__])