"""
Alignment Loader Service - resolves `alignment-config.yaml` entity sources
into IRRecords, and runs the full check across every configured entity.

Format is inferred from the file extension unless `EntitySource.format` is
set explicitly:
  .yaml/.yml/.json (openapi-shaped)  -> openapi
  .avsc                              -> avro
  .proto                             -> protobuf (requires `type`)
  .graphql/.gql                      -> graphql (requires `type`)
  .sql                                -> sql (requires `table`)
"""

import json
from pathlib import Path
from typing import Any

import yaml

from Asgard.Forseti.Alignment.models.alignment_models import (
    AlignmentConfig,
    AlignmentReport,
    EntityBinding,
    EntitySource,
)
from Asgard.Forseti.Alignment.models.ir_models import IRRecord
from Asgard.Forseti.Alignment.services.alignment_checker_service import check_entity_alignment
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService
from Asgard.Forseti.Database.services.schema_analyzer_service import SchemaAnalyzerService
from Asgard.Forseti.GraphQL.utilities._graphql_parse_utils import parse_sdl
from Asgard.Forseti.Protobuf.services.protobuf_validator_service import ProtobufValidatorService
from Asgard.Forseti.Reporting.models.finding_models import Finding
from Asgard.Forseti.Rules.models._rule_base_models import Severity

_EXT_FORMAT_MAP = {
    ".avsc": "avro",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".sql": "sql",
}


def infer_format(source: EntitySource) -> str:
    """Infer the source format from an explicit override or file extension."""
    if source.format:
        return source.format.lower()
    ext = Path(source.file).suffix.lower()
    return _EXT_FORMAT_MAP.get(ext, "openapi")


def load_config(path: str) -> AlignmentConfig:
    """Load and validate `alignment-config.yaml`."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return AlignmentConfig.model_validate(raw)


def build_ir_record(source: EntitySource, base_dir: str = "") -> IRRecord:
    """Resolve one `EntitySource` into an `IRRecord`, dispatched by format."""
    file_path = str(Path(base_dir) / source.file) if base_dir else source.file
    fmt = infer_format(source)
    builder = IRBuilderService()

    if fmt == "protobuf":
        if not source.type:
            raise ValueError(f"Protobuf source {source.file!r} requires `type` (message name)")
        result = ProtobufValidatorService().validate_file(file_path)
        if result.parsed_schema is None:
            raise ValueError(f"Failed to parse Protobuf file {file_path!r}: {result.errors}")
        return builder.build_protobuf(result.parsed_schema, source.type, file=source.file)

    if fmt == "graphql":
        if not source.type:
            raise ValueError(f"GraphQL source {source.file!r} requires `type`")
        sdl = Path(file_path).read_text(encoding="utf-8")
        parsed = parse_sdl(sdl)
        return builder.build_graphql(parsed, source.type, file=source.file)

    if fmt == "sql":
        if not source.table:
            raise ValueError(f"SQL source {source.file!r} requires `table`")
        schema = SchemaAnalyzerService().analyze_file(file_path)
        table = next((t for t in schema.tables if t.name == source.table), None)
        if table is None:
            raise ValueError(f"Table {source.table!r} not found in {file_path!r}")
        return builder.build_sql(table, file=source.file)

    # openapi / jsonschema / avro: raw dict from JSON/YAML.
    raw_text = Path(file_path).read_text(encoding="utf-8")
    document: dict[str, Any]
    if file_path.endswith(".json"):
        document = json.loads(raw_text)
    else:
        document = yaml.safe_load(raw_text) or {}

    if fmt == "avro":
        return builder.build(document, "avro", file=source.file)

    # openapi: resolve components.schemas[schema_name] if given, else use document itself.
    schema_doc = document
    name = source.schema_name or ""
    if source.schema_name:
        schema_doc = (
            document.get("components", {}).get("schemas", {}).get(source.schema_name)
            or document.get("definitions", {}).get(source.schema_name)
            or document
        )
    return builder.build(schema_doc, "openapi", name=name or source.schema_name or "", file=source.file)


def check_config(config: AlignmentConfig, base_dir: str = "", entity_filter: str = "") -> tuple[list[Finding], AlignmentReport]:
    """Resolve every entity's sources to IR and run alignment checks across all of them."""
    all_findings: list[Finding] = []
    report = AlignmentReport()

    for entity_name, binding in config.entities.items():
        if entity_filter and entity_name != entity_filter:
            continue
        sources: dict[str, IRRecord] = {}
        for source in binding.sources:
            label = source.file
            sources[label] = build_ir_record(source, base_dir=base_dir)

        edges = [(edge.from_source, edge.to_source) for edge in binding.direction]
        findings = check_entity_alignment(
            entity_name, sources, direction_edges=edges, ignore_fields=set(binding.ignore_fields)
        )
        all_findings.extend(findings)
        report.entities_checked.append(entity_name)
        for finding in findings:
            if finding.severity == Severity.ERROR:
                report.critical_count += 1
            elif finding.severity == Severity.WARNING:
                report.warning_count += 1
            else:
                report.info_count += 1

    return all_findings, report
