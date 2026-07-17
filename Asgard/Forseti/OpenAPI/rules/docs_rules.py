"""
OpenAPI Documentation Rules - descriptions, summaries, tags, contact and
license metadata (plan 03 Phase 1, Linter layer).
"""

from typing import Any, Iterator

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    description_quality,
    escape_pointer,
    iter_component_schemas,
    iter_operations,
    iter_parameters,
    openapi_rule,
)
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    Severity,
)

_DOCS = RuleCategory.DOCS


@openapi_rule(
    "oas.docs.info-description", Severity.WARNING, category=_DOCS,
    description="info should carry a description",
    rationale="The info description is the API's front door for consumers.",
)
def check_info_description(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    info = document.get("info")
    if isinstance(info, dict) and not str(info.get("description") or "").strip():
        yield "/info", "info.description is missing or empty"


@openapi_rule(
    "oas.docs.info-contact", Severity.INFO, category=_DOCS,
    description="info should declare a contact",
    rationale="Consumers need a channel for support and change notices.",
)
def check_info_contact(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    info = document.get("info")
    if isinstance(info, dict) and not info.get("contact"):
        yield "/info", "info.contact is missing"


@openapi_rule(
    "oas.docs.info-license", Severity.INFO, category=_DOCS,
    description="info should declare a license",
    rationale="License terms govern how the API description may be reused.",
)
def check_info_license(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    info = document.get("info")
    if isinstance(info, dict) and not info.get("license"):
        yield "/info", "info.license is missing"


@openapi_rule(
    "oas.docs.operation-description", Severity.WARNING, category=_DOCS,
    description="Every operation should have a description",
    rationale="Undescribed operations force consumers to guess behaviour.",
)
def check_operation_description(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if not str(operation.get("description") or "").strip():
            yield json_path, f"Operation {method.upper()} {path} has no description"


@openapi_rule(
    "oas.docs.operation-summary", Severity.WARNING, category=_DOCS,
    description="Every operation should have a summary",
    rationale="Summaries drive navigation in rendered documentation.",
)
def check_operation_summary(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if not str(operation.get("summary") or "").strip():
            yield json_path, f"Operation {method.upper()} {path} has no summary"


@openapi_rule(
    "oas.docs.operation-id", Severity.WARNING, category=_DOCS,
    description="Every operation should declare an operationId",
    rationale="operationIds anchor client generation, links and telemetry.",
)
def check_operation_id(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if not str(operation.get("operationId") or "").strip():
            yield json_path, f"Operation {method.upper()} {path} has no operationId"


@openapi_rule(
    "oas.docs.operation-tags", Severity.WARNING, category=_DOCS,
    description="Every operation should carry at least one tag",
    rationale="Untagged operations fall outside every documentation group.",
)
def check_operation_tags(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if not operation.get("tags"):
            yield json_path, f"Operation {method.upper()} {path} has no tags"


@openapi_rule(
    "oas.docs.tags-defined", Severity.WARNING, category=_DOCS,
    description="Operation tags should be declared in the global tags list",
    rationale="Undeclared tags render without descriptions or ordering.",
)
def check_tags_defined(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    declared = {tag.get("name") for tag in (document.get("tags") or [])
                if isinstance(tag, dict)}
    if not declared:
        return
    for path, method, operation, json_path in iter_operations(document):
        for tag in operation.get("tags") or []:
            if tag not in declared:
                yield (f"{json_path}/tags",
                       f"Tag '{tag}' on {method.upper()} {path} is not declared "
                       "in the global tags list")


@openapi_rule(
    "oas.docs.tag-description", Severity.INFO, category=_DOCS,
    description="Global tags should have descriptions",
    rationale="Tag descriptions introduce each documentation section.",
)
def check_tag_description(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for index, tag in enumerate(document.get("tags") or []):
        if isinstance(tag, dict) and not str(tag.get("description") or "").strip():
            yield f"/tags/{index}", f"Tag '{tag.get('name')}' has no description"


@openapi_rule(
    "oas.docs.parameter-description", Severity.INFO, category=_DOCS,
    description="Parameters should have descriptions",
    rationale="Parameter semantics (units, formats, defaults) live in "
              "descriptions.",
)
def check_parameter_description(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for param, json_path, context in iter_parameters(document):
        if not str(param.get("description") or "").strip():
            yield (json_path,
                   f"Parameter '{param.get('name')}' ({context}) has no description")


@openapi_rule(
    "oas.docs.schema-description", Severity.INFO, category=_DOCS,
    description="Component schemas should have descriptions",
    rationale="Schema descriptions are the data dictionary of the API.",
)
def check_schema_description(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        if "$ref" in schema:
            continue
        if not str(schema.get("description") or "").strip():
            yield json_path, f"Schema '{name}' has no description"


@openapi_rule(
    "oas.docs.non-trivial-description", Severity.WARNING, category=_DOCS,
    confidence=Confidence.HEURISTIC,
    description="Descriptions must not be placeholders, tautologies or stubs",
    rationale="'TODO' and 'The billing address' for billingAddress convey "
              "zero information; the coverage metric must not be gameable "
              "(DEEPTHINK_08).",
)
def check_description_entropy(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        text = operation.get("description")
        if text:
            ok, reason = description_quality(
                operation.get("operationId") or f"{method} {path}", text
            )
            if not ok:
                yield (f"{json_path}/description",
                       f"Description of {method.upper()} {path} is low-quality: "
                       f"{reason}")
    for name, schema, schema_path in iter_component_schemas(document):
        for prop, prop_schema in (schema.get("properties") or {}).items():
            if not isinstance(prop_schema, dict):
                continue
            text = prop_schema.get("description")
            if text:
                ok, reason = description_quality(prop, text)
                if not ok:
                    yield (f"{schema_path}/properties/{escape_pointer(prop)}"
                           "/description",
                           f"Description of {name}.{prop} is low-quality: {reason}")
