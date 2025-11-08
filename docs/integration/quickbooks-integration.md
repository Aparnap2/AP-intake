# QuickBooks Integration

This document provides comprehensive information about the QuickBooks Online integration in the AP Intake & Validation system.

## Overview

The QuickBooks integration allows seamless export of processed invoices from the AP Intake system to QuickBooks Online as bills. The integration uses OAuth 2.0 for secure authentication and provides both real-time and batch export capabilities.

## Features

- **OAuth 2.0 Authentication**: Secure authentication using Intuit's OAuth 2.0 flow
- **Invoice Export**: Export individual invoices or batches to QuickBooks as bills
- **Vendor Management**: Automatic vendor creation and updates
- **Account Mapping**: Support for custom expense account mapping
- **Webhook Support**: Real-time sync of QuickBooks data changes
- **Batch Operations**: Efficient bulk export using QuickBooks batch API
- **PDF Download**: Download bill PDFs directly from QuickBooks
- **Error Handling**: Comprehensive error handling and retry logic
- **Audit Trail**: Complete export history and audit logging

## Architecture

### Components

1. **QuickBooks Service** (`app/services/quickbooks_service.py`)
   - Core QuickBooks API integration
   - OAuth 2.0 flow management
   - Invoice data mapping and validation
   - Batch operations and webhook handling

2. **QuickBooks Models** (`app/models/quickbooks.py`)
   - Database models for connections, exports, webhooks
   - Vendor and account mapping tables
   - Export audit tracking

3. **QuickBooks Endpoints** (`app/api/api_v1/endpoints/quickbooks.py`)
   - REST API endpoints for QuickBooks operations
   - OAuth callback handling
   - Export management and monitoring

4. **QuickBooks Tasks** (`app/workers/quickbooks_tasks.py`)
   - Background Celery tasks for exports
   - Token refresh automation
   - Webhook processing

### Database Schema

The integration uses the following main tables:

- `quickbooks_connections`: OAuth connections and token storage
- `quickbooks_exports`: Export history and audit log
- `quickbooks_webhooks`: Webhook event tracking
- `quickbooks_vendor_mappings`: Local to QuickBooks vendor mapping
- `quickbooks_account_mappings`: Expense account mapping

## Setup and Configuration

### 1. QuickBooks App Configuration

1. Go to [Intuit Developer Portal](https://developer.intuit.com/)
2. Create a new app or use existing one
3. Configure OAuth 2.0 redirect URI: `http://localhost:8000/api/v1/quickbooks/callback`
4. Enable accounting scope and webhook subscriptions
5. Note down Client ID and Client Secret

### 2. Environment Configuration

Update your `.env` file with QuickBooks credentials:

```bash
# QuickBooks Configuration
QUICKBOOKS_SANDBOX_CLIENT_ID=your_client_id
QUICKBOOKS_SANDBOX_CLIENT_SECRET=your_client_secret
QUICKBOOKS_REDIRECT_URI=http://localhost:8000/api/v1/quickbooks/callback
QUICKBOOKS_ENVIRONMENT=sandbox  # or production
```

### 3. Database Migration

Run the database migration to create QuickBooks tables:

```bash
docker-compose exec api alembic upgrade head
```

### 4. Install Dependencies

The required dependencies are already included in `pyproject.toml`:

```python
"python-quickbooks==0.10.1",
"intuitlib==1.1.0",
"httpx==0.25.2",
```

## API Endpoints

### Authentication

#### Initiate OAuth Flow
```http
GET /api/v1/quickbooks/authorize?user_id={user_id}
```

#### OAuth Callback
```http
GET /api/v1/quickbooks/callback?code={code}&state={state}&realm_id={realm_id}
```

### Connection Management

#### List Connections
```http
GET /api/v1/quickbooks/connections?user_id={user_id}&status={status}
```

#### Disconnect
```http
DELETE /api/v1/quickbooks/disconnect/{connection_id}
```

### Export Operations

#### Export Single Invoice
```http
POST /api/v1/quickbooks/export/invoice/{invoice_id}?dry_run=false&user_id={user_id}
```

#### Batch Export
```http
POST /api/v1/quickbooks/export/batch
Content-Type: application/json

{
  "invoice_ids": ["uuid1", "uuid2", "uuid3"],
  "dry_run": false
}
```

### Export History

#### Get Export History
```http
GET /api/v1/quickbooks/exports?user_id={user_id}&status={status}&limit=50&offset=0
```

### Webhooks

#### Handle Webhook
```http
POST /api/v1/quickbooks/webhook
Content-Type: application/json

{
  "eventNotifications": [...]
}
```

## Usage Examples

### 1. Connect to QuickBooks

```python
import httpx

# Step 1: Get authorization URL
response = httpx.get(
    "http://localhost:8000/api/v1/quickbooks/authorize",
    params={"user_id": "user-uuid"}
)
data = response.json()
auth_url = data["data"]["authorization_url"]

# Step 2: User authorizes via QuickBooks (redirect to auth_url)
# Step 3: Handle callback (automatic redirect configured)
```

### 2. Export Invoice to QuickBooks

```python
import httpx

# Export single invoice
response = httpx.post(
    f"http://localhost:8000/api/v1/quickbooks/export/invoice/{invoice_id}",
    params={"dry_run": False, "user_id": "user-uuid"}
)
result = response.json()

if result["success"]:
    bill_id = result["data"]["bill_id"]
    print(f"Invoice exported as QuickBooks bill: {bill_id}")
```

### 3. Batch Export Multiple Invoices

```python
import httpx

# Batch export
response = httpx.post(
    "http://localhost:8000/api/v1/quickbooks/export/batch",
    params={"user_id": "user-uuid"},
    json={
        "invoice_ids": ["uuid1", "uuid2", "uuid3"],
        "dry_run": False
    }
)
result = response.json()

if result["success"]:
    export_result = result["data"]
    print(f"Exported {export_result['success']} invoices successfully")
    print(f"Failed: {export_result['failed']}")
```

## Data Mapping

### Invoice to Bill Mapping

| AP Intake Field | QuickBooks Field | Notes |
|-----------------|------------------|-------|
| `vendor_name` | `VendorRef` | Auto-creates vendor if doesn't exist |
| `invoice_no` | `PrivateNote` | Included in bill memo |
| `invoice_date` | `TxnDate` | Transaction date |
| `due_date` | `DueDate` | Payment due date |
| `lines[].description` | `Line[].Description` | Line item description |
| `lines[].amount` | `Line[].Amount` | Line item amount |
| `lines[].quantity` | `Line[].Qty` | Line item quantity |
| `lines[].unit_price` | `Line[].UnitPrice` | Line item unit price |

### Vendor Mapping

The system automatically:

1. Searches for existing vendors by display name
2. Creates new vendors if not found
3. Updates existing vendors with new information
4. Maintains mapping between local and QuickBooks vendor IDs

## Error Handling

### Common Errors

1. **Authentication Errors**
   - Token expired: Automatic refresh attempted
   - Invalid credentials: Re-authorization required
   - Scope insufficient: Check app permissions

2. **Validation Errors**
   - Missing vendor: Auto-created if possible
   - Invalid amounts: Must be greater than 0
   - Missing descriptions: Required for all line items

3. **API Errors**
   - Rate limiting: Automatic retry with exponential backoff
   - Service unavailable: Retry with exponential backoff
   - Data conflicts: Logged for manual resolution

### Retry Logic

- **Individual Exports**: 3 retries with 60s, 120s, 240s delays
- **Batch Exports**: 2 retries with 120s, 240s delays
- **Token Refresh**: Automated for expiring tokens
- **Webhook Processing**: Logged but not retried

## Monitoring and Logging

### Export Monitoring

Monitor exports via:

1. **API Endpoint**: `/api/v1/quickbooks/exports`
2. **Database**: `quickbooks_exports` table
3. **Logs**: Application logs with structured JSON format
4. **Celery**: Task monitoring via Flower or RabbitMQ

### Key Metrics

- Export success rate
- Average processing time
- Token refresh frequency
- Error rates by type
- Batch operation performance

### Log Examples

```json
{
  "timestamp": "2025-01-06T10:00:00Z",
  "level": "INFO",
  "message": "QuickBooks export completed successfully",
  "context": {
    "invoice_id": "uuid-123",
    "bill_id": "qb-456",
    "processing_time_ms": 1250,
    "user_id": "user-789"
  }
}
```

## Webhooks

### Configuration

1. Configure webhook URL in QuickBooks app: `https://your-domain.com/api/v1/quickbooks/webhook`
2. Set verifier token in your app configuration
3. Subscribe to relevant entity events (Bill, Vendor, etc.)

### Supported Events

- **Bill Create/Update/Delete**: Sync bill changes
- **Vendor Create/Update/Delete**: Sync vendor changes
- **Account Changes**: Update account mappings

### Webhook Processing

Webhooks are processed asynchronously via Celery tasks:

1. Signature verification (if configured)
2. Event parsing and validation
3. Entity-specific processing
4. Error handling and logging

## Security

### OAuth 2.0 Security

- State parameter for CSRF protection
- Secure token storage with encryption
- Automatic token refresh
- Scope-limited access

### Data Security

- All credentials stored securely in database
- Access tokens encrypted at rest
- HTTPS required for all OAuth communications
- Audit logging for all export operations

### Best Practices

1. Regularly rotate client secrets
2. Monitor for unusual export activity
3. Implement user access controls
4. Use principle of least privilege for scopes

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify client ID and secret
   - Check redirect URI configuration
   - Ensure app is properly configured in QuickBooks

2. **Export Failed**
   - Check invoice data completeness
   - Verify vendor information
   - Review error messages in logs

3. **Token Issues**
   - Check token expiration
   - Verify refresh token validity
   - Review OAuth scope permissions

4. **Performance Issues**
   - Use batch operations for multiple invoices
   - Monitor API rate limits
   - Check Celery worker performance

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("app.services.quickbooks_service").setLevel(logging.DEBUG)
```

### Support

For integration issues:

1. Check application logs
2. Review QuickBooks app configuration
3. Verify database connectivity
4. Test with sample data

## Development

### Running Tests

```bash
# Run QuickBooks tests
docker-compose exec api pytest tests/test_quickbooks_*.py -v

# Run integration tests
docker-compose exec api pytest tests/integration/test_quickbooks_integration.py -v
```

### Mock QuickBooks

For development without QuickBooks:

```python
# Use mock service for testing
from app.services.quickbooks_service import QuickBooksService
from unittest.mock import Mock

# Mock the QuickBooks client
mock_service = Mock(spec=QuickBooksService)
mock_service.create_bill.return_value = {"Id": "mock-bill-id"}
```

### Contributing

When contributing to the QuickBooks integration:

1. Add comprehensive tests
2. Update documentation
3. Handle edge cases
4. Follow existing patterns
5. Add proper error handling

## Version History

- **v1.0.0**: Initial QuickBooks integration
  - OAuth 2.0 authentication
  - Basic invoice export
  - Vendor management
  - Batch operations

## References

- [QuickBooks Online API Documentation](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities)
- [Python-QuickBooks Library](https://github.com/sidecars/python-quickbooks)
- [Intuit OAuth 2.0 Guide](https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/authentication-oauth2)