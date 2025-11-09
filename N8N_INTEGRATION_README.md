# n8n Integration for AP/AR System

## Overview

This document describes the comprehensive n8n integration service that has been implemented to provide workflow automation capabilities for the AP/AR system. The integration follows a Test-Driven Development (TDD) approach with comprehensive test coverage and robust error handling.

## 🚀 Features Implemented

### Core n8n Integration
- **n8n Client Service**: Complete API integration with authentication and error handling
- **Workflow Triggers**: Support for triggering various workflow types
- **Webhook Handlers**: Secure webhook event processing with signature validation
- **Template Management**: Create, update, activate, and manage workflow templates
- **Retry Logic**: Automatic retry with exponential backoff for failed operations
- **Security Features**: Webhook signature validation, data sanitization, and API key management

### Workflow Types Supported
1. **AP Invoice Processing**: Automated processing of accounts payable invoices
2. **AR Invoice Processing**: Automated processing of accounts receivable invoices
3. **Working Capital Analysis**: Daily financial analysis and projections
4. **Exception Handling**: Automated exception resolution and escalation
5. **Weekly Report Generation**: Automated financial and operational reports
6. **Customer Onboarding**: Streamlined customer setup workflows

## 📁 Files Created

### Core Service Files
- `app/services/n8n_service.py` - Main n8n integration service
- `app/schemas/n8n_schemas.py` - Pydantic schemas for data validation
- `app/api/api_v1/endpoints/n8n_webhooks.py` - FastAPI webhook endpoints

### Workflow Templates
- `templates/n8n_workflows/ap_invoice_processing.json` - AP invoice workflow
- `templates/n8n_workflows/working_capital_analysis.json` - Financial analysis workflow
- `templates/n8n_workflows/exception_handling.json` - Exception management workflow
- `templates/n8n_workflows/weekly_report_generation.json` - Report generation workflow

### Test Files
- `tests/unit/test_n8n_service.py` - Comprehensive test suite (TDD approach)
- `tests/unit/test_n8n_integration.py` - Integration tests
- `test_n8n_simple.py` - Simple validation test

### Configuration
- Updated `app/core/config.py` with n8n configuration options
- Updated `app/api/api_v1/api.py` to include n8n webhook endpoints
- Updated `pyproject.toml` with required dependencies

## ⚙️ Configuration

### Environment Variables
Add these to your `.env` file:

```bash
# n8n Integration Configuration
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_api_key
N8N_USERNAME=your_n8n_username  # Optional, for token auth
N8N_PASSWORD=your_n8n_password  # Optional, for token auth
N8N_WEBHOOK_SECRET=your_webhook_secret
N8N_TIMEOUT=30
N8N_MAX_RETRIES=3
N8N_RETRY_DELAY=1.0
N8N_ENCRYPTION_KEY=your_encryption_key  # Optional

# Workflow IDs
N8N_AP_WORKFLOW_ID=ap_invoice_processing
N8N_AR_WORKFLOW_ID=ar_invoice_processing
N8N_WORKING_CAPITAL_WORKFLOW_ID=working_capital_analysis
N8N_CUSTOMER_ONBOARDING_WORKFLOW_ID=customer_onboarding
N8N_EXCEPTION_HANDLING_WORKFLOW_ID=exception_handling
N8N_WEEKLY_REPORT_WORKFLOW_ID=weekly_report_generation
```

## 🔧 Usage Examples

### Basic Service Usage

```python
from app.services.n8n_service import N8nService

async def main():
    # Initialize n8n service
    async with N8nService() as n8n:
        # Test connection
        status = await n8n.test_connection()
        print(f"Connection status: {status}")

        # Trigger AP invoice processing
        invoice_data = {
            "invoice_id": "inv_123",
            "vendor_id": "vendor_456",
            "amount": 1250.00,
            "status": "processed"
        }

        result = await n8n.trigger_ap_invoice_processing(invoice_data)
        print(f"Workflow triggered: {result['execution_id']}")
```

