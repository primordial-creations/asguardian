"""
OpenAPI Structure Rules - reference integrity, uniqueness, and shape
checks (plan 03 Phase 1, Compiler layer: deterministic ERRORs).
"""

import re
from typing import Any, Iterator

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    HTTP_METHODS,
    escape_pointer,
    iter_operations,
    openapi_rule,
)
from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import (
    find_broken_refs,
    find_unused_schemas,
)
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    Severity,
)

_STRUCT = RuleCategory.STRUCTURE


@openapi_rule(
    "oas.structure.no-broken-refs", Severity.ERROR, category=_STRUCT, core=True,
    description="All local $ref pointers must resolve",
    rationale="A dangling $ref makes the document unusable for codegen, "
              "validation and documentation tooling.",
)
def check_broken_refs(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for json_path, ref in find_broken_refs(document):
        yield json_path, f"Unresolvable reference: {ref}"


@openapi_rule(
    "oas.structure.operation-id-unique", Severity.ERROR, category=_STRUCT,
    description="operationId values must be unique across the document",
    rationale="Duplicate operationIds break client generation and link objects.",
)
def check_operation_id_unique(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    seen: dict[str, str] = {}
    for path, method, operation, json_path in iter_operations(document):
        op_id = operation.get("operationId")
        if not isinstance(op_id, str) or not op_id:
            continue
        if op_id in seen:
            yield (f"{json_path}/operationId",
                   f"Duplicate operationId '{op_id}' (also used by {seen[op_id]})")
        else:
            seen[op_id] = f"{method.upper()} {path}"


@openapi_rule(
    "oas.structure.no-duplicate-parameters", Severity.ERROR, category=_STRUCT,
    description="An operation must not declare the same (name, in) parameter twice",
    rationale="Duplicate parameters are ambiguous: consumers cannot know "
              "which definition applies.",
)
def check_duplicate_parameters(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        seen: set[tuple[str, str]] = set()
        for param in operation.get("parameters") or []:
            if not isinstance(param, dict) or "$ref" in param:
                continue
            key = (str(param.get("name")), str(param.get("in")))
            if key in seen:
                yield (f"{json_path}/parameters",
                       f"Duplicate parameter '{key[0]}' (in: {key[1]}) "
                       f"on {method.upper()} {path}")
            seen.add(key)


@openapi_rule(
    "oas.structure.parameter-name-and-in", Severity.ERROR, category=_STRUCT,
    description="Parameters must declare both 'name' and 'in'",
    rationale="A parameter without name/in cannot be sent by any client.",
)
def check_parameter_name_in(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        for index, param in enumerate(operation.get("parameters") or []):
            if not isinstance(param, dict) or "$ref" in param:
                continue
            for field in ("name", "in"):
                if not param.get(field):
                    yield (f"{json_path}/parameters/{index}",
                           f"Parameter #{index} on {method.upper()} {path} "
                           f"missing required field: {field}")


@openapi_rule(
    "oas.structure.path-params-unique", Severity.ERROR, category=_STRUCT,
    description="A path template must not repeat a parameter name",
    rationale="'/a/{id}/b/{id}' is ambiguous and rejected by routers.",
)
def check_path_template_unique(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path in (document.get("paths") or {}):
        names = re.findall(r"\{([^}]+)\}", str(path))
        duplicates = {n for n in names if names.count(n) > 1}
        for name in sorted(duplicates):
            yield (f"/paths/{escape_pointer(path)}",
                   f"Path parameter '{{{name}}}' appears more than once in {path}")


@openapi_rule(
    "oas.structure.no-query-in-path", Severity.ERROR, category=_STRUCT,
    description="Path templates must not embed query strings or fragments",
    rationale="Query parameters belong in 'parameters' with in: query; "
              "embedded '?' breaks path matching.",
)
def check_no_query_in_path(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path in (document.get("paths") or {}):
        if "?" in str(path) or "#" in str(path):
            yield (f"/paths/{escape_pointer(path)}",
                   f"Path contains query string or fragment: {path}")


@openapi_rule(
    "oas.structure.no-equivalent-paths", Severity.WARNING, category=_STRUCT,
    description="Paths must not be equivalent up to parameter renaming",
    rationale="'/users/{id}' and '/users/{userId}' are the same route; "
              "one of them is unreachable.",
)
def check_equivalent_paths(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    normalized: dict[str, str] = {}
    for path in (document.get("paths") or {}):
        canonical = re.sub(r"\{[^}]+\}", "{}", str(path))
        if canonical in normalized and normalized[canonical] != path:
            yield (f"/paths/{escape_pointer(path)}",
                   f"Path {path} is equivalent to {normalized[canonical]} "
                   "(differs only in parameter names)")
        else:
            normalized.setdefault(canonical, str(path))


_STATUS_RE = re.compile(r"^[1-5](\d{2}|XX)$")


@openapi_rule(
    "oas.structure.valid-status-codes", Severity.ERROR, category=_STRUCT,
    description="Response keys must be valid HTTP status codes, ranges or 'default'",
    rationale="Invalid status-code keys are silently dropped by consumers.",
)
def check_valid_status_codes(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        for status in (operation.get("responses") or {}):
            code = str(status)
            if code != "default" and not _STATUS_RE.match(code):
                yield (f"{json_path}/responses/{escape_pointer(code)}",
                       f"Invalid response status code '{code}' "
                       f"on {method.upper()} {path}")


@openapi_rule(
    "oas.structure.request-body-content", Severity.ERROR, category=_STRUCT,
    description="requestBody must define at least one media type in content",
    rationale="A request body without content is unusable by clients.",
)
def check_request_body_content(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        body = operation.get("requestBody")
        if isinstance(body, dict) and "$ref" not in body and not body.get("content"):
            yield (f"{json_path}/requestBody",
                   f"requestBody on {method.upper()} {path} has no content media types")


@openapi_rule(
    "oas.structure.media-type-schema", Severity.WARNING, category=_STRUCT,
    description="Media type objects should define a schema",
    rationale="Without a schema the payload shape is undocumented and "
              "unvalidatable (top empirical gap, RESEARCH_09).",
)
def check_media_type_schema(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        containers = [("requestBody", operation.get("requestBody"))]
        for status, response in (operation.get("responses") or {}).items():
            containers.append((f"responses/{escape_pointer(str(status))}", response))
        for label, container in containers:
            if not isinstance(container, dict) or "$ref" in container:
                continue
            for media, media_obj in (container.get("content") or {}).items():
                if isinstance(media_obj, dict) and "schema" not in media_obj:
                    yield (f"{json_path}/{label}/content/{escape_pointer(media)}",
                           f"Media type '{media}' on {method.upper()} {path} "
                           "defines no schema")


@openapi_rule(
    "oas.structure.unique-tag-names", Severity.WARNING, category=_STRUCT,
    description="Global tag names must be unique",
    rationale="Duplicate tags split documentation groups unpredictably.",
)
def check_unique_tags(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    seen: set[str] = set()
    for index, tag in enumerate(document.get("tags") or []):
        name = tag.get("name") if isinstance(tag, dict) else None
        if not name:
            continue
        if name in seen:
            yield f"/tags/{index}", f"Duplicate tag name '{name}'"
        seen.add(name)


@openapi_rule(
    "oas.structure.no-unused-components", Severity.INFO, category=_STRUCT,
    description="Component schemas should be referenced somewhere",
    rationale="Orphan schemas are dead weight and often stale.",
)
def check_unused_components(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name in find_unused_schemas(document):
        yield (f"/components/schemas/{escape_pointer(name)}",
               f"Component schema '{name}' is defined but never referenced")


@openapi_rule(
    "oas.structure.path-item-has-operation", Severity.WARNING, category=_STRUCT,
    description="Path items should define at least one operation",
    rationale="An operation-less path is unreachable API surface.",
)
def check_path_has_operation(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, path_item in (document.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        if "$ref" in path_item:
            continue
        if not any(method in path_item for method in HTTP_METHODS):
            yield (f"/paths/{escape_pointer(path)}",
                   f"Path {path} defines no operations")


@openapi_rule(
    "oas.structure.discriminator-property-required", Severity.WARNING,
    category=_STRUCT, confidence=Confidence.DETERMINISTIC,
    description="Discriminator propertyName should be a required property",
    rationale="Polymorphic dispatch fails when the discriminator field is absent.",
)
def check_discriminator(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    schemas = (document.get("components") or {}).get("schemas") or {}
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        discriminator = schema.get("discriminator")
        if not isinstance(discriminator, dict):
            continue
        prop = discriminator.get("propertyName")
        if prop and prop not in (schema.get("required") or []):
            yield (f"/components/schemas/{escape_pointer(name)}/discriminator",
                   f"Discriminator property '{prop}' of schema '{name}' "
                   "is not listed in required")
