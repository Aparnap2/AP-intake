# Export Service Documentation

## Overview

The Export Service provides comprehensive functionality for exporting invoice data from the AP Intake system in various formats. It supports configurable templates, batch processing, multiple destinations, and comprehensive audit logging.

## Features

### Core Features
- **Multiple Export Formats**: CSV, JSON (with extensibility for XML, Excel, PDF)
- **Configurable Templates**: Field mapping, transformation, and validation rules
- **Batch Processing**: Handle large datasets with progress tracking
- **Multiple Destinations**: Download, file storage, API endpoints, email
- **Background Processing**: Celery-based async processing with retry logic
- **Audit Logging**: Complete export activity tracking
- **Performance Metrics**: Processing time, file size, throughput metrics
- **Compression & Encryption**: Optional file compression and encryption

### Advanced Features
- **Field Transformation**: Built-in functions for formatting data
- **Validation Rules**: Comprehensive data validation before export
- **Template Management**: Create, update, version export templates
- **Export Scheduling**: Automated recurring exports
- **Error Handling**: Robust error recovery and retry mechanisms
- **User Permissions**: Role-based access control for exports

## Architecture

### Components

1. **ExportService** (`app/services/export_service.py`)
   - Core export processing logic
   - Template-based export generation
   - Destination handling

2. **Export Models** (`app/models/export_models.py`)
   - Database models for templates, jobs, metrics
   - Export status and audit tracking

3. **Export Schemas** (`app/schemas/export_schemas.py`)
   - Pydantic models for API validation
   - Request/response schemas

4. **Export API** (`app/api/api_v1/endpoints/exports.py`)
   - RESTful API endpoints
   - Template and job management

5. **Export Tasks** (`app/workers/export_tasks.py`)
   - Celery background tasks
   - Scheduled processing and cleanup

### Data Flow

```
User Request → API Endpoint → Export Service → Background Task → File Generation → Destination → Notification
     ↓              ↓                ↓               ↓              ↓            ↓              ↓
  Templates → Validation → Queue → Processing → Storage/Download → Metrics → Audit Log
```

## API Reference

### Template Management

#### Create Export Template
```http
POST /api/v1/exports/templates
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Standard CSV Export",
  "description": "Standard CSV with basic invoice fields",
  "format": "csv",
  "field_mappings": [
    {
      "source_field": "header.vendor_name",
      "target_field": "Vendor Name",
      "field_type": "string",
      "required": true
    },
    {
      "source_field": "header.total",
      "target_field": "Total Amount",
      "field_type": "decimal",
      "required": true,
      "transform_function": "currency_format"
    }
  ],
  "header_config": {
    "title": "Invoice Export Report",
    "date": true
  },
  "compression": false,
  "encryption": false
}
```

#### List Export Templates
```http
GET /api/v1/exports/templates?format=csv&is_active=true&limit=10&offset=0
```

#### Get Export Template
```http
GET /api/v1/exports/templates/{template_id}
```

#### Update Export Template
```http
PUT /api/v1/exports/templates/{template_id}
Content-Type: application/json

{
  "name": "Updated Template Name",
  "field_mappings": [...]
}
```

#### Delete Export Template
```http
DELETE /api/v1/exports/templates/{template_id}
```

### Export Job Management

#### Create Export Job
```http
POST /api/v1/exports/jobs
Content-Type: application/json

{
  "invoice_ids": ["uuid1", "uuid2"],
  "filters": {
    "vendor_ids": ["uuid1", "uuid2"],
    "status": ["validated"],
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
    "has_exceptions": false
  },
  "export_config": {
    "template_id": "template-uuid",
    "destination": "download",
    "destination_config": {
      "description": "Monthly invoice export"
    },
    "batch_size": 1000,
    "notify_on_completion": true,
    "notification_config": {
      "email": "user@example.com"
    }
  },
  "priority": 5,
  "scheduled_at": "2024-02-01T00:00:00Z"
}
```

#### List Export Jobs
```http
GET /api/v1/exports/jobs?status=completed&format=csv&limit=10&offset=0
```

#### Get Export Job
```http
GET /api/v1/exports/jobs/{job_id}
```

#### Get Export Progress
```http
GET /api/v1/exports/jobs/{job_id}/progress
```

#### Cancel Export Job
```http
POST /api/v1/exports/jobs/{job_id}/cancel
```

#### Download Export File
```http
GET /api/v1/exports/jobs/{job_id}/download
```

#### Get Export Metrics
```http
GET /api/v1/exports/jobs/{job_id}/metrics
```

