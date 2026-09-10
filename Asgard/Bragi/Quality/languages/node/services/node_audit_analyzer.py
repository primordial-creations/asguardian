"""
Node dependency vulnerability scanning via npm audit.

npm audit cross-references package-lock.json against the npm/GitHub
Advisory Database. Unlike cargo-audit, npm ships with Node itself, so the
only "not available" case is Node/npm missing entirely; a missing
package-lock.json (or no network access to the registry) is reported as a
skipped, non-fatal condition instead.
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
from Asgard.Bragi.Quality.languages.common.tool_runner import (
    require_executable,
    run_tool,
)
from Asgard.Bragi.Quality.languages.node.models.node_toolchain_models import NodeAuditConfig

_NPM_SEVERITY_TO_TOOL = {
    "critical": ToolSeverity.ERROR,
    "high": ToolSeverity.ERROR,
    "moderate": ToolSeverity.WARNING,
    "low": ToolSeverity.INFO,
    "info": ToolSeverity.INFO,
}

INSTALL_HINT = "Install Node.js (which bundles npm) from https://nodejs.org"


class NodeAuditAnalyzer:
    """Runs npm audit against a Node project and normalises the output."""

    def __init__(self, config: Optional[NodeAuditConfig] = None) -> None:
        self._config = config or NodeAuditConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> ToolReport:
        path = Path(scan_path) if scan_path else self._config.scan_path
        path = path.resolve()
        start = datetime.now()

        report = ToolReport(scan_path=str(path), language="node", tool="npm-audit")

        npm_bin = require_executable("npm", path, INSTALL_HINT)

        if not (path / "package.json").is_file():
            report.tools_unavailable.append(f"No package.json found under {path}; skipping npm audit.")
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        result = run_tool([npm_bin, "audit", "--json"], cwd=path, timeout=self._config.timeout_seconds)

        if result.timed_out:
            report.tools_unavailable.append(f"npm audit timed out after {self._config.timeout_seconds}s")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        if not result.stdout.strip():
            detail = (result.stderr or "produced no output").strip().splitlines()[-1:] or ["produced no output"]
            report.tools_unavailable.append(f"npm audit failed to run: {detail[0]}")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            report.tools_unavailable.append("npm audit produced unparseable output")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        if not isinstance(payload, dict):
            report.tools_unavailable.append("npm audit produced an invalid JSON envelope (expected an object)")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        has_top_level_error = "error" in payload
        top_level_error = payload.get("error")
        vulnerabilities = payload.get("vulnerabilities", {} if has_top_level_error else None)
        if not isinstance(vulnerabilities, dict):
            report.tools_unavailable.append("npm audit output did not contain a valid vulnerabilities object")
            report.tool_failed = True
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        incomplete_output = False
        report.files_analyzed = 1 if "vulnerabilities" in payload else 0
        for pkg_name, entry in vulnerabilities.items():
            if not isinstance(pkg_name, str) or not pkg_name or not self._is_supported_entry(entry):
                incomplete_output = True
                continue
            finding = self._finding_from_entry(pkg_name, entry)
            if finding is not None:
                report.add_finding(finding)
                if self._config.max_findings and report.total_findings >= self._config.max_findings:
                    report.tool_failed = True
                    report.tools_unavailable.append("npm audit finding limit reached; remaining vulnerabilities are unverified")
                    break
            else:
                incomplete_output = True

        if incomplete_output:
            report.tools_unavailable.append("npm audit output contained malformed or unsupported vulnerability entries")
            report.tool_failed = True

        # npm may include vulnerability data alongside a top-level execution
        # error. Keep those findings, but never represent the partial result as
        # a complete scan.
        if has_top_level_error:
            if isinstance(top_level_error, dict):
                summary = top_level_error.get("summary") or top_level_error.get("code") or "unknown error"
            else:
                summary = str(top_level_error or "unknown error")
            report.tools_unavailable.append(f"npm audit could not complete: {summary}")
            report.tool_failed = True

        if result.returncode not in (0, 1):
            report.tools_unavailable.append(f"npm audit failed to complete (exit {result.returncode})")
            report.tool_failed = True
        elif result.returncode == 1 and not vulnerabilities and not has_top_level_error:
            report.tools_unavailable.append("npm audit exited nonzero without reporting any vulnerabilities")
            report.tool_failed = True

        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
        return report

    @staticmethod
    def _is_supported_entry(entry: object) -> bool:
        if not isinstance(entry, dict):
            return False
        if str(entry.get("severity", "")).lower() not in _NPM_SEVERITY_TO_TOOL:
            return False
        via = entry.get("via")
        if not isinstance(via, list):
            return False
        if any(not isinstance(advisory, (str, dict)) for advisory in via):
            return False
        for advisory in via:
            if isinstance(advisory, dict) and any(
                key in advisory and not isinstance(advisory[key], str)
                for key in ("title", "url")
            ):
                return False
        fix_available = entry.get("fixAvailable", False)
        if not isinstance(fix_available, (bool, dict)):
            return False
        if isinstance(fix_available, dict) and any(
            key in fix_available and not isinstance(fix_available[key], str)
            for key in ("name", "version")
        ):
            return False
        return True

    @staticmethod
    def _finding_from_entry(pkg_name: str, entry: dict) -> Optional[ToolFinding]:
        severity_str = str(entry.get("severity", "")).lower()
        severity = _NPM_SEVERITY_TO_TOOL.get(severity_str)
        if severity is None:
            return None

        advisories = [v for v in (entry.get("via") or []) if isinstance(v, dict)]
        titles = [a.get("title", "") for a in advisories if a.get("title")]
        urls = [a.get("url", "") for a in advisories if a.get("url")]

        description = "; ".join(titles) if titles else (
            f"{pkg_name} is a transitive dependency of a vulnerable package"
        )
        fix_available = entry.get("fixAvailable")
        fix_suggestion = ""
        if fix_available is True:
            fix_suggestion = "Fix available: run npm audit fix."
        elif isinstance(fix_available, dict):
            fix_name = fix_available.get("name", pkg_name)
            fix_version = fix_available.get("version", "")
            fix_suggestion = f"Fix available: upgrade {fix_name} to {fix_version} (npm audit fix)."
        elif urls:
            fix_suggestion = f"See {urls[0]}"

        return ToolFinding(
            file_path="package.json",
            line_number=0,
            column=0,
            rule_id=f"npm-audit::{pkg_name}",
            category=ToolCategory.DEPENDENCY,
            severity=severity,
            title=f"{pkg_name}: {severity_str} severity vulnerability",
            description=description,
            code_snippet="",
            fix_suggestion=fix_suggestion,
            tool="npm-audit",
        )
