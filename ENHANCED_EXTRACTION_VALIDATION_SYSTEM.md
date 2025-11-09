# Enhanced Extraction and Validation System

This document describes the comprehensive enhanced extraction and validation system that provides advanced invoice processing capabilities with per-field confidence scoring, LLM-powered patching, and machine-readable reason taxonomy.

## Overview

The enhanced system builds upon the existing invoice processing workflow to provide:

1. **Enhanced Extraction**: Docling-first extraction with per-field confidence scores, PDF bbox coordinates, and field-level lineage tracking
2. **LLM Patching**: Intelligent correction of low-confidence fields using small, cost-effective LLM models
3. **Advanced Validation**: Comprehensive validation with deterministic structural validation, mathematical validation, and business rules validation
4. **Exception Management**: Machine-readable reason taxonomy and standardized exception handling

## Core Components

### 1. Enhanced Extraction Service (`app/services/enhanced_extraction_service.py`)

The enhanced extraction service provides field-level extraction with confidence scoring and bbox coordinate tracking.

**Key Features:**
- Per-field confidence scores (0-100 scale)
- PDF bbox coordinate storage for field location tracking
- Field-level extraction metadata and lineage
- Integration with LLM patching service
- Processing notes and quality metrics

**Core Classes:**
- `EnhancedExtractionService`: Main service for enhanced extraction
- `FieldMetadata`: Metadata for extracted fields with confidence and bbox
- `BBoxCoordinates`: PDF bounding box coordinates for field locations
- `ExtractionLineage`: Lineage tracking for extraction provenance

**Example Usage:**
```python
service = EnhancedExtractionService()
result = await service.extract_with_enhancement(
    file_content=pdf_bytes,
    file_path="invoice.pdf",
    enable_llm_patching=True
)

# Access field-level metadata
for field_name, field_metadata in header_fields.items():
    print(f"Field: {field_name}")
    print(f"Value: {field_metadata.value}")
    print(f"Confidence: {field_metadata.confidence}")
    print(f"BBox: {field_metadata.bbox}")
    print(f"LLM Patched: {field_metadata.lineage.llm_patched}")
```

### 2. LLM Patch Service (`app/services/llm_patch_service.py`)

Intelligent LLM-powered field correction with cost optimization and detailed tracking.

**Key Features:**
- Cost-optimized patching with configurable limits
- Per-request usage tracking and cost estimation
- Retry logic with exponential backoff
- Field validation before applying patches
- Performance metrics and usage statistics

**Core Classes:**
- `LLMPatchService`: Main service for field patching
- `LLMPatchRequest`: Request structure for patching
- `LLMPatchResult`: Result with metadata and cost information
- `LLMUsage`: Usage tracking for cost monitoring

**Example Usage:**
```python
service = LLMPatchService()
patched_result = await service.patch_fields(
    extraction_result={
        "header": {"vendor_name": "acme corp"},  # Low confidence
        "confidence": {"header": {"vendor_name": 0.4}}
    }
)

print(f"Cost: ${patched_result.cost_estimate:.4f}")
print(f"Patched fields: {patched_result.patched_fields}")
```

### 3. Advanced Validation Engine (`app/services/validation_engine.py`)

Comprehensive validation engine with deterministic rules and machine-readable reason taxonomy.

**Key Features:**
- Structural validation (required fields, formats)
- Mathematical validation (calculations, totals)
- Business rules validation (vendor, PO, duplicates)
- Machine-readable reason taxonomy for failures
- Versioned validation rules with configuration

**Core Classes:**
- `ValidationEngine`: Main validation engine
- `ValidationRule`: Individual validation rule with versioning
- `RuleExecutionResult`: Result of rule execution
- `ReasonTaxonomy`: Machine-readable reason codes

**Reason Taxonomy Examples:**
- `PO_NOT_FOUND`: Purchase Order not in system
- `TOTAL_MISMATCH`: Calculated vs stated totals differ
- `LOW_CONFIDENCE`: Extraction confidence below threshold
- `DUPLICATE_SUSPECT`: Potential duplicate detected
- `VENDOR_NOT_FOUND`: Vendor not in system
- `MISSING_REQUIRED_FIELDS`: Required fields missing

