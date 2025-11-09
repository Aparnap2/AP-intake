"""
Schema validation service for AP Intake system.

This service provides schema validation, data contract enforcement,
and version compatibility checking for all invoice data.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from app.schemas.schema_registry import (
    schema_registry,
    SchemaInfo,
    SchemaCompatibilityReport,
    validate_data,
    check_compatibility
)
from app.models.schemas import InvoiceExtractionResult

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Schema validation error."""
    pass


class SchemaVersionError(Exception):
    """Schema version error."""
    pass


class SchemaService:
    """
    Service for managing schema validation and data contracts.

    Provides:
    - Data validation against schemas
    - Schema version compatibility checking
    - Contract compliance verification
    - Migration path analysis
    """

    def __init__(self):
        self.registry = schema_registry
        self._ensure_default_schemas()

    def _ensure_default_schemas(self):
        """Ensure default schemas are registered."""
        # Import and register default schemas
        from app.schemas.json_schemas import (
            PreparedBillSchema,
            VendorSchema,
            LineItemSchema,
            ExtractionResultSchema,
            ValidationResultSchema,
            ExportFormatSchema
        )

        default_schemas = [
            ("PreparedBill", "1.0.0", PreparedBillSchema(version="1.0.0").properties),
            ("Vendor", "1.0.0", VendorSchema(version="1.0.0").properties),
            ("LineItem", "1.0.0", LineItemSchema(version="1.0.0").properties),
            ("ExtractionResult", "1.0.0", ExtractionResultSchema(version="1.0.0").properties),
            ("ValidationResult", "1.0.0", ValidationResultSchema(version="1.0.0").properties),
            ("ExportFormat", "1.0.0", ExportFormatSchema(version="1.0.0").properties),
        ]

        for name, version, schema_def in default_schemas:
            try:
                existing = self.registry.get_schema(name, version)
                if not existing:
                    self.registry.register_schema(
                        name=name,
                        version=version,
                        schema_definition=schema_def,
                        description=f"Default {name} schema version {version}"
                    )
                    logger.info(f"Registered default schema {name}:{version}")
            except Exception as e:
                logger.warning(f"Failed to register default schema {name}:{version}: {e}")

    def validate_invoice_extraction(
        self,
        extraction_result: InvoiceExtractionResult,
        schema_version: Optional[str] = None,
        strict_mode: bool = True
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate invoice extraction result against schema.

        Args:
            extraction_result: Invoice extraction result to validate
            schema_version: Schema version to validate against (if None, uses latest)
            strict_mode: If True, raises exceptions for validation errors

        Returns:
            Tuple of (is_valid, errors, validation_metadata)

        Raises:
            SchemaValidationError: If validation fails and strict_mode is True
            SchemaVersionError: If schema version is not found
        """
        try:
            # Convert extraction result to dict
            extraction_dict = extraction_result.model_dump()

            # Add required schema fields
            extraction_dict.update({
                "extraction_id": str(UUID()),  # Generate if not present
                "invoice_id": str(extraction_dict.get("invoice_id", UUID())),
                "extraction_timestamp": extraction_dict.get("extraction_timestamp", datetime.utcnow().isoformat()),
                "parser_version": extraction_dict.get("metadata", {}).get("parser_version", "1.0.0"),
                "rules_version": "1.0.0",  # Current rules version
            })

            # Validate against ExtractionResult schema
            is_valid, errors = validate_data(
                extraction_dict,
                "ExtractionResult",
                schema_version
            )

            validation_metadata = {
                "schema_name": "ExtractionResult",
                "schema_version": schema_version or "latest",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "strict_mode": strict_mode,
                "field_count": len(extraction_dict),
                "has_header": "header" in extraction_dict,
                "line_items_count": len(extraction_dict.get("lines", [])),
                "has_confidence": "confidence" in extraction_dict,
                "has_metadata": "metadata" in extraction_dict
            }

            if not is_valid and strict_mode:
                raise SchemaValidationError(f"Schema validation failed: {errors}")

            return is_valid, errors, validation_metadata

        except Exception as e:
            if isinstance(e, (SchemaValidationError, SchemaVersionError)):
                raise

            logger.error(f"Unexpected error during invoice extraction validation: {e}")
            if strict_mode:
                raise SchemaValidationError(f"Validation error: {e}")
            return False, [str(e)], {"error": str(e)}

    def validate_prepared_bill(
        self,
        prepared_bill_data: Dict[str, Any],
        schema_version: Optional[str] = None,
        strict_mode: bool = True
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate prepared bill data against schema.

        Args:
            prepared_bill_data: Prepared bill data to validate
            schema_version: Schema version to validate against
            strict_mode: If True, raises exceptions for validation errors

        Returns:
            Tuple of (is_valid, errors, validation_metadata)
        """
        try:
            # Ensure required fields are present
            required_fields = ["bill_id", "version", "rules_version", "parser_version"]
            for field in required_fields:
                if field not in prepared_bill_data:
                    if field in ["version", "rules_version", "parser_version"]:
                        prepared_bill_data[field] = "1.0.0"
                    else:
                        raise SchemaValidationError(f"Missing required field: {field}")

            # Validate against PreparedBill schema
            is_valid, errors = validate_data(
                prepared_bill_data,
                "PreparedBill",
                schema_version
            )

            validation_metadata = {
                "schema_name": "PreparedBill",
                "schema_version": schema_version or "latest",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "strict_mode": strict_mode,
                "bill_id": prepared_bill_data.get("bill_id"),
                "has_vendor": "vendor" in prepared_bill_data,
                "has_header": "bill_header" in prepared_bill_data,
                "line_items_count": len(prepared_bill_data.get("line_items", [])),
                "export_ready": prepared_bill_data.get("export_ready", False)
            }

            if not is_valid and strict_mode:
                raise SchemaValidationError(f"PreparedBill validation failed: {errors}")

            return is_valid, errors, validation_metadata

        except Exception as e:
            if isinstance(e, (SchemaValidationError, SchemaVersionError)):
                raise

            logger.error(f"Unexpected error during prepared bill validation: {e}")
            if strict_mode:
                raise SchemaValidationError(f"Validation error: {e}")
            return False, [str(e)], {"error": str(e)}

    def validate_vendor_data(
        self,
        vendor_data: Dict[str, Any],
        schema_version: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate vendor data against schema."""
        return validate_data(vendor_data, "Vendor", schema_version)

    def validate_line_items(
        self,
        line_items: List[Dict[str, Any]],
        schema_version: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate line items against schema."""
        if not isinstance(line_items, list):
            return False, ["Line items must be a list"]

        all_errors = []
        for i, item in enumerate(line_items):
            is_valid, errors = validate_data(item, "LineItem", schema_version)
            if not is_valid:
                all_errors.extend([f"Line {i + 1}: {error}" for error in errors])

        return len(all_errors) == 0, all_errors

    def check_schema_compatibility(
        self,
        schema_name: str,
        from_version: str,
        to_version: str
    ) -> SchemaCompatibilityReport:
        """Check compatibility between schema versions."""
        return check_compatibility(schema_name, from_version, to_version)

    def get_latest_schema_version(self, schema_name: str) -> Optional[str]:
        """Get the latest version of a schema."""
        schema_info = self.registry.get_schema(schema_name)
        return schema_info.version if schema_info else None

    def validate_api_request(
        self,
        request_data: Dict[str, Any],
        endpoint_schema: str,
        request_version: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate API request against endpoint schema."""
        try:
            # Validate against appropriate schema based on endpoint
            if endpoint_schema == "invoice_upload":
                # Validate file upload metadata
                required_fields = ["file_name", "file_size"]
                for field in required_fields:
                    if field not in request_data:
                        return False, [f"Missing required field: {field}"]

            elif endpoint_schema == "extraction_result":
                # Validate extraction result format
                return self.validate_invoice_extraction(
                    request_data,
                    schema_version=request_version,
                    strict_mode=False
                )

            elif endpoint_schema == "prepared_bill":
                # Validate prepared bill format
                return self.validate_prepared_bill(
                    request_data,
                    schema_version=request_version,
                    strict_mode=False
                )

            # Default validation
            return True, []

        except Exception as e:
            logger.error(f"API request validation error: {e}")
            return False, [str(e)]

    def validate_api_response(
        self,
        response_data: Dict[str, Any],
        endpoint_schema: str,
        response_version: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate API response against endpoint schema."""
        try:
            # Similar to request validation but for response format
            if endpoint_schema == "invoice_list":
                # Validate list response structure
                if "invoices" not in response_data or not isinstance(response_data["invoices"], list):
                    return False, ["Response must contain 'invoices' array"]

                # Validate each invoice in the list
                for i, invoice in enumerate(response_data["invoices"]):
                    is_valid, errors = self.validate_invoice_extraction(
                        invoice,
                        schema_version=response_version,
                        strict_mode=False
                    )
                    if not is_valid:
                        return False, [f"Invoice {i + 1}: {errors}"]

            elif endpoint_schema == "extraction_detail":
                # Validate detailed extraction response
                return self.validate_invoice_extraction(
                    response_data,
                    schema_version=response_version,
                    strict_mode=False
                )

            return True, []

        except Exception as e:
            logger.error(f"API response validation error: {e}")
            return False, [str(e)]

    def add_version_metadata(
        self,
        data: Dict[str, Any],
        schema_name: str,
        schema_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add version metadata to data.

        Args:
            data: Data to add metadata to
            schema_name: Schema name
            schema_version: Schema version (if None, uses latest)

        Returns:
            Data with added version metadata
        """
        if schema_version is None:
            schema_version = self.get_latest_schema_version(schema_name) or "1.0.0"

        # Add version fields based on schema type
        if schema_name == "PreparedBill":
            data.update({
                "version": schema_version,
                "rules_version": "1.0.0",
                "parser_version": data.get("parser_version", "1.0.0")
            })
        elif schema_name == "ExtractionResult":
            data.update({
                "rules_version": "1.0.0",
                "parser_version": data.get("parser_version", "1.0.0")
            })

        return data

    def get_schema_info(self, schema_name: str, version: Optional[str] = None) -> Optional[SchemaInfo]:
        """Get schema information."""
        return self.registry.get_schema(schema_name, version)

    def list_available_schemas(self) -> Dict[str, List[str]]:
        """List all available schemas and their versions."""
        return {
            name: [schema.version for schema in schemas]
            for name, schemas in self.registry.list_schemas().items()
        }

    def export_schema_documentation(
        self,
        schema_name: str,
        version: Optional[str] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export schema documentation."""
        schema_info = self.get_schema_info(schema_name, version)
        if not schema_info:
            raise SchemaVersionError(f"Schema {schema_name}:{version or 'latest'} not found")

        return self.registry.export_schema(schema_name, version, format)

    def validate_contract_compliance(
        self,
        data: Dict[str, Any],
        contract_requirements: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate data against custom contract requirements.

        Args:
            data: Data to validate
            contract_requirements: Custom contract requirements

        Returns:
            Tuple of (is_compliant, compliance_issues)
        """
        issues = []

        # Check required fields
        required_fields = contract_requirements.get("required_fields", [])
        for field in required_fields:
            if field not in data:
                issues.append(f"Missing required contract field: {field}")

        # Check field constraints
        field_constraints = contract_requirements.get("field_constraints", {})
        for field, constraints in field_constraints.items():
            if field in data:
                value = data[field]
                # Check type constraints
                if "type" in constraints:
                    expected_type = constraints["type"]
                    if expected_type == "string" and not isinstance(value, str):
                        issues.append(f"Field {field} must be string")
                    elif expected_type == "number" and not isinstance(value, (int, float)):
                        issues.append(f"Field {field} must be number")
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        issues.append(f"Field {field} must be boolean")

                # Check value constraints
                if "min_value" in constraints and isinstance(value, (int, float)):
                    if value < constraints["min_value"]:
                        issues.append(f"Field {field} value {value} below minimum {constraints['min_value']}")

                if "max_value" in constraints and isinstance(value, (int, float)):
                    if value > constraints["max_value"]:
                        issues.append(f"Field {field} value {value} above maximum {constraints['max_value']}")

                if "allowed_values" in constraints:
                    if value not in constraints["allowed_values"]:
                        issues.append(f"Field {field} value {value} not in allowed values: {constraints['allowed_values']}")

        return len(issues) == 0, issues


# Global schema service instance
schema_service = SchemaService()


# Convenience functions
def validate_invoice_extraction(
    extraction_result: InvoiceExtractionResult,
    schema_version: Optional[str] = None,
    strict_mode: bool = True
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate invoice extraction result."""
    return schema_service.validate_invoice_extraction(
        extraction_result,
        schema_version,
        strict_mode
    )


def validate_prepared_bill(
    prepared_bill_data: Dict[str, Any],
    schema_version: Optional[str] = None,
    strict_mode: bool = True
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate prepared bill data."""
    return schema_service.validate_prepared_bill(
        prepared_bill_data,
        schema_version,
        strict_mode
    )


def validate_api_request(
    request_data: Dict[str, Any],
    endpoint_schema: str,
    request_version: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """Validate API request."""
    return schema_service.validate_api_request(
        request_data,
        endpoint_schema,
        request_version
    )


def validate_api_response(
    response_data: Dict[str, Any],
    endpoint_schema: str,
    response_version: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """Validate API response."""
    return schema_service.validate_api_response(
        response_data,
        endpoint_schema,
        response_version
    )