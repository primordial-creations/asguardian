"""
OpenAPI Lifecycle Rules - sunset/deprecation metadata linting (plan 04,
DEEPTHINK_07 / RFC 8594).

Deprecation is rewarded, not punished: these rules nudge producers to
attach machine-readable lifecycle metadata (x-sunset-date, x-replaced-by)
so consumers can plan migration. None of them is ever an ERROR.
"""

from datetime import date
from typing import Any, Iterator, Optional

from Asgard.Forseti.OpenAPI.rules._rule_helpers import iter_operations, openapi_rule
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, Severity

_LIFE = RuleCategory.LIFECYCLE

SUNSET_KEY = "x-sunset-date"
REPLACED_BY_KEY = "x-replaced-by"
MIGRATION_GUIDE_KEY = "x-migration-guide"


def parse_iso_date(value: Any) -> Optional[date]:
    """Parse an ISO date (or datetime prefix); None when unparseable."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _iter_deprecated_nodes(
    document: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], str, str]]:
    """Yield (node, json_path, label) for deprecated operations and schemas."""
    for path, method, operation, json_path in iter_operations(document):
        if operation.get("deprecated", False):
            yield operation, json_path, f"Operation {method.upper()} {path}"
    schemas = (document.get("components") or {}).get("schemas") or {}
    for name, schema in schemas.items():
        if isinstance(schema, dict) and schema.get("deprecated", False):
            yield schema, f"/components/schemas/{name}", f"Schema '{name}'"


@openapi_rule(
    "oas.lifecycle.deprecated-needs-sunset", Severity.WARNING, category=_LIFE,
    description="Deprecated elements should declare x-sunset-date",
    rationale="A deprecation without a sunset date (RFC 8594) gives "
              "consumers no deadline to plan against.",
)
def check_deprecated_needs_sunset(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for node, json_path, label in _iter_deprecated_nodes(document):
        if parse_iso_date(node.get(SUNSET_KEY)) is None:
            yield (json_path,
                   f"{label} is deprecated but declares no valid "
                   f"{SUNSET_KEY} (ISO date)")


@openapi_rule(
    "oas.lifecycle.sunset-passed", Severity.WARNING, category=_LIFE,
    description="Elements past their sunset date should be removed",
    rationale="Keeping sunsetted elements alive erodes trust in every future "
              "sunset date. Removal is the producer's call — this only nudges.",
)
def check_sunset_passed(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    today = date.today()
    for node, json_path, label in _iter_deprecated_nodes(document):
        sunset = parse_iso_date(node.get(SUNSET_KEY))
        if sunset is not None and sunset < today:
            yield (json_path,
                   f"{label} passed its sunset date ({sunset.isoformat()}) "
                   "but is still present")


@openapi_rule(
    "oas.lifecycle.replacement-missing", Severity.INFO, category=_LIFE,
    description="Deprecated elements should point at their replacement",
    rationale="x-replaced-by turns a dead end into a migration path.",
)
def check_replacement_missing(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for node, json_path, label in _iter_deprecated_nodes(document):
        if not node.get(REPLACED_BY_KEY):
            yield (json_path,
                   f"{label} is deprecated but declares no {REPLACED_BY_KEY}")
