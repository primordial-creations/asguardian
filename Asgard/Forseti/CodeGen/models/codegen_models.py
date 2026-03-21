"""
CodeGen Models - Pydantic models for API client code generation.

These models represent code generation configurations, generated files,
and generation results for various programming languages.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.CodeGen.models._codegen_base_models import (
    CodeGenConfig,
    CodeStyle,
    HttpClientType,
    ParameterDefinition,
    PropertyDefinition,
    TargetLanguage,
)


class GeneratedFile(BaseModel):
    """A generated source code file."""

    path: str = Field(
        description="Relative path for the file"
    )
    content: str = Field(
        description="File content"
    )
    language: TargetLanguage = Field(
        description="Programming language"
    )
    file_type: str = Field(
        description="Type of file (client, model, types, util)"
    )
    line_count: int = Field(
        default=0,
        description="Number of lines in the file"
    )

    class Config:
        use_enum_values = True

    @property
    def extension(self) -> str:
        """Get file extension based on language."""
        extensions = {
            TargetLanguage.TYPESCRIPT: ".ts",
            TargetLanguage.PYTHON: ".py",
            TargetLanguage.GOLANG: ".go",
            TargetLanguage.JAVA: ".java",
            TargetLanguage.CSHARP: ".cs",
            TargetLanguage.RUST: ".rs",
            TargetLanguage.KOTLIN: ".kt",
            TargetLanguage.SWIFT: ".swift",
        }
        return extensions.get(self.language, ".txt")


class TypeDefinition(BaseModel):
    """A type/interface definition."""

    name: str = Field(
        description="Type name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Type description"
    )
    properties: dict[str, "PropertyDefinition"] = Field(
        default_factory=dict,
        description="Type properties"
    )
    required_properties: list[str] = Field(
        default_factory=list,
        description="Required property names"
    )
    is_enum: bool = Field(
        default=False,
        description="Whether this is an enum type"
    )
    enum_values: list[Any] = Field(
        default_factory=list,
        description="Enum values if is_enum is True"
    )
    extends: Optional[str] = Field(
        default=None,
        description="Parent type to extend"
    )


class MethodDefinition(BaseModel):
    """An API method definition."""

    name: str = Field(
        description="Method name"
    )
    http_method: str = Field(
        description="HTTP method (GET, POST, etc.)"
    )
    path: str = Field(
        description="API path"
    )
    description: Optional[str] = Field(
        default=None,
        description="Method description"
    )
    parameters: list["ParameterDefinition"] = Field(
        default_factory=list,
        description="Method parameters"
    )
    request_body_type: Optional[str] = Field(
        default=None,
        description="Request body type"
    )
    response_type: Optional[str] = Field(
        default=None,
        description="Response type"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="API tags"
    )
    deprecated: bool = Field(
        default=False,
        description="Whether the method is deprecated"
    )
    security: list[str] = Field(
        default_factory=list,
        description="Required security schemes"
    )


class CodeGenReport(BaseModel):
    """Report from code generation."""

    success: bool = Field(
        description="Whether generation was successful"
    )
    source_spec: Optional[str] = Field(
        default=None,
        description="Source specification path"
    )
    target_language: TargetLanguage = Field(
        description="Target language"
    )
    generated_files: list[GeneratedFile] = Field(
        default_factory=list,
        description="List of generated files"
    )
    types_generated: int = Field(
        default=0,
        description="Number of types generated"
    )
    methods_generated: int = Field(
        default=0,
        description="Number of methods generated"
    )
    total_lines: int = Field(
        default=0,
        description="Total lines of code generated"
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

    @property
    def file_count(self) -> int:
        """Get number of generated files."""
        return len(self.generated_files)


TypeDefinition.model_rebuild()


__all__ = [
    "CodeGenConfig",
    "CodeGenReport",
    "CodeStyle",
    "GeneratedFile",
    "HttpClientType",
    "MethodDefinition",
    "ParameterDefinition",
    "PropertyDefinition",
    "TargetLanguage",
    "TypeDefinition",
]
