"""
JavaScript/TypeScript quality analysis via ESLint.

Orchestrates the project's own ESLint rather than reimplementing its rule
set. Complements the existing regex-based JSAnalyzer/TSAnalyzer (which need
no project configuration and run identically everywhere) with the project's
own configured rules, including any custom or plugin rules ESLint's config
enables that a generic regex scan cannot know about.

Requires the target project to already have an ESLint configuration
(eslint.config.{js,mjs,cjs,ts} for ESLint >=9's flat config, or a legacy
.eslintrc.* / "eslintConfig" in package.json); scanning a project with none
skips gracefully rather than letting ESLint's own "no config found" error
look like a scan failure.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Bragi.Quality.languages.common.tool_models import (
    ToolCategory,
    ToolFinding,
    ToolReport,
    ToolSeverity,
)
from Asgard.Bragi.Quality.languages.common.tool_runner import resolve_node_tool, run_tool
from Asgard.Bragi.Quality.languages.node.models.node_toolchain_models import NodeLintConfig

_FLAT_CONFIG_NAMES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts")
_LEGACY_CONFIG_NAMES = (
    ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml", ".eslintrc",
)

_SEVERITY_MAP = {2: ToolSeverity.ERROR, 1: ToolSeverity.WARNING}

_SECURITY_RULE_MARKERS = ("security/", "no-eval", "no-implied-eval", "detect-", "no-new-func")

INSTALL_HINT = "Install Node.js (which provides npx) from https://nodejs.org, then add eslint as a devDependency."


class NodeEslintAnalyzer:
    """Runs ESLint over a Node project and normalises the output."""

    def __init__(self, config: Optional[NodeLintConfig] = None) -> None:
        self._config = config or NodeLintConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> ToolReport:
        path = Path(scan_path) if scan_path else self._config.scan_path
        path = path.resolve()
        start = datetime.now()

        report = ToolReport(scan_path=str(path), language="node", tool="eslint")

        if not self._has_eslint_config(path):
            report.tools_unavailable.append(
                f"No ESLint configuration found under {path} "
                "(eslint.config.js or .eslintrc.*); skipping ESLint."
            )
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        argv = resolve_node_tool("eslint", path, INSTALL_HINT)
        cmd = argv + ["--format", "json"] + list(self._config.extra_args) + ["."]

        result = run_tool(cmd, cwd=path, timeout=self._config.timeout_seconds)

        if result.timed_out:
            report.tools_unavailable.append(f"eslint timed out after {self._config.timeout_seconds}s")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        if not result.stdout.strip():
            detail = (result.stderr or "produced no output").strip().splitlines()[-1:] or ["produced no output"]
            report.tools_unavailable.append(f"eslint failed to run: {detail[0]}")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        try:
            file_results = json.loads(result.stdout)
        except json.JSONDecodeError:
            report.tools_unavailable.append("eslint produced unparseable output")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        if not isinstance(file_results, list):
            report.tools_unavailable.append(
                "eslint produced an invalid JSON envelope (expected a list of file results)"
            )
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        diagnostics_found = 0
        incomplete_output = False
        report.files_analyzed = 0
        for file_result in file_results:
            if not isinstance(file_result, dict):
                incomplete_output = True
                continue
            file_path = file_result.get("filePath", "")
            messages = file_result.get("messages")
            if not isinstance(file_path, str) or not file_path or not isinstance(messages, list):
                incomplete_output = True
                continue
            report.files_analyzed += 1
            try:
                relative_path = str(Path(file_path).resolve().relative_to(path))
            except ValueError:
                relative_path = file_path
            for message in messages:
                if not self._is_supported_message(message):
                    incomplete_output = True
                    continue
                finding = self._finding_from_message(message, relative_path)
                if finding is not None:
                    report.add_finding(finding)
                    diagnostics_found += 1
                    if self._config.max_findings and report.total_findings >= self._config.max_findings:
                        report.tool_failed = True
                        report.tools_unavailable.append("eslint finding limit reached; remaining diagnostics are unverified")
                        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
                        return report
                else:
                    incomplete_output = True

        if incomplete_output:
            report.tools_unavailable.append("eslint output contained malformed or unsupported diagnostic entries")
            report.tool_failed = True

        if result.returncode not in (0, 1):
            report.tools_unavailable.append(f"eslint failed to complete (exit {result.returncode})")
            report.tool_failed = True
        elif result.returncode == 1 and diagnostics_found == 0:
            report.tools_unavailable.append("eslint exited nonzero without reporting any diagnostics")
            report.tool_failed = True
        elif result.returncode == 0 and report.error_count:
            report.tools_unavailable.append("eslint reported error diagnostics despite a successful exit status")
            report.tool_failed = True

        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
        return report

    @staticmethod
    def _has_eslint_config(path: Path) -> bool:
        for name in _FLAT_CONFIG_NAMES + _LEGACY_CONFIG_NAMES:
            if (path / name).is_file():
                return True
        package_json = path / "package.json"
        if package_json.is_file():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            return "eslintConfig" in data
        return False

    @staticmethod
    def _is_supported_message(message: object) -> bool:
        if not isinstance(message, dict):
            return False
        severity = message.get("severity")
        if isinstance(severity, bool) or not isinstance(severity, int) or severity not in _SEVERITY_MAP:
            return False
        if not isinstance(message.get("message"), str):
            return False
        if message.get("ruleId") is not None and not isinstance(message.get("ruleId"), str):
            return False
        for field in ("line", "column"):
            value = message.get(field, 0)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                return False
        return True

    @staticmethod
    def _finding_from_message(message: dict, relative_path: str) -> Optional[ToolFinding]:
        severity = _SEVERITY_MAP.get(message.get("severity"))
        if severity is None:
            return None

        rule_id = message.get("ruleId") or "eslint.parse-error"
        category = ToolCategory.SECURITY if any(
            marker in rule_id for marker in _SECURITY_RULE_MARKERS
        ) else ToolCategory.STYLE

        return ToolFinding(
            file_path=relative_path,
            line_number=message.get("line", 0) or 0,
            column=message.get("column", 0) or 0,
            rule_id=rule_id,
            category=category,
            severity=severity,
            title=(message.get("message") or "")[:200],
            description=message.get("message", ""),
            code_snippet="",
            fix_suggestion="",
            tool="eslint",
        )
