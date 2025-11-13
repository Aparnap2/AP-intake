# Idempotency and Staging Infrastructure Implementation

## Overview

This document describes the comprehensive idempotency and staging infrastructure implemented for the AP Intake & Validation system to ensure enterprise-grade reliability, data integrity, and auditability.

## Architecture

### Idempotency System

The idempotency system prevents duplicate operations and ensures data consistency across all API endpoints.

#### Key Components

1. **IdempotencyRecord** (`app/models/idempotency.py`)
   - Tracks operation status and execution attempts
   - Stores operation data and results
   - Provides TTL-based expiration
   - Supports retry logic with configurable limits

2. **IdempotencyService** (`app/services/idempotency_service.py`)
   - Generates deterministic idempotency keys
   - Manages operation lifecycle
   - Handles conflicts and retries
   - Provides cleanup functionality

3. **IdempotencyConflict** (`app/models/idempotency.py`)
   - Records operation conflicts
   - Tracks resolution actions
   - Provides audit trail for conflicts

#### Idempotency Key Generation

Idempotency keys are generated deterministically based on:

- **Invoice Upload**: `vendor_id + file_hash + user_id`
- **Invoice Processing**: `invoice_id + operation_type`
- **Export Staging**: `invoice_id + destination_system + export_format`
- **Export Posting**: `staged_export_id + user_id + action`

#### Configuration

```python
# Idempotency Settings
IDEMPOTENCY_TTL_SECONDS: int = 24 * 3600  # 24 hours
IDEMPOTENCY_MAX_EXECUTIONS: int = 3
IDEMPOTENCY_CLEANUP_HOURS: int = 1
IDEMPOTENCY_CACHE_PREFIX: str = "idempotency"
IDEMPOTENCY_ENABLE_METRICS: bool = True
```

### Staging System

The staging system provides a comprehensive export workflow with approval chains, audit trails, and rollback capabilities.

#### Key Components

1. **StagedExport** (`app/models/staging.py`)
   - Main staging table with workflow states
   - Stores data snapshots at each stage
   - Tracks field-level changes
   - Supports quality scoring and validation

2. **StagingApprovalChain** (`app/models/staging.py`)
   - Multi-level approval workflows
   - Risk assessment and business justification
   - Expiration handling for approvals

3. **StagingAuditTrail** (`app/models/staging.py`)
   - Comprehensive audit logging
   - Before/after data snapshots
   - Business event tracking
   - Impact assessment

4. **StagingBatch** (`app/models/staging.py`)
   - Batch processing support
   - Progress tracking
   - Quality metrics aggregation

#### Workflow States

1. **PREPARED**: Data staged and ready for review
2. **UNDER_REVIEW**: Currently being reviewed
3. **APPROVED**: Approved for posting
4. **REJECTED**: Rejected with reasons
5. **POSTED**: Successfully posted to destination
6. **FAILED**: Posting failed with error details
7. **ROLLED_BACK**: Posted data rolled back

#### Configuration

```python
# Staging Settings
STAGING_QUALITY_THRESHOLD: int = 70
STAGING_APPROVAL_TIMEOUT_HOURS: int = 72
STAGING_MAX_BATCH_SIZE: int = 1000
STAGING_ENABLE_DIFF_TRACKING: bool = True
STAGING_ENABLE_APPROVAL_CHAINS: bool = True
STAGING_DEFAULT_PRIORITY: int = 5
STAGING_COMPLIANCE_FLAGS: List[str] = ["SOX", "GDPR", "FINANCIAL"]
STAGING_ENABLE_ROLLBACK: bool = True
```

## API Endpoints

### Idempotency Integration

All critical endpoints now support idempotency:

1. **POST /api/v1/ingestion/upload**
   - Supports client-provided idempotency keys
   - Auto-generates keys from file hash and vendor ID
   - Returns existing results for duplicate requests

```bash
# With client-provided key
POST /api/v1/ingestion/upload?idempotency_key=client-generated-key

# Server generates key from vendor_id + file_hash
POST /api/v1/ingestion/upload
```

### Staging Endpoints

1. **POST /api/v1/staging/stage**
   - Stage an export for review
   - Includes quality validation and audit logging

```bash
POST /api/v1/staging/stage
{
  "invoice_id": "uuid",
  "export_format": "csv",
  "destination_system": "quickbooks",
  "export_data": {...},
  "prepared_by": "user-uuid"
}
```

