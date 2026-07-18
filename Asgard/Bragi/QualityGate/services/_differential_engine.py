"""
Differential Gate Engine — fingerprint-based "clean as you code" evaluation.

Implements the Heimdall-09 / Bragi-06 blocking policy:

    - A finding is NEW iff its fingerprint is absent from the reference-branch
      baseline (line-shift immune; count ratchets are abandoned as gameable).
    - Block iff a NEW finding is HIGH or CRITICAL, its confidence is at least
      0.50 (Certain/Probable), and its rule is deterministic. Everything else
      is advisory (non-blocking comments / async burndown).
    - Pre-existing baseline findings never block.
    - Valid, unexpired suppressions silence matching findings; invalid or
      expired suppression directives themselves fail the gate.
    - Break-glass (`emergency-sec-bypass`) skips blocking gracefully but is
      fully audited and never reports an honest PASS.
    - No baseline available => NOT_EVALUATED, never a silent pass.
"""

from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Set

from Asgard.Bragi.QualityGate.services._git_diff import (
    LineRange,
    line_in_changes,
    total_changed_lines,
)

from Asgard.Bragi.QualityGate.baseline_store import BranchBaseline
from Asgard.Bragi.QualityGate.fingerprint import compute_fingerprint
from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    BreakGlassRecord,
    DifferentialGateResult,
    FindingSeverity,
    GateFinding,
    GateStatus,
)
from Asgard.Bragi.QualityGate.suppressions import (
    SuppressionDirective,
    lint_suppressions,
)

#: Minimum confidence (Certain/Probable bucket) for a finding to block.
BLOCKING_CONFIDENCE_THRESHOLD = 0.50

#: Severities that may block when NEW.
BLOCKING_SEVERITIES = {FindingSeverity.CRITICAL.value, FindingSeverity.HIGH.value}


def coerce_finding(obj, default_rule_id: str = "unknown") -> GateFinding:
    """
    Project an arbitrary scanner finding object (or dict) into a GateFinding.

    Recognises common attribute spellings so any Asgard scanner — or a
    third-party SARIF-shaped record — can feed the differential gate.
    """
    if isinstance(obj, GateFinding):
        return obj

    def _get(*names, default=None):
        for name in names:
            if isinstance(obj, dict):
                if name in obj and obj[name] is not None:
                    return obj[name]
            else:
                value = getattr(obj, name, None)
                if value is not None:
                    return value
        return default

    severity_raw = str(_get("severity", "level", default="medium")).lower()
    if severity_raw not in {s.value for s in FindingSeverity}:
        severity_raw = "medium"

    line = _get("line", "line_number", "lineno")
    try:
        line = int(line) if line is not None else None
    except (TypeError, ValueError):
        line = None

    try:
        confidence = float(_get("confidence", default=1.0))
    except (TypeError, ValueError):
        confidence = 1.0
    confidence = min(max(confidence, 0.0), 1.0)

    return GateFinding(
        rule_id=str(_get("rule_id", "rule", "violation_type", "check_id",
                         default=default_rule_id)),
        file_path=str(_get("file_path", "file", "path", default="")),
        line=line,
        severity=severity_raw,
        confidence=confidence,
        message=str(_get("message", "description", default="") or ""),
        snippet=str(_get("snippet", "code", "code_snippet", default="") or ""),
        fingerprint=str(_get("fingerprint", default="") or ""),
    )


def ensure_fingerprint(
    finding: GateFinding,
    sources: Optional[Dict[str, str]] = None,
) -> GateFinding:
    """Fill in the finding's fingerprint if empty (AST anchor when source given)."""
    if finding.fingerprint:
        return finding
    source = (sources or {}).get(finding.file_path)
    finding.fingerprint = compute_fingerprint(
        finding.rule_id,
        finding.file_path,
        source=source,
        line=finding.line,
        snippet=finding.snippet or (finding.message or None),
    )
    return finding


def verify_scan_determinism(
    first_scan: Iterable[GateFinding],
    second_scan: Iterable[GateFinding],
) -> List[str]:
    """
    Zero-flakiness check: given two scans of identical input, return the rule
    ids whose fingerprint sets differ. Those rules forfeit blocking rights
    (fail the rule, not the user).
    """
    def _by_rule(findings: Iterable[GateFinding]) -> Dict[str, Set[str]]:
        acc: Dict[str, Set[str]] = {}
        for f in findings:
            acc.setdefault(f.rule_id, set()).add(f.fingerprint)
        return acc

    first = _by_rule(first_scan)
    second = _by_rule(second_scan)
    flaky = [
        rule for rule in set(first) | set(second)
        if first.get(rule, set()) != second.get(rule, set())
    ]
    return sorted(flaky)


