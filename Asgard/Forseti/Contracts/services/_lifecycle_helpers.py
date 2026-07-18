"""
Lifecycle Helpers - lifecycle-metadata extraction per format and
lifecycle-aware severity adjustment (plan 04, DEEPTHINK_07 / DEEPTHINK_04 §C).

Extraction maps element locations (matching the Compatibility engine's
UnifiedChange.location convention) to LifecycleMeta. Adjustment rewards
graceful removal: post-sunset removals cost nothing; pre-sunset removals
of deprecated elements cost half.
"""

import re
from datetime import date
from typing import Any, Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import TierVerdict
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Contracts.models.contract_models import LifecycleMeta

_HTTP_METHODS = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

SUNSET_KEY = "x-sunset-date"
SINCE_KEY = "x-deprecated-since"
REPLACED_BY_KEY = "x-replaced-by"
MIGRATION_GUIDE_KEY = "x-migration-guide"

# Change kinds that represent removal of the old element.
REMOVAL_KINDS = {
    "OAS-PATH-REMOVED", "OAS-METHOD-REMOVED", "OAS-PARAM-REMOVED",
    "OAS-REQBODY-REMOVED", "OAS-REQ-FIELD-REMOVED", "OAS-RES-FIELD-REMOVED",
    "OAS-RESPONSE-REMOVED", "OAS-SCHEMA-REMOVED",
    "GQL-TYPE-REMOVED", "GQL-FIELD-REMOVED", "GQL-ENUM-VALUE-REMOVED",
    "GQL-ARG-REMOVED", "GQL-INPUT-FIELD-REMOVED", "GQL-UNION-MEMBER-REMOVED",
    "PROTO-MESSAGE-REMOVED", "PROTO-FIELD-REMOVED-UNRESERVED",
    "PROTO-FIELD-REMOVED-RESERVED", "PROTO-ENUM-REMOVED",
    "PROTO-ENUM-VALUE-REMOVED", "PROTO-RPC-REMOVED", "PROTO-SERVICE-REMOVED",
    "AVRO-FIELD-REMOVED", "AVRO-ENUM-SYMBOL-REMOVED",
    "ASYNC-CHANNEL-REMOVED", "ASYNC-OPERATION-REMOVED",
    "ASYNC-MSG-FIELD-REMOVED",
}


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


def _meta_from_node(node: dict[str, Any], location: str) -> Optional[LifecycleMeta]:
    """Build LifecycleMeta from an OpenAPI-style node, if deprecated."""
    if not isinstance(node, dict) or not node.get("deprecated", False):
        return None
    return LifecycleMeta(
        location=location,
        deprecated=True,
        since=parse_iso_date(node.get(SINCE_KEY)),
        sunset=parse_iso_date(node.get(SUNSET_KEY)),
        replaced_by=node.get(REPLACED_BY_KEY),
        migration_guide=node.get(MIGRATION_GUIDE_KEY),
    )


def extract_openapi_lifecycle(spec: dict[str, Any]) -> dict[str, LifecycleMeta]:
    """
    Extract lifecycle metadata keyed by the Compatibility adapter's
    location convention: '<path>' / '<path>/<method>' /
    '#/components/schemas/<Name>' (+ '/properties/<prop>' for fields).
    """
    metas: dict[str, LifecycleMeta] = {}
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        op_metas = []
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                meta = _meta_from_node(operation, f"{path}/{method}")
                if meta:
                    metas[meta.location] = meta
                op_metas.append(meta)
        # A path counts as deprecated when every operation on it is.
        if op_metas and all(op_metas):
            first = op_metas[0]
            metas[path] = LifecycleMeta(
                location=path, deprecated=True,
                since=first.since, sunset=first.sunset,
                replaced_by=first.replaced_by,
                migration_guide=first.migration_guide,
            )
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            for param in operation.get("parameters") or []:
                if isinstance(param, dict) and param.get("deprecated"):
                    meta = _meta_from_node(
                        param, f"{path}/{method}/parameters/{param.get('name')}"
                    )
                    if meta:
                        metas[meta.location] = meta
    schemas = (spec.get("components") or {}).get("schemas") or {}
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        ref = f"#/components/schemas/{name}"
        meta = _meta_from_node(schema, ref)
        if meta:
            metas[ref] = meta
        for prop, prop_schema in (schema.get("properties") or {}).items():
            if isinstance(prop_schema, dict):
                prop_meta = _meta_from_node(prop_schema, f"{ref}/properties/{prop}")
                if prop_meta:
                    metas[prop_meta.location] = prop_meta
    return metas


