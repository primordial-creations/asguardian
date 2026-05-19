"""Main Php analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.php.models.php_models import (
    PhpFinding,
    PhpReport,
    PhpScanConfig,
)
from Asgard.Heimdall.Quality.languages.php.services._php_rules import (
    check_sql_injection, check_xss, check_no_eval, check_file_inclusion, check_command_injection, check_no_md5_password, check_no_extract, check_no_hardcoded_credentials,
)

_RULES = [
    check_sql_injection,
    check_xss,
    check_no_eval,
    check_file_inclusion,
    check_command_injection,
    check_no_md5_password,
    check_no_extract,
    check_no_hardcoded_credentials,
]


class PhpAnalyzer:
    """Analyses Php source files for security and quality issues."""

    def __init__(self, config: Optional[PhpScanConfig] = None) -> None:
        self._config = config or PhpScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> PhpReport:
        """Analyze all PHP files under scan_path and return a PhpReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = PhpReport(scan_path=str(path))
        for src_file in path.rglob("*.php"):
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

    def analyze_file(self, file_path: Path) -> List[PhpFinding]:
        if file_path.suffix.lower() not in {".php", ".php3", ".php4", ".php5", ".phtml"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[PhpFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[PhpScanConfig] = None) -> List[PhpFinding]:
        cfg = config or PhpScanConfig(scan_path=scan_path)
        findings: List[PhpFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
