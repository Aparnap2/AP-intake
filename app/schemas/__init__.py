"""
Data contracts and JSON schema management for AP Intake system.

This module provides comprehensive schema definitions, validation, and versioning
for all invoice data structures used throughout the system.
"""

from .json_schemas import (
    PreparedBillSchema,
    VendorSchema,
    LineItemSchema,
    ExtractionResultSchema,
    ValidationResultSchema,
    ExportFormatSchema,
    get_schema_by_version,
    get_latest_schema,
    validate_data_against_schema,
)

from .schema_registry import (
    SchemaRegistry,
    SchemaVersion,
    register_schema,
    get_schema,
    list_schemas,
    check_compatibility,
)

__all__ = [
    # Schema definitions
    "PreparedBillSchema",
    "VendorSchema",
    "LineItemSchema",
    "ExtractionResultSchema",
    "ValidationResultSchema",
    "ExportFormatSchema",

    # Schema utilities
    "get_schema_by_version",
    "get_latest_schema",
    "validate_data_against_schema",

    # Schema registry
    "SchemaRegistry",
    "SchemaVersion",
    "register_schema",
    "get_schema",
    "list_schemas",
    "check_compatibility",
]

# Version information
SCHEMA_VERSION = "1.0.0"
SUPPORTED_VERSIONS = ["1.0.0"]