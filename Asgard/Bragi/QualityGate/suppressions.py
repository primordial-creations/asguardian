"""
Structured Suppressions — reason-mandatory, machine-readable inline ignores.

Schema (Heimdall-09 §3):

    # heimdall-ignore: SQLI - FP: input cast to int before query
    # heimdall-ignore: SQLI - RISK ACCEPTED until 2026-12-01 - TICKET-123
    # heimdall-ignore: SQLI                                     <- INVALID

Rules:
    - A suppression must name a rule id AND carry a justification:
      either "FP: <reason>" or "RISK ACCEPTED until <YYYY-MM-DD> - <ticket>".
    - A bare ignore (no justification) is invalid and fails the gate.
    - Expired RISK ACCEPTED suppressions fail the gate.
    - FP suppressions never expire (time-limited FPs randomly break
      unrelated PRs — operationally disastrous).

Both `# heimdall-ignore:` and `# asgard-ignore:` markers are honoured, with
`#`, `//`, `--`, and `;` comment leaders, so the mechanism works across
languages with zero configuration.
"""

import re
from datetime import date, datetime
from enum import Enum
from typing import Iterable, List, Optional, Set

from pydantic import BaseModel, Field


class SuppressionKind(str, Enum):
    """The two admissible suppression justifications."""
    FALSE_POSITIVE = "fp"
    RISK_ACCEPTED = "risk_accepted"


_DIRECTIVE_RE = re.compile(
    r"(?:#|//|--|;)\s*(?:heimdall|asgard)-ignore:\s*(?P<rule>[A-Za-z0-9_.\-]+)"
    r"\s*(?:-\s*(?P<justification>.*))?$"
)
_FP_RE = re.compile(r"^FP:\s*(?P<reason>\S.*)$")
_RISK_RE = re.compile(
    r"^RISK\s+ACCEPTED\s+until\s+(?P<date>\d{4}-\d{2}-\d{2})"
    r"\s*-\s*(?P<ticket>\S.*)$",
    re.IGNORECASE,
)


class SuppressionDirective(BaseModel):
    """One parsed suppression comment."""
    file_path: str = Field("", description="File containing the directive")
    line: int = Field(0, description="1-based line number of the directive")
    rule_id: str = Field("", description="Rule the directive suppresses")
    kind: Optional[SuppressionKind] = Field(None, description="Justification kind")
    reason: str = Field("", description="FP reason or risk-acceptance ticket text")
    ticket: str = Field("", description="Ticket reference for RISK ACCEPTED")
    expires: Optional[date] = Field(None, description="Expiry for RISK ACCEPTED")
    raw: str = Field("", description="Raw directive text")
    valid: bool = Field(False, description="Whether the directive satisfies the schema")
    error: str = Field("", description="Why the directive is invalid, if it is")

    class Config:
        use_enum_values = True

    def is_expired(self, today: Optional[date] = None) -> bool:
        """RISK ACCEPTED directives expire; FP directives never do."""
        if self.expires is None:
            return False
        return (today or date.today()) > self.expires

    def is_active(self, today: Optional[date] = None) -> bool:
        """Valid and not expired."""
        return self.valid and not self.is_expired(today)


def parse_suppression_comment(
    text: str,
    file_path: str = "",
    line: int = 0,
) -> Optional[SuppressionDirective]:
    """
    Parse a single line for a suppression directive.

    Returns None when the line contains no directive; otherwise a
    SuppressionDirective with `valid`/`error` populated per the schema.
    """
    match = _DIRECTIVE_RE.search(text)
    if not match:
        return None

    rule_id = match.group("rule")
    justification = (match.group("justification") or "").strip()
    directive = SuppressionDirective(
        file_path=file_path,
        line=line,
        rule_id=rule_id,
        raw=text.strip(),
    )

    if not justification:
        directive.error = (
            f"Suppression of '{rule_id}' has no justification. "
            "Use 'FP: <reason>' or 'RISK ACCEPTED until <YYYY-MM-DD> - <ticket>'."
        )
        return directive

    fp_match = _FP_RE.match(justification)
    if fp_match:
        directive.kind = SuppressionKind.FALSE_POSITIVE
        directive.reason = fp_match.group("reason").strip()
        directive.valid = True
        return directive

    risk_match = _RISK_RE.match(justification)
    if risk_match:
        directive.kind = SuppressionKind.RISK_ACCEPTED
        directive.ticket = risk_match.group("ticket").strip()
        directive.reason = justification
        try:
            directive.expires = datetime.strptime(
                risk_match.group("date"), "%Y-%m-%d"
            ).date()
        except ValueError:
            directive.error = (
                f"Suppression of '{rule_id}' has an invalid expiry date "
                f"'{risk_match.group('date')}'."
            )
            return directive
        directive.valid = True
        return directive

    directive.error = (
        f"Suppression of '{rule_id}' has a malformed justification "
        f"'{justification}'. Use 'FP: <reason>' or "
        "'RISK ACCEPTED until <YYYY-MM-DD> - <ticket>'."
    )
    return directive


def parse_suppressions(source: str, file_path: str = "") -> List[SuppressionDirective]:
    """Scan source text for suppression directives (one per line)."""
    directives: List[SuppressionDirective] = []
    for idx, line_text in enumerate(source.splitlines(), start=1):
        directive = parse_suppression_comment(line_text, file_path=file_path, line=idx)
        if directive is not None:
            directives.append(directive)
    return directives


def lint_suppressions(
    directives: List[SuppressionDirective],
    today: Optional[date] = None,
) -> List[str]:
    """
    Enforce the suppression schema.

    Returns violations: schema-invalid directives and expired RISK ACCEPTED
    directives. Any violation fails the build.
    """
    violations: List[str] = []
    for d in directives:
        location = f"{d.file_path}:{d.line}" if d.file_path else f"line {d.line}"
        if not d.valid:
            violations.append(f"{location}: {d.error}")
        elif d.is_expired(today):
            violations.append(
                f"{location}: Suppression of '{d.rule_id}' expired on "
                f"{d.expires.isoformat()} ({d.ticket}). Fix the finding or "
                "re-review the risk acceptance."
            )
    return violations


def find_unused_suppressions(
    directives: Iterable[SuppressionDirective],
    active_rule_ids: Set[str],
    today: Optional[date] = None,
) -> List[SuppressionDirective]:
    """
    Unused-suppression detection (Bragi Plan 04 Sec.3.4 / DEEPTHINK_11's
    state-based alternative to time-bomb expiry): a directive is stale when
    its rule no longer fires anywhere the directive would apply, i.e. its
    ``rule_id`` is absent from ``active_rule_ids`` (the set of rule ids
    that fired somewhere in the current scan).

    Only active (valid, non-expired) directives are considered - an
    already-invalid or already-expired directive is reported by
    `lint_suppressions` instead, not duplicated here.
    """
    return [
        d for d in directives
        if d.is_active(today) and d.rule_id not in active_rule_ids
    ]
