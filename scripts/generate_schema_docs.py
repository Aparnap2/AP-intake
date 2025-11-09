#!/usr/bin/env python3
"""
Schema documentation generator.

This script generates comprehensive documentation for all registered schemas,
including examples, field descriptions, and version history.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.schemas.schema_registry import schema_registry
from app.schemas.json_schemas import get_latest_schema


class SchemaDocumentationGenerator:
    """Generates documentation for JSON schemas."""

    def __init__(self, output_dir: str = "docs/schemas"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.registry = schema_registry

    def generate_field_documentation(self, properties: Dict[str, Any], required: List[str]) -> str:
        """Generate documentation for schema fields."""
        docs = []
        docs.append("### Fields\n")

        for field_name, field_def in properties.items():
            is_required = field_name in required
            field_type = field_def.get("type", "unknown")
            description = field_def.get("description", "")
            default = field_def.get("default")
            examples = field_def.get("examples", [])

            # Field header
            required_indicator = " **(required)**" if is_required else ""
            docs.append(f"#### `{field_name}`{required_indicator}\n")
            docs.append(f"- **Type**: `{field_type}`\n")
            if description:
                docs.append(f"- **Description**: {description}\n")
            if default is not None:
                docs.append(f"- **Default**: `{default}`\n")
            if examples:
                docs.append(f"- **Examples**: {', '.join([f'`{ex}`' for ex in examples])}\n")

            # Add constraints
            constraints = []
            if "minimum" in field_def:
                constraints.append(f"min: {field_def['minimum']}")
            if "maximum" in field_def:
                constraints.append(f"max: {field_def['maximum']}")
            if "minLength" in field_def:
                constraints.append(f"min length: {field_def['minLength']}")
            if "maxLength" in field_def:
                constraints.append(f"max length: {field_def['maxLength']}")
            if "pattern" in field_def:
                constraints.append(f"pattern: `{field_def['pattern']}`")
            if "enum" in field_def:
                constraints.append(f"enum: {field_def['enum']}")

            if constraints:
                docs.append(f"- **Constraints**: {', '.join(constraints)}\n")

            docs.append("")

        return "\n".join(docs)

    def generate_example_json(self, schema_def: Dict[str, Any]) -> str:
        """Generate an example JSON based on the schema."""
        def generate_example_for_type(type_def: Dict[str, Any], required_fields: List[str] = None) -> Any:
            if isinstance(type_def, str):
                # This is a $ref
                if type_def.startswith("#/definitions/"):
                    ref_name = type_def.split("/")[-1]
                    # Find the definition in schema
                    definitions = schema_def.get("definitions", {})
                    if ref_name in definitions:
                        return generate_example_for_type(definitions[ref_name])
                return f"<{type_def}>"

            if not isinstance(type_def, dict):
                return "<unknown>"

            if "allOf" in type_def:
                # Merge allOf schemas
                result = {}
                for sub_schema in type_def["allOf"]:
                    sub_example = generate_example_for_type(sub_schema)
                    if isinstance(sub_example, dict):
                        result.update(sub_example)
                return result

            if "anyOf" in type_def:
                # Use first option for example
                return generate_example_for_type(type_def["anyOf"][0])

            if "$ref" in type_def:
                return generate_example_for_type(type_def["$ref"])

            field_type = type_def.get("type", "unknown")
            required_fields = required_fields or type_def.get("required", [])

            if field_type == "object":
                result = {}
                properties = type_def.get("properties", {})
                for prop_name, prop_def in properties.items():
                    if prop_name in required_fields:
                        result[prop_name] = generate_example_for_type(prop_def)
                    elif prop_def.get("default") is not None:
                        result[prop_name] = prop_def["default"]
                    elif prop_def.get("type") != "object":  # Avoid infinite recursion
                        result[prop_name] = generate_example_for_type(prop_def)
                return result

            elif field_type == "array":
                items_def = type_def.get("items", {})
                return [generate_example_for_type(items_def)]

            elif field_type == "string":
                if "enum" in type_def:
                    return type_def["enum"][0]
                elif "format" in type_def:
                    format_type = type_def["format"]
                    if format_type == "date":
                        return "2024-01-15"
                    elif format_type == "date-time":
                        return "2024-01-15T10:00:00Z"
                    elif format_type == "email":
                        return "example@example.com"
                    elif format_type == "uuid":
                        return "123e4567-e89b-12d3-a456-426614174000"
                    else:
                        return f"<{format_type}>"
                elif "pattern" in type_def:
                    return f"<pattern: {type_def['pattern']}>"
                else:
                    return "example string"

            elif field_type == "number" or field_type == "integer":
                if "minimum" in type_def:
                    return type_def["minimum"]
                elif "maximum" in type_def:
                    return type_def["maximum"]
                else:
                    return 0 if field_type == "integer" else 0.0

            elif field_type == "boolean":
                return True

            elif field_type == "null":
                return None

            else:
                return f"<{field_type}>"

        example = generate_example_for_type(schema_def)
        return json.dumps(example, indent=2)

    def generate_schema_documentation(self, schema_name: str) -> str:
        """Generate documentation for a specific schema."""
        versions = self.registry.get_all_versions(schema_name)
        if not versions:
            return f"# {schema_name}\n\nNo versions found.\n"

        docs = []
        docs.append(f"# {schema_name}\n")
        docs.append(f"*Generated on {datetime.utcnow().isoformat()}*\n")

        # Version history
        docs.append("## Version History\n")
        for version_info in versions:
            status = "✅ Active" if version_info.is_active else "⚠️ Deprecated"
            created = version_info.created_at.strftime("%Y-%m-%d")
            docs.append(f"- **{version_info.version}** ({created}) - {status}")
            if version_info.description:
                docs.append(f"  - {version_info.description}")
            if version_info.deprecation_date:
                docs.append(f"  - Deprecated: {version_info.deprecation_date.strftime('%Y-%m-%d')}")
        docs.append("")

        # Latest version documentation
        latest_version = versions[0]  # Registry returns sorted list
        docs.append(f"## Latest Version ({latest_version.version})\n")

        if latest_version.description:
            docs.append(f"{latest_version.description}\n")

        schema_def = latest_version.schema_definition

        # Schema overview
        docs.append("### Schema Overview\n")
        docs.append(f"- **Type**: `{schema_def.get('type', 'unknown')}`\n")
        docs.append(f"- **Required Fields**: {len(schema_def.get('required', []))}\n")
        docs.append(f"- **Properties**: {len(schema_def.get('properties', {}))}\n")
        docs.append("")

        # Field documentation
        if "properties" in schema_def:
            docs.append(self.generate_field_documentation(
                schema_def["properties"],
                schema_def.get("required", [])
            ))

        # Example
        docs.append("### Example\n")
        docs.append("```json\n")
        docs.append(self.generate_example_json(schema_def))
        docs.append("\n```\n")

        # Validation rules
        docs.append("### Validation Rules\n")
        docs.append("This schema includes the following validation rules:\n")
        if schema_def.get("required"):
            docs.append(f"- **Required fields**: {', '.join(schema_def['required'])}\n")
        if schema_def.get("additionalProperties") is False:
            docs.append("- **Additional properties**: Not allowed\n")
        docs.append("")

        return "\n".join(docs)

    def generate_comparision_documentation(self, schema_name: str, from_version: str, to_version: str) -> str:
        """Generate comparison documentation between two versions."""
        try:
            compatibility = self.registry.check_compatibility(schema_name, from_version, to_version)
        except Exception as e:
            return f"# {schema_name} Comparison: {from_version} → {to_version}\n\nError generating comparison: {e}\n"

        docs = []
        docs.append(f"# {schema_name} Version Comparison\n")
        docs.append(f"## {from_version} → {to_version}\n")
        docs.append(f"*Generated on {datetime.utcnow().isoformat()}*\n")

        # Compatibility summary
        if compatibility.is_compatible:
            docs.append("✅ **Backward Compatible** - No breaking changes detected\n")
        else:
            docs.append("⚠️ **Breaking Changes Detected** - Migration required\n")

        docs.append(f"- **Migration Required**: {'Yes' if compatibility.migration_required else 'No'}\n")
        docs.append(f"- **Migration Complexity**: {compatibility.migration_complexity}\n")
        docs.append("")

        # Breaking changes
        if compatibility.breaking_changes:
            docs.append("## ❌ Breaking Changes\n")
            for change in compatibility.breaking_changes:
                docs.append(f"- {change}\n")
            docs.append("")

        # Non-breaking changes
        if compatibility.non_breaking_changes:
            docs.append("## ✅ Non-Breaking Changes\n")
            for change in compatibility.non_breaking_changes:
                docs.append(f"- {change}\n")
            docs.append("")

        # Recommendations
        if compatibility.recommendations:
            docs.append("## 💡 Recommendations\n")
            for rec in compatibility.recommendations:
                docs.append(f"- {rec}\n")
            docs.append("")

        return "\n".join(docs)

    def generate_index_page(self, schemas: Dict[str, List]) -> str:
        """Generate an index page for all schemas."""
        docs = []
        docs.append("# Schema Documentation\n")
        docs.append(f"*Generated on {datetime.utcnow().isoformat()}*\n")
        docs.append("This document contains comprehensive documentation for all JSON schemas used in the AP Intake system.\n")

        docs.append("## Available Schemas\n")
        for schema_name, versions in schemas.items():
            latest_version = versions[0].version if versions else "unknown"
            status = "✅ Active" if versions[0].is_active else "⚠️ Deprecated"
            docs.append(f"- [{schema_name}](./{schema_name.lower()}.md) - Latest: {latest_version} ({status})\n")

        docs.append("""
