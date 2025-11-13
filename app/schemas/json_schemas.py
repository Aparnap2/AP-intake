"""
JSON Schema definitions for AP Intake system.

This module contains all JSON schema definitions with versioning support
for invoice data structures, validation results, and export formats.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict
import jsonschema


class SchemaVersion(BaseModel):
    """Schema version information."""
    major: int = Field(..., ge=0)
    minor: int = Field(..., ge=0)
    patch: int = Field(..., ge=0)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_string(cls, version_str: str) -> "SchemaVersion":
        """Parse version string."""
        parts = version_str.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version_str}")
        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2])
        )

    def is_compatible_with(self, other: "SchemaVersion") -> bool:
        """Check if this version is compatible with another version."""
        # Major version must match, minor can be higher, patch can be different
        return self.major == other.major and self.minor >= other.minor


class BaseSchema(BaseModel):
    """Base schema with version and metadata."""
    version: str = Field(..., description="Schema version")
    schema_name: str = Field(..., description="Schema name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = Field(None, description="Schema description")

    model_config = ConfigDict(extra="forbid")


# Core Schema Definitions

class VendorSchema(BaseSchema):
    """Vendor information schema."""
    schema_name: str = Field(default="Vendor")

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "vendor_id": {
                "type": ["string", "null"],
                "description": "Unique vendor identifier"
            },
            "vendor_name": {
                "type": ["string", "null"],
                "minLength": 1,
                "maxLength": 200,
                "description": "Vendor/Company name"
            },
            "vendor_address": {
                "type": ["object", "null"],
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "postal_code": {"type": "string"},
                    "country": {"type": "string"}
                },
                "additionalProperties": False
            },
            "vendor_tax_id": {
                "type": ["string", "null"],
                "maxLength": 50,
                "pattern": "^[A-Z0-9-]*$",
                "description": "Vendor tax ID/ABN"
            },
            "vendor_email": {
                "type": ["string", "null"],
                "format": "email",
                "description": "Vendor email address"
            },
            "vendor_phone": {
                "type": ["string", "null"],
                "description": "Vendor phone number"
            }
        },
        "required": [],
        "additionalProperties": False
    })


class LineItemSchema(BaseSchema):
    """Line item schema."""
    schema_name: str = Field(default="LineItem", )

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "line_number": {
                "type": ["integer", "null"],
                "minimum": 1,
                "description": "Line number on invoice"
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "maxLength": 500,
                "description": "Line item description"
            },
            "quantity": {
                "type": "number",
                "minimum": 0,
                "multipleOf": 0.01,
                "description": "Quantity"
            },
            "unit_price": {
                "type": "number",
                "minimum": 0,
                "multipleOf": 0.01,
                "description": "Unit price"
            },
            "total_amount": {
                "type": "number",
                "minimum": 0,
                "multipleOf": 0.01,
                "description": "Total amount"
            },
            "item_code": {
                "type": ["string", "null"],
                "maxLength": 50,
                "description": "Product/service code"
            },
            "gl_account": {
                "type": ["string", "null"],
                "maxLength": 50,
                "description": "General ledger account"
            },
            "tax_rate": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 1,
                "multipleOf": 0.0001,
                "description": "Tax rate (decimal)"
            },
            "tax_amount": {
                "type": ["number", "null"],
                "minimum": 0,
                "multipleOf": 0.01,
                "description": "Tax amount"
            }
        },
        "required": ["description", "quantity", "unit_price", "total_amount"],
        "additionalProperties": False
    })


class ExtractionResultSchema(BaseSchema):
    """Extraction result schema."""
    schema_name: str = Field(default="ExtractionResult", )

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "extraction_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique extraction identifier"
            },
            "invoice_id": {
                "type": "string",
                "format": "uuid",
                "description": "Associated invoice ID"
            },
            "extraction_timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When extraction was performed"
            },
            "parser_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Version of extraction parser"
            },
            "rules_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Version of validation rules"
            },
            "header": {
                "$ref": "#/definitions/InvoiceHeader"
            },
            "lines": {
                "type": "array",
                "items": {"$ref": "#/definitions/LineItem"},
                "minItems": 0,
                "description": "Line items"
            },
            "confidence": {
                "$ref": "#/definitions/ConfidenceScores"
            },
            "metadata": {
                "$ref": "#/definitions/ExtractionMetadata"
            },
            "processing_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Processing notes and warnings"
            }
        },
        "required": [
            "extraction_id", "invoice_id", "extraction_timestamp",
            "parser_version", "rules_version", "header", "lines",
            "confidence", "metadata"
        ],
        "additionalProperties": False,
        "definitions": {
            "InvoiceHeader": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": ["string", "null"],
                        "maxLength": 50,
                        "description": "Invoice number"
                    },
                    "invoice_date": {
                        "type": ["string", "null"],
                        "format": "date",
                        "description": "Invoice date"
                    },
                    "due_date": {
                        "type": ["string", "null"],
                        "format": "date",
                        "description": "Due date"
                    },
                    "vendor_name": {
                        "type": ["string", "null"],
                        "minLength": 1,
                        "maxLength": 200,
                        "description": "Vendor name"
                    },
                    "vendor_address": {
                        "type": ["object", "null"],
                        "properties": {
                            "street": {"type": "string"},
                            "city": {"type": "string"},
                            "state": {"type": "string"},
                            "postal_code": {"type": "string"},
                            "country": {"type": "string"}
                        },
                        "additionalProperties": False
                    },
                    "vendor_tax_id": {
                        "type": ["string", "null"],
                        "maxLength": 50,
                        "description": "Vendor tax ID"
                    },
                    "subtotal_amount": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "multipleOf": 0.01,
                        "description": "Subtotal before tax"
                    },
                    "tax_amount": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "multipleOf": 0.01,
                        "description": "Total tax amount"
                    },
                    "total_amount": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "multipleOf": 0.01,
                        "description": "Grand total amount"
                    },
                    "currency": {
                        "type": "string",
                        "pattern": "^[A-Z]{3}$",
                        "default": "USD",
                        "description": "3-letter currency code"
                    },
                    "purchase_order": {
                        "type": ["string", "null"],
                        "maxLength": 50,
                        "description": "Purchase order number"
                    }
                },
                "additionalProperties": False
            },
            "LineItem": {
                "type": "object",
                "properties": {
                    "line_number": {"type": ["integer", "null"], "minimum": 1},
                    "description": {"type": "string", "minLength": 1, "maxLength": 500},
                    "quantity": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "unit_price": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "total_amount": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "item_code": {"type": ["string", "null"], "maxLength": 50},
                    "gl_account": {"type": ["string", "null"], "maxLength": 50},
                    "tax_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "tax_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01}
                },
                "required": ["description", "quantity", "unit_price", "total_amount"],
                "additionalProperties": False
            },
            "ConfidenceScores": {
                "type": "object",
                "properties": {
                    "overall": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "description": "Overall confidence score"
                    },
                    "invoice_number_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "default": 0.0
                    },
                    "vendor_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "default": 0.0
                    },
                    "date_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "default": 0.0
                    },
                    "amounts_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "default": 0.0
                    },
                    "line_items_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001,
                        "default": 0.0
                    }
                },
                "required": ["overall"],
                "additionalProperties": False
            },
            "ExtractionMetadata": {
                "type": "object",
                "properties": {
                    "parser_version": {"type": "string"},
                    "processing_time_ms": {"type": "integer", "minimum": 0},
                    "page_count": {"type": "integer", "minimum": 1},
                    "file_size_bytes": {"type": "integer", "minimum": 0},
                    "completeness_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001
                    },
                    "accuracy_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001
                    }
                },
                "required": [
                    "parser_version", "processing_time_ms",
                    "page_count", "file_size_bytes"
                ],
                "additionalProperties": False
            }
        }
    })


class ValidationResultSchema(BaseSchema):
    """Validation result schema."""
    schema_name: str = Field(default="ValidationResult", )

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "validation_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique validation identifier"
            },
            "invoice_id": {
                "type": "string",
                "format": "uuid",
                "description": "Associated invoice ID"
            },
            "validation_timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When validation was performed"
            },
            "rules_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Version of validation rules applied"
            },
            "schema_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Schema version used for validation"
            },
            "checks": {
                "type": "object",
                "properties": {
                    "required_fields_present": {"type": "boolean"},
                    "vendor_recognized": {"type": "boolean"},
                    "amounts_positive": {"type": "boolean"},
                    "dates_logical": {"type": "boolean"},
                    "line_items_balanced": {"type": "boolean"},
                    "tax_calculations_correct": {"type": "boolean"},
                    "duplicate_invoice": {"type": "boolean"}
                },
                "additionalProperties": False
            },
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "severity": {"type": "string", "enum": ["error", "warning", "info"]},
                        "message": {"type": "string"},
                        "rule": {"type": "string"},
                        "suggestion": {"type": ["string", "null"]}
                    },
                    "required": ["field", "severity", "message", "rule"],
                    "additionalProperties": False
                },
                "description": "Validation issues found"
            },
            "warnings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "message": {"type": "string"},
                        "suggestion": {"type": ["string", "null"]}
                    },
                    "required": ["field", "message"],
                    "additionalProperties": False
                },
                "description": "Non-critical issues"
            },
            "summary": {
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean"},
                    "requires_human_review": {"type": "boolean"},
                    "auto_approval_eligible": {"type": "boolean"},
                    "error_count": {"type": "integer", "minimum": 0},
                    "warning_count": {"type": "integer", "minimum": 0},
                    "confidence_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001
                    }
                },
                "required": [
                    "passed", "requires_human_review",
                    "auto_approval_eligible", "error_count",
                    "warning_count", "confidence_score"
                ],
                "additionalProperties": False
            }
        },
        "required": [
            "validation_id", "invoice_id", "validation_timestamp",
            "rules_version", "schema_version", "checks", "issues",
            "warnings", "summary"
        ],
        "additionalProperties": False
    })


class ExportFormatSchema(BaseSchema):
    """Export format schema."""
    schema_name: str = Field(default="ExportFormat", )

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "export_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique export identifier"
            },
            "export_timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When export was generated"
            },
            "format_type": {
                "type": "string",
                "enum": ["csv", "json", "xml", "erp"],
                "description": "Export format type"
            },
            "target_system": {
                "type": "string",
                "description": "Target system for export"
            },
            "schema_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Schema version used for export"
            },
            "prepared_bill": {
                "$ref": "#/definitions/PreparedBill"
            },
            "export_metadata": {
                "type": "object",
                "properties": {
                    "export_version": {"type": "string"},
                    "generator_version": {"type": "string"},
                    "compression_used": {"type": ["boolean", "null"]},
                    "encryption_used": {"type": ["boolean", "null"]},
                    "file_count": {"type": "integer", "minimum": 1},
                    "total_records": {"type": "integer", "minimum": 1}
                },
                "required": ["export_version", "generator_version", "file_count", "total_records"],
                "additionalProperties": False
            }
        },
        "required": [
            "export_id", "export_timestamp", "format_type",
            "target_system", "schema_version", "prepared_bill",
            "export_metadata"
        ],
        "additionalProperties": False,
        "definitions": {
            "PreparedBill": {
                "type": "object",
                "properties": {
                    "bill_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Unique bill identifier"
                    },
                    "vendor": {"$ref": "#/definitions/Vendor"},
                    "bill_header": {"$ref": "#/definitions/BillHeader"},
                    "line_items": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/LineItem"},
                        "minItems": 1
                    },
                    "validation_result": {"$ref": "#/definitions/ValidationSummary"},
                    "export_ready": {
                        "type": "boolean",
                        "description": "Ready for export to target system"
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "updated_at": {
                        "type": "string",
                        "format": "date-time"
                    }
                },
                "required": [
                    "bill_id", "vendor", "bill_header", "line_items",
                    "validation_result", "export_ready", "created_at", "updated_at"
                ],
                "additionalProperties": False,
                "definitions": {
                    "Vendor": {
                        "type": "object",
                        "properties": {
                            "vendor_id": {"type": ["string", "null"]},
                            "vendor_name": {"type": ["string", "null"], "minLength": 1, "maxLength": 200},
                            "vendor_address": {
                                "type": ["object", "null"],
                                "properties": {
                                    "street": {"type": "string"},
                                    "city": {"type": "string"},
                                    "state": {"type": "string"},
                                    "postal_code": {"type": "string"},
                                    "country": {"type": "string"}
                                },
                                "additionalProperties": False
                            },
                            "vendor_tax_id": {"type": ["string", "null"], "maxLength": 50}
                        },
                        "additionalProperties": False
                    },
                    "BillHeader": {
                        "type": "object",
                        "properties": {
                            "invoice_number": {"type": ["string", "null"], "maxLength": 50},
                            "invoice_date": {"type": ["string", "null"], "format": "date"},
                            "due_date": {"type": ["string", "null"], "format": "date"},
                            "subtotal_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01},
                            "tax_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01},
                            "total_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01},
                            "currency": {"type": "string", "pattern": "^[A-Z]{3}$", "default": "USD"},
                            "purchase_order": {"type": ["string", "null"], "maxLength": 50}
                        },
                        "additionalProperties": False
                    },
                    "LineItem": {
                        "type": "object",
                        "properties": {
                            "line_number": {"type": ["integer", "null"], "minimum": 1},
                            "description": {"type": "string", "minLength": 1, "maxLength": 500},
                            "quantity": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                            "unit_price": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                            "total_amount": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                            "item_code": {"type": ["string", "null"], "maxLength": 50},
                            "gl_account": {"type": ["string", "null"], "maxLength": 50}
                        },
                        "required": ["description", "quantity", "unit_price", "total_amount"],
                        "additionalProperties": False
                    },
                    "ValidationSummary": {
                        "type": "object",
                        "properties": {
                            "passed": {"type": "boolean"},
                            "requires_human_review": {"type": "boolean"},
                            "error_count": {"type": "integer", "minimum": 0},
                            "warning_count": {"type": "integer", "minimum": 0},
                            "confidence_score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "multipleOf": 0.001
                            }
                        },
                        "required": [
                            "passed", "requires_human_review",
                            "error_count", "warning_count", "confidence_score"
                        ],
                        "additionalProperties": False
                    }
                }
            }
        }
    })


# Main PreparedBill Schema - combines all components
class PreparedBillSchema(BaseSchema):
    """Complete PreparedBill schema definition."""
    schema_name: str = Field(default="PreparedBill", )

    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "bill_id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique bill identifier"
            },
            "version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Data contract version"
            },
            "rules_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Validation rules version"
            },
            "parser_version": {
                "type": "string",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                "description": "Parser version used for extraction"
            },
            "vendor": {"$ref": "#/definitions/Vendor"},
            "bill_header": {"$ref": "#/definitions/BillHeader"},
            "line_items": {
                "type": "array",
                "items": {"$ref": "#/definitions/LineItem"},
                "minItems": 1
            },
            "extraction_result": {"$ref": "#/definitions/ExtractionResult"},
            "validation_result": {"$ref": "#/definitions/ValidationResult"},
            "export_ready": {
                "type": "boolean",
                "description": "Ready for export to ERP system"
            },
            "created_at": {
                "type": "string",
                "format": "date-time"
            },
            "updated_at": {
                "type": "string",
                "format": "date-time"
            }
        },
        "required": [
            "bill_id", "version", "rules_version", "parser_version",
            "vendor", "bill_header", "line_items", "extraction_result",
            "validation_result", "export_ready", "created_at", "updated_at"
        ],
        "additionalProperties": False,
        "definitions": {
            "Vendor": {
                "type": "object",
                "properties": {
                    "vendor_id": {"type": ["string", "null"]},
                    "vendor_name": {"type": "string", "minLength": 1, "maxLength": 200},
                    "vendor_address": {
                        "type": ["object", "null"],
                        "properties": {
                            "street": {"type": "string"},
                            "city": {"type": "string"},
                            "state": {"type": "string"},
                            "postal_code": {"type": "string"},
                            "country": {"type": "string"}
                        },
                        "additionalProperties": False
                    },
                    "vendor_tax_id": {"type": ["string", "null"], "maxLength": 50}
                },
                "required": ["vendor_name"],
                "additionalProperties": False
            },
            "BillHeader": {
                "type": "object",
                "properties": {
                    "invoice_number": {"type": ["string", "null"], "maxLength": 50},
                    "invoice_date": {"type": "string", "format": "date"},
                    "due_date": {"type": ["string", "null"], "format": "date"},
                    "subtotal_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01},
                    "tax_amount": {"type": ["number", "null"], "minimum": 0, "multipleOf": 0.01},
                    "total_amount": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "currency": {"type": "string", "pattern": "^[A-Z]{3}$", "default": "USD"},
                    "purchase_order": {"type": ["string", "null"], "maxLength": 50}
                },
                "required": ["invoice_date", "total_amount", "currency"],
                "additionalProperties": False
            },
            "LineItem": {
                "type": "object",
                "properties": {
                    "line_number": {"type": ["integer", "null"], "minimum": 1},
                    "description": {"type": "string", "minLength": 1, "maxLength": 500},
                    "quantity": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "unit_price": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "total_amount": {"type": "number", "minimum": 0, "multipleOf": 0.01},
                    "item_code": {"type": ["string", "null"], "maxLength": 50},
                    "gl_account": {"type": ["string", "null"], "maxLength": 50}
                },
                "required": ["description", "quantity", "unit_price", "total_amount"],
                "additionalProperties": False
            },
            "ExtractionResult": {
                "type": "object",
                "properties": {
                    "confidence": {
                        "type": "object",
                        "properties": {
                            "overall": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "multipleOf": 0.001
                            }
                        },
                        "required": ["overall"]
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "processing_time_ms": {"type": "integer", "minimum": 0},
                            "page_count": {"type": "integer", "minimum": 1},
                            "completeness_score": {
                                "type": ["number", "null"],
                                "minimum": 0,
                                "maximum": 1,
                                "multipleOf": 0.001
                            }
                        },
                        "required": ["processing_time_ms", "page_count"]
                    }
                },
                "required": ["confidence", "metadata"]
            },
            "ValidationResult": {
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean"},
                    "requires_human_review": {"type": "boolean"},
                    "error_count": {"type": "integer", "minimum": 0},
                    "warning_count": {"type": "integer", "minimum": 0},
                    "confidence_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "multipleOf": 0.001
                    }
                },
                "required": [
                    "passed", "requires_human_review",
                    "error_count", "warning_count", "confidence_score"
                ]
            }
        }
    })


# Schema registry and utilities
class SchemaRegistry:
    """Registry for managing schema versions."""

    def __init__(self):
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_schemas()

    def _initialize_default_schemas(self):
        """Initialize default schema versions."""
        # Version 1.0.0 schemas
        self.register_schema("PreparedBill", "1.0.0", PreparedBillSchema(version="1.0.0").properties)
        self.register_schema("Vendor", "1.0.0", VendorSchema(version="1.0.0").properties)
        self.register_schema("LineItem", "1.0.0", LineItemSchema(version="1.0.0").properties)
        self.register_schema("ExtractionResult", "1.0.0", ExtractionResultSchema(version="1.0.0").properties)
        self.register_schema("ValidationResult", "1.0.0", ValidationResultSchema(version="1.0.0").properties)
        self.register_schema("ExportFormat", "1.0.0", ExportFormatSchema(version="1.0.0").properties)

    def register_schema(self, name: str, version: str, schema: Dict[str, Any]):
        """Register a schema version."""
        key = f"{name}:{version}"
        self._schemas[key] = schema

    def get_schema(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get a specific schema version."""
        key = f"{name}:{version}"
        return self._schemas.get(key)

    def get_latest_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of a schema."""
        # For now, return the highest version number
        matching_schemas = [(k, v) for k, v in self._schemas.items() if k.startswith(f"{name}:")]
        if not matching_schemas:
            return None

        # Sort by version (simplified)
        latest = max(matching_schemas, key=lambda x: x[0])
        return latest[1]

    def list_schemas(self) -> Dict[str, List[str]]:
        """List all registered schemas and their versions."""
        result = {}
        for key in self._schemas.keys():
            name, version = key.split(":", 1)
            if name not in result:
                result[name] = []
            result[name].append(version)

        # Sort versions
        for versions in result.values():
            versions.sort()

        return result


# Global schema registry instance
schema_registry = SchemaRegistry()


# Utility functions
def get_schema_by_version(name: str, version: str) -> Optional[Dict[str, Any]]:
    """Get schema by name and version."""
    return schema_registry.get_schema(name, version)


def get_latest_schema(name: str) -> Optional[Dict[str, Any]]:
    """Get the latest version of a schema."""
    return schema_registry.get_latest_schema(name)


def validate_data_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate data against a JSON schema.

    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        jsonschema.validate(data, schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [f"Validation error: {e.message} at {'/'.join(str(p) for p in e.absolute_path)}"]
    except jsonschema.SchemaError as e:
        return False, [f"Schema error: {e.message}"]


def check_schema_compatibility(old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Check if a new schema is backward compatible with an old schema.

    Returns:
        Tuple of (is_compatible, compatibility_issues)
    """
    issues = []

    # Basic compatibility checks
    if old_schema.get("type") != new_schema.get("type"):
        issues.append("Type mismatch between schemas")

    if old_schema.get("required") and new_schema.get("required"):
        # Check if any required fields were removed
        old_required = set(old_schema["required"])
        new_required = set(new_schema["required"])

        if not old_required.issubset(new_required):
            removed_fields = old_required - new_required
            issues.append(f"Previously required fields removed: {removed_fields}")

    # Check property changes
    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})

    for field_name, old_field in old_props.items():
        if field_name in new_props:
            new_field = new_props[field_name]

            # Check type compatibility
            if old_field.get("type") != new_field.get("type"):
                issues.append(f"Type changed for field '{field_name}': {old_field.get('type')} -> {new_field.get('type')}")

            # Check constraint tightening
            if "minimum" in old_field and "minimum" in new_field:
                if new_field["minimum"] > old_field["minimum"]:
                    issues.append(f"Minimum constraint tightened for field '{field_name}'")

            if "maxLength" in old_field and "maxLength" in new_field:
                if new_field["maxLength"] < old_field["maxLength"]:
                    issues.append(f"MaxLength constraint tightened for field '{field_name}'")
        else:
            issues.append(f"Field '{field_name}' removed from schema")

    return len(issues) == 0, issues


