"""
CodeGen Base Models - Enums, config, and simple definition models.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TargetLanguage(str, Enum):
    """Target programming languages for code generation."""
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    GOLANG = "golang"
    JAVA = "java"
    CSHARP = "csharp"
    RUST = "rust"
    KOTLIN = "kotlin"
    SWIFT = "swift"


class HttpClientType(str, Enum):
    """HTTP client libraries to use in generated code."""
    FETCH = "fetch"
    AXIOS = "axios"
    REQUESTS = "requests"
    HTTPX = "httpx"
    AIOHTTP = "aiohttp"
    NET_HTTP = "net/http"
    RESTY = "resty"
    OKHTTP = "okhttp"
    HTTPCLIENT = "httpclient"
    REQWEST = "reqwest"


class CodeStyle(str, Enum):
    """Code style preferences."""
    STANDARD = "standard"
    MINIMAL = "minimal"
    VERBOSE = "verbose"


class CodeGenConfig(BaseModel):
    """Configuration for code generation."""

    target_language: TargetLanguage = Field(
        default=TargetLanguage.TYPESCRIPT,
        description="Target programming language"
    )
    http_client: Optional[HttpClientType] = Field(
        default=None,
        description="HTTP client to use (auto-selected if None)"
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Output directory for generated files"
    )
    package_name: str = Field(
        default="api_client",
        description="Package/module name for generated code"
    )
    generate_types: bool = Field(
        default=True,
        description="Generate type definitions/interfaces"
    )
    generate_client: bool = Field(
        default=True,
        description="Generate API client class"
    )
    generate_models: bool = Field(
        default=True,
        description="Generate model classes"
    )
    use_async: bool = Field(
        default=True,
        description="Generate async/await code where supported"
    )
    include_validation: bool = Field(
        default=False,
        description="Include runtime validation"
    )
    include_documentation: bool = Field(
        default=True,
        description="Include JSDoc/docstring documentation"
    )
    strict_types: bool = Field(
        default=True,
        description="Use strict type checking"
    )
    code_style: CodeStyle = Field(
        default=CodeStyle.STANDARD,
        description="Code style preference"
    )
    custom_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Custom headers to include in all requests"
    )
    base_url_config: bool = Field(
        default=True,
        description="Make base URL configurable"
    )
    error_handling: bool = Field(
        default=True,
        description="Include error handling utilities"
    )
    retry_logic: bool = Field(
        default=False,
        description="Include retry logic for failed requests"
    )

    class Config:
        use_enum_values = True


class PropertyDefinition(BaseModel):
    """A property within a type definition."""

    name: str = Field(
        description="Property name"
    )
    type_name: str = Field(
        description="Type name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Property description"
    )
    required: bool = Field(
        default=False,
        description="Whether the property is required"
    )
    nullable: bool = Field(
        default=False,
        description="Whether the property can be null"
    )
    default_value: Optional[Any] = Field(
        default=None,
        description="Default value"
    )
    format: Optional[str] = Field(
        default=None,
        description="Format hint (date, date-time, etc.)"
    )
    is_array: bool = Field(
        default=False,
        description="Whether this is an array type"
    )
    array_item_type: Optional[str] = Field(
        default=None,
        description="Type of array items"
    )


class ParameterDefinition(BaseModel):
    """An API parameter definition."""

    name: str = Field(
        description="Parameter name"
    )
    location: str = Field(
        description="Parameter location (path, query, header)"
    )
    type_name: str = Field(
        description="Parameter type"
    )
    description: Optional[str] = Field(
        default=None,
        description="Parameter description"
    )
    required: bool = Field(
        default=False,
        description="Whether the parameter is required"
    )
    default_value: Optional[Any] = Field(
        default=None,
        description="Default value"
    )
