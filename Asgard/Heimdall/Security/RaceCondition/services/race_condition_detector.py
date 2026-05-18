"""Race condition detector."""

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

_RACE_PATTERNS: dict = {
    "toctou_file": [
        (r"(?:os\.path\.exists|Path.*\.exists|fs\.exists)\s*\([^)]+\)", "HIGH", "toctou_exists", "TOCTOU: Check-then-use on file existence", "Use atomic operations or file locking"),
        (r"(?:os\.access|access)\s*\([^)]+\)", "HIGH", "toctou_access", "TOCTOU: Check-then-use on file access", "Use try/except instead of access check"),
    ],
    "shared_state": [
        (r"(?:global|static)\s+\w+\s*=\s*(?:\[\]|\{\}|0|None|null)", "MEDIUM", "shared_mutable_state", "Shared mutable state without synchronization", "Use thread-safe data structures or locks"),
    ],
    "thread_unsafe": [
        (r"threading\.Thread.*target.*(?:self\.|cls\.)\w+\s*(?:\+=|-=|\+\+|--)", "HIGH", "thread_unsafe_mutation", "Thread mutation without lock", "Protect shared state with threading.Lock()"),
        (r"concurrent\.futures.*(?:self\.|cls\.)\w+\s*(?:\+=|-=)", "HIGH", "executor_unsafe", "Shared state mutation in thread pool", "Use locks or thread-safe collections"),
    ],
    "async_issues": [
        (r"await\s+\w+\([^)]*\)\s*\n.*\w+\s*=", "MEDIUM", "async_shared_assign", "Assignment after await may have race with other coroutines", "Use asyncio.Lock() for shared state"),
    ],
    "database": [
        (r"SELECT.*WHERE.*(?:=|IN).*(?:\n.*)?UPDATE.*WHERE.*(?:=|IN)", "HIGH", "select_then_update", "SELECT then UPDATE without transaction (TOCTOU in DB)", "Use SELECT FOR UPDATE or transactions"),
    ],
    "cache": [
        (r"if\s+\w+\s+(?:not\s+)?in\s+(?:cache|redis|memcache).*\n.*(?:cache|redis|memcache)\[", "MEDIUM", "cache_toctou", "Cache check-then-set without atomic operation", "Use atomic cache operations (SET NX, SETNX)"),
    ],
    "counter_operations": [
        (r"(?:self\.|cls\.)?\w+\s*\+=\s*1(?!\s*#\s*atomic)", "MEDIUM", "non_atomic_counter", "Non-atomic counter increment in multi-threaded context", "Use threading.Lock() or atomic operations"),
    ],
    "file_operations": [
        (r"tempfile\.mktemp\s*\(", "HIGH", "mktemp_toctou", "mktemp() is vulnerable to TOCTOU (use mkstemp/NamedTemporaryFile)", "Use tempfile.mkstemp() or NamedTemporaryFile"),
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
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        findings: List[RaceConditionFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        findings.append(RaceConditionFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=RaceConditionSeverity(sev),
                            category=category,
                            issue_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                        ))
                        break

        return findings
