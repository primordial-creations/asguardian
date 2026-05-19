"""Main Java analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.java.models.java_models import (
    JavaFinding,
    JavaReport,
    JavaScanConfig,
)
from Asgard.Heimdall.Quality.languages.java.services._java_rules import (
    check_sql_injection, check_no_system_exit, check_no_print_stacktrace, check_empty_catch, check_string_equals, check_no_hardcoded_credentials, check_no_raw_types, check_no_object_finalize,
)

_RULES = [
    check_sql_injection,
    check_no_system_exit,
    check_no_print_stacktrace,
    check_empty_catch,
    check_string_equals,
    check_no_hardcoded_credentials,
    check_no_raw_types,
    check_no_object_finalize,
]


class JavaAnalyzer:
    """Analyses Java source files for security and quality issues."""

    def __init__(self, config: Optional[JavaScanConfig] = None) -> None:
        self._config = config or JavaScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> JavaReport:
        """Analyze all Java files under scan_path and return a JavaReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = JavaReport(scan_path=str(path))
        for src_file in path.rglob("*.java"):
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

    def analyze_file(self, file_path: Path) -> List[JavaFinding]:
        if file_path.suffix.lower() not in {".java"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[JavaFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[JavaScanConfig] = None) -> List[JavaFinding]:
        cfg = config or JavaScanConfig(scan_path=scan_path)
        findings: List[JavaFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
