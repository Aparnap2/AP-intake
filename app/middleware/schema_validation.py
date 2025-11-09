"""
Schema validation middleware for FastAPI.

This middleware provides automatic schema validation for API requests and responses,
ensuring data contract compliance at API boundaries.
"""

import json
import logging
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from app.services.schema_service import schema_service, SchemaValidationError, SchemaVersionError

logger = logging.getLogger(__name__)


class SchemaValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic schema validation of API requests and responses.

    Features:
    - Request validation against endpoint schemas
    - Response validation to ensure contract compliance
    - Version negotiation for API schemas
    - Validation error handling with proper HTTP status codes
    - Performance monitoring and logging
    """

    def __init__(
        self,
        app,
        validate_requests: bool = True,
        validate_responses: bool = True,
        strict_mode: bool = False,
        exclude_paths: Optional[list] = None
    ):
        """
        Initialize schema validation middleware.

        Args:
            app: FastAPI application
            validate_requests: Whether to validate incoming requests
            validate_responses: Whether to validate outgoing responses
            strict_mode: If True, validation errors raise exceptions
            exclude_paths: List of paths to exclude from validation
        """
        super().__init__(app)
        self.validate_requests = validate_requests
        self.validate_responses = validate_responses
        self.strict_mode = strict_mode
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/favicon.ico"
        ]

        # Endpoint to schema mappings
        self.endpoint_schemas = {
            # Invoice endpoints
            "POST:/api/v1/invoices": {
                "request": "invoice_upload",
                "response": "extraction_result"
            },
            "GET:/api/v1/invoices": {
                "request": None,
                "response": "invoice_list"
            },
            "GET:/api/v1/invoices/{id}": {
                "request": None,
                "response": "extraction_detail"
            },
            "PUT:/api/v1/invoices/{id}": {
                "request": "prepared_bill",
                "response": "extraction_result"
            },
            "DELETE:/api/v1/invoices/{id}": {
                "request": None,
                "response": None
            },

            # Schema endpoints
            "GET:/api/v1/schemas": {
                "request": None,
                "response": None  # Handled separately
            },
            "GET:/api/v1/schemas/{name}": {
                "request": None,
                "response": None  # Handled separately
            },

            # Export endpoints
            "POST:/api/v1/invoices/{id}/export": {
                "request": "export_request",
                "response": "export_format"
            }
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through schema validation pipeline.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            HTTP response
        """
        # Skip validation for excluded paths
        if self._should_skip_validation(request):
            return await call_next(request)

        start_time = time.time()

        try:
            # Validate request if enabled and schema is defined
            if self.validate_requests:
                await self._validate_request(request)

            # Process request through the application
            response = await call_next(request)

            # Validate response if enabled and schema is defined
            if self.validate_responses and response.status_code == 200:
                response = await self._validate_response(request, response)

            # Log validation performance
            process_time = time.time() - start_time
            logger.debug(f"Schema validation completed in {process_time:.3f}s for {request.method}:{request.url.path}")

            return response

        except SchemaValidationError as e:
            logger.error(f"Schema validation error for {request.method}:{request.url.path}: {e}")
            return self._create_validation_error_response(
                "Schema validation failed",
                str(e),
                status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        except SchemaVersionError as e:
            logger.error(f"Schema version error for {request.method}:{request.url.path}: {e}")
            return self._create_validation_error_response(
                "Schema version error",
                str(e),
                status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Unexpected error in schema validation middleware: {e}")
            if self.strict_mode:
                return self._create_validation_error_response(
                    "Internal validation error",
                    str(e),
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            # In non-strict mode, continue without validation
            return await call_next(request)

    def _should_skip_validation(self, request: Request) -> bool:
        """Check if request should skip validation."""
        path = request.url.path
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    def _get_endpoint_schema(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get schema configuration for the endpoint."""
        # Extract path parameters for matching
        path_parts = request.url.path.strip("/").split("/")
        method = request.method.upper()

        # Try exact match first
        endpoint_key = f"{method}:{request.url.path}"
        if endpoint_key in self.endpoint_schemas:
            return self.endpoint_schemas[endpoint_key]

        # Try pattern matching for paths with parameters
        for pattern, schemas in self.endpoint_schemas.items():
            if self._path_matches_pattern(request.url.path, pattern.split(":")[1]):
                return schemas

        return None

    def _path_matches_pattern(self, actual_path: str, pattern: str) -> bool:
        """Check if actual path matches pattern with parameters."""
        actual_parts = actual_path.strip("/").split("/")
        pattern_parts = pattern.strip("/").split("/")

        if len(actual_parts) != len(pattern_parts):
            return False

        for actual, pattern in zip(actual_parts, pattern_parts):
            if not (pattern.startswith("{") and pattern.endswith("}")):
                if actual != pattern:
                    return False

        return True

    async def _validate_request(self, request: Request):
        """Validate incoming request against schema."""
        endpoint_schema = self._get_endpoint_schema(request)
        if not endpoint_schema or not endpoint_schema.get("request"):
            return  # No request validation needed

        request_schema = endpoint_schema["request"]

        try:
            # Read request body
            body = await request.body()
            if not body:
                return  # Empty body, skip validation

            # Parse JSON
            try:
                request_data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                raise SchemaValidationError(f"Invalid JSON in request body: {e}")

            # Get requested version from headers
            schema_version = request.headers.get("X-Schema-Version")
            if not schema_version:
                schema_version = request.headers.get("API-Version")

            # Validate against schema
            is_valid, errors = schema_service.validate_api_request(
                request_data,
                request_schema,
                schema_version
            )

            if not is_valid:
                raise SchemaValidationError(f"Request validation failed: {errors}")

            logger.debug(f"Request validation passed for {request.method}:{request.url.path}")

        except SchemaValidationError:
            raise  # Re-raise schema validation errors
        except Exception as e:
            logger.error(f"Error during request validation: {e}")
            if self.strict_mode:
                raise SchemaValidationError(f"Request validation error: {e}")

    async def _validate_response(self, request: Request, response: Response) -> Response:
        """Validate outgoing response against schema."""
        endpoint_schema = self._get_endpoint_schema(request)
        if not endpoint_schema or not endpoint_schema.get("response"):
            return response  # No response validation needed

        response_schema = endpoint_schema["response"]

        # Only validate JSON responses
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response

        try:
            # For streaming responses, we can't easily validate
            if isinstance(response, StreamingResponse):
                logger.warning(f"Skipping validation for streaming response to {request.url.path}")
                return response

            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Parse JSON
            try:
                response_data = json.loads(response_body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in response body: {e}")
                return response  # Don't fail response for invalid JSON

            # Get response version from response headers or use latest
            schema_version = response.headers.get("X-Schema-Version")
            if not schema_version:
                schema_version = request.headers.get("API-Version")

            # Validate against schema
            is_valid, errors = schema_service.validate_api_response(
                response_data,
                response_schema,
                schema_version
            )

            if not is_valid:
                logger.error(f"Response validation failed for {request.method}:{request.url.path}: {errors}")
                if self.strict_mode:
                    raise SchemaValidationError(f"Response validation failed: {errors}")
                else:
                    # In non-strict mode, add validation warnings to response headers
                    response.headers["X-Schema-Validation-Warnings"] = ";".join(errors)
            else:
                # Add validation success header
                response.headers["X-Schema-Validated"] = "true"
                if schema_version:
                    response.headers["X-Schema-Version"] = schema_version

            logger.debug(f"Response validation passed for {request.method}:{request.url.path}")

            # Return new response with validated body
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        except SchemaValidationError:
            raise  # Re-raise schema validation errors
        except Exception as e:
            logger.error(f"Error during response validation: {e}")
            if self.strict_mode:
                raise SchemaValidationError(f"Response validation error: {e}")
            return response  # Return original response on error

    def _create_validation_error_response(
        self,
        error_type: str,
        error_message: str,
        status_code: int
    ) -> JSONResponse:
        """Create standardized validation error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "type": error_type,
                    "message": error_message,
                    "timestamp": datetime.utcnow().isoformat(),
                    "validation_failed": True
                }
            },
            headers={"X-Content-Type-Options": "nosniff"}
        )


def validate_schema(
    endpoint_schema: str,
    request_version: Optional[str] = None,
    strict_mode: bool = True
):
    """
    Decorator for endpoint-level schema validation.

    Args:
        endpoint_schema: Schema name to validate against
        request_version: Expected schema version
        strict_mode: Whether to raise exceptions on validation errors
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Extract request from function arguments
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    # Try to get request from kwargs
                    request = kwargs.get("request")

                if request:
                    # Validate request
                    is_valid, errors = schema_service.validate_api_request(
                        request,
                        endpoint_schema,
                        request_version
                    )

                    if not is_valid:
                        if strict_mode:
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Schema validation failed: {errors}"
                            )
                        else:
                            logger.warning(f"Schema validation failed: {errors}")

                # Call the original function
                result = await func(*args, **kwargs)

                # Validate response if it's a dictionary
                if isinstance(result, dict):
                    is_valid, errors = schema_service.validate_api_response(
                        result,
                        endpoint_schema,
                        request_version
                    )

                    if not is_valid and strict_mode:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Response validation failed: {errors}"
                        )

                return result

            except Exception as e:
                logger.error(f"Schema validation decorator error: {e}")
                raise

        return wrapper
    return decorator


def add_schema_headers(
    schema_name: str,
    schema_version: Optional[str] = None
):
    """
    Decorator to add schema information to response headers.

    Args:
        schema_name: Name of the schema used
        schema_version: Version of the schema
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # If result is a FastAPI Response, add headers
            if hasattr(result, 'headers'):
                result.headers["X-Schema-Name"] = schema_name
                if schema_version:
                    result.headers["X-Schema-Version"] = schema_version
            else:
                # If result is a dictionary, we'll need to convert to Response
                # This is handled by FastAPI's response model system
                pass

            return result

        return wrapper
    return decorator


# Import time module for performance monitoring
import time