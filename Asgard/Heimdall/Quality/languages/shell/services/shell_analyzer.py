"""
Heimdall Shell Script Analyzer

Performs regex-based static analysis on shell and bash script files.
Files are discovered by extension (.sh, .bash) and optionally by shebang
line (#!/bin/bash, #!/bin/sh, #!/usr/bin/env bash).
"""

import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.shell.models.shell_models import (
    ShellAnalysisConfig,
    ShellFinding,
    ShellReport,
)
from Asgard.Heimdall.Quality.languages.shell.services._shell_rules import (
    _SHELL_SHEBANGS,
    check_curl_insecure,
    check_eval_injection,
    check_hardcoded_secret,
    check_sudo_usage,
    check_wget_no_check,
)
from Asgard.Heimdall.Quality.languages.shell.services._shell_bug_rules import (
    check_cd_without_check,
    check_function_keyword,
    check_max_line_length,
    check_missing_set_e,
    check_missing_set_u,
    check_trailing_whitespace,
    check_unquoted_dollar_star,
)


class ShellAnalyzer:
    """
    Regex-based static analyzer for shell script files.

    Each public rule method returns a list of ShellFinding objects for a
    single file.  The top-level analyze() method discovers files, runs all
    enabled rules, and returns an aggregated ShellReport.
    """

    def __init__(self, config: Optional[ShellAnalysisConfig] = None) -> None:
        self._config = config or ShellAnalysisConfig()

    def analyze(self, scan_path: Optional[str] = None) -> ShellReport:
        """
        Analyze all matching shell script files under scan_path.

        Args:
            scan_path: Optional override for the config scan path.

        Returns:
            ShellReport containing all findings.
        """
        start = datetime.now()
        root = Path(scan_path).resolve() if scan_path else self._config.scan_path.resolve()
        report = ShellReport(scan_path=str(root))

        files = self._discover_files(root)
        report.files_analyzed = len(files)

        for file_path in files:
            try:
                source_lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for finding in self._analyze_file(str(file_path), source_lines):
                report.add_finding(finding)

        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
        return report

    def _discover_files(self, root: Path) -> List[Path]:
        """Return all shell script files matching extensions or shebang."""
        results: set = set()

        for ext in self._config.include_extensions:
            for candidate in root.rglob(f"*{ext}"):
                if not self._is_excluded(candidate):
                    results.add(candidate)

        if self._config.also_check_shebangs:
            for candidate in root.rglob("*"):
                if candidate.is_file() and not self._is_excluded(candidate):
                    if candidate.suffix not in self._config.include_extensions:
                        if self._has_shell_shebang(candidate):
                            results.add(candidate)

        return sorted(results)

    def _has_shell_shebang(self, path: Path) -> bool:
        """Return True if the first line of the file is a recognized shell shebang."""
        try:
            first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
            return any(first_line.startswith(shebang) for shebang in _SHELL_SHEBANGS)
        except (OSError, IndexError):
            return False

    def _is_excluded(self, path: Path) -> bool:
        """Return True if the path matches any exclusion pattern."""
        parts = path.parts
        for pattern in self._config.exclude_patterns:
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _is_rule_enabled(self, rule_id: str) -> bool:
        """Return True when the rule should be executed."""
        if rule_id in self._config.disabled_rules:
            return False
        if self._config.enabled_rules is not None:
            return rule_id in self._config.enabled_rules
        return True

    def _analyze_file(self, file_path: str, lines: List[str]) -> List[ShellFinding]:
        """Run all enabled rules against a single file's source lines."""
        findings: List[ShellFinding] = []
        findings.extend(check_eval_injection(file_path, lines, self._is_rule_enabled("shell.eval-injection")))
        findings.extend(check_curl_insecure(file_path, lines, self._is_rule_enabled("shell.curl-insecure")))
        findings.extend(check_wget_no_check(file_path, lines, self._is_rule_enabled("shell.wget-no-check")))
        findings.extend(check_hardcoded_secret(file_path, lines, self._is_rule_enabled("shell.hardcoded-secret")))
        findings.extend(check_sudo_usage(file_path, lines, self._is_rule_enabled("shell.sudo-usage")))
        findings.extend(check_missing_set_e(file_path, lines, self._is_rule_enabled("shell.missing-set-e")))
        findings.extend(check_missing_set_u(file_path, lines, self._is_rule_enabled("shell.missing-set-u")))
        findings.extend(check_cd_without_check(file_path, lines, self._is_rule_enabled("shell.cd-without-check")))
        findings.extend(check_unquoted_dollar_star(file_path, lines, self._is_rule_enabled("shell.unquoted-dollar-star")))
        findings.extend(check_trailing_whitespace(file_path, lines, self._is_rule_enabled("shell.trailing-whitespace")))
        findings.extend(check_max_line_length(file_path, lines, self._is_rule_enabled("shell.max-line-length")))
        findings.extend(check_function_keyword(file_path, lines, self._is_rule_enabled("shell.function-keyword")))
        return findings
