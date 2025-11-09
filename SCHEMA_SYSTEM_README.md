# Data Contracts and JSON Schema Management System

## Overview

This comprehensive data contracts and JSON schema management system ensures that all invoice data adheres to defined schemas, provides version management, and validates data at API boundaries and processing stages throughout the AP Intake invoice processing system.

## 🚀 Quick Start

### 1. Validate Data Against Schemas

```python
from app.services.schema_service import schema_service

# Validate extraction result
is_valid, errors, metadata = schema_service.validate_invoice_extraction(
    extraction_result,
    schema_version="1.0.0"
)

# Validate prepared bill data
is_valid, errors, metadata = schema_service.validate_prepared_bill(
    prepared_bill_data,
    schema_version="1.0.0"
)
```

### 2. Register New Schema Version

```python
from app.schemas.schema_registry import register_schema

# Register a new schema version
schema_info = register_schema(
    name="CustomSchema",
    version="1.0.0",
    schema_definition={
        "type": "object",
        "properties": {
            "field1": {"type": "string"},
            "field2": {"type": "number"}
        },
        "required": ["field1"]
    },
    description="Custom schema for specific use case"
)
```

### 3. Check Schema Compatibility

```python
# Check if new version is backward compatible
compatibility = schema_service.check_schema_compatibility(
    "PreparedBill",
    "1.0.0",
    "1.1.0"
)

if compatibility.breaking_changes:
    print(f"Breaking changes detected: {compatibility.breaking_changes}")
else:
    print("Schema is backward compatible")
```

### 4. API Integration

```python
from app.middleware.schema_validation import validate_schema, add_schema_headers

@router.post("/invoices")
@validate_schema("invoice_upload")
@add_schema_headers("ExtractionResult")
async def create_invoice(request: Request):
    # Request automatically validated against schema
    result = await process_invoice(request)
    # Response automatically validated and headers added
    return result
```

## 📋 Core Components

### 1. Schema Registry (`app/schemas/schema_registry.py`)

Central repository for managing schema versions and lifecycle:

- **Version Management**: Semantic versioning for all schemas
- **Compatibility Analysis**: Automatic detection of breaking changes
- **Lifecycle Control**: Schema registration, deprecation, and retirement
- **Persistence**: Optional storage of schema definitions

### 2. Schema Definitions (`app/schemas/json_schemas.py`)

Comprehensive JSON Schema definitions for all data structures:

- **PreparedBill**: Complete invoice data ready for export
- **ExtractionResult**: Output of invoice extraction process
- **ValidationResult**: Business rule validation results
- **Vendor**: Vendor information structure
- **LineItem**: Individual invoice line items
- **ExportFormat**: Export format definitions

### 3. Schema Service (`app/services/schema_service.py`)

Business logic for schema validation and integration:

- **Data Validation**: Validate data against schemas
- **API Contract Compliance**: Ensure API endpoints follow contracts
- **Version Metadata**: Add version information to data
- **Integration Support**: Helper functions for easy integration

### 4. Validation Middleware (`app/middleware/schema_validation.py`)

FastAPI middleware for automatic validation:

- **Request Validation**: Automatically validate incoming requests
- **Response Validation**: Ensure outgoing responses comply with schemas
- **Error Handling**: Proper error responses for validation failures
- **Performance Monitoring**: Track validation performance

### 5. Schema API (`app/api/api_v1/endpoints/schemas.py`)

REST endpoints for schema management:

- **Schema CRUD**: Create, read, update, delete schema versions
- **Validation Endpoints**: Validate data against schemas
- **Compatibility Checks**: Analyze version compatibility
- **Documentation**: Auto-generate schema documentation

## 🔧 Configuration

### Environment Variables

```bash
# Schema validation settings
SCHEMA_VALIDATION_STRICT_MODE=true
SCHEMA_VALIDATION_INCLUDE_DEPRECATED=false
SCHEMA_REGISTRY_STORAGE_PATH=/app/data/schemas.json

# Performance settings
SCHEMA_VALIDATION_CACHE_SIZE=1000
SCHEMA_VALIDATION_TIMEOUT_MS=5000
```

### Schema Registration on Startup

Default schemas are automatically registered when the application starts:

```python
# In app/main.py
from app.schemas import SCHEMA_VERSION, SUPPORTED_VERSIONS

# Schema system automatically initializes
# All default schemas are registered with version 1.0.0
```

## 📊 Schema Types

### PreparedBill Schema

The main data contract representing a fully processed invoice:

```json
{
  "bill_id": "uuid",
  "version": "1.0.0",
  "rules_version": "1.0.0",
  "parser_version": "1.0.0",
  "vendor": {
    "vendor_name": "string",
    "vendor_tax_id": "string"
  },
  "bill_header": {
    "invoice_date": "date",
    "total_amount": "number",
    "currency": "string"
  },
  "line_items": [
    {
      "description": "string",
      "quantity": "number",
      "unit_price": "number",
      "total_amount": "number"
    }
  ],
  "extraction_result": {...},
  "validation_result": {...},
  "export_ready": true
}
```

