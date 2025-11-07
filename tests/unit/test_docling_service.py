"""
Unit tests for DoclingService document extraction functionality.
"""

import asyncio
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.docling_service import DoclingService
from app.core.exceptions import ExtractionException


class TestDoclingService:
    """Test suite for DoclingService."""

    @pytest.fixture
    def docling_service(self) -> DoclingService:
        """Create DoclingService instance for testing."""
        return DoclingService()

    @pytest.fixture
    def sample_pdf_content(self) -> bytes:
        """Sample PDF content for testing."""
        return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000224 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n314\n%%EOF"

    @pytest.fixture
    def temp_pdf_file(self, sample_pdf_content: bytes) -> Path:
        """Create temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
            temp.write(sample_pdf_content)
            temp_path = Path(temp.name)
        yield temp_path
        temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_from_file_success(self, docling_service: DoclingService, temp_pdf_file: Path):
        """Test successful extraction from file."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            # Mock the DocumentConverter result
            mock_document = MagicMock()
            mock_document.text = "Vendor: Test Vendor\nInvoice: INV-001\nTotal: $100.00"
            mock_document.pages = [MagicMock()]  # One page

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_file(str(temp_pdf_file))

            assert result is not None
            assert "header" in result
            assert "lines" in result
            assert "confidence" in result
            assert "metadata" in result
            assert "overall_confidence" in result

            # Verify metadata
            metadata = result["metadata"]
            assert metadata["file_path"] == str(temp_pdf_file)
            assert metadata["file_size"] > 0
            assert metadata["pages_processed"] == 1
            assert "extracted_at" in metadata

            mock_convert.assert_called_once_with(str(temp_pdf_file))

    @pytest.mark.asyncio
    async def test_extract_from_file_not_found(self, docling_service: DoclingService):
        """Test extraction from non-existent file."""
        with pytest.raises(ExtractionException, match="Failed to extract document"):
            await docling_service.extract_from_file("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_extract_from_content_success(self, docling_service: DoclingService, sample_pdf_content: bytes):
        """Test successful extraction from content bytes."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            # Mock the DocumentConverter result
            mock_document = MagicMock()
            mock_document.text = "Test Vendor\nInvoice: INV-002\nAmount: $200.00"
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(sample_pdf_content)

            assert result is not None
            assert "header" in result
            assert "metadata" in result

            # Verify file hash calculation
            expected_hash = hashlib.sha256(sample_pdf_content).hexdigest()
            assert result["metadata"]["file_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_extract_from_content_with_file_path(self, docling_service: DoclingService, temp_pdf_file: Path):
        """Test extraction from content with file path provided."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = "Vendor: Sample Corp\nInvoice: INV-003"
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            sample_content = temp_pdf_file.read_bytes()
            result = await docling_service.extract_from_content(sample_content, file_path=str(temp_pdf_file))

            assert result is not None
            mock_convert.assert_called_once_with(str(temp_pdf_file))

    @pytest.mark.asyncio
    async def test_extract_from_content_creates_temp_file(self, docling_service: DoclingService, sample_pdf_content: bytes):
        """Test that extraction creates temporary file when no path provided."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = "Test content"
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(sample_pdf_content)

            assert result is not None
            # Verify convert was called with a temporary file path
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args[0]
            assert call_args[0].endswith('.pdf')
            assert Path(call_args[0]).exists() is False  # Temp file should be cleaned up

    @pytest.mark.asyncio
    async def test_extract_header_vendor_name(self, docling_service: DoclingService):
        """Test vendor name extraction with various patterns."""
        test_cases = [
            ("Vendor: Test Vendor Inc", "Test Vendor Inc"),
            ("Supplier: ABC Corporation", "ABC Corporation"),
            ("Bill to: XYZ Company LLC", "XYZ Company LLC"),
            ("From: Global Supplies Inc", "Global Supplies Inc"),
            ("TestVendor Inc Invoice", "TestVendor Inc"),
        ]

        for text, expected_vendor in test_cases:
            with patch.object(docling_service.converter, 'convert') as mock_convert:
                mock_document = MagicMock()
                mock_document.text = text
                mock_document.pages = [MagicMock()]

                mock_result = MagicMock()
                mock_result.document = mock_document
                mock_result.status = "success"
                mock_convert.return_value = mock_result

                result = await docling_service.extract_from_content(b"fake content")
                header = result["header"]
                assert header.get("vendor_name") == expected_vendor, f"Failed for text: {text}"

    @pytest.mark.asyncio
    async def test_extract_header_invoice_number(self, docling_service: DoclingService):
        """Test invoice number extraction with various patterns."""
        test_cases = [
            ("Invoice No: INV-2024-001", "INV-2024-001"),
            ("Invoice #12345", "12345"),
            ("Bill Number: B-987", "B-987"),
            ("Invoice INV/2024/001", "INV/2024/001"),
        ]

        for text, expected_invoice in test_cases:
            with patch.object(docling_service.converter, 'convert') as mock_convert:
                mock_document = MagicMock()
                mock_document.text = text
                mock_document.pages = [MagicMock()]

                mock_result = MagicMock()
                mock_result.document = mock_document
                mock_result.status = "success"
                mock_convert.return_value = mock_result

                result = await docling_service.extract_from_content(b"fake content")
                header = result["header"]
                assert header.get("invoice_no") == expected_invoice, f"Failed for text: {text}"

    @pytest.mark.asyncio
    async def test_extract_header_amounts(self, docling_service: DoclingService):
        """Test monetary amount extraction."""
        text_content = """
        Subtotal: $1,000.00
        Tax: $100.00
        Total: $1,100.00
        """

        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = text_content
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(b"fake content")
            header = result["header"]

            assert header.get("subtotal") == 1000.00
            assert header.get("tax") == 100.00
            assert header.get("total") == 1100.00

    @pytest.mark.asyncio
    async def test_extract_header_dates(self, docling_service: DoclingService):
        """Test date extraction and normalization."""
        test_cases = [
            ("Invoice Date: 01/15/2024", "2024-01-15"),
            ("Date: 2024-01-20", "2024-01-20"),
            ("Bill Date: 15-01-2024", "2024-01-15"),
            ("Due Date: 02/15/2024", "2024-02-15"),
        ]

        for text, expected_date in test_cases:
            with patch.object(docling_service.converter, 'convert') as mock_convert:
                mock_document = MagicMock()
                mock_document.text = text
                mock_document.pages = [MagicMock()]

                mock_result = MagicMock()
                mock_result.document = mock_document
                mock_result.status = "success"
                mock_convert.return_value = mock_result

                result = await docling_service.extract_from_content(b"fake content")
                header = result["header"]
                assert header.get("invoice_date") == expected_date, f"Failed for text: {text}"

    @pytest.mark.asyncio
    async def test_extract_currency(self, docling_service: DoclingService):
        """Test currency extraction from symbols and codes."""
        test_cases = [
            ("Total: $100.00", "USD"),
            ("Total: €100.00", "EUR"),
            ("Total: £100.00", "GBP"),
            ("Total: ¥100.00", "JPY"),
            ("Currency: USD", "USD"),
            ("Currency: EUR", "EUR"),
        ]

        for text, expected_currency in test_cases:
            with patch.object(docling_service.converter, 'convert') as mock_convert:
                mock_document = MagicMock()
                mock_document.text = text
                mock_document.pages = [MagicMock()]

                mock_result = MagicMock()
                mock_result.document = mock_document
                mock_result.status = "success"
                mock_convert.return_value = mock_result

                result = await docling_service.extract_from_content(b"fake content")
                header = result["header"]
                assert header.get("currency") == expected_currency, f"Failed for text: {text}"

    @pytest.mark.asyncio
    async def test_extract_lines_table_format(self, docling_service: DoclingService):
        """Test line item extraction from table format."""
        text_content = """
        Description        Amount
        Test Product 1    $100.00
        Test Product 2    $200.00
        Service Fee       $50.00
        """

        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = text_content
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(b"fake content")
            lines = result["lines"]

            assert len(lines) >= 2  # Should extract at least 2 line items
            assert all("description" in line for line in lines)
            assert all("amount" in line for line in lines)

    @pytest.mark.asyncio
    async def test_extract_lines_text_format(self, docling_service: DoclingService):
        """Test line item extraction from text format."""
        text_content = """
        Item 1: Test Product - $100.00
        Item 2: Another Product - $250.50
        """

        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = text_content
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(b"fake content")
            lines = result["lines"]

            assert len(lines) >= 1  # Should extract at least 1 line item

    @pytest.mark.asyncio
    async def test_parse_line_item_with_quantity(self, docling_service: DoclingService):
        """Test parsing line item with quantity and unit price."""
        item_text = "Test Product 2 x $50.00 = $100.00"

        result = docling_service._parse_line_item(item_text)

        assert result is not None
        assert result["description"] == "Test Product"
        assert result["quantity"] == 2.0
        assert result["unit_price"] == 50.0
        assert result["amount"] == 100.00

    @pytest.mark.asyncio
    async def test_parse_line_item_without_quantity(self, docling_service: DoclingService):
        """Test parsing line item without explicit quantity."""
        item_text = "Simple Service $150.00"

        result = docling_service._parse_line_item(item_text)

        assert result is not None
        assert result["description"] == "Simple Service"
        assert result["quantity"] == 1.0
        assert result["unit_price"] == 150.00
        assert result["amount"] == 150.00

    @pytest.mark.asyncio
    async def test_calculate_confidence(self, docling_service: DoclingService):
        """Test confidence score calculation."""
        # Create mock document and extraction data
        header = {
            "vendor_name": "Test Vendor",
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "total": 1000.00
        }
        lines = [
            {"description": "Test Product", "amount": 1000.00}
        ]

        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = "Test content"
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            result = await docling_service.extract_from_content(b"fake content")

            assert "confidence" in result
            assert "overall_confidence" in result
            assert 0 <= result["overall_confidence"] <= 1

    @pytest.mark.asyncio
    async def test_clean_header_data(self, docling_service: DoclingService):
        """Test header data cleaning and normalization."""
        dirty_header = {
            "vendor_name": "  Test Vendor Inc  ",
            "invoice_no": "INV-001",
            "invoice_date": "01/15/2024",
            "total": "1000.00",
            "subtotal": "900.00",
            "tax": "100.00",
            "currency": "USD",
            "empty_field": "",
            "none_field": None,
        }

        cleaned = docling_service._clean_header_data(dirty_header)

        assert cleaned["vendor_name"] == "Test Vendor Inc"
        assert cleaned["invoice_no"] == "INV-001"
        assert cleaned["invoice_date"] == "2024-01-15"
        assert cleaned["total"] == 1000.00
        assert cleaned["subtotal"] == 900.00
        assert cleaned["tax"] == 100.00
        assert cleaned["currency"] == "USD"
        assert "empty_field" not in cleaned
        assert "none_field" not in cleaned

    @pytest.mark.asyncio
    async def test_normalize_date_various_formats(self, docling_service: DoclingService):
        """Test date normalization for various formats."""
        test_cases = [
            ("01/15/2024", "2024-01-15"),
            ("2024-01-15", "2024-01-15"),
            ("15-01-2024", "2024-01-15"),
            ("01/15/24", "2024-01-15"),
            ("2024/01/15", "2024-01-15"),
        ]

        for input_date, expected_output in test_cases:
            result = docling_service._normalize_date(input_date)
            assert result == expected_output, f"Failed for {input_date}"

    @pytest.mark.asyncio
    async def test_normalize_date_invalid(self, docling_service: DoclingService):
        """Test date normalization with invalid dates."""
        invalid_dates = [
            "32/13/2024",  # Invalid day/month
            "invalid-date",
            "",
            None,
        ]

        for invalid_date in invalid_dates:
            result = docling_service._normalize_date(invalid_date)
            # Should return original value or None for invalid dates
            assert result is None or result == invalid_date

    @pytest.mark.asyncio
    async def test_max_pages_limit(self, docling_service: DoclingService):
        """Test page limit enforcement."""
        # Create mock document with many pages
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = "Test content"
            mock_document.pages = [MagicMock() for _ in range(100)]  # 100 pages

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            # Temporarily set a low page limit for testing
            original_limit = docling_service.max_pages
            docling_service.max_pages = 5

            try:
                with patch('logging.Logger.warning') as mock_warning:
                    result = await docling_service.extract_from_content(b"fake content")
                    mock_warning.assert_called_once()
                    assert "exceeding limit" in mock_warning.call_args[0][0]
            finally:
                docling_service.max_pages = original_limit

    @pytest.mark.asyncio
    async def test_extraction_error_handling(self, docling_service: DoclingService):
        """Test error handling during extraction."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_convert.side_effect = Exception("Conversion failed")

            with pytest.raises(ExtractionException, match="Document extraction failed"):
                await docling_service.extract_from_content(b"fake content")

    @pytest.mark.asyncio
    async def test_header_extraction_error_handling(self, docling_service: DoclingService):
        """Test error handling in header extraction."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = "Test content"
            mock_document.pages = [MagicMock()]
            # Simulate an error during header processing
            mock_document.text = None  # This will cause an error

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            # Should not raise exception, but return empty header
            result = await docling_service.extract_from_content(b"fake content")
            assert result["header"] == {}

    @pytest.mark.asyncio
    async def test_lines_extraction_error_handling(self, docling_service: DoclingService):
        """Test error handling in line extraction."""
        with patch.object(docling_service.converter, 'convert') as mock_convert:
            mock_document = MagicMock()
            mock_document.text = None  # This will cause an error in lines extraction
            mock_document.pages = [MagicMock()]

            mock_result = MagicMock()
            mock_result.document = mock_document
            mock_result.status = "success"
            mock_convert.return_value = mock_result

            # Should not raise exception, but return empty lines
            result = await docling_service.extract_from_content(b"fake content")
            assert result["lines"] == []

    def test_extract_with_patterns(self, docling_service: DoclingService):
        """Test pattern-based text extraction."""
        text = "Invoice Number: INV-2024-001"
        patterns = [
            r"Invoice Number:\s*([A-Za-z0-9\-\/]+)",
            r"Invoice:\s*([A-Za-z0-9\-\/]+)",
        ]

        result = docling_service._extract_with_patterns(text, patterns)
        assert result == "INV-2024-001"

    def test_extract_with_patterns_no_match(self, docling_service: DoclingService):
        """Test pattern extraction with no matches."""
        text = "No invoice number here"
        patterns = [
            r"Invoice Number:\s*([A-Za-z0-9\-\/]+)",
        ]

        result = docling_service._extract_with_patterns(text, patterns)
        assert result is None

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization with default settings."""
        service = DoclingService()

        assert service.confidence_threshold is not None
        assert service.max_pages is not None
        assert service.converter is not None
        assert service.pipeline_options is not None

    @pytest.mark.asyncio
    async def test_extract_with_patterns_whitespace_handling(self, docling_service: DoclingService):
        """Test pattern extraction with whitespace handling."""
        text = "   Vendor:    Test Vendor Inc   "
        patterns = [
            r"Vendor:\s*([^\n\r]+?)(?:\n|$)",
        ]

        result = docling_service._extract_with_patterns(text, patterns)
        assert result == "Test Vendor Inc"