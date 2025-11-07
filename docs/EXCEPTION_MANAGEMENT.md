# Exception Management System

The AP Intake & Validation system includes a comprehensive Exception Management System that provides robust handling of validation failures, classification of exceptions, resolution workflows, and metrics reporting.

## Overview

The Exception Management System (Phase 1.3) is designed to handle all types of validation exceptions that occur during invoice processing, including:

- Mathematical discrepancies (subtotal/total mismatches)
- Duplicate invoice detection
- PO/GRN matching failures
- Vendor policy violations
- Data quality issues
- System errors

## Architecture

### Core Components

1. **Exception Service** (`app/services/exception_service.py`)
   - Main service for exception management
   - Integrates with validation service to automatically create exceptions
   - Provides classification, resolution, and metrics functionality

2. **Exception Schemas** (`app/api/schemas/exception.py`)
   - Comprehensive API schemas for exception management
   - Includes request/response models, filtering, and metrics

3. **Exception API Endpoints** (`app/api/api_v1/endpoints/exceptions.py`)
   - RESTful API endpoints for exception management
   - Supports listing, searching, resolving, and exporting exceptions

4. **Exception Handlers**
   - Specialized handlers for different exception categories
   - Provide category-specific validation and resolution logic

### Database Model

The `Exception` model in `app/models/invoice.py` stores:
- Exception details and reason codes
- Resolution tracking (who, when, how)
- Flexible JSON metadata for category-specific information
- Performance indexes for efficient querying

## Exception Categories

### 1. Math Exceptions
Handle mathematical discrepancies in invoices:
- **SUBTOTAL_MISMATCH**: Line items total doesn't match subtotal
- **TOTAL_MISMATCH**: Total amount doesn't match calculated total
- **LINE_MATH_MISMATCH**: Individual line math inconsistencies
- **INVALID_AMOUNT**: Invalid or malformed amounts

**Auto-resolution options:**
- `RECALCULATE`: Recalculate totals based on line items
- `MANUAL_ADJUST`: Manually adjust amounts with validation

### 2. Duplicate Exceptions
Handle duplicate invoice detection:
- **DUPLICATE_INVOICE**: Potential duplicate detected

**Auto-resolution options:**
- `MANUAL_REVIEW`: Review duplicates manually
- `REJECT_DUPLICATE`: Reject confirmed duplicates

