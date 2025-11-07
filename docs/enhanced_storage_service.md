# Enhanced Storage Service Documentation

## Overview

The AP Intake system includes an enhanced local storage service with advanced features for file management, including compression, deduplication, access control, and comprehensive audit logging.

## Features

### 1. File Compression
- **Automatic compression** for files above the configured threshold
- **Multiple compression algorithms**: gzip, LZ4
- **Intelligent compression** - skips already compressed files (JPEG, PNG, ZIP, etc.)
- **Compression ratio tracking** for storage optimization monitoring

### 2. File Deduplication
- **Content-based deduplication** using SHA-256 hashes
- **Reference counting** for multiple files with identical content
- **Storage space optimization** by storing unique content only once
- **Automatic cleanup** when reference count reaches zero

### 3. Organized File Structure
```
storage/
├── originals/           # Original file backups
├── compressed/          # Compressed files
├── processed/           # Processed files
├── temp/               # Temporary files
├── archive/            # Archived files
├── by_date/            # Date-based organization
│   ├── 2024/
│   │   ├── 01/
│   │   └── 02/
├── by_vendor/          # Vendor-based organization
│   ├── ACME_Corporation/
│   └── Global_Supplies/
└── by_type/            # File type-based organization
    ├── pdfs/
    ├── images/
    └── documents/
```

### 4. Access Control & Security
- **Role-based access control** (RBAC)
- **File-level permissions** (public, private, restricted)
- **User-based access restrictions**
- **Expiration-based access control**
- **IP address and session tracking**

### 5. Comprehensive Audit Logging
- **Complete operation tracking** (store, retrieve, delete, archive)
- **Performance metrics** (operation duration)
- **User and session tracking**
- **Error logging and reporting**
- **Access attempt monitoring**

## Configuration

Add these settings to your `.env` file:

```bash
# Enhanced Local Storage Configuration
STORAGE_TYPE=local
STORAGE_PATH=./storage
STORAGE_COMPRESSION_ENABLED=true
STORAGE_COMPRESSION_TYPE=gzip    # gzip, lz4, none
STORAGE_COMPRESSION_THRESHOLD=1024  # bytes
```

## Usage

### Basic File Storage

```python
from app.services.storage_service import StorageService
from fastapi import Request

storage_service = StorageService()

# Store a file with enhanced features
result = await storage_service.store_file(
    file_content=file_content,
    filename="invoice_12345.pdf",
    content_type="application/pdf",
    user_id="user123",
    session_id="session456",
    organization_path="company_ABC/2024",
    vendor_name="Global Supplies Inc.",
    invoice_date="2024-01-15"
)

print(f"File stored at: {result['file_path']}")
print(f"File hash: {result['file_hash']}")
print(f"Compressed: {result['is_compressed']}")
print(f"Compression ratio: {result['compression_ratio']}")
```

### File Retrieval

```python
# Retrieve file with access control
content = await storage_service.get_file_content(
    file_path=result['file_path'],
    user_id="user123",
    session_id="session456"
)
```

### File Listing

```python
# List files with access control
files = await storage_service.list_files(
    prefix="by_vendor/Global_Supplies",
    limit=50,
    user_id="user123",
    include_archived=False
)
```

### File Deletion

```python
# Soft delete (archive)
await storage_service.delete_file(
    file_path=result['file_path'],
    user_id="user123",
    permanent=False
)

# Permanent delete
await storage_service.delete_file(
    file_path=result['file_path'],
    user_id="user123",
    permanent=True
)
```

## Database Schema

### Storage Audit Table
Tracks all file operations with comprehensive metadata:

```sql
CREATE TABLE storage_audit (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    operation_status VARCHAR(20) NOT NULL,
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    file_size INTEGER,
    content_type VARCHAR(100),
    error_message TEXT,
    metadata TEXT,
    created_at TIMESTAMP NOT NULL,
    duration_ms INTEGER
);
```

### File Deduplication Table
Manages content-based deduplication:

```sql
CREATE TABLE file_deduplication (
    id SERIAL PRIMARY KEY,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_path VARCHAR(500) UNIQUE NOT NULL,
    file_size INTEGER NOT NULL,
    content_type VARCHAR(100),
    reference_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP NOT NULL,
    last_accessed TIMESTAMP NOT NULL,
    is_compressed BOOLEAN DEFAULT FALSE,
    compression_type VARCHAR(20),
    original_size INTEGER,
    compressed_size INTEGER
);
```

### File Access Control Table
Manages file permissions and access control:

```sql
CREATE TABLE file_access_control (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    access_level VARCHAR(20) DEFAULT 'private',
    allowed_users TEXT,
    allowed_roles TEXT,
    access_rules TEXT,
    expires_at TIMESTAMP,
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

## Storage Management Tools

### Storage Manager CLI

The system includes a command-line tool for storage management:

```bash
# Get storage statistics
python scripts/storage_manager.py stats

# Clean up temporary files
python scripts/storage_manager.py cleanup-temp --max-age-hours 24

# Clean up old audit logs
python scripts/storage_manager.py cleanup-audit --max-age-days 90

# Find orphaned files
python scripts/storage_manager.py find-orphans

# Generate access report
python scripts/storage_manager.py access-report --report-days 30

# Run optimization
python scripts/storage_manager.py optimize

# Get output in JSON format
python scripts/storage_manager.py stats --format json
```

### Example Output

```
Storage Statistics
==================================================
Storage Path: /app/storage
Total Files: 1,234
Total Size: 1,456.78 MB
Unique Files: 890
Deduplicated Files: 344
Compressed Files: 567
Space Saved by Compression: 234.56 MB
Archive Size: 123.45 MB
Temp Size: 12.34 MB

By File Type:
  pdfs: 1,234.56 MB
  images: 123.45 MB
  documents: 98.76 MB

By Organization:
  ACME_Corporation: 456.78 MB
  Global_Supplies: 234.56 MB
  date:2024/01: 123.45 MB
```

## Performance Optimization

### Compression Settings

- **gzip**: Good compression ratio, moderate CPU usage
- **lz4**: Fast compression/decompression, moderate ratio
- **none**: No compression (for testing or when CPU is limited)

### Storage Optimization Tips

1. **Regular cleanup**: Use the storage manager to clean temp files and old audit logs
2. **Monitor compression ratios**: Adjust threshold based on your file types
3. **Organize by vendor/date**: Use metadata for efficient organization
4. **Monitor deduplication**: High deduplication ratios indicate good storage efficiency

### Access Control Best Practices

1. **Use least privilege**: Grant minimum necessary access
2. **Set expiration dates**: For temporary access
3. **Regular audit reviews**: Monitor access patterns
4. **User-based restrictions**: Implement per-user file access

## Monitoring and Maintenance

### Key Metrics to Monitor

- **Compression ratio**: Should be >10% for compressed files
- **Deduplication ratio**: Higher is better for storage efficiency
- **Access patterns**: Monitor for unusual activity
- **Storage growth**: Track usage over time
- **Error rates**: Monitor for system issues

### Regular Maintenance Tasks

1. **Weekly**: Clean up temporary files
2. **Monthly**: Clean up old audit logs
3. **Quarterly**: Review access controls and permissions
4. **Annually**: Archive old files and review storage organization

## Troubleshooting

### Common Issues

1. **Permission denied errors**: Check file access controls
2. **Compression failures**: Verify sufficient disk space and permissions
3. **Deduplication issues**: Check database connectivity
4. **Performance issues**: Monitor CPU usage with compression enabled

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('app.services.local_storage_service').setLevel(logging.DEBUG)
```

## Integration with LangGraph Workflow

The enhanced storage service integrates seamlessly with the invoice processing workflow:

```python
# In your LangGraph workflow node
async def process_invoice_node(state):
    # Get file from previous step
    file_content = state.get("file_content")
    filename = state.get("filename")

    # Store with organization metadata
    storage_result = await storage_service.store_file(
        file_content=file_content,
        filename=filename,
        vendor_name=state.get("vendor_name"),
        invoice_date=state.get("invoice_date"),
        user_id=state.get("user_id")
    )

    # Update state with storage info
    state.update({
        "file_path": storage_result["file_path"],
        "file_hash": storage_result["file_hash"],
        "storage_info": storage_result
    })

    return state
```

## Security Considerations

1. **File access logging**: All access is logged for audit purposes
2. **Path traversal prevention**: Built-in protection against directory traversal
3. **Content validation**: File type and size validation
4. **User authentication**: Integration with existing auth system
5. **Encrypted storage**: Files can be stored encrypted (future enhancement)

## Future Enhancements

1. **Encryption at rest**: Client-side encryption support
2. **Multi-region storage**: Geographic distribution
3. **Advanced compression**: Support for additional algorithms
4. **Smart tiering**: Automatic migration to cold storage
5. **Real-time sync**: Multi-node synchronization