_GQL_DEPRECATED = re.compile(
    r"^\s*(?P<name>\w+)\s*(?:\([^)]*\))?\s*:\s*[\[\]\w!]+\s*"
    r"@deprecated(?:\s*\(\s*reason\s*:\s*\"(?P<reason>[^\"]*)\"\s*\))?",
)
_GQL_TYPE = re.compile(r"^\s*(?:type|interface|input|enum)\s+(?P<type>\w+)")
_GQL_SUNSET = re.compile(r"sunset[=:\s]+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def extract_graphql_lifecycle(sdl: str) -> dict[str, LifecycleMeta]:
    """Extract @deprecated(reason:) fields keyed 'Type.field'."""
    metas: dict[str, LifecycleMeta] = {}
    current_type = ""
    for line in sdl.splitlines():
        type_match = _GQL_TYPE.match(line)
        if type_match:
            current_type = type_match.group("type")
            continue
        match = _GQL_DEPRECATED.match(line)
        if match and "@deprecated" in line:
            location = f"{current_type}.{match.group('name')}" if current_type \
                else match.group("name")
            reason = match.group("reason") or ""
            sunset_match = _GQL_SUNSET.search(reason)
            metas[location] = LifecycleMeta(
                location=location,
                deprecated=True,
                sunset=parse_iso_date(sunset_match.group(1)) if sunset_match else None,
            )
    return metas


_PROTO_FIELD = re.compile(
    r"^\s*(?:optional\s+|repeated\s+|required\s+)?\w[\w.<>, ]*\s+(?P<name>\w+)\s*=\s*\d+"
    r"\s*\[(?P<options>[^\]]*deprecated\s*=\s*true[^\]]*)\]",
)
_PROTO_MESSAGE = re.compile(r"^\s*message\s+(?P<name>\w+)")


def extract_protobuf_lifecycle(proto_text: str) -> dict[str, LifecycleMeta]:
    """Extract `[deprecated = true]` fields keyed 'Message.field'."""
    metas: dict[str, LifecycleMeta] = {}
    current_message = ""
    for line in proto_text.splitlines():
        message_match = _PROTO_MESSAGE.match(line)
        if message_match:
            current_message = message_match.group("name")
            continue
        match = _PROTO_FIELD.match(line)
        if match:
            location = f"{current_message}.{match.group('name')}" \
                if current_message else match.group("name")
            metas[location] = LifecycleMeta(location=location, deprecated=True)
    return metas


_AVRO_DOC_TAG = re.compile(
    r"@deprecated(?:\s*\(\s*(?P<args>[^)]*)\))?", re.IGNORECASE
)
_AVRO_KV = re.compile(r"(\w+)\s*=\s*([\w-]+)")


def extract_avro_lifecycle(schema: Any, prefix: str = "") -> dict[str, LifecycleMeta]:
    """Extract '@deprecated(since=..., sunset=...)' doc tags from Avro schemas."""
    metas: dict[str, LifecycleMeta] = {}

    def visit(node: Any, location: str) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item, location)
            return
        if not isinstance(node, dict):
            return
        name = node.get("name")
        here = f"{location}.{name}" if location and name else (name or location)
        doc = node.get("doc")
        if isinstance(doc, str):
            match = _AVRO_DOC_TAG.search(doc)
            if match:
                kwargs = dict(_AVRO_KV.findall(match.group("args") or ""))
                metas[here or ""] = LifecycleMeta(
                    location=here or "",
                    deprecated=True,
                    since=parse_iso_date(kwargs.get("since")),
                    sunset=parse_iso_date(kwargs.get("sunset")),
                )
        for field in node.get("fields") or []:
            visit(field, here or "")
        field_type = node.get("type")
        if isinstance(field_type, (dict, list)):
            visit(field_type, here or "")

    visit(schema, prefix)
    return metas


def find_lifecycle_meta(
    location: str,
    metas: dict[str, LifecycleMeta],
) -> Optional[LifecycleMeta]:
    """Longest-prefix lifecycle lookup so nested changes inherit parents."""
    best: Optional[str] = None
    for key in metas:
        if location == key or location.startswith(key.rstrip("/") + "/") \
                or location.startswith(key + "."):
            if best is None or len(key) > len(best):
                best = key
    return metas.get(best) if best else None


def lifecycle_adjust(
    change: UnifiedChange,
    meta: Optional[LifecycleMeta],
    today: Optional[date] = None,
) -> UnifiedChange:
    """
    Lifecycle-aware severity adjustment (DEEPTHINK_04 §C).

    Post-sunset removal of a deprecated element: zero deduction, semantic
    PASS — graceful lifecycle management is rewarded. Pre-sunset removal
    of a deprecated element: deduction halved, mitigation points at the
    sunset date or a waiver.
    """
    today = today or date.today()
    if meta is None or not meta.deprecated:
        return change
    if change.rule_id not in REMOVAL_KINDS:
        return change
    if meta.sunset_elapsed(today):
        change.base_severity = 0
        change.impact.structural = TierVerdict.PASS
        change.impact.semantic = TierVerdict.PASS
        suffix = f" (deprecated{f' since {meta.since}' if meta.since else ''}, " \
                 f"sunset {meta.sunset} elapsed — graceful removal)"
        change.message += suffix
        change.mitigation = None
    else:
        change.base_severity = max(1, change.base_severity // 2)
        if meta.sunset:
            change.mitigation = (
                f"Wait for the declared sunset ({meta.sunset.isoformat()}) "
                "or record a waiver"
            )
        else:
            change.mitigation = (
                "Element was deprecated but has no x-sunset-date; declare one "
                "and wait for it, or record a waiver"
            )
        change.message += " (element was deprecated)"
    return change


def apply_lifecycle(
    changes: list[UnifiedChange],
    metas: dict[str, LifecycleMeta],
    today: Optional[date] = None,
) -> list[UnifiedChange]:
    """Apply lifecycle adjustment to every change in place; returns the list."""
    for change in changes:
        lifecycle_adjust(change, find_lifecycle_meta(change.location, metas), today)
    return changes
