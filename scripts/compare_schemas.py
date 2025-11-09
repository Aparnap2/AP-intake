#!/usr/bin/env python3
"""
Schema comparison script.

This script compares schema definitions between two branches or directories
to detect changes and potential compatibility issues.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import difflib

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SchemaComparator:
    """Compares schema definitions between different versions."""

    def __init__(self, base_dir: str, current_dir: str):
        self.base_dir = Path(base_dir)
        self.current_dir = Path(current_dir)
        self.comparison_results = []

    def load_schema_file(self, directory: Path) -> Dict[str, Any]:
        """Load schema definitions from a directory."""
        schemas_dir = directory / "app" / "schemas"
        schemas = {}

        if not schemas_dir.exists():
            print(f"Warning: schemas directory not found in {directory}")
            return schemas

        # Load main schema files
        for schema_file in schemas_dir.glob("*.py"):
            if schema_file.name.startswith("__"):
                continue

            try:
                # For now, we'll do a simple text comparison
                # In a real implementation, you'd parse the Python files
                # and extract schema definitions
                with open(schema_file, 'r') as f:
                    content = f.read()
                    schemas[schema_file.stem] = {
                        "type": "python_file",
                        "content": content,
                        "path": str(schema_file.relative_to(directory))
                    }
            except Exception as e:
                print(f"Warning: Could not load {schema_file}: {e}")

        # Also check for JSON schema files if they exist
        json_schemas_dir = directory / "schemas"
        if json_schemas_dir.exists():
            for json_file in json_schemas_dir.glob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        schema_data = json.load(f)
                        schemas[json_file.stem] = {
                            "type": "json_schema",
                            "content": schema_data,
                            "path": str(json_file.relative_to(directory))
                        }
                except Exception as e:
                    print(f"Warning: Could not load {json_file}: {e}")

        return schemas

    def compare_schemas(self) -> Dict[str, Any]:
        """Compare schemas between base and current directories."""
        print("🔍 Loading schemas from base directory...")
        base_schemas = self.load_schema_file(self.base_dir)

        print("🔍 Loading schemas from current directory...")
        current_schemas = self.load_schema_file(self.current_dir)

        print("📊 Comparing schemas...")
        comparison = {
            "new_schemas": [],
            "modified_schemas": [],
            "removed_schemas": [],
            "unchanged_schemas": [],
            "summary": {}
        }

        # Find new schemas
        for name in current_schemas:
            if name not in base_schemas:
                comparison["new_schemas"].append({
                    "name": name,
                    "path": current_schemas[name]["path"],
                    "type": current_schemas[name]["type"]
                })

        # Find removed schemas
        for name in base_schemas:
            if name not in current_schemas:
                comparison["removed_schemas"].append({
                    "name": name,
                    "path": base_schemas[name]["path"],
                    "type": base_schemas[name]["type"]
                })

        # Find modified schemas
        for name in current_schemas:
            if name in base_schemas:
                base_content = base_schemas[name]["content"]
                current_content = current_schemas[name]["content"]

                if base_content != current_content:
                    if current_schemas[name]["type"] == "json_schema":
                        # For JSON schemas, do structured comparison
                        changes = self.compare_json_schemas(
                            base_content,
                            current_content,
                            name
                        )
                    else:
                        # For Python files, do text comparison
                        changes = self.compare_text_schemas(
                            base_content,
                            current_content,
                            name
                        )

                    comparison["modified_schemas"].append({
                        "name": name,
                        "path": current_schemas[name]["path"],
                        "type": current_schemas[name]["type"],
                        "changes": changes
                    })
                else:
                    comparison["unchanged_schemas"].append({
                        "name": name,
                        "path": current_schemas[name]["path"],
                        "type": current_schemas[name]["type"]
                    })

        # Generate summary
        comparison["summary"] = {
            "total_base_schemas": len(base_schemas),
            "total_current_schemas": len(current_schemas),
            "new_count": len(comparison["new_schemas"]),
            "modified_count": len(comparison["modified_schemas"]),
            "removed_count": len(comparison["removed_schemas"]),
            "unchanged_count": len(comparison["unchanged_schemas"])
        }

        return comparison

    def compare_json_schemas(self, base_schema: Dict, current_schema: Dict, name: str) -> Dict[str, Any]:
        """Compare two JSON schemas and identify changes."""
        changes = {
            "breaking_changes": [],
            "non_breaking_changes": [],
            "additions": [],
            "removals": [],
            "modifications": []
        }

        # Compare top-level properties
        self.compare_schema_properties(
            base_schema.get("properties", {}),
            current_schema.get("properties", {}),
            changes,
            name
        )

        # Compare required fields
        base_required = set(base_schema.get("required", []))
        current_required = set(current_schema.get("required", []))

        # New required fields (breaking change)
        newly_required = current_required - base_required
        for field in newly_required:
            changes["breaking_changes"].append(f"Field '{field}' is now required")

        # Removed required fields (breaking change)
        removed_required = base_required - current_required
        for field in removed_required:
            changes["breaking_changes"].append(f"Field '{field}' is no longer required")

        # Compare type changes
        if base_schema.get("type") != current_schema.get("type"):
            changes["breaking_changes"].append(
                f"Schema type changed from {base_schema.get('type')} to {current_schema.get('type')}"
            )

        # Compare additionalProperties
        base_additional = base_schema.get("additionalProperties", True)
        current_additional = current_schema.get("additionalProperties", True)
        if base_additional and not current_additional:
            changes["non_breaking_changes"].append("additionalProperties changed from true to false")
        elif not base_additional and current_additional:
            changes["non_breaking_changes"].append("additionalProperties changed from false to true")

        return changes

    def compare_schema_properties(self, base_props: Dict, current_props: Dict, changes: Dict[str, List], schema_name: str):
        """Compare schema properties and identify changes."""
        # Find new properties
        for prop_name in current_props:
            if prop_name not in base_props:
                changes["additions"].append(f"New property '{prop_name}' added")
                # Check if new property is required (would be caught above)
                if current_props[prop_name].get("required", False):
                    changes["breaking_changes"].append(f"New required property '{prop_name}' added")
                else:
                    changes["non_breaking_changes"].append(f"New optional property '{prop_name}' added")

        # Find removed properties
        for prop_name in base_props:
            if prop_name not in current_props:
                changes["removals"].append(f"Property '{prop_name}' removed")
                # Check if removed property was required
                if base_props[prop_name].get("required", False):
                    changes["breaking_changes"].append(f"Required property '{prop_name}' removed")
                else:
                    changes["non_breaking_changes"].append(f"Optional property '{prop_name}' removed")

        # Find modified properties
        for prop_name in current_props:
            if prop_name in base_props:
                base_prop = base_props[prop_name]
                current_prop = current_props[prop_name]

                # Check for type changes
                base_type = base_prop.get("type")
                current_type = current_prop.get("type")
                if base_type != current_type:
                    changes["breaking_changes"].append(
                        f"Property '{prop_name}' type changed from {base_type} to {current_type}"
                    )

                # Check for constraint changes
                constraints = ["minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"]
                for constraint in constraints:
                    if constraint in base_prop and constraint in current_prop:
                        base_value = base_prop[constraint]
                        current_value = current_prop[constraint]
                        if base_value != current_value:
                            if constraint.startswith("min"):
                                if current_value > base_value:
                                    changes["breaking_changes"].append(
                                        f"Property '{prop_name}' {constraint} tightened from {base_value} to {current_value}"
                                    )
                                else:
                                    changes["non_breaking_changes"].append(
                                        f"Property '{prop_name}' {constraint} loosened from {base_value} to {current_value}"
                                    )
                            elif constraint.startswith("max"):
                                if current_value < base_value:
                                    changes["breaking_changes"].append(
                                        f"Property '{prop_name}' {constraint} tightened from {base_value} to {current_value}"
                                    )
                                else:
                                    changes["non_breaking_changes"].append(
                                        f"Property '{prop_name}' {constraint} loosened from {base_value} to {current_value}"
                                    )

                # Check for enum changes
                base_enum = base_prop.get("enum")
                current_enum = current_prop.get("enum")
                if base_enum and current_enum:
                    if base_enum != current_enum:
                        removed_values = set(base_enum) - set(current_enum)
                        added_values = set(current_enum) - set(base_enum)
                        if removed_values:
                            changes["breaking_changes"].append(
                                f"Property '{prop_name}' enum values removed: {removed_values}"
                            )
                        if added_values:
                            changes["non_breaking_changes"].append(
                                f"Property '{prop_name}' enum values added: {added_values}"
                            )

    def compare_text_schemas(self, base_content: str, current_content: str, name: str) -> Dict[str, Any]:
        """Compare Python schema files and identify changes."""
        changes = {
            "line_changes": [],
            "additions": [],
            "removals": [],
            "structural_changes": []
        }

        # Generate unified diff
        base_lines = base_content.splitlines(keepends=True)
        current_lines = current_content.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            base_lines,
            current_lines,
            fromfile=f"{name} (base)",
            tofile=f"{name} (current)",
            lineterm=''
        ))

        # Analyze diff for meaningful changes
        for line in diff:
            if line.startswith('@@'):
                # Line number information
                changes["line_changes"].append(line)
            elif line.startswith('+'):
                # Added line
                clean_line = line[1:].strip()
                if clean_line and not clean_line.startswith('#'):
                    changes["additions"].append(clean_line)
            elif line.startswith('-'):
                # Removed line
                clean_line = line[1:].strip()
                if clean_line and not clean_line.startswith('#'):
                    changes["removals"].append(clean_line)

        # Look for structural changes
        base_imports = self.extract_imports(base_content)
        current_imports = self.extract_imports(current_content)

        if base_imports != current_imports:
            changes["structural_changes"].append("Imports changed")

        base_classes = self.extract_class_definitions(base_content)
        current_classes = self.extract_class_definitions(current_content)

        if base_classes != current_classes:
            changes["structural_changes"].append("Class definitions changed")

        return changes

    def extract_imports(self, content: str) -> List[str]:
        """Extract import statements from Python content."""
        imports = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
        return imports

    def extract_class_definitions(self, content: str) -> List[str]:
        """Extract class definitions from Python content."""
        classes = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('class '):
                # Extract class name
                class_name = line.split('(')[0].replace('class ', '').strip(':')
                classes.append(class_name)
        return classes

    def generate_report(self, comparison: Dict[str, Any]) -> str:
        """Generate a human-readable comparison report."""
        report = []
        report.append("# Schema Comparison Report\n")
        report.append(f"*Generated on {self.get_timestamp()}*\n")

        # Summary
        summary = comparison["summary"]
        report.append("## Summary\n")
        report.append(f"- **Base schemas**: {summary['total_base_schemas']}")
        report.append(f"- **Current schemas**: {summary['total_current_schemas']}")
        report.append(f"- **New schemas**: {summary['new_count']}")
        report.append(f"- **Modified schemas**: {summary['modified_count']}")
        report.append(f"- **Removed schemas**: {summary['removed_count']}")
        report.append(f"- **Unchanged schemas**: {summary['unchanged_count']}")
        report.append("")

        # Breaking changes summary
        total_breaking = sum(
            len(schema["changes"].get("breaking_changes", []))
            for schema in comparison["modified_schemas"]
        )
        if total_breaking > 0:
            report.append("⚠️ **BREAKING CHANGES DETECTED**\n")
            report.append(f"Total breaking changes: {total_breaking}\n")

        # New schemas
        if comparison["new_schemas"]:
            report.append("## ✅ New Schemas\n")
            for schema in comparison["new_schemas"]:
                report.append(f"- **{schema['name']}** ({schema['type']}) - `{schema['path']}`")
            report.append("")

        # Modified schemas
        if comparison["modified_schemas"]:
            report.append("## 📝 Modified Schemas\n")
            for schema in comparison["modified_schemas"]:
                report.append(f"### {schema['name']}\n")
                report.append(f"**Path**: `{schema['path']}`\n")
                report.append(f"**Type**: {schema['type']}\n")

                changes = schema["changes"]

                # Breaking changes
                if changes.get("breaking_changes"):
                    report.append("#### ❌ Breaking Changes\n")
                    for change in changes["breaking_changes"]:
                        report.append(f"- {change}")
                    report.append("")

                # Non-breaking changes
                if changes.get("non_breaking_changes"):
                    report.append("#### ✅ Non-Breaking Changes\n")
                    for change in changes["non_breaking_changes"]:
                        report.append(f"- {change}")
                    report.append("")

                # Additions
                if changes.get("additions"):
                    report.append("#### ➕ Additions\n")
                    for addition in changes["additions"]:
                        report.append(f"- {addition}")
                    report.append("")

                # Removals
                if changes.get("removals"):
                    report.append("#### ➖ Removals\n")
                    for removal in changes["removals"]:
                        report.append(f"- {removal}")
                    report.append("")

        # Removed schemas
        if comparison["removed_schemas"]:
            report.append("## 🗑️ Removed Schemas\n")
            for schema in comparison["removed_schemas"]:
                report.append(f"- **{schema['name']}** ({schema['type']}) - `{schema['path']}`")
            report.append("")

        # Recommendations
        report.append("## 💡 Recommendations\n")
        if total_breaking > 0:
            report.append("⚠️ **Breaking changes detected**: Review and plan migration path")
            report.append("- Consider version bump (major version increment)")
            report.append("- Update dependent code")
            report.append("- Document migration requirements")
        elif comparison["modified_schemas"]:
            report.append("✅ **No breaking changes**: Safe to proceed")
            report.append("- Consider version bump (minor version increment)")
            report.append("- Update documentation if needed")
        else:
            report.append("✅ **No schema changes**: Everything is up to date")

        return "\n".join(report)

    def get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def save_report(self, comparison: Dict[str, Any], output_file: str = "schema_changes_report.json"):
        """Save comparison results to file."""
        # Save JSON report
        with open(output_file, 'w') as f:
            json.dump(comparison, f, indent=2)
        print(f"📄 JSON report saved to {output_file}")

        # Save Markdown report
        md_file = output_file.replace('.json', '.md')
        md_content = self.generate_report(comparison)
        with open(md_file, 'w') as f:
            f.write(md_content)
        print(f"📄 Markdown report saved to {md_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare schemas between directories")
    parser.add_argument("--base-dir", required=True, help="Base directory for comparison")
    parser.add_argument("--current-dir", required=True, help="Current directory for comparison")
    parser.add_argument("--output", default="schema_changes_report.json", help="Output file for report")

    args = parser.parse_args()

    try:
        print("🔍 Starting schema comparison...")
        comparator = SchemaComparator(args.base_dir, args.current_dir)

        comparison = comparator.compare_schemas()
        comparator.save_report(comparison, args.output)

        # Print summary
        summary = comparison["summary"]
        print(f"\n📊 Comparison Summary:")
        print(f"  Base schemas: {summary['total_base_schemas']}")
        print(f"  Current schemas: {summary['total_current_schemas']}")
        print(f"  New: {summary['new_count']}")
        print(f"  Modified: {summary['modified_count']}")
        print(f"  Removed: {summary['removed_count']}")

        total_breaking = sum(
            len(schema["changes"].get("breaking_changes", []))
            for schema in comparison["modified_schemas"]
        )

        if total_breaking > 0:
            print(f"\n⚠️ {total_breaking} breaking changes detected!")
            sys.exit(1)
        else:
            print(f"\n✅ No breaking changes detected!")
            sys.exit(0)

    except Exception as e:
        print(f"❌ Schema comparison failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()