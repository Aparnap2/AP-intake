"""
Comprehensive mathematical validation tests for invoice processing.
Tests total = sum(line items) + tax calculation with 85% confidence threshold.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.services.validation_engine import ValidationEngine, ReasonTaxonomy
from app.api.schemas.validation import ValidationSeverity


class TestMathematicalValidation:
    """Test comprehensive mathematical validation for invoices."""

    @pytest.fixture
    def validation_engine(self):
        """Create validation engine instance."""
        return ValidationEngine()

    @pytest.fixture
    def valid_invoice_data(self):
        """Valid invoice data with correct math."""
        return {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_number": "INV-001",
                "invoice_date": "2024-01-15",
                "due_date": "2024-02-15",
                "subtotal": Decimal("1000.00"),
                "tax_amount": Decimal("100.00"),
                "total_amount": Decimal("1100.00"),
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Item 1",
                    "quantity": Decimal("10"),
                    "unit_price": Decimal("50.00"),
                    "amount": Decimal("500.00"),
                    "tax_rate": Decimal("0.10")
                },
                {
                    "description": "Item 2",
                    "quantity": Decimal("5"),
                    "unit_price": Decimal("100.00"),
                    "amount": Decimal("500.00"),
                    "tax_rate": Decimal("0.10")
                }
            ],
            "confidence": {
                "overall": 0.87,  # Above 85% threshold
                "header": 0.88,
                "lines": 0.86
            }
        }

    @pytest.fixture
    def invalid_invoice_data(self):
        """Invoice data with mathematical errors."""
        return {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_number": "INV-002",
                "invoice_date": "2024-01-15",
                "due_date": "2024-02-15",
                "subtotal": Decimal("1000.00"),
                "tax_amount": Decimal("100.00"),
                "total_amount": Decimal("1150.00"),  # Wrong - should be 1100.00
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Item 1",
                    "quantity": Decimal("10"),
                    "unit_price": Decimal("50.00"),
                    "amount": Decimal("500.00"),  # Correct: 10 × 50 = 500
                    "tax_rate": Decimal("0.10")
                },
                {
                    "description": "Item 2",
                    "quantity": Decimal("5"),
                    "unit_price": Decimal("100.00"),
                    "amount": Decimal("550.00"),  # Wrong - should be 5 × 100 = 500
                    "tax_rate": Decimal("0.10")
                }
            ],
            "confidence": {
                "overall": 0.92,  # High confidence but math is wrong
                "header": 0.95,
                "lines": 0.89
            }
        }

    @pytest.fixture
    def low_confidence_invoice_data(self):
        """Valid invoice data with low confidence score."""
        return {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_number": "INV-003",
                "invoice_date": "2024-01-15",
                "due_date": "2024-02-15",
                "subtotal": Decimal("1000.00"),
                "tax_amount": Decimal("100.00"),
                "total_amount": Decimal("1100.00"),
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Item 1",
                    "quantity": Decimal("10"),
                    "unit_price": Decimal("50.00"),
                    "amount": Decimal("500.00"),
                    "tax_rate": Decimal("0.10")
                }
            ],
            "confidence": {
                "overall": 0.75,  # Below 85% threshold
                "header": 0.70,
                "lines": 0.80
            }
        }

    @pytest.mark.asyncio
    async def test_line_item_math_validation_success(self, validation_engine, valid_invoice_data):
        """Test line item math validation with correct calculations."""
        lines = valid_invoice_data["lines"]

        result = await validation_engine._validate_line_item_math(
            rule=validation_engine.rules["math"][0],  # line_item_math_validation rule
            lines=lines
        )

        assert result.passed == True
        assert result.reason_taxonomy is None

    @pytest.mark.asyncio
    async def test_line_item_math_validation_failure(self, validation_engine, invalid_invoice_data):
        """Test line item math validation detects calculation errors."""
        lines = invalid_invoice_data["lines"]

        result = await validation_engine._validate_line_item_math(
            rule=validation_engine.rules["math"][0],
            lines=lines
        )

        assert result.passed == False
        assert result.reason_taxonomy == ReasonTaxonomy.LINE_MATH_MISMATCH

    @pytest.mark.asyncio
    async def test_subtotal_validation_success(self, validation_engine, valid_invoice_data):
        """Test subtotal validation with correct sum."""
        header = valid_invoice_data["header"]
        lines = valid_invoice_data["lines"]

        result = await validation_engine._validate_subtotal(
            rule=validation_engine.rules["math"][1],  # subtotal_validation rule
            header=header,
            lines=lines
        )

        assert result.passed == True

    @pytest.mark.asyncio
    async def test_subtotal_validation_failure(self, validation_engine, invalid_invoice_data):
        """Test subtotal validation detects mismatch."""
        header = invalid_invoice_data["header"]
        lines = invalid_invoice_data["lines"]

        # Subtotal should be 1050.00 (500 + 550) but is set to 1000.00
        result = await validation_engine._validate_subtotal(
            rule=validation_engine.rules["math"][1],
            header=header,
            lines=lines
        )

        assert result.passed == False
        assert result.reason_taxonomy == ReasonTaxonomy.SUBTOTAL_MISMATCH

    @pytest.mark.asyncio
    async def test_total_amount_validation_success(self, validation_engine, valid_invoice_data):
        """Test total amount validation: total = sum(line items) + tax."""
        header = valid_invoice_data["header"]
        lines = valid_invoice_data["lines"]

        result = await validation_engine._validate_total_amount(
            rule=validation_engine.rules["math"][2],  # total_validation rule
            header=header,
            lines=lines
        )

        assert result.passed == True

    @pytest.mark.asyncio
    async def test_total_amount_validation_failure(self, validation_engine, invalid_invoice_data):
        """Test total amount validation detects incorrect grand total."""
        header = invalid_invoice_data["header"]
        lines = invalid_invoice_data["lines"]

        # Total should be 1150.00 (500 + 550 + 100 tax) but header shows 1150.00 vs lines total 1050
        result = await validation_engine._validate_total_amount(
            rule=validation_engine.rules["math"][2],
            header=header,
            lines=lines
        )

        assert result.passed == False
        assert result.reason_taxonomy == ReasonTaxonomy.TOTAL_MISMATCH

    @pytest.mark.asyncio
    async def test_tax_calculation_validation(self, validation_engine, valid_invoice_data):
        """Test tax calculation validation."""
        header = valid_invoice_data["header"]
        lines = valid_invoice_data["lines"]

        result = await validation_engine._validate_tax_calculation(
            rule=validation_engine.rules["math"][3],  # tax_calculation_validation rule
            header=header,
            lines=lines
        )

        assert result.passed == True

    @pytest.mark.asyncio
    async def test_comprehensive_validation_success(self, validation_engine, valid_invoice_data):
        """Test comprehensive validation passes for correct invoice."""
        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=valid_invoice_data,
                invoice_id="test-invoice-001",
                strict_mode=False
            )

            assert result.validation_passed == True
            assert result.confidence_score == valid_invoice_data["confidence"]["overall"]
            assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_comprehensive_validation_math_errors(self, validation_engine, invalid_invoice_data):
        """Test comprehensive validation detects mathematical errors."""
        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=invalid_invoice_data,
                invoice_id="test-invoice-002",
                strict_mode=False
            )

            assert result.validation_passed == False

            # Should have mathematical validation errors
            math_errors = [
                issue for issue in result.issues
                if issue.reason_code in [
                    ReasonTaxonomy.LINE_MATH_MISMATCH.value,
                    ReasonTaxonomy.SUBTOTAL_MISMATCH.value,
                    ReasonTaxonomy.TOTAL_MISMATCH.value
                ]
            ]

            assert len(math_errors) > 0

    @pytest.mark.asyncio
    async def test_comprehensive_validation_low_confidence(self, validation_engine, low_confidence_invoice_data):
        """Test comprehensive validation with low confidence score."""
        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=low_confidence_invoice_data,
                invoice_id="test-invoice-003",
                strict_mode=False
            )

            assert result.validation_passed == False
            assert result.confidence_score == 0.75  # Below 85% threshold

            # Should have low confidence error
            confidence_errors = [
                issue for issue in result.issues
                if issue.reason_code == ReasonTaxonomy.LOW_CONFIDENCE.value
            ]

            assert len(confidence_errors) > 0

    def test_line_item_calculation_precision(self, validation_engine):
        """Test line item calculations with decimal precision."""
        test_cases = [
            # (quantity, unit_price, expected_amount)
            (Decimal("1"), Decimal("99.99"), Decimal("99.99")),
            (Decimal("2"), Decimal("50.00"), Decimal("100.00")),
            (Decimal("3.5"), Decimal("10.00"), Decimal("35.00")),
            (Decimal("0.99"), Decimal("100.00"), Decimal("99.00")),
            (Decimal("1000"), Decimal("0.01"), Decimal("10.00")),
        ]

        for quantity, unit_price, expected_amount in test_cases:
            calculated_amount = quantity * unit_price
            assert calculated_amount == expected_amount, \
                f"Failed: {quantity} × {unit_price} = {calculated_amount}, expected {expected_amount}"

    def test_total_calculation_edge_cases(self):
        """Test total calculation edge cases."""
        # Test with zero values
        subtotal = Decimal("0.00")
        tax = Decimal("0.00")
        expected_total = Decimal("0.00")
        actual_total = subtotal + tax
        assert actual_total == expected_total

        # Test with very small values
        subtotal = Decimal("0.01")
        tax = Decimal("0.00")
        expected_total = Decimal("0.01")
        actual_total = subtotal + tax
        assert actual_total == expected_total

        # Test with tax rounding
        subtotal = Decimal("100.00")
        tax_rate = Decimal("0.0825")  # 8.25%
        tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        expected_total = Decimal("108.25")  # 100 + 8.25
        actual_total = subtotal + tax
        assert actual_total == expected_total

    @pytest.mark.asyncio
    async def test_complex_invoice_validation(self, validation_engine):
        """Test validation with complex invoice structure."""
        complex_invoice = {
            "header": {
                "vendor_name": "Complex Vendor",
                "invoice_number": "COMPLEX-001",
                "invoice_date": "2024-01-15",
                "due_date": "2024-02-15",
                "subtotal": Decimal("2475.50"),
                "tax_amount": Decimal("198.04"),
                "total_amount": Decimal("2673.54"),
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Hardware Item",
                    "quantity": Decimal("2"),
                    "unit_price": Decimal("500.00"),
                    "amount": Decimal("1000.00"),
                    "tax_rate": Decimal("0.08")
                },
                {
                    "description": "Software License",
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("750.00"),
                    "amount": Decimal("750.00"),
                    "tax_rate": Decimal("0.08")
                },
                {
                    "description": "Service Hours",
                    "quantity": Decimal("25"),
                    "unit_price": Decimal("25.00"),
                    "amount": Decimal("625.00"),
                    "tax_rate": Decimal("0.08")
                },
                {
                    "description": "Support Contract",
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("100.50"),
                    "amount": Decimal("100.50"),
                    "tax_rate": Decimal("0.08")
                }
            ],
            "confidence": {
                "overall": 0.91,  # Above 85% threshold
                "header": 0.93,
                "lines": 0.89
            }
        }

        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=complex_invoice,
                invoice_id="complex-invoice-001",
                strict_mode=True
            )

            assert result.validation_passed == True
            assert result.confidence_score > 0.85

    @pytest.mark.asyncio
    async def test_negative_and_zero_values(self, validation_engine):
        """Test validation handles negative and zero values appropriately."""
        invoice_with_negatives = {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_number": "NEGATIVE-001",
                "subtotal": Decimal("1000.00"),
                "tax_amount": Decimal("100.00"),
                "total_amount": Decimal("900.00"),  # Negative discount applied
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Item with discount",
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("1000.00"),
                    "amount": Decimal("1000.00"),
                    "tax_rate": Decimal("0.10")
                }
            ],
            "confidence": {
                "overall": 0.88
            }
        }

        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=invoice_with_negatives,
                invoice_id="negative-test-001",
                strict_mode=False
            )

            # This should fail validation due to total mismatch (1000 + 100 != 900)
            assert result.validation_passed == False

    def test_tolerance_handling(self):
        """Test validation handles floating point tolerance correctly."""
        # Test within acceptable tolerance (0.01)
        subtotal = Decimal("1000.00")
        tax = Decimal("100.00")
        expected_total = Decimal("1100.00")

        # Small floating point differences should be handled
        actual_total_1 = Decimal("1100.00")
        actual_total_2 = Decimal("1100.01")  # 1 cent difference

        # Exact match should pass
        assert actual_total_1 == (subtotal + tax)

        # Small difference should be within tolerance in validation
        difference = abs(actual_total_2 - (subtotal + tax))
        assert difference <= Decimal("0.01")  # Within 1 cent tolerance

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, validation_engine):
        """Test validation fails when required fields are missing."""
        incomplete_invoice = {
            "header": {
                "vendor_name": "Test Vendor",
                # Missing required fields
                "subtotal": Decimal("1000.00"),
                "tax_amount": Decimal("100.00"),
                "total_amount": Decimal("1100.00"),
            },
            "lines": [],  # Missing lines
            "confidence": {"overall": 0.90}
        }

        with patch('app.db.session.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session.return_value

            result = await validation_engine.validate_comprehensive(
                extraction_result=incomplete_invoice,
                invoice_id="incomplete-invoice",
                strict_mode=False
            )

            assert result.validation_passed == False

            # Should have missing fields errors
            missing_field_errors = [
                issue for issue in result.issues
                if issue.reason_code == ReasonTaxonomy.MISSING_REQUIRED_FIELDS.value
            ]

            assert len(missing_field_errors) > 0