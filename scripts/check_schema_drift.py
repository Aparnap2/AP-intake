#!/usr/bin/env python3
"""
Schema drift detection script.

This script checks for unauthorized changes to schema definitions
and validates that all changes follow proper versioning and compatibility rules.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.schemas.schema_registry import schema_registry, check_compatibility
from app.schemas.json_schemas import get_latest_schema, validate_data_against_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaDriftDetector:
    """Detects and reports schema drift."""

    def __init__(self, registry_path: Optional[str] = None):
        self.registry = schema_registry
        self.drift_detected = False
        self.issues: List[str] = []

    def check_schema_definitions(self) -> bool:
        """Check all schema definitions for validity."""
        logger.info("Checking schema definitions...")

        schemas = self.registry.list_schemas()
        all_valid = True

        for schema_name, versions in schemas.items():
            for version in versions:
                schema_info = self.registry.get_schema(schema_name, version)
                if not schema_info:
                    self.issues.append(f"Schema {schema_name}:{version} not found in registry")
                    all_valid = False
                    continue

                # Validate schema against JSON Schema meta-schema
                try:
                    # Basic validation - ensure required fields are present
                    if not isinstance(schema_info.schema_definition, dict):
                        self.issues.append(f"Schema {schema_name}:{version} definition is not a dictionary")
                        all_valid = False
                        continue

                    if "type" not in schema_info.schema_definition:
                        self.issues.append(f"Schema {schema_name}:{version} missing 'type' field")
                        all_valid = False

                except Exception as e:
                    self.issues.append(f"Error validating schema {schema_name}:{version}: {e}")
                    all_valid = False

        if all_valid:
            logger.info("✅ All schema definitions are valid")
        else:
            logger.error("❌ Schema definition issues found")

        return all_valid

    def check_version_consistency(self) -> bool:
        """Check version consistency across schemas."""
        logger.info("Checking version consistency...")

        schemas = self.registry.list_schemas()
        all_consistent = True

        for schema_name, versions in schemas.items():
            if len(versions) < 2:
                continue

            # Sort versions
            versions_sorted = sorted(versions, key=lambda v: tuple(map(int, v.split('.'))))

            # Check for gaps in versioning
            for i in range(1, len(versions_sorted)):
                prev_version = versions_sorted[i-1]
                curr_version = versions_sorted[i]

                prev_parts = list(map(int, prev_version.split('.')))
                curr_parts = list(map(int, curr_version.split('.')))

                # Check if version progression makes sense
                if curr_parts[0] < prev_parts[0]:
                    self.issues.append(f"Schema {schema_name}: Version {curr_version} is lower than previous {prev_version}")
                    all_consistent = False
                elif curr_parts[0] == prev_parts[0] and curr_parts[1] < prev_parts[1]:
                    self.issues.append(f"Schema {schema_name}: Minor version {curr_version} is lower than previous {prev_version}")
                    all_consistent = False
                elif (curr_parts[0] == prev_parts[0] and
                      curr_parts[1] == prev_parts[1] and
                      curr_parts[2] <= prev_parts[2]):
                    self.issues.append(f"Schema {schema_name}: Patch version {curr_version} is not greater than previous {prev_version}")
                    all_consistent = False

        if all_consistent:
            logger.info("✅ All schema versions are consistent")
        else:
            logger.error("❌ Version consistency issues found")

        return all_consistent

    def check_compatibility_across_versions(self) -> bool:
        """Check backward compatibility across schema versions."""
        logger.info("Checking backward compatibility...")

        schemas = self.registry.list_schemas()
        all_compatible = True

        for schema_name, versions in schemas.items():
            if len(versions) < 2:
                continue

            # Sort versions to check in order
            versions_sorted = sorted(versions, key=lambda v: tuple(map(int, v.split('.'))))

            # Check compatibility between consecutive versions
            for i in range(1, len(versions_sorted)):
                old_version = versions_sorted[i-1]
                new_version = versions_sorted[i]

                try:
                    compatibility = check_compatibility(schema_name, old_version, new_version)

                    if not compatibility.is_compatible:
                        self.issues.append(
                            f"Schema {schema_name}: Breaking changes from {old_version} to {new_version}: "
                            f"{', '.join(compatibility.breaking_changes)}"
                        )
                        all_compatible = False

                    # Log compatibility results
                    if compatibility.breaking_changes:
                        logger.warning(
                            f"⚠️  Schema {schema_name} {old_version} -> {new_version} has "
                            f"{len(compatibility.breaking_changes)} breaking changes"
                        )
                    else:
                        logger.info(f"✅ Schema {schema_name} {old_version} -> {new_version} is backward compatible")

                except Exception as e:
                    self.issues.append(f"Error checking compatibility for {schema_name} {old_version} -> {new_version}: {e}")
                    all_compatible = False

        if all_compatible:
            logger.info("✅ All schema versions are backward compatible")
        else:
            logger.error("❌ Backward compatibility issues found")

        return all_compatible

    def check_required_fields(self) -> bool:
        """Check that all required fields are present in schemas."""
        logger.info("Checking required fields...")

        required_schemas = ["PreparedBill", "ExtractionResult", "ValidationResult"]
        all_present = True

        for schema_name in required_schemas:
            latest_schema = get_latest_schema(schema_name)
            if not latest_schema:
                self.issues.append(f"Required schema {schema_name} not found")
                all_present = False
                continue

            # Check for required top-level fields
            required_fields = {
                "PreparedBill": ["bill_id", "version", "rules_version", "parser_version", "vendor", "bill_header", "line_items"],
                "ExtractionResult": ["extraction_id", "invoice_id", "extraction_timestamp", "parser_version", "header", "lines", "confidence"],
                "ValidationResult": ["validation_id", "invoice_id", "validation_timestamp", "rules_version", "checks", "summary"]
            }

            if schema_name in required_fields:
                schema_required = required_fields[schema_name]
                properties = latest_schema.get("properties", {})
                schema_required_fields = latest_schema.get("required", [])

                for field in schema_required:
                    if field not in properties:
                        self.issues.append(f"Schema {schema_name} missing required property: {field}")
                        all_present = False

                for field in schema_required:
                    if field not in schema_required_fields:
                        self.issues.append(f"Schema {schema_name} property {field} should be required")
                        all_present = False

        if all_present:
            logger.info("✅ All required fields are present")
        else:
            logger.error("❌ Required field issues found")

        return all_present

    def check_example_data(self) -> bool:
        """Validate schemas against example data."""
        logger.info("Validating against example data...")

        # Example PreparedBill data
        example_prepared_bill = {
            "bill_id": "123e4567-e89b-12d3-a456-426614174000",
            "version": "1.0.0",
            "rules_version": "1.0.0",
            "parser_version": "1.0.0",
            "vendor": {
                "vendor_name": "Test Vendor Inc.",
                "vendor_tax_id": "123456789"
            },
            "bill_header": {
                "invoice_date": "2024-01-15",
                "total_amount": 100.50,
                "currency": "USD"
            },
            "line_items": [
                {
                    "description": "Test Service",
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

        try:
            prepared_bill_schema = get_latest_schema("PreparedBill")
            if prepared_bill_schema:
                is_valid, errors = validate_data_against_schema(example_prepared_bill, prepared_bill_schema)
                if not is_valid:
                    self.issues.extend([f"PreparedBill example validation: {error}" for error in errors])
                    logger.error("❌ PreparedBill example validation failed")
                    return False
                else:
                    logger.info("✅ PreparedBill example validation passed")
            else:
                self.issues.append("PreparedBill schema not found for example validation")
                return False

        except Exception as e:
            self.issues.append(f"Error validating example data: {e}")
            logger.error("❌ Example validation failed")
            return False

        return True

    def run_all_checks(self) -> bool:
        """Run all schema drift checks."""
        logger.info("🔍 Starting comprehensive schema drift detection...")

        checks = [
            ("Schema Definitions", self.check_schema_definitions),
            ("Version Consistency", self.check_version_consistency),
            ("Backward Compatibility", self.check_compatibility_across_versions),
            ("Required Fields", self.check_required_fields),
            ("Example Data", self.check_example_data)
        ]

        all_passed = True
        for check_name, check_func in checks:
            logger.info(f"\n--- Running {check_name} Check ---")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ {check_name} check failed with error: {e}")
                self.issues.append(f"{check_name} check error: {e}")
                all_passed = False

        # Generate report
        self.generate_report()

        return all_passed

    def generate_report(self):
        """Generate a comprehensive drift report."""
        logger.info("\n" + "="*60)
        logger.info("SCHEMA DRIFT DETECTION REPORT")
        logger.info("="*60)

        if self.issues:
            logger.error(f"❌ {len(self.issues)} issues detected:")
            for i, issue in enumerate(self.issues, 1):
                logger.error(f"  {i}. {issue}")
        else:
            logger.info("✅ No schema drift issues detected")

        # Save report to file
        report_data = {
            "timestamp": "2024-01-15T10:00:00Z",  # Would use actual timestamp
            "drift_detected": len(self.issues) > 0,
            "issues_count": len(self.issues),
            "issues": self.issues,
            "schemas_checked": list(self.registry.list_schemas().keys())
        }

        report_file = Path("schema_drift_report.json")
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"\n📄 Detailed report saved to: {report_file}")

        if self.issues:
            logger.error("\n🚨 SCHEMA DRIFT DETECTED - Review and fix issues before proceeding")
        else:
            logger.info("\n✅ SCHEMA DRIFT CHECK PASSED - All schemas are valid")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check for schema drift")
    parser.add_argument(
        "--registry-path",
        help="Path to schema registry file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        detector = SchemaDriftDetector(args.registry_path)
        success = detector.run_all_checks()

        if not success:
            logger.error("Schema drift detected. Please review the report and fix issues.")
            sys.exit(1)
        else:
            logger.info("Schema drift check passed successfully.")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Schema drift detection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()