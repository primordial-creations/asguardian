"""
Legacy Models - the single shared base for the previously triplicated
per-format `BreakingChange` models (plan 01 step 1).

`Contracts.models.contract_models.BreakingChange`,
`Avro.models.avro_models.BreakingChange` and
`Protobuf.models.protobuf_models.BreakingChange` now subclass this base,
keeping their public fields and per-format `BreakingChangeType` enums for
one deprecation cycle. New code should use `UnifiedChange`.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LegacyBreakingChange(BaseModel):
    """Shared shape of the deprecated per-format BreakingChange models."""

    change_type: str = Field(description="Type of breaking change")
    path: str = Field(description="Path to the changed element")
    message: str = Field(description="Human-readable description of the change")
    old_value: Optional[str] = Field(
        default=None,
        description="Old value before the change",
    )
    new_value: Optional[str] = Field(
        default=None,
        description="New value after the change",
    )
    severity: str = Field(
        default="error",
        description="Severity of the breaking change",
    )
    mitigation: Optional[str] = Field(
        default=None,
        description="Suggested mitigation for the breaking change",
    )

    class Config:
        use_enum_values = True
