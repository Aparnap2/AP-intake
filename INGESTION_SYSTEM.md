# AP Intake Ingestion System Documentation

## Overview

The AP Intake Ingestion System provides comprehensive file handling, deduplication, and secure access management for invoice processing. This system ensures data integrity, prevents duplicate processing, and provides robust security features for file access.

## Architecture

### Core Components

1. **Ingestion Service** (`app/services/ingestion_service.py`)
   - File validation and metadata extraction
   - Secure file storage with multiple backends
   - Comprehensive deduplication analysis
   - Background processing queue management

2. **Deduplication Service** (`app/services/deduplication_service.py`)
   - Multiple deduplication strategies
   - Configurable detection rules
   - Duplicate resolution workflows
   - Performance analytics

3. **Signed URL Service** (`app/services/signed_url_service.py`)
   - Secure time-limited file access
   - IP and access restrictions
   - Usage tracking and audit logs
   - Automatic cleanup of expired URLs

4. **Background Tasks** (`app/workers/ingestion_tasks.py`)
   - Asynchronous file processing
   - Duplicate resolution automation
   - Error handling and retry logic
   - Performance monitoring

## Deduplication Strategies

### 1. File Hash Deduplication
- **Method**: SHA-256 cryptographic hashing
- **Confidence**: 100% for exact matches
- **Use Case**: Preventing identical file uploads
- **Performance**: Very fast, O(1) lookup

### 2. Business Rules Deduplication
- **Method**: Vendor + Amount + Date combination
- **Tolerance**: Configurable amount and date variations
- **Confidence**: 80-95% based on match quality
- **Use Case**: Different files representing same invoice

### 3. Temporal Deduplication
- **Method**: Time window analysis (default 24 hours)
- **Factors**: File size, type, vendor, timing
- **Confidence**: 60-80%
- **Use Case**: Multiple uploads of same document

### 4. Fuzzy Matching Deduplication
- **Method**: Content similarity analysis
- **Techniques**: Text extraction, sequence matching
- **Confidence**: 70-90%
- **Use Case**: Modified or reformatted invoices

### 5. Composite Strategy
- **Method**: Weighted combination of multiple strategies
- **Weights**: Configurable per strategy
- **Confidence**: 70-95% based on combined evidence
- **Use Case**: Comprehensive duplicate detection

## API Endpoints

### File Ingestion

#### Upload File
```http
POST /api/v1/ingestion/upload
Content-Type: multipart/form-data

file: [file]
vendor_id: [optional uuid]
source_type: upload|email|api|batch
source_reference: [optional reference id]
uploaded_by: [optional user identifier]
```

**Response:**
```json
{
  "id": "ingestion-job-uuid",
  "original_filename": "invoice.pdf",
  "file_size_bytes": 1048576,
  "file_hash_sha256": "sha256-hash",
  "status": "processing",
  "storage_path": "path/to/file",
  "duplicate_analysis": {
    "strategies_applied": ["file_hash", "business_rules"],
    "duplicates_found": [],
    "confidence_scores": {}
  },
  "estimated_processing_time_seconds": 30
}
```

### Duplicate Management

#### List Duplicate Groups
```http
GET /api/v1/ingestion/duplicates?limit=100&vendor_id=uuid&status=detected
```

**Response:**
```json
[
  {
    "group_id": "group-uuid",
    "duplicate_count": 3,
    "total_confidence": 2.5,
    "strategies_used": ["file_hash", "business_rules"],
    "duplicates": [
      {
        "id": "duplicate-uuid",
        "ingestion_job_id": "job-uuid",
        "confidence_score": 0.95,
        "strategy": "file_hash",
        "filename": "invoice.pdf",
        "requires_human_review": false
      }
    ]
  }
]
```

#### Resolve Duplicate
```http
POST /api/v1/ingestion/duplicates/{duplicate_id}/resolve
Content-Type: application/json

{
  "resolution": "auto_ignore",
  "resolved_by": "user-identifier",
  "resolution_notes": "Exact file match - ignoring duplicate"
}
```

### Secure File Access