### Batch Operations

#### Create Batch Export
```http
POST /api/v1/exports/jobs/batch
Content-Type: application/json

{
  "export_requests": [
    {
      "export_config": {
        "template_id": "template-uuid",
        "destination": "download",
        "destination_config": {}
      }
    }
  ],
  "priority": 5,
  "max_parallel_jobs": 3
}
```

## Configuration

### Field Mapping Types

- **string**: Text fields
- **number**: Numeric fields
- **decimal**: Decimal/currency fields
- **date**: Date fields
- **boolean**: Boolean fields
- **json**: Complex JSON fields

### Transformation Functions

- **uppercase**: Convert to uppercase
- **lowercase**: Convert to lowercase
- **title_case**: Title case formatting
- **currency_format**: Format as currency ($1,234.56)
- **percentage**: Format as percentage (45.2%)
- **date_format**: Format dates with custom pattern
- **phone_format**: Format phone numbers

### Validation Rules

- **required**: Field must be present and non-empty
- **min_length**: Minimum string length
- **max_length**: Maximum string length
- **pattern**: Regex pattern matching
- **in_list**: Value must be in allowed list
- **numeric_range**: Value within numeric range
- **date_range**: Date within date range

### Export Destinations

#### Download
```json
{
  "destination": "download"
}
```

#### File Storage
```json
{
  "destination": "file_storage",
  "config": {
    "path": "exports/2024/01",
    "filename": "invoices_{date}.{format}"
  }
}
```

#### API Endpoint
```json
{
  "destination": "api_endpoint",
  "config": {
    "url": "https://api.example.com/imports",
    "auth_method": "bearer",
    "token": "access-token",
    "headers": {
      "Content-Type": "application/json"
    }
  }
}
```

#### Email
```json
{
  "destination": "email",
  "config": {
    "recipients": ["user@example.com"],
    "subject": "Invoice Export - {date}",
    "body": "Please find attached invoice export"
  }
}
```

## Default Templates

### Standard CSV Export
- **Purpose**: Basic invoice data export
- **Fields**: Invoice ID, Vendor Name, Invoice Number, Date, Amount, Status
- **Format**: CSV with headers and summary footer

### Detailed JSON Export
- **Purpose**: Complete invoice data export
- **Fields**: All invoice data including headers, line items, metadata
- **Format**: JSON with full data structure

### Accounting CSV Export
- **Purpose**: Accounting system integration
- **Fields**: Financial focus - amounts, dates, vendors
- **Format**: CSV optimized for accounting imports

### QuickBooks Export
- **Purpose**: QuickBooks integration
- **Fields**: QuickBooks-compatible format
- **Format**: JSON with QuickBooks API structure

## Usage Examples

### Basic CSV Export
```python
import requests

# Create template
template_data = {
    "name": "My CSV Export",
    "format": "csv",
    "field_mappings": [
        {
            "source_field": "header.vendor_name",
            "target_field": "Vendor",
            "field_type": "string",
            "required": True
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/exports/templates",
    json=template_data,
    headers={"Authorization": "Bearer <token>"}
)

template_id = response.json()["id"]

# Create export job
job_data = {
    "export_config": {
        "template_id": template_id,
        "destination": "download",
        "destination_config": {}
    }
}

response = requests.post(
    "http://localhost:8000/api/v1/exports/jobs",
    json=job_data,
    headers={"Authorization": "Bearer <token>"}
)

job_id = response.json()["export_id"]

# Check progress
response = requests.get(
    f"http://localhost:8000/api/v1/exports/jobs/{job_id}/progress",
    headers={"Authorization": "Bearer <token>"}
)

progress = response.json()
print(f"Status: {progress['status']}, Progress: {progress['progress_percentage']}%")
```

### Batch Export with Filters
```python
# Create batch export for specific date range
batch_data = {
    "export_requests": [
        {
            "filters": {
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "status": ["validated"]
            },
            "export_config": {
                "template_id": "csv-template-id",
                "destination": "file_storage",
                "destination_config": {
                    "path": "monthly-exports",
                    "filename": "january_invoices.csv"
                }
            }
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/exports/jobs/batch",
    json=batch_data,
    headers={"Authorization": "Bearer <token>"}
)
```

## Performance Considerations

### Large Dataset Handling
- **Batch Processing**: Default batch size of 1000 records
- **Streaming**: Files are streamed to avoid memory issues
- **Progress Tracking**: Real-time progress updates
- **Compression**: Optional gzip compression for large files

