"""Main Go analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Bragi.Quality.languages.go.models.go_models import (
    GoFinding,
    GoReport,
    GoScanConfig,
)
from Asgard.Bragi.Quality.languages.go.services._go_rules import (
    check_error_not_checked, check_no_panic, check_sql_injection, check_no_defer_in_loop, check_no_hardcoded_credentials, check_no_unbuffered_channel, check_no_global_mutex, check_context_not_propagated,
    check_command_injection, check_xss, check_path_traversal, check_weak_crypto,
)

_RULES = [
    check_error_not_checked,
    check_no_panic,
    check_sql_injection,
    check_no_defer_in_loop,
    check_no_hardcoded_credentials,
    check_no_unbuffered_channel,
    check_no_global_mutex,
    check_context_not_propagated,
    check_command_injection,
    check_xss,
    check_path_traversal,
    check_weak_crypto,
]


class GoAnalyzer:
    """Analyses Go source files for security and quality issues."""

    def __init__(self, config: Optional[GoScanConfig] = None) -> None:
        self._config = config or GoScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> GoReport:
        """Analyze all Go files under scan_path and return a GoReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = GoReport(scan_path=str(path))
        for src_file in path.rglob("*.go"):
            try:
                source = src_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = source.splitlines()
            for rule_fn in _RULES:
                rule_id = rule_fn.__doc__.split(":")[0].strip() if rule_fn.__doc__ else ""
                enabled = self._config.rules.get(rule_id, True)
                report.findings.extend(rule_fn(str(src_file), lines, enabled=enabled))
        return report

    def analyze_file(self, file_path: Path) -> List[GoFinding]:
        if file_path.suffix.lower() not in {".go"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[GoFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[GoScanConfig] = None) -> List[GoFinding]:
        cfg = config or GoScanConfig(scan_path=scan_path)
        findings: List[GoFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
