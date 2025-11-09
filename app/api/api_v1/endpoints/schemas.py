"""
Schema management API endpoints.

This module provides REST endpoints for managing JSON schemas,
including registration, validation, versioning, and documentation.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Header
from fastapi.responses import JSONResponse, PlainTextResponse

from app.schemas.schema_registry import (
    schema_registry,
    SchemaInfo,
    register_schema,
    get_schema,
    check_compatibility,
    list_schemas
)
from app.services.schema_service import (
    schema_service,
    SchemaValidationError,
    SchemaVersionError
)
from app.middleware.schema_validation import validate_schema, add_schema_headers

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="List all available schemas")
@add_schema_headers("SchemaList")
async def list_available_schemas(
    include_deprecated: bool = Query(False, description="Include deprecated schemas"),
    api_version: Optional[str] = Header(None, description="API version")
) -> Dict[str, Any]:
    """
    List all available schemas and their versions.

    Returns a dictionary with schema names as keys and lists of versions as values.
    """
    try:
        schemas = schema_service.list_available_schemas()

        # Filter deprecated schemas if requested
        if not include_deprecated:
            filtered_schemas = {}
            for name, versions in schemas.items():
                active_versions = []
                for version in versions:
                    schema_info = schema_service.get_schema_info(name, version)
                    if schema_info and schema_info.is_active:
                        active_versions.append(version)
                if active_versions:
                    filtered_schemas[name] = active_versions
            schemas = filtered_schemas

        return {
            "schemas": schemas,
            "total_schemas": len(schemas),
            "api_version": api_version or "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list schemas: {str(e)}"
        )


@router.get("/{name}", summary="Get schema information")
@add_schema_headers("SchemaInfo")
async def get_schema_info(
    name: str,
    version: Optional[str] = Query(None, description="Schema version (if not provided, returns latest)"),
    include_definition: bool = Query(False, description="Include full schema definition"),
    format: str = Query("json", description="Response format: json, yaml"),
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Get information about a specific schema.

    If version is not provided, returns the latest active version.
    """
    try:
        schema_info = schema_service.get_schema_info(name, version)
        if not schema_info:
            raise HTTPException(
                status_code=404,
                detail=f"Schema {name}:{version or 'latest'} not found"
            )

        response_data = {
            "name": schema_info.name,
            "version": schema_info.version,
            "description": schema_info.description,
            "created_at": schema_info.created_at.isoformat(),
            "updated_at": schema_info.updated_at.isoformat(),
            "is_active": schema_info.is_active,
            "deprecation_date": schema_info.deprecation_date.isoformat() if schema_info.deprecation_date else None,
            "migration_path": schema_info.migration_path
        }

        if include_definition:
            response_data["definition"] = schema_info.schema_definition

        if format.lower() == "yaml":
            try:
                import yaml
                yaml_content = yaml.dump(response_data, default_flow_style=False)
                return PlainTextResponse(
                    content=yaml_content,
                    media_type="application/x-yaml"
                )
            except ImportError:
                raise HTTPException(
                    status_code=400,
                    detail="PyYAML required for YAML format"
                )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema info for {name}:{version}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get schema info: {str(e)}"
        )


