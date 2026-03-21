"""
MockServer Base Models - Enums, configs, and simple request/response models.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MockResponseType(str, Enum):
    """Types of mock responses."""
    STATIC = "static"
    DYNAMIC = "dynamic"
    RANDOM = "random"
    SEQUENTIAL = "sequential"


class HttpMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class DataType(str, Enum):
    """Types of data for mock generation."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    UUID = "uuid"
    URL = "url"
    PHONE = "phone"
    NAME = "name"
    ADDRESS = "address"


class MockServerConfig(BaseModel):
    """Configuration for mock server generation."""

    host: str = Field(default="0.0.0.0", description="Host to bind the server to")
    port: int = Field(default=8080, description="Port to run the server on")
    base_path: str = Field(default="", description="Base path prefix for all endpoints")
    response_delay_ms: int = Field(
        default=0,
        description="Artificial delay for responses in milliseconds"
    )
    enable_cors: bool = Field(default=True, description="Enable CORS headers")
    enable_logging: bool = Field(default=True, description="Enable request/response logging")
    validate_requests: bool = Field(
        default=False,
        description="Validate incoming requests against schema"
    )
    use_realistic_data: bool = Field(
        default=True,
        description="Generate realistic mock data"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible data generation"
    )
    server_framework: str = Field(
        default="flask",
        description="Server framework to generate (flask, fastapi, express)"
    )

    class Config:
        use_enum_values = True


class MockDataConfig(BaseModel):
    """Configuration for mock data generation."""

    use_examples: bool = Field(
        default=True,
        description="Use examples from schema when available"
    )
    use_defaults: bool = Field(
        default=True,
        description="Use default values from schema when available"
    )
    generate_optional: bool = Field(
        default=True,
        description="Generate values for optional fields"
    )
    array_min_items: int = Field(default=1, description="Minimum items for arrays")
    array_max_items: int = Field(default=5, description="Maximum items for arrays")
    string_min_length: int = Field(default=1, description="Minimum length for strings")
    string_max_length: int = Field(default=50, description="Maximum length for strings")
    number_min: float = Field(default=0, description="Minimum for numbers")
    number_max: float = Field(default=1000, description="Maximum for numbers")
    locale: str = Field(default="en_US", description="Locale for generating realistic data")


class MockHeader(BaseModel):
    """A mock HTTP header."""

    name: str = Field(description="Header name")
    value: str = Field(description="Header value")
    required: bool = Field(default=False, description="Whether the header is required")


class MockResponse(BaseModel):
    """Definition of a mock response."""

    status_code: int = Field(default=200, description="HTTP status code")
    content_type: str = Field(
        default="application/json",
        description="Response content type"
    )
    body: Optional[Any] = Field(default=None, description="Response body")
    body_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for generating response body"
    )
    headers: list[MockHeader] = Field(
        default_factory=list,
        description="Response headers"
    )
    delay_ms: Optional[int] = Field(
        default=None,
        description="Response-specific delay in milliseconds"
    )
    response_type: MockResponseType = Field(
        default=MockResponseType.DYNAMIC,
        description="Type of response generation"
    )
    probability: float = Field(
        default=1.0,
        description="Probability of this response (for random selection)"
    )

    class Config:
        use_enum_values = True


class MockParameter(BaseModel):
    """A mock endpoint parameter."""

    name: str = Field(description="Parameter name")
    location: str = Field(description="Parameter location (path, query, header)")
    required: bool = Field(default=False, description="Whether the parameter is required")
    schema_: Optional[dict[str, Any]] = Field(
        default=None,
        alias="schema",
        description="Parameter schema"
    )
    example: Optional[Any] = Field(default=None, description="Example value")

    class Config:
        populate_by_name = True


class MockRequestBody(BaseModel):
    """A mock request body definition."""

    content_type: str = Field(
        default="application/json",
        description="Request content type"
    )
    required: bool = Field(
        default=False,
        description="Whether the request body is required"
    )
    schema_: Optional[dict[str, Any]] = Field(
        default=None,
        alias="schema",
        description="Request body schema"
    )
    example: Optional[Any] = Field(default=None, description="Example request body")

    class Config:
        populate_by_name = True
