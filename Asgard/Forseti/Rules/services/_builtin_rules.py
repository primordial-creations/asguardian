"""
Builtin Rules - registry entries for Forseti's shipped rule set.

Executable OpenAPI rules wrap the pre-existing validator helper
functions one-by-one (plan 02). Other formats' legacy validator checks
get metadata-only registrations so their findings carry stable
namespaced rule ids, fixed severities and rationales in the unified
reporting pipeline; their execution still lives in the format services.
"""

from typing import Any, Iterable

from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.models.rule_models import RuleMeta
from Asgard.Forseti.Rules.services.rule_registry_service import default_registry, register_rule

_HTTP_METHODS = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]


def _legacy_openapi_findings(
    document: dict[str, Any],
    legacy_rules: set[str],
    rule_id: str,
    severity: Severity,
    category: RuleCategory,
) -> Iterable[Finding]:
    """Run the legacy OpenAPI helpers and adapt matching errors to Findings."""
    from Asgard.Forseti.OpenAPI.services import _spec_validator_helpers as helpers
    from Asgard.Forseti.OpenAPI.utilities.openapi_utils import detect_openapi_version

    legacy_errors = []
    legacy_errors.extend(helpers.validate_structure(document, detect_openapi_version(document)))
    legacy_errors.extend(helpers.validate_paths(document))
    legacy_errors.extend(helpers.validate_schemas(document))
    for error in legacy_errors:
        if error.rule in legacy_rules:
            yield Finding(
                rule_id=rule_id,
                severity=severity,
                message=error.message,
                coordinates=Coordinates(json_path=error.path),
                category=category,
                format=SchemaFormat.OPENAPI,
            )


def _register_openapi_wrapped(
    rule_id: str,
    legacy_rules: set[str],
    severity: Severity,
    *,
    category: RuleCategory = RuleCategory.STRUCTURE,
    confidence: Confidence = Confidence.DETERMINISTIC,
    core: bool = False,
    description: str = "",
    rationale: str = "",
) -> None:
    meta = RuleMeta(
        rule_id=rule_id,
        formats={SchemaFormat.OPENAPI},
        cost=Cost.ON,
        confidence=confidence,
        severity=severity,
        category=category,
        core=core,
        description=description,
        rationale=rationale,
        legacy_ids=legacy_rules,
    )

    def check(document: dict[str, Any]) -> Iterable[Finding]:
        return _legacy_openapi_findings(document, legacy_rules, rule_id, severity, category)

    default_registry.register(meta, check)


_register_openapi_wrapped(
    "oas.structure.required-field",
    {"required-field", "non-empty-responses"},
    Severity.ERROR,
    core=True,
    description="Required OpenAPI fields must be present",
    rationale="Missing required fields make the document structurally invalid "
              "and unusable by downstream tooling.",
)
_register_openapi_wrapped(
    "oas.paths.valid-path-item",
    {"valid-path-item"},
    Severity.ERROR,
    core=True,
    description="Path items must be objects",
    rationale="A non-object path item cannot be interpreted by any OpenAPI consumer.",
)
_register_openapi_wrapped(
    "oas.paths.path-format",
    {"path-format"},
    Severity.ERROR,
    description="Paths must start with '/'",
    rationale="The OpenAPI specification requires path templates to begin with a slash.",
)
_register_openapi_wrapped(
    "oas.paths.path-parameter-defined",
    {"path-parameter-defined"},
    Severity.ERROR,
    category=RuleCategory.SEMANTICS,
    description="Every templated path parameter must be defined",
    rationale="Undefined path parameters break client generation and request routing.",
)
_register_openapi_wrapped(
    "oas.schema.valid-schema",
    {"valid-schema"},
    Severity.ERROR,
    core=True,
    description="Component schemas must be objects",
)
_register_openapi_wrapped(
    "oas.schema.no-direct-self-reference",
    {"no-direct-self-reference"},
    Severity.WARNING,
    category=RuleCategory.SEMANTICS,
    confidence=Confidence.HEURISTIC,
    description="Schemas should not directly reference themselves",
    rationale="Direct self-references usually indicate a modelling mistake; "
              "intentional recursion should route through an intermediate schema.",
)