### Memory Management
- **Temporary Files**: Export files created in temp directory
- **Cleanup**: Automatic cleanup of temporary files
- **Memory Monitoring**: Track memory usage during export
- **Optimization**: Configurable batch sizes based on data size

### Concurrency
- **Background Processing**: All exports run in background tasks
- **Queue Management**: Celery queues for job processing
- **Parallel Processing**: Multiple jobs can run simultaneously
- **Resource Limits**: Configurable limits on concurrent jobs

## Error Handling

### Common Error Scenarios
- **Template Not Found**: Invalid template ID
- **Permission Denied**: User lacks export permissions
- **Invalid Data**: Data validation failures
- **Destination Errors**: Storage/API failures
- **Processing Errors**: Background task failures

### Error Recovery
- **Automatic Retries**: Configurable retry with exponential backoff
- **Partial Recovery**: Continue processing after record-level errors
- **Error Logging**: Comprehensive error tracking
- **User Notification**: Error notifications via configured channels

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Required field 'Vendor Name' is missing",
    "details": {
      "field": "Vendor Name",
      "rule": "required"
    }
  }
}
```

## Monitoring and Metrics

### Export Metrics
- **Processing Time**: Total export duration
- **Record Count**: Number of records processed
- **File Size**: Generated file size
- **Throughput**: Records per second
- **Error Rate**: Percentage of failed records

### Audit Logging
- **Job Creation**: Template and configuration used
- **Progress Updates**: Processing stage changes
- **Completion**: Final status and results
- **Errors**: Error details and recovery actions
- **User Actions**: Who initiated exports and when

### Health Checks
- **Service Status**: Export service availability
- **Queue Health**: Celery queue status
- **Storage Health**: Storage backend connectivity
- **Performance Metrics**: Recent export performance

## Security

### Authentication
- **JWT Tokens**: Required for all API calls
- **User Context**: Exports associated with creating user
- **Role-Based Access**: Admin vs user permissions
- **API Keys**: Alternative authentication for system integrations

### Data Protection
- **Input Validation**: All inputs validated
- **SQL Injection**: Parameterized queries used
- **File Security**: Temporary files secured
- **Access Control**: Users can only access their exports

### Audit Trail
- **Complete Logging**: All export actions logged
- **User Attribution**: Actions linked to users
- **Change Tracking**: Template changes tracked
- **Compliance**: Audit log retention policies

## Troubleshooting

### Common Issues

#### Export Job Stuck in Processing
1. Check Celery worker status: `celery -A app.workers.export_tasks inspect active`
2. Review error logs for worker failures
3. Check database connection
4. Verify storage backend connectivity

#### Large File Download Fails
1. Check file size vs. memory limits
2. Verify compression is enabled for large exports
3. Check download timeout settings
4. Use streaming download for very large files

#### Template Validation Errors
1. Verify field mappings are correct
2. Check source field paths exist in data
3. Validate transformation functions
4. Test with small dataset first

#### Performance Issues
1. Reduce batch size for memory constraints
2. Enable compression for large exports
3. Check database query performance
4. Monitor system resource usage

### Debug Information
- **Job ID**: Use for tracking specific exports
- **Template ID**: Identify template configuration
- **Error Logs**: Review detailed error messages
- **Metrics**: Check performance statistics
- **Audit Logs**: Review complete action history

## Migration Guide

### From Legacy Export
1. **Create New Templates**: Recreate export configurations
2. **Update API Calls**: Use new endpoint structure
3. **Migrate Jobs**: Existing jobs remain functional
4. **Update Monitoring**: Use new metrics and logging

### Template Migration
```python
# Legacy field mapping
legacy_mapping = {"vendor": "header.vendor_name"}

# New field mapping
new_mapping = ExportFieldMapping(
    source_field="header.vendor_name",
    target_field="Vendor Name",
    field_type="string",
    required=True
)
```

## Best Practices

### Template Design
- **Clear Naming**: Use descriptive template names
- **Documentation**: Include template descriptions
- **Validation**: Add appropriate validation rules
- **Testing**: Test templates with sample data

### Export Management
- **Regular Cleanup**: Remove old export jobs
- **Monitoring**: Track export performance metrics
- **Error Handling**: Implement proper error recovery
- **User Training**: Document export procedures

### Performance Optimization
- **Batch Sizes**: Tune batch sizes for data volume
- **Compression**: Use compression for large exports
- **Scheduling**: Schedule large exports during off-hours
- **Monitoring**: Track resource usage and bottlenecks