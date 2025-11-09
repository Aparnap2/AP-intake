"""
Schema registry service for managing data contracts.

This module provides centralized management of JSON schemas with versioning,
validation, and compatibility checking capabilities.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict

import jsonschema
from fastapi import HTTPException

logger = logging.getLogger(__name__)


@dataclass
class SchemaVersion:
    """Schema version information."""
    version: str
    created_at: datetime
    schema_definition: Dict[str, Any]
    description: Optional[str] = None


@dataclass
class SchemaInfo:
    """Information about a registered schema."""
    name: str
    version: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    schema_definition: Dict[str, Any]
    is_active: bool = True
    deprecation_date: Optional[datetime] = None
    migration_path: Optional[str] = None


@dataclass
class SchemaCompatibilityReport:
    """Schema compatibility analysis result."""
    is_compatible: bool
    breaking_changes: List[str]
    non_breaking_changes: List[str]
    recommendations: List[str]
    migration_required: bool
    migration_complexity: str  # "simple", "moderate", "complex"


class SchemaRegistry:
    """
    Centralized registry for JSON schemas with versioning support.

    Features:
    - Schema versioning and lifecycle management
    - Compatibility checking between versions
    - Migration path tracking
    - Schema validation
    - Deprecation management
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize schema registry.

        Args:
            storage_path: Path to persist schema registry data
        """
        self._schemas: Dict[str, SchemaInfo] = {}
        self._version_index: Dict[str, List[str]] = {}  # name -> [versions]
        self._storage_path = Path(storage_path) if storage_path else None
        self._load_schemas()

    def _load_schemas(self):
        """Load schemas from storage if available."""
        if self._storage_path and self._storage_path.exists():
            try:
                with open(self._storage_path, 'r') as f:
                    data = json.load(f)
                    for schema_data in data.get('schemas', []):
                        schema_info = SchemaInfo(
                            name=schema_data['name'],
                            version=schema_data['version'],
                            description=schema_data.get('description'),
                            created_at=datetime.fromisoformat(schema_data['created_at']),
                            updated_at=datetime.fromisoformat(schema_data['updated_at']),
                            schema_definition=schema_data['schema_definition'],
                            is_active=schema_data.get('is_active', True),
                            deprecation_date=datetime.fromisoformat(schema_data['deprecation_date']) if schema_data.get('deprecation_date') else None,
                            migration_path=schema_data.get('migration_path')
                        )
                        self._register_schema_internal(schema_info)
                logger.info(f"Loaded {len(self._schemas)} schemas from storage")
            except Exception as e:
                logger.error(f"Failed to load schemas from storage: {e}")

    def _save_schemas(self):
        """Save schemas to storage if configured."""
        if not self._storage_path:
            return

        try:
            # Ensure parent directory exists
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'schemas': [
                    {
                        'name': schema.name,
                        'version': schema.version,
                        'description': schema.description,
                        'created_at': schema.created_at.isoformat(),
                        'updated_at': schema.updated_at.isoformat(),
                        'schema_definition': schema.schema_definition,
                        'is_active': schema.is_active,
                        'deprecation_date': schema.deprecation_date.isoformat() if schema.deprecation_date else None,
                        'migration_path': schema.migration_path
                    }
                    for schema in self._schemas.values()
                ]
            }

            with open(self._storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self._schemas)} schemas to storage")
        except Exception as e:
            logger.error(f"Failed to save schemas to storage: {e}")

    def _register_schema_internal(self, schema_info: SchemaInfo):
        """Internal schema registration."""
        key = f"{schema_info.name}:{schema_info.version}"
        self._schemas[key] = schema_info

        if schema_info.name not in self._version_index:
            self._version_index[schema_info.name] = []
        if schema_info.version not in self._version_index[schema_info.name]:
            self._version_index[schema_info.name].append(schema_info.version)
            self._version_index[schema_info.name].sort()

    def register_schema(
        self,
        name: str,
        version: str,
        schema_definition: Dict[str, Any],
        description: Optional[str] = None,
        migration_path: Optional[str] = None
    ) -> SchemaInfo:
        """
        Register a new schema version.

        Args:
            name: Schema name
            version: Semantic version (e.g., "1.0.0")
            schema_definition: JSON Schema definition
            description: Schema description
            migration_path: Migration guide path

        Returns:
            SchemaInfo object for the registered schema

        Raises:
            ValueError: If schema already exists or version is invalid
        """
        # Validate version format
        if not self._is_valid_version(version):
            raise ValueError(f"Invalid version format: {version}. Use semantic versioning (e.g., '1.0.0')")

        key = f"{name}:{version}"
        if key in self._schemas:
            raise ValueError(f"Schema {name}:{version} already exists")

        # Validate schema definition
        self._validate_schema_definition(schema_definition)

        schema_info = SchemaInfo(
            name=name,
            version=version,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            schema_definition=schema_definition,
            migration_path=migration_path
        )

        self._register_schema_internal(schema_info)
        self._save_schemas()

        logger.info(f"Registered schema {name}:{version}")
        return schema_info

    def get_schema(self, name: str, version: Optional[str] = None) -> Optional[SchemaInfo]:
        """
        Get a schema by name and version.

        Args:
            name: Schema name
            version: Specific version (if None, returns latest active version)

        Returns:
            SchemaInfo object or None if not found
        """
        if version:
            key = f"{name}:{version}"
            return self._schemas.get(key)
        else:
            # Return latest active version
            versions = self._version_index.get(name, [])
            for v in reversed(versions):
                key = f"{name}:{v}"
                schema = self._schemas.get(key)
                if schema and schema.is_active:
                    return schema
            return None

    def get_all_versions(self, name: str) -> List[SchemaInfo]:
        """Get all versions of a schema."""
        versions = self._version_index.get(name, [])
        schemas = []
        for version in versions:
            key = f"{name}:{version}"
            if key in self._schemas:
                schemas.append(self._schemas[key])
        return schemas

    def list_schemas(self) -> Dict[str, List[SchemaInfo]]:
        """List all registered schemas."""
        result = {}
        for name in self._version_index.keys():
            result[name] = self.get_all_versions(name)
        return result

    def update_schema(
        self,
        name: str,
        version: str,
        schema_definition: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> SchemaInfo:
        """Update an existing schema."""
        key = f"{name}:{version}"
        if key not in self._schemas:
            raise ValueError(f"Schema {name}:{version} not found")

        schema_info = self._schemas[key]

        if schema_definition:
            self._validate_schema_definition(schema_definition)
            schema_info.schema_definition = schema_definition

        if description is not None:
            schema_info.description = description

        schema_info.updated_at = datetime.utcnow()
        self._save_schemas()

        logger.info(f"Updated schema {name}:{version}")
        return schema_info

    def deprecate_schema(self, name: str, version: str, deprecation_date: Optional[datetime] = None):
        """Deprecate a schema version."""
        key = f"{name}:{version}"
        if key not in self._schemas:
            raise ValueError(f"Schema {name}:{version} not found")

        schema_info = self._schemas[key]
        schema_info.is_active = False
        schema_info.deprecation_date = deprecation_date or datetime.utcnow()
        self._save_schemas()

        logger.info(f"Deprecated schema {name}:{version}")

    def validate_data(self, data: Dict[str, Any], schema_name: str, version: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate data against a schema.

        Args:
            data: Data to validate
            schema_name: Schema name
            version: Schema version (if None, uses latest)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        schema_info = self.get_schema(schema_name, version)
        if not schema_info:
            raise ValueError(f"Schema {schema_name}:{version or 'latest'} not found")

        try:
            jsonschema.validate(data, schema_info.schema_definition)
            return True, []
        except jsonschema.ValidationError as e:
            error_path = "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            return False, [f"Validation failed at {error_path}: {e.message}"]
        except jsonschema.SchemaError as e:
            return False, [f"Schema error: {e.message}"]

    def check_compatibility(self, name: str, old_version: str, new_version: str) -> SchemaCompatibilityReport:
        """
        Check compatibility between two schema versions.

        Args:
            name: Schema name
            old_version: Previous version
            new_version: New version

        Returns:
            Compatibility analysis report
        """
        old_schema = self.get_schema(name, old_version)
        new_schema = self.get_schema(name, new_version)

        if not old_schema:
            raise ValueError(f"Schema {name}:{old_version} not found")
        if not new_schema:
            raise ValueError(f"Schema {name}:{new_version} not found")

        return self._analyze_compatibility(old_schema.schema_definition, new_schema.schema_definition)

    def _analyze_compatibility(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> SchemaCompatibilityReport:
        """Analyze compatibility between two schemas."""
        breaking_changes = []
        non_breaking_changes = []
        recommendations = []

        # Check basic type compatibility
        if old_schema.get("type") != new_schema.get("type"):
            breaking_changes.append(f"Type changed: {old_schema.get('type')} -> {new_schema.get('type')}")

        # Check required fields
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        # New required fields are breaking changes
        newly_required = new_required - old_required
        if newly_required:
            breaking_changes.append(f"New required fields: {newly_required}")

        # Removed required fields are breaking changes
        removed_required = old_required - new_required
        if removed_required:
            breaking_changes.append(f"Removed required fields: {removed_required}")

        # Check property changes
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})

        for field_name, old_field in old_props.items():
            if field_name in new_props:
                new_field = new_props[field_name]

                # Type changes are breaking
                old_type = old_field.get("type")
                new_type = new_field.get("type")
                if old_type != new_type:
                    if isinstance(old_type, list) and isinstance(new_type, list):
                        # Check if new type is subset of old type (non-breaking)
                        if not set(new_type).issubset(set(old_type)):
                            breaking_changes.append(f"Type incompatible for field '{field_name}': {old_type} -> {new_type}")
                    else:
                        breaking_changes.append(f"Type changed for field '{field_name}': {old_type} -> {new_type}")

                # Constraint tightening is breaking
                constraints = ["minimum", "minLength", "maxItems", "minItems"]
                for constraint in constraints:
                    if constraint in old_field and constraint in new_field:
                        if new_field[constraint] > old_field[constraint]:
                            breaking_changes.append(f"Constraint tightened for field '{field_name}': {constraint}")

                # Constraint loosening is non-breaking
                constraints = ["maximum", "maxLength"]
                for constraint in constraints:
                    if constraint in old_field and constraint in new_field:
                        if new_field[constraint] < old_field[constraint]:
                            non_breaking_changes.append(f"Constraint loosened for field '{field_name}': {constraint}")

                # Enum changes
                old_enum = old_field.get("enum")
                new_enum = new_field.get("enum")
                if old_enum and new_enum:
                    removed_values = set(old_enum) - set(new_enum)
                    if removed_values:
                        breaking_changes.append(f"Enum values removed for field '{field_name}': {removed_values}")
                    added_values = set(new_enum) - set(old_enum)
                    non_breaking_changes.append(f"Enum values added for field '{field_name}': {added_values}")

            else:
                breaking_changes.append(f"Field '{field_name}' removed")

        # Check for new fields (non-breaking)
        for field_name in new_props:
            if field_name not in old_props:
                non_breaking_changes.append(f"New field '{field_name}' added")

        # Generate recommendations
        if breaking_changes:
            recommendations.append("Consider creating a migration script for breaking changes")
            if len(breaking_changes) > 3:
                recommendations.append("Multiple breaking changes detected - consider a major version bump")

        if not breaking_changes and non_breaking_changes:
            recommendations.append("Changes are backward compatible - minor version bump appropriate")

        # Determine migration complexity
        migration_required = len(breaking_changes) > 0
        if len(breaking_changes) == 0:
            migration_complexity = "simple"
        elif len(breaking_changes) <= 3:
            migration_complexity = "moderate"
        else:
            migration_complexity = "complex"

        return SchemaCompatibilityReport(
            is_compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes,
            non_breaking_changes=non_breaking_changes,
            recommendations=recommendations,
            migration_required=migration_required,
            migration_complexity=migration_complexity
        )

    def _is_valid_version(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        try:
            parts = version.split(".")
            if len(parts) != 3:
                return False
            for part in parts:
                int(part)  # Will raise ValueError if not numeric
            return True
        except ValueError:
            return False

    def _validate_schema_definition(self, schema: Dict[str, Any]):
        """Validate a JSON schema definition."""
        try:
            # Use jsonschema to validate the schema itself against meta-schema
            # For now, just basic validation
            if not isinstance(schema, dict):
                raise ValueError("Schema must be a dictionary")

            if "type" not in schema:
                raise ValueError("Schema must specify a 'type'")

            # Additional validation rules can be added here
        except Exception as e:
            raise ValueError(f"Invalid schema definition: {e}")

    def export_schema(self, name: str, version: Optional[str] = None, format: str = "json") -> Dict[str, Any]:
        """
        Export schema in specified format.

        Args:
            name: Schema name
            version: Schema version (if None, exports latest)
            format: Export format ("json", "yaml")

        Returns:
            Exported schema data
        """
        schema_info = self.get_schema(name, version)
        if not schema_info:
            raise ValueError(f"Schema {name}:{version or 'latest'} not found")

        export_data = {
            "name": schema_info.name,
            "version": schema_info.version,
            "description": schema_info.description,
            "created_at": schema_info.created_at.isoformat(),
            "updated_at": schema_info.updated_at.isoformat(),
            "is_active": schema_info.is_active,
            "schema": schema_info.schema_definition
        }

        if format.lower() == "yaml":
            try:
                import yaml
                return {"yaml": yaml.dump(export_data, default_flow_style=False)}
            except ImportError:
                raise ImportError("PyYAML required for YAML export")

        return export_data

    def get_migration_path(self, name: str, from_version: str, to_version: str) -> Optional[str]:
        """Get migration path between versions."""
        # For now, return stored migration path if available
        schema = self.get_schema(name, to_version)
        return schema.migration_path if schema else None

    def generate_changelog(self, name: str, from_version: Optional[str] = None, to_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate changelog between schema versions.

        Args:
            name: Schema name
            from_version: Starting version (if None, uses first version)
            to_version: Ending version (if None, uses latest version)

        Returns:
            Changelog information
        """
        all_versions = self._version_index.get(name, [])
        if not all_versions:
            raise ValueError(f"No versions found for schema {name}")

        if not from_version:
            from_version = all_versions[0]
        if not to_version:
            to_version = all_versions[-1]

        from_idx = all_versions.index(from_version)
        to_idx = all_versions.index(to_version)

        if from_idx >= to_idx:
            raise ValueError(f"Invalid version range: {from_version} -> {to_version}")

        changelog = {
            "schema_name": name,
            "from_version": from_version,
            "to_version": to_version,
            "changes": []
        }

        # Compare each consecutive version
        for i in range(from_idx, to_idx):
            current_version = all_versions[i]
            next_version = all_versions[i + 1]

            current_schema = self.get_schema(name, current_version)
            next_schema = self.get_schema(name, next_version)

            compatibility = self._analyze_compatibility(
                current_schema.schema_definition,
                next_schema.schema_definition
            )

            changelog["changes"].append({
                "from_version": current_version,
                "to_version": next_version,
                "breaking_changes": compatibility.breaking_changes,
                "non_breaking_changes": compatibility.non_breaking_changes,
                "migration_required": compatibility.migration_required,
                "migration_complexity": compatibility.migration_complexity
            })

        return changelog


# Global schema registry instance
schema_registry = SchemaRegistry()


# Utility functions for external use
def register_schema(name: str, version: str, schema: Dict[str, Any], **kwargs) -> SchemaInfo:
    """Register a schema with the global registry."""
    return schema_registry.register_schema(name, version, schema, **kwargs)


def get_schema(name: str, version: Optional[str] = None) -> Optional[SchemaInfo]:
    """Get a schema from the global registry."""
    return schema_registry.get_schema(name, version)


def validate_data(data: Dict[str, Any], schema_name: str, version: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate data against a schema."""
    return schema_registry.validate_data(data, schema_name, version)


def check_compatibility(name: str, old_version: str, new_version: str) -> SchemaCompatibilityReport:
    """Check schema compatibility."""
    return schema_registry.check_compatibility(name, old_version, new_version)


def list_schemas() -> Dict[str, List[SchemaInfo]]:
    """List all registered schemas."""
    return schema_registry.list_schemas()