### Webhook Handler Usage

```python
from app.services.n8n_service import N8nService
from app.schemas.n8n_schemas import N8nWebhookEvent

async def handle_webhook(webhook_data, signature):
    n8n = N8nService()

    # Create webhook event
    event = N8nWebhookEvent(
        workflow_id=webhook_data.get("workflowId"),
        execution_id=webhook_data.get("executionId"),
        status=webhook_data.get("status"),
        timestamp=datetime.utcnow(),
        data=webhook_data,
        signature=signature
    )

    # Process webhook
    result = await n8n.process_webhook_event(event)
    return result
```

### Workflow Template Management

```python
from app.schemas.n8n_schemas import N8nWorkflowTemplate

# Create new workflow template
template = N8nWorkflowTemplate(
    name="Custom AP Processing",
    description="Custom AP processing workflow",
    workflow_type="ap_processing",
    version="1.0.0",
    active=True
)

# Save to n8n
result = await n8n.create_workflow_template(template)

# Activate template
await n8n.activate_workflow_template(result["id"])
```

## 🔗 API Endpoints

### Webhook Endpoints

- `POST /api/v1/webhook/n8n/{webhook_path}` - Generic n8n webhook handler
- `POST /api/v1/webhook/n8n/ap-invoice` - AP invoice specific webhook
- `POST /api/v1/webhook/n8n/ar-invoice` - AR invoice specific webhook
- `POST /api/v1/webhook/n8n/working-capital` - Working capital webhook
- `POST /api/v1/webhook/n8n/exception-handling` - Exception handling webhook
- `POST /api/v1/webhook/n8n/weekly-report` - Weekly report webhook
- `GET /api/v1/webhook/n8n/status` - Webhook endpoint status
- `POST /api/v1/webhook/n8n/test` - Test webhook functionality

### Service Methods

The `N8nService` class provides the following main methods:

```python
# Connection and authentication
async def test_connection() -> Dict[str, Any]
async def authenticate() -> Dict[str, Any]

# Workflow execution
async def trigger_workflow(request: N8nWorkflowExecutionRequest) -> Dict[str, Any]
async def trigger_ap_invoice_processing(invoice_data: Dict) -> Dict[str, Any]
async def trigger_ar_invoice_processing(invoice_data: Dict) -> Dict[str, Any]
async def trigger_working_capital_analysis() -> Dict[str, Any]
async def trigger_exception_handling(exception_data: Dict) -> Dict[str, Any]
async def trigger_weekly_report_generation() -> Dict[str, Any]
async def trigger_customer_onboarding(customer_data: Dict) -> Dict[str, Any]

# Webhook processing
async def process_webhook_event(event: N8nWebhookEvent) -> Dict[str, Any]
def validate_webhook_signature(payload, signature, secret) -> bool

# Template management
async def create_workflow_template(template: N8nWorkflowTemplate) -> Dict[str, Any]
async def update_workflow_template(template: N8nWorkflowTemplate) -> Dict[str, Any]
async def list_workflow_templates(limit=100, offset=0) -> Dict[str, Any]
async def get_workflow_template(template_id: str) -> Dict[str, Any]
async def delete_workflow_template(template_id: str) -> Dict[str, Any]
async def activate_workflow_template(template_id: str) -> Dict[str, Any]
async def deactivate_workflow_template(template_id: str) -> Dict[str, Any]

# Metrics and monitoring
async def get_workflow_executions(workflow_id=None, status=None, limit=50, offset=0) -> Dict[str, Any]
async def get_workflow_metrics(days=7) -> N8nWorkflowMetrics
```

## 🧪 Testing

### Running Tests

```bash
# Run simple validation test
python3 test_n8n_simple.py

# Run comprehensive tests (when dependencies are resolved)
uv run pytest tests/unit/test_n8n_service.py -v

# Run integration tests
uv run pytest tests/unit/test_n8n_integration.py -v
```

