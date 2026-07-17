"""
OpenAPI Style Rules - naming and URL-shape conventions (plan 03 Phase 1).
Conventions are organisational preferences: WARNINGs and HINTs only.
"""

import re
from typing import Any, Iterator

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    escape_pointer,
    iter_component_schemas,
    iter_operations,
    openapi_rule,
)
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    Severity,
)

_STYLE = RuleCategory.STYLE
_H = Confidence.HEURISTIC

_KEBAB_SEGMENT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_CAMEL = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_PATH_VERBS = {"get", "create", "update", "delete", "remove", "fetch",
               "set", "post", "put", "list", "add", "edit"}


@openapi_rule(
    "oas.style.no-trailing-slash", Severity.WARNING, category=_STYLE,
    description="Paths must not end with a trailing slash",
    rationale="'/users' and '/users/' are distinct routes in most routers; "
              "the trailing-slash variant causes duplicate or 404 traffic.",
)
def check_trailing_slash(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path in (document.get("paths") or {}):
        text = str(path)
        if len(text) > 1 and text.endswith("/"):
            yield f"/paths/{escape_pointer(text)}", f"Path has a trailing slash: {text}"


@openapi_rule(
    "oas.style.path-kebab-case", Severity.HINT, category=_STYLE, confidence=_H,
    description="Path segments should use kebab-case",
    rationale="Consistent lowercase-hyphenated paths are the dominant REST "
              "convention; mixed casing invites client typos.",
)
def check_path_kebab_case(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path in (document.get("paths") or {}):
        for segment in str(path).split("/"):
            if not segment or segment.startswith("{"):
                continue
            if not _KEBAB_SEGMENT.match(segment):
                yield (f"/paths/{escape_pointer(str(path))}",
                       f"Path segment '{segment}' in {path} is not kebab-case")
                break


@openapi_rule(
    "oas.style.no-path-verbs", Severity.HINT, category=_STYLE, confidence=_H,
    description="Path segments should be nouns; HTTP methods carry the verb",
    rationale="'/getUsers' duplicates the HTTP method in the URL and breaks "
              "resource-oriented routing.",
)
def check_path_verbs(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path in (document.get("paths") or {}):
        for segment in str(path).split("/"):
            if not segment or segment.startswith("{"):
                continue
            first_word = re.split(r"[-_]", segment)[0]
            camel = re.match(r"^[a-z]+", segment)
            head = (camel.group(0) if camel else first_word).lower()
            if head in _PATH_VERBS and head == segment.lower()[:len(head)] \
                    and len(segment) > len(head):
                yield (f"/paths/{escape_pointer(str(path))}",
                       f"Path segment '{segment}' in {path} starts with a verb")
                break


@openapi_rule(
    "oas.style.property-camel-case", Severity.HINT, category=_STYLE, confidence=_H,
    description="Schema property names should use a consistent camelCase style",
    rationale="Mixed property-naming styles inside one API confuse SDK users; "
              "pick one convention.",
)
def check_property_camel_case(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    styles: dict[str, int] = {"camel": 0, "snake": 0, "other": 0}
    offenders: list[tuple[str, str, str]] = []
    for name, schema, json_path in iter_component_schemas(document):
        for prop in (schema.get("properties") or {}):
            text = str(prop)
            if _CAMEL.match(text) and "_" not in text:
                styles["camel"] += 1
            elif re.match(r"^[a-z0-9]+(_[a-z0-9]+)+$", text):
                styles["snake"] += 1
                offenders.append((name, text, f"{json_path}/properties/{escape_pointer(text)}"))
            else:
                styles["other"] += 1
                offenders.append((name, text, f"{json_path}/properties/{escape_pointer(text)}"))
    total = sum(styles.values())
    # Only nag when the document is predominantly camelCase but has strays.
    if total and styles["camel"] / total >= 0.7:
        for schema_name, prop, json_path in offenders:
            yield (json_path,
                   f"Property '{prop}' of schema '{schema_name}' breaks the "
                   "document's dominant camelCase convention")


@openapi_rule(
    "oas.style.operation-id-camel-case", Severity.HINT, category=_STYLE,
    confidence=_H,
    description="operationId should be camelCase",
    rationale="Code generators map operationIds to method names; camelCase "
              "survives every target language.",
)
def check_operation_id_style(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        op_id = operation.get("operationId")
        if isinstance(op_id, str) and op_id and not _CAMEL.match(op_id):
            yield (f"{json_path}/operationId",
                   f"operationId '{op_id}' is not camelCase")


@openapi_rule(
    "oas.style.versioned-base-path", Severity.HINT, category=_STYLE, confidence=_H,
    description="The API should expose a version in server URL or base path",
    rationale="Without URL versioning, breaking changes have no side-by-side "
              "escape hatch.",
)
def check_versioned_base_path(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    version_re = re.compile(r"/v\d+")
    servers = document.get("servers") or []
    for server in servers:
        if isinstance(server, dict) and version_re.search(str(server.get("url", ""))):
            return
    if document.get("basePath") and version_re.search(str(document["basePath"])):
        return
    for path in (document.get("paths") or {}):
        if version_re.search(str(path)):
            return
    if document.get("paths"):
        yield "/servers" if servers else "/", \
            "No version segment (e.g. /v1) found in server URLs or paths"


@openapi_rule(
    "oas.style.server-no-trailing-slash", Severity.WARNING, category=_STYLE,
    description="Server URLs should not end with a trailing slash",
    rationale="Server URL + path concatenation yields '//' with a trailing "
              "slash present.",
)
def check_server_trailing_slash(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for index, server in enumerate(document.get("servers") or []):
        if not isinstance(server, dict):
            continue
        url = str(server.get("url", ""))
        if len(url) > 1 and url.endswith("/"):
            yield f"/servers/{index}/url", f"Server URL has a trailing slash: {url}"


@openapi_rule(
    "oas.style.schema-name-pascal-case", Severity.HINT, category=_STYLE,
    confidence=_H,
    description="Component schema names should be PascalCase",
    rationale="PascalCase schema names map cleanly onto generated classes.",
)
def check_schema_name_style(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, _schema, json_path in iter_component_schemas(document):
        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", str(name)):
            yield json_path, f"Schema name '{name}' is not PascalCase"
