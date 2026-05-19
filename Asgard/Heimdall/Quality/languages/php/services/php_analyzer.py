"""Main Php analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List

from Asgard.Heimdall.Quality.languages.php.models.php_models import (
    PhpFinding,
    PhpScanConfig,
)
from Asgard.Heimdall.Quality.languages.php.services._php_rules import (
    check_sql_injection, check_xss, check_no_eval, check_file_inclusion, check_command_injection, check_no_md5_password, check_no_extract, check_no_hardcoded_credentials,
)


class PhpAnalyzer:
    """Analyses Php source files for security and quality issues."""

    def __init__(self) -> None:
        self._rules = [
            check_sql_injection,
            check_xss,
            check_no_eval,
            check_file_inclusion,
            check_command_injection,
            check_no_md5_password,
            check_no_extract,
            check_no_hardcoded_credentials,
        ]

    def analyze_file(self, file_path: Path) -> List[PhpFinding]:
        if file_path.suffix.lower() not in {".php", ".php3", ".php4", ".php5", ".phtml"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[PhpFinding] = []
        for rule in self._rules:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: PhpScanConfig | None = None) -> List[PhpFinding]:
        cfg = config or PhpScanConfig(scan_path=scan_path)
        findings: List[PhpFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