#### Generate Signed URL
```http
POST /api/v1/ingestion/jobs/{job_id}/signed-urls
Content-Type: application/json

{
  "expiry_hours": 24,
  "max_access_count": 1,
  "allowed_ips": ["192.168.1.100"],
  "created_for": "invoice-review"
}
```

**Response:**
```json
{
  "id": "signed-url-uuid",
  "url": "https://api.example.com/files/secure-token",
  "token": "secure-token",
  "expires_at": "2024-01-16T10:00:00Z",
  "security_features": {
    "token_length": 32,
    "url_expires": true,
    "access_limited": true,
    "ip_restricted": true
  }
}
```

#### Access File via Signed URL
```http
GET /api/v1/ingestion/files/{url_token}
```

## Database Schema

### Ingestion Jobs Table
```sql
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY,
    original_filename VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_hash_sha256 VARCHAR(64) UNIQUE NOT NULL,
    storage_path TEXT NOT NULL,
    storage_backend VARCHAR(50) NOT NULL,
    status INGESTION_STATUS NOT NULL,
    extracted_metadata JSONB,
    vendor_id UUID REFERENCES vendors(id),
    processing_priority INTEGER DEFAULT 5,
    deduplication_strategy DEDUPLICATION_STRATEGY NOT NULL,
    duplicate_group_id UUID,
    is_duplicate BOOLEAN DEFAULT FALSE,
    -- Additional fields for tracking and error handling
);
```

### Duplicate Records Table
```sql
CREATE TABLE duplicate_records (
    id UUID PRIMARY KEY,
    ingestion_job_id UUID NOT NULL REFERENCES ingestion_jobs(id),
    detection_strategy DEDUPLICATION_STRATEGY NOT NULL,
    confidence_score FLOAT NOT NULL,
    similarity_score FLOAT,
    match_criteria JSONB NOT NULL,
    comparison_details JSONB,
    resolution_action DUPLICATE_RESOLUTION,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    requires_human_review BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'detected'
);
```

### Signed URLs Table
```sql
CREATE TABLE signed_urls (
    id UUID PRIMARY KEY,
    ingestion_job_id UUID NOT NULL REFERENCES ingestion_jobs(id),
    url_token VARCHAR(255) UNIQUE NOT NULL,
    signed_url TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    access_count INTEGER DEFAULT 0,
    max_access_count INTEGER DEFAULT 1,
    allowed_ip_addresses TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by VARCHAR(255)
);
```

## Configuration

### Environment Variables
```bash
# File Storage Configuration
STORAGE_TYPE=local|s3|r2|supabase
STORAGE_PATH=/var/lib/ap_intake/files
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=ap-intake-files
S3_ENDPOINT_URL=https://s3.amazonaws.com

# Deduplication Configuration
DOCLING_CONFIDENCE_THRESHOLD=0.8
MAX_FILE_SIZE_MB=100
ALLOWED_FILE_TYPES=pdf,png,jpg,tiff,webp,doc,docx

# Security Configuration
SECRET_KEY=your-secret-key-for-signing
BASE_URL=https://api.example.com
SIGNED_URL_DEFAULT_EXPIRY_HOURS=24
SIGNED_URL_MAX_EXPIRY_HOURS=168

# Processing Configuration
INGESTION_PROCESSING_PRIORITY=5
MAX_RETRY_ATTEMPTS=5
BACKGROUND_TASK_DELAY=60
```

### Deduplication Rules Configuration
```json
{
  "file_hash": {
    "confidence_threshold": 1.0,
    "enabled": true,
    "priority": 10
  },
  "business_rules": {
    "date_tolerance_days": 3,
    "amount_tolerance": 0.01,
    "confidence_threshold": 0.8,
    "enabled": true,
    "priority": 8
  },
  "temporal": {
    "window_hours": 24,
    "confidence_threshold": 0.6,
    "enabled": true,
    "priority": 6
  },
  "fuzzy_matching": {
    "similarity_threshold": 0.85,
    "days_back": 30,
    "max_comparisons": 50,
    "confidence_threshold": 0.7,
    "enabled": true,
    "priority": 4
  },
  "composite": {
    "strategies": ["FILE_HASH", "BUSINESS_RULES", "TEMPORAL"],
    "strategy_weights": {
      "FILE_HASH": 1.0,
      "BUSINESS_RULES": 0.8,
      "TEMPORAL": 0.6
    },
    "confidence_threshold": 0.7,
    "enabled": true,
    "priority": 9
  }
}
```