**Example Usage:**
```python
engine = ValidationEngine()
result = await engine.validate_comprehensive(
    extraction_result=extraction_data,
    invoice_id="invoice-123",
    strict_mode=False
)

print(f"Validation passed: {result.passed}")
print(f"Confidence score: {result.confidence_score}")
for issue in result.issues:
    print(f"Issue: {issue.reason_taxonomy} - {issue.message}")
```

### 4. Enhanced Models

#### Extraction Models (`app/models/extraction.py`)

Enhanced database models for field-level extraction tracking:

- `FieldExtraction`: Field-level extraction with confidence and bbox
- `ExtractionLineage`: Lineage tracking for extraction provenance
- `BBoxCoordinates`: PDF bounding box coordinates
- `ExtractionSession`: Session tracking for extraction processes

#### Validation Models (`app/models/validation.py`)

Enhanced validation models with reason taxonomy:

- `ValidationRule`: Versioned validation rules
- `ValidationSession`: Complete validation session tracking
- `ValidationIssue`: Detailed validation issues with reason taxonomy
- `ValidationMetrics`: Aggregated validation metrics

### 5. Enhanced Invoice Processor (`app/workflows/enhanced_invoice_processor.py`)

Enhanced workflow orchestration integrating all components:

**Workflow Steps:**
1. **Enhanced Receive**: File validation with metadata extraction
2. **Enhanced Extract**: Docling extraction with field-level confidence
3. **Enhance**: LLM patching for low-confidence fields
4. **Enhanced Validate**: Comprehensive validation with reason taxonomy
5. **Quality Assessment**: Overall quality scoring and classification
6. **Enhanced Triage**: Intelligent routing based on quality and validation
7. **Enhanced Export**: Export with quality metadata and lineage

## Quality Metrics and Scoring

The system provides comprehensive quality metrics:

### Extraction Quality Metrics
- **Completeness Score**: Percentage of required fields extracted
- **Accuracy Score**: Weighted confidence scores across all fields
- **BBox Detection Rate**: Percentage of fields with coordinate data
- **LLM Enhancement Rate**: Percentage of fields enhanced by LLM

### Validation Quality Metrics
- **Rule Pass Rate**: Percentage of validation rules passed
- **Issue Severity Distribution**: Breakdown of errors, warnings, info
- **Reason Taxonomy Distribution**: Most common failure reasons
- **Auto-Resolution Rate**: Percentage of issues auto-resolvable

### Processing Quality Levels
- **Excellent**: Quality score ≥ 0.9, validation passed, no human review needed
- **Good**: Quality score ≥ 0.75, minor issues only, conditional approval
- **Fair**: Quality score ≥ 0.5, some issues, review recommended
- **Poor**: Quality score < 0.5, significant issues, manual review required

## Cost Optimization

The LLM patching service includes cost optimization features:

### Cost Control Mechanisms
- **Maximum Cost per Invoice**: Configurable cost limits ($0.10 default)
- **Field Prioritization**: Patch most important fields first when budget constrained
- **Cost Estimation**: Pre-execution cost estimation
- **Usage Tracking**: Per-request and daily usage tracking

### Cost Estimation Example
```python
# Estimate cost before patching
cost_estimate = service._estimate_patch_cost(low_confidence_fields)
if cost_estimate <= max_cost_per_invoice:
    # Proceed with patching
    result = await service.patch_fields(extraction_result)
```

## Integration Points

### API Endpoints (`app/api/api_v1/endpoints/validation.py`)

Enhanced validation API endpoints:

- `POST /validate`: Comprehensive validation with enhancement
- `POST /validate/{invoice_id}`: Validate by invoice ID with enhancement
- `GET /rules`: Get available validation rules
- `GET /sessions/{session_id}/issues`: Get validation issues
- `POST /issues/{issue_id}/resolve`: Resolve validation issues
- `GET /summary`: Get validation summary for period
- `GET /export`: Export validation data
- `GET /metrics`: Get detailed validation metrics

### Database Schema

The system creates additional tables for enhanced tracking:

```sql
-- Extraction tracking
CREATE TABLE field_extractions (...);
CREATE TABLE extraction_lineage (...);
CREATE TABLE bbox_coordinates (...);
CREATE TABLE extraction_sessions (...);

-- Validation tracking
CREATE TABLE validation_rules (...);
CREATE TABLE validation_sessions (...);
CREATE TABLE validation_issues (...);
CREATE TABLE validation_metrics (...);
```