@register_rule(RuleMeta(
    rule_id="oas.lifecycle.deprecated-operation",
    formats={SchemaFormat.OPENAPI},
    cost=Cost.ON,
    confidence=Confidence.DETERMINISTIC,
    severity=Severity.INFO,
    category=RuleCategory.LIFECYCLE,
    description="Operation is marked deprecated",
    rationale="Deprecation is graceful lifecycle management, not a defect: "
              "consumers should plan migration, but the build must not break.",
    legacy_ids={"no-deprecated"},
))
def _check_deprecated_operation(document: dict[str, Any]) -> Iterable[Finding]:
    """Informational notice for deprecated operations (never an ERROR)."""
    for path, path_item in (document.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict) and operation.get("deprecated", False):
                yield Finding(
                    rule_id="oas.lifecycle.deprecated-operation",
                    severity=Severity.INFO,
                    message=f"Operation {method.upper()} {path} is deprecated",
                    coordinates=Coordinates(json_path=f"/paths{path}/{method}"),
                    category=RuleCategory.LIFECYCLE,
                    format=SchemaFormat.OPENAPI,
                )


def _register_meta_only(
    fmt: SchemaFormat,
    prefix: str,
    entries: list[tuple[str, Severity, RuleCategory, Confidence, bool]],
) -> None:
    for legacy, severity, category, confidence, core in entries:
        default_registry.register(RuleMeta(
            rule_id=f"{prefix}.{category.value}.{legacy}",
            formats={fmt},
            severity=severity,
            category=category,
            confidence=confidence,
            core=core,
            legacy_ids={legacy},
        ))


_D = Confidence.DETERMINISTIC
_H = Confidence.HEURISTIC

