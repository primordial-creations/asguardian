"""
MockServer Models - Pydantic models for mock server generation and data.

These models represent mock server configurations, endpoints, and
generated mock data for testing API implementations.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.MockServer.models._mock_base_models import (
    DataType,
    HttpMethod,
    MockDataConfig,
    MockHeader,
    MockParameter,
    MockRequestBody,
    MockResponse,
    MockResponseType,
    MockServerConfig,
)


class MockEndpoint(BaseModel):
    """Definition of a mock API endpoint."""

    path: str = Field(description="Endpoint path (may include path parameters)")
    method: HttpMethod = Field(description="HTTP method")
    operation_id: Optional[str] = Field(
        default=None,
        description="Operation identifier"
    )
    summary: Optional[str] = Field(default=None, description="Endpoint summary")
    description: Optional[str] = Field(default=None, description="Endpoint description")
    tags: list[str] = Field(default_factory=list, description="Endpoint tags")
    parameters: list[MockParameter] = Field(
        default_factory=list,
        description="Endpoint parameters"
    )
    request_body: Optional[MockRequestBody] = Field(
        default=None,
        description="Request body definition"
    )
    responses: dict[str, MockResponse] = Field(
        default_factory=dict,
        description="Response definitions by status code"
    )
    default_response: Optional[str] = Field(
        default=None,
        description="Default response status code"
    )
    security: list[dict[str, list[str]]] = Field(
        default_factory=list,
        description="Security requirements"
    )

    class Config:
        use_enum_values = True

    @property
    def path_parameters(self) -> list[MockParameter]:
        """Get path parameters."""
        return [p for p in self.parameters if p.location == "path"]

    @property
    def query_parameters(self) -> list[MockParameter]:
        """Get query parameters."""
        return [p for p in self.parameters if p.location == "query"]

    @property
    def header_parameters(self) -> list[MockParameter]:
        """Get header parameters."""
        return [p for p in self.parameters if p.location == "header"]


class MockServerDefinition(BaseModel):
    """Complete mock server definition."""

    title: str = Field(description="Server title")
    description: Optional[str] = Field(default=None, description="Server description")
    version: str = Field(default="1.0.0", description="API version")
    base_url: str = Field(default="", description="Base URL for the API")
    endpoints: list[MockEndpoint] = Field(
        default_factory=list,
        description="List of mock endpoints"
    )
    config: MockServerConfig = Field(
        default_factory=MockServerConfig,
        description="Server configuration"
    )
    global_headers: list[MockHeader] = Field(
        default_factory=list,
        description="Headers to add to all responses"
    )
    source_spec: Optional[str] = Field(
        default=None,
        description="Path to source specification"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Generation timestamp"
    )

    @property
    def endpoint_count(self) -> int:
        """Return the number of endpoints."""
        return len(self.endpoints)

    def get_endpoints_by_tag(self) -> dict[str, list[MockEndpoint]]:
        """Group endpoints by tag."""
        result: dict[str, list[MockEndpoint]] = {}
        for endpoint in self.endpoints:
            tags = endpoint.tags or ["untagged"]
            for tag in tags:
                if tag not in result:
                    result[tag] = []
                result[tag].append(endpoint)
        return result


class GeneratedFile(BaseModel):
    """A generated file from mock server generation."""

    path: str = Field(description="Relative path for the file")
    content: str = Field(description="File content")
    file_type: str = Field(description="File type (python, javascript, json, etc.)")
    is_entry_point: bool = Field(
        default=False,
        description="Whether this is the main entry point"
    )


class MockServerGenerationResult(BaseModel):
    """Result of mock server generation."""

    success: bool = Field(description="Whether generation was successful")
    server_definition: MockServerDefinition = Field(
        description="The mock server definition"
    )
    generated_files: list[GeneratedFile] = Field(
        default_factory=list,
        description="Generated server files"
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


class MockDataResult(BaseModel):
    """Result of mock data generation."""

    data: Any = Field(description="Generated mock data")
    schema_used: Optional[dict[str, Any]] = Field(
        default=None,
        description="Schema used for generation"
    )
    generation_strategy: str = Field(description="Strategy used for generation")
    warnings: list[str] = Field(
        default_factory=list,
        description="Generation warnings"
    )


__all__ = [
    "DataType",
    "GeneratedFile",
    "HttpMethod",
    "MockDataConfig",
    "MockDataResult",
    "MockEndpoint",
    "MockHeader",
    "MockParameter",
    "MockRequestBody",
    "MockResponse",
    "MockResponseType",
    "MockServerConfig",
    "MockServerDefinition",
    "MockServerGenerationResult",
]
