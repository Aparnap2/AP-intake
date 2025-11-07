"""
Default export template configurations.
"""

from typing import List, Dict, Any

from app.schemas.export_schemas import ExportFieldMapping
from app.models.export_models import ExportFormat


def get_default_export_templates() -> List[Dict[str, Any]]:
    """Get default export template configurations."""

    templates = []

    # Standard CSV Export Template
    standard_csv = {
        "name": "Standard CSV Export",
        "description": "Standard CSV export with basic invoice fields for general use",
        "format": ExportFormat.CSV,
        "field_mappings": [
            {
                "source_field": "id",
                "target_field": "Invoice ID",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.vendor_name",
                "target_field": "Vendor Name",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_no",
                "target_field": "Invoice Number",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_date",
                "target_field": "Invoice Date",
                "field_type": "date",
                "required": True,
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.due_date",
                "target_field": "Due Date",
                "field_type": "date",
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.po_no",
                "target_field": "PO Number",
                "field_type": "string"
            },
            {
                "source_field": "header.currency",
                "target_field": "Currency",
                "field_type": "string",
                "default_value": "USD"
            },
            {
                "source_field": "header.subtotal",
                "target_field": "Subtotal",
                "field_type": "decimal",
                "required": True,
                "transform_function": "currency_format"
            },
            {
                "source_field": "header.tax",
                "target_field": "Tax Amount",
                "field_type": "decimal",
                "transform_function": "currency_format"
            },
            {
                "source_field": "header.total",
                "target_field": "Total Amount",
                "field_type": "decimal",
                "required": True,
                "transform_function": "currency_format"
            },
            {
                "source_field": "lines",
                "target_field": "Line Item Count",
                "field_type": "number"
            },
            {
                "source_field": "metadata.status",
                "target_field": "Processing Status",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "metadata.processed_at",
                "target_field": "Processed Date",
                "field_type": "date",
                "format_string": "%Y-%m-%d %H:%M:%S"
            }
        ],
        "header_config": {
            "title": "Invoice Export Report",
            "date": True,
            "include_timestamp": True,
            "include_filters": True
        },
        "footer_config": {
            "include_totals": True,
            "include_record_count": True,
            "include_export_time": True
        },
        "compression": False,
        "encryption": False
    }
    templates.append(standard_csv)

    # Detailed JSON Export Template
    detailed_json = {
        "name": "Detailed JSON Export",
        "description": "Complete JSON export with all invoice data, line items, and metadata",
        "format": ExportFormat.JSON,
        "field_mappings": [
            {
                "source_field": "id",
                "target_field": "invoice_id",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header",
                "target_field": "invoice_header",
                "field_type": "json",
                "required": True
            },
            {
                "source_field": "lines",
                "target_field": "line_items",
                "field_type": "json",
                "required": True
            },
            {
                "source_field": "metadata.confidence",
                "target_field": "extraction_confidence",
                "field_type": "json"
            },
            {
                "source_field": "metadata.processed_at",
                "target_field": "processed_timestamp",
                "field_type": "date"
            },
            {
                "source_field": "metadata.status",
                "target_field": "processing_status",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "metadata.vendor_id",
                "target_field": "vendor_id",
                "field_type": "string"
            }
        ],
        "header_config": {
            "include_metadata": True,
            "include_system_info": True,
            "include_export_stats": True
        },
        "compression": True,
        "encryption": False
    }
    templates.append(detailed_json)

    # Accounting CSV Export Template
    accounting_csv = {
        "name": "Accounting CSV Export",
        "description": "Accounting-focused CSV export optimized for financial system imports",
        "format": ExportFormat.CSV,
        "field_mappings": [
            {
                "source_field": "header.invoice_no",
                "target_field": "Document Number",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.vendor_name",
                "target_field": "Vendor Name",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_date",
                "target_field": "Document Date",
                "field_type": "date",
                "required": True,
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.due_date",
                "target_field": "Due Date",
                "field_type": "date",
                "required": True,
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.po_no",
                "target_field": "Purchase Order",
                "field_type": "string"
            },
            {
                "source_field": "header.subtotal",
                "target_field": "Net Amount",
                "field_type": "decimal",
                "required": True
            },
            {
                "source_field": "header.tax",
                "target_field": "Tax Amount",
                "field_type": "decimal"
            },
            {
                "source_field": "header.total",
                "target_field": "Gross Amount",
                "field_type": "decimal",
                "required": True
            },
            {
                "source_field": "header.currency",
                "target_field": "Currency Code",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "lines",
                "target_field": "Line Item Count",
                "field_type": "number"
            },
            {
                "source_field": "id",
                "target_field": "Invoice UUID",
                "field_type": "string"
            }
        ],
        "header_config": {
            "title": "Accounts Payable Export",
            "date": True,
            "include_period": True,
            "include_currency_info": True
        },
        "footer_config": {
            "include_financial_totals": True,
            "include_summary_stats": True,
            "include_tax_summary": True
        },
        "compression": False,
        "encryption": False
    }
    templates.append(accounting_csv)

    # QuickBooks Export Template
    quickbooks_json = {
        "name": "QuickBooks Export",
        "description": "QuickBooks-compatible export format for direct API integration",
        "format": ExportFormat.JSON,
        "field_mappings": [
            {
                "source_field": "header.vendor_name",
                "target_field": "VendorRef",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_no",
                "target_field": "DocNumber",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_date",
                "target_field": "TxnDate",
                "field_type": "date",
                "required": True,
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.due_date",
                "target_field": "DueDate",
                "field_type": "date",
                "required": True,
                "format_string": "%Y-%m-%d"
            },
            {
                "source_field": "header.total",
                "target_field": "TotalAmt",
                "field_type": "decimal",
                "required": True
            },
            {
                "source_field": "lines",
                "target_field": "Line",
                "field_type": "json",
                "required": True
            },
            {
                "source_field": "header.po_no",
                "target_field": "PrivateNote",
                "field_type": "string",
                "transform_function": "title_case"
            },
            {
                "source_field": "header.currency",
                "target_field": "CurrencyRef",
                "field_type": "string",
                "required": True
            }
        ],
        "header_config": {
            "quickbooks_format": True,
            "api_version": "v3",
            "include_domain": "QBO",
            "include_sparse": False
        },
        "compression": True,
        "encryption": False
    }
    templates.append(quickbooks_json)

    # Analytics JSON Template
    analytics_json = {
        "name": "Analytics JSON Export",
        "description": "Analytics-focused export with calculated fields and aggregations",
        "format": ExportFormat.JSON,
        "field_mappings": [
            {
                "source_field": "id",
                "target_field": "invoice_id",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.vendor_name",
                "target_field": "vendor",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_date",
                "target_field": "invoice_date",
                "field_type": "date",
                "required": True
            },
            {
                "source_field": "header.total",
                "target_field": "invoice_amount",
                "field_type": "decimal",
                "required": True
            },
            {
                "source_field": "lines",
                "target_field": "line_count",
                "field_type": "number"
            },
            {
                "source_field": "metadata.confidence.overall",
                "target_field": "extraction_confidence_score",
                "field_type": "decimal"
            },
            {
                "source_field": "metadata.processed_at",
                "target_field": "processing_duration_minutes",
                "field_type": "number"
            },
            {
                "source_field": "metadata.status",
                "target_field": "processing_status",
                "field_type": "string"
            }
        ],
        "header_config": {
            "analytics_format": True,
            "include_aggregations": True,
            "include_time_series": True,
            "include_performance_metrics": True
        },
        "compression": True,
        "encryption": False
    }
    templates.append(analytics_json)

    # Audit Export Template
    audit_csv = {
        "name": "Audit Trail Export",
        "description": "Comprehensive audit trail export for compliance and review",
        "format": ExportFormat.CSV,
        "field_mappings": [
            {
                "source_field": "id",
                "target_field": "Invoice UUID",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.vendor_name",
                "target_field": "Vendor",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_no",
                "target_field": "Invoice Number",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "header.invoice_date",
                "target_field": "Invoice Date",
                "field_type": "date",
                "required": True
            },
            {
                "source_field": "header.total",
                "target_field": "Invoice Total",
                "field_type": "decimal",
                "required": True
            },
            {
                "source_field": "metadata.status",
                "target_field": "Processing Status",
                "field_type": "string",
                "required": True
            },
            {
                "source_field": "metadata.processed_at",
                "target_field": "Processing Timestamp",
                "field_type": "date",
                "required": True
            },
            {
                "source_field": "metadata.confidence.overall",
                "target_field": "Confidence Score",
                "field_type": "decimal"
            },
            {
                "source_field": "file_name",
                "target_field": "Source File",
                "field_type": "string"
            },
            {
                "source_field": "file_size",
                "target_field": "File Size",
                "field_type": "string"
            }
        ],
        "header_config": {
            "title": "Invoice Processing Audit Trail",
            "date": True,
            "include_system_info": True,
            "include_compliance_info": True
        },
        "footer_config": {
            "include_audit_summary": True,
            "include_compliance_metrics": True,
            "include_data_quality_metrics": True
        },
        "compression": True,
        "encryption": True
    }
    templates.append(audit_csv)

    return templates


