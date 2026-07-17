"""
Canonical Intermediate Representation (IR) models for cross-format alignment.

DEEPTHINK_08's blueprint: instead of comparing OpenAPI/Avro/GraphQL/SQL
schemas pairwise (six formats -> fifteen bespoke comparators), every format
adapter projects into this small IR, and a single checker compares IR
records against each other. Nullability, presence-requirement and type
capacity are normalized here so the checker never needs format knowledge.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TypeClass(str, Enum):
    """Canonical type classes every format's scalar/composite types map onto."""

    BOOL = "bool"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    DECIMAL = "decimal"
    STRING = "string"
    BYTES = "bytes"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    RECORD = "record"
    LIST = "list"
    MAP = "map"
    ENUM = "enum"
    VARIANT = "variant"
    ANY = "any"


class SourceRef(BaseModel):
    """Where an IR node came from, for reporting."""

    file: str = Field(default="")
    format: str = Field(default="")
    path: str = Field(default="/")


class IRType(BaseModel):
    """A resolved type: class plus optional composite/enum detail."""

    type_class: TypeClass
    item_type: Optional["IRType"] = Field(default=None, description="LIST element type")
    enum_symbols: list[str] = Field(default_factory=list)
    record_name: Optional[str] = Field(default=None, description="RECORD/VARIANT target name")


class IRField(BaseModel):
    """A single field/property, normalized across formats."""

    raw_name: str
    lexical_tokens: tuple[str, ...] = Field(default_factory=tuple)
    type: IRType
    nullable: bool = Field(default=False, description="Normalized nullability")
    required: bool = Field(default=False, description="Presence-required (distinct from nullable)")
    default: Any = None
    doc: Optional[str] = Field(default=None)
    source: SourceRef = Field(default_factory=SourceRef)


class IRRecord(BaseModel):
    """A record/message/object type: the unit `Alignment` compares."""

    name: str
    fields: list[IRField] = Field(default_factory=list)
    source: SourceRef = Field(default_factory=SourceRef)

    def field_by_tokens(self, tokens: tuple[str, ...]) -> Optional[IRField]:
        """Find a field whose lexical tokens exactly match."""
        for field in self.fields:
            if field.lexical_tokens == tokens:
                return field
        return None


IRType.model_rebuild()
