"""
Documentation Base Models - Enums, config, and simple endpoint/schema info models.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentationFormat(str, Enum):
    """Supported documentation output formats."""
    HTML = "html"
    MARKDOWN = "markdown"
    PDF = "pdf"
    ASCIIDOC = "asciidoc"


class DocumentationTheme(str, Enum):
    """Available documentation themes."""
    DEFAULT = "default"
    MODERN = "modern"
    MINIMAL = "minimal"
    DARK = "dark"


class EndpointInfo(BaseModel):
    """Information about an API endpoint for documentation."""

    path: str = Field(
        description="Endpoint path"
    )
    method: str = Field(
        description="HTTP method"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Endpoint summary"
    )
    description: Optional[str] = Field(
        default=None,
        description="Endpoint description"
    )
    operation_id: Optional[str] = Field(
        default=None,
        description="Operation identifier"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Endpoint tags"
    )
    parameters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Endpoint parameters"
    )
    request_body: Optional[dict[str, Any]] = Field(
        default=None,
        description="Request body schema"
    )
    responses: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Response definitions"
    )
    deprecated: bool = Field(
        default=False,
        description="Whether the endpoint is deprecated"
    )
    security: list[dict[str, list[str]]] = Field(
        default_factory=list,
        description="Security requirements"
    )
    examples: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Request/response examples"
    )


class SchemaInfo(BaseModel):
    """Information about a schema for documentation."""

    name: str = Field(
        description="Schema name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Schema description"
    )
    properties: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Schema properties"
    )
    required: list[str] = Field(
        default_factory=list,
        description="Required properties"
    )
    is_enum: bool = Field(
        default=False,
        description="Whether this is an enum"
    )
    enum_values: list[Any] = Field(
        default_factory=list,
        description="Enum values"
    )
    example: Optional[Any] = Field(
        default=None,
        description="Example value"
    )


class TagGroup(BaseModel):
    """Group of endpoints by tag."""

    name: str = Field(
        description="Tag name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Tag description"
    )
    endpoints: list[EndpointInfo] = Field(
        default_factory=list,
        description="Endpoints in this group"
    )


class APIDocConfig(BaseModel):
    """Configuration for API documentation generation."""

    title: Optional[str] = Field(
        default=None,
        description="Override API title"
    )
    description: Optional[str] = Field(
        default=None,
        description="Override API description"
    )
    output_format: DocumentationFormat = Field(
        default=DocumentationFormat.HTML,
        description="Output format"
    )
    theme: DocumentationTheme = Field(
        default=DocumentationTheme.DEFAULT,
        description="Documentation theme"
    )
    include_examples: bool = Field(
        default=True,
        description="Include request/response examples"
    )
    include_schemas: bool = Field(
        default=True,
        description="Include schema definitions section"
    )
    include_authentication: bool = Field(
        default=True,
        description="Include authentication section"
    )
    include_changelog: bool = Field(
        default=False,
        description="Include changelog if available"
    )
    group_by_tags: bool = Field(
        default=True,
        description="Group endpoints by tags"
    )
    show_deprecated: bool = Field(
        default=True,
        description="Show deprecated endpoints"
    )
    custom_css: Optional[str] = Field(
        default=None,
        description="Custom CSS to include"
    )
    custom_logo_url: Optional[str] = Field(
        default=None,
        description="Custom logo URL"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Override base URL"
    )
    contact_email: Optional[str] = Field(
        default=None,
        description="Contact email"
    )
    license_url: Optional[str] = Field(
        default=None,
        description="License URL"
    )

    class Config:
        use_enum_values = True