## Schema Types

- **PreparedBill**: Complete invoice data ready for export
- **ExtractionResult**: Output of invoice extraction process
- **ValidationResult**: Business rule validation results
- **Vendor**: Vendor information structure
- **LineItem**: Individual invoice line items
- **ExportFormat**: Export format definitions

## Usage

These schemas are used throughout the AP Intake system for:

1. **API Validation**: Ensuring request/response data integrity
2. **Data Processing**: Validating data at each processing stage
3. **Export Generation**: Ensuring ERP compatibility
4. **Integration**: Maintaining contract compliance with external systems

## Version Management

All schemas follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes requiring migration
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes and documentation updates

For more information on schema management, see [Schema Development Guide](../development/schemas.md).
""")

        return "\n".join(docs)

    def generate_all_documentation(self):
        """Generate documentation for all schemas."""
        print("📚 Generating schema documentation...")

        schemas = self.registry.list_schemas()

        # Generate individual schema documentation
        for schema_name, versions in schemas.items():
            print(f"  📝 Generating docs for {schema_name}")
            doc_content = self.generate_schema_documentation(schema_name)

            # Save to file
            output_file = self.output_dir / f"{schema_name.lower()}.md"
            with open(output_file, 'w') as f:
                f.write(doc_content)

            print(f"    ✅ Saved to {output_file}")

        # Generate index page
        print("  📝 Generating index page")
        index_content = self.generate_index_page(schemas)
        index_file = self.output_dir / "index.md"
        with open(index_file, 'w') as f:
            f.write(index_content)
        print(f"    ✅ Saved to {index_file}")

        # Generate version comparisons for major changes
        print("  📝 Generating version comparisons")
        comparisons_dir = self.output_dir / "comparisons"
        comparisons_dir.mkdir(exist_ok=True)

        for schema_name, versions in schemas.items():
            if len(versions) > 1:
                # Compare latest with previous version
                latest = versions[0]
                previous = versions[1]

                comparison_content = self.generate_comparision_documentation(
                    schema_name, previous.version, latest.version
                )

                comparison_file = comparisons_dir / f"{schema_name.lower()}_{previous.version}_to_{latest.version}.md"
                with open(comparison_file, 'w') as f:
                    f.write(comparison_content)

                print(f"    ✅ Comparison saved to {comparison_file}")

        # Generate summary JSON
        print("  📊 Generating summary data")
        summary_data = {
            "generated_at": datetime.utcnow().isoformat(),
            "schemas": {
                name: {
                    "latest_version": versions[0].version if versions else None,
                    "total_versions": len(versions),
                    "active_versions": len([v for v in versions if v.is_active]),
                    "latest_created": versions[0].created_at.isoformat() if versions else None
                }
                for name, versions in schemas.items()
            },
            "files_generated": [
                str(self.output_dir / f"{name.lower()}.md")
                for name in schemas.keys()
            ] + [
                str(self.output_dir / "index.md")
            ]
        }

        summary_file = self.output_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        print(f"    ✅ Summary saved to {summary_file}")

        print(f"\n✅ Documentation generation complete!")
        print(f"📁 Output directory: {self.output_dir.absolute()}")
        print(f"📄 {len(schemas)} schema documents generated")
        print(f"📊 Summary data available in summary.json")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate schema documentation")
    parser.add_argument(
        "--output-dir",
        default="docs/schemas",
        help="Output directory for documentation"
    )
    parser.add_argument(
        "--schema",
        help="Generate documentation for specific schema only"
    )

    args = parser.parse_args()

    try:
        generator = SchemaDocumentationGenerator(args.output_dir)

        if args.schema:
            # Generate documentation for specific schema
            print(f"📚 Generating documentation for {args.schema}...")
            doc_content = generator.generate_schema_documentation(args.schema)
            output_file = Path(args.output_dir) / f"{args.schema.lower()}.md"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                f.write(doc_content)
            print(f"✅ Documentation saved to {output_file}")
        else:
            # Generate all documentation
            generator.generate_all_documentation()

    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()