### 3. Matching Exceptions
Handle PO/GRN matching failures:
- **PO_NOT_FOUND**: Purchase order not found
- **PO_MISMATCH**: PO details don't match invoice
- **PO_AMOUNT_MISMATCH`: Amount variance exceeds tolerance
- **PO_QUANTITY_MISMATCH`: Quantity variance exceeds tolerance
- **GRN_NOT_FOUND**: Goods receipt note not found
- **GRN_MISMATCH`: GRN details don't match

**Auto-resolution options:**
- `UPDATE_PO`: Update PO reference if incorrect
- `ACCEPT_VARIANCE`: Accept within tolerance limits
- `MANUAL_REVIEW`: Escalate for manual review

### 4. Vendor Policy Exceptions
Handle vendor policy violations:
- **INACTIVE_VENDOR**: Vendor not active in system
- **INVALID_CURRENCY`: Currency doesn't match vendor setup
- **INVALID_TAX_ID`: Tax ID doesn't match vendor records
- **SPEND_LIMIT_EXCEEDED`: Invoice exceeds vendor credit limit
- **PAYMENT_TERMS_VIOLATION`: Payment terms violate policy

**Auto-resolution options:**
- `ESCALATE`: Escalate to management
- `MANUAL_APPROVAL`: Require manual approval

### 5. Data Quality Exceptions
Handle data quality issues:
- **MISSING_REQUIRED_FIELD`: Required field missing or empty
- **INVALID_FIELD_FORMAT`: Field format is invalid
- **INVALID_DATA_STRUCTURE`: Data structure is malformed
- **NO_LINE_ITEMS`: No line items found

**Auto-resolution options:**
- `DATA_CORRECTION`: Auto-correct when possible
- `MANUAL_REVIEW`: Manual review required

### 6. System Exceptions
Handle system-level errors:
- **VALIDATION_ERROR`: Validation process failed
- **DATABASE_ERROR`: Database operation failed
- **EXTRACTION_ERROR`: Document extraction failed
- **STORAGE_ERROR`: File storage operation failed

**Auto-resolution options:**
- `SYSTEM_RETRY`: Retry the operation
- `ESCALATE`: Escalate to technical team

## API Endpoints

### Exception Management

#### List Exceptions
```http
GET /api/v1/exceptions/
```

**Query Parameters:**
- `invoice_id`: Filter by invoice ID
- `status`: Filter by status (open, resolved, etc.)
- `severity`: Filter by severity (error, warning, info)
- `category`: Filter by category (math, duplicate, etc.)
- `reason_code`: Filter by specific reason code
- `created_after`: Filter by creation date (after)
- `created_before`: Filter by creation date (before)
- `limit`: Number of results (default: 50, max: 1000)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "exceptions": [
    {
      "id": "uuid",
      "invoice_id": "uuid",
      "reason_code": "SUBTOTAL_MISMATCH",
      "category": "MATH",
      "severity": "ERROR",
      "status": "OPEN",
      "message": "Mathematical discrepancy detected",
      "details": {...},
      "auto_resolution_possible": true,
      "suggested_actions": ["MANUAL_ADJUST"],
      "created_at": "2025-01-06T12:00:00Z",
      "updated_at": "2025-01-06T12:00:00Z",
      "resolved_at": null,
      "resolved_by": null,
      "resolution_notes": null
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### Get Exception Details
```http
GET /api/v1/exceptions/{exception_id}
```

#### Resolve Exception
```http
POST /api/v1/exceptions/{exception_id}/resolve
```

**Request Body:**
```json
{
  "action": "MANUAL_ADJUST",
  "resolved_by": "accountant_user",
  "notes": "Adjusted subtotal to match line items",
  "resolution_data": {
    "adjustment_amount": 0.50
  },
  "auto_approve_invoice": false
}
```

#### Batch Resolve Exceptions
```http
POST /api/v1/exceptions/batch-resolve
```

**Request Body:**
```json
{
  "exception_ids": ["uuid1", "uuid2", "uuid3"],
  "action": "MANUAL_REVIEW",
  "resolved_by": "supervisor_user",
  "notes": "Bulk approval for similar issues",
  "resolution_data": {},
  "auto_approve_invoices": true
}
```

### Search and Discovery

#### Search Exceptions
```http
GET /api/v1/exceptions/search?query=subtotal
```

#### Export Exceptions
```http
GET /api/v1/exceptions/export?severity=ERROR&category=MATH
```

### Metrics and Dashboard

#### Get Exception Metrics
```http
GET /api/v1/exceptions/metrics/summary?days=30
```

**Response:**
```json
{
  "total_exceptions": 100,
  "resolved_exceptions": 80,
  "open_exceptions": 20,
  "resolution_rate": 80.0,
  "avg_resolution_hours": 4.5,
  "by_category": {"MATH": 40, "MATCHING": 30},
  "by_severity": {"ERROR": 60, "WARNING": 40},
  "top_reason_codes": {"SUBTOTAL_MISMATCH": 25},
  "period_days": 30,
  "generated_at": "2025-01-06T12:00:00Z"
}
```

#### Get Dashboard Data
```http
GET /api/v1/exceptions/dashboard
```

### Manual Exception Creation

#### Create Manual Exception
```http
POST /api/v1/exceptions/
```

**Request Body:**
```json
{
  "invoice_id": "uuid",
  "reason_code": "SUBTOTAL_MISMATCH",
  "category": "MATH",
  "severity": "ERROR",
  "message": "Manual math exception",
  "details": {"field": "subtotal"},
  "auto_resolution_possible": true,
  "suggested_actions": ["MANUAL_ADJUST"]
}
```

## Integration with Validation Service

The Exception Management System is automatically integrated with the Validation Service. When validation fails:

1. **Automatic Exception Creation**: Validation issues are automatically converted to exceptions
2. **Intelligent Classification**: Issues are grouped and classified by category
3. **Resolution Suggestions**: Auto-resolution options are provided based on exception type
4. **Notification**: High-priority exceptions trigger notifications

### Example Workflow

```python
# Validation fails with math errors
validation_result = await validation_service.validate_invoice(extraction_data)