### Test Coverage

The test suite covers:
- ✅ Service initialization and configuration
- ✅ Authentication and API key management
- ✅ Workflow execution triggers
- ✅ Webhook signature validation
- ✅ Data sanitization and security
- ✅ Error handling and retry logic
- ✅ Template management operations
- ✅ Integration with existing invoice processing workflow
- ✅ Performance metrics collection

## 🔒 Security Features

### Webhook Security
- **Signature Validation**: HMAC-SHA256 signature validation for all incoming webhooks
- **Request Sanitization**: Automatic removal of malicious content (XSS, SQL injection)
- **Error Sanitization**: Sensitive information removed from error messages

### API Security
- **API Key Management**: Secure storage and rotation of API keys
- **Token-based Authentication**: Support for bearer token authentication
- **Encryption**: Optional encryption of sensitive data using Fernet

### Data Protection
- **Input Validation**: Comprehensive validation using Pydantic schemas
- **Request/Response Logging**: Secure logging with sensitive data redaction
- **Timeout Protection**: Configurable timeouts to prevent resource exhaustion

## 📊 Monitoring and Observability

### Metrics Collection
- Workflow execution counts and success rates
- Average execution times and performance trends
- Error rates and common failure patterns
- API response times and availability

### Logging
- Structured logging with correlation IDs
- Request/response logging for debugging
- Security event logging for audit trails

### Health Checks
- Connection status monitoring
- Workflow template availability
- Service health endpoints

## 🚀 Deployment Considerations

### Dependencies
The n8n integration requires the following additional dependencies:
- `aiohttp>=3.8.0` - HTTP client for n8n API
- `backoff>=2.2.1` - Retry logic with exponential backoff
- `cryptography>=41.0.0` - Encryption and security features

### Configuration
- Ensure n8n instance is accessible from the AP/AR system
- Configure appropriate API keys and webhook secrets
- Set up firewall rules for n8n communication
- Configure monitoring and alerting for workflow failures

### Scaling
- Use connection pooling for HTTP requests
- Implement appropriate retry policies
- Consider caching for frequently accessed workflow templates
- Monitor resource usage and performance metrics

## 🔄 Integration Points

### Existing System Integration
- **Invoice Processing**: Connects with existing LangGraph invoice processing workflow
- **Exception Management**: Integrates with exception handling service for automated resolution
- **Metrics Service**: Provides workflow execution metrics to the monitoring system
- **Storage Service**: Uses existing storage service for file handling

### External Systems
- **n8n Platform**: Primary workflow automation platform
- **Email Systems**: For notifications and report distribution
- **ERP Systems**: For invoice export and data synchronization
- **Dashboard Systems**: For workflow monitoring and visualization

## 📚 Additional Resources

### Documentation
- [n8n Official Documentation](https://docs.n8n.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)

### Workflow Templates
The included workflow templates demonstrate:
- Best practices for n8n workflow design
- Integration patterns with external APIs
- Error handling and retry strategies
- Data transformation and validation

### Examples and Samples
- `test_n8n_simple.py` - Basic usage examples
- `tests/unit/test_n8n_service.py` - Comprehensive test examples
- Workflow templates in `templates/n8n_workflows/` - Real-world workflow examples

## 🎯 Next Steps

1. **Deploy n8n Instance**: Set up n8n platform for workflow execution
2. **Import Templates**: Import the provided workflow templates into n8n
3. **Configure Authentication**: Set up API keys and webhook secrets
4. **Test Integration**: Use the provided test scripts to validate functionality
5. **Monitor Performance**: Set up monitoring and alerting for workflow executions
6. **Scale Workflows**: Optimize workflows for production workloads

---

**Note**: This n8n integration has been implemented using Test-Driven Development (TDD) principles with comprehensive test coverage and follows industry best practices for security, performance, and reliability.