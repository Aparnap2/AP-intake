# SQLAlchemy Relationship Fix Summary

## Problem
The `FileDeduplication.audit_logs` relationship in `/home/aparna/Desktop/ap_intake/app/models/storage_audit.py` was causing the following SQLAlchemy error:

```
Could not locate any relevant foreign key columns for primary join condition
'file_deduplication.file_hash = storage_audit.file_hash' on relationship
FileDeduplication.audit_logs
```

## Root Cause
The relationship was defined using a logical join on `file_hash` columns, but SQLAlchemy couldn't automatically detect the foreign key relationship because:

1. There is no actual foreign key constraint between `FileDeduplication.file_hash` and `StorageAudit.file_hash`
2. Both tables have `file_hash` as indexed columns, but not as foreign keys
3. SQLAlchemy requires explicit foreign key annotation for non-standard relationships

## Solution
Fixed the relationship by:

1. **Added `foreign` import**: Added `foreign` to the SQLAlchemy imports in the models file
2. **Updated relationship definition**: Modified the `primaryjoin` condition to use `foreign(StorageAudit.file_hash)` to explicitly indicate which side should be treated as the foreign key

### Before (Broken):
```python
audit_logs = relationship("StorageAudit",
                       primaryjoin="FileDeduplication.file_hash == StorageAudit.file_hash",
                       viewonly=True,
                       lazy="dynamic")
```

### After (Fixed):
```python
audit_logs = relationship("StorageAudit",
                       primaryjoin="FileDeduplication.file_hash == foreign(StorageAudit.file_hash)",
                       viewonly=True,
                       lazy="dynamic")
```

## Technical Details

- **Models Involved**: `FileDeduplication` and `StorageAudit` in `app/models/storage_audit.py`
- **Join Column**: `file_hash` (String(64), indexed in both tables)
- **Relationship Type**: Logical relationship (not foreign key constrained)
- **Access Pattern**: `FileDeduplication.audit_logs` returns a dynamic query of related `StorageAudit` records
- **SQLAlchemy Compatibility**: Works with async SQLAlchemy 2.0

## Usage Example
```python
# Get audit logs for a specific file hash
dedup_record = session.get(FileDeduplication, 1)
audit_logs = dedup_record.audit_logs.filter_by(operation="store").all()
```

## Benefits of This Fix

1. **Proper Relationship Resolution**: SQLAlchemy can now correctly resolve the join condition
2. **Maintains Intended Behavior**: The relationship remains viewonly and dynamic as originally intended
3. **Async Compatible**: Works with SQLAlchemy 2.0 async sessions
4. **No Database Changes Required**: This is a model-layer fix only, no migration needed
5. **Performance Optimized**: Uses existing indexes on both `file_hash` columns

## Files Modified

- `/home/aparna/Desktop/ap_intake/app/models/storage_audit.py`
  - Added `foreign` import
  - Fixed `audit_logs` relationship definition

## Testing

The fix can be verified by:
1. Importing the models without errors
2. Creating FileDeduplication instances and accessing the `audit_logs` attribute
3. Running the application's test suite
4. Starting the FastAPI application with the updated models