@router.get("/{name}/versions", summary="List all versions of a schema")
async def list_schema_versions(
    name: str,
    include_deprecated: bool = Query(False),
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """List all versions of a specific schema."""
    try:
        all_versions = schema_registry.get_all_versions(name)

        if not all_versions:
            raise HTTPException(
                status_code=404,
                detail=f"No versions found for schema {name}"
            )

        versions_data = []
        for schema_info in all_versions:
            if not include_deprecated and not schema_info.is_active:
                continue

            versions_data.append({
                "version": schema_info.version,
                "created_at": schema_info.created_at.isoformat(),
                "updated_at": schema_info.updated_at.isoformat(),
                "is_active": schema_info.is_active,
                "deprecation_date": schema_info.deprecation_date.isoformat() if schema_info.deprecation_date else None,
                "description": schema_info.description
            })

        return {
            "schema_name": name,
            "versions": versions_data,
            "total_versions": len(versions_data),
            "latest_version": versions_data[0]["version"] if versions_data else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing versions for {name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list schema versions: {str(e)}"
        )


@router.post("/{name}/versions", summary="Register a new schema version")
@validate_schema("SchemaRegistration")
async def register_schema_version(
    name: str,
    schema_data: Dict[str, Any],
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Register a new version of a schema.

    Request body should contain:
    - version: Semantic version string
    - definition: JSON Schema definition
    - description: Optional description
    - migration_path: Optional migration guide path
    """
    try:
        version = schema_data.get("version")
        definition = schema_data.get("definition")
        description = schema_data.get("description")
        migration_path = schema_data.get("migration_path")

        if not version:
            raise HTTPException(
                status_code=400,
                detail="Version is required"
            )

        if not definition:
            raise HTTPException(
                status_code=400,
                detail="Schema definition is required"
            )

        # Check if schema already exists
        existing = schema_service.get_schema_info(name, version)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Schema {name}:{version} already exists"
            )

        # Register the schema
        schema_info = register_schema(
            name=name,
            version=version,
            schema=definition,
            description=description,
            migration_path=migration_path
        )

        return {
            "message": f"Schema {name}:{version} registered successfully",
            "schema": {
                "name": schema_info.name,
                "version": schema_info.version,
                "created_at": schema_info.created_at.isoformat(),
                "description": schema_info.description
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering schema {name}:{version}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register schema: {str(e)}"
        )


@router.post("/validate", summary="Validate data against schema")
async def validate_data_against_schema(
    validation_request: Dict[str, Any],
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Validate data against a schema.

    Request body should contain:
    - schema_name: Name of the schema to validate against
    - schema_version: Version of the schema (optional, uses latest if not provided)
    - data: Data to validate
    """
    try:
        schema_name = validation_request.get("schema_name")
        schema_version = validation_request.get("schema_version")
        data = validation_request.get("data")

        if not schema_name:
            raise HTTPException(
                status_code=400,
                detail="schema_name is required"
            )

        if not data:
            raise HTTPException(
                status_code=400,
                detail="data is required"
            )

        # Validate based on schema type
        if schema_name == "PreparedBill":
            is_valid, errors, metadata = schema_service.validate_prepared_bill(
                data,
                schema_version,
                strict_mode=False
            )
        elif schema_name == "ExtractionResult":
            # Convert to InvoiceExtractionResult if needed
            from app.models.schemas import InvoiceExtractionResult
            try:
                extraction_result = InvoiceExtractionResult(**data)
                is_valid, errors, metadata = schema_service.validate_invoice_extraction(
                    extraction_result,
                    schema_version,
                    strict_mode=False
                )
            except Exception as e:
                is_valid, errors = False, [f"Invalid extraction result format: {e}"]
                metadata = {}
        else:
            # Generic validation
            is_valid, errors = schema_service.registry.validate_data(
                data,
                schema_name,
                schema_version
            )
            metadata = {}

        return {
            "valid": is_valid,
            "errors": errors,
            "metadata": metadata,
            "schema_name": schema_name,
            "schema_version": schema_version or "latest",
            "validation_timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@router.get("/{name}/compatibility/{from_version}/{to_version}", summary="Check schema compatibility")
async def check_schema_compatibility(
    name: str,
    from_version: str,
    to_version: str,
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Check compatibility between two schema versions."""
    try:
        compatibility_report = schema_service.check_schema_compatibility(
            name, from_version, to_version
        )

        return {
            "schema_name": name,
            "from_version": from_version,
            "to_version": to_version,
            "is_compatible": compatibility_report.is_compatible,
            "breaking_changes": compatibility_report.breaking_changes,
            "non_breaking_changes": compatibility_report.non_breaking_changes,
            "recommendations": compatibility_report.recommendations,
            "migration_required": compatibility_report.migration_required,
            "migration_complexity": compatibility_report.migration_complexity,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking compatibility for {name}:{from_version}->{to_version}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Compatibility check failed: {str(e)}"
        )


@router.get("/{name}/changelog", summary="Get schema changelog")
async def get_schema_changelog(
    name: str,
    from_version: Optional[str] = Query(None, description="Starting version"),
    to_version: Optional[str] = Query(None, description="Ending version"),
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get changelog between schema versions."""
    try:
        changelog = schema_registry.generate_changelog(name, from_version, to_version)

        return {
            "changelog": changelog,
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating changelog for {name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Changelog generation failed: {str(e)}"
        )


@router.post("/{name}/deprecate", summary="Deprecate a schema version")
async def deprecate_schema_version(
    name: str,
    version: str,
    deprecation_data: Optional[Dict[str, Any]] = None,
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Deprecate a specific schema version."""
    try:
        deprecation_date = None
        if deprecation_data:
            deprecation_date_str = deprecation_data.get("deprecation_date")
            if deprecation_date_str:
                deprecation_date = datetime.fromisoformat(deprecation_date_str)

        schema_registry.deprecate_schema(name, version, deprecation_date)

        return {
            "message": f"Schema {name}:{version} deprecated successfully",
            "deprecation_date": deprecation_date.isoformat() if deprecation_date else datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error deprecating schema {name}:{version}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Schema deprecation failed: {str(e)}"
        )


@router.get("/{name}/export", summary="Export schema definition")
async def export_schema(
    name: str,
    version: Optional[str] = Query(None, description="Schema version"),
    format: str = Query("json", description="Export format: json, yaml"),
    include_metadata: bool = Query(True, description="Include schema metadata"),
    api_version: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Export schema definition in specified format."""
    try:
        exported_data = schema_service.export_schema_documentation(
            name,
            version,
            format
        )

        if not include_metadata and format.lower() == "json":
            # Return only the schema definition
            return exported_data.get("schema", exported_data)

        return exported_data

    except Exception as e:
        logger.error(f"Error exporting schema {name}:{version}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Schema export failed: {str(e)}"
        )


@router.get("/health", summary="Schema service health check")
async def schema_health_check() -> Dict[str, Any]:
    """Health check for schema service."""
    try:
        # Test basic schema operations
        schemas_count = len(list_schemas())
        latest_prepared_bill = schema_service.get_latest_schema_version("PreparedBill")

        return {
            "status": "healthy",
            "schema_registry": {
                "total_schemas": schemas_count,
                "latest_prepared_bill_version": latest_prepared_bill,
                "registry_status": "operational"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Schema health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )