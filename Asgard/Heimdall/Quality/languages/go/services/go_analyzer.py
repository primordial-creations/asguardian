"""Main Go analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List

from Asgard.Heimdall.Quality.languages.go.models.go_models import (
    GoFinding,
    GoScanConfig,
)
from Asgard.Heimdall.Quality.languages.go.services._go_rules import (
    check_error_not_checked, check_no_panic, check_sql_injection, check_no_defer_in_loop, check_no_hardcoded_credentials, check_no_unbuffered_channel, check_no_global_mutex, check_context_not_propagated,
)


class GoAnalyzer:
    """Analyses Go source files for security and quality issues."""

    def __init__(self) -> None:
        self._rules = [
            check_error_not_checked,
            check_no_panic,
            check_sql_injection,
            check_no_defer_in_loop,
            check_no_hardcoded_credentials,
            check_no_unbuffered_channel,
            check_no_global_mutex,
            check_context_not_propagated,
        ]

    def analyze_file(self, file_path: Path) -> List[GoFinding]:
        if file_path.suffix.lower() not in {".go"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[GoFinding] = []
        for rule in self._rules:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: GoScanConfig | None = None) -> List[GoFinding]:
        cfg = config or GoScanConfig(scan_path=scan_path)
        findings: List[GoFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
