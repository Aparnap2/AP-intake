"""
Tests for the enhanced validation service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.schemas.validation import (
    ValidationCode,
    ValidationSeverity,
    ValidationRulesConfig,
)
from app.services.validation_service import (
    ValidationService,
    MathValidator,
    MatchingValidator,
    VendorPolicyValidator,
    DuplicateDetector,
)


@pytest.fixture
def validation_service():
    """Create validation service instance."""
    return ValidationService()


@pytest.fixture
def sample_extraction_result():
    """Sample invoice extraction result."""
    return {
        "header": {
            "vendor_name": "Test Vendor Inc.",
            "invoice_no": "INV-2024-001",
            "invoice_date": "2024-01-15",
            "total": "1250.00",
            "subtotal": "1000.00",
            "tax": "250.00",
            "currency": "USD",
            "po_number": "PO-2024-001",
            "tax_id": "123456789"
        },
        "lines": [
            {
                "description": "Consulting Services",
                "amount": "1000.00",
                "quantity": "10",
                "unit_price": "100.00"
            }
        ]
    }


@pytest.fixture
def sample_vendor():
    """Sample vendor data."""
    vendor = MagicMock()
    vendor.id = "vendor-123"
    vendor.name = "Test Vendor Inc."
    vendor.currency = "USD"
    vendor.tax_id = "123456789"
    vendor.active = True
    vendor.status.value = "active"
    vendor.credit_limit = "10000.00"
    return vendor


@pytest.fixture
def sample_po():
    """Sample purchase order data."""
    po = MagicMock()
    po.id = "po-123"
    po.po_no = "PO-2024-001"
    po.total_amount = "1000.00"
    po.currency = "USD"
    po.status.value = "sent"
    return po


class TestValidationService:
    """Test the main validation service."""

    @pytest.mark.asyncio
    async def test_validate_invoice_success(self, validation_service, sample_extraction_result):
        """Test successful invoice validation."""
        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = MagicMock()

            result = await validation_service.validate_invoice(
                sample_extraction_result,
                invoice_id="test-123"
            )

            assert result["passed"] is True
            assert result["error_count"] == 0
            assert result["confidence_score"] > 0
            assert result["rules_version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_validate_invoice_missing_required_fields(self, validation_service):
        """Test validation with missing required fields."""
        invalid_extraction = {
            "header": {
                "vendor_name": "Test Vendor"
                # Missing invoice_no, invoice_date, total
            },
            "lines": []
        }

        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = MagicMock()

            result = await validation_service.validate_invoice(
                invalid_extraction,
                invoice_id="test-123"
            )

            assert result["passed"] is False
            assert result["error_count"] > 0

            # Check for specific error codes
            error_codes = [issue["code"] for issue in result["issues"]]
            assert ValidationCode.MISSING_REQUIRED_FIELD in error_codes
            assert ValidationCode.NO_LINE_ITEMS in error_codes

    @pytest.mark.asyncio
    async def test_validate_invoice_math_mismatch(self, validation_service):
        """Test validation with math errors."""
        invalid_extraction = {
            "header": {
                "vendor_name": "Test Vendor Inc.",
                "invoice_no": "INV-2024-001",
                "invoice_date": "2024-01-15",
                "total": "1500.00",  # Doesn't match subtotal + tax
                "subtotal": "1000.00",
                "tax": "250.00",
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Service",
                    "amount": "1000.00",
                    "quantity": "1",
                    "unit_price": "1000.00"
                }
            ]
        }

        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = MagicMock()

            result = await validation_service.validate_invoice(
                invalid_extraction,
                invoice_id="test-123"
            )

            assert result["passed"] is False
            error_codes = [issue["code"] for issue in result["issues"]]
            assert ValidationCode.TOTAL_MISMATCH in error_codes

    @pytest.mark.asyncio
    async def test_strict_mode_validation(self, validation_service, sample_extraction_result):
        """Test strict mode validation (warnings treated as errors)."""
        # Add a warning scenario (invalid currency format)
        sample_extraction_result["header"]["currency"] = "INVALID"

        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = MagicMock()

            # Normal mode should pass
            result = await validation_service.validate_invoice(
                sample_extraction_result,
                invoice_id="test-123",
                strict_mode=False
            )
            assert result["passed"] is True

            # Strict mode should fail
            result = await validation_service.validate_invoice(
                sample_extraction_result,
                invoice_id="test-123",
                strict_mode=True
            )
            assert result["passed"] is False

    def test_parse_date_formats(self, validation_service):
        """Test date parsing with various formats."""
        # Valid formats
        assert validation_service._parse_date("2024-01-15") is not None
        assert validation_service._parse_date("01/15/2024") is not None
        assert validation_service._parse_date("15-01-2024") is not None

        # Invalid formats
        assert validation_service._parse_date("invalid") is None
        assert validation_service._parse_date("") is None
        assert validation_service._parse_date(None) is None

    def test_calculate_confidence_score(self, validation_service):
        """Test confidence score calculation."""
        from app.api.schemas.validation import MathValidationResult, MatchingResult, VendorPolicyResult, DuplicateCheckResult

        # Perfect validation
        math_result = MathValidationResult(
            lines_total=1000.0,
            subtotal_match=True,
            total_match=True,
            tax_amount=250.0
        )
        matching_result = MatchingResult(
            po_found=True,
            po_amount_match=True,
            grn_found=True,
            quantity_match=True,
            matching_type="3_way"
        )
        vendor_result = VendorPolicyResult(
            vendor_active=True,
            currency_valid=True,
            spend_limit_ok=True,
            payment_terms_ok=True
        )
        duplicate_result = DuplicateCheckResult(
            is_duplicate=False,
            confidence=0.0
        )

        score = validation_service._calculate_confidence_score(
            True, True, True, math_result, matching_result, vendor_result, duplicate_result
        )
        assert score == 100.0

        # Failed validation
        score = validation_service._calculate_confidence_score(
            False, False, False, None, None, None, None
        )
        assert score == 0.0


class TestMathValidator:
    """Test the math validator."""

    @pytest.fixture
    def math_validator(self):
        """Create math validator instance."""
        config = ValidationRulesConfig(
            version="2.0.0",
            thresholds={"math_tolerance_cents": 1}
        )
        return MathValidator(config)

    @pytest.mark.asyncio
    async def test_successful_math_validation(self, math_validator, sample_extraction_result):
        """Test successful math validation."""
        issues = []
        result = await math_validator.validate(
            sample_extraction_result["header"],
            sample_extraction_result["lines"],
            issues
        )

        assert result is not None
        assert result.subtotal_match is True
        assert result.total_match is True
        assert result.lines_total == 1000.0
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_math_validation_total_mismatch(self, math_validator):
        """Test math validation with total mismatch."""
        header = {
            "total": "1500.00",
            "subtotal": "1000.00",
            "tax": "250.00"
        }
        lines = [{"amount": "1000.00"}]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result.total_match is False
        assert result.total_difference > 0
        assert len(issues) > 0
        assert issues[0].code == ValidationCode.TOTAL_MISMATCH

    @pytest.mark.asyncio
    async def test_math_validation_missing_subtotal(self, math_validator):
        """Test math validation with missing subtotal."""
        header = {
            "total": "1250.00",
            "tax": "250.00"
            # Missing subtotal
        }
        lines = [{"amount": "1000.00"}]
        issues = []

        result = await math_validator.validate(header, lines, issues)

        assert result.subtotal_match is None
        assert result.total_match is True  # Should use lines_total as subtotal
        assert any(issue.code == ValidationCode.MISSING_REQUIRED_FIELD for issue in issues)


class TestMatchingValidator:
    """Test the matching validator."""

    @pytest.fixture
    def matching_validator(self):
        """Create matching validator instance."""
        config = ValidationRulesConfig(
            version="2.0.0",
            thresholds={
                "po_amount_tolerance_percent": 5.0,
                "grn_quantity_tolerance_percent": 10.0
            }
        )
        return MatchingValidator(config)

    @pytest.mark.asyncio
    async def test_successful_po_matching(self, matching_validator, sample_extraction_result, sample_vendor, sample_po):
        """Test successful PO matching."""
        mock_session = AsyncMock()

        # Mock PO query
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = sample_po

        # Mock vendor query
        with patch('app.services.validation_service.select') as mock_select:
            mock_query.join.return_value.where.return_value = mock_query
            mock_select.return_value = mock_query

            issues = []
            result = await matching_validator.validate(
                sample_extraction_result["header"],
                sample_extraction_result["lines"],
                mock_session,
                issues
            )

            assert result.po_found is True
            assert result.po_number == "PO-2024-001"
            assert result.matching_type == "2_way"  # No GRN found

    @pytest.mark.asyncio
    async def test_po_not_found(self, matching_validator, sample_extraction_result):
        """Test PO not found scenario."""
        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = None

        with patch('app.services.validation_service.select') as mock_select:
            mock_query.join.return_value.where.return_value = mock_query
            mock_select.return_value = mock_query

            issues = []
            result = await matching_validator.validate(
                sample_extraction_result["header"],
                sample_extraction_result["lines"],
                mock_session,
                issues
            )

            assert result.po_found is False
            assert len(issues) > 0
            assert issues[0].code == ValidationCode.PO_NOT_FOUND

    @pytest.mark.asyncio
    async def test_po_amount_mismatch(self, matching_validator, sample_extraction_result, sample_vendor, sample_po):
        """Test PO amount mismatch."""
        # Change PO amount to create mismatch
        sample_po.total_amount = "900.00"  # Different from invoice total of 1250.00

        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = sample_po

        with patch('app.services.validation_service.select') as mock_select:
            mock_query.join.return_value.where.return_value = mock_query
            mock_select.return_value = mock_query

            issues = []
            result = await matching_validator.validate(
                sample_extraction_result["header"],
                sample_extraction_result["lines"],
                mock_session,
                issues
            )

            assert result.po_found is True
            assert result.po_amount_match is False
            assert len(issues) > 0
            assert issues[0].code == ValidationCode.PO_AMOUNT_MISMATCH


class TestVendorPolicyValidator:
    """Test the vendor policy validator."""

    @pytest.fixture
    def vendor_policy_validator(self):
        """Create vendor policy validator instance."""
        config = ValidationRulesConfig(version="2.0.0")
        return VendorPolicyValidator(config)

    @pytest.mark.asyncio
    async def test_successful_vendor_validation(self, vendor_policy_validator, sample_extraction_result, sample_vendor):
        """Test successful vendor policy validation."""
        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = sample_vendor

        with patch('app.services.validation_service.select') as mock_select:
            mock_select.return_value = mock_query

            issues = []
            result = await vendor_policy_validator.validate(
                sample_extraction_result["header"],
                "vendor-123",
                mock_session,
                issues
            )

            assert result.vendor_active is True
            assert result.currency_valid is True
            assert result.tax_id_valid is True
            assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_vendor_not_found(self, vendor_policy_validator, sample_extraction_result):
        """Test vendor not found scenario."""
        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = None

        with patch('app.services.validation_service.select') as mock_select:
            mock_select.return_value = mock_query

            issues = []
            result = await vendor_policy_validator.validate(
                sample_extraction_result["header"],
                None,
                mock_session,
                issues
            )

            assert result.vendor_active is False
            assert len(issues) > 0
            assert issues[0].code == ValidationCode.INACTIVE_VENDOR

    @pytest.mark.asyncio
    async def test_currency_mismatch(self, vendor_policy_validator, sample_extraction_result, sample_vendor):
        """Test currency mismatch validation."""
        # Change invoice currency to create mismatch
        sample_extraction_result["header"]["currency"] = "EUR"

        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.scalar_one_or_none.return_value = sample_vendor

        with patch('app.services.validation_service.select') as mock_select:
            mock_select.return_value = mock_query

            issues = []
            result = await vendor_policy_validator.validate(
                sample_extraction_result["header"],
                "vendor-123",
                mock_session,
                issues
            )

            assert result.currency_valid is False
            assert len(issues) > 0
            assert issues[0].code == ValidationCode.INVALID_CURRENCY


class TestDuplicateDetector:
    """Test the duplicate detector."""

    @pytest.fixture
    def duplicate_detector(self):
        """Create duplicate detector instance."""
        config = ValidationRulesConfig(
            version="2.0.0",
            thresholds={"duplicate_confidence_threshold": 0.95}
        )
        return DuplicateDetector(config)

    @pytest.mark.asyncio
    async def test_no_duplicate_found(self, duplicate_detector, sample_extraction_result):
        """Test when no duplicate is found."""
        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.all.return_value = []  # No duplicates found

        with patch('app.services.validation_service.select') as mock_select:
            mock_select.return_value = mock_query

            issues = []
            result = await duplicate_detector.check(
                sample_extraction_result["header"],
                "invoice-123",
                mock_session,
                issues
            )

            assert result.is_duplicate is False
            assert result.confidence == 0.0
            assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_duplicate_found(self, duplicate_detector, sample_extraction_result):
        """Test when duplicate is found."""
        # Mock duplicate invoice
        mock_duplicate_invoice = MagicMock()
        mock_duplicate_invoice.id = "duplicate-123"
        mock_duplicate_invoice.status.value = "processed"
        mock_duplicate_invoice.created_at = datetime.now() - timedelta(days=1)

        mock_duplicate_extraction = MagicMock()
        mock_duplicate_extraction.header_json = {
            "invoice_no": "INV-2024-001",
            "total": "1250.00",
            "invoice_date": "2024-01-15"
        }

        mock_session = AsyncMock()
        mock_query = AsyncMock()
        mock_session.execute.return_value = mock_query
        mock_query.all.return_value = [(mock_duplicate_invoice, mock_duplicate_extraction)]

        # Mock vendor query
        mock_vendor = MagicMock()
        with patch('app.services.validation_service.select') as mock_select:
            mock_select.return_value = mock_query
            mock_query.return_value.where.return_value = mock_query
            mock_query.scalar_one_or_none.return_value = mock_vendor

            issues = []
            result = await duplicate_detector.check(
                sample_extraction_result["header"],
                "invoice-123",
                mock_session,
                issues
            )

            assert result.is_duplicate is True
            assert result.confidence == 1.0
            assert len(result.duplicate_invoices) == 1
            assert len(issues) > 0
            assert issues[0].code == ValidationCode.DUPLICATE_INVOICE

    @pytest.mark.asyncio
    async def test_insufficient_data_for_duplicate_check(self, duplicate_detector):
        """Test duplicate check with insufficient data."""
        header = {"vendor_name": "Test Vendor"}  # Missing invoice_no

        mock_session = AsyncMock()
        issues = []
        result = await duplicate_detector.check(
            header,
            "invoice-123",
            mock_session,
            issues
        )

        assert result.is_duplicate is False
        assert result.match_criteria["reason"] == "insufficient_data"
        assert len(issues) == 0


class TestValidationIntegration:
    """Integration tests for the complete validation service."""

    @pytest.mark.asyncio
    async def test_end_to_end_validation(self, validation_service, sample_extraction_result):
        """Test complete validation workflow."""
        # Mock all database interactions
        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Mock vendor lookup
            mock_vendor = MagicMock()
            mock_vendor.active = True
            mock_vendor.status.value = "active"
            mock_vendor.currency = "USD"
            mock_vendor.tax_id = "123456789"
            mock_vendor.credit_limit = "10000.00"

            # Mock PO lookup
            mock_po = MagicMock()
            mock_po.po_no = "PO-2024-001"
            mock_po.total_amount = "1250.00"
            mock_po.currency = "USD"
            mock_po.status.value = "sent"

            # Configure mock returns
            mock_session_instance.execute.return_value.scalar_one_or_none.side_effect = [
                mock_vendor,  # Vendor lookup
                mock_po,      # PO lookup
                [],           # GRN lookup (none found)
                0.0           # Current spend query
            ]

            result = await validation_service.validate_invoice(
                sample_extraction_result,
                invoice_id="test-123",
                vendor_id="vendor-123"
            )

            assert result["passed"] is True
            assert result["confidence_score"] > 80  # High confidence for good data
            assert result["check_results"]["structure_check"] is True
            assert result["check_results"]["header_fields_check"] is True
            assert result["check_results"]["line_items_check"] is True
            assert result["check_results"]["math_check"] is True
            assert result["check_results"]["vendor_policy_check"] is True
            assert result["check_results"]["matching_check"] is True
            assert result["check_results"]["duplicate_check"] is True

    @pytest.mark.asyncio
    async def test_validation_with_multiple_issues(self, validation_service):
        """Test validation with multiple types of issues."""
        problematic_extraction = {
            "header": {
                "vendor_name": "Unknown Vendor",
                "invoice_no": "INV-2024-001",
                "invoice_date": "invalid-date",
                "total": "1500.00",
                "subtotal": "1000.00",
                "tax": "250.00",
                "currency": "INVALID",
                "po_number": "PO-NOT-FOUND"
            },
            "lines": [
                {
                    "description": "Service",
                    "amount": "1000.00",
                    "quantity": "1",
                    "unit_price": "1100.00"  # Math mismatch
                }
            ]
        }

        with patch('app.services.validation_service.AsyncSessionLocal') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # No vendor found
            mock_session_instance.execute.return_value.scalar_one_or_none.return_value = None

            result = await validation_service.validate_invoice(
                problematic_extraction,
                invoice_id="test-123"
            )

            assert result["passed"] is False
            assert result["error_count"] > 0
            assert result["warning_count"] > 0

            # Check for various issue types
            error_codes = [issue["code"] for issue in result["issues"]]
            assert ValidationCode.INVALID_FIELD_FORMAT in error_codes  # Invalid date
            assert ValidationCode.INVALID_CURRENCY in error_codes    # Invalid currency
            assert ValidationCode.PO_NOT_FOUND in error_codes       # PO not found
            assert ValidationCode.INACTIVE_VENDOR in error_codes    # Vendor not found