class DifferentialGateEngine:
    """
    Evaluates the differential (new-code) gate.

    Args:
        flaky_rules: rules proven non-deterministic; demoted to warn-only.
        today: injectable clock for suppression expiry checks (tests).
    """

    def __init__(self, flaky_rules: Optional[Iterable[str]] = None,
                 today: Optional[date] = None):
        self.flaky_rules: Set[str] = set(flaky_rules or ())
        self.today = today

    def evaluate(
        self,
        findings: Sequence,
        baseline: Optional[BranchBaseline],
        *,
        sources: Optional[Dict[str, str]] = None,
        suppressions: Optional[Sequence[SuppressionDirective]] = None,
        break_glass: Optional[BreakGlassRecord] = None,
        changed_files: Optional[Dict[str, List[LineRange]]] = None,
        small_change_threshold_lines: Optional[int] = None,
    ) -> DifferentialGateResult:
        """
        Classify findings against the baseline and apply the blocking policy.

        Missing baseline never silently passes: the result is NOT_EVALUATED.

        When `changed_files` (from the git-diff engine) is supplied:
        - changes below `small_change_threshold_lines` skip evaluation by
          explicit policy: PASSED (small change), annotated as skipped;
        - pre-existing findings on MODIFIED lines surface as
          `legacy_touched_findings` warnings (DEEPTHINK_09's "legacy the
          developer directly modified" rule).
        """
        gate_findings = [
            ensure_fingerprint(coerce_finding(f), sources) for f in findings
        ]
        suppressions = list(suppressions or ())
        suppression_violations = lint_suppressions(suppressions, self.today)

        result = DifferentialGateResult(
            baseline_available=baseline is not None,
            baseline_branch=baseline.branch if baseline else "",
            baseline_commit=baseline.commit if baseline else "",
            suppression_violations=suppression_violations,
            demoted_flaky_rules=sorted(
                self.flaky_rules & {f.rule_id for f in gate_findings}
            ),
        )

        if changed_files is not None:
            result.changed_lines = total_changed_lines(changed_files)
            if (small_change_threshold_lines is not None
                    and result.changed_lines < small_change_threshold_lines):
                result.skipped_small_change = True
                result.status = GateStatus.PASSED
                result.summary = (
                    f"Differential gate: PASSED (small change) — "
                    f"{result.changed_lines} changed line(s) below the "
                    f"{small_change_threshold_lines}-line threshold; "
                    "conditions skipped by explicit policy."
                )
                return result

        if baseline is None:
            result.status = GateStatus.NOT_EVALUATED
            result.summary = (
                "Differential gate NOT EVALUATED: no baseline fingerprint set "
                "is available for comparison. Capture a reference-branch "
                "baseline first; absence of a baseline is not a pass."
            )
            return result

        baseline_fps = baseline.fingerprint_set
        active_suppressions = [s for s in suppressions if s.is_active(self.today)]

        for finding in gate_findings:
            if finding.fingerprint in baseline_fps:
                result.preexisting_count += 1
                if changed_files is not None and line_in_changes(
                        changed_files, finding.file_path, finding.line):
                    result.legacy_touched_findings.append(finding)
                continue
            if self._is_suppressed(finding, active_suppressions):
                result.suppressed_findings.append(finding)
                continue
            result.new_findings.append(finding)
            if self._blocks(finding):
                result.blocking_findings.append(finding)
            else:
                result.advisory_findings.append(finding)

        result.status = self._status(result, break_glass)
        result.summary = self._summary(result)
        return result

    # -- policy ------------------------------------------------------------

    def _blocks(self, finding: GateFinding) -> bool:
        """HIGH/CRITICAL + Certain/Probable + deterministic rule."""
        return (
            str(finding.severity) in BLOCKING_SEVERITIES
            and finding.confidence >= BLOCKING_CONFIDENCE_THRESHOLD
            and finding.rule_id not in self.flaky_rules
        )

    @staticmethod
    def _is_suppressed(finding: GateFinding,
                       active: List[SuppressionDirective]) -> bool:
        """A suppression matches on rule id and file (line-local when both known)."""
        from Asgard.Bragi.QualityGate.fingerprint import normalize_path
        for s in active:
            if s.rule_id.lower() != finding.rule_id.lower():
                continue
            if s.file_path and finding.file_path and \
                    normalize_path(s.file_path) != normalize_path(finding.file_path):
                continue
            if s.line and finding.line is not None and \
                    abs(s.line - finding.line) > 1:
                continue
            return True
        return False

    def _status(self, result: DifferentialGateResult,
                break_glass: Optional[BreakGlassRecord]) -> GateStatus:
        blocked = bool(result.blocking_findings) or bool(result.suppression_violations)
        if blocked and break_glass is not None:
            break_glass.bypassed_findings = [
                f.fingerprint for f in result.blocking_findings
            ]
            result.break_glass = break_glass
            return GateStatus.WARNING
        if blocked:
            return GateStatus.FAILED
        if (result.advisory_findings or result.suppressed_findings
                or result.legacy_touched_findings):
            return GateStatus.WARNING
        return GateStatus.PASSED

    @staticmethod
    def _summary(result: DifferentialGateResult) -> str:
        parts = [
            f"Differential gate: {str(result.status).upper()}",
            f"{len(result.new_findings)} new finding(s)",
            f"{len(result.blocking_findings)} blocking",
            f"{result.preexisting_count} pre-existing (async burndown)",
        ]
        if result.legacy_touched_findings:
            parts.append(
                f"{len(result.legacy_touched_findings)} legacy finding(s) on "
                "modified lines (warnings)"
            )
        if result.suppression_violations:
            parts.append(
                f"{len(result.suppression_violations)} invalid/expired suppression(s)"
            )
        if result.demoted_flaky_rules:
            parts.append(
                f"flaky rules demoted to warn-only: {', '.join(result.demoted_flaky_rules)}"
            )
        if result.break_glass is not None:
            parts.append(
                f"BREAK-GLASS bypass by {result.break_glass.actor} "
                f"({result.break_glass.remediation_sla_hours}h remediation SLA)"
            )
        return "; ".join(parts)
