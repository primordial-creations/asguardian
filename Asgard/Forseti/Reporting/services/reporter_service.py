"""
Reporter Service - audience adapters over the canonical Finding model.

All reporters render from the same finding list; severity is fixed and
only *display* varies by audience (DEEPTHINK_09). Findings are sorted
stably by (file, line, rule_id) for golden-file friendliness.
"""

import json
from typing import Optional, Sequence

from Asgard.Forseti.Reporting.models.finding_models import (
    Finding,
    ReportEnvelope,
    ReportSummary,
)
from Asgard.Forseti.Rules.models._rule_base_models import Severity

TOOL_VERSION = "0.1.0"

_GITHUB_LEVELS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
    Severity.HINT: "notice",
}

_SARIF_LEVELS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
    Severity.HINT: "note",
}


def _sorted(findings: Sequence[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (
        f.coordinates.file or "",
        f.coordinates.line or 0,
        f.rule_id,
        f.coordinates.json_path,
    ))


def _sev_tag(severity: Severity) -> str:
    return {"error": "ERR", "warning": "WARN", "info": "INFO", "hint": "HINT"}[severity.value]


class TextReporter:
    """Dense greppable UNIX lines: `file:line:col SEV [rule-id] message`."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def render(self, findings: Sequence[Finding], **_: object) -> str:
        lines = []
        for finding in _sorted(findings):
            if finding.suppressed:
                continue
            if self.quiet and finding.severity != Severity.ERROR:
                continue
            coords = finding.coordinates
            location = ":".join(str(part) for part in (
                coords.file or "<input>",
                coords.line if coords.line is not None else "-",
                coords.column if coords.column is not None else "-",
            ))
            lines.append(
                f"{location} {_sev_tag(finding.severity)} "
                f"[{finding.rule_id}] {finding.message}"
            )
        summary = ReportSummary.from_findings(list(findings))
        lines.append(
            f"{summary.errors} error(s), {summary.warnings} warning(s), "
            f"{summary.info} info, {summary.hints} hint(s), "
            f"{summary.suppressed} suppressed"
        )
        return "\n".join(lines)


class ExplainReporter(TextReporter):
    """Text plus rationale and remediation per finding (educational surface)."""

    def render(self, findings: Sequence[Finding], **kwargs: object) -> str:
        lines = []
        for finding in _sorted(findings):
            if finding.suppressed:
                continue
            lines.append(TextReporter(quiet=False).render([finding]).splitlines()[0])
            if finding.rationale:
                lines.append(f"    why: {finding.rationale}")
            if finding.remediation:
                lines.append(f"    fix: {finding.remediation.description}")
        summary = ReportSummary.from_findings(list(findings))
        lines.append(
            f"{summary.errors} error(s), {summary.warnings} warning(s), "
            f"{summary.info} info, {summary.hints} hint(s), "
            f"{summary.suppressed} suppressed"
        )
        return "\n".join(lines)


class JsonReporter:
    """Stable machine envelope: {tool, version, ruleset_version, findings, summary}."""

    def render(
        self,
        findings: Sequence[Finding],
        ruleset_version: str = "1.0.0",
        score: Optional[float] = None,
        **_: object,
    ) -> str:
        envelope = ReportEnvelope(
            tool="forseti",
            version=TOOL_VERSION,
            ruleset_version=ruleset_version,
            findings=_sorted(findings),
            summary=ReportSummary.from_findings(list(findings)),
            score=score,
        )
        return json.dumps(envelope.model_dump(mode="json"), indent=2)

    @staticmethod
    def parse(text: str) -> ReportEnvelope:
        """Round-trip parse of a JSON envelope."""
        return ReportEnvelope(**json.loads(text))


class MarkdownReporter:
    """PR-comment-ready markdown grouped by severity."""

    def render(self, findings: Sequence[Finding], **_: object) -> str:
        summary = ReportSummary.from_findings(list(findings))
        lines = ["# Forseti Report", ""]
        lines.append(
            f"**{summary.errors}** error(s) | **{summary.warnings}** warning(s) | "
            f"**{summary.info}** info | **{summary.hints}** hint(s) | "
            f"**{summary.suppressed}** suppressed"
        )
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.HINT):
            group = [
                f for f in _sorted(findings)
                if f.severity == severity and not f.suppressed
            ]
            if not group:
                continue
            lines.append(f"\n## {severity.value.title()}s\n")
            lines.append("| Location | Rule | Message |")
            lines.append("|----------|------|---------|")
            for finding in group:
                coords = finding.coordinates
                where = coords.file or coords.json_path
                if coords.line is not None:
                    where = f"{where}:{coords.line}"
                lines.append(f"| `{where}` | {finding.rule_id} | {finding.message} |")
        return "\n".join(lines)


class SarifReporter:
    """SARIF 2.1.0 output (hand-rolled; no third-party dependency)."""

    def render(
        self,
        findings: Sequence[Finding],
        ruleset_version: str = "1.0.0",
        rule_metas: Optional[Sequence[object]] = None,
        **_: object,
    ) -> str:
        ordered = _sorted(findings)
        rule_ids = sorted({f.rule_id for f in ordered})
        metas_by_id = {}
        for meta in rule_metas or []:
            metas_by_id[getattr(meta, "rule_id", None)] = meta
        rules = []
        for rule_id in rule_ids:
            meta = metas_by_id.get(rule_id)
            descriptor: dict = {"id": rule_id}
            if meta is not None:
                if getattr(meta, "description", ""):
                    descriptor["shortDescription"] = {"text": meta.description}
                if getattr(meta, "rationale", ""):
                    descriptor["fullDescription"] = {"text": meta.rationale}
                descriptor["properties"] = {
                    "category": str(getattr(meta, "category", "")),
                    "confidence": str(getattr(meta, "confidence", "")),
                }
            rules.append(descriptor)
        rule_index = {rule_id: i for i, rule_id in enumerate(rule_ids)}
        results = []
        for finding in ordered:
            coords = finding.coordinates
            region = {}
            if coords.line is not None:
                region["startLine"] = coords.line
                if coords.column is not None:
                    region["startColumn"] = coords.column
            location = {
                "physicalLocation": {
                    "artifactLocation": {"uri": coords.file or "<input>"},
                    **({"region": region} if region else {}),
                },
                "logicalLocations": [{"fullyQualifiedName": coords.json_path}],
            }
            result = {
                "ruleId": finding.rule_id,
                "ruleIndex": rule_index[finding.rule_id],
                "level": _SARIF_LEVELS[finding.severity],
                "message": {"text": finding.message},
                "locations": [location],
            }
            if finding.suppressed:
                result["suppressions"] = [{
                    "kind": "inSource",
                    **({"justification": finding.suppression_reason}
                       if finding.suppression_reason else {}),
                }]
            results.append(result)
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
                       "Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {
                    "name": "Forseti",
                    "version": TOOL_VERSION,
                    "semanticVersion": ruleset_version,
                    "informationUri": "https://github.com/asgard/asguardian",
                    "rules": rules,
                }},
                "results": results,
            }],
        }
        return json.dumps(sarif, indent=2)


class GithubReporter:
    """GitHub Actions workflow-command annotations."""

    def render(self, findings: Sequence[Finding], **_: object) -> str:
        lines = []
        for finding in _sorted(findings):
            if finding.suppressed:
                continue
            coords = finding.coordinates
            level = _GITHUB_LEVELS[finding.severity]
            props = []
            if coords.file:
                props.append(f"file={coords.file}")
            if coords.line is not None:
                props.append(f"line={coords.line}")
            if coords.column is not None:
                props.append(f"col={coords.column}")
            prop_str = " " + ",".join(props) if props else ""
            lines.append(f"::{level}{prop_str}::[{finding.rule_id}] {finding.message}")
        return "\n".join(lines)


def select_reporter(fmt: str = "text", explain: bool = False, quiet: bool = False):
    """Choose the reporter for a --format / --explain / --quiet combination."""
    if explain and fmt in ("text", None):
        return ExplainReporter()
    reporters = {
        "text": TextReporter(quiet=quiet),
        "json": JsonReporter(),
        "markdown": MarkdownReporter(),
        "sarif": SarifReporter(),
        "github": GithubReporter(),
    }
    return reporters.get(fmt or "text", TextReporter(quiet=quiet))
