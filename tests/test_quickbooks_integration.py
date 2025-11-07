"""
Integration tests for QuickBooks API endpoints.

This module tests the full QuickBooks integration flow through the REST API.
"""

import json
import pytest
from datetime import datetime
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.models.quickbooks import QuickBooksConnection, QuickBooksConnectionStatus
from app.models.invoice import Invoice, InvoiceExtraction


class TestQuickBooksIntegration:
    """Integration tests for QuickBooks endpoints."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('app.db.session.get_db') as mock_db:
            mock_session = Mock()
            mock_db.return_value = mock_session
            yield mock_session

    @pytest.fixture
    def sample_connection(self):
        """Create a sample QuickBooks connection."""
        from uuid import uuid4
        connection = QuickBooksConnection(
            id=uuid4(),
            user_id=uuid4(),
            realm_id="test-realm-123",
            company_name="Test Company",
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            status=QuickBooksConnectionStatus.CONNECTED
        )
        return connection

    @pytest.fixture
    def sample_invoice(self):
        """Create a sample invoice."""
        from uuid import uuid4
        invoice = Invoice(
            id=uuid4(),
            vendor_id=uuid4(),
            filename="test.pdf"
        )
        return invoice

    @pytest.mark.asyncio
    async def test_authorize_endpoint(self, client, mock_db_session):
        """Test QuickBooks authorization endpoint."""
        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_authorization_url.return_value = (
                "https://appcenter.intuit.com/connect/oauth2?client_id=test",
                "test-state-123"
            )
            mock_service_class.return_value.__aenter__.return_value = mock_service

            response = await client.get("/api/v1/quickbooks/authorize?user_id=test-user-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "authorization_url" in data["data"]
            assert data["data"]["state"] == "test-state-123"

    @pytest.mark.asyncio
    async def test_authorize_existing_connection(self, client, mock_db_session, sample_connection):
        """Test authorization with existing connection."""
        from uuid import uuid4
        user_id = uuid4()
        sample_connection.user_id = user_id
        sample_connection.status = QuickBooksConnectionStatus.CONNECTED

        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_connection

        response = await client.get(f"/api/v1/quickbooks/authorize?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Already connected to QuickBooks" in data["message"]

    @pytest.mark.asyncio
    async def test_callback_success(self, client, mock_db_session):
        """Test successful OAuth callback."""
        from uuid import uuid4
        user_id = uuid4()
        realm_id = "test-realm-123"

        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class, \
             patch('app.core.config.settings') as mock_settings:

            mock_service = AsyncMock()
            mock_service.exchange_code_for_tokens.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "realm_id": realm_id
            }
            mock_service.get_user_info.return_value = {"email": "test@example.com"}
            mock_service.get_company_info.return_value = {"CompanyInfo": {"CompanyName": "Test"}}
            mock_service_class.return_value.__aenter__.return_value = mock_service

            mock_settings.UI_HOST = "http://localhost:3000"

            # Mock that no existing connection exists
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            response = await client.get(
                "/api/v1/quickbooks/callback",
                params={
                    "code": "test-auth-code",
                    "state": "test-state-123",
                    "realm_id": realm_id
                },
                follow_redirects=False
            )

            assert response.status_code == 302  # Redirect
            assert "localhost:3000" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_get_connections(self, client, mock_db_session, sample_connection):
        """Test getting QuickBooks connections."""
        from uuid import uuid4
        user_id = uuid4()
        sample_connection.user_id = user_id

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_connection]

        response = await client.get(f"/api/v1/quickbooks/connections?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["realm_id"] == sample_connection.realm_id
        assert data["data"][0]["status"] == sample_connection.status.value

    @pytest.mark.asyncio
    async def test_export_invoice_success(self, client, mock_db_session, sample_connection, sample_invoice):
        """Test successful invoice export."""
        from uuid import uuid4

        # Create sample extraction
        extraction = InvoiceExtraction(
            id=uuid4(),
            invoice_id=sample_invoice.id,
            header_json={"vendor_name": "Test Vendor", "invoice_no": "INV-001"},
            lines_json=[{"description": "Test Item", "amount": "100.00"}]
        )

        # Setup mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_connection,  # First call returns connection
            sample_invoice,      # Second call returns invoice
            extraction           # Third call returns extraction
        ]

        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class, \
             patch('app.models.quickbooks.QuickBooksExport') as mock_export_class:

            mock_service = AsyncMock()
            mock_service.create_bill.return_value = {
                "Id": "bill-123",
                "TotalAmt": 100.0
            }
            mock_service_class.return_value.__aenter__.return_value = mock_service

            mock_export = Mock()
            mock_export.id = uuid4()
            mock_export_class.return_value = mock_export

            response = await client.post(
                f"/api/v1/quickbooks/export/invoice/{sample_invoice.id}",
                params={"dry_run": False, "user_id": str(sample_connection.user_id)}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["bill_id"] == "bill-123"
            assert data["data"]["total_amount"] == 100.0

    @pytest.mark.asyncio
    async def test_export_invoice_no_connection(self, client, mock_db_session):
        """Test invoice export with no connection."""
        from uuid import uuid4
        invoice_id = uuid4()
        user_id = uuid4()

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        response = await client.post(
            f"/api/v1/quickbooks/export/invoice/{invoice_id}",
            params={"dry_run": False, "user_id": str(user_id)}
        )

        assert response.status_code == 404
        data = response.json()
        assert "No active QuickBooks connection found" in data["detail"]

    @pytest.mark.asyncio
    async def test_batch_export_success(self, client, mock_db_session, sample_connection):
        """Test successful batch export."""
        from uuid import uuid4
        user_id = uuid4()
        sample_connection.user_id = user_id

        # Setup connection mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_connection

        # Setup invoice/extraction mocks
        invoice_ids = [str(uuid4()), str(uuid4())]

        def mock_query_side_effect(*args, **kwargs):
            if hasattr(mock_query_side_effect, 'call_count'):
                mock_query_side_effect.call_count += 1
            else:
                mock_query_side_effect.call_count = 1

            # First call: get connection (already mocked above)
            if mock_query_side_effect.call_count == 1:
                return sample_connection

            # Subsequent calls: return invoices and extractions
            mock_invoice = Mock()
            mock_invoice.id = uuid4()
            mock_invoice.vendor_id = uuid4()
            mock_invoice.updated_at = datetime.now()

            mock_extraction = Mock()
            mock_extraction.header_json = {"vendor_name": "Test Vendor"}
            mock_extraction.lines_json = [{"description": "Test", "amount": "100"}]
            mock_extraction.created_at = datetime.now()

            # Return invoice then extraction for each invoice ID
            if mock_query_side_effect.call_count % 2 == 0:
                return mock_invoice
            else:
                return mock_extraction

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = mock_query_side_effect

        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.export_multiple_bills.return_value = {
                "total": 2,
                "success": 2,
                "failed": 0,
                "errors": [],
                "created_bills": [
                    {"invoice_id": invoice_ids[0], "bill_id": "bill-1"},
                    {"invoice_id": invoice_ids[1], "bill_id": "bill-2"}
                ]
            }
            mock_service_class.return_value.__aenter__.return_value = mock_service

            response = await client.post(
                "/api/v1/quickbooks/export/batch",
                params={"user_id": str(user_id)},
                json={
                    "invoice_ids": invoice_ids,
                    "dry_run": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["success"] == 2
            assert data["data"]["failed"] == 0
            assert len(data["data"]["created_bills"]) == 2

    @pytest.mark.asyncio
    async def test_webhook_handling(self, client):
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

        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.handle_webhook.return_value = {
                "status": "success",
                "processed_entities": [
                    {"type": "Bill", "id": "bill-123", "operation": "Create", "status": "processed"}
                ]
            }
            mock_service_class.return_value.__aenter__.return_value = mock_service

            response = await client.post(
                "/api/v1/quickbooks/webhook",
                json=webhook_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["status"] == "success"
            assert len(data["data"]["processed_entities"]) == 1

    @pytest.mark.asyncio
    async def test_disconnect_success(self, client, mock_db_session, sample_connection):
        """Test successful disconnection."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_connection

        with patch('app.services.quickbooks_service.QuickBooksService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.disconnect_app.return_value = True
            mock_service_class.return_value.__aenter__.return_value = mock_service

            response = await client.delete(f"/api/v1/quickbooks/disconnect/{sample_connection.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Successfully disconnected" in data["message"]

    @pytest.mark.asyncio
    async def test_get_export_history(self, client, mock_db_session, sample_connection):
        """Test getting export history."""
        from uuid import uuid4
        from app.models.quickbooks import QuickBooksExport

        export = QuickBooksExport(
            id=uuid4(),
            connection_id=sample_connection.id,
            invoice_id=uuid4(),
            quickbooks_bill_id="bill-123",
            export_type="bill",
            status="success"
        )

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [export]

        response = await client.get(
            "/api/v1/quickbooks/exports",
            params={"user_id": str(sample_connection.user_id), "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["quickbooks_bill_id"] == "bill-123"
        assert data["data"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_export_history_filtering(self, client, mock_db_session):
        """Test export history filtering."""
        from uuid import uuid4

        # Mock empty result
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        response = await client.get(
            "/api/v1/quickbooks/exports",
            params={
                "user_id": str(uuid4()),
                "status": "failed",
                "limit": 5,
                "offset": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self, client, mock_db_session):
        """Test error handling in endpoints."""
        from uuid import uuid4
        invoice_id = uuid4()
        user_id = uuid4()

        # Mock no connection found
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        response = await client.post(
            f"/api/v1/quickbooks/export/invoice/{invoice_id}",
            params={"dry_run": False, "user_id": str(user_id)}
        )

        assert response.status_code == 404
        data = response.json()
        assert "No active QuickBooks connection found" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalid_parameters(self, client, mock_db_session):
        """Test handling of invalid parameters."""
        # Test invalid UUID
        response = await client.post(
            "/api/v1/quickbooks/export/invoice/invalid-uuid",
            params={"dry_run": False, "user_id": "invalid-uuid"}
        )

        assert response.status_code == 422  # Validation error

        # Test invalid status filter
        response = await client.get(
            "/api/v1/quickbooks/exports",
            params={"status": "invalid-status"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid status" in data["detail"]