def get_export_template_by_name(template_name: str) -> Dict[str, Any]:
    """Get a specific template by name."""
    templates = get_default_export_templates()
    for template in templates:
        if template["name"] == template_name:
            return template
    return None


def get_templates_by_format(export_format: ExportFormat) -> List[Dict[str, Any]]:
    """Get all templates for a specific format."""
    templates = get_default_export_templates()
    return [t for t in templates if t["format"] == export_format]


# Template validation rules
def get_validation_rules_for_template(template_name: str) -> List[Dict[str, Any]]:
    """Get validation rules for a specific template."""

    validation_rules = {
        "Standard CSV Export": [
            {
                "field_path": "header.vendor_name",
                "rule_type": "required",
                "rule_config": {},
                "error_message": "Vendor name is required",
                "severity": "error"
            },
            {
                "field_path": "header.invoice_no",
                "rule_type": "required",
                "rule_config": {},
                "error_message": "Invoice number is required",
                "severity": "error"
            },
            {
                "field_path": "header.total",
                "rule_type": "numeric_range",
                "rule_config": {"min": 0, "max": 999999999.99},
                "error_message": "Total amount must be positive",
                "severity": "error"
            }
        ],
        "Accounting CSV Export": [
            {
                "field_path": "header.invoice_no",
                "rule_type": "pattern",
                "rule_config": {"pattern": r"^[A-Za-z0-9\-_/]+$"},
                "error_message": "Invoice number contains invalid characters",
                "severity": "warning"
            },
            {
                "field_path": "header.currency",
                "rule_type": "in_list",
                "rule_config": {"allowed_values": ["USD", "EUR", "GBP", "CAD", "AUD"]},
                "error_message": "Unsupported currency code",
                "severity": "error"
            }
        ],
        "QuickBooks Export": [
            {
                "field_path": "header.vendor_name",
                "rule_type": "required",
                "rule_config": {},
                "error_message": "Vendor name required for QuickBooks",
                "severity": "error"
            },
            {
                "field_path": "header.invoice_no",
                "rule_type": "pattern",
                "rule_config": {"pattern": r"^[A-Za-z0-9]{1,21}$"},
                "error_message": "QuickBooks doc number max 21 chars",
                "severity": "error"
            }
        ]
    }

    return validation_rules.get(template_name, [])


# Template transformation examples
def get_transformation_examples() -> Dict[str, List[Dict[str, str]]]:
    """Get examples of field transformations."""

    return {
        "date_formatting": [
            {
                "input": "2024-01-15T10:30:00Z",
                "format_string": "%Y-%m-%d",
                "output": "2024-01-15"
            },
            {
                "input": "2024-01-15T10:30:00Z",
                "format_string": "%B %d, %Y",
                "output": "January 15, 2024"
            }
        ],
        "currency_formatting": [
            {
                "input": 1234.56,
                "transform_function": "currency_format",
                "output": "$1,234.56"
            },
            {
                "input": 0,
                "transform_function": "currency_format",
                "output": "$0.00"
            }
        ],
        "text_transformations": [
            {
                "input": "test vendor name",
                "transform_function": "uppercase",
                "output": "TEST VENDOR NAME"
            },
            {
                "input": "test vendor name",
                "transform_function": "title_case",
                "output": "Test Vendor Name"
            }
        ]
    }