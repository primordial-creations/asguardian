"""
OpenAPI Models - Pydantic models for OpenAPI specification handling.

These models represent OpenAPI 3.0/3.1 specification structures and
validation results.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.OpenAPI.models._openapi_base_models import (
    OpenAPIConfig,
    OpenAPIContact,
    OpenAPIInfo,
    OpenAPILicense,
    OpenAPIServer,
    OpenAPIValidationError,
    OpenAPIValidationResult,
    OpenAPIVersion,
    ParameterLocation,
    SecuritySchemeType,
    ValidationSeverity,
)


class OpenAPISchema(BaseModel):
    """JSON Schema object for OpenAPI."""

    type: Optional[str] = Field(default=None, description="Schema type")
    format: Optional[str] = Field(default=None, description="Schema format")
    title: Optional[str] = Field(default=None, description="Schema title")
    description: Optional[str] = Field(default=None, description="Schema description")
    default: Optional[Any] = Field(default=None, description="Default value")
    nullable: Optional[bool] = Field(default=None, description="Allow null values")
    read_only: Optional[bool] = Field(default=None, description="Read-only property")
    write_only: Optional[bool] = Field(default=None, description="Write-only property")
    deprecated: Optional[bool] = Field(default=None, description="Deprecated flag")
    example: Optional[Any] = Field(default=None, description="Example value")
    properties: Optional[dict[str, Any]] = Field(
        default=None,
        description="Object properties"
    )
    required: Optional[list[str]] = Field(
        default=None,
        description="Required properties"
    )
    items: Optional[Any] = Field(default=None, description="Array items schema")
    enum: Optional[list[Any]] = Field(default=None, description="Enum values")
    all_of: Optional[list[Any]] = Field(default=None, description="allOf composition")
    one_of: Optional[list[Any]] = Field(default=None, description="oneOf composition")
    any_of: Optional[list[Any]] = Field(default=None, description="anyOf composition")
    ref: Optional[str] = Field(default=None, alias="$ref", description="Reference")
    additional_properties: Optional[Any] = Field(
        default=None,
        description="Additional properties schema"
    )
    minimum: Optional[float] = Field(default=None, description="Minimum value")
    maximum: Optional[float] = Field(default=None, description="Maximum value")
    min_length: Optional[int] = Field(default=None, description="Minimum string length")
    max_length: Optional[int] = Field(default=None, description="Maximum string length")
    pattern: Optional[str] = Field(default=None, description="Regex pattern")
    min_items: Optional[int] = Field(default=None, description="Minimum array items")
    max_items: Optional[int] = Field(default=None, description="Maximum array items")
    unique_items: Optional[bool] = Field(default=None, description="Unique array items")


class OpenAPIParameter(BaseModel):
    """Parameter object for operations."""

    name: str = Field(description="Parameter name")
    location: ParameterLocation = Field(
        alias="in",
        description="Parameter location"
    )
    description: Optional[str] = Field(default=None, description="Parameter description")
    required: Optional[bool] = Field(default=None, description="Required flag")
    deprecated: Optional[bool] = Field(default=None, description="Deprecated flag")
    allow_empty_value: Optional[bool] = Field(
        default=None,
        description="Allow empty value"
    )
    schema_: Optional[OpenAPISchema] = Field(
        default=None,
        alias="schema",
        description="Parameter schema"
    )
    example: Optional[Any] = Field(default=None, description="Example value")
    examples: Optional[dict[str, Any]] = Field(default=None, description="Examples")

    class Config:
        use_enum_values = True
        populate_by_name = True


class OpenAPIRequestBody(BaseModel):
    """Request body object for operations."""

    description: Optional[str] = Field(default=None, description="Request body description")
    content: dict[str, Any] = Field(description="Content by media type")
    required: Optional[bool] = Field(default=None, description="Required flag")


class OpenAPIResponse(BaseModel):
    """Response object for operations."""

    description: str = Field(description="Response description")
    headers: Optional[dict[str, Any]] = Field(default=None, description="Response headers")
    content: Optional[dict[str, Any]] = Field(
        default=None,
        description="Content by media type"
    )
    links: Optional[dict[str, Any]] = Field(default=None, description="Response links")


class OpenAPISecurityScheme(BaseModel):
    """Security scheme object."""

    type: SecuritySchemeType = Field(description="Security scheme type")
    description: Optional[str] = Field(default=None, description="Scheme description")
    name: Optional[str] = Field(
        default=None,
        description="Name for apiKey"
    )
    location: Optional[str] = Field(
        default=None,
        alias="in",
        description="Location for apiKey"
    )
    scheme: Optional[str] = Field(
        default=None,
        description="HTTP auth scheme"
    )
    bearer_format: Optional[str] = Field(
        default=None,
        description="Bearer token format"
    )
    flows: Optional[dict[str, Any]] = Field(
        default=None,
        description="OAuth2 flows"
    )
    openid_connect_url: Optional[str] = Field(
        default=None,
        description="OpenID Connect URL"
    )

    class Config:
        use_enum_values = True
        populate_by_name = True


class OpenAPIOperation(BaseModel):
    """Operation object for API paths."""

    operation_id: Optional[str] = Field(default=None, description="Operation ID")
    summary: Optional[str] = Field(default=None, description="Operation summary")
    description: Optional[str] = Field(default=None, description="Operation description")
    tags: Optional[list[str]] = Field(default=None, description="Operation tags")
    external_docs: Optional[dict[str, Any]] = Field(
        default=None,
        description="External documentation"
    )
    parameters: Optional[list[OpenAPIParameter]] = Field(
        default=None,
        description="Operation parameters"
    )
    request_body: Optional[OpenAPIRequestBody] = Field(
        default=None,
        description="Request body"
    )
    responses: dict[str, OpenAPIResponse] = Field(
        description="Operation responses"
    )
    callbacks: Optional[dict[str, Any]] = Field(default=None, description="Callbacks")
    deprecated: Optional[bool] = Field(default=None, description="Deprecated flag")
    security: Optional[list[dict[str, list[str]]]] = Field(
        default=None,
        description="Security requirements"
    )
    servers: Optional[list[OpenAPIServer]] = Field(
        default=None,
        description="Operation servers"
    )


class OpenAPIPath(BaseModel):
    """Path item object."""

    path: str = Field(description="Path template")
    summary: Optional[str] = Field(default=None, description="Path summary")
    description: Optional[str] = Field(default=None, description="Path description")
    get: Optional[OpenAPIOperation] = Field(default=None, description="GET operation")
    put: Optional[OpenAPIOperation] = Field(default=None, description="PUT operation")
    post: Optional[OpenAPIOperation] = Field(default=None, description="POST operation")
    delete: Optional[OpenAPIOperation] = Field(default=None, description="DELETE operation")
    options: Optional[OpenAPIOperation] = Field(default=None, description="OPTIONS operation")
    head: Optional[OpenAPIOperation] = Field(default=None, description="HEAD operation")
    patch: Optional[OpenAPIOperation] = Field(default=None, description="PATCH operation")
    trace: Optional[OpenAPIOperation] = Field(default=None, description="TRACE operation")
    servers: Optional[list[OpenAPIServer]] = Field(
        default=None,
        description="Path servers"
    )
    parameters: Optional[list[OpenAPIParameter]] = Field(
        default=None,
        description="Path parameters"
    )

    @property
    def operations(self) -> dict[str, OpenAPIOperation]:
        """Return all defined operations for this path."""
        ops = {}
        for method in ["get", "put", "post", "delete", "options", "head", "patch", "trace"]:
            op = getattr(self, method, None)
            if op is not None:
                ops[method.upper()] = op
        return ops


class OpenAPISpec(BaseModel):
    """Complete OpenAPI specification."""

    openapi: str = Field(description="OpenAPI version string")
    info: OpenAPIInfo = Field(description="API information")
    servers: Optional[list[OpenAPIServer]] = Field(
        default=None,
        description="Server list"
    )
    paths: dict[str, Any] = Field(
        default_factory=dict,
        description="API paths"
    )
    components: Optional[dict[str, Any]] = Field(
        default=None,
        description="Reusable components"
    )
    security: Optional[list[dict[str, list[str]]]] = Field(
        default=None,
        description="Security requirements"
    )
    tags: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="API tags"
    )
    external_docs: Optional[dict[str, Any]] = Field(
        default=None,
        description="External documentation"
    )

    @property
    def version(self) -> OpenAPIVersion:
        """Return the OpenAPI version as an enum."""
        if self.openapi.startswith("3.1"):
            return OpenAPIVersion.V3_1
        elif self.openapi.startswith("3.0"):
            return OpenAPIVersion.V3_0
        elif self.openapi.startswith("2."):
            return OpenAPIVersion.V2_0
        return OpenAPIVersion.V3_0

    @property
    def path_count(self) -> int:
        """Return the number of paths."""
        return len(self.paths)

    @property
    def operation_count(self) -> int:
        """Return the total number of operations."""
        count = 0
        methods = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]
        for path_item in self.paths.values():
            if isinstance(path_item, dict):
                for method in methods:
                    if method in path_item:
                        count += 1
        return count


__all__ = [
    "OpenAPIConfig",
    "OpenAPIContact",
    "OpenAPIInfo",
    "OpenAPILicense",
    "OpenAPIOperation",
    "OpenAPIParameter",
    "OpenAPIPath",
    "OpenAPIRequestBody",
    "OpenAPIResponse",
    "OpenAPISchema",
    "OpenAPISecurityScheme",
    "OpenAPIServer",
    "OpenAPISpec",
    "OpenAPIValidationError",
    "OpenAPIValidationResult",
    "OpenAPIVersion",
    "ParameterLocation",
    "SecuritySchemeType",
    "ValidationSeverity",
]