### ExtractionResult Schema

Output of the invoice extraction process with confidence scores:

```json
{
  "extraction_id": "uuid",
  "invoice_id": "uuid",
  "extraction_timestamp": "datetime",
  "parser_version": "1.0.0",
  "rules_version": "1.0.0",
  "header": {...},
  "lines": [...],
  "confidence": {
    "overall": 0.95,
    "invoice_number_confidence": 0.98
  },
  "metadata": {
    "processing_time_ms": 1500,
    "page_count": 1
  }
}
```

## 🔄 Version Management

### Semantic Versioning

All schemas follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes that require migration
- **MINOR** (1.0.0 → 1.1.0): New features added in backward-compatible way
- **PATCH** (1.0.0 → 1.0.1): Bug fixes and documentation updates

### Version Compatibility

The system automatically checks compatibility between versions:

```python
compatibility = schema_service.check_schema_compatibility(
    "PreparedBill", "1.0.0", "1.1.0"
)

print(f"Compatible: {compatibility.is_compatible}")
print(f"Breaking changes: {compatibility.breaking_changes}")
print(f"Migration required: {compatibility.migration_required}")
```

### Version Lifecycle

1. **Development**: New versions created in development branch
2. **Testing**: Comprehensive validation and compatibility checking
3. **Release**: Promoted to active status
4. **Deprecation**: Scheduled for removal (with 30-day notice)
5. **Retirement**: No longer supported

## 🧪 Testing

### Run Schema Tests

```bash
# Run all schema-related tests
pytest tests/test_schemas/ -v

# Run specific test categories
pytest tests/test_schemas/test_json_schema_syntax.py -v
pytest tests/test_schemas/test_schema_validation.py -v
pytest tests/test_schemas/test_schema_compatibility.py -v
```

### Schema Drift Detection

```bash
# Check for schema drift
python scripts/check_schema_drift.py

# Compare schemas with base branch
python scripts/compare_schemas.py --base-dir ../base-branch --current-dir .
```

### Performance Testing

```bash
# Benchmark schema validation performance
python scripts/benchmark_schema_validation.py
```

## 📚 Documentation Generation

### Generate Schema Documentation

```bash
# Generate documentation for all schemas
python scripts/generate_schema_docs.py

# Generate documentation for specific schema
python scripts/generate_schema_docs.py --schema PreparedBill

# Custom output directory
python scripts/generate_schema_docs.py --output-dir docs/custom
```

### Generated Documentation Includes

- **Schema Definitions**: Complete field descriptions and constraints
- **Examples**: Sample JSON for each schema
- **Version History**: Change log across versions
- **Validation Rules**: Detailed validation requirements
- **Migration Guides**: Instructions for version upgrades

## 🔍 CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/schema-validation.yml` workflow provides:

1. **Automated Validation**: Runs on every schema change
2. **Drift Detection**: Compares schemas with base branch
3. **Security Scanning**: Checks for sensitive data patterns
4. **Performance Testing**: Benchmarks validation performance
5. **Documentation Generation**: Auto-generates schema docs

### Workflow Triggers

- **Push**: On changes to schema files in main/develop branches
- **Pull Request**: On schema changes in PRs
- **Schedule**: Daily drift detection checks

### Breaking Change Detection

The workflow automatically detects and reports breaking changes:

```yaml
# Example PR comment generated by workflow
## 🔍 Schema Changes Detected

### 📝 Modified Schemas
- **PreparedBill**: 1.0.0 → 1.1.0
  - ⚠️ Breaking changes:
    - Field 'vendor_id' is now required

### ⚠️ Compatibility Issues
- Client migration required for PreparedBill schema
```

## 🔌 API Integration

### Adding Schema Validation to Endpoints

```python
from app.middleware.schema_validation import validate_schema, add_schema_headers

# Automatic request/response validation
@router.post("/invoices")
@validate_schema("invoice_upload")
@add_schema_headers("ExtractionResult")
async def create_invoice(request: Request):
    # Request automatically validated
    result = await process_invoice(request)
    # Response automatically validated
    return result

# Custom validation
@router.post("/custom-endpoint")
async def custom_endpoint(request: Request):
    # Manual validation
    request_data = await request.json()
    is_valid, errors = schema_service.validate_api_request(
        request_data,
        "custom_schema",
        request.headers.get("API-Version")
    )

    if not is_valid:
        raise HTTPException(422, detail=errors)

    # Process request...
```

### API Headers

The system uses specific headers for schema versioning:

