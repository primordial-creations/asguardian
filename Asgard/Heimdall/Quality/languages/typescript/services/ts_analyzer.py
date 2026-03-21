"""
Heimdall TypeScript Analyzer

Extends the JavaScript analyzer with TypeScript-specific rules.
Scans .ts and .tsx files, runs all JS rules, then appends TS-specific
findings.  The returned report has language set to 'typescript'.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSAnalysisConfig,
    JSFinding,
    JSReport,
    JSRuleCategory,
    JSSeverity,
)
from Asgard.Heimdall.Quality.languages.javascript.services.js_analyzer import JSAnalyzer
from Asgard.Heimdall.Quality.languages.javascript.services._js_rules import _make_finding


class TSAnalyzer:
    """
    Regex-based static analyzer for TypeScript and TSX files.

    Delegates JS rule execution to JSAnalyzer (configured for TS extensions),
    then applies additional TypeScript-specific rules to each file.
    """

    _TS_EXTENSIONS = [".ts", ".tsx"]

    def __init__(self, config: Optional[JSAnalysisConfig] = None) -> None:
        if config is None:
            config = JSAnalysisConfig(
                language="typescript",
                include_extensions=self._TS_EXTENSIONS,
            )
        else:
            # Force TS extensions and language label regardless of caller config
            config = config.copy(
                update={
                    "include_extensions": self._TS_EXTENSIONS,
                    "language": "typescript",
                }
            )
        self._config = config
        self._js_analyzer = JSAnalyzer(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, scan_path: Optional[str] = None) -> JSReport:
        """
        Analyze all matching TypeScript source files under scan_path.

        Args:
            scan_path: Optional override for the config scan path.

        Returns:
            JSReport with language='typescript' containing all findings.
        """
        start = datetime.now()
        root = Path(scan_path).resolve() if scan_path else self._config.scan_path.resolve()

        # Run JS rules via the base analyzer
        report = self._js_analyzer.analyze(scan_path=str(root))
        report.language = "typescript"

        # Run TS-specific rules per file
        files = self._js_analyzer._discover_files(root)
        for file_path in files:
            try:
                source_lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for finding in self._analyze_ts_file(str(file_path), source_lines):
                report.add_finding(finding)

        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
        return report

    # ------------------------------------------------------------------
    # TypeScript-specific rules
    # ------------------------------------------------------------------

    def _is_rule_enabled(self, rule_id: str) -> bool:
        """Return True when the rule should be executed."""
        if rule_id in self._config.disabled_rules:
            return False
        if self._config.enabled_rules is not None:
            return rule_id in self._config.enabled_rules
        return True

    def _analyze_ts_file(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """Run all TS-specific rules against a single file's source lines."""
        findings: List[JSFinding] = []
        findings.extend(self._check_no_explicit_any(file_path, lines))
        findings.extend(self._check_no_any_cast(file_path, lines))
        findings.extend(self._check_no_non_null_assertion(file_path, lines))
        findings.extend(self._check_prefer_interface(file_path, lines))
        findings.extend(self._check_no_implicit_any(file_path, lines))
        return findings

    def _check_no_explicit_any(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """ts.no-explicit-any: explicit ': any' type annotation."""
        if not self._is_rule_enabled("ts.no-explicit-any"):
            return []
        findings: List[JSFinding] = []
        pattern = re.compile(r":\s*any\b")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(_make_finding(
                    file_path=file_path,
                    line_number=idx,
                    rule_id="ts.no-explicit-any",
                    category=JSRuleCategory.CODE_SMELL,
                    severity=JSSeverity.WARNING,
                    title="Explicit 'any' type annotation",
                    description="Using 'any' defeats the purpose of TypeScript's type system.",
                    code_snippet=line,
                    fix_suggestion="Replace 'any' with a specific type or use 'unknown'.",
                ))
        return findings

    def _check_no_any_cast(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """ts.no-any-cast: cast to 'any' via 'as any'."""
        if not self._is_rule_enabled("ts.no-any-cast"):
            return []
        findings: List[JSFinding] = []
        pattern = re.compile(r"\bas\s+any\b")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(_make_finding(
                    file_path=file_path,
                    line_number=idx,
                    rule_id="ts.no-any-cast",
                    category=JSRuleCategory.CODE_SMELL,
                    severity=JSSeverity.WARNING,
                    title="Cast to 'any'",
                    description="Casting to 'any' bypasses TypeScript's type checking.",
                    code_snippet=line,
                    fix_suggestion="Cast to a specific type or use 'unknown' with a type guard.",
                ))
        return findings

    def _check_no_non_null_assertion(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """ts.no-non-null-assertion: non-null assertion operator (!.)."""
        if not self._is_rule_enabled("ts.no-non-null-assertion"):
            return []
        findings: List[JSFinding] = []
        pattern = re.compile(r"\w+!\s*[.\[]")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(_make_finding(
                    file_path=file_path,
                    line_number=idx,
                    rule_id="ts.no-non-null-assertion",
                    category=JSRuleCategory.BUG,
                    severity=JSSeverity.INFO,
                    title="Non-null assertion operator used",
                    description=(
                        "The non-null assertion operator (!) tells TypeScript to ignore possible null/undefined. "
                        "If the value is actually null at runtime, this will cause an error."
                    ),
                    code_snippet=line,
                    fix_suggestion="Add a proper null check or restructure to avoid the assertion.",
                ))
        return findings

    def _check_prefer_interface(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """ts.prefer-interface: type alias used for object shape."""
        if not self._is_rule_enabled("ts.prefer-interface"):
            return []
        findings: List[JSFinding] = []
        pattern = re.compile(r"\btype\s+\w+\s*=\s*\{")
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(_make_finding(
                    file_path=file_path,
                    line_number=idx,
                    rule_id="ts.prefer-interface",
                    category=JSRuleCategory.STYLE,
                    severity=JSSeverity.INFO,
                    title="Prefer interface over type alias for object shapes",
                    description=(
                        "Using 'interface' for object shape declarations is preferred over 'type = {...}' "
                        "because interfaces can be extended and merged."
                    ),
                    code_snippet=line,
                    fix_suggestion="Replace 'type X = { ... }' with 'interface X { ... }'.",
                ))
        return findings

    def _check_no_implicit_any(self, file_path: str, lines: List[str]) -> List[JSFinding]:
        """ts.no-implicit-any: function parameters without type annotations."""
        if not self._is_rule_enabled("ts.no-implicit-any"):
            return []
        findings: List[JSFinding] = []
        # Match function declarations that have parameters but no ':' type annotation
        # Simplified heuristic: function keyword + name + params where params contain
        # identifiers without a following colon
        func_pattern = re.compile(r"\bfunction\s+\w+\s*\(([^)]*)\)")
        for idx, line in enumerate(lines, start=1):
            match = func_pattern.search(line)
            if match:
                params_str = match.group(1).strip()
                if not params_str:
                    continue
                # If the params string contains identifiers without ':' type hints
                if ":" not in params_str:
                    findings.append(_make_finding(
                        file_path=file_path,
                        line_number=idx,
                        rule_id="ts.no-implicit-any",
                        category=JSRuleCategory.CODE_SMELL,
                        severity=JSSeverity.WARNING,
                        title="Function parameters missing type annotations",
                        description=(
                            "Function parameters have no type annotations, resulting in implicit 'any' types."
                        ),
                        code_snippet=line,
                        fix_suggestion="Add explicit type annotations to all function parameters.",
                    ))
        return findings
