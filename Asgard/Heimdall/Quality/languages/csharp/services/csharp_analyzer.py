"""Main Csharp analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.csharp.models.csharp_models import (
    CsharpFinding,
    CsharpReport,
    CsharpScanConfig,
)
from Asgard.Heimdall.Quality.languages.csharp.services._csharp_rules import (
    check_sql_injection, check_no_hardcoded_credentials, check_no_empty_catch, check_xss, check_no_weak_crypto, check_path_traversal, check_command_injection, check_no_debug_code,
)

_RULES = [
    check_sql_injection,
    check_no_hardcoded_credentials,
    check_no_empty_catch,
    check_xss,
    check_no_weak_crypto,
    check_path_traversal,
    check_command_injection,
    check_no_debug_code,
]


class CsharpAnalyzer:
    """Analyses Csharp source files for security and quality issues."""

    def __init__(self, config: Optional[CsharpScanConfig] = None) -> None:
        self._config = config or CsharpScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> CsharpReport:
        """Analyze all C# files under scan_path and return a CsharpReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = CsharpReport(scan_path=str(path))
        for src_file in path.rglob("*.cs"):
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

    def analyze_file(self, file_path: Path) -> List[CsharpFinding]:
        if file_path.suffix.lower() not in {".cs"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[CsharpFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[CsharpScanConfig] = None) -> List[CsharpFinding]:
        cfg = config or CsharpScanConfig(scan_path=scan_path)
        findings: List[CsharpFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
