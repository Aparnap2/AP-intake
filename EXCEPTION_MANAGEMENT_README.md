# Exception Management System

A comprehensive exception management system for the AP Intake platform that provides intelligent handling of invoice processing exceptions with real-time monitoring, batch operations, and analytics.

## Overview

The Exception Management System enables organizations to efficiently handle invoice processing exceptions that occur during automated extraction and validation. It provides tools for reviewing, resolving, and analyzing exceptions to improve processing accuracy and efficiency.

## Features

### 🎯 Core Exception Management
- **Smart Exception Detection**: Automatically identifies and categorizes exceptions during invoice processing
- **Comprehensive Taxonomy**: 17 different exception reason codes with detailed categorization
- **Severity-Based Prioritization**: Critical, High, Medium, and Low severity levels
- **Real-Time Status Tracking**: Live updates on exception resolution progress

### 📊 Exception Dashboard
- **Overview Statistics**: Total exceptions, open items, resolved today, average resolution time
- **Advanced Filtering**: Search by reason, status, severity, assignee, date range, confidence levels
- **Bulk Operations**: Select and resolve multiple exceptions simultaneously
- **Sortable Tables**: Sort by any column with customizable views

### 🔍 Exception Review Interface
- **Detailed Exception View**: Complete exception information with invoice context
- **PDF Preview**: Side-by-side document viewing with extracted data
- **Confidence Analysis**: Field-level confidence scores with visual indicators
- **Resolution Workflow**: Step-by-step guided exception resolution process
- **Field Editing**: Manual correction of extracted data with validation
- **Assignment Management**: Assign exceptions to team members with notifications

### 📦 Batch Resolution
- **Similar Exception Grouping**: Automatically groups similar exceptions for batch processing
- **Bulk Resolution Methods**: Multiple resolution strategies for batch operations
- **Progress Tracking**: Real-time progress monitoring for batch operations
- **Rollback Capabilities**: Undo/redo functionality for batch changes
- **Template-Based Resolutions**: Save and reuse resolution patterns

### 📈 Analytics & Insights
- **Performance Metrics**: Resolution times, team performance, exception trends
- **Visual Analytics**: Charts and graphs for exception patterns and trends
- **Top Performer Tracking**: Identify and recognize top performers
- **Exception Breakdown**: Detailed analysis by reason, severity, and time periods
- **AI-Powered Insights**: Automated recommendations for process improvements

### 🔄 Real-Time Features
- **Live Updates**: WebSocket integration for real-time status updates
- **Notifications**: Email and in-app notifications for exception assignments
- **Collaboration**: Multi-user support with real-time collaboration features
- **Presence Indicators**: See who's currently working on exceptions

## Architecture

### Frontend Components

#### Core Components
- **ExceptionDashboard**: Main dashboard with filtering, search, and bulk operations
- **ExceptionReview**: Detailed exception review interface with PDF preview
- **BatchResolution**: Bulk exception processing with similar exception grouping
- **ExceptionAnalytics**: Comprehensive analytics and reporting dashboard
- **ConfidenceMeter**: Visual confidence indicators with threshold comparison
- **ExceptionFilter**: Advanced filtering and search capabilities

#### Data Management
- **useExceptions**: Main exception data management hook
- **useExceptionAnalytics**: Analytics data management
- **useBatchOperations**: Batch operation management
- **useExceptionSuggestions**: AI-powered resolution suggestions

#### API Integration
- **exception-api**: Type-safe API client with comprehensive error handling
- **exception-types**: TypeScript interfaces and validation schemas

### Backend Components