# Exceptions are automatically created
if not validation_result.passed:
    # ExceptionService.create_exception_from_validation() is called
    # Exceptions are stored in database with appropriate classification
    # Notifications are sent for high-priority exceptions
```

## Exception Resolution Workflow

### 1. Exception Detection
- Validation fails during invoice processing
- Issues are grouped and classified
- Exceptions are created with suggested actions

### 2. Exception Assignment
- Auto-resolution attempted when possible
- Manual review queues created for exceptions requiring attention
- Notifications sent to appropriate personnel

### 3. Exception Resolution
- Users resolve exceptions through API or UI
- Resolution actions are validated against business rules
- Audit trail maintained for all resolution activities

### 4. Post-Resolution
- Invoice status updated to "ready" if auto-approved
- Resolution metrics captured for reporting
- Feedback loop improves future exception handling

## Database Performance

### Indexes
The exception table includes optimized indexes for:
- `idx_exception_invoice_status`: Invoice + resolution status
- `idx_exception_reason_created`: Reason code + creation date
- `idx_exception_resolved_by`: Resolver + resolution date
- `idx_exception_category`: JSON field for category filtering
- `idx_exception_severity`: JSON field for severity filtering
- `idx_exception_status`: JSON field for status filtering

### Constraints
- `reason_code` cannot be empty
- `details_json` must be present
- Foreign key relationships maintain data integrity

## Monitoring and Metrics

### Key Metrics
- **Resolution Rate**: Percentage of exceptions resolved
- **Average Resolution Time**: Mean time to resolve exceptions
- **Exception Trend**: Volume changes over time
- **Category Distribution**: Breakdown by exception type
- **Resolver Performance**: Individual resolution statistics

### Dashboards
- Exception summary with counts and trends
- Recent exceptions requiring attention
- Auto-resolution candidates
- Pending escalations

## Configuration

### Exception Thresholds
Configure in `app/core/config.py`:
- Exception notification thresholds
- Auto-approval limits
- Escalation rules
- Resolution time SLAs

### Notification Settings
Configure notification channels:
- Email notifications for high-severity exceptions
- Slack/Teams integration for team alerts
- Mobile push notifications for urgent issues

## Security and Auditing

### Access Control
- Role-based access to exception management
- Permission-based resolution actions
- Audit logging for all exception activities

### Data Privacy
- Exception data stored securely
- Access logging for compliance
- Data retention policies

## Testing

The exception management system includes comprehensive tests:

### Service Tests (`tests/test_exception_service.py`)
- Exception creation and classification
- Resolution workflows
- Metrics calculation
- Batch operations

### API Tests (`tests/test_exception_api.py`)
- Endpoint functionality
- Request/response validation
- Error handling
- Authentication/authorization

### Test Coverage
- Exception classification logic
- Resolution validation
- Database operations
- API contract compliance

## Future Enhancements

### Planned Features
- Machine learning for exception prediction
- Advanced auto-resolution capabilities
- Integration with external systems
- Custom workflow configurations
- Mobile app for exception management

### Scalability
- Distributed exception processing
- Real-time exception monitoring
- Advanced analytics and reporting
- Multi-tenant support

## Troubleshooting

### Common Issues

1. **Exceptions Not Created**
   - Check validation service integration
   - Verify database connectivity
   - Review exception service logs

2. **Resolution Actions Failing**
   - Validate user permissions
   - Check business rule configurations
   - Review exception handler logic

3. **Performance Issues**
   - Monitor database query performance
   - Check index usage
   - Review exception volume trends

### Debugging
- Enable debug logging in exception service
- Review database query performance
- Monitor API response times
- Check notification delivery status

## Support

For questions or issues with the Exception Management System:
- Review the API documentation at `/api/v1/docs`
- Check system logs for error details
- Contact the development team with specific error messages