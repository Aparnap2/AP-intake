# Test PDF Invoice Generator for AP Intake & Validation System

This directory contains comprehensive tools for generating test PDF invoices to thoroughly test the document parsing and validation capabilities of the AP Intake & Validation system.

## Overview

The invoice generator creates professional, realistic test invoices that cover various scenarios to validate the system's ability to:

- Extract header information (vendor name, invoice number, dates, amounts)
- Parse line items with descriptions, quantities, and prices
- Handle different invoice formats and complexities
- Test validation logic with edge cases and error scenarios
- Measure extraction confidence scores

## Files

### Main Scripts

1. **`create_test_invoice.py`** - Main invoice generator script
   - Creates professional PDF invoices using ReportLab
   - Supports multiple scenarios (standard, complex, error cases, etc.)
   - Includes barcode/QR code generation capabilities
   - Customizable vendor, customer, and product data

2. **`test_invoice_generation.py`** - Testing script for generated invoices
   - Tests generated PDFs with the Docling extraction service
   - Validates extraction results with the validation service
   - Provides confidence scores and detailed analysis
   - Generates test reports

3. **`README_invoice_generator.md`** - This documentation file

## Usage

### Generate All Test Scenarios

```bash
# Generate all test invoice scenarios
uv run python scripts/create_test_invoice.py --scenario all

# Output directory: ./test_invoices/
# Files created:
# - test_invoice_standard_YYYYMMDD_HHMMSS.pdf
# - test_invoice_complex_YYYYMMDD_HHMMSS.pdf
# - test_invoice_minimal_YYYYMMDD_HHMMSS.pdf
# - test_invoice_high_value_YYYYMMDD_HHMMSS.pdf
# - test_invoice_many_items_YYYYMMDD_HHMMSS.pdf
# - test_invoice_error_scenarios_YYYYMMDD_HHMMSS.pdf
```

### Generate Specific Scenario

```bash
# Generate a single standard invoice
uv run python scripts/create_test_invoice.py --scenario standard --count 1

# Generate multiple complex invoices
uv run python scripts/create_test_invoice.py --scenario complex --count 5

# Generate high-value invoices (for testing large amount validation)
uv run python scripts/create_test_invoice.py --scenario high_value --count 3
```

### Custom Output Directory

```bash
# Generate invoices in a custom directory
uv run python scripts/create_test_invoice.py --scenario all --output-dir ./my_test_invoices
```

### Test Generated Invoices

```bash
# Test all generated invoices
uv run python scripts/test_invoice_generation.py

# Test a specific invoice file
uv run python scripts/test_invoice_generation.py --file test_invoices/test_invoice_standard_*.pdf

# Save test results to JSON
uv run python scripts/test_invoice_generation.py --output test_results.json
```

## Invoice Scenarios

### 1. Standard Invoice
- **Purpose**: Basic functionality testing
- **Features**: 3-5 line items, standard layout, all required fields
- **Expected**: High confidence extraction, validation passes

### 2. Complex Invoice
- **Purpose**: Advanced parsing capabilities
- **Features**: 8+ line items, freight charges, multiple tax rates, 2-page layout
- **Expected**: Good confidence, tests multi-page handling

### 3. Minimal Invoice
- **Purpose**: Edge case testing
- **Features**: Single line item, minimal information
- **Expected**: Tests minimum field extraction

### 4. High Value Invoice
- **Purpose**: Large amount validation
- **Features**: High-value items ($25K-$100K), premium services
- **Expected**: Tests high-value validation rules

### 5. Many Items Invoice
- **Purpose**: Stress testing
- **Features**: 25+ line items, varied products
- **Expected**: Tests table parsing and memory handling

### 6. Error Scenarios Invoice
- **Purpose**: Negative testing and validation
- **Features**: Missing fields, invalid dates, negative amounts, mismatched calculations
- **Expected**: Low confidence, validation failures, error detection

## Generated Invoice Features

### Professional Layout
- Clean, business-like formatting
- Proper headers and footers
- Professional color scheme
- Consistent typography

### Complete Information
- **Vendor Details**: Name, address, phone, email, tax ID
- **Customer Information**: Bill-to details
- **Invoice Metadata**: Number, dates, PO reference, terms
- **Line Items**: SKU, description, quantity, unit price, amount
- **Financial Calculations**: Subtotal, tax, freight, total
- **Payment Information**: Bank details, terms

