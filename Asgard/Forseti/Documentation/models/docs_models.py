"""
Documentation Models - Pydantic models for API documentation generation.

These models represent documentation configurations, generated documents,
and documentation reports.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Documentation.models._docs_base_models import (
    APIDocConfig,
    DocumentationFormat,
    DocumentationTheme,
    EndpointInfo,
    SchemaInfo,
    TagGroup,
)


class GeneratedDocument(BaseModel):
    """A generated documentation file."""

    path: str = Field(
        description="Output file path"
    )
    content: str = Field(
        description="Document content"
    )
    format: DocumentationFormat = Field(
        description="Document format"
    )
    title: str = Field(
        description="Document title"
    )
    size_bytes: int = Field(
        default=0,
        description="File size in bytes"
    )

    class Config:
        use_enum_values = True


class DocumentationReport(BaseModel):
    """Report from documentation generation."""

    success: bool = Field(
        description="Whether generation was successful"
    )
    source_spec: Optional[str] = Field(
        default=None,
        description="Source specification path"
    )
    api_title: str = Field(
        description="API title"
    )
    api_version: str = Field(
        description="API version"
    )
    generated_documents: list[GeneratedDocument] = Field(
        default_factory=list,
        description="List of generated documents"
    )
    endpoint_count: int = Field(
        default=0,
        description="Number of documented endpoints"
    )
    schema_count: int = Field(
        default=0,
        description="Number of documented schemas"
    )
    tag_count: int = Field(
        default=0,
        description="Number of tag groups"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Generation warnings"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Generation errors"
    )
    generation_time_ms: float = Field(
        default=0.0,
        description="Time taken for generation in milliseconds"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Generation timestamp"
    )

    class Config:
        use_enum_values = True


class DocumentationStructure(BaseModel):
    """Complete documentation structure for an API."""

    title: str = Field(
        description="API title"
    )
    version: str = Field(
        description="API version"
    )
    description: Optional[str] = Field(
        default=None,
        description="API description"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL"
    )
    contact: Optional[dict[str, str]] = Field(
        default=None,
        description="Contact information"
    )
    license: Optional[dict[str, str]] = Field(
        default=None,
        description="License information"
    )
    servers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Server definitions"
    )
    security_schemes: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Security scheme definitions"
    )
    tag_groups: list[TagGroup] = Field(
        default_factory=list,
        description="Endpoints grouped by tag"
    )
    schemas: list[SchemaInfo] = Field(
        default_factory=list,
        description="Schema definitions"
    )
    external_docs: Optional[dict[str, str]] = Field(
        default=None,
        description="External documentation link"
    )


__all__ = [
    "APIDocConfig",
    "DocumentationFormat",
    "DocumentationReport",
    "DocumentationStructure",
    "DocumentationTheme",
    "EndpointInfo",
    "GeneratedDocument",
    "SchemaInfo",
    "TagGroup",
]
