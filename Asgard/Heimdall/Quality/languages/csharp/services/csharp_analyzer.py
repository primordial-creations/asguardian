"""Main Csharp analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List

from Asgard.Heimdall.Quality.languages.csharp.models.csharp_models import (
    CsharpFinding,
    CsharpScanConfig,
)
from Asgard.Heimdall.Quality.languages.csharp.services._csharp_rules import (
    check_sql_injection, check_no_hardcoded_credentials, check_no_empty_catch, check_xss, check_no_weak_crypto, check_path_traversal, check_command_injection, check_no_debug_code,
)


class CsharpAnalyzer:
    """Analyses Csharp source files for security and quality issues."""

    def __init__(self) -> None:
        self._rules = [
            check_sql_injection,
            check_no_hardcoded_credentials,
            check_no_empty_catch,
            check_xss,
            check_no_weak_crypto,
            check_path_traversal,
            check_command_injection,
            check_no_debug_code,
        ]

    def analyze_file(self, file_path: Path) -> List[CsharpFinding]:
        if file_path.suffix.lower() not in {".cs"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[CsharpFinding] = []
        for rule in self._rules:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: CsharpScanConfig | None = None) -> List[CsharpFinding]:
        cfg = config or CsharpScanConfig(scan_path=scan_path)
        findings: List[CsharpFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