### Advanced Features
- **Barcodes**: Code128 barcodes with invoice numbers
- **QR Codes**: Payment information encoded
- **Multiple Currencies**: USD support (easily extensible)
- **Tax Calculations**: Various tax rates (0%, 6%, 7.5%, 8%, 10%)
- **Date Variations**: Realistic date ranges and formats

## System Integration

### Extraction Testing
The generated invoices test the Docling service's ability to extract:
- Header information using regex patterns
- Table data for line items
- Currency and amount parsing
- Date format normalization

### Validation Testing
Invoices test validation rules for:
- Required field presence
- Amount accuracy and calculations
- Date format validation
- Business rule compliance
- Confidence threshold checking

### Confidence Scoring
Each invoice generation provides data to test:
- Field-level confidence scores
- Overall document confidence
- Pattern matching reliability
- OCR accuracy assessment

## Customization

### Adding New Vendors
Edit the `_get_vendor_data()` method in the generator to add new vendor information:
```python
{
    "name": "Your Company Inc.",
    "address": "123 Business Ave\nCity, ST 12345",
    "phone": "(555) 123-4567",
    "email": "billing@yourcompany.com",
    "tax_id": "12-3456789",
    "bank": "Bank Name",
    "account": "1234567890",
    "routing": "021000021"
}
```

### Adding New Products
Edit the `_get_product_data()` method to add new products/services:
```python
{"sku": "PROD-001", "description": "Your Product/Service", "unit_price": 100.00}
```

### Custom Scenarios
Add new scenarios by:
1. Creating a new scenario name in `generate_invoice_data()`
2. Adding a corresponding `_generate_*_line_items()` method
3. Updating the scenario list in the main function

## Dependencies

### Required
- `reportlab>=4.4.4` - PDF generation
- Standard Python libraries (datetime, pathlib, etc.)

### Optional (enhanced features)
- `python-barcode>=0.15.1` - Barcode generation
- `qrcode[pil]>=7.4.2` - QR code generation

The script will work without the optional libraries, but will skip barcode/QR code generation.

## Best Practices

### For Testing
1. **Start Simple**: Test with standard invoices first
2. **Progressive Complexity**: Move to complex scenarios after basic validation
3. **Edge Cases**: Use error scenarios to test validation logic
4. **Batch Testing**: Generate multiple invoices for statistical analysis

### For Development
1. **Version Control**: Track invoice changes with git
2. **Regression Testing**: Keep a set of standard test invoices
3. **Performance Monitoring**: Time the extraction process
4. **Confidence Tracking**: Monitor extraction quality over time

### Troubleshooting

#### Common Issues
1. **Import Errors**: Ensure all dependencies are installed with `uv sync`
2. **Permission Errors**: Check write permissions for output directory
3. **Font Issues**: The script uses standard ReportLab fonts that should be available
4. **Memory Issues**: For "many_items" scenario, ensure sufficient system memory

#### Validation Failures
If generated invoices fail validation:
1. Check the validation rules in `app/services/validation_service.py`
2. Review confidence thresholds in system configuration
3. Examine extraction patterns in `app/services/docling_service.py`
4. Use the test script to get detailed error information

## Integration with CI/CD

### Automated Testing
Include invoice generation and testing in your CI pipeline:
```yaml
# Example GitHub Actions step
- name: Test Invoice Processing
  run: |
    uv run python scripts/create_test_invoice.py --scenario standard
    uv run python scripts/test_invoice_generation.py --output test_results.json
```

### Performance Monitoring
Track extraction performance and confidence scores over time to detect system degradation.

## Support

For issues or questions:
1. Check the system logs for detailed error information
2. Review the Docling and validation service configurations
3. Test with simpler scenarios to isolate the problem
4. Consult the main project documentation

## Future Enhancements

Potential improvements:
1. **Multi-language Support**: Add invoices in different languages
2. **Currency Support**: Generate invoices with various currencies
3. **Template Variations**: More invoice layout templates
4. **Image Integration**: Add company logos and signatures
5. **Handwritten Elements**: Simulate scanned document quality variations
6. **Batch Generation**: Generate large datasets for performance testing