# Email Integration for AP Intake System

This document describes the email integration functionality for automatically ingesting PDF invoices from Gmail.

## Overview

The email integration system provides:

- **Gmail API Integration**: OAuth 2.0 authentication and email retrieval
- **PDF Attachment Extraction**: Automatic detection and download of PDF invoices
- **Security Validation**: Comprehensive security checks and spam filtering
- **Deduplication**: Email and file deduplication to prevent processing duplicates
- **Background Processing**: Async workers for continuous email monitoring
- **Auto-Invoicing**: Direct integration with the existing invoice processing workflow

## Architecture

### Core Components

1. **GmailService** (`app/services/gmail_service.py`)
   - OAuth 2.0 authentication flow
   - Gmail API interactions
   - Email and attachment retrieval

2. **EmailIngestionService** (`app/services/email_ingestion_service.py`)
   - Unified email processing across providers
   - Security validation and filtering
   - Integration with storage and workflow services

3. **Background Workers** (`app/workers/email_tasks.py`)
   - Continuous email monitoring
   - Batch processing capabilities
   - Task management and scheduling

4. **Database Models** (`app/models/email.py`)
   - Email and attachment tracking
   - Processing logs and statistics
   - User credentials and configurations

## Configuration

### Environment Variables

```bash
# Gmail API Configuration
GMAIL_CLIENT_ID=your-gmail-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-gmail-client-secret

# Email Ingestion Settings
EMAIL_INGESTION_ENABLED=true
EMAIL_MONITORING_INTERVAL_MINUTES=60
EMAIL_MAX_PROCESSING_DAYS=7
EMAIL_SECURITY_VALIDATION_ENABLED=true
EMAIL_AUTO_PROCESS_INVOICES=true
```

### OAuth 2.0 Setup

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Gmail API

2. **Create OAuth 2.0 Credentials**
   - Go to APIs & Services → Credentials
   - Create OAuth 2.0 Client ID
   - Add authorized redirect URIs (e.g., `http://localhost:8000/emails/callback`)
   - Copy Client ID and Client Secret

3. **Configure Application**
   - Add credentials to environment variables
   - Update redirect URIs in application configuration

## API Endpoints

### Authentication

#### Get Authorization URL
```http
POST /api/v1/emails/authorize/gmail
Content-Type: application/json

{
  "redirect_uri": "http://localhost:8000/callback",
  "state": "optional_state_parameter"
}
```

#### Store Credentials
```http
POST /api/v1/emails/credentials/gmail
Content-Type: application/json

{
  "user_id": "user-uuid",
  "authorization_code": "code_from_oauth_callback",
  "redirect_uri": "http://localhost:8000/callback"
}
```

### Email Processing

#### Manual Ingestion
```http
POST /api/v1/emails/ingest/gmail
Content-Type: application/json

{
  "credentials_id": "credentials-uuid",
  "days_back": 7,
  "max_emails": 50,
  "auto_process": true
}
```

#### Create Monitoring Configuration
```http
POST /api/v1/emails/monitoring/config
Content-Type: application/json

{
  "user_id": "user-uuid",
  "credentials_id": "credentials-uuid",
  "is_active": true,
  "monitoring_interval_minutes": 60,
  "days_back_to_process": 7,
  "max_emails_per_run": 50,
  "auto_process_invoices": true,
  "security_validation_enabled": true
}
```

#### Search Processed Emails
```http
GET /api/v1/emails/search?user_id=user-uuid&query=invoice&limit=20&offset=0
```

#### Get Statistics
```http
GET /api/v1/emails/statistics/user-uuid?days=30
```

### Monitoring

#### Get Monitoring Status
```http
GET /api/v1/emails/monitoring/status/user-uuid
```

#### Stop Monitoring
```http
DELETE /api/v1/emails/monitoring/user-uuid
```

#### Get Active Tasks
```http
GET /api/v1/emails/tasks/active
```

#### Health Check
```http
GET /api/v1/emails/health
```

## Security Features

### Email Validation

1. **Malicious Pattern Detection**
   - Urgency/phishing keywords
   - Suspicious URLs
   - HTML injection attempts

2. **Sender Verification**
   - Trusted domain validation
   - Excessive attachment detection
   - Reputation-based filtering

3. **Content Security**
   - PDF structure validation
   - File size limits
   - Malware scanning integration points

### Rate Limiting

- Gmail API quota management
- Exponential backoff on errors
- Request throttling to prevent API abuse

### Data Protection

- OAuth token encryption (production)
- Secure credential storage
- Access control and auditing

## Background Processing

### Celery Tasks

1. **monitor_gmail_inbox**
   - Continuous email monitoring
   - Configurable intervals and filters
   - Automatic invoice processing

2. **process_email_attachment**
   - Individual attachment processing
   - Integration with invoice workflow
   - Error handling and retries

3. **schedule_email_monitoring**
   - Periodic task scheduling
   - User-specific monitoring configs
   - Task lifecycle management

### Task Management

