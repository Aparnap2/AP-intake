"""
Test JSON schema syntax validation.
"""

import pytest
import json
from jsonschema import validate, ValidationError

from app.schemas.json_schemas import (
    PreparedBillSchema,
    VendorSchema,
    LineItemSchema,
    ExtractionResultSchema,
    ValidationResultSchema,
    ExportFormatSchema,
    get_latest_schema,
    validate_data_against_schema
)


class TestJSONSchemaSyntax:
    """Test JSON schema definitions for syntax validity."""

    def test_prepared_bill_schema_syntax(self):
        """Test PreparedBill schema syntax."""
        schema_def = PreparedBillSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def
        assert "required" in schema_def

    def test_vendor_schema_syntax(self):
        """Test Vendor schema syntax."""
        schema_def = VendorSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def

    def test_line_item_schema_syntax(self):
        """Test LineItem schema syntax."""
        schema_def = LineItemSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def
        assert "required" in schema_def

    def test_extraction_result_schema_syntax(self):
        """Test ExtractionResult schema syntax."""
        schema_def = ExtractionResultSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def
        assert "required" in schema_def
        assert "definitions" in schema_def

    def test_validation_result_schema_syntax(self):
        """Test ValidationResult schema syntax."""
        schema_def = ValidationResultSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def
        assert "required" in schema_def

    def test_export_format_schema_syntax(self):
        """Test ExportFormat schema syntax."""
        schema_def = ExportFormatSchema(version="1.0.0").properties

        # Validate that it's a valid JSON Schema
        assert isinstance(schema_def, dict)
        assert "type" in schema_def
        assert schema_def["type"] == "object"
        assert "properties" in schema_def
        assert "required" in schema_def

    def test_schema_references_are_valid(self):
        """Test that schema references are valid."""
        prepared_bill_schema = PreparedBillSchema(version="1.0.0").properties

        # Check that $ref values are properly formatted
        self._check_references(prepared_bill_schema)

        extraction_schema = ExtractionResultSchema(version="1.0.0").properties
        self._check_references(extraction_schema)

    def _check_references(self, schema: dict):
        """Recursively check schema references."""
        if isinstance(schema, dict):
            if "$ref" in schema:
                ref = schema["$ref"]
                assert ref.startswith("#/definitions/"), f"Invalid reference format: {ref}"

            for value in schema.values():
                self._check_references(value)
        elif isinstance(schema, list):
            for item in schema:
                self._check_references(item)

    def test_all_schemas_have_required_fields(self):
        """Test that all schemas have required fields."""
        schemas = [
            (PreparedBillSchema(version="1.0.0").properties, ["bill_id", "version", "rules_version", "parser_version"]),
            (ExtractionResultSchema(version="1.0.0").properties, ["extraction_id", "invoice_id", "extraction_timestamp"]),
            (ValidationResultSchema(version="1.0.0").properties, ["validation_id", "invoice_id", "validation_timestamp"]),
        ]

        for schema_def, expected_required in schemas:
            required = schema_def.get("required", [])
            for field in expected_required:
                assert field in required, f"Required field {field} missing from schema"

    def test_schema_definitions_are_complete(self):
        """Test that schema definitions are complete."""
        extraction_schema = ExtractionResultSchema(version="1.0.0").properties
        definitions = extraction_schema.get("definitions", {})

        # Check that all referenced definitions exist
        expected_definitions = [
            "InvoiceHeader",
            "LineItem",
            "ConfidenceScores",
            "ExtractionMetadata"
        ]

        for definition_name in expected_definitions:
            assert definition_name in definitions, f"Definition {definition_name} missing"

        # Check that definitions have required structure
        for definition_name, definition_def in definitions.items():
            assert isinstance(definition_def, dict), f"Definition {definition_name} must be a dictionary"
            assert "type" in definition_def, f"Definition {definition_name} must have a type"
            assert "properties" in definition_def, f"Definition {definition_name} must have properties"

    def test_schema_validation_with_valid_data(self):
        """Test schema validation with valid data."""
        prepared_bill_schema = get_latest_schema("PreparedBill")

        valid_data = {
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

        is_valid, errors = validate_data_against_schema(valid_data, prepared_bill_schema)
        assert is_valid, f"Valid data should pass validation: {errors}"

    def test_schema_validation_with_invalid_data(self):
        """Test schema validation with invalid data."""
        prepared_bill_schema = get_latest_schema("PreparedBill")

        invalid_data = {
            # Missing required fields
            "vendor": {
                "vendor_name": "Test Vendor"
            },
            "bill_header": {
                "total_amount": "invalid_amount",  # Invalid type
                "currency": "USD"
            }
        }

        is_valid, errors = validate_data_against_schema(invalid_data, prepared_bill_schema)
        assert not is_valid, "Invalid data should fail validation"
        assert len(errors) > 0, "Should have validation errors"

    def test_line_item_schema_constraints(self):
        """Test LineItem schema constraints."""
        line_item_schema = get_latest_schema("LineItem")

        # Valid line item
        valid_item = {
            "description": "Test Item",
            "quantity": 1,
            "unit_price": 100.50,
            "total_amount": 100.50
        }

        is_valid, errors = validate_data_against_schema(valid_item, line_item_schema)
        assert is_valid, f"Valid line item should pass validation: {errors}"

        # Invalid quantity (negative)
        invalid_item = {
            "description": "Test Item",
            "quantity": -1,
            "unit_price": 100.50,
            "total_amount": 100.50
        }

        is_valid, errors = validate_data_against_schema(invalid_item, line_item_schema)
        assert not is_valid, "Negative quantity should fail validation"

    def test_vendor_schema_validation(self):
        """Test Vendor schema validation."""
        vendor_schema = get_latest_schema("Vendor")

        # Valid vendor
        valid_vendor = {
            "vendor_name": "Test Vendor Inc.",
            "vendor_tax_id": "123456789"
        }

        is_valid, errors = validate_data_against_schema(valid_vendor, vendor_schema)
        assert is_valid, f"Valid vendor should pass validation: {errors}"

        # Vendor with address
        vendor_with_address = {
            "vendor_name": "Test Vendor Inc.",
            "vendor_address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "TS",
                "postal_code": "12345",
                "country": "US"
            },
            "vendor_tax_id": "123456789"
        }

        is_valid, errors = validate_data_against_schema(vendor_with_address, vendor_schema)
        assert is_valid, f"Vendor with address should pass validation: {errors}"

    def test_extraction_result_schema_validation(self):
        """Test ExtractionResult schema validation."""
        extraction_schema = get_latest_schema("ExtractionResult")

        valid_extraction = {
            "extraction_id": "123e4567-e89b-12d3-a456-426614174000",
            "invoice_id": "123e4567-e89b-12d3-a456-426614174001",
            "extraction_timestamp": "2024-01-15T10:00:00Z",
            "parser_version": "1.0.0",
            "rules_version": "1.0.0",
            "header": {
                "invoice_number": "INV-001",
                "invoice_date": "2024-01-15",
                "total_amount": 100.50,
                "currency": "USD"
            },
            "lines": [
                {
                    "description": "Test Item",
                    "quantity": 1,
                    "unit_price": 100.50,
                    "total_amount": 100.50
                }
            ],
            "confidence": {
                "overall": 0.95,
                "vendor_confidence": 0.92
            },
            "metadata": {
                "processing_time_ms": 1500,
                "page_count": 1,
                "file_size_bytes": 1024
            }
        }

        is_valid, errors = validate_data_against_schema(valid_extraction, extraction_schema)
        assert is_valid, f"Valid extraction should pass validation: {errors}"