"""
Race condition / TOCTOU detector (plan 07.7).

Precision-first per RESEARCH_06 / DEEPTHINK_04's FP-bias table: this
category is precision-biased, not recall-biased, so the old
line-regex table (flagging every `x += 1`, every module-level `{}`, every
`await` followed by an assignment) has been removed -- it was
unconditionally noisy on completely race-free code. Python now goes
through the AST canonical-pattern resolver
(`_toctou_ast_analysis.scan_toctou`, plan 07.7): exists()-then-open()
file races and ORM get/mutate/save without select_for_update(). Other
languages keep a small, deliberately narrow regex fallback restricted to
the two patterns that are unambiguous from text alone (`tempfile.mktemp`,
raw non-atomic file check-then-open shape) -- broad shared-state/counter
guessing is not reinstated for any language.

Severity is capped at MEDIUM: TOCTOU findings are never gate-blocking
(plan 07.7 explicit instruction) since exploitability depends on runtime
scheduling this static pass cannot observe.
"""

import ast
import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import (
    RaceConditionFinding,
    RaceConditionScanConfig,
    RaceConditionScanReport,
    RaceConditionSeverity,
)
from Asgard.Heimdall.Security.RaceCondition.services import _toctou_ast_analysis as _ast_analysis
from Asgard.Heimdall.Security.context.test_context import is_test_context
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

# Non-Python fallback: only the two patterns unambiguous from text alone.
_RACE_PATTERNS: dict = {
    "toctou_file": [
        (r"(?:os\.path\.exists|Path.*\.exists|fs\.exists)\s*\([^)]+\)", "LOW", "toctou_exists", "Possible TOCTOU: check-then-use on file existence (unconfirmed without cross-statement dataflow on this language)", "Use atomic operations or file locking"),
    ],
    "file_operations": [
        (r"tempfile\.mktemp\s*\(", "MEDIUM", "mktemp_toctou", "mktemp() is vulnerable to TOCTOU (use mkstemp/NamedTemporaryFile)", "Use tempfile.mkstemp() or NamedTemporaryFile"),
    ],
}


class RaceConditionDetector:
    """Detects potential race conditions in source code."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _RACE_PATTERNS.items():
            self._compiled[category] = [
                (re.compile(p, re.IGNORECASE | re.MULTILINE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: RaceConditionScanConfig) -> RaceConditionScanReport:
        findings: List[RaceConditionFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            findings = self._scan_file(target)
            files_scanned = 1
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    ff = self._scan_file(fp)
                    if ff:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_category: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category] = by_category.get(f.category, 0) + 1

        return RaceConditionScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[RaceConditionFinding]:
        if file_path.suffix.lower() not in {".py", ".js", ".ts", ".java", ".go", ".cs", ".rb"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        lines = source.splitlines()
        in_test = is_test_context(str(file_path))

        if file_path.suffix.lower() == ".py":
            try:
                tree = ast.parse(source)
            except SyntaxError:
                tree = None
            if tree is not None:
                return self._scan_python_ast(tree, lines, file_path, in_test)

        return self._scan_regex_fallback(lines, file_path, in_test)

    def _scan_python_ast(self, tree, lines, file_path: Path, in_test: bool) -> List[RaceConditionFinding]:
        findings: List[RaceConditionFinding] = []
        for hit in _ast_analysis.scan_toctou(tree, lines):
            severity = hit.severity
            confidence = hit.confidence
            description = hit.description
            if in_test:
                # TOCTOU races in test fixtures are not shipped-code risk;
                # downgrade rather than suppress (plan 08 network-config
                # class action for TEST_UNIT/TEST_INTEGRATION).
                confidence = min(confidence, 0.2)
                description += " (in test code -- downgraded, not suppressed)"
            findings.append(RaceConditionFinding(
                file_path=str(file_path),
                line_number=hit.line_number,
                severity=RaceConditionSeverity(severity),
                category="toctou",
                issue_type=hit.issue_type,
                code_snippet=hit.snippet,
                description=description,
                recommendation=hit.recommendation,
                mechanism_id=hit.mechanism_id,
                confidence=confidence,
                confidence_bucket=confidence_bucket(confidence),
                is_hotspot=confidence < 0.5,
            ))
        return findings

    def _scan_regex_fallback(self, lines, file_path: Path, in_test: bool) -> List[RaceConditionFinding]:
        findings: List[RaceConditionFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        confidence = 0.3 if sev == "LOW" else 0.5
                        if in_test:
                            confidence = min(confidence, 0.15)
                        findings.append(RaceConditionFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=RaceConditionSeverity(sev),
                            category=category,
                            issue_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                            mechanism_id=f"race_condition.{ptype}",
                            confidence=confidence,
                            confidence_bucket=confidence_bucket(confidence),
                            is_hotspot=confidence < 0.5,
                        ))
                        break

        return findings
