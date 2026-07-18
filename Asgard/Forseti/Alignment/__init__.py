"""
Alignment - cross-format entity alignment (plan 07).

Parses OpenAPI/JSON Schema and Avro schemas into a canonical Intermediate
Representation (IR) and compares fields of the same logical entity across
sources: type contradictions, nullability contract breaches, enum
divergence, precision risk, idiomatic coercions, subset divergence and
lexical-casing divergence. Findings carry stable `align.*` rule ids
registered in the shared Rules registry.

Phase 1 scope (this module): OpenAPI/JSON Schema + Avro adapters.
Protobuf/GraphQL/SQL adapters and the `align discover` wizard are later
phases and are not implemented here.
"""

from Asgard.Forseti.Alignment.services.alignment_checker_service import (
    check_entity_alignment,
)
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService

__all__ = ["IRBuilderService", "check_entity_alignment"]