```python
from app.workers.email_tasks import (
    monitor_gmail_inbox,
    schedule_email_monitoring,
    get_email_monitoring_task_status,
    cancel_email_monitoring
)

# Start monitoring
task = monitor_gmail_inbox.delay(
    user_id="user-uuid",
    credentials_data=credentials_dict,
    days_back=7,
    max_emails=50
)

# Schedule recurring monitoring
schedule_task = schedule_email_monitoring.delay(
    user_id="user-uuid",
    credentials_data=credentials_dict,
    schedule_minutes=60
)

# Check status
status = get_email_monitoring_task_status("user-uuid")

# Cancel monitoring
cancelled = cancel_email_monitoring("user-uuid")
```

## Database Schema

### Email Tables

1. **emails**
   - Email metadata and content
   - Processing status and security flags
   - User and provider information

2. **email_attachments**
   - Attachment metadata and storage info
   - Processing results and confidence scores
   - Security scan results

3. **email_processing_logs**
   - Detailed processing logs
   - Step-by-step execution tracking
   - Error handling and retry information

4. **email_credentials**
   - Encrypted OAuth credentials
   - Token management and refresh
   - Usage quotas and limits

5. **email_monitoring_configs**
   - User monitoring preferences
   - Filter rules and schedules
   - Statistics and performance metrics

## Usage Examples

### Basic Email Ingestion

```python
from app.services.gmail_service import GmailService, GmailCredentials
from app.services.email_ingestion_service import EmailIngestionService

# Initialize services
gmail_service = GmailService()
ingestion_service = EmailIngestionService()

# Get authorization URL
auth_url, state = await gmail_service.get_authorization_url(
    redirect_uri="http://localhost:8000/callback"
)

# After user authorization, exchange code for credentials
credentials = await gmail_service.exchange_code_for_credentials(
    authorization_code="auth_code_from_callback",
    redirect_uri="http://localhost:8000/callback"
)

# Build Gmail service
await gmail_service.build_service(credentials)

# Ingest emails
records = await ingestion_service.ingest_from_gmail(
    credentials=credentials,
    days_back=7,
    max_emails=50,
    auto_process=True
)

print(f"Processed {len(records)} emails")
```

### Background Monitoring Setup

```python
from app.workers.email_tasks import schedule_email_monitoring
from app.services.gmail_service import GmailCredentials

# Schedule continuous monitoring
task = schedule_email_monitoring.delay(
    user_id="user-uuid",
    credentials_data={
        "token": "access_token",
        "refresh_token": "refresh_token",
        "client_id": "gmail_client_id",
        "client_secret": "gmail_client_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
    },
    schedule_minutes=60
)

print(f"Monitoring task scheduled: {task.id}")
```

## Troubleshooting

### Common Issues

1. **OAuth Authentication Errors**
   - Check redirect URI configuration
   - Verify client ID and secret
   - Ensure Gmail API is enabled

2. **Rate Limiting**
   - Monitor Gmail API quotas
   - Implement proper backoff strategies
   - Consider user quota management

3. **Attachment Processing Errors**
   - Validate PDF structure
   - Check storage service availability
   - Review security scan results

4. **Background Task Failures**
   - Check Celery worker logs
   - Verify Redis/RabbitMQ connectivity
   - Review task configuration

### Monitoring and Logs

```bash
# Check Celery worker logs
docker-compose logs -f worker

# Check API logs
docker-compose logs -f api

# Monitor email processing
curl http://localhost:8000/api/v1/emails/health
```

## Development

### Running Tests

```bash
# Run email integration tests
pytest tests/test_email_integration.py -v

# Run with coverage
pytest tests/test_email_integration.py --cov=app.services.email_ingestion_service
```

### Local Development

1. **Setup Gmail API Credentials**
   - Create local `.env` file with Gmail credentials
   - Configure OAuth redirect URI for local development

2. **Start Services**
   ```bash
   docker-compose up -d api worker redis
   ```

3. **Test OAuth Flow**
   - Visit `/api/v1/emails/authorize/gmail` endpoint
   - Complete OAuth flow in browser
   - Store returned credentials

## Future Enhancements

1. **Microsoft Graph API Support**
   - Outlook/Office 365 integration
   - Unified email provider interface

2. **Advanced Security**
   - Machine learning spam detection
   - Advanced malware scanning
   - Behavioral analysis

3. **Enhanced Filtering**
   - Custom rule engine
   - AI-powered email categorization
   - Smart vendor detection

4. **Performance Optimization**
   - Parallel email processing
   - Caching strategies
   - Database optimization

## Support

For issues and questions:

1. Check application logs for error details
2. Review API documentation at `/docs` endpoint
3. Monitor system health at `/api/v1/emails/health`
4. Consult troubleshooting section above

## Security Considerations

- OAuth credentials should be encrypted in production
- Implement proper access control for email endpoints
- Monitor for unusual email processing patterns
- Regular security audits of email processing logic
- Consider implementing additional email validation rules