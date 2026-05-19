"""Main Ruby analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.ruby.models.ruby_models import (
    RubyFinding,
    RubyReport,
    RubyScanConfig,
)
from Asgard.Heimdall.Quality.languages.ruby.services._ruby_rules import (
    check_sql_injection, check_no_eval, check_command_injection, check_no_yaml_load, check_no_send, check_mass_assignment, check_no_hardcoded_credentials, check_no_md5_sha1,
    check_xss, check_path_traversal,
)

_RULES = [
    check_sql_injection,
    check_no_eval,
    check_command_injection,
    check_no_yaml_load,
    check_no_send,
    check_mass_assignment,
    check_no_hardcoded_credentials,
    check_no_md5_sha1,
    check_xss,
    check_path_traversal,
]


class RubyAnalyzer:
    """Analyses Ruby source files for security and quality issues."""

    def __init__(self, config: Optional[RubyScanConfig] = None) -> None:
        self._config = config or RubyScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> RubyReport:
        """Analyze all Ruby files under scan_path and return a RubyReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = RubyReport(scan_path=str(path))
        for src_file in path.rglob("*.rb"):
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

    def analyze_file(self, file_path: Path) -> List[RubyFinding]:
        if file_path.suffix.lower() not in {".rb", ".rake", ".gemspec"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[RubyFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[RubyScanConfig] = None) -> List[RubyFinding]:
        cfg = config or RubyScanConfig(scan_path=scan_path)
        findings: List[RubyFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
