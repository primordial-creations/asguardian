"""
Suppression Helpers - inline `x-forseti-ignore` parsing (with mandatory reasons).

Two suppression syntaxes:
- Structured documents (OpenAPI/AsyncAPI/JSON Schema/Avro):
    x-forseti-ignore:
      - rule: oas.docs.description-required
        reason: legacy downstream crashes on format
- Text documents (proto/GraphQL/SQL):
    // forseti:ignore <rule-id> <reason...>

A suppression without a reason is itself a WARNING; suppressed findings
remain in the output with `suppressed: true` so suppression-velocity
telemetry is possible (DEEPTHINK_09).
"""

import fnmatch
import re
from typing import Any, Optional

from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity
from Asgard.Forseti.Rules.models.rule_models import SuppressionEntry

IGNORE_KEY = "x-forseti-ignore"
MISSING_REASON_RULE = "forseti.suppression.missing-reason"

_COMMENT_RE = re.compile(
    r"(?://|#|--)\s*forseti:ignore\s+(?P<rule>\S+)(?:\s+(?P<reason>.*))?$"
)


def collect_suppressions(document: Any, _path: str = "") -> list[SuppressionEntry]:
    """Walk a parsed document collecting x-forseti-ignore entries."""
    suppressions: list[SuppressionEntry] = []
    if isinstance(document, dict):
        raw = document.get(IGNORE_KEY)
        if raw is not None:
            for item in raw if isinstance(raw, list) else [raw]:
                if isinstance(item, str):
                    suppressions.append(SuppressionEntry(rule=item, scope=_path or "/"))
                elif isinstance(item, dict) and item.get("rule"):
                    suppressions.append(SuppressionEntry(
                        rule=str(item["rule"]),
                        reason=item.get("reason"),
                        scope=_path or "/",
                    ))
        for key, value in document.items():
            if key == IGNORE_KEY:
                continue
            token = str(key).replace("~", "~0").replace("/", "~1")
            suppressions.extend(collect_suppressions(value, f"{_path}/{token}"))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            suppressions.extend(collect_suppressions(value, f"{_path}/{index}"))
    return suppressions


def parse_comment_suppressions(text: str) -> list[SuppressionEntry]:
    """Parse `// forseti:ignore <rule> <reason>` comment suppressions."""
    suppressions: list[SuppressionEntry] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _COMMENT_RE.search(line)
        if match:
            reason = (match.group("reason") or "").strip() or None
            suppressions.append(SuppressionEntry(
                rule=match.group("rule"),
                reason=reason,
                scope=f"line:{line_no}",
            ))
    return suppressions


def _normalize_pointer(path: str) -> str:
    """Unescape a JSON pointer and collapse duplicate slashes.

    Legacy findings embed raw keys ('/paths/users/{id}/get') while
    suppression scopes are escaped ('/paths/~1users~1{id}/get'); both
    normalize to the same comparable form.
    """
    unescaped = path.replace("~1", "/").replace("~0", "~")
    return re.sub(r"/+", "/", unescaped)


def _scope_matches(finding: Finding, scope: str) -> bool:
    if scope.startswith("line:"):
        try:
            return finding.coordinates.line == int(scope.split(":", 1)[1])
        except ValueError:
            return False
    if scope in ("", "/"):
        return True
    return _normalize_pointer(finding.coordinates.json_path).startswith(
        _normalize_pointer(scope)
    )


def apply_suppressions(
    findings: list[Finding],
    suppressions: list[SuppressionEntry],
    fmt: SchemaFormat = SchemaFormat.OPENAPI,
    core_rule_ids: Optional[set[str]] = None,
    file: Optional[str] = None,
) -> list[Finding]:
    """
    Mark suppressed findings and append missing-reason warnings.

    Core rules cannot be suppressed. Returns the (mutated) finding list
    with any missing-reason warnings appended.
    """
    core_rule_ids = core_rule_ids or set()
    for suppression in suppressions:
        if not suppression.has_reason:
            findings.append(Finding(
                rule_id=MISSING_REASON_RULE,
                severity=Severity.WARNING,
                message=(
                    f"Suppression of '{suppression.rule}' has no reason; "
                    "a reason string is mandatory"
                ),
                coordinates=Coordinates(file=file, json_path=suppression.scope or "/"),
                category=RuleCategory.STYLE,
                format=fmt,
            ))
        for finding in findings:
            if finding.suppressed or finding.rule_id == MISSING_REASON_RULE:
                continue
            if finding.rule_id in core_rule_ids:
                continue
            if not fnmatch.fnmatch(finding.rule_id, suppression.rule):
                continue
            if _scope_matches(finding, suppression.scope):
                finding.suppressed = True
                finding.suppression_reason = suppression.reason
    return findings
