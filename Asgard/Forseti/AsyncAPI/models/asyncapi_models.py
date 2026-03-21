"""
AsyncAPI Models - Pydantic models for AsyncAPI specification handling.

These models represent AsyncAPI 2.x/3.x specification structures and
validation results for event-driven and message-based APIs.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.AsyncAPI.models._asyncapi_base_models import (
    AsyncAPIConfig,
    AsyncAPIInfo,
    AsyncAPIValidationError,
    AsyncAPIVersion,
    Channel,
    ChannelType,
    MessageInfo,
    OperationInfo,
    ProtocolType,
    ServerInfo,
    ValidationSeverity,
)


class AsyncAPISpec(BaseModel):
    """Complete AsyncAPI specification."""

    asyncapi: str = Field(
        description="AsyncAPI version string"
    )
    id: Optional[str] = Field(
        default=None,
        description="Application identifier"
    )
    info: AsyncAPIInfo = Field(
        description="API information"
    )
    servers: Optional[dict[str, ServerInfo]] = Field(
        default=None,
        description="Server definitions"
    )
    channels: dict[str, Any] = Field(
        default_factory=dict,
        description="Channel definitions"
    )
    components: Optional[dict[str, Any]] = Field(
        default=None,
        description="Reusable components"
    )
    tags: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="API tags"
    )
    external_docs: Optional[dict[str, Any]] = Field(
        default=None,
        alias="externalDocs",
        description="External documentation"
    )
    default_content_type: Optional[str] = Field(
        default=None,
        alias="defaultContentType",
        description="Default content type for messages"
    )

    class Config:
        populate_by_name = True

    @property
    def version(self) -> AsyncAPIVersion:
        """Return the AsyncAPI version as an enum."""
        if self.asyncapi.startswith("3."):
            return AsyncAPIVersion.V3_0
        elif self.asyncapi.startswith("2.6"):
            return AsyncAPIVersion.V2_6
        elif self.asyncapi.startswith("2.5"):
            return AsyncAPIVersion.V2_5
        elif self.asyncapi.startswith("2.4"):
            return AsyncAPIVersion.V2_4
        elif self.asyncapi.startswith("2.3"):
            return AsyncAPIVersion.V2_3
        elif self.asyncapi.startswith("2.2"):
            return AsyncAPIVersion.V2_2
        elif self.asyncapi.startswith("2.1"):
            return AsyncAPIVersion.V2_1
        elif self.asyncapi.startswith("2.0"):
            return AsyncAPIVersion.V2_0
        return AsyncAPIVersion.V2_6

    @property
    def channel_count(self) -> int:
        """Return the number of channels."""
        return len(self.channels)

    @property
    def server_count(self) -> int:
        """Return the number of servers."""
        return len(self.servers) if self.servers else 0


class AsyncAPIValidationResult(BaseModel):
    """Result of AsyncAPI specification validation."""

    is_valid: bool = Field(
        description="Whether the specification is valid"
    )
    spec_path: Optional[str] = Field(
        default=None,
        description="Path to the validated specification file"
    )
    asyncapi_version: Optional[AsyncAPIVersion] = Field(
        default=None,
        description="Detected AsyncAPI version"
    )
    errors: list[AsyncAPIValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: list[AsyncAPIValidationError] = Field(
        default_factory=list,
        description="List of validation warnings"
    )
    info_messages: list[AsyncAPIValidationError] = Field(
        default_factory=list,
        description="List of informational messages"
    )
    validated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of validation"
    )
    validation_time_ms: float = Field(
        default=0.0,
        description="Time taken to validate in milliseconds"
    )

    class Config:
        use_enum_values = True

    @property
    def error_count(self) -> int:
        """Return the number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Return the number of warnings."""
        return len(self.warnings)

    @property
    def total_issues(self) -> int:
        """Return total number of issues (errors + warnings)."""
        return self.error_count + self.warning_count


class AsyncAPIReport(BaseModel):
    """Comprehensive report for AsyncAPI specification analysis."""

    spec_path: Optional[str] = Field(
        default=None,
        description="Path to the specification file"
    )
    validation_result: AsyncAPIValidationResult = Field(
        description="Validation result"
    )
    spec: Optional[AsyncAPISpec] = Field(
        default=None,
        description="Parsed specification"
    )
    channels: list[Channel] = Field(
        default_factory=list,
        description="Parsed channels"
    )
    message_count: int = Field(
        default=0,
        description="Total number of messages"
    )
    protocol_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of channels by protocol"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Report generation timestamp"
    )


__all__ = [
    "AsyncAPIConfig",
    "AsyncAPIInfo",
    "AsyncAPIReport",
    "AsyncAPISpec",
    "AsyncAPIValidationError",
    "AsyncAPIValidationResult",
    "AsyncAPIVersion",
    "Channel",
    "ChannelType",
    "MessageInfo",
    "OperationInfo",
    "ProtocolType",
    "ServerInfo",
    "ValidationSeverity",
]
