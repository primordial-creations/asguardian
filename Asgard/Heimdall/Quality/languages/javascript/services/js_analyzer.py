"""
Heimdall JavaScript Analyzer

Performs regex-based static analysis on JavaScript and JSX source files.
Because Python's ast module cannot parse JS/TS, all rules are implemented
using line-by-line regular expression matching.
"""

import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSAnalysisConfig,
    JSFinding,
    JSReport,
)
from Asgard.Heimdall.Quality.languages.javascript.services._js_rules import (
    check_eqeqeq,
    check_no_alert,
    check_no_debugger,
    check_no_eval,
    check_no_implied_eval,
)
from Asgard.Heimdall.Quality.languages.javascript.services._js_style_rules import (
    check_complexity,
    check_max_file_lines,
    check_max_line_length,
    check_no_console,
    check_no_empty_block,
    check_no_trailing_spaces,
    check_no_var,
)


class JSAnalyzer:
    """
    Regex-based static analyzer for JavaScript and JSX files.

    Each public rule method returns a list of JSFinding objects for a single
    file.  The top-level analyze() method discovers files, runs all enabled
    rules, and returns an aggregated JSReport.
    """

    def __init__(self, config: Optional[JSAnalysisConfig] = None) -> None:
        self._config = config or JSAnalysisConfig()

    def analyze(self, scan_path: Optional[str] = None) -> JSReport:
        """
        Analyze all matching source files under scan_path.

        Args:
            scan_path: Optional override for the config scan path.

        Returns:
            JSReport containing all findings.
        """
        start = datetime.now()
        root = Path(scan_path).resolve() if scan_path else self._config.scan_path.resolve()
        report = JSReport(scan_path=str(root), language=self._config.language)

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
        """Return all files matching the configured extensions, excluding patterns."""
        results: List[Path] = []
        for ext in self._config.include_extensions:
            for candidate in root.rglob(f"*{ext}"):
                if not self._is_excluded(candidate):
                    results.append(candidate)
        return sorted(set(results))

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

    def _analyze_file(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """Run all enabled rules against a single file's source lines."""
        findings: List[JSFinding] = []
        findings.extend(check_no_eval(file_path, lines, self._is_rule_enabled("js.no-eval")))
        findings.extend(check_no_implied_eval(file_path, lines, self._is_rule_enabled("js.no-implied-eval")))
        findings.extend(check_no_debugger(file_path, lines, self._is_rule_enabled("js.no-debugger")))
        findings.extend(check_eqeqeq(file_path, lines, self._is_rule_enabled("js.eqeqeq")))
        findings.extend(check_no_alert(file_path, lines, self._is_rule_enabled("js.no-alert")))
        findings.extend(check_no_var(file_path, lines, self._is_rule_enabled("js.no-var")))
        findings.extend(check_no_empty_block(file_path, lines, self._is_rule_enabled("js.no-empty-block")))
        findings.extend(check_no_console(file_path, lines, self._is_rule_enabled("js.no-console")))
        findings.extend(check_max_file_lines(file_path, lines, self._is_rule_enabled("js.max-file-lines"), self._config.max_file_lines))
        findings.extend(check_complexity(file_path, lines, self._is_rule_enabled("js.complexity"), self._config.max_complexity))
        findings.extend(check_no_trailing_spaces(file_path, lines, self._is_rule_enabled("js.no-trailing-spaces")))
        findings.extend(check_max_line_length(file_path, lines, self._is_rule_enabled("js.max-line-length")))
        return findings
