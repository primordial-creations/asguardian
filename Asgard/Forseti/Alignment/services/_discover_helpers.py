"""
`align discover` wizard helpers - drafts an initial `alignment-config.yaml`
by name-heuristics only (DEEPTHINK_08 3 option 3: heuristics are fine to
*draft* a config a human then edits and commits, never to enforce silently).

Strategy: strip common suffixes (Event/Response/Dto/Input/Payload/Entity)
and casing, then group same-named entities across input files. Each file's
"entity name" candidates come from its top-level schemas/messages/types/
tables (best-effort, format-inferred from extension).
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from Asgard.Forseti.Alignment.models.alignment_models import AlignmentConfig, EntityBinding, EntitySource
from Asgard.Forseti.Database.services.schema_analyzer_service import SchemaAnalyzerService
from Asgard.Forseti.GraphQL.utilities._graphql_parse_utils import parse_sdl
from Asgard.Forseti.Protobuf.services.protobuf_validator_service import ProtobufValidatorService

_SUFFIXES = ("Event", "Response", "Request", "Dto", "DTO", "Input", "Payload", "Entity", "Model")
_SUFFIX_RE = re.compile("(" + "|".join(_SUFFIXES) + ")$")


def strip_suffix(name: str) -> str:
    """Strip a trailing well-known suffix, e.g. `OrderEvent` -> `Order`."""
    return _SUFFIX_RE.sub("", name) or name


def _candidates_for_file(path: str) -> list[tuple[str, EntitySource]]:
    """Best-effort (name, EntitySource) pairs for the top-level entities in one file."""
    ext = Path(path).suffix.lower()
    out: list[tuple[str, EntitySource]] = []
    try:
        if ext == ".avsc":
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            name = document.get("name", Path(path).stem)
            out.append((name, EntitySource(file=path, format="avro")))
        elif ext == ".proto":
            result = ProtobufValidatorService().validate_file(path)
            if result.parsed_schema:
                for message in result.parsed_schema.messages:
                    out.append((message.name, EntitySource(file=path, type=message.name, format="protobuf")))
        elif ext in (".graphql", ".gql"):
            parsed = parse_sdl(Path(path).read_text(encoding="utf-8"))
            for type_name in parsed.get("types", {}):
                out.append((type_name, EntitySource(file=path, type=type_name, format="graphql")))
        elif ext == ".sql":
            schema = SchemaAnalyzerService().analyze_file(path)
            for table in schema.tables:
                out.append((table.name, EntitySource(file=path, table=table.name, format="sql")))
        elif ext in (".yaml", ".yml", ".json"):
            raw_text = Path(path).read_text(encoding="utf-8")
            document: dict[str, Any] = json.loads(raw_text) if ext == ".json" else (yaml.safe_load(raw_text) or {})
            schemas = document.get("components", {}).get("schemas", {}) or document.get("definitions", {})
            if schemas:
                for schema_name in schemas:
                    out.append((schema_name, EntitySource(file=path, schema_name=schema_name, format="openapi")))
            elif document.get("type") or document.get("properties"):
                name = document.get("title", Path(path).stem)
                out.append((name, EntitySource(file=path, format="openapi")))
    except Exception:
        return []
    return out


def discover(paths: list[str]) -> AlignmentConfig:
    """Draft an `AlignmentConfig` from name-heuristic matching across `paths`."""
    grouped: dict[str, list[EntitySource]] = {}
    for path in paths:
        for raw_name, source in _candidates_for_file(path):
            key = strip_suffix(raw_name)
            grouped.setdefault(key, []).append(source)

    entities = {
        name: EntityBinding(sources=sources)
        for name, sources in grouped.items()
        if len(sources) > 1  # only entities that appear cross-format are worth drafting
    }
    return AlignmentConfig(entities=entities)


def write_config(config: AlignmentConfig, output_path: str) -> None:
    """Serialize an `AlignmentConfig` to YAML, matching the plan-07 example shape."""
    payload = config.model_dump(mode="json", exclude_none=True, by_alias=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, default_flow_style=False)
