"""
OpenAPI Example Rules - every example must validate against its own
schema (plan 03, DEEPTHINK_08 anti-gaming; RESEARCH_09 ties example
validity to time-to-first-successful-call).

Validation reuses the JSONSchema module; refs are resolved locally first.
OpenAPI 3.0 `nullable` is shimmed onto the type before validation.
"""

import copy
from typing import Any, Iterator, Optional

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    escape_pointer,
    iter_operations,
    openapi_rule,
)
from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import resolve_pointer
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, Severity

_MAX_DEPTH = 30


def _prepare_schema(document: dict[str, Any], schema: Any,
                    depth: int = 0, seen: Optional[frozenset] = None) -> Any:
    """Inline local refs and apply the 3.0 nullable shim (cycle-safe)."""
    seen = seen or frozenset()
    if depth > _MAX_DEPTH:
        return {}
    if isinstance(schema, list):
        return [_prepare_schema(document, item, depth + 1, seen) for item in schema]
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in seen or not ref.startswith("#/"):
            return {}  # break cycles / skip external refs: permissive schema
        target = resolve_pointer(document, ref)
        if target is None:
            return {}
        merged = {k: v for k, v in schema.items() if k != "$ref"}
        prepared = _prepare_schema(document, target, depth + 1, seen | {ref})
        if isinstance(prepared, dict):
            prepared = {**prepared, **merged} if merged else prepared
        return prepared
    result = {k: _prepare_schema(document, v, depth + 1, seen)
              for k, v in schema.items()}
    if result.pop("nullable", False):
        declared = result.get("type")
        if isinstance(declared, str):
            result["type"] = [declared, "null"]
        elif isinstance(declared, list) and "null" not in declared:
            result["type"] = declared + ["null"]
    return result


def _validate_example(document: dict[str, Any], schema: dict[str, Any],
                      example: Any) -> list[str]:
    """Validate one example value; returns error messages."""
    from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig
    from Asgard.Forseti.JSONSchema.services.schema_validator_service import (
        SchemaValidatorService,
    )

    prepared = _prepare_schema(document, copy.deepcopy(schema))
    if not isinstance(prepared, dict):
        return []
    prepared.pop("example", None)
    prepared.pop("examples", None)
    validator = SchemaValidatorService(
        JSONSchemaConfig(strict_mode=False, resolve_references=False)
    )
    result = validator.validate(example, prepared)
    return [f"{error.path}: {error.message}" for error in result.errors]


def _iter_schema_examples(
    document: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], Any, str, str]]:
    """Yield (schema, example, json_path, label) pairs from the document."""
    # Component-schema level `example`
    schemas = (document.get("components") or {}).get("schemas") or {}
    for name, schema in schemas.items():
        if isinstance(schema, dict) and "example" in schema:
            yield (schema, schema["example"],
                   f"/components/schemas/{escape_pointer(name)}/example",
                   f"schema '{name}'")

    # Media-type example / examples (request bodies + responses)
    for path, method, operation, op_path in iter_operations(document):
        label = f"{method.upper()} {path}"
        containers: list[tuple[str, Any]] = []
        body = operation.get("requestBody")
        if isinstance(body, dict):
            containers.append((f"{op_path}/requestBody", body))
        for status, response in (operation.get("responses") or {}).items():
            if isinstance(response, dict):
                containers.append(
                    (f"{op_path}/responses/{escape_pointer(str(status))}", response)
                )
        for base, container in containers:
            for media, media_obj in (container.get("content") or {}).items():
                if not isinstance(media_obj, dict):
                    continue
                schema = media_obj.get("schema")
                if not isinstance(schema, dict):
                    continue
                media_base = f"{base}/content/{escape_pointer(media)}"
                if "example" in media_obj:
                    yield schema, media_obj["example"], f"{media_base}/example", label
                for ex_name, ex in (media_obj.get("examples") or {}).items():
                    if isinstance(ex, dict) and "value" in ex:
                        yield (schema, ex["value"],
                               f"{media_base}/examples/{escape_pointer(ex_name)}/value",
                               f"{label} example '{ex_name}'")

        # Parameter examples
        for index, param in enumerate(operation.get("parameters") or []):
            if not isinstance(param, dict) or "$ref" in param:
                continue
            schema = param.get("schema")
            if isinstance(schema, dict) and "example" in param:
                yield (schema, param["example"],
                       f"{op_path}/parameters/{index}/example",
                       f"{label} parameter '{param.get('name')}'")


@openapi_rule(
    "oas.examples.example-matches-schema", Severity.WARNING,
    category=RuleCategory.DOCS,
    description="Examples must validate against their own schema",
    rationale="An invalid example is a documented lie: it fails the first "
              "copy-paste request a consumer makes (RESEARCH_09 TTFSC).",
)
def check_examples_valid(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for schema, example, json_path, label in _iter_schema_examples(document):
        errors = _validate_example(document, schema, example)
        for error in errors[:5]:
            yield json_path, f"Example for {label} does not match its schema: {error}"
