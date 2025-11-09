# Data Contracts and JSON Schema Management

This document describes the comprehensive data contracts and JSON schema management system implemented for the AP Intake invoice processing system.

## Overview

The schema management system provides:
- **Data Contract Enforcement**: Ensures all invoice data adheres to defined schemas
- **Version Management**: Semantic versioning for all schema definitions
- **Validation Pipeline**: Automatic validation at API boundaries and processing stages
- **Compatibility Checking**: Tools to ensure backward compatibility between schema versions
- **Documentation Generation**: Auto-generated schema documentation and examples

## Architecture

### Core Components

1. **Schema Registry** (`app/schemas/schema_registry.py`)
   - Central repository for all schema definitions
   - Version management and lifecycle control
   - Compatibility analysis and migration tracking

2. **Schema Definitions** (`app/schemas/json_schemas.py`)
   - JSON Schema definitions for all data structures
   - PreparedBill, Vendor, LineItem, ExtractionResult, ValidationResult, ExportFormat schemas
   - Built-in validation rules and constraints

3. **Schema Service** (`app/services/schema_service.py`)
   - Business logic for schema validation
   - Integration with invoice processing workflow
   - API contract compliance checking

4. **Validation Middleware** (`app/middleware/schema_validation.py`)
   - Automatic request/response validation
   - API boundary enforcement
   - Performance monitoring and error handling

5. **Schema API** (`app/api/api_v1/endpoints/schemas.py`)
   - REST endpoints for schema management
   - Validation, versioning, and documentation services
   - Health monitoring and compatibility checks

## Schema Types

### 1. PreparedBill Schema

The main data contract representing a fully processed invoice ready for export.

```json
{
  "bill_id": "uuid",
  "version": "1.0.0",
  "rules_version": "1.0.0",
  "parser_version": "1.0.0",
  "vendor": {
    "vendor_name": "string",
    "vendor_address": {...},
    "vendor_tax_id": "string"
  },
  "bill_header": {
    "invoice_number": "string",
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
  "export_ready": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 2. ExtractionResult Schema

Represents the output of the invoice extraction process with confidence scores.

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
    "invoice_number_confidence": 0.98,
    "vendor_confidence": 0.92
  },
  "metadata": {
    "processing_time_ms": 1500,
    "page_count": 1,
    "completeness_score": 0.88
  }
}
```

### 3. ValidationResult Schema

Contains the results of business rule validation.

```json
{
  "validation_id": "uuid",
  "invoice_id": "uuid",
  "validation_timestamp": "datetime",
  "rules_version": "1.0.0",
  "schema_version": "1.0.0",
  "checks": {
    "required_fields_present": true,
    "vendor_recognized": true,
    "amounts_positive": true
  },
  "issues": [...],
  "warnings": [...],
  "summary": {
    "passed": true,
    "requires_human_review": false,
    "error_count": 0,
    "warning_count": 1,
    "confidence_score": 0.94
  }
}
```

## Version Management

### Semantic Versioning

All schemas follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes that require migration
- **MINOR**: New features added in backward-compatible way
- **PATCH**: Bug fixes and documentation updates

### Version Lifecycle

1. **Development**: New versions created in development branch
2. **Testing**: Comprehensive validation and compatibility checking
3. **Release**: Promoted to active status
4. **Deprecation**: Scheduled for removal (with 30-day notice)
5. **Retirement**: No longer supported

### Version Compatibility

The system automatically checks compatibility between versions:

```python
# Check compatibility
compatibility = schema_service.check_schema_compatibility(
    "PreparedBill", "1.0.0", "1.1.0"
)

if compatibility.breaking_changes:
    # Migration required
    pass
```

## Validation Pipeline

### 1. Request Validation

Incoming API requests are automatically validated against appropriate schemas:

```python
# Middleware automatically validates POST /api/v1/invoices
# against invoice_upload schema
```

### 2. Processing Validation

During invoice processing, data is validated at each stage:

```python
# Validate extraction result
is_valid, errors, metadata = schema_service.validate_invoice_extraction(
    extraction_result,
    schema_version="1.0.0"
)

# Validate prepared bill
is_valid, errors, metadata = schema_service.validate_prepared_bill(
    prepared_bill_data,
    schema_version="1.0.0"
)
```

### 3. Response Validation

Outgoing API responses are validated to ensure contract compliance:

```python
# Middleware automatically validates responses
# adds X-Schema-Validated header on success
```

## Integration Guide

### Adding Schema Validation to Endpoints

```python
from app.middleware.schema_validation import validate_schema, add_schema_headers

@router.post("/invoices")
@validate_schema("invoice_upload")
@add_schema_headers("ExtractionResult")
async def create_invoice(request: Request):
    # Request automatically validated
    result = await process_invoice(request)
    # Response automatically validated
    return result
```

### Custom Schema Validation

```python
from app.services.schema_service import schema_service

# Validate custom data
is_valid, errors = schema_service.validate_data(
    data,
    "CustomSchema",
    "1.0.0"
)

# Validate against custom contract requirements
is_compliant, issues = schema_service.validate_contract_compliance(
    data,
    contract_requirements
)
```

