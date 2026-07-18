"""
Alignment - cross-format entity alignment (plan 07).

Parses OpenAPI/JSON Schema, Avro, Protobuf, GraphQL and SQL (Database
module) schemas into a canonical Intermediate Representation (IR) and
compares fields of the same logical entity across sources: type
contradictions, nullability contract breaches, enum divergence, precision
risk, idiomatic coercions, subset divergence and lexical-casing
divergence. Findings carry stable `align.*` rule ids registered in the
shared Rules registry.

`AlignmentLoaderService`-equivalent free functions (`load_config`,
`build_ir_record`, `check_config`) resolve an external `alignment-config.
yaml` catalog into IR and run the full check; `align discover` drafts an
initial config from cross-file name heuristics (never used to enforce).
CLI: `forseti align check --config alignment-config.yaml`,
`forseti align discover <paths...> -o alignment-config.yaml`. `forseti
audit <path>` auto-runs `align check` when `alignment-config.yaml` is
present at the audited path.
"""

from Asgard.Forseti.Alignment.services.alignment_checker_service import (
    check_entity_alignment,
)
from Asgard.Forseti.Alignment.services.alignment_loader_service import (
    build_ir_record,
    check_config,
    load_config,
)
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService

__all__ = [
    "IRBuilderService",
    "check_entity_alignment",
    "load_config",
    "build_ir_record",
    "check_config",
]