## Security Features

### File Access Control
1. **Signed URLs**: Cryptographically signed, time-limited access tokens
2. **IP Restrictions**: Optional IP address whitelisting
3. **Access Limits**: Configurable maximum access counts
4. **Audit Trail**: Complete access logging and tracking

### Data Protection
1. **File Hashing**: SHA-256 cryptographic hashing for integrity
2. **Secure Storage**: Support for encrypted storage backends
3. **Access Control**: Role-based access to sensitive operations
4. **Data Retention**: Configurable retention and cleanup policies

## Performance Considerations

### Optimization Strategies
1. **Indexing Strategy**: Comprehensive database indexing for fast lookups
2. **Caching**: Redis caching for duplicate detection results
3. **Async Processing**: Background task queue for non-blocking operations
4. **Batch Operations**: Efficient batch processing for multiple files

### Monitoring Metrics
1. **Processing Time**: Average time per file by type and size
2. **Duplicate Detection**: Accuracy and false positive rates
3. **Storage Usage**: File storage trends and cleanup efficiency
4. **System Load**: CPU, memory, and I/O utilization

## Integration Points

### Existing System Integration
1. **Invoice Processing**: Seamless integration with existing invoice workflow
2. **Vendor Management**: Automatic vendor association during ingestion
3. **Storage Service**: Compatible with existing storage infrastructure
4. **User Authentication**: Integration with existing auth system

### External System Integration
1. **Email Ingestion**: Automatic processing of email attachments
2. **API Integration**: RESTful API for external system integration
3. **Webhook Support**: Event notifications for processing status
4. **Export Capabilities**: Integration with external ERP systems

## Frontend Integration

### React Components
1. **DuplicateManagement**: Comprehensive duplicate resolution UI
2. **FileUpload**: Enhanced file upload with progress tracking
3. **SecureFileViewer**: Secure file preview and download interface
4. **IngestionAnalytics**: Real-time metrics and monitoring dashboard

### User Experience Features
1. **Progress Tracking**: Real-time processing status updates
2. **Batch Operations**: Bulk duplicate resolution actions
3. **Visual Comparisons**: Side-by-side file comparison tools
4. **Audit Logs**: Complete history of user actions

## Troubleshooting

### Common Issues
1. **File Upload Failures**: Check file size, type, and storage configuration
2. **Duplicate Detection**: Review strategy configuration and thresholds
3. **Processing Delays**: Monitor background task queue and system resources
4. **Access Issues**: Verify signed URL generation and validation

### Debug Tools
1. **Logging**: Comprehensive logging at all service levels
2. **Metrics**: Detailed performance and error metrics
3. **Health Checks**: System health and status monitoring
4. **Admin Interface**: Administrative tools for system management

## Migration Guide

### Database Migration
```bash
# Run database migrations
alembic upgrade head

# Verify migration
alembic current
alembic history
```

### Configuration Migration
1. Update environment variables
2. Configure storage backends
3. Set up deduplication rules
4. Initialize background workers

### Data Migration
1. Migrate existing files to new storage structure
2. Update file references in database
3. Generate file hashes for existing data
4. Initialize duplicate analysis for historical data

## Future Enhancements

### Planned Features
1. **Machine Learning**: AI-powered duplicate detection
2. **Advanced Analytics**: Predictive duplicate prevention
3. **Mobile Support**: Native mobile app integration
4. **Blockchain**: Immutable audit trail capabilities

### Scalability Improvements
1. **Distributed Processing**: Multi-node processing capabilities
2. **Advanced Caching**: Multi-level caching strategy
3. **Load Balancing**: Intelligent request distribution
4. **Auto-scaling**: Dynamic resource allocation

---

## Support

For technical support and questions:
- Documentation: Check this guide and API documentation
- Issues: Report bugs and feature requests via issue tracker
- Community: Join our developer community for discussions
- Support: Contact support team for enterprise assistance