# Example usage and testing
if __name__ == "__main__":
    # Test schema registration and retrieval
    prepared_bill_schema = get_latest_schema("PreparedBill")
    print(f"Latest PreparedBill schema keys: {list(prepared_bill_schema.keys())}")

    # Test data validation
    test_data = {
        "bill_id": "123e4567-e89b-12d3-a456-426614174000",
        "version": "1.0.0",
        "rules_version": "1.0.0",
        "parser_version": "1.0.0",
        "vendor": {
            "vendor_name": "Test Vendor",
            "vendor_tax_id": "123456789"
        },
        "bill_header": {
            "invoice_date": "2024-01-15",
            "total_amount": 100.50,
            "currency": "USD"
        },
        "line_items": [
            {
                "description": "Test Item",
                "quantity": 1,
                "unit_price": 100.50,
                "total_amount": 100.50
            }
        ],
        "extraction_result": {
            "confidence": {"overall": 0.95},
            "metadata": {"processing_time_ms": 1500, "page_count": 1}
        },
        "validation_result": {
            "passed": True,
            "requires_human_review": False,
            "error_count": 0,
            "warning_count": 0,
            "confidence_score": 0.95
        },
        "export_ready": True,
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z"
    }

    is_valid, errors = validate_data_against_schema(test_data, prepared_bill_schema)
    print(f"Validation result: {is_valid}")
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")