2. **PUT /api/v1/staging/{id}/approve**
   - Approve a staged export with optional modifications
   - Tracks field changes and business reasons

```bash
PUT /api/v1/staging/{id}/approve
{
  "approved_by": "user-uuid",
  "approved_data": {...},  # Optional modified data
  "change_reason": "Corrected total amount",
  "approval_comments": "Looks good otherwise"
}
```

3. **POST /api/v1/staging/{id}/post**
   - Post approved export to destination system
   - Tracks external references and job IDs

```bash
POST /api/v1/staging/{id}/post
{
  "posted_by": "user-uuid",
  "external_reference": "EXT-12345",
  "export_filename": "export_001.csv"
}
```

4. **PUT /api/v1/staging/{id}/reject**
   - Reject a staged export with reasons

5. **POST /api/v1/staging/{id}/rollback**
   - Roll back a posted export
   - Integrates with destination system for reversal

6. **GET /api/v1/staging/{id}/diff**
   - Get comprehensive diff between data versions
   - Shows field-level changes and business reasons

## Database Schema

### Idempotency Tables

```sql
CREATE TABLE idempotency_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    operation_status VARCHAR(20) DEFAULT 'pending',
    invoice_id UUID REFERENCES invoices(id),
    ingestion_job_id UUID REFERENCES ingestion_jobs(id),
    operation_data JSONB NOT NULL,
    result_data JSONB,
    error_data JSONB,
    execution_count INTEGER DEFAULT 0,
    max_executions INTEGER DEFAULT 1,
    first_attempt_at TIMESTAMP,
    last_attempt_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,
    ttl_seconds INTEGER,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    client_ip VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Staging Tables

```sql
CREATE TABLE staged_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) NOT NULL,
    staging_status VARCHAR(20) DEFAULT 'prepared',
    export_format VARCHAR(20) NOT NULL,
    destination_system VARCHAR(255) NOT NULL,
    prepared_data JSONB NOT NULL,
    approved_data JSONB,
    posted_data JSONB,
    original_data JSONB,
    prepared_by UUID,
    approved_by UUID,
    posted_by UUID,
    rejected_by UUID,
    prepared_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP,
    posted_at TIMESTAMP,
    rejected_at TIMESTAMP,
    diff_summary JSONB,
    change_reason TEXT,
    field_changes JSONB,
    export_job_id VARCHAR(100),
    external_reference VARCHAR(255),
    export_filename VARCHAR(255),
    export_file_path TEXT,
    export_file_size INTEGER,
    validation_errors JSONB,
    validation_warnings JSONB,
    quality_score INTEGER,
    error_message TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    batch_id UUID,
    priority INTEGER DEFAULT 5,
    business_unit VARCHAR(100),
    cost_center VARCHAR(50),
    compliance_flags TEXT[],
    audit_notes TEXT,
    reviewer_comments TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Usage Examples

### Idempotent File Upload

```python
import httpx

# First request - creates new ingestion job
response1 = await httpx.post(
    "http://localhost:8000/api/v1/ingestion/upload",
    files={"file": open("invoice.pdf", "rb")},
    params={
        "vendor_id": "vendor-uuid",
        "uploaded_by": "user-uuid"
    }
)

# Second request with same file - returns existing result
response2 = await httpx.post(
    "http://localhost:8000/api/v1/ingestion/upload",
    files={"file": open("invoice.pdf", "rb")},
    params={
        "vendor_id": "vendor-uuid",
        "uploaded_by": "user-uuid"
    }
)

# Both responses have the same ingestion job ID
assert response1.json()["id"] == response2.json()["id"]
```

### Export Staging Workflow

```python
import httpx

# 1. Stage export
staging_response = await httpx.post(
    "http://localhost:8000/api/v1/staging/stage",
    json={
        "invoice_id": "invoice-uuid",
        "export_format": "csv",
        "destination_system": "quickbooks",
        "export_data": {
            "vendor_name": "ACME Corp",
            "invoice_number": "INV-001",
            "total_amount": 1000.00
        },
        "prepared_by": "user-uuid"
    }
)

staged_export_id = staging_response.json()["id"]

# 2. Get diff to see changes
diff_response = await httpx.get(
    f"http://localhost:8000/api/v1/staging/{staged_export_id}/diff"
)

# 3. Approve with modifications
approval_response = await httpx.put(
    f"http://localhost:8000/api/v1/staging/{staged_export_id}/approve",
    json={
        "approved_by": "manager-uuid",
        "approved_data": {
            "vendor_name": "ACME Corporation",  # Corrected name
            "invoice_number": "INV-001",
            "total_amount": 1100.00  # Corrected amount
        },
        "change_reason": "Corrected vendor name and total amount"
    }
)

# 4. Post to destination system
post_response = await httpx.post(
    f"http://localhost:8000/api/v1/staging/{staged_export_id}/post",
    json={
        "posted_by": "user-uuid",
        "external_reference": "QB-12345"
    }
)
```

