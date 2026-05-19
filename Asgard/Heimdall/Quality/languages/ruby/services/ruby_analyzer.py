"""Main Ruby analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List

from Asgard.Heimdall.Quality.languages.ruby.models.ruby_models import (
    RubyFinding,
    RubyScanConfig,
)
from Asgard.Heimdall.Quality.languages.ruby.services._ruby_rules import (
    check_sql_injection, check_no_eval, check_command_injection, check_no_yaml_load, check_no_send, check_mass_assignment, check_no_hardcoded_credentials, check_no_md5_sha1,
)


class RubyAnalyzer:
    """Analyses Ruby source files for security and quality issues."""

    def __init__(self) -> None:
        self._rules = [
            check_sql_injection,
            check_no_eval,
            check_command_injection,
            check_no_yaml_load,
            check_no_send,
            check_mass_assignment,
            check_no_hardcoded_credentials,
            check_no_md5_sha1,
        ]

    def analyze_file(self, file_path: Path) -> List[RubyFinding]:
        if file_path.suffix.lower() not in {".rb", ".rake", ".gemspec"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[RubyFinding] = []
        for rule in self._rules:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: RubyScanConfig | None = None) -> List[RubyFinding]:
        cfg = config or RubyScanConfig(scan_path=scan_path)
        findings: List[RubyFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
