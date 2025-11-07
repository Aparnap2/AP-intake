"""
Tests for QuickBooks service integration.

This module contains unit tests for the QuickBooks service,
testing OAuth flow, invoice export, and error handling.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from app.services.quickbooks_service import QuickBooksService, QuickBooksServiceException
from app.core.exceptions import ValidationException


class TestQuickBooksService:
    """Test cases for QuickBooksService."""

    @pytest.fixture
    def qb_service(self):
        """Create a QuickBooks service instance for testing."""
        with patch('app.services.quickbooks_service.settings'):
            return QuickBooksService()

    @pytest.fixture
    def sample_invoice_data(self):
        """Sample invoice data for testing."""
        return {
            "header": {
                "vendor_name": "Test Vendor",
                "invoice_no": "INV-001",
                "invoice_date": "2025-01-01",
                "due_date": "2025-01-15",
                "po_no": "PO-001",
                "currency": "USD",
                "total": "100.00"
            },
            "lines": [
                {
                    "description": "Test Item 1",
                    "quantity": "1",
                    "unit_price": "50.00",
                    "amount": "50.00"
                },
                {
                    "description": "Test Item 2",
                    "quantity": "2",
                    "unit_price": "25.00",
                    "amount": "50.00"
                }
            ],
            "metadata": {
                "invoice_id": "test-invoice-uuid",
                "processed_at": "2025-01-01T10:00:00Z"
            }
        }

    @pytest.mark.asyncio
    async def test_get_authorization_url(self, qb_service):
        """Test OAuth authorization URL generation."""
        with patch.object(qb_service.auth_client, 'get_authorization_url') as mock_auth_url:
            mock_auth_url.return_value = "https://appcenter.intuit.com/connect/oauth2?client_id=test"

            auth_url, state = await qb_service.get_authorization_url()

            assert auth_url is not None
            assert state is not None
            assert state in qb_service._oauth_state_cache
            mock_auth_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens(self, qb_service):
        """Test OAuth code exchange for tokens."""
        # Setup state cache
        state = "test-state"
        qb_service._oauth_state_cache[state] = {
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10)
        }

        with patch.object(qb_service.auth_client, 'get_bearer_access_token') as mock_token:
            qb_service.auth_client.access_token = "test-access-token"
            qb_service.auth_client.refresh_token = "test-refresh-token"
            qb_service.auth_client.expires_in = 3600
            mock_token.return_value = True

            result = await qb_service.exchange_code_for_tokens("test-code", state, "test-realm")

            assert result["access_token"] == "test-access-token"
            assert result["refresh_token"] == "test-refresh-token"
            assert result["realm_id"] == "test-realm"
            assert state not in qb_service._oauth_state_cache  # Should be cleaned up

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self, qb_service):
        """Test OAuth code exchange with invalid state."""
        with pytest.raises(QuickBooksServiceException, match="Invalid or expired state parameter"):
            await qb_service.exchange_code_for_tokens("test-code", "invalid-state", "test-realm")

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, qb_service):
        """Test access token refresh."""
        with patch.object(qb_service.auth_client, 'refresh_access_token') as mock_refresh:
            qb_service.auth_client.access_token = "new-access-token"
            qb_service.auth_client.refresh_token = "new-refresh-token"
            qb_service.auth_client.expires_in = 3600
            mock_refresh.return_value = True

            result = await qb_service.refresh_access_token("old-refresh-token", "test-realm")

            assert result["access_token"] == "new-access-token"
            assert result["refresh_token"] == "new-refresh-token"
            assert result["realm_id"] == "test-realm"

    @pytest.mark.asyncio
    async def test_get_user_info(self, qb_service):
        """Test getting user information."""
        with patch.object(qb_service.auth_client, 'get_user_info') as mock_user_info:
            mock_user_info.return_value = {"email": "test@example.com", "name": "Test User"}

            result = await qb_service.get_user_info("test-access-token")

            assert result["email"] == "test@example.com"
            assert result["name"] == "Test User"
            mock_user_info.assert_called_once_with("test-access-token")

    @pytest.mark.asyncio
    async def test_create_or_update_vendor_new(self, qb_service):
        """Test creating a new vendor."""
        vendor_data = {
            "DisplayName": "New Test Vendor",
            "CompanyName": "Test Company"
        }

        with patch('quickbooks.objects.vendor.Vendor.query') as mock_query, \
             patch('quickbooks.objects.vendor.Vendor') as mock_vendor_class:

            # Vendor doesn't exist
            mock_query.return_value = []

            # Mock vendor creation
            mock_vendor = Mock()
            mock_vendor.Id = "vendor-123"
            mock_vendor.DisplayName = "New Test Vendor"
            mock_vendor.save = AsyncMock()
            mock_vendor.to_dict.return_value = {
                "Id": "vendor-123",
                "DisplayName": "New Test Vendor"
            }
            mock_vendor_class.return_value = mock_vendor

            result = await qb_service.create_or_update_vendor(
                "test-access-token",
                "test-realm",
                vendor_data
            )

            assert result["Id"] == "vendor-123"
            assert result["DisplayName"] == "New Test Vendor"
            mock_vendor.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bill_success(self, qb_service, sample_invoice_data):
        """Test successful bill creation."""
        with patch('quickbooks.objects.bill.Bill') as mock_bill_class, \
             patch.object(qb_service, '_find_vendor_by_name') as mock_find_vendor, \
             patch.object(qb_service, '_get_default_expense_account') as mock_get_account:

            # Mock vendor
            mock_vendor = Mock()
            mock_vendor.Id = "vendor-123"
            mock_vendor.to_ref.return_value = {"value": "vendor-123"}
            mock_find_vendor.return_value = mock_vendor

            # Mock account
            mock_get_account.return_value = {"value": "account-456"}

            # Mock bill creation
            mock_bill = Mock()
            mock_bill.Id = "bill-789"
            mock_bill.TotalAmt = 100.0
            mock_bill.save = AsyncMock()
            mock_bill.to_dict.return_value = {
                "Id": "bill-789",
                "TotalAmt": 100.0
            }
            mock_bill_class.return_value = mock_bill

            result = await qb_service.create_bill(
                "test-access-token",
                "test-realm",
                sample_invoice_data,
                dry_run=False
            )

            assert result["Id"] == "bill-789"
            assert result["TotalAmt"] == 100.0
            mock_bill.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bill_dry_run(self, qb_service, sample_invoice_data):
        """Test bill creation in dry run mode."""
        with patch('quickbooks.objects.bill.Bill') as mock_bill_class, \
             patch.object(qb_service, '_find_vendor_by_name') as mock_find_vendor, \
             patch.object(qb_service, '_get_default_expense_account') as mock_get_account:

            # Mock vendor
            mock_vendor = Mock()
            mock_vendor.Id = "vendor-123"
            mock_vendor.to_ref.return_value = {"value": "vendor-123"}
            mock_find_vendor.return_value = mock_vendor

            # Mock account
            mock_get_account.return_value = {"value": "account-456"}

            # Mock bill (no save for dry run)
            mock_bill = Mock()
            mock_bill.TotalAmt = 100.0
            mock_bill.to_dict.return_value = {"TotalAmt": 100.0}
            mock_bill_class.return_value = mock_bill

            result = await qb_service.create_bill(
                "test-access-token",
                "test-realm",
                sample_invoice_data,
                dry_run=True
            )

            assert result["status"] == "validated"
            assert result["total_amount"] == 100.0
            # Should not call save for dry run
            mock_bill.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_bill_validation_error(self, qb_service, sample_invoice_data):
        """Test bill creation with validation error."""
        # Remove lines to trigger validation error
        invalid_data = sample_invoice_data.copy()
        invalid_data["lines"] = []

        with pytest.raises(ValidationException, match="Bill validation failed"):
            await qb_service.create_bill(
                "test-access-token",
                "test-realm",
                invalid_data,
                dry_run=False
            )

    @pytest.mark.asyncio
    async def test_export_multiple_bills_success(self, qb_service, sample_invoice_data):
        """Test successful batch export of multiple bills."""
        invoices = [sample_invoice_data, sample_invoice_data]

        with patch.object(qb_service, 'export_multiple_bills') as mock_batch_export:
            mock_batch_export.return_value = {
                "total": 2,
                "success": 2,
                "failed": 0,
                "errors": [],
                "created_bills": [
                    {"invoice_id": "inv1", "bill_id": "bill1"},
                    {"invoice_id": "inv2", "bill_id": "bill2"}
                ]
            }

            result = await qb_service.export_multiple_bills(
                "test-access-token",
                "test-realm",
                invoices,
                dry_run=False
            )

            assert result["total"] == 2
            assert result["success"] == 2
            assert result["failed"] == 0
            assert len(result["created_bills"]) == 2

    @pytest.mark.asyncio
    async def test_download_bill_pdf(self, qb_service):
        """Test downloading bill PDF."""
        with patch.object(qb_service, 'get_quickbooks_client') as mock_get_client:
            mock_client = Mock()
            mock_client.download_pdf.return_value = b"PDF content here"
            mock_get_client.return_value = mock_client

            result = await qb_service.download_bill_pdf(
                "test-access-token",
                "test-realm",
                "bill-123"
            )

            assert result == b"PDF content here"
            mock_client.download_pdf.assert_called_once_with("bill-123", "Bill")

    @pytest.mark.asyncio
    async def test_send_bill_email(self, qb_service):
        """Test sending bill via email."""
        with patch.object(qb_service, 'get_quickbooks_client') as mock_get_client, \
             patch('quickbooks.objects.bill.Bill.get') as mock_get_bill:

            mock_client = Mock()
            mock_get_client.return_value = mock_client

            mock_bill = Mock()
            mock_bill.send_email = AsyncMock(return_value=True)
            mock_get_bill.return_value = mock_bill

            result = await qb_service.send_bill_email(
                "test-access-token",
                "test-realm",
                "bill-123",
                "test@example.com"
            )

            assert result["status"] == "sent"
            assert result["bill_id"] == "bill-123"
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_handle_webhook(self, qb_service):
        """Test webhook handling."""
        webhook_data = {
            "eventNotifications": [
                {
                    "dataChangeEvent": {
                        "entities": [
                            {
                                "type": "Bill",
                                "id": "bill-123",
                                "operation": "Create"
                            }
                        ]
                    }
                }
            ]
        }

        result = await qb_service.handle_webhook(webhook_data)

        assert result["status"] == "success"
        assert len(result["processed_entities"]) == 1
        assert result["processed_entities"][0]["type"] == "Bill"
        assert result["processed_entities"][0]["operation"] == "Create"

    @pytest.mark.asyncio
    async def test_disconnect_app(self, qb_service):
        """Test app disconnection."""
        with patch.object(qb_service, 'get_quickbooks_client') as mock_get_client, \
             patch('quickbooks.services.disconnect.DisconnectService') as mock_disconnect_service:

            mock_client = Mock()
            mock_get_client.return_value = mock_client

            mock_service = Mock()
            mock_service.disconnect.return_value = True
            mock_disconnect_service.return_value = mock_service

            result = await qb_service.disconnect_app(
                "test-access-token",
                "test-realm"
            )

            assert result is True
            mock_service.disconnect.assert_called_once_with(mock_client)

    def test_format_date_valid(self, qb_service):
        """Test date formatting with valid inputs."""
        # Test various date formats
        assert qb_service._format_date("2025-01-01").day == 1
        assert qb_service._format_date("01/01/2025").day == 1
        assert qb_service._format_date("01/01/25").day == 1
        assert qb_service._format_date(None).day == datetime.now().day  # Returns today
        assert qb_service._format_date("").day == datetime.now().day  # Returns today

    def test_validate_bill_valid(self, qb_service):
        """Test bill validation with valid bill."""
        mock_bill = Mock()
        mock_bill.VendorRef = Mock()
        mock_bill.VendorRef.value = "vendor-123"
        mock_bill.Line = [
            Mock(Amount=100.0, Description="Test item")
        ]

        errors = qb_service._validate_bill(mock_bill)
        assert len(errors) == 0

    def test_validate_bill_missing_vendor(self, qb_service):
        """Test bill validation with missing vendor."""
        mock_bill = Mock()
        mock_bill.VendorRef = None
        mock_bill.Line = [Mock(Amount=100.0, Description="Test item")]

        errors = qb_service._validate_bill(mock_bill)
        assert len(errors) > 0
        assert any("Vendor reference is required" in error for error in errors)

    def test_validate_bill_missing_lines(self, qb_service):
        """Test bill validation with missing line items."""
        mock_bill = Mock()
        mock_bill.VendorRef = Mock()
        mock_bill.VendorRef.value = "vendor-123"
        mock_bill.Line = []

        errors = qb_service._validate_bill(mock_bill)
        assert len(errors) > 0
        assert any("line item is required" in error for error in errors)

    def test_validate_bill_invalid_line_amount(self, qb_service):
        """Test bill validation with invalid line amount."""
        mock_bill = Mock()
        mock_bill.VendorRef = Mock()
        mock_bill.VendorRef.value = "vendor-123"
        mock_bill.Line = [Mock(Amount=0, Description="Test item")]

        errors = qb_service._validate_bill(mock_bill)
        assert len(errors) > 0
        assert any("Amount is required and must be greater than 0" in error for error in errors)

    def test_generate_state(self, qb_service):
        """Test state parameter generation."""
        state1 = qb_service._generate_state()
        state2 = qb_service._generate_state()

        assert state1 != state2
        assert len(state1) > 20  # Should be sufficiently long

    def test_get_quickbooks_client(self, qb_service):
        """Test QuickBooks client creation."""
        with patch('quickbooks.QuickBooks') as mock_qb:
            mock_client = Mock()
            mock_qb.return_value = mock_client

            client = qb_service.get_quickbooks_client("test-token", "test-realm")

            mock_qb.assert_called_once_with(
                client_id=qb_service.client_id,
                client_secret=qb_service.client_secret,
                access_token="test-token",
                refresh_token=None,
                company_id="test-realm",
                environment=qb_service.environment,
                minorversion=63
            )
            assert client == mock_client