## Configuration

### Environment Variables

Key configuration options:

```bash
# Enhanced extraction
DOCLING_CONFIDENCE_THRESHOLD=0.8
DOCLING_MAX_PAGES=10

# LLM patching
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.1
OPENROUTER_API_KEY=your_api_key

# Validation
VALIDATION_RULES_VERSION=2.0.0
STRICT_VALIDATION_MODE=false

# Cost controls
MAX_LLM_COST_PER_INVOICE=0.10
MAX_FIELDS_PER_REQUEST=10
```

### Validation Rules Configuration

Customizable validation rules:

```python
rules_config = ValidationRulesConfig(
    version="2.0.0",
    thresholds={
        "max_invoice_age_days": 365,
        "max_total_amount": 1000000,
        "duplicate_confidence_threshold": 0.95,
        "po_amount_tolerance_percent": 5.0,
        "math_tolerance_cents": 1,
    },
    required_fields={
        "header": ["vendor_name", "invoice_number", "total_amount"],
        "lines": ["description", "amount"],
    }
)
```

## Testing

The system includes comprehensive testing (`test_enhanced_extraction_validation.py`):

### Test Coverage
- Enhanced extraction service with bbox tracking
- LLM patching with cost optimization
- Advanced validation engine with reason taxonomy
- Enhanced invoice processor workflow
- Field lineage tracking
- Reason taxonomy mapping

### Running Tests
```bash
# Install dependencies
pip install aiofiles sqlalchemy langfuse openai

# Run comprehensive tests
python test_enhanced_extraction_validation.py

# Check test report
cat enhanced_extraction_validation_test_report.json
```

## Performance Metrics

### Expected Performance Targets
- **Extraction Time**: < 2 seconds per page
- **Validation Time**: < 500ms per invoice
- **LLM Patching**: < 1 second for typical invoice
- **Overall Processing**: < 5 seconds end-to-end
- **Cost per Invoice**: < $0.05 average (including LLM patching)

### Monitoring and Observability

The system provides comprehensive metrics:

```python
# Usage statistics
usage_stats = llm_service.get_usage_stats()
print(f"Total requests: {usage_stats['total_requests']}")
print(f"Total cost: ${usage_stats['total_cost']:.4f}")

# Validation metrics
validation_summary = await get_validation_summary(days=7)
print(f"Pass rate: {validation_summary.pass_rate:.2%}")
print(f"Average confidence: {validation_summary.average_confidence:.3f}")
```

## Best Practices

### Extraction Enhancement
1. **Enable LLM patching** for invoices with confidence below threshold
2. **Monitor costs** and adjust cost limits based on volume
3. **Track bbox coordinates** for audit trails and UI highlighting
4. **Maintain lineage** for compliance and debugging

### Validation Rules
1. **Version rules** when making changes
2. **Configure thresholds** appropriately for business requirements
3. **Use reason taxonomy** for consistent issue classification
4. **Monitor rule performance** and optimize regularly

### Cost Management
1. **Set appropriate cost limits** based on processing volume
2. **Prioritize important fields** when budget constrained
3. **Monitor usage patterns** and adjust configuration
4. **Consider alternative models** for cost optimization

## Future Enhancements

Planned improvements to the enhanced system:

1. **Advanced bbox detection** with computer vision
2. **Multi-model LLM support** for optimal cost/quality balance
3. **ML-based quality prediction** before processing
4. **Enhanced UI** for review and correction of extraction
5. **Real-time processing** for high-volume scenarios
6. **Advanced anomaly detection** for fraud prevention

## Conclusion

The enhanced extraction and validation system provides:

✅ **Per-field confidence scoring** with PDF bbox coordinates
✅ **Cost-optimized LLM patching** with usage tracking
✅ **Comprehensive validation** with machine-readable reason taxonomy
✅ **Field-level lineage tracking** for audit and compliance
✅ **Quality assessment** and intelligent triage
✅ **Performance monitoring** and cost control

This system significantly improves the accuracy, reliability, and cost-effectiveness of invoice processing while maintaining full audit trails and compliance requirements.