_register_meta_only(SchemaFormat.GRAPHQL, "gql", [
    ("file-exists", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("valid-file", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("valid-syntax", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("balanced-braces", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("closed-strings", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("query-type-required", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("defined-type", Severity.ERROR, RuleCategory.SEMANTICS, _D, False),
    ("unique-type-names", Severity.ERROR, RuleCategory.SEMANTICS, _D, False),
    ("interface-exists", Severity.ERROR, RuleCategory.SEMANTICS, _D, False),
    ("known-directive", Severity.WARNING, RuleCategory.SEMANTICS, _D, False),
    ("deprecated-field", Severity.INFO, RuleCategory.LIFECYCLE, _D, False),
])

_register_meta_only(SchemaFormat.ASYNCAPI, "asyncapi", [
    ("file-exists", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("valid-syntax", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("required-field", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("version-format", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("valid-channel", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("valid-operation", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("valid-server", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("valid-schema", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("valid-url", Severity.WARNING, RuleCategory.SEMANTICS, _D, False),
    ("channel-has-operation", Severity.WARNING, RuleCategory.SEMANTICS, _D, False),
    ("operation-has-message", Severity.WARNING, RuleCategory.SEMANTICS, _D, False),
    ("payload-has-type", Severity.WARNING, RuleCategory.SEMANTICS, _D, False),
    ("parameter-defined", Severity.ERROR, RuleCategory.SEMANTICS, _D, False),
    ("operation-id-recommended", Severity.HINT, RuleCategory.DOCS, _H, False),
    ("no-deprecated", Severity.INFO, RuleCategory.LIFECYCLE, _D, False),
    ("no-direct-self-reference", Severity.WARNING, RuleCategory.SEMANTICS, _H, False),
])

_register_meta_only(SchemaFormat.AVRO, "avro", [
    ("file-exists", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("readable-file", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("valid-json", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("parseable-schema", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("doc-recommended", Severity.INFO, RuleCategory.DOCS, _H, False),
    ("default-recommended", Severity.INFO, RuleCategory.SEMANTICS, _H, False),
    ("naming-convention", Severity.WARNING, RuleCategory.STYLE, _H, False),
])

# Expanded OpenAPI lint/security/lifecycle rules (plans 03/04) register
# themselves into the same default registry on import.
from Asgard.Forseti.OpenAPI import rules as _openapi_rules  # noqa: E402,F401

_register_meta_only(SchemaFormat.PROTOBUF, "proto", [
    ("file-exists", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("readable-file", Severity.ERROR, RuleCategory.STRUCTURE, _D, True),
    ("syntax-declaration", Severity.WARNING, RuleCategory.STRUCTURE, _D, False),
    ("package-required", Severity.WARNING, RuleCategory.STRUCTURE, _D, False),
    ("unique-field-numbers", Severity.ERROR, RuleCategory.STRUCTURE, _D, False),
    ("reserved-number", Severity.ERROR, RuleCategory.COMPATIBILITY, _D, False),
    ("reserved-name", Severity.ERROR, RuleCategory.COMPATIBILITY, _D, False),
    ("naming-convention", Severity.WARNING, RuleCategory.STYLE, _H, False),
    ("efficient-field-number", Severity.HINT, RuleCategory.STYLE, _H, False),
])

# Plan 06 (LiveContract drift/negative probing) and plan 07 (cross-format
# Alignment) emit findings from bespoke check functions (they operate on
# probe results / multi-source IR comparisons, not a single parsed
# document), so their rule ids are registered here as metadata-only
# entries: stable id, fixed severity and rationale for the reporting
# pipeline, with execution living in LiveContract/Alignment services.
for _rule_id, _severity, _category, _confidence, _rationale in [
    (
        "drift.undocumented-status",
        Severity.ERROR,
        RuleCategory.COMPATIBILITY,
        _D,
        "A live response used a status code the spec never declared - the spec no longer "
        "describes the implementation's real contract.",
    ),
    (
        "drift.schema-mismatch",
        Severity.ERROR,
        RuleCategory.COMPATIBILITY,
        _D,
        "A live response body failed the documented schema for its status code - consumers "
        "generated from the spec will misparse real responses.",
    ),
    (
        "negative.expected-4xx",
        Severity.ERROR,
        RuleCategory.SECURITY,
        _D,
        "A mutated/invalid request was accepted as success; the implementation is not "
        "validating input the spec declares required.",
    ),
    (
        "negative.server-error",
        Severity.ERROR,
        RuleCategory.SECURITY,
        _D,
        "A mutated/invalid request crashed the implementation (5xx) instead of being "
        "rejected with a handled 4xx.",
    ),
    (
        "align.type-contradiction",
        Severity.ERROR,
        RuleCategory.SEMANTICS,
        _D,
        "The same logical field has incompatible types across formats (e.g. string vs bool) - "
        "no reasonable mapping exists.",
    ),
    (
        "align.nullability-breach",
        Severity.ERROR,
        RuleCategory.SEMANTICS,
        _D,
        "A producer-side field is nullable/optional but the declared consumer requires a "
        "non-null value - a real null will break the consumer.",
    ),
    (
        "align.enum-divergence",
        Severity.ERROR,
        RuleCategory.SEMANTICS,
        _D,
        "Producer enum symbols are not a subset of the consumer's - the consumer cannot "
        "represent every value the producer can emit.",
    ),
    (
        "align.precision-risk",
        Severity.WARNING,
        RuleCategory.SEMANTICS,
        _D,
        "A numeric type is narrowed across formats (e.g. int64 -> int32) and may lose "
        "precision or overflow.",
    ),
    (
        "align.idiomatic-coercion",
        Severity.INFO,
        RuleCategory.SEMANTICS,
        _D,
        "A safe, idiomatic cross-format type mapping (e.g. int64 <-> String for GraphQL ids).",
    ),
    (
        "align.subset-divergence",
        Severity.INFO,
        RuleCategory.SEMANTICS,
        _D,
        "A field exists in some sources but not others - may be intentional projection; "
        "add to `ignore_fields` to suppress if so.",
    ),
    (
        "align.lexical-divergence",
        Severity.INFO,
        RuleCategory.STYLE,
        _D,
        "The same logical field uses a different casing/naming convention across formats.",
    ),
]:
    default_registry.register(RuleMeta(
        rule_id=_rule_id,
        formats={SchemaFormat.CONTRACT},
        severity=_severity,
        category=_category,
        confidence=_confidence,
        core=False,
        rationale=_rationale,
    ))
