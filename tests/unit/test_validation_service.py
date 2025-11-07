"""
Unit tests for ValidationService comprehensive invoice validation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.validation_service import (
    ValidationService,
    MathValidator,
    MatchingValidator,
    VendorPolicyValidator,
    DuplicateDetector,
)
from app.api.schemas.validation import (
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationRulesConfig,
)
from app.models.reference import Vendor, PurchaseOrder, GoodsReceiptNote


class TestValidationService:
    """Test suite for ValidationService."""

    @pytest.fixture
    def validation_service(self) -> ValidationService:
        """Create ValidationService instance for testing."""
        return ValidationService()

    @pytest.fixture
    def valid_extraction_result(self) -> Dict[str, Any]:
        """Valid extraction result for testing."""
        return {
            "header": {
                "vendor_name": "Test Vendor Inc",
                "invoice_no": "INV-2024-001",
                "invoice_date": "2024-01-15",
                "due_date": "2024-02-15",
                "po_number": "PO-2024-001",
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
            "overall_confidence": 0.95,
        }

    @pytest.fixture
    def invalid_extraction_result(self) -> Dict[str, Any]:
        """Invalid extraction result for testing."""
        return {
            "header": {
                "vendor_name": "",  # Missing required field
                "invoice_no": None,  # Missing required field
                "total": -100.00,  # Invalid amount
                "invoice_date": "32/13/2024",  # Invalid date
            },
            "lines": [],  # No line items
            "overall_confidence": 0.3,
        }

    @pytest.mark.asyncio
    async def test_validate_invoice_success(
        self, validation_service: ValidationService, valid_extraction_result: Dict[str, Any]
    ):
        """Test successful invoice validation."""
        with patch.object(validation_service, '_create_validation_exceptions') as mock_exceptions:
            mock_exceptions.return_value = []

            result = await validation_service.validate_invoice(
                extraction_result=valid_extraction_result,
                invoice_id="test-invoice-id"
            )

            assert result["passed"] is True
            assert result["error_count"] == 0
            assert result["confidence_score"] > 0.8
            assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_invoice_failure(
        self, validation_service: ValidationService, invalid_extraction_result: Dict[str, Any]
    ):
        """Test invoice validation failure."""
        with patch.object(validation_service, '_create_validation_exceptions') as mock_exceptions:
            mock_exceptions.return_value = []

            result = await validation_service.validate_invoice(
                extraction_result=invalid_extraction_result,
                invoice_id="test-invoice-id"
            )

            assert result["passed"] is False
            assert result["error_count"] > 0
            assert len(result["issues"]) > 0

            # Check for specific validation issues
            error_codes = [issue.code for issue in result["issues"]]
            assert ValidationCode.MISSING_REQUIRED_FIELD in error_codes
            assert ValidationCode.INVALID_AMOUNT in error_codes
            assert ValidationCode.NO_LINE_ITEMS in error_codes

    @pytest.mark.asyncio
    async def test_validate_structure_success(self, validation_service: ValidationService):
        """Test successful structure validation."""
        header = {"vendor_name": "Test Vendor"}
        lines = [{"description": "Test", "amount": 100.0}]
        issues = []

        result = await validation_service._validate_structure(
            header, lines, issues, validation_service.rules_config
        )

        assert result is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_structure_failure(self, validation_service: ValidationService):
        """Test structure validation failures."""
        issues = []

        # Test invalid header
        result = await validation_service._validate_structure(
            "invalid_header", [], issues, validation_service.rules_config
        )
        assert result is False
        assert len(issues) > 0

        # Reset issues
        issues.clear()

        # Test invalid lines
        result = await validation_service._validate_structure(
            {}, "invalid_lines", issues, validation_service.rules_config
        )
        assert result is False
        assert len(issues) > 0

        # Reset issues
        issues.clear()

        # Test empty lines
        result = await validation_service._validate_structure(
            {}, [], issues, validation_service.rules_config
        )
        assert result is False
        assert len(issues) > 0

    @pytest.mark.asyncio
    async def test_validate_header_success(self, validation_service: ValidationService):
        """Test successful header validation."""
        header = {
            "vendor_name": "Test Vendor",
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "total": 1000.00,
            "currency": "USD",
        }
        issues = []

        result = await validation_service._validate_header(
            header, issues, validation_service.rules_config
        )

        assert result is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_header_missing_fields(self, validation_service: ValidationService):
        """Test header validation with missing required fields."""
        header = {
            "vendor_name": "",
            "invoice_no": None,
            "total": 1000.00,
        }
        issues = []

        result = await validation_service._validate_header(
            header, issues, validation_service.rules_config
        )

        assert result is False
        assert len(issues) >= 2  # vendor_name and invoice_no missing

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.MISSING_REQUIRED_FIELD in error_codes

    @pytest.mark.asyncio
    async def test_validate_header_formats(self, validation_service: ValidationService):
        """Test header field format validation."""
        issues = []

        # Test invalid date format
        header = {
            "vendor_name": "Test Vendor",
            "invoice_no": "INV-001",
            "invoice_date": "32/13/2024",  # Invalid
            "total": 1000.00,
            "currency": "INVALID",  # Invalid currency
        }

        await validation_service._validate_header_formats(header, issues, validation_service.rules_config)

        assert len(issues) >= 2
        error_codes = [issue.code for issue in issues]
        assert ValidationCode.INVALID_FIELD_FORMAT in error_codes

    @pytest.mark.asyncio
    async def test_validate_lines_success(self, validation_service: ValidationService):
        """Test successful line items validation."""
        lines = [
            {
                "description": "Test Product",
                "quantity": 2,
                "unit_price": 50.00,
                "amount": 100.00,
            }
        ]
        issues = []

        result = await validation_service._validate_lines(
            lines, issues, validation_service.rules_config
        )

        assert result is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_lines_missing_fields(self, validation_service: ValidationService):
        """Test line items validation with missing fields."""
        lines = [
            {
                "description": "",  # Missing required field
                "amount": 100.00,
            },
            {
                # Missing description
                "quantity": 1,
                "amount": 50.00,
            }
        ]
        issues = []

        result = await validation_service._validate_lines(
            lines, issues, validation_service.rules_config
        )

        assert result is False
        assert len(issues) >= 2

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.MISSING_REQUIRED_FIELD in error_codes

    @pytest.mark.asyncio
    async def test_validate_line_amounts(self, validation_service: ValidationService):
        """Test line item amount validation."""
        issues = []

        # Test valid amounts
        line = {
            "description": "Test Product",
            "quantity": 2,
            "unit_price": 50.00,
            "amount": 100.00,
        }

        await validation_service._validate_line_amounts(
            line, 0, issues, validation_service.rules_config
        )
        assert len(issues) == 0

        # Test amount too low
        issues.clear()
        line["amount"] = 0.001  # Below minimum

        await validation_service._validate_line_amounts(
            line, 0, issues, validation_service.rules_config
        )
        assert len(issues) > 0

        # Test amount too high
        issues.clear()
        line["amount"] = 200000.00  # Above maximum

        await validation_service._validate_line_amounts(
            line, 0, issues, validation_service.rules_config
        )
        assert len(issues) > 0

        # Test math mismatch
        issues.clear()
        line["amount"] = 90.00  # Doesn't match 2 x 50.00

        await validation_service._validate_line_amounts(
            line, 0, issues, validation_service.rules_config
        )
        assert len(issues) > 0

    def test_parse_date(self, validation_service: ValidationService):
        """Test date parsing functionality."""
        valid_dates = [
            ("2024-01-15", datetime(2024, 1, 15)),
            ("01/15/2024", datetime(2024, 1, 15)),
            ("15-01-2024", datetime(2024, 1, 15)),
            ("2024/01/15", datetime(2024, 1, 15)),
        ]

        for date_str, expected in valid_dates:
            result = validation_service._parse_date(date_str)
            assert result == expected

        invalid_dates = [
            "32/13/2024",
            "invalid-date",
            "",
            None,
        ]

        for invalid_date in invalid_dates:
            result = validation_service._parse_date(invalid_date)
            assert result is None

    def test_is_valid_amount(self, validation_service: ValidationService):
        """Test amount validation helper."""
        valid_amounts = [100, 100.50, "100", "100.50"]
        invalid_amounts = [None, "", "invalid", [], {}]

        for amount in valid_amounts:
            assert validation_service._is_valid_amount(amount) is True

        for amount in invalid_amounts:
            assert validation_service._is_valid_amount(amount) is False

    def test_calculate_confidence_score(self, validation_service: ValidationService):
        """Test confidence score calculation."""
        # Test perfect score
        score = validation_service._calculate_confidence_score(
            structure_result=True,
            header_result=True,
            lines_result=True,
            math_result=MagicMock(subtotal_match=True, total_match=True),
            matching_result=MagicMock(po_found=True, po_amount_match=True, grn_found=True, quantity_match=True),
            vendor_policy_result=MagicMock(vendor_active=True, currency_valid=True, spend_limit_ok=True),
            duplicate_result=MagicMock(is_duplicate=False)
        )
        assert score == 100.0

        # Test zero score
        score = validation_service._calculate_confidence_score(
            structure_result=False,
            header_result=False,
            lines_result=False,
            math_result=None,
            matching_result=None,
            vendor_policy_result=None,
            duplicate_result=None
        )
        assert score < 50.0

    def test_create_header_summary(self, validation_service: ValidationService):
        """Test header summary creation."""
        header = {
            "vendor_name": "Test Vendor",
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "total": 1100.00,
            "currency": "USD",
            "po_number": "PO-001",
            "tax": 100.00,
        }

        summary = validation_service._create_header_summary(header)

        assert summary["vendor_name"] == "Test Vendor"
        assert summary["invoice_no"] == "INV-001"
        assert summary["total"] == 1100.00
        assert summary["currency"] == "USD"

    def test_create_lines_summary(self, validation_service: ValidationService):
        """Test lines summary creation."""
        lines = [
            {"description": "Test Product 1", "amount": 100.00},
            {"description": "Test Product 2", "amount": 200.00},
            {"description": "Test Product 3", "amount": 150.00},
        ]

        summary = validation_service._create_lines_summary(lines)

        assert summary["count"] == 3
        assert summary["total"] == 450.00
        assert len(summary["descriptions"]) == 3
        assert "Test Product 1" in summary["descriptions"][0]

    def test_create_lines_summary_empty(self, validation_service: ValidationService):
        """Test lines summary creation with empty lines."""
        summary = validation_service._create_lines_summary([])

        assert summary["count"] == 0
        assert summary["total"] == 0.0


class TestMathValidator:
    """Test suite for MathValidator."""

    @pytest.fixture
    def math_validator(self) -> MathValidator:
        """Create MathValidator instance for testing."""
        config = ValidationRulesConfig(
            thresholds={"math_tolerance_cents": 1}
        )
        return MathValidator(config)

    @pytest.mark.asyncio
    async def test_validate_math_success(self, math_validator: MathValidator):
        """Test successful math validation."""
        header = {
            "subtotal": 1000.00,
            "tax": 100.00,
            "total": 1100.00,
        }
        lines = [
            {"amount": 600.00},
            {"amount": 400.00},
        ]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result is not None
        assert result.subtotal_match is True
        assert result.total_match is True
        assert result.lines_total == 1000.00
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_math_subtotal_mismatch(self, math_validator: MathValidator):
        """Test math validation with subtotal mismatch."""
        header = {
            "subtotal": 900.00,  # Wrong subtotal
            "tax": 100.00,
            "total": 1100.00,
        }
        lines = [
            {"amount": 600.00},
            {"amount": 400.00},
        ]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result is not None
        assert result.subtotal_match is False
        assert result.subtotal_difference == 100.00
        assert len(issues) > 0

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.SUBTOTAL_MISMATCH in error_codes

    @pytest.mark.asyncio
    async def test_validate_math_total_mismatch(self, math_validator: MathValidator):
        """Test math validation with total mismatch."""
        header = {
            "subtotal": 1000.00,
            "tax": 100.00,
            "total": 1200.00,  # Wrong total
        }
        lines = [
            {"amount": 600.00},
            {"amount": 400.00},
        ]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result is not None
        assert result.total_match is False
        assert result.total_difference == 100.00
        assert len(issues) > 0

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.TOTAL_MISMATCH in error_codes

    @pytest.mark.asyncio
    async def test_validate_math_missing_totals(self, math_validator: MathValidator):
        """Test math validation with missing total fields."""
        header = {}  # No subtotal or total
        lines = [{"amount": 100.00}]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result is not None
        assert result.subtotal_match is None
        assert result.total_match is None
        assert len(issues) > 0

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.MISSING_REQUIRED_FIELD in error_codes

    @pytest.mark.asyncio
    async def test_validate_line_math(self, math_validator: MathValidator):
        """Test individual line item math validation."""
        issues = []

        # Valid line math
        line = {"quantity": 2, "unit_price": 50.00, "amount": 100.00}
        line_validation = {"valid": True}

        await math_validator._validate_line_math(line, 0, issues, line_validation)
        assert len(issues) == 0
        assert line_validation["valid"] is True

        # Invalid line math
        issues.clear()
        line["amount"] = 90.00  # Doesn't match 2 x 50.00

        await math_validator._validate_line_math(line, 0, issues, line_validation)
        assert len(issues) > 0
        assert line_validation["valid"] is False

        error_codes = [issue.code for issue in issues]
        assert ValidationCode.LINE_MATH_MISMATCH in error_codes


class TestMatchingValidator:
    """Test suite for MatchingValidator."""

    @pytest.fixture
    def matching_validator(self) -> MatchingValidator:
        """Create MatchingValidator instance for testing."""
        config = ValidationRulesConfig(
            thresholds={
                "po_amount_tolerance_percent": 5.0,
                "grn_quantity_tolerance_percent": 10.0,
            }
        )
        return MatchingValidator(config)

    @pytest.mark.asyncio
    async def test_validate_matching_success(self, matching_validator: MatchingValidator):
        """Test successful PO/GRN matching."""
        header = {
            "po_number": "PO-001",
            "vendor_name": "Test Vendor",
            "total": 1000.00,
        }
        lines = [
            {"description": "Test Product", "quantity": 10},
        ]

        # Mock database session and results
        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_vendor.id = "vendor-123"
        mock_po = MagicMock()
        mock_po.id = "po-123"
        mock_po.po_no = "PO-001"
        mock_po.total_amount = 1000.00
        mock_po.status = MagicMock(value="approved")
        mock_grn = MagicMock()
        mock_grn.grn_no = "GRN-001"
        mock_grn.received_at = datetime.utcnow()
        mock_grn.lines_json = [{"description": "Test Product", "quantity": 10}]

        # Mock database queries
        with patch('sqlalchemy.select') as mock_select:
            # Mock vendor query
            mock_vendor_result = AsyncMock()
            mock_vendor_result.scalar_one_or_none.return_value = mock_vendor
            # Mock PO query
            mock_po_result = AsyncMock()
            mock_po_result.scalar_one_or_none.return_value = mock_po
            # Mock GRN query
            mock_grn_result = AsyncMock()
            mock_grn_result.scalars.return_value.all.return_value = [mock_grn]

            mock_select.return_value.join.return_value.where.return_value = mock_vendor_result
            mock_select.return_value.where.return_value = mock_po_result
            mock_select.return_value.where.return_value = mock_grn_result

            issues = []
            result = await matching_validator.validate(header, lines, mock_session, issues)

            assert result is not None
            assert result.po_found is True
            assert result.po_amount_match is True
            assert result.grn_found is True
            assert result.matching_type == "3_way"
            assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_matching_no_po(self, matching_validator: MatchingValidator):
        """Test matching when PO not found."""
        header = {
            "po_number": "PO-NOTFOUND",
            "vendor_name": "Test Vendor",
            "total": 1000.00,
        }
        lines = [{"description": "Test Product"}]

        mock_session = AsyncMock(spec=AsyncSession)

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None  # PO not found
            mock_select.return_value.join.return_value.where.return_value = mock_result

            issues = []
            result = await matching_validator.validate(header, lines, mock_session, issues)

            assert result is not None
            assert result.po_found is False
            assert result.matching_type == "2_way"
            assert len(issues) > 0

            error_codes = [issue.code for issue in issues]
            assert ValidationCode.PO_NOT_FOUND in error_codes

    @pytest.mark.asyncio
    async def test_validate_matching_amount_mismatch(self, matching_validator: MatchingValidator):
        """Test matching with PO amount mismatch."""
        header = {
            "po_number": "PO-001",
            "vendor_name": "Test Vendor",
            "total": 1200.00,  # Higher than PO
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_po = MagicMock()
        mock_po.total_amount = 1000.00  # Lower than invoice

        with patch('sqlalchemy.select') as mock_select:
            mock_vendor_result = AsyncMock()
            mock_vendor_result.scalar_one_or_none.return_value = mock_vendor
            mock_po_result = AsyncMock()
            mock_po_result.scalar_one_or_none.return_value = mock_po

            mock_select.return_value.join.return_value.where.return_value = mock_vendor_result
            mock_select.return_value.where.return_value = mock_po_result

            issues = []
            result = await matching_validator.validate(header, [], mock_session, issues)

            assert result is not None
            assert result.po_amount_match is False
            assert len(issues) > 0

            error_codes = [issue.code for issue in issues]
            assert ValidationCode.PO_AMOUNT_MISMATCH in error_codes


class TestVendorPolicyValidator:
    """Test suite for VendorPolicyValidator."""

    @pytest.fixture
    def vendor_policy_validator(self) -> VendorPolicyValidator:
        """Create VendorPolicyValidator instance for testing."""
        config = ValidationRulesConfig(thresholds={})
        return VendorPolicyValidator(config)

    @pytest.mark.asyncio
    async def test_validate_vendor_success(self, vendor_policy_validator: VendorPolicyValidator):
        """Test successful vendor policy validation."""
        header = {
            "vendor_name": "Test Vendor",
            "currency": "USD",
            "total": 1000.00,
            "tax_id": "12-3456789",
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_vendor.id = "vendor-123"
        mock_vendor.name = "Test Vendor"
        mock_vendor.currency = "USD"
        mock_vendor.tax_id = "12-3456789"
        mock_vendor.active = True
        mock_vendor.status = MagicMock(value="active")
        mock_vendor.credit_limit = 10000.00

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_vendor
            mock_select.return_value.where.return_value = mock_result

            with patch('sqlalchemy.func.sum') as mock_sum:
                mock_sum_result = AsyncMock()
                mock_sum_result.scalar.return_value = 5000.00  # Current spend
                mock_select.return_value = mock_sum_result

                issues = []
                result = await vendor_policy_validator.validate(
                    header, None, mock_session, issues
                )

                assert result is not None
                assert result.vendor_active is True
                assert result.currency_valid is True
                assert result.tax_id_valid is True
                assert result.spend_limit_ok is True
                assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_validate_vendor_not_found(self, vendor_policy_validator: VendorPolicyValidator):
        """Test validation when vendor not found."""
        header = {
            "vendor_name": "Unknown Vendor",
            "currency": "USD",
            "total": 1000.00,
        }

        mock_session = AsyncMock(spec=AsyncSession)

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_select.return_value.where.return_value = mock_result

            issues = []
            result = await vendor_policy_validator.validate(
                header, None, mock_session, issues
            )

            assert result is not None
            assert result.vendor_active is False
            assert len(issues) > 0

            error_codes = [issue.code for issue in issues]
            assert ValidationCode.INACTIVE_VENDOR in error_codes

    @pytest.mark.asyncio
    async def test_validate_vendor_inactive(self, vendor_policy_validator: VendorPolicyValidator):
        """Test validation with inactive vendor."""
        header = {
            "vendor_name": "Test Vendor",
            "currency": "USD",
            "total": 1000.00,
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_vendor.active = False
        mock_vendor.status = MagicMock(value="inactive")

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_vendor
            mock_select.return_value.where.return_value = mock_result

            issues = []
            result = await vendor_policy_validator.validate(
                header, None, mock_session, issues
            )

            assert result is not None
            assert result.vendor_active is False
            assert len(issues) > 0

            error_codes = [issue.code for issue in issues]
            assert ValidationCode.INACTIVE_VENDOR in error_codes

    @pytest.mark.asyncio
    async def test_validate_currency_mismatch(self, vendor_policy_validator: VendorPolicyValidator):
        """Test validation with currency mismatch."""
        header = {
            "vendor_name": "Test Vendor",
            "currency": "EUR",  # Different from vendor
            "total": 1000.00,
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_vendor.currency = "USD"
        mock_vendor.active = True

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_vendor
            mock_select.return_value.where.return_value = mock_result

            issues = []
            result = await vendor_policy_validator.validate(
                header, None, mock_session, issues
            )

            assert result is not None
            assert result.currency_valid is False
            assert len(issues) > 0

            error_codes = [issue.code for issue in issues]
            assert ValidationCode.INVALID_CURRENCY in error_codes

    @pytest.mark.asyncio
    async def test_validate_spend_limit_exceeded(self, vendor_policy_validator: VendorPolicyValidator):
        """Test validation when spend limit exceeded."""
        header = {
            "vendor_name": "Test Vendor",
            "currency": "USD",
            "total": 6000.00,  # Will exceed limit
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_vendor = MagicMock()
        mock_vendor.currency = "USD"
        mock_vendor.active = True
        mock_vendor.credit_limit = 10000.00

        with patch('sqlalchemy.select') as mock_select:
            # Mock vendor query
            mock_vendor_result = AsyncMock()
            mock_vendor_result.scalar_one_or_none.return_value = mock_vendor
            # Mock spend query
            mock_spend_result = AsyncMock()
            mock_spend_result.scalar.return_value = 5000.00  # Current spend
            mock_select.return_value.where.return_value = mock_vendor_result
            mock_select.return_value = mock_spend_result

            with patch('sqlalchemy.func.sum') as mock_sum:
                issues = []
                result = await vendor_policy_validator.validate(
                    header, None, mock_session, issues
                )

                assert result is not None
                assert result.spend_limit_ok is False
                assert len(issues) > 0

                error_codes = [issue.code for issue in issues]
                assert ValidationCode.SPEND_LIMIT_EXCEEDED in error_codes


class TestDuplicateDetector:
    """Test suite for DuplicateDetector."""

    @pytest.fixture
    def duplicate_detector(self) -> DuplicateDetector:
        """Create DuplicateDetector instance for testing."""
        config = ValidationRulesConfig(
            thresholds={"duplicate_confidence_threshold": 0.95}
        )
        return DuplicateDetector(config)

    @pytest.mark.asyncio
    async def test_check_duplicate_success(self, duplicate_detector: DuplicateDetector):
        """Test successful duplicate check - no duplicates found."""
        header = {
            "invoice_no": "INV-001",
            "vendor_name": "Test Vendor",
            "total": "1000.00",
            "invoice_date": "2024-01-15",
        }

        mock_session = AsyncMock(spec=AsyncSession)

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.all.return_value = []  # No duplicates found
            mock_select.return_value.join.return_value.where.return_value = mock_result

            issues = []
            result = await duplicate_detector.check(header, None, mock_session, issues)

            assert result is not None
            assert result.is_duplicate is False
            assert len(result.duplicate_invoices) == 0
            assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_check_duplicate_found(self, duplicate_detector: DuplicateDetector):
        """Test duplicate check - duplicates found."""
        header = {
            "invoice_no": "INV-001",
            "vendor_name": "Test Vendor",
            "total": "1000.00",
            "invoice_date": "2024-01-15",
        }

        mock_session = AsyncMock(spec=AsyncSession)
        mock_duplicate_invoice = MagicMock()
        mock_duplicate_extraction = MagicMock()
        mock_duplicate_extraction.header_json = {
            "invoice_no": "INV-001",
            "total": "1000.00",
            "invoice_date": "2024-01-15",
        }

        with patch('sqlalchemy.select') as mock_select:
            mock_result = AsyncMock()
            mock_result.all.return_value = [(mock_duplicate_invoice, mock_duplicate_extraction)]
            mock_select.return_value.join.return_value.where.return_value = mock_result

            with patch.object(duplicate_detector, '_extract_header_value') as mock_extract:
                mock_extract.side_effect = lambda json_dict, key: json_dict.get(key, "")

                issues = []
                result = await duplicate_detector.check(header, None, mock_session, issues)

                assert result is not None
                assert result.is_duplicate is True
                assert len(result.duplicate_invoices) == 1
                assert len(issues) > 0

                error_codes = [issue.code for issue in issues]
                assert ValidationCode.DUPLICATE_INVOICE in error_codes

    @pytest.mark.asyncio
    async def test_check_duplicate_insufficient_data(self, duplicate_detector: DuplicateDetector):
        """Test duplicate check with insufficient data."""
        header = {
            "vendor_name": "Test Vendor",
            # Missing invoice_no
        }

        mock_session = AsyncMock(spec=AsyncSession)
        issues = []

        result = await duplicate_detector.check(header, None, mock_session, issues)

        assert result is not None
        assert result.is_duplicate is False
        assert "insufficient_data" in result.match_criteria["reason"]
        assert len(issues) == 0

    def test_extract_header_value(self, duplicate_detector: DuplicateDetector):
        """Test header value extraction."""
        header_json = {
            "invoice_no": "INV-001",
            "total": "1000.00",
        }

        # Test valid extraction
        result = duplicate_detector._extract_header_value(header_json, "invoice_no")
        assert result == "INV-001"

        # Test missing key
        result = duplicate_detector._extract_header_value(header_json, "missing_key")
        assert result == ""

        # Test non-dict input
        result = duplicate_detector._extract_header_value("not a dict", "invoice_no")
        assert result == ""