```http
# Request headers
API-Version: 1.0.0
X-Schema-Version: 1.0.0

# Response headers
X-Schema-Validated: true
X-Schema-Version: 1.0.0
X-Schema-Validation-Warnings: Field xyz missing
```

## 📈 Performance Considerations

### Validation Performance

- **Typical Performance**: <10ms for standard invoice validation
- **Batch Processing**: Parallel validation for large datasets
- **Caching**: Schema definitions cached in memory
- **Monitoring**: Metrics exposed at `/metrics`

### Memory Usage

- **Schema Cache**: ~1MB for all default schemas
- **Registry Storage**: Minimal JSON persistence
- **Validation Metadata**: Temporary, cleaned up automatically

### Optimization Tips

1. **Use Specific Versions**: Avoid "latest" in production
2. **Cache Validation Results**: For repeated validations
3. **Batch Validations**: Group multiple validations
4. **Monitor Performance**: Track validation metrics

## 🔒 Security Considerations

### Data Protection

- **No Sensitive Data**: Schema definitions contain no PII
- **Sanitized Logs**: Validation logs exclude sensitive information
- **Access Control**: Schema modification requires authorization

### Injection Prevention

- **Meta-schema Validation**: All schemas validated against JSON Schema meta-schema
- **Sandboxed Validation**: Custom validation rules isolated
- **Restricted Registration**: Schema creation limited to authorized users

### Audit Trail

- **Change Tracking**: All schema changes logged with user attribution
- **Version History**: Complete audit trail maintained
- **Deprecation Records**: Documentation of all schema lifecycle events

## 🚨 Troubleshooting

### Common Issues

1. **Validation Failures**
   ```
   Error: Schema validation failed: Missing required field: vendor_name
   ```
   **Solution**: Ensure all required fields are present in data

2. **Version Conflicts**
   ```
   Error: Schema version 1.0.0 not found
   ```
   **Solution**: Check available versions with `GET /api/v1/schemas/{name}/versions`

3. **Compatibility Issues**
   ```
   Error: Breaking changes detected between versions
   ```
   **Solution**: Review compatibility report and plan migration

### Debug Tools

```python
# Validate data with detailed errors
is_valid, errors, metadata = schema_service.validate_invoice_extraction(
    extraction_result,
    schema_version="1.0.0",
    strict_mode=False
)

# Get detailed compatibility report
report = schema_service.check_schema_compatibility(
    "PreparedBill", "1.0.0", "1.1.0"
)

# Export schema for inspection
export_data = schema_service.export_schema_documentation(
    "PreparedBill", "1.0.0", "yaml"
)
```

### Log Analysis

```bash
# Check validation errors
grep "Schema validation" app.log

# Monitor performance
grep "Schema validation completed" app.log

# Find compatibility issues
grep "Breaking changes" app.log
```

## 📋 Best Practices

### Schema Design

1. **Keep schemas minimal** - Only include necessary fields
2. **Use clear field names** - Follow naming conventions
3. **Provide detailed descriptions** - Help developers understand purpose
4. **Plan for evolution** - Design for backward compatibility

### Version Management

1. **Semantic versioning** - Follow strict versioning rules
2. **Deprecation notices** - Provide advance notice of changes
3. **Migration paths** - Document required changes
4. **Testing** - Validate compatibility thoroughly

### Validation

1. **Fail fast** - Validate early in processing pipeline
2. **Clear errors** - Provide actionable error messages
3. **Performance** - Optimize for speed and memory
4. **Monitoring** - Track validation metrics

## 📚 Additional Resources

### Documentation

- [Comprehensive Schema Guide](docs/development/schemas.md)
- [API Documentation](http://localhost:8000/docs)
- [JSON Schema Specification](https://json-schema.org/)
- [Semantic Versioning](https://semver.org/)

### Scripts and Tools

- `scripts/check_schema_drift.py` - Detect schema drift
- `scripts/generate_schema_docs.py` - Generate documentation
- `scripts/compare_schemas.py` - Compare schema versions
- `scripts/benchmark_schema_validation.py` - Performance testing

### Support

For questions or issues related to schema management:

1. Check the API documentation at `/docs`
2. Review the schema health endpoint at `/api/v1/schemas/health`
3. Consult the troubleshooting section above
4. Contact the development team with specific issues

---

## 🎯 Quick Integration Checklist

- [ ] Install required dependencies: `pip install jsonschema pydantic`
- [ ] Add schema validation middleware to FastAPI app
- [ ] Define custom schemas for your data structures
- [ ] Configure CI/CD workflow for schema validation
- [ ] Set up monitoring for schema validation performance
- [ ] Generate and review schema documentation
- [ ] Test schema validation with sample data
- [ ] Configure deprecation policies for schema versions

Ready to ensure data contract compliance across your AP Intake system! 🚀