### Adding New Schemas

1. Define schema in `app/schemas/json_schemas.py`:

```python
class NewSchema(BaseSchema):
    schema_name: str = Field(default="NewSchema", const=True)
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            # Schema definition
        },
        "required": [...],
        "additionalProperties": False
    })
```

2. Register in schema service:

```python
# In SchemaService._ensure_default_schemas()
self.registry.register_schema(
    name="NewSchema",
    version="1.0.0",
    schema_definition=NewSchema(version="1.0.0").properties,
    description="New schema description"
)
```

3. Add validation logic:

```python
def validate_new_schema(
    self,
    data: Dict[str, Any],
    schema_version: Optional[str] = None
) -> Tuple[bool, List[str]]:
    return validate_data(data, "NewSchema", schema_version)
```

## API Endpoints

### Schema Management

- `GET /api/v1/schemas` - List all available schemas
- `GET /api/v1/schemas/{name}` - Get specific schema information
- `GET /api/v1/schemas/{name}/versions` - List all versions
- `POST /api/v1/schemas/{name}/versions` - Register new version

### Validation

- `POST /api/v1/schemas/validate` - Validate data against schema
- `GET /api/v1/schemas/{name}/compatibility/{from}/{to}` - Check compatibility
- `GET /api/v1/schemas/{name}/changelog` - Get version changelog

### Export

- `GET /api/v1/schemas/{name}/export` - Export schema definition
- `POST /api/v1/schemas/{name}/deprecate` - Deprecate schema version
- `GET /api/v1/schemas/health` - Service health check

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/schema-validation.yml` workflow provides:

1. **Automated Validation**: Runs on every schema change
2. **Drift Detection**: Compares schemas with base branch
3. **Security Scanning**: Checks for sensitive data patterns
4. **Performance Testing**: Benchmarks validation performance
5. **Documentation Generation**: Auto-generates schema docs

### Schema Drift Detection

```bash
# Run locally
python scripts/check_schema_drift.py

# Compare with base branch
python scripts/compare_schemas.py --base-dir ../base-branch --current-dir .
```

### Breaking Change Detection

```bash
# Check for breaking changes
python scripts/check_breaking_changes.py --base-dir ../base-branch --current-dir .
```

## Performance Considerations

### Validation Performance

- Schema validation typically completes in <10ms for standard invoice data
- Large batch processing uses parallel validation
- Caching reduces repeated validation overhead

### Memory Usage

- Schema definitions are cached in memory
- Registry persistence uses minimal storage
- Validation metadata is temporary and cleaned up automatically

### Monitoring

- Validation metrics exposed at `/metrics`
- Performance tracking in application logs
- Alert thresholds for validation failures

## Security Considerations

### Data Protection

- No sensitive data included in schema definitions
- Validation logs sanitize personal information
- Schema access controlled by API permissions

### Injection Prevention

- JSON schema parsing validated against meta-schema
- Custom validation rules sandboxed
- Schema registration restricted to authorized users

### Audit Trail

- All schema changes logged with user attribution
- Version history maintained for compliance
- Deprecation timeline documented

## Troubleshooting

### Common Issues

1. **Validation Failures**
   ```
   Error: Schema validation failed: Missing required field: vendor_name
   ```
   Solution: Ensure all required fields are present in data

2. **Version Conflicts**
   ```
   Error: Schema version 1.0.0 not found
   ```
   Solution: Check available versions with `GET /api/v1/schemas/{name}/versions`

3. **Compatibility Issues**
   ```
   Error: Breaking changes detected between versions
   ```
   Solution: Review compatibility report and plan migration

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

## Best Practices

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

### Documentation

1. **Auto-generated** - Use tools to keep docs current
2. **Examples** - Provide clear usage examples
3. **Changelogs** - Document all changes
4. **Migration guides** - Help with version upgrades

## Migration Guide

### Upgrading Schema Versions

1. **Analyze changes**:
   ```python
   compatibility = schema_service.check_schema_compatibility(
       "PreparedBill", "1.0.0", "1.1.0"
   )
   ```

2. **Plan migration**:
   - Review breaking changes
   - Update code to handle new fields
   - Test migration script

3. **Deploy gradually**:
   - Support both versions during transition
   - Monitor validation results
   - Update clients to new version

4. **Complete migration**:
   - Remove old version support
   - Update documentation
   - Retire deprecated schemas

### Example Migration

```python
# Migrate data from v1.0.0 to v1.1.0
def migrate_prepared_bill_v1_to_v1_1(data_v1: Dict) -> Dict:
    data_v1_1 = data_v1.copy()

    # Add new required field
    if 'new_field' not in data_v1_1:
        data_v1_1['new_field'] = 'default_value'

    # Update version
    data_v1_1['version'] = '1.1.0'

    return data_v1_1
```

## References

- [JSON Schema Specification](https://json-schema.org/)
- [Semantic Versioning](https://semver.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)

## Support

For questions or issues related to schema management:

1. Check the API documentation at `/docs`
2. Review the schema health endpoint at `/api/v1/schemas/health`
3. Consult the troubleshooting section above
4. Contact the development team with specific issues