#### API Endpoints
- **GET /api/v1/exceptions/**: List exceptions with comprehensive filtering
- **GET /api/v1/exceptions/{id}**: Get detailed exception information
- **PUT /api/v1/exceptions/{id}**: Update exception details
- **POST /api/v1/exceptions/{id}/resolve**: Resolve exception
- **POST /api/v1/exceptions/batch/resolve**: Batch resolution operations
- **GET /api/v1/exceptions/analytics/summary**: Exception analytics

#### Database Models
- **Exception**: Main exception record with resolution tracking
- **Invoice**: Related invoice information
- **InvoiceExtraction**: Extraction results with confidence scores
- **Validation**: Validation results and business rule checks

## Exception Types

### Exception Reason Codes

1. **low_confidence_extraction**: Document extraction confidence below threshold
2. **missing_required_fields**: Required fields are missing or invalid
3. **vendor_not_found**: Vendor not recognized in system
4. **amount_mismatch**: Amount validation failed or mismatch detected
5. **date_validation_failed**: Invoice or due date validation failed
6. **duplicate_invoice**: Duplicate invoice detected
7. **business_rule_violation**: Business rule validation failed
8. **document_quality_poor**: Document quality is too poor for processing
9. **currency_mismatch**: Currency validation failed
10. **tax_calculation_error**: Tax calculation validation failed
11. **invalid_invoice_format**: Invoice format is invalid or unsupported
12. **reference_data_mismatch**: Reference data mismatch detected
13. **payment_terms_invalid**: Payment terms validation failed
14. **po_number_mismatch**: Purchase order number validation failed
15. **accounting_period_closed**: Accounting period is closed
16. **approval_required**: Manual approval required
17. **custom_validation_failed**: Custom validation rule failed

### Severity Levels
- **Critical**: Requires immediate attention (e.g., payment issues, compliance violations)
- **High**: Important but not urgent (e.g., vendor not found, amount mismatches)
- **Medium**: Standard processing exceptions (e.g., low confidence, missing fields)
- **Low**: Minor issues that can be addressed during regular processing

### Resolution Methods
- **manual_correction**: Manually correct the extracted data
- **vendor_contact**: Reach out to vendor for clarification
- **system_reprocess**: Run document through extraction again
- **exception_overridden**: Override validation and approve
- **data_enrichment**: Add missing data from external sources
- **business_rule_adjusted**: Modify validation rules

## Getting Started

### Prerequisites
- Node.js 18+ for frontend development
- Python 3.9+ for backend development
- PostgreSQL database
- Redis for caching (optional)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ap_intake
```

2. **Install frontend dependencies**
```bash
cd web
npm install
```

3. **Install backend dependencies**
```bash
cd ..
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run database migrations**
```bash
alembic upgrade head
```

6. **Start the development servers**
```bash
# Backend (in root directory)
uvicorn app.main:app --reload

# Frontend (in web directory)
npm run dev
```

### Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Usage

### Basic Exception Review
1. Navigate to the Exception Dashboard
2. Use filters to find exceptions requiring attention
3. Click on an exception to open the review interface
4. Review the exception details and confidence scores
5. Choose a resolution method and add notes
6. Resolve the exception or assign to another team member

### Batch Operations
1. Select multiple exceptions using checkboxes
2. Click "Batch Resolve" to open batch resolution interface
3. Review grouped similar exceptions
4. Choose resolution method and settings
5. Process batch and monitor progress

### Analytics and Reporting
1. Go to the Analytics tab
2. Select time range and metrics to view
3. Analyze trends and patterns
4. Export reports for further analysis

## Configuration

### Exception Thresholds
Configure confidence thresholds and processing rules in the backend configuration:

```python
# app/core/config.py
DOCLING_CONFIDENCE_THRESHOLD = 0.8  # Minimum confidence for auto-processing
EXCEPTION_AUTO_ASSIGNMENT = True     # Enable automatic assignment
BATCH_PROCESSING_LIMIT = 100         # Maximum exceptions per batch
```

### Notification Settings
Configure email and notification preferences:

```python
# app/core/config.py
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
NOTIFICATION_EMAIL_ENABLED = True
EXCEPTION_ASSIGNMENT_NOTIFICATIONS = True
```

## API Reference

### Exception Endpoints

#### List Exceptions
```http
GET /api/v1/exceptions?skip=0&limit=50&status=open&severity=high
```

**Query Parameters:**
- `skip`: Number of records to skip (pagination)
- `limit`: Maximum number of records to return
- `search`: Text search query
- `status`: Filter by status (open, in_progress, resolved, etc.)
- `severity`: Filter by severity (low, medium, high, critical)
- `reason_code`: Filter by exception reason
- `assigned_to`: Filter by assignee
- `date_start`: Filter by creation date (start)
- `date_end`: Filter by creation date (end)
- `confidence_min`: Minimum confidence score
- `confidence_max`: Maximum confidence score

#### Get Exception Details
```http
GET /api/v1/exceptions/{exception_id}
```

#### Update Exception
```http
PUT /api/v1/exceptions/{exception_id}
Content-Type: application/json

{
  "status": "resolved",
  "resolution_method": "manual_correction",
  "resolution_notes": "Corrected vendor name and amount",
  "assigned_to": "john.doe"
}
```

#### Batch Resolution
```http
POST /api/v1/exceptions/batch/resolve
Content-Type: application/json

{
  "exception_ids": ["uuid1", "uuid2", "uuid3"],
  "resolution_method": "manual_correction",
  "resolution_notes": "Batch correction of similar issues",
  "assign_to": "jane.smith",
  "tags": ["q3_review", "vendor_issues"]
}
```

#### Get Analytics
```http
GET /api/v1/exceptions/analytics/summary?start=2024-01-01&end=2024-01-31
```

## Performance Considerations

### Database Optimization
- Indexes on frequently queried fields (status, severity, created_at)
- Partitioning for large exception tables
- Regular cleanup of resolved exceptions

### Caching Strategy
- Redis caching for exception analytics
- Frontend state management for dashboard performance
- API response caching for frequently accessed data

### Background Processing
- Celery tasks for batch operations
- Asynchronous exception processing
- Queue management for high-volume periods

## Security

### Authentication & Authorization
- JWT-based authentication
- Role-based access control
- Exception-level permissions

### Data Protection
- Encrypted storage of sensitive invoice data
- Audit logging for all exception modifications
- GDPR compliance for personal data handling

## Troubleshooting

### Common Issues

1. **Exceptions not appearing in dashboard**
   - Check database connection and table indexes
   - Verify API authentication
   - Review browser console for JavaScript errors

2. **Slow dashboard performance**
   - Check database query performance
   - Review pagination settings
   - Consider caching strategies

3. **Batch operations failing**
   - Check background task queue status
   - Review Celery worker logs
   - Verify exception ID formats

### Logs and Monitoring
- Application logs: `logs/exception_management.log`
- Performance metrics: `/metrics` endpoint
- Error tracking: Sentry integration (if configured)

## Contributing

### Development Guidelines
1. Follow TypeScript best practices
2. Use semantic versioning for releases
3. Write comprehensive tests for new features
4. Update documentation for API changes

### Testing
```bash
# Frontend tests
cd web
npm test

# Backend tests
pytest tests/test_exceptions.py
```

## Support

For support and questions:
- Create an issue in the project repository
- Check the API documentation at `/docs`
- Review the troubleshooting guide above

## Roadmap

### Upcoming Features
- **Machine Learning Integration**: Improved exception prediction and auto-resolution
- **Mobile App**: Native mobile application for exception management
- **Advanced Analytics**: Predictive analytics and exception forecasting
- **Integration Hub**: Connect with external ERP and accounting systems
- **Workflow Automation**: Custom workflow builder for exception handling

### Enhancement Areas
- Performance optimizations for high-volume processing
- Enhanced collaboration features
- Additional notification channels (Slack, Teams)
- Custom exception types and workflows
- Advanced reporting and export capabilities