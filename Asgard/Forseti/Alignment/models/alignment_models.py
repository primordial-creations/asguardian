"""
Alignment Config and Report models.

`AlignmentConfig` is the external entity catalog (DEEPTHINK_08 §3 option 1):
a hand-authored YAML mapping a logical entity name to its per-format
sources, plus direction edges (which source is the producer for a given
consumer) that drive severity, and an `ignore_fields` escape hatch for
intentional subsetting.
"""

from typing import Optional

from pydantic import BaseModel, Field


class EntitySource(BaseModel):
    """One format-specific location for a logical entity."""

    file: str
    type: Optional[str] = Field(default=None, description="Type/message name within the file")
    schema_name: Optional[str] = Field(default=None, description="OpenAPI components.schemas key")
    table: Optional[str] = Field(default=None, description="SQL table name")
    format: Optional[str] = Field(
        default=None,
        description="Explicit format override; inferred from file extension if omitted",
    )


class DirectionEdge(BaseModel):
    """Producer -> consumer edge between two sources of the same entity."""

    from_source: str = Field(alias="from")
    to_source: str = Field(alias="to")

    model_config = {"populate_by_name": True}


class EntityBinding(BaseModel):
    """One logical entity's cross-format sources + direction edges."""

    sources: list[EntitySource] = Field(default_factory=list)
    direction: list[DirectionEdge] = Field(default_factory=list)
    ignore_fields: list[str] = Field(default_factory=list)


class AlignmentConfig(BaseModel):
    """Parsed `alignment-config.yaml`."""

    entities: dict[str, EntityBinding] = Field(default_factory=dict)


class AlignmentReport(BaseModel):
    """Summary of an alignment check run (findings flow through Reporting.Finding)."""

    entities_checked: list[str] = Field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    @property
    def build_passes(self) -> bool:
        """Exit-code driver: fails iff any CRITICAL finding."""
        return self.critical_count == 0