## Monitoring and Metrics

### Idempotency Metrics

- Total operations by type
- Success/failure rates
- Duplicate prevention counts
- Conflict detection rates
- Average execution times

### Staging Metrics

- Export pipeline health
- Approval chain efficiency
- Quality score distributions
- Processing time by stage
- Rollback rates and reasons

### Dashboard Monitoring

The system provides comprehensive monitoring through:

1. **Grafana dashboards** for real-time metrics
2. **Prometheus alerts** for system health
3. **Audit logs** for compliance tracking
4. **Error tracking** via Sentry

## Security and Compliance

### Data Protection

- All audit trails are immutable
- Sensitive data is encrypted at rest
- Access controls enforced at all levels
- Data retention policies enforced

### Compliance Features

- **SOX compliance**: Complete audit trails
- **GDPR compliance**: Data access logging
- **Financial controls**: Approval chains and segregation of duties
- **Change tracking**: Before/after snapshots

### Security Controls

- Role-based access control (RBAC)
- Multi-factor authentication for critical operations
- IP-based access restrictions
- Session management and timeout

## Testing

### Unit Tests

- Idempotency key generation
- Operation lifecycle management
- Conflict resolution
- Data validation

### Integration Tests

- End-to-end staging workflows
- Database transaction integrity
- API idempotency behavior
- Audit trail accuracy

### Performance Tests

- Concurrent operation handling
- Large batch processing
- Database query optimization
- Cache performance

## Troubleshooting

### Common Issues

1. **Idempotency Key Conflicts**
   - Check operation parameters are consistent
   - Verify key generation logic
   - Review TTL settings

2. **Staging Workflow Failures**
   - Check data validation errors
   - Verify approval chain setup
   - Review destination system connectivity

3. **Audit Trail Issues**
   - Verify database connectivity
   - Check transaction boundaries
   - Review async operation handling

### Debug Tools

- API endpoint `/api/v1/health/detailed`
- Database query logs
- Application logs with correlation IDs
- Performance monitoring dashboards

## Migration and Deployment

### Database Migration

```bash
# Apply new tables and indexes
alembic upgrade head

# Verify migration
alembic current
```

### Configuration Updates

Update environment variables in `.env`:

```bash
# Idempotency settings
IDEMPOTENCY_TTL_SECONDS=86400
IDEMPOTENCY_MAX_EXECUTIONS=3
IDEMPOTENCY_CLEANUP_HOURS=1

# Staging settings
STAGING_QUALITY_THRESHOLD=70
STAGING_APPROVAL_TIMEOUT_HOURS=72
STAGING_ENABLE_ROLLBACK=true
```

### Service Deployment

```bash
# Deploy with updated configuration
docker-compose up -d

# Verify services are healthy
curl http://localhost:8000/health
```

## Future Enhancements

### Planned Features

1. **Advanced Idempotency**
   - Distributed locking across multiple instances
   - Redis-based caching for high-throughput operations
   - Machine learning for conflict prediction

2. **Enhanced Staging**
   - Automated approval based on risk scores
   - Advanced change detection algorithms
   - Integration with more ERP systems

3. **Monitoring Improvements**
   - Real-time anomaly detection
   - Predictive performance monitoring
   - Advanced compliance reporting

### Scalability Considerations

- Horizontal scaling support
- Database sharding for high-volume scenarios
- Caching layers for improved performance
- Load balancing optimization

## Conclusion

The idempotency and staging infrastructure provides enterprise-grade reliability and auditability for the AP Intake & Validation system. It ensures data integrity, prevents duplicate operations, and provides comprehensive audit trails for compliance requirements.

The implementation follows industry best practices for:
- Database design and transaction management
- API design and error handling
- Security and compliance
- Monitoring and observability
- Testing and quality assurance

This infrastructure forms the foundation for production deployment and can be extended to support additional features and requirements as the system evolves.