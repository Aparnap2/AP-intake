"""
Enhanced unit tests for ValidationService with comprehensive coverage.
"""

import pytest
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.validation_service import ValidationService
from app.core.exceptions import ValidationException
from tests.factories import ExtractionDataFactory, LowConfidenceExtractionFactory, CorruptedExtractionFactory


class TestValidationServiceBasicValidation:
    """Test suite for basic validation functionality."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.fixture
    def valid_extraction_data(self):
        """Valid extraction data for positive testing."""
        return ExtractionDataFactory()

    @pytest.mark.asyncio
    async def test_validate_invoice_success(self, validation_service: ValidationService, valid_extraction_data):
        """Test successful invoice validation."""
        result = await validation_service.validate_invoice(valid_extraction_data)

        assert result is not None
        assert "passed" in result
        assert "confidence_score" in result
        assert "total_issues" in result
        assert "error_count" in result
        assert "warning_count" in result
        assert "issues" in result
        assert "check_results" in result

        # For valid data, validation should pass
        assert result["passed"] is True
        assert result["confidence_score"] >= 0.8
        assert result["total_issues"] == 0
        assert result["error_count"] == 0
        assert result["check_results"]["structure_check"] is True
        assert result["check_results"]["header_fields_check"] is True
        assert result["check_results"]["line_items_check"] is True
        assert result["check_results"]["math_check"] is True
        assert result["check_results"]["business_rules_check"] is True

    @pytest.mark.asyncio
    async def test_validate_invoice_low_confidence(self, validation_service: ValidationService):
        """Test validation with low confidence data."""
        low_conf_data = LowConfidenceExtractionFactory()
        result = await validation_service.validate_invoice(low_conf_data)

        assert result["passed"] is False
        assert result["confidence_score"] < 0.7
        assert result["total_issues"] > 0
        assert result["error_count"] > 0

        # Check that confidence issue is detected
        confidence_issues = [issue for issue in result["issues"] if "confidence" in issue["error"].lower()]
        assert len(confidence_issues) > 0

    @pytest.mark.asyncio
    async def test_validate_invoice_corrupted_data(self, validation_service: ValidationService):
        """Test validation with corrupted/incomplete data."""
        corrupted_data = CorruptedExtractionFactory()
        result = await validation_service.validate_invoice(corrupted_data)

        assert result["passed"] is False
        assert result["total_issues"] > 0
        assert result["error_count"] > 0

        # Check that structure validation fails
        assert result["check_results"]["structure_check"] is False
        assert result["check_results"]["header_fields_check"] is False

    @pytest.mark.asyncio
    async def test_validate_invoice_empty_data(self, validation_service: ValidationService):
        """Test validation with empty extraction data."""
        empty_data = {}
        result = await validation_service.validate_invoice(empty_data)

        assert result["passed"] is False
        assert result["total_issues"] > 0
        assert result["error_count"] > 0
        assert result["check_results"]["structure_check"] is False


class TestValidationServiceStructureCheck:
    """Test suite for structure validation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_structure_check_valid_data(self, validation_service: ValidationService):
        """Test structure check with valid data."""
        valid_data = ExtractionDataFactory()
        result = validation_service._check_structure(valid_data)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_structure_check_missing_header(self, validation_service: ValidationService):
        """Test structure check with missing header."""
        invalid_data = {
            "lines": [{"description": "Test", "amount": 100.0}]
        }
        result = validation_service._check_structure(invalid_data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("header" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_structure_check_missing_lines(self, validation_service: ValidationService):
        """Test structure check with missing lines."""
        invalid_data = {
            "header": {"vendor_name": "Test Vendor", "total": 100.0}
        }
        result = validation_service._check_structure(invalid_data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("lines" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_structure_check_empty_lines(self, validation_service: ValidationService):
        """Test structure check with empty lines array."""
        invalid_data = {
            "header": {"vendor_name": "Test Vendor", "total": 100.0},
            "lines": []
        }
        result = validation_service._check_structure(invalid_data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("no line items" in issue["error"].lower() for issue in result["issues"])


class TestValidationServiceHeaderFieldsCheck:
    """Test suite for header field validation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_header_fields_check_valid(self, validation_service: ValidationService):
        """Test header fields check with valid data."""
        valid_header = ExtractionDataFactory()["header"]
        result = validation_service._check_header_fields(valid_header)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_header_fields_check_missing_vendor(self, validation_service: ValidationService):
        """Test header fields check with missing vendor name."""
        invalid_header = {
            "invoice_no": "INV-001",
            "total": 100.0,
            "currency": "USD"
        }
        result = validation_service._check_header_fields(invalid_header)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("vendor name" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_header_fields_check_invalid_total(self, validation_service: ValidationService):
        """Test header fields check with invalid total amount."""
        invalid_headers = [
            {"vendor_name": "Test Vendor", "total": -100.0},  # Negative amount
            {"vendor_name": "Test Vendor", "total": 0.0},     # Zero amount
            {"vendor_name": "Test Vendor", "total": "invalid"}, # Invalid type
        ]

        for header in invalid_headers:
            result = validation_service._check_header_fields(header)
            assert result["passed"] is False
            assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_header_fields_check_invalid_date(self, validation_service: ValidationService):
        """Test header fields check with invalid date."""
        invalid_dates = [
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day
            "invalid-date",
            "01/01/2024",  # Wrong format
        ]

        for date_str in invalid_dates:
            header = {
                "vendor_name": "Test Vendor",
                "invoice_no": "INV-001",
                "invoice_date": date_str,
                "total": 100.0
            }
            result = validation_service._check_header_fields(header)
            assert result["passed"] is False
            assert any("date" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_header_fields_check_invalid_currency(self, validation_service: ValidationService):
        """Test header fields check with invalid currency."""
        invalid_header = {
            "vendor_name": "Test Vendor",
            "total": 100.0,
            "currency": "INVALID"
        }
        result = validation_service._check_header_fields(invalid_header)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("currency" in issue["error"].lower() for issue in result["issues"])


class TestValidationServiceLineItemsCheck:
    """Test suite for line items validation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_line_items_check_valid(self, validation_service: ValidationService):
        """Test line items check with valid data."""
        valid_lines = ExtractionDataFactory()["lines"]
        result = validation_service._check_line_items(valid_lines)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_line_items_check_missing_description(self, validation_service: ValidationService):
        """Test line items check with missing description."""
        invalid_lines = [
            {"amount": 100.0, "quantity": 1},  # Missing description
        ]
        result = validation_service._check_line_items(invalid_lines)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("description" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_line_items_check_invalid_amounts(self, validation_service: ValidationService):
        """Test line items check with invalid amounts."""
        invalid_lines = [
            {"description": "Test", "amount": -50.0},    # Negative amount
            {"description": "Test", "amount": 0.0},      # Zero amount
            {"description": "Test", "amount": "invalid"}, # Invalid type
        ]

        for line in invalid_lines:
            result = validation_service._check_line_items([line])
            assert result["passed"] is False
            assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_line_items_check_invalid_quantities(self, validation_service: ValidationService):
        """Test line items check with invalid quantities."""
        invalid_lines = [
            {"description": "Test", "amount": 100.0, "quantity": -1},    # Negative quantity
            {"description": "Test", "amount": 100.0, "quantity": 0},      # Zero quantity
            {"description": "Test", "amount": 100.0, "quantity": "invalid"}, # Invalid type
        ]

        for line in invalid_lines:
            result = validation_service._check_line_items([line])
            assert result["passed"] is False
            assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_line_items_check_calculation_errors(self, validation_service: ValidationService):
        """Test line items check with calculation errors."""
        # Line where quantity * unit_price != amount
        invalid_line = {
            "description": "Test",
            "quantity": 2,
            "unit_price": 50.0,
            "amount": 200.0  # Should be 100.0
        }
        result = validation_service._check_line_items([invalid_line])

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("calculation" in issue["error"].lower() for issue in result["issues"])


class TestValidationServiceMathCheck:
    """Test suite for mathematical validation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_math_check_valid_calculation(self, validation_service: ValidationService):
        """Test math check with correct calculations."""
        # Create data with correct math: subtotal + tax = total
        lines = [
            {"description": "Item 1", "quantity": 1, "unit_price": 100.0, "amount": 100.0},
            {"description": "Item 2", "quantity": 2, "unit_price": 50.0, "amount": 100.0}
        ]
        header = {
            "vendor_name": "Test Vendor",
            "subtotal": 200.0,
            "tax": 20.0,
            "total": 220.0
        }
        data = {"header": header, "lines": lines}

        result = validation_service._check_math(data)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_math_check_incorrect_total(self, validation_service: ValidationService):
        """Test math check with incorrect total calculation."""
        lines = [
            {"description": "Item 1", "amount": 100.0}
        ]
        header = {
            "vendor_name": "Test Vendor",
            "subtotal": 100.0,
            "tax": 10.0,
            "total": 150.0  # Should be 110.0
        }
        data = {"header": header, "lines": lines}

        result = validation_service._check_math(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("total" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_math_check_incorrect_subtotal(self, validation_service: ValidationService):
        """Test math check with incorrect subtotal calculation."""
        lines = [
            {"description": "Item 1", "amount": 100.0},
            {"description": "Item 2", "amount": 50.0}
        ]
        header = {
            "vendor_name": "Test Vendor",
            "subtotal": 200.0,  # Should be 150.0
            "tax": 20.0,
            "total": 220.0
        }
        data = {"header": header, "lines": lines}

        result = validation_service._check_math(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("subtotal" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_math_check_rounding_tolerance(self, validation_service: ValidationService):
        """Test math check with rounding tolerance."""
        lines = [
            {"description": "Item 1", "amount": 33.33},
            {"description": "Item 2", "amount": 33.33},
            {"description": "Item 3", "amount": 33.34}
        ]
        header = {
            "vendor_name": "Test Vendor",
            "subtotal": 100.0,
            "tax": 8.25,
            "total": 108.25
        }
        data = {"header": header, "lines": lines}

        result = validation_service._check_math(data)

        # Should pass due to rounding tolerance
        assert result["passed"] is True
        assert len(result["issues"]) == 0


class TestValidationServiceBusinessRules:
    """Test suite for business rules validation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_business_rules_normal_invoice(self, validation_service: ValidationService):
        """Test business rules with normal invoice values."""
        data = ExtractionDataFactory()
        result = validation_service._check_business_rules(data)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_business_rules_extremely_high_amount(self, validation_service: ValidationService):
        """Test business rules with extremely high invoice amount."""
        data = ExtractionDataFactory()
        data["header"]["total"] = 10000000.0  # $10M

        result = validation_service._check_business_rules(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("high amount" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_business_rules_future_date(self, validation_service: ValidationService):
        """Test business rules with future invoice date."""
        future_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        data = ExtractionDataFactory()
        data["header"]["invoice_date"] = future_date

        result = validation_service._check_business_rules(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("future date" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_business_rules_very_old_date(self, validation_service: ValidationService):
        """Test business rules with very old invoice date."""
        old_date = (datetime.utcnow() - timedelta(days=400)).strftime("%Y-%m-%d")
        data = ExtractionDataFactory()
        data["header"]["invoice_date"] = old_date

        result = validation_service._check_business_rules(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("old invoice" in issue["error"].lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_business_rules_too_many_line_items(self, validation_service: ValidationService):
        """Test business rules with too many line items."""
        data = ExtractionDataFactory()
        # Create 200 line items (assuming limit is 100)
        data["lines"] = [
            {"description": f"Item {i}", "amount": 10.0}
            for i in range(200)
        ]

        result = validation_service._check_business_rules(data)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert any("line items" in issue["error"].lower() for issue in result["issues"])


class TestValidationServiceConfidenceScoring:
    """Test suite for confidence score calculation."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_calculate_overall_confidence_high(self, validation_service: ValidationService):
        """Test confidence score calculation with high values."""
        confidence_data = {
            "header": {
                "vendor_name": 0.95,
                "invoice_no": 0.98,
                "invoice_date": 0.92,
                "total": 0.97,
                "overall": 0.95
            },
            "lines": [0.90, 0.92, 0.88],
            "overall": 0.93
        }

        score = validation_service._calculate_overall_confidence(confidence_data)

        assert score >= 0.9
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_overall_confidence_low(self, validation_service: ValidationService):
        """Test confidence score calculation with low values."""
        confidence_data = {
            "header": {
                "vendor_name": 0.3,
                "invoice_no": 0.4,
                "invoice_date": 0.2,
                "total": 0.5,
                "overall": 0.35
            },
            "lines": [0.3, 0.4],
            "overall": 0.35
        }

        score = validation_service._calculate_overall_confidence(confidence_data)

        assert score < 0.5
        assert score >= 0.0

    @pytest.mark.asyncio
    async def test_calculate_overall_confidence_mixed(self, validation_service: ValidationService):
        """Test confidence score calculation with mixed values."""
        confidence_data = {
            "header": {
                "vendor_name": 0.95,
                "invoice_no": 0.98,
                "invoice_date": 0.3,  # Low confidence here
                "total": 0.97,
                "overall": 0.8
            },
            "lines": [0.9, 0.4, 0.8],  # Mixed line confidence
            "overall": 0.7
        }

        score = validation_service._calculate_overall_confidence(confidence_data)

        # Should be moderate due to mixed confidence
        assert 0.5 <= score <= 0.85


class TestValidationServiceErrorHandling:
    """Test suite for error handling and edge cases."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_validate_invoice_none_input(self, validation_service: ValidationService):
        """Test validation with None input."""
        with pytest.raises(ValidationException):
            await validation_service.validate_invoice(None)

    @pytest.mark.asyncio
    async def test_validate_invoice_invalid_types(self, validation_service: ValidationService):
        """Test validation with invalid input types."""
        invalid_inputs = [
            "string_input",
            123,
            [],
            True
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationException):
                await validation_service.validate_invoice(invalid_input)

    @pytest.mark.asyncio
    async def test_validate_invoice_malformed_data(self, validation_service: ValidationService):
        """Test validation with malformed data structures."""
        malformed_data = {
            "header": "not_a_dict",  # Should be dict
            "lines": "not_a_list"    # Should be list
        }

        result = await validation_service.validate_invoice(malformed_data)

        assert result["passed"] is False
        assert result["error_count"] > 0

    @pytest.mark.asyncio
    async def test_decimal_conversion_errors(self, validation_service: ValidationService):
        """Test handling of decimal conversion errors."""
        data_with_invalid_decimal = {
            "header": {
                "vendor_name": "Test Vendor",
                "total": "invalid_decimal"
            },
            "lines": [
                {"description": "Test", "amount": "also_invalid"}
            ]
        }

        result = await validation_service.validate_invoice(data_with_invalid_decimal)

        assert result["passed"] is False
        assert result["error_count"] > 0

    @pytest.mark.asyncio
    async def test_date_parsing_errors(self, validation_service: ValidationService):
        """Test handling of date parsing errors."""
        data_with_invalid_dates = {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_date": "not_a_date",
                "due_date": "also_not_a_date",
                "total": 100.0
            },
            "lines": [{"description": "Test", "amount": 100.0}]
        }

        result = await validation_service.validate_invoice(data_with_invalid_dates)

        assert result["passed"] is False
        assert result["error_count"] >= 2  # Should catch both date errors


class TestValidationServiceThresholds:
    """Test suite for validation threshold configurations."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.mark.asyncio
    async def test_confidence_threshold_boundary(self, validation_service: ValidationService):
        """Test behavior at confidence threshold boundary."""
        # Test exactly at threshold
        threshold_data = ExtractionDataFactory()
        threshold_data["overall_confidence"] = validation_service.confidence_threshold

        result = await validation_service.validate_invoice(threshold_data)

        # Should pass at exactly threshold
        assert result["passed"] is True

        # Test just below threshold
        threshold_data["overall_confidence"] = validation_service.confidence_threshold - 0.01

        result = await validation_service.validate_invoice(threshold_data)

        # Should fail below threshold
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_custom_confidence_threshold(self, validation_service: ValidationService):
        """Test validation with custom confidence threshold."""
        # Temporarily adjust threshold
        original_threshold = validation_service.confidence_threshold
        validation_service.confidence_threshold = 0.95

        try:
            # Test with high confidence that meets new threshold
            high_conf_data = ExtractionDataFactory()
            high_conf_data["overall_confidence"] = 0.96

            result = await validation_service.validate_invoice(high_conf_data)
            assert result["passed"] is True

            # Test with confidence that would pass original but fail new threshold
            medium_conf_data = ExtractionDataFactory()
            medium_conf_data["overall_confidence"] = 0.90

            result = await validation_service.validate_invoice(medium_conf_data)
            assert result["passed"] is False

        finally:
            # Restore original threshold
            validation_service.confidence_threshold = original_threshold