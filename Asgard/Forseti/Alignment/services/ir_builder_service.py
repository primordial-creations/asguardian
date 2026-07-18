"""
IR Builder Service - format-agnostic dispatch to per-format IR adapters.

Phase 1 (plan 07): OpenAPI/JSON Schema + Avro. Phase 2/3 add Protobuf,
GraphQL and SQL without changing this service's contract - callers always
get an `IRRecord` back regardless of source format.
"""

from typing import Any

from Asgard.Forseti.Alignment.models.ir_models import IRRecord
from Asgard.Forseti.Alignment.services._ir_avro_helpers import avro_schema_to_ir_record
from Asgard.Forseti.Alignment.services._ir_graphql_helpers import graphql_sdl_to_ir_record
from Asgard.Forseti.Alignment.services._ir_openapi_helpers import openapi_schema_to_ir_record
from Asgard.Forseti.Alignment.services._ir_protobuf_helpers import protobuf_schema_to_ir_record
from Asgard.Forseti.Alignment.services._ir_sql_helpers import sql_table_to_ir_record

SUPPORTED_FORMATS = {"openapi", "jsonschema", "avro", "protobuf", "graphql", "sql"}


class IRBuilderService:
    """Builds an `IRRecord` from a raw parsed document, dispatched by format."""

    def build(
        self,
        document: dict[str, Any],
        fmt: str,
        *,
        name: str = "",
        file: str = "",
    ) -> IRRecord:
        """Build an IRRecord. `fmt` in {'openapi', 'jsonschema', 'avro'}."""
        fmt = fmt.lower()
        if fmt in ("openapi", "jsonschema"):
            return openapi_schema_to_ir_record(document, name=name or document.get("title", ""), file=file)
        if fmt == "avro":
            return avro_schema_to_ir_record(document, file=file)
        raise ValueError(f"Unsupported alignment source format: {fmt!r} (supported: {sorted(SUPPORTED_FORMATS)})")

    def build_protobuf(self, schema: Any, message_name: str, *, file: str = "") -> IRRecord:
        """Build an IRRecord from a parsed `ProtobufSchema` + message name."""
        return protobuf_schema_to_ir_record(schema, message_name, file=file)

    def build_graphql(self, parsed_sdl: dict[str, Any], type_name: str, *, file: str = "") -> IRRecord:
        """Build an IRRecord from `parse_sdl(...)` output + a type name."""
        return graphql_sdl_to_ir_record(parsed_sdl, type_name, file=file)

    def build_sql(self, table: Any, *, file: str = "") -> IRRecord:
        """Build an IRRecord from a parsed `TableDefinition`."""
        return sql_table_to_ir_record(table, file=file)
