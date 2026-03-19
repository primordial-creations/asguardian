"""
CLI Command Handlers

This module re-exports all handler functions from the original CLI.
The handlers contain the actual business logic for each command.

In a future refactoring, these can be broken into separate modules:
- quality_handlers.py
- security_handlers.py
- performance_handlers.py
- etc.
"""

# Re-export all handler functions from the original CLI module
# This allows the new modular structure to work while preserving the existing functionality

# Import the original CLI module to access its functions
# We use a lazy import pattern to avoid circular imports
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# These will be populated when first called
_handlers_loaded = False
_handler_functions = {}


def _load_handlers():
    """Load handlers from the original CLI on first use."""
    global _handlers_loaded, _handler_functions
    if _handlers_loaded:
        return

    # Import from the original CLI location (will be moved here eventually)
    # For now, we inline the handler implementations to avoid circular imports
    _handlers_loaded = True


def _create_handler(func_name: str, analysis_func):
    """Create a handler wrapper that loads the original function on first call."""
    def wrapper(*args, **kwargs):
        return analysis_func(*args, **kwargs)
    wrapper.__name__ = func_name
    return wrapper


# Import directly from the original module's namespace
# These functions will be available after the original cli.py is modified
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Architecture import ArchitectureAnalyzer, ArchitectureConfig
from Asgard.Heimdall.CodeFix.services.codefix_service import CodeFixService
from Asgard.Heimdall.Coverage import CoverageAnalyzer, CoverageConfig
from Asgard.Heimdall.Dependencies import DependencyAnalyzer, DependencyConfig
from Asgard.Heimdall.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat
from Asgard.Heimdall.Dependencies.services.sbom_generator import SBOMGenerator
from Asgard.Heimdall.Init.linter_initializer import LinterInitializer
from Asgard.Heimdall.OOP import OOPAnalyzer, OOPConfig
from Asgard.Heimdall.Performance import StaticPerformanceService, PerformanceScanConfig
from Asgard.Heimdall.Quality.utilities.file_utils import discover_files
from Asgard.Heimdall.Security import StaticSecurityService, SecurityScanConfig
from Asgard.MCP.models.mcp_models import MCPServerConfig
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer


class _TeeStream:
    """Writes to two streams simultaneously (terminal + buffer)."""

    def __init__(self, primary, secondary: io.StringIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        self._primary.write(s)
        self._secondary.write(s)
        return len(s)

    def flush(self) -> None:
        self._primary.flush()

    def reconfigure(self, **kwargs) -> None:
        if hasattr(self._primary, "reconfigure"):
            self._primary.reconfigure(**kwargs)

    def fileno(self) -> int:
        return self._primary.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._primary, "encoding", "utf-8")


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI terminal escape sequences from text."""
    return _ANSI_ESCAPE.sub("", text)


def _report_file_path(suffix: str = ".html") -> Path:
    return Path.cwd() / f"heimdall_report_{uuid.uuid4().hex[:8]}{suffix}"


def open_output_in_browser(content: str, title: str = "Heimdall Report") -> None:
    """Wrap report content in an HTML page and open it in the default browser."""
    is_html = content.lstrip().startswith(("<!DOCTYPE", "<html", "<!doctype"))
    if is_html:
        html = content
    else:
        clean = _strip_ansi(content)
        escaped = (
            clean
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{
      background: #1e1e1e;
      color: #d4d4d4;
      font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
      margin: 0;
      padding: 24px;
      font-size: 13px;
      line-height: 1.6;
    }}
    h1 {{
      color: #569cd6;
      font-size: 1.1em;
      margin: 0 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid #333;
    }}
    pre {{
      white-space: pre-wrap;
      word-wrap: break-word;
      margin: 0;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <pre>{escaped}</pre>
</body>
</html>"""

    report_path = _report_file_path()
    report_path.write_text(html, encoding="utf-8")

    # Use the platform-native open command — more reliable than webbrowser.open()
    # for snap/flatpak Firefox installations that ignore the webbrowser module.
    if sys.platform == "darwin":
        opener = "open"
    elif sys.platform == "win32":
        opener = None  # use os.startfile
    else:
        opener = shutil.which("xdg-open")

    opened = False
    if opener:
        try:
            subprocess.Popen(
                [opener, str(report_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            opened = True
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            os.startfile(str(report_path))
            opened = True
        except Exception:
            pass

    if not opened:
        webbrowser.open(str(report_path))

    print(f"Report saved: {report_path}", file=sys.__stdout__)

from Asgard.Heimdall.Quality.models.analysis_models import (
    AnalysisConfig,
    AnalysisResult,
    DEFAULT_EXTENSION_THRESHOLDS,
    SeverityLevel,
)
from Asgard.Heimdall.Quality.models.complexity_models import (
    ComplexityConfig,
    ComplexityResult,
    ComplexitySeverity,
)
from Asgard.Heimdall.Quality.models.duplication_models import (
    DuplicationConfig,
    DuplicationResult,
    DuplicationSeverity,
)
from Asgard.Heimdall.Quality.models.smell_models import (
    SmellConfig,
    SmellSeverity,
    SmellThresholds,
)
from Asgard.Heimdall.Quality.models.debt_models import (
    DebtConfig,
    DebtSeverity,
    TimeHorizon,
)
from Asgard.Heimdall.Quality.models.maintainability_models import (
    MaintainabilityConfig,
    MaintainabilityLevel,
    LanguageProfile,
)
from Asgard.Heimdall.Quality.services.file_length_analyzer import FileAnalyzer
from Asgard.Heimdall.Quality.services.complexity_analyzer import ComplexityAnalyzer
from Asgard.Heimdall.Quality.services.duplication_detector import DuplicationDetector
from Asgard.Heimdall.Quality.services.code_smell_detector import CodeSmellDetector
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer
from Asgard.Heimdall.Quality.services.maintainability_analyzer import MaintainabilityAnalyzer

from Asgard.Heimdall.Quality.models.env_fallback_models import (
    EnvFallbackConfig,
    EnvFallbackSeverity,
)
from Asgard.Heimdall.Quality.services.env_fallback_scanner import EnvFallbackScanner

from Asgard.Heimdall.Quality.models.lazy_import_models import (
    LazyImportConfig,
    LazyImportSeverity,
)
from Asgard.Heimdall.Quality.services.lazy_import_scanner import LazyImportScanner

from Asgard.Heimdall.Quality.models.library_usage_models import (
    ForbiddenImportConfig,
    ForbiddenImportSeverity,
)
from Asgard.Heimdall.Quality.services.library_usage_scanner import LibraryUsageScanner

from Asgard.Heimdall.Quality.models.datetime_models import (
    DatetimeConfig,
)
from Asgard.Heimdall.Quality.services.datetime_scanner import DatetimeScanner

from Asgard.Heimdall.Quality.models.typing_models import (
    TypingConfig,
)
from Asgard.Heimdall.Quality.services.typing_scanner import TypingScanner

from Asgard.Heimdall.Quality.models.type_check_models import (
    TypeCheckConfig,
)
from Asgard.Heimdall.Quality.services.type_checker import TypeChecker

from Asgard.Heimdall.Quality.models.thread_safety_models import (
    ThreadSafetyConfig,
    ThreadSafetySeverity,
)
from Asgard.Heimdall.Quality.services.thread_safety_scanner import ThreadSafetyScanner

from Asgard.Heimdall.Quality.models.race_condition_models import (
    RaceConditionConfig,
    RaceConditionSeverity,
)
from Asgard.Heimdall.Quality.services.race_condition_scanner import RaceConditionScanner

from Asgard.Heimdall.Quality.models.daemon_thread_models import (
    DaemonThreadConfig,
    DaemonThreadSeverity,
)
from Asgard.Heimdall.Quality.services.daemon_thread_scanner import DaemonThreadScanner

from Asgard.Heimdall.Quality.models.future_leak_models import (
    FutureLeakConfig,
    FutureLeakSeverity,
)
from Asgard.Heimdall.Quality.services.future_leak_scanner import FutureLeakScanner

from Asgard.Heimdall.Quality.models.blocking_async_models import (
    BlockingAsyncConfig,
    BlockingAsyncSeverity,
)
from Asgard.Heimdall.Quality.services.blocking_async_scanner import BlockingAsyncScanner

from Asgard.Heimdall.Quality.models.resource_cleanup_models import (
    ResourceCleanupConfig,
    ResourceCleanupSeverity,
)
from Asgard.Heimdall.Quality.services.resource_cleanup_scanner import ResourceCleanupScanner

from Asgard.Heimdall.Quality.models.error_handling_models import (
    ErrorHandlingConfig,
    ErrorHandlingSeverity,
)
from Asgard.Heimdall.Quality.services.error_handling_scanner import ErrorHandlingScanner

from Asgard.Heimdall.Security.models.config_secrets_models import (
    ConfigSecretsConfig,
    ConfigSecretSeverity,
)
from Asgard.Heimdall.Security.services.config_secrets_scanner import ConfigSecretsScanner

from Asgard.Heimdall.Security.models.security_models import (
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService

from Asgard.Heimdall.Performance.models.performance_models import (
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services.static_performance_service import StaticPerformanceService

from Asgard.Heimdall.OOP.models.oop_models import OOPConfig
from Asgard.Heimdall.OOP.services.oop_analyzer import OOPAnalyzer

from Asgard.Heimdall.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Heimdall.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Heimdall.Dependencies.services.graph_builder import GraphBuilder

from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureConfig
from Asgard.Heimdall.Architecture.services.architecture_analyzer import ArchitectureAnalyzer

from Asgard.Heimdall.Coverage.models.coverage_models import CoverageConfig
from Asgard.Heimdall.Coverage.services.coverage_analyzer import CoverageAnalyzer

from Asgard.Heimdall.Quality.models.syntax_models import (
    LinterType,
    SyntaxConfig,
    SyntaxSeverity,
)
from Asgard.Heimdall.Quality.services.syntax_checker import SyntaxChecker

from Asgard.Heimdall.Dependencies.models.requirements_models import (
    RequirementsConfig,
)
from Asgard.Heimdall.Dependencies.services.requirements_checker import RequirementsChecker

from Asgard.Heimdall.Dependencies.models.license_models import LicenseConfig
from Asgard.Heimdall.Dependencies.services.license_checker import LicenseChecker

from Asgard.Baseline.baseline_manager import BaselineManager

from Asgard.Heimdall.cli.common import SEVERITY_MARKERS

from Asgard.Heimdall.Quality.models.documentation_models import DocumentationConfig
from Asgard.Heimdall.Quality.services.documentation_scanner import DocumentationScanner
from Asgard.Heimdall.Quality.models.naming_models import NamingConfig
from Asgard.Heimdall.Quality.services.naming_convention_scanner import NamingConventionScanner
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig, ReviewPriority
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Compliance.models.compliance_models import ComplianceConfig
from Asgard.Heimdall.Security.Compliance.services.compliance_reporter import ComplianceReporter
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService as _StaticSecuritySvc
from Asgard.Heimdall.Quality.models.debt_models import DebtConfig
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer as _TechDebtAnalyzer
from Asgard.Heimdall.Ratings.models.ratings_models import RatingsConfig
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.Profiles.services.profile_manager import ProfileManager
from Asgard.Heimdall.Profiles.models.profile_models import QualityProfile, RuleConfig
from Asgard.Heimdall.common.new_code_period import (
    NewCodePeriodConfig,
    NewCodePeriodDetector,
    NewCodePeriodType,
)
from Asgard.Reporting.History.services.history_store import HistoryStore
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot, MetricSnapshot

import traceback as _traceback
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintConfig
from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Quality.BugDetection.models.bug_models import BugDetectionConfig
from Asgard.Heimdall.Quality.BugDetection.services.bug_detector import BugDetector
from Asgard.Heimdall.Quality.languages.javascript.models.js_models import JSAnalysisConfig
from Asgard.Heimdall.Quality.languages.javascript.services.js_analyzer import JSAnalyzer
from Asgard.Heimdall.Quality.languages.typescript.services.ts_analyzer import TSAnalyzer
from Asgard.Heimdall.Quality.languages.shell.models.shell_models import ShellAnalysisConfig
from Asgard.Heimdall.Quality.languages.shell.services.shell_analyzer import ShellAnalyzer
from Asgard.Heimdall.Issues.models.issue_models import IssueFilter, IssueStatus, IssueSeverity, IssueType, IssuesSummary, TrackedIssue
from Asgard.Heimdall.Issues.services.issue_tracker import IssueTracker
from Asgard.Heimdall.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat
from Asgard.Heimdall.Dependencies.services.sbom_generator import SBOMGenerator
from Asgard.Heimdall.CodeFix.services.codefix_service import CodeFixService
from Asgard.MCP.models.mcp_models import MCPServerConfig
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer
from Asgard.Dashboard.models.dashboard_models import DashboardConfig
from Asgard.Dashboard.services.dashboard_server import DashboardServer


_HTML_SEVERITY_COLORS = {
    "critical": "#c0392b",
    "severe": "#e67e22",
    "moderate": "#f1c40f",
    "warning": "#3498db",
}


def _generate_quality_html_report(result) -> str:
    """Generate a self-contained HTML report for the file length quality analysis."""
    compliance_color = "#27ae60" if result.compliance_rate >= 90 else "#e67e22" if result.compliance_rate >= 70 else "#c0392b"
    status_text = "PASS" if not result.has_violations else "VIOLATIONS FOUND"
    status_color = "#27ae60" if not result.has_violations else "#c0392b"

    violation_rows = []
    by_severity = result.get_violations_by_severity()
    for severity in [SeverityLevel.CRITICAL.value, SeverityLevel.SEVERE.value,
                     SeverityLevel.MODERATE.value, SeverityLevel.WARNING.value]:
        violations = by_severity[severity]
        for v in violations:
            badge_color = _HTML_SEVERITY_COLORS.get(severity, "#7f8c8d")
            violation_rows.append(
                f"<tr>"
                f"<td>{v.relative_path}</td>"
                f"<td>{v.line_count}</td>"
                f"<td>{v.threshold}</td>"
                f"<td>+{v.lines_over}</td>"
                f"<td><span style=\"background:{badge_color};color:#fff;padding:2px 8px;"
                f"border-radius:4px;font-size:0.8em;\">{severity.upper()}</span></td>"
                f"</tr>"
            )

    violations_table = ""
    if violation_rows:
        violations_table = (
            "<h2>Files Exceeding Threshold</h2>"
            "<table>"
            "<thead><tr><th>File</th><th>Lines</th><th>Threshold</th><th>Over</th><th>Severity</th></tr></thead>"
            "<tbody>" + "".join(violation_rows) + "</tbody>"
            "</table>"
        )
    else:
        violations_table = "<p class=\"pass-msg\">All files are within the threshold.</p>"

    html = (
        "<!DOCTYPE html>"
        "<html lang=\"en\">"
        "<head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        "<title>Heimdall Code Quality Report</title>"
        "<style>"
        "body{font-family:sans-serif;margin:0;padding:0;background:#f5f6fa;color:#2c3e50;}"
        "header{background:#2c3e50;color:#fff;padding:20px 32px;}"
        "header h1{margin:0;font-size:1.5em;}"
        "header p{margin:4px 0 0;opacity:0.7;font-size:0.9em;}"
        "main{padding:24px 32px;}"
        ".summary{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;}"
        ".card{background:#fff;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,.08);min-width:140px;}"
        ".card .label{font-size:0.75em;text-transform:uppercase;letter-spacing:.05em;color:#7f8c8d;}"
        ".card .value{font-size:2em;font-weight:700;margin-top:4px;}"
        ".status-badge{display:inline-block;padding:6px 16px;border-radius:6px;color:#fff;"
        f"background:{status_color};font-weight:700;font-size:1em;margin-bottom:24px;}}"
        "table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;"
        "box-shadow:0 1px 4px rgba(0,0,0,.08);overflow:hidden;}"
        "th{background:#2c3e50;color:#fff;text-align:left;padding:10px 14px;font-size:0.85em;}"
        "td{padding:9px 14px;border-bottom:1px solid #ecf0f1;font-size:0.85em;word-break:break-all;}"
        "tr:last-child td{border-bottom:none;}"
        "tr:nth-child(even) td{background:#f9fafb;}"
        ".pass-msg{color:#27ae60;font-weight:600;font-size:1.1em;}"
        "h2{margin:0 0 12px;font-size:1.1em;color:#2c3e50;}"
        "</style>"
        "</head>"
        "<body>"
        "<header>"
        "<h1>Heimdall Code Quality Report &mdash; File Length Analysis</h1>"
        f"<p>Scan path: {result.scan_path} &nbsp;|&nbsp; "
        f"Generated: {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; "
        f"Duration: {result.scan_duration_seconds:.2f}s</p>"
        "</header>"
        "<main>"
        f"<div class=\"status-badge\">{status_text}</div>"
        "<div class=\"summary\">"
        "<div class=\"card\"><div class=\"label\">Files Scanned</div>"
        f"<div class=\"value\">{result.total_files_scanned}</div></div>"
        "<div class=\"card\"><div class=\"label\">Violations</div>"
        f"<div class=\"value\" style=\"color:{status_color}\">{result.files_exceeding_threshold}</div></div>"
        "<div class=\"card\"><div class=\"label\">Compliance Rate</div>"
        f"<div class=\"value\" style=\"color:{compliance_color}\">{result.compliance_rate:.1f}%</div></div>"
        "</div>"
        f"{violations_table}"
        "</main>"
        "</body>"
        "</html>"
    )
    return html


def run_quality_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the file length quality analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    # Check for dry-run mode
    if getattr(args, 'dry_run', False):
        files = list(discover_files(scan_path, args.exclude if args.exclude else []))
        print(f"\nDry run: Would analyze {len(files)} files")
        for f in sorted(files)[:20]:
            print(f"  {f}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        return 0

    # Build extension thresholds
    ext_thresholds = dict(DEFAULT_EXTENSION_THRESHOLDS)
    if hasattr(args, 'ext_threshold') and args.ext_threshold:
        for et in args.ext_threshold:
            if ":" in et:
                parts = et.split(":")
                ext = parts[0] if parts[0].startswith(".") else f".{parts[0]}"
                try:
                    ext_thresholds[ext] = int(parts[1])
                except ValueError:
                    pass

    # Build exclude patterns
    exclude_patterns = list(args.exclude) if args.exclude else []

    # Build configuration
    config = AnalysisConfig(
        scan_path=scan_path,
        default_threshold=args.threshold if args.threshold else 300,
        extension_thresholds=ext_thresholds,
        include_extensions=args.extensions if hasattr(args, 'extensions') and args.extensions else None,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        # Format and print results
        if args.format == "json":
            output = {
                "scan_path": result.scan_path,
                "thresholds": {"default": result.default_threshold, "by_extension": result.extension_thresholds},
                "scanned_at": result.scanned_at.isoformat(),
                "scan_duration_seconds": result.scan_duration_seconds,
                "summary": {
                    "total_files_scanned": result.total_files_scanned,
                    "files_exceeding_threshold": result.files_exceeding_threshold,
                    "compliance_rate": round(result.compliance_rate, 2),
                },
                "violations": [
                    {"file_path": v.relative_path, "line_count": v.line_count, "threshold": v.threshold,
                     "lines_over": v.lines_over, "severity": v.severity, "extension": v.file_extension}
                    for v in result.violations
                ],
            }
            print(json.dumps(output, indent=2))
        elif args.format == "html":
            print(_generate_quality_html_report(result))
        else:
            # Text format
            lines = [
                "", "=" * 70, "  HEIMDALL CODE QUALITY REPORT", "  File Length Analysis", "=" * 70, "",
                f"  Scan Path:    {result.scan_path}",
                f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:     {result.scan_duration_seconds:.2f}s", ""
            ]

            if result.has_violations:
                lines.extend(["-" * 70, "  FILES EXCEEDING THRESHOLD", "-" * 70, ""])
                by_severity = result.get_violations_by_severity()
                for severity in [SeverityLevel.CRITICAL.value, SeverityLevel.SEVERE.value,
                                 SeverityLevel.MODERATE.value, SeverityLevel.WARNING.value]:
                    violations = by_severity[severity]
                    if violations:
                        lines.append(f"  {SEVERITY_MARKERS[severity]}")
                        lines.append("")
                        for v in violations:
                            lines.append(f"    {v.relative_path}")
                            lines.append(f"      {v.line_count} lines (+{v.lines_over} over {v.threshold}-line threshold)")
                            lines.append("")
            else:
                lines.extend(["  All files are within the threshold. Nice work!", ""])

            lines.extend(["-" * 70, "  SUMMARY", "-" * 70, "",
                          f"  Files Scanned:          {result.total_files_scanned}",
                          f"  Files Over Threshold:   {result.files_exceeding_threshold}",
                          f"  Compliance Rate:        {result.compliance_rate:.1f}%", ""])

            if result.has_violations:
                sorted_violations = sorted(result.violations, key=lambda x: x.line_count, reverse=True)
                lines.extend(["-" * 70, "  VIOLATIONS (longest first)", "  " + "-" * 47, ""])
                for v in sorted_violations:
                    lines.append(f"  {v.relative_path}   {v.line_count} lines  (limit: {v.threshold}, over by {v.lines_over})")
                lines.append("")

            lines.extend(["=" * 70, ""])
            print("\n".join(lines))

        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_complexity_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the complexity analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = ComplexityConfig(
        scan_path=scan_path,
        cyclomatic_threshold=args.cyclomatic_threshold,
        cognitive_threshold=args.cognitive_threshold,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_duplication_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the duplication analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DuplicationConfig(
        scan_path=scan_path,
        min_block_size=getattr(args, 'min_lines', 6),
        similarity_threshold=getattr(args, 'min_tokens', 50) / 100.0,
        output_format=args.format,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        verbose=verbose,
    )

    try:
        detector = DuplicationDetector(config)
        result = detector.analyze()
        report = detector.generate_report(result, args.format)
        print(report)
        return 1 if result.has_duplicates else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_smell_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the code smell analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    thresholds = SmellThresholds(
        long_method_lines=getattr(args, 'long_method_lines', 50),
        large_class_methods=getattr(args, 'large_class_methods', 20),
        long_parameter_list=getattr(args, 'long_parameter_list', 5),
    )

    config = SmellConfig(
        scan_path=scan_path,
        smell_categories=getattr(args, 'categories', None),
        severity_filter=SmellSeverity(args.severity),
        thresholds=thresholds,
        output_format=args.format,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        verbose=verbose,
    )

    try:
        detector = CodeSmellDetector(config)
        result = detector.analyze(scan_path)
        report = detector.generate_report(result, args.format)
        print(report)
        return 1 if result.has_smells else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_debt_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the technical debt analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DebtConfig(
        scan_path=scan_path,
        debt_types=getattr(args, 'debt_types', None),
        time_horizon=TimeHorizon(getattr(args, 'time_horizon', 'sprint')),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = TechnicalDebtAnalyzer(config)
        result = analyzer.analyze(scan_path)
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_debt else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_maintainability_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the maintainability index analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = MaintainabilityConfig(
        scan_path=scan_path,
        include_halstead=not getattr(args, 'no_halstead', False),
        include_comments=not getattr(args, 'no_comments', False),
        language_profile=LanguageProfile(getattr(args, 'language', 'python')),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = MaintainabilityAnalyzer(config)
        result = analyzer.analyze(scan_path)
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_env_fallback_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the environment variable fallback analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": EnvFallbackSeverity.LOW,
        "medium": EnvFallbackSeverity.MEDIUM,
        "high": EnvFallbackSeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, EnvFallbackSeverity.LOW)

    config = EnvFallbackConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = EnvFallbackScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_lazy_imports_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the lazy imports analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": LazyImportSeverity.LOW,
        "medium": LazyImportSeverity.MEDIUM,
        "high": LazyImportSeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, LazyImportSeverity.LOW)

    config = LazyImportConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = LazyImportScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_security_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    """Execute security analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "info": SecuritySeverity.INFO,
        "low": SecuritySeverity.LOW,
        "medium": SecuritySeverity.MEDIUM,
        "high": SecuritySeverity.HIGH,
        "critical": SecuritySeverity.CRITICAL,
    }
    min_severity = severity_map.get(args.severity, SecuritySeverity.LOW)

    config = SecurityScanConfig(
        scan_path=scan_path,
        scan_type=analysis_type,
        min_severity=min_severity,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        service = StaticSecurityService(config)
        result = service.analyze(scan_path)
        report = service.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_performance_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    """Execute performance analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "info": PerformanceSeverity.INFO,
        "low": PerformanceSeverity.LOW,
        "medium": PerformanceSeverity.MEDIUM,
        "high": PerformanceSeverity.HIGH,
        "critical": PerformanceSeverity.CRITICAL,
    }
    min_severity = severity_map.get(args.severity, PerformanceSeverity.LOW)

    config = PerformanceScanConfig(
        scan_path=scan_path,
        scan_type=analysis_type,
        min_severity=min_severity,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        service = StaticPerformanceService(config)
        result = service.analyze(scan_path)
        report = service.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_oop_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute OOP metrics analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = OOPConfig(
        scan_path=scan_path,
        cbo_threshold=args.cbo_threshold,
        lcom_threshold=args.lcom_threshold,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = OOPAnalyzer(config)
        result = analyzer.analyze(scan_path)
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_deps_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    """Execute dependency analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DependencyConfig(
        scan_path=scan_path,
        max_depth=getattr(args, 'max_depth', 10),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = DependencyAnalyzer(config)

        if analysis_type == "cycles":
            result = analyzer.find_cycles(scan_path)
            report = analyzer.generate_cycles_report(result, args.format)
            print(report)
            return 1 if result else 0
        elif analysis_type == "modularity":
            result = analyzer.analyze_modularity(scan_path)
            report = analyzer.generate_modularity_report(result, args.format)
            print(report)
            return 1 if result.has_issues else 0
        else:
            result = analyzer.analyze(scan_path)
            direction = getattr(args, "direction", "LR")
            report = analyzer.generate_report(result, args.format, direction)
            print(report)
            return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_deps_export(args: argparse.Namespace, verbose: bool = False) -> int:
    """Export dependency graph in dot, json, or mermaid format."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DependencyConfig(
        scan_path=scan_path,
        exclude_patterns=exclude_patterns,
    )

    try:
        builder = GraphBuilder(config)
        export_format = getattr(args, "export_format", "mermaid")
        output_path = Path(args.output) if getattr(args, "output", None) else None
        direction = getattr(args, "direction", "LR")

        if export_format in ("dot", "graphviz"):
            result = builder.export_dot(scan_path, output_path, direction)
        elif export_format == "json":
            result = json.dumps(builder.export_json(scan_path), indent=2)
            if output_path:
                output_path.write_text(result)
        elif export_format == "mermaid":
            result = builder.export_mermaid(scan_path, output_path, direction)
        else:
            print(f"Unknown export format: {export_format}")
            return 1

        if output_path:
            print(f"Exported {export_format} graph to {output_path}")
        else:
            print(result)

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_arch_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    """Execute architecture analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    config = ArchitectureConfig(scan_path=scan_path)
    if args.exclude:
        config.exclude_patterns = list(set(config.exclude_patterns) | set(args.exclude))

    try:
        analyzer = ArchitectureAnalyzer(config)

        validate_solid = not getattr(args, 'no_solid', False) if analysis_type == "all" else analysis_type == "solid"
        analyze_layers = not getattr(args, 'no_layers', False) if analysis_type == "all" else analysis_type == "layers"
        detect_patterns = not getattr(args, 'no_patterns', False) if analysis_type == "all" else analysis_type == "patterns"
        analyze_hexagonal = getattr(args, 'hexagonal', False) if analysis_type == "all" else analysis_type == "hexagonal"

        result = analyzer.analyze(
            scan_path,
            validate_solid=validate_solid,
            analyze_layers=analyze_layers,
            detect_patterns=detect_patterns,
            analyze_hexagonal=analyze_hexagonal,
        )
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if not result.is_healthy else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_coverage_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    """Execute coverage analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    test_path = None
    if hasattr(args, 'test_path') and args.test_path:
        test_path = Path(args.test_path).resolve()

    config = CoverageConfig(
        scan_path=scan_path,
        include_private=getattr(args, 'include_private', False),
        exclude_patterns=exclude_patterns,
    )

    try:
        analyzer = CoverageAnalyzer(config)

        if analysis_type == "gaps":
            gaps = analyzer.get_gaps(scan_path)
            if args.format == "json":
                print(json.dumps([{
                    "method": g.method.full_name,
                    "file": g.file_path,
                    "severity": g.severity.value,
                    "message": g.message,
                } for g in gaps], indent=2))
            else:
                print(f"\nCoverage Gaps Found: {len(gaps)}")
                for g in gaps[:20]:
                    print(f"  [{g.severity.value.upper()}] {g.method.full_name}")
                if len(gaps) > 20:
                    print(f"  ... and {len(gaps) - 20} more")
            return 1 if gaps else 0
        elif analysis_type == "suggestions":
            max_suggestions = getattr(args, 'max_suggestions', 10)
            suggestions = analyzer.get_suggestions(scan_path, max_suggestions)
            if args.format == "json":
                print(json.dumps([{
                    "test_name": s.test_name,
                    "method": s.method.full_name,
                    "priority": s.priority.value,
                    "description": s.description,
                } for s in suggestions], indent=2))
            else:
                print(f"\nTest Suggestions ({len(suggestions)}):")
                for s in suggestions:
                    print(f"  [{s.priority.value.upper()}] {s.test_name}")
                    print(f"    {s.description}")
            return 0
        else:
            result = analyzer.analyze(scan_path, test_path)
            report = analyzer.generate_report(result, args.format)
            print(report)
            return 1 if result.has_gaps else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_syntax_analysis(args: argparse.Namespace, verbose: bool = False, fix_mode: bool = False) -> int:
    """Execute syntax checking analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".mypy_cache", ".pytest_cache", "*.egg-info", "build", "dist",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    linter_map = {
        "ruff": LinterType.RUFF,
        "flake8": LinterType.FLAKE8,
        "pylint": LinterType.PYLINT,
        "mypy": LinterType.MYPY,
    }
    linters = [linter_map[l] for l in args.linters if l in linter_map]

    severity_map = {
        "error": SyntaxSeverity.ERROR,
        "warning": SyntaxSeverity.WARNING,
        "info": SyntaxSeverity.INFO,
        "style": SyntaxSeverity.STYLE,
    }
    min_severity = severity_map.get(args.severity, SyntaxSeverity.WARNING)

    config = SyntaxConfig(
        scan_path=scan_path,
        include_extensions=args.extensions,
        exclude_patterns=exclude_patterns,
        linters=linters,
        min_severity=min_severity,
        include_style=getattr(args, 'include_style', False),
        fix_mode=fix_mode,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = SyntaxChecker(config)

        if fix_mode:
            result, fixes_applied = checker.fix()
            report = checker.generate_report(result, args.format)
            print(report)
            if fixes_applied > 0:
                print(f"\nApplied {fixes_applied} auto-fixes.")
            return 1 if result.has_errors else 0
        else:
            result = checker.analyze()
            report = checker.generate_report(result, args.format)
            print(report)
            return 1 if result.has_errors else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_requirements_analysis(args: argparse.Namespace, verbose: bool = False, sync_mode: bool = False) -> int:
    """Execute requirements checking analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
        "*.egg-info",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    check_unused = getattr(args, "check_unused", True)
    if getattr(args, "no_check_unused", False):
        check_unused = False

    config = RequirementsConfig(
        scan_path=scan_path,
        requirements_files=getattr(args, "requirements_files", ["requirements.txt"]),
        exclude_patterns=exclude_patterns,
        check_unused=check_unused,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = RequirementsChecker(config)

        if sync_mode:
            result, changes = checker.sync(
                target_file=getattr(args, 'target_file', 'requirements.txt')
            )
            report = checker.generate_report(result, args.format)
            print(report)
            if changes:
                print(f"\nSync complete: {len(changes)} changes made")
            return 1 if result.has_issues else 0
        else:
            result = checker.analyze()
            report = checker.generate_report(result, args.format)
            print(report)
            return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_licenses_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute license checking analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    config = LicenseConfig(
        scan_path=scan_path,
        requirements_files=getattr(args, "requirements_files", ["requirements.txt"]),
        allowed_licenses=getattr(args, "allowed", None),
        prohibited_licenses=getattr(args, "prohibited", None),
        warning_licenses=getattr(args, "warn", None),
        use_cache=not getattr(args, "no_cache", False),
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = LicenseChecker(config)
        result = checker.analyze()
        report = checker.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_logic_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "audit") -> int:
    """Execute logic analysis (duplication, patterns, complexity)."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    issues_found = False

    if analysis_type in ("duplication", "audit"):
        # Run duplication detection
        config = DuplicationConfig(
            scan_path=scan_path,
            min_block_size=getattr(args, 'min_similarity', 0.8) * 10,
            similarity_threshold=getattr(args, 'min_similarity', 0.8),
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            detector = DuplicationDetector(config)
            result = detector.analyze()
            if analysis_type == "duplication":
                report = detector.generate_report(result, args.format)
                print(report)
            else:
                print(f"\n[Duplication] Found {result.total_clone_families} clone families")
            if result.has_duplicates:
                issues_found = True
        except Exception as e:
            print(f"Duplication analysis error: {e}")

    if analysis_type in ("patterns", "audit"):
        # Run code smell detection
        config = SmellConfig(
            scan_path=scan_path,
            severity_filter=SmellSeverity(args.severity),
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            detector = CodeSmellDetector(config)
            result = detector.analyze(scan_path)
            if analysis_type == "patterns":
                report = detector.generate_report(result, args.format)
                print(report)
            else:
                print(f"[Patterns] Found {result.total_smells} code smells")
            if result.has_smells:
                issues_found = True
        except Exception as e:
            print(f"Pattern analysis error: {e}")

    if analysis_type in ("complexity", "audit"):
        # Run complexity analysis
        config = ComplexityConfig(
            scan_path=scan_path,
            cyclomatic_threshold=10,
            cognitive_threshold=15,
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            analyzer = ComplexityAnalyzer(config)
            result = analyzer.analyze()
            if analysis_type == "complexity":
                report = analyzer.generate_report(result, args.format)
                print(report)
            else:
                print(f"[Complexity] Found {result.total_violations} violations")
            if result.has_violations:
                issues_found = True
        except Exception as e:
            print(f"Complexity analysis error: {e}")

    return 1 if issues_found else 0


def run_forbidden_imports_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the forbidden imports analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = ForbiddenImportConfig(
        scan_path=scan_path,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = LibraryUsageScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_datetime_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the datetime usage analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DatetimeConfig(
        scan_path=scan_path,
        check_utcnow=not getattr(args, 'no_check_utcnow', False),
        check_now_no_tz=not getattr(args, 'no_check_now', False),
        check_today_no_tz=not getattr(args, 'no_check_today', False),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = DatetimeScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_typing_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the typing coverage analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = TypingConfig(
        scan_path=scan_path,
        minimum_coverage=getattr(args, 'threshold', 80.0),
        exclude_private=not getattr(args, 'include_private', False),
        exclude_dunder=not getattr(args, 'include_dunder', False),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = TypingScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_type_check_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute static type checking (mypy by default, pyright optionally)."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    # Extra user-supplied exclude patterns are appended to the defaults
    user_excludes = list(args.exclude) if args.exclude else []

    # Handle errors-only flag
    include_warnings = True
    severity_filter = getattr(args, "severity", None)
    if getattr(args, "errors_only", False):
        severity_filter = "error"
        include_warnings = False

    default_config = TypeCheckConfig()
    exclude_patterns = default_config.exclude_patterns + user_excludes

    config = TypeCheckConfig(
        engine=getattr(args, "engine", "mypy"),
        type_checking_mode=getattr(args, "mode", "basic"),
        python_version=getattr(args, "python_version", ""),
        python_platform=getattr(args, "python_platform", ""),
        venv_path=getattr(args, "venv_path", ""),
        include_tests=getattr(args, "include_tests", False),
        include_warnings=include_warnings,
        severity_filter=severity_filter,
        category_filter=getattr(args, "category", None),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
        npx_path=getattr(args, "npx_path", "npx"),
        subprocess_timeout=getattr(args, "timeout", 300),
    )

    try:
        checker = TypeChecker(config)
        result = checker.analyze(scan_path)
        report = checker.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_thread_safety_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the thread safety analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "medium": ThreadSafetySeverity.MEDIUM,
        "high": ThreadSafetySeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, ThreadSafetySeverity.MEDIUM)

    config = ThreadSafetyConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = ThreadSafetyScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_race_conditions_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the race condition analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = RaceConditionConfig(
        scan_path=scan_path,
        severity_filter=RaceConditionSeverity.HIGH,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = RaceConditionScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_daemon_threads_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the daemon thread analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": DaemonThreadSeverity.LOW,
        "medium": DaemonThreadSeverity.MEDIUM,
    }
    severity_filter = severity_map.get(args.severity, DaemonThreadSeverity.LOW)

    config = DaemonThreadConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = DaemonThreadScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_resource_cleanup_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the resource cleanup analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": ResourceCleanupSeverity.LOW,
        "medium": ResourceCleanupSeverity.MEDIUM,
        "high": ResourceCleanupSeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, ResourceCleanupSeverity.MEDIUM)

    config = ResourceCleanupConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = ResourceCleanupScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_error_handling_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the error handling coverage analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": ErrorHandlingSeverity.LOW,
        "medium": ErrorHandlingSeverity.MEDIUM,
        "high": ErrorHandlingSeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, ErrorHandlingSeverity.MEDIUM)

    config = ErrorHandlingConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = ErrorHandlingScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_config_secrets_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the config secrets analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": ConfigSecretSeverity.LOW,
        "medium": ConfigSecretSeverity.MEDIUM,
        "high": ConfigSecretSeverity.HIGH,
        "critical": ConfigSecretSeverity.CRITICAL,
    }
    severity_filter = severity_map.get(args.severity, ConfigSecretSeverity.MEDIUM)

    config = ConfigSecretsConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        entropy_threshold=getattr(args, "entropy_threshold", 3.5),
        entropy_min_length=getattr(args, "entropy_min_length", 20),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = ConfigSecretsScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_findings else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_future_leaks_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the future/promise leak analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": FutureLeakSeverity.LOW,
        "medium": FutureLeakSeverity.MEDIUM,
        "high": FutureLeakSeverity.HIGH,
    }
    severity_filter = severity_map.get(args.severity, FutureLeakSeverity.MEDIUM)

    config = FutureLeakConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = FutureLeakScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_blocking_async_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute the blocking-in-async analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "low": BlockingAsyncSeverity.LOW,
        "medium": BlockingAsyncSeverity.MEDIUM,
        "high": BlockingAsyncSeverity.HIGH,
    }
    severity_filter = severity_map.get(getattr(args, "severity", "high"), BlockingAsyncSeverity.HIGH)

    config = BlockingAsyncConfig(
        scan_path=scan_path,
        severity_filter=severity_filter,
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        scanner = BlockingAsyncScanner(config)
        result = scanner.analyze(scan_path)
        report = scanner.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_baseline_command(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute a baseline management subcommand (show, list, clean, remove)."""
    project_path = Path(args.path).resolve()
    baseline_file = getattr(args, "baseline_file", ".asgard-baseline.json")
    output_format = getattr(args, "format", "text")
    baseline_subcommand = getattr(args, "baseline_command", None)

    if baseline_subcommand is None:
        print("Error: Please specify a baseline command: show, list, clean, remove")
        return 1

    try:
        manager = BaselineManager(project_path=project_path, baseline_file=baseline_file)

        if baseline_subcommand == "show":
            report = manager.generate_report(output_format)
            print(report)
            return 0

        elif baseline_subcommand == "list":
            violation_type = getattr(args, "type", None)
            file_pattern = getattr(args, "file", None)
            entries = manager.list_entries(
                violation_type=violation_type,
                file_path=file_pattern,
            )
            if output_format == "json":
                print(json.dumps(
                    [
                        {
                            "violation_id": e.violation_id,
                            "file_path": e.file_path,
                            "line_number": e.line_number,
                            "violation_type": e.violation_type,
                            "message": e.message,
                            "reason": e.reason,
                            "expired": e.is_expired,
                        }
                        for e in entries
                    ],
                    indent=2,
                ))
            else:
                if not entries:
                    print("No baseline entries found.")
                else:
                    print(f"\nBaseline Entries ({len(entries)}):")
                    print("-" * 60)
                    for entry in entries:
                        status = "[EXPIRED]" if entry.is_expired else ""
                        print(
                            f"  {entry.file_path}:{entry.line_number}"
                            f" [{entry.violation_type}] {status}"
                        )
                        if entry.reason:
                            print(f"    Reason: {entry.reason}")
                        print(f"    ID: {entry.violation_id}")
            return 0

        elif baseline_subcommand == "clean":
            removed = manager.clean_expired()
            print(f"Removed {removed} expired baseline entries.")
            return 0

        elif baseline_subcommand == "remove":
            violation_id = getattr(args, "id", None)
            if not violation_id:
                print("Error: --id is required for the remove subcommand.")
                return 1
            removed = manager.remove_entry(violation_id)
            if removed:
                print(f"Removed baseline entry: {violation_id}")
                return 0
            else:
                print(f"No baseline entry found with ID: {violation_id}")
                return 1

        else:
            print(f"Unknown baseline command: {baseline_subcommand}")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_documentation_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute documentation coverage and comment density analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    config = DocumentationConfig(
        scan_path=scan_path,
        min_comment_density=getattr(args, "min_comment_density", 10.0),
        min_api_coverage=getattr(args, "min_api_coverage", 70.0),
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
            "migrations", "test_*", "*_test.py",
        ],
        output_format=args.format,
    )

    try:
        scanner = DocumentationScanner(config)
        report = scanner.scan(scan_path)

        if args.format == "json":
            print(scanner.generate_report(report, "json"))
        elif args.format in ("markdown", "md"):
            print(scanner.generate_report(report, "markdown"))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL DOCUMENTATION COVERAGE REPORT",
                "=" * 70,
                "",
                f"  Scan Path:          {report.scan_path}",
                f"  Scanned At:         {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:           {report.scan_duration_seconds:.2f}s",
                "",
                f"  Files Analyzed:     {report.total_files}",
                f"  Comment Density:    {report.overall_comment_density:.1f}%",
                f"  API Coverage:       {report.overall_api_coverage:.1f}%",
                f"  Total Public APIs:  {report.total_public_apis}",
                f"  Undocumented APIs:  {report.undocumented_apis}",
                "",
            ]
            problem_files = [
                f for f in report.file_results
                if f.comment_density < config.min_comment_density or f.public_api_coverage < config.min_api_coverage
            ]
            if problem_files:
                lines.extend(["-" * 70, "  FILES BELOW THRESHOLDS", "-" * 70, ""])
                for f in sorted(problem_files, key=lambda x: x.public_api_coverage):
                    lines.append(f"  {f.path}")
                    lines.append(
                        f"    Density: {f.comment_density:.1f}%  "
                        f"Coverage: {f.public_api_coverage:.1f}%  "
                        f"Undocumented: {f.undocumented_count}"
                    )
                    lines.append("")
            else:
                lines.extend(["  All files meet documentation thresholds.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.undocumented_apis > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_naming_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute naming convention enforcement analysis."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    config = NamingConfig(
        scan_path=scan_path,
        check_functions=not getattr(args, "no_functions", False),
        check_classes=not getattr(args, "no_classes", False),
        check_variables=not getattr(args, "no_variables", False),
        check_constants=not getattr(args, "no_constants", False),
        allow_list=list(getattr(args, "allow_list", [])),
        include_tests=getattr(args, "include_tests", True),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist", "migrations",
        ],
        output_format=args.format,
    )

    try:
        scanner = NamingConventionScanner(config)
        report = scanner.scan(scan_path)

        if args.format == "json":
            print(scanner.generate_report(report, "json"))
        elif args.format in ("markdown", "md"):
            print(scanner.generate_report(report, "markdown"))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL NAMING CONVENTION REPORT",
                "=" * 70,
                "",
                f"  Scan Path:               {report.scan_path}",
                f"  Scanned At:              {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:                {report.scan_duration_seconds:.2f}s",
                "",
                f"  Total Violations:        {report.total_violations}",
                f"  Files With Violations:   {report.files_with_violations}",
                "",
            ]
            if report.violations_by_type:
                lines.append("  Violations by Type:")
                for etype, count in sorted(report.violations_by_type.items()):
                    lines.append(f"    {etype}: {count}")
                lines.append("")
            if report.has_violations:
                lines.extend(["-" * 70, "  VIOLATIONS", "-" * 70, ""])
                for file_path, violations in sorted(report.file_results.items()):
                    if not violations:
                        continue
                    lines.append(f"  {file_path}")
                    for v in sorted(violations, key=lambda x: x.line_number):
                        lines.append(f"    Line {v.line_number:4d}: [{v.element_type}] {v.element_name}")
                        if verbose:
                            lines.append(f"             {v.description}")
                    lines.append("")
            else:
                lines.extend(["  No naming violations found.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.has_violations else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_hotspots_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute security hotspot detection."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    priority_str = getattr(args, "priority", "low")
    try:
        min_priority = ReviewPriority(priority_str)
    except ValueError:
        min_priority = ReviewPriority.LOW

    config = HotspotConfig(
        scan_path=scan_path,
        min_priority=min_priority,
        include_tests=getattr(args, "include_tests", True),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
        ],
        output_format=getattr(args, "format", "text"),
    )

    try:
        detector = HotspotDetector(config)
        report = detector.scan(scan_path)

        if args.format == "json":
            output = {
                "scan_info": {
                    "scan_path": report.scan_path,
                    "scanned_at": report.scanned_at.isoformat(),
                    "duration_seconds": report.scan_duration_seconds,
                },
                "summary": {
                    "total_hotspots": report.total_hotspots,
                    "high_priority": report.high_priority_count,
                    "medium_priority": report.medium_priority_count,
                    "low_priority": report.low_priority_count,
                    "by_category": report.hotspots_by_category,
                },
                "hotspots": [
                    {
                        "file_path": h.file_path,
                        "line_number": h.line_number,
                        "category": h.category,
                        "review_priority": h.review_priority,
                        "title": h.title,
                        "description": h.description,
                        "code_snippet": h.code_snippet,
                        "review_guidance": h.review_guidance,
                        "owasp_category": h.owasp_category,
                        "cwe_id": h.cwe_id,
                    }
                    for h in report.hotspots
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL SECURITY HOTSPOT REPORT",
                "=" * 70,
                "",
                f"  Scan Path:      {report.scan_path}",
                f"  Scanned At:     {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:       {report.scan_duration_seconds:.2f}s",
                "",
                f"  Total Hotspots: {report.total_hotspots}",
                f"  [HIGH]:         {report.high_priority_count}",
                f"  [MEDIUM]:       {report.medium_priority_count}",
                f"  [LOW]:          {report.low_priority_count}",
                "",
            ]
            if report.hotspots:
                lines.extend(["-" * 70, "  HOTSPOTS", "-" * 70, ""])
                for h in report.hotspots:
                    priority_label = str(h.review_priority).upper()
                    lines.append(f"  [{priority_label}] {h.title}")
                    lines.append(f"  File: {h.file_path}:{h.line_number}")
                    if h.owasp_category:
                        lines.append(f"  OWASP: {h.owasp_category}  CWE: {h.cwe_id or 'N/A'}")
                    if verbose:
                        lines.append(f"  Description: {h.description}")
                        lines.append(f"  Guidance: {h.review_guidance}")
                    if h.code_snippet:
                        lines.append(f"  Code: {h.code_snippet}")
                    lines.append("")
            else:
                lines.extend(["  No security hotspots detected.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.high_priority_count > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_compliance_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute OWASP/CWE compliance reporting."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    include_owasp = not getattr(args, "no_owasp", False)
    include_cwe = not getattr(args, "no_cwe", False)

    config = ComplianceConfig(
        include_owasp=include_owasp,
        include_cwe=include_cwe,
    )

    try:
        # Run security scan to get findings
        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        # Run hotspot detection
        hotspot_detector = HotspotDetector()
        hotspot_report = hotspot_detector.scan(scan_path)

        reporter = ComplianceReporter(config)

        if args.format == "json":
            output = {}
            if include_owasp:
                owasp = reporter.generate_owasp_report(security_report, hotspot_report, str(scan_path))
                output["owasp"] = {
                    "version": owasp.owasp_version,
                    "overall_grade": owasp.overall_grade,
                    "total_findings_mapped": owasp.total_findings_mapped,
                    "categories": {
                        cat_id: {
                            "name": cat.category_name,
                            "grade": cat.grade,
                            "findings": cat.findings_count,
                            "critical": cat.critical_count,
                            "high": cat.high_count,
                            "medium": cat.medium_count,
                            "low": cat.low_count,
                        }
                        for cat_id, cat in sorted(owasp.categories.items())
                    },
                }
            if include_cwe:
                cwe = reporter.generate_cwe_report(security_report, hotspot_report, str(scan_path))
                output["cwe"] = {
                    "version": cwe.cwe_version,
                    "overall_grade": cwe.overall_grade,
                    "top_25": {
                        cwe_id: {
                            "name": entry.category_name,
                            "grade": entry.grade,
                            "findings": entry.findings_count,
                        }
                        for cwe_id, entry in sorted(cwe.top_25_coverage.items())
                        if entry.findings_count > 0
                    },
                }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL COMPLIANCE REPORT",
                "=" * 70,
                "",
                f"  Scan Path: {scan_path}",
                "",
            ]

            if include_owasp:
                owasp = reporter.generate_owasp_report(security_report, hotspot_report, str(scan_path))
                lines.extend([
                    f"  OWASP Top 10 (2021) - Overall Grade: {owasp.overall_grade}",
                    "-" * 70,
                ])
                for cat_id, cat in sorted(owasp.categories.items()):
                    marker = "  " if cat.findings_count == 0 else "! "
                    lines.append(
                        f"  {marker}{cat_id} [{cat.grade}] {cat.category_name} "
                        f"({cat.findings_count} finding(s))"
                    )
                lines.append("")

            if include_cwe:
                cwe = reporter.generate_cwe_report(security_report, hotspot_report, str(scan_path))
                lines.extend([
                    f"  CWE Top 25 (2024) - Overall Grade: {cwe.overall_grade}",
                    "-" * 70,
                ])
                flagged = [
                    (cwe_id, entry)
                    for cwe_id, entry in sorted(cwe.top_25_coverage.items())
                    if entry.findings_count > 0
                ]
                if flagged:
                    for cwe_id, entry in flagged:
                        lines.append(
                            f"  ! {cwe_id} [{entry.grade}] {entry.category_name} "
                            f"({entry.findings_count} finding(s))"
                        )
                else:
                    lines.append("  No CWE Top 25 findings detected.")
                lines.append("")

            lines.append("=" * 70)
            print("\n".join(lines))

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_ratings_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute A-E quality ratings calculation."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        # Gather debt report for maintainability rating
        debt_config = DebtConfig(scan_path=scan_path)
        debt_analyzer = _TechDebtAnalyzer(debt_config)
        debt_report = debt_analyzer.analyze(scan_path)

        # Gather security report for security rating
        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        config = RatingsConfig(scan_path=scan_path)
        calculator = RatingsCalculator(config)
        ratings = calculator.calculate_from_reports(
            scan_path=str(scan_path),
            debt_report=debt_report,
            security_report=security_report,
        )

        if getattr(args, "history", False):
            try:
                _save_ratings_to_history(str(scan_path), ratings)
            except Exception as hist_err:
                print(f"Warning: could not save to history: {hist_err}")

        if args.format == "json":
            output = {
                "scan_path": ratings.scan_path,
                "scanned_at": ratings.scanned_at.isoformat(),
                "overall_rating": ratings.overall_rating,
                "maintainability": {
                    "rating": ratings.maintainability.rating,
                    "score": ratings.maintainability.score,
                    "rationale": ratings.maintainability.rationale,
                    "issues_count": ratings.maintainability.issues_count,
                },
                "reliability": {
                    "rating": ratings.reliability.rating,
                    "score": ratings.reliability.score,
                    "rationale": ratings.reliability.rationale,
                    "issues_count": ratings.reliability.issues_count,
                },
                "security": {
                    "rating": ratings.security.rating,
                    "score": ratings.security.score,
                    "rationale": ratings.security.rationale,
                    "issues_count": ratings.security.issues_count,
                },
            }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL QUALITY RATINGS REPORT",
                "=" * 70,
                "",
                f"  Scan Path:           {ratings.scan_path}",
                f"  Calculated At:       {ratings.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"  Overall Rating:      [{ratings.overall_rating}]",
                "",
                "-" * 70,
                f"  Maintainability:     [{ratings.maintainability.rating}]",
                f"    {ratings.maintainability.rationale}",
                f"  Reliability:         [{ratings.reliability.rating}]",
                f"    {ratings.reliability.rationale}",
                f"  Security:            [{ratings.security.rating}]",
                f"    {ratings.security.rationale}",
                "",
                "=" * 70,
            ]
            print("\n".join(lines))

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def _save_ratings_to_history(project_path: str, ratings) -> None:
    """Persist ratings result to the local history store."""
    store = HistoryStore()
    metrics = [
        MetricSnapshot(metric_name="maintainability_score", value=float(ratings.maintainability.score), unit="score"),
        MetricSnapshot(metric_name="reliability_score", value=float(ratings.reliability.score), unit="score"),
        MetricSnapshot(metric_name="security_score", value=float(ratings.security.score), unit="score"),
    ]
    rating_values = {
        "maintainability": str(ratings.maintainability.rating),
        "reliability": str(ratings.reliability.rating),
        "security": str(ratings.security.rating),
    }
    snapshot = AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        project_path=project_path,
        scan_timestamp=datetime.now(),
        metrics=metrics,
        ratings=rating_values,
    )
    store.save_snapshot(snapshot)


def _save_gate_to_history(project_path: str, gate_result, ratings) -> None:
    """Persist gate evaluation result to the local history store."""
    store = HistoryStore()
    metrics: List[MetricSnapshot] = []
    if ratings is not None:
        metrics.extend([
            MetricSnapshot(metric_name="maintainability_score", value=float(ratings.maintainability.score), unit="score"),
            MetricSnapshot(metric_name="reliability_score", value=float(ratings.reliability.score), unit="score"),
            MetricSnapshot(metric_name="security_score", value=float(ratings.security.score), unit="score"),
        ])
    gate_status = str(getattr(gate_result, "status", "unknown")).lower()
    rating_values = {}
    if ratings is not None:
        rating_values = {
            "maintainability": str(ratings.maintainability.rating),
            "reliability": str(ratings.reliability.rating),
            "security": str(ratings.security.rating),
        }
    snapshot = AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        project_path=project_path,
        scan_timestamp=datetime.now(),
        metrics=metrics,
        quality_gate_status=gate_status,
        ratings=rating_values,
    )
    store.save_snapshot(snapshot)


def run_gate_evaluation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute quality gate evaluation."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        # Gather all reports needed
        debt_config = DebtConfig(scan_path=scan_path)
        debt_analyzer = _TechDebtAnalyzer(debt_config)
        debt_report = debt_analyzer.analyze(scan_path)

        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        # Calculate ratings
        ratings_calculator = RatingsCalculator()
        ratings = ratings_calculator.calculate_from_reports(
            scan_path=str(scan_path),
            debt_report=debt_report,
            security_report=security_report,
        )

        # Documentation report
        doc_scanner = DocumentationScanner()
        doc_report = doc_scanner.scan(scan_path)

        # Evaluate gate
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        result = evaluator.evaluate_from_reports(
            gate,
            ratings=ratings,
            documentation_report=doc_report,
            security_report=security_report,
            debt_report=debt_report,
            scan_path=str(scan_path),
        )

        if args.format == "json":
            output = {
                "gate_name": result.gate_name,
                "status": result.status,
                "summary": result.summary,
                "scan_path": result.scan_path,
                "evaluated_at": result.evaluated_at.isoformat(),
                "condition_results": [
                    {
                        "metric": r.condition.metric,
                        "operator": r.condition.operator,
                        "threshold": r.condition.threshold,
                        "actual_value": r.actual_value,
                        "passed": r.passed,
                        "error_on_fail": r.condition.error_on_fail,
                        "message": r.message,
                    }
                    for r in result.condition_results
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            status_str = str(result.status).upper()
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL QUALITY GATE EVALUATION",
                "=" * 70,
                "",
                f"  Gate:         {result.gate_name}",
                f"  Scan Path:    {result.scan_path}",
                f"  Evaluated At: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"  Status:       [{status_str}]",
                f"  Summary:      {result.summary}",
                "",
                "-" * 70,
                "  CONDITION RESULTS",
                "-" * 70,
                "",
            ]
            for r in result.condition_results:
                pass_marker = "[PASS]" if r.passed else ("[FAIL]" if r.condition.error_on_fail else "[WARN]")
                lines.append(f"  {pass_marker} {r.message}")
                if verbose and r.condition.description:
                    lines.append(f"         {r.condition.description}")
            lines.extend(["", "=" * 70])
            print("\n".join(lines))

        if getattr(args, "history", False):
            try:
                _save_gate_to_history(str(scan_path), result, ratings)
            except Exception as hist_err:
                print(f"Warning: could not save to history: {hist_err}")

        # Exit with non-zero if gate failed
        return 1 if str(result.status).lower() == "failed" else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


__all__ = [
    "run_quality_analysis",
    "run_complexity_analysis",
    "run_duplication_analysis",
    "run_smell_analysis",
    "run_debt_analysis",
    "run_maintainability_analysis",
    "run_env_fallback_analysis",
    "run_lazy_imports_analysis",
    "run_security_analysis",
    "run_performance_analysis",
    "run_oop_analysis",
    "run_deps_analysis",
    "run_deps_export",
    "run_arch_analysis",
    "run_coverage_analysis",
    "run_syntax_analysis",
    "run_requirements_analysis",
    "run_licenses_analysis",
    "run_logic_analysis",
    "run_thread_safety_analysis",
    "run_race_conditions_analysis",
    "run_daemon_threads_analysis",
    "run_future_leaks_analysis",
    "run_blocking_async_analysis",
    "run_resource_cleanup_analysis",
    "run_error_handling_analysis",
    "run_config_secrets_analysis",
    "run_baseline_command",
    "run_init_linter",
    "run_documentation_analysis",
    "run_naming_analysis",
    "run_hotspots_analysis",
    "run_compliance_analysis",
    "run_ratings_analysis",
    "run_gate_evaluation",
    "run_profiles_command",
    "run_history_command",
    "run_new_code_detect",
]


def run_init_linter(args, verbose: bool = False) -> int:
    """Handle the init-linter command.

    Generates linting configuration files for a project based on
    GAIA coding standards. Also generates VSCode settings and checks
    for required tools/extensions.
    """
    project_path = Path(args.path).resolve()

    if not project_path.exists():
        print(f"Error: path '{args.path}' does not exist.")
        return 1

    if not project_path.is_dir():
        print(f"Error: path '{args.path}' is not a directory.")
        return 1

    project_name = getattr(args, "project_name", None)
    project_type = getattr(args, "project_type", None)
    force = getattr(args, "force", False)

    initializer = LinterInitializer(
        project_path=project_path,
        project_name=project_name,
        force=force,
    )

    # Resolve actual project type for tool checking
    if project_type == "python":
        is_python, is_typescript = True, False
    elif project_type == "typescript":
        is_python, is_typescript = False, True
    elif project_type == "both":
        is_python, is_typescript = True, True
    else:
        is_python, is_typescript = initializer.detect_project_type()

    if verbose:
        detection_parts = []
        if is_python:
            detection_parts.append("Python")
        if is_typescript:
            detection_parts.append("TypeScript/JavaScript")
        detected = ", ".join(detection_parts) if detection_parts else "none"
        print(f"Project path: {project_path}")
        print(f"Project name: {initializer.project_name}")
        print(f"Detected type: {detected}")
        if project_type:
            print(f"Forced type:   {project_type}")
        print()

    # Generate config files
    results = initializer.init_all(project_type=project_type)

    print(f"Initializing linter configs in: {project_path}")
    print()

    print("  Config files:")
    for filename, status in results:
        print(f"    {filename:.<40s} {status}")

    # Check CLI tools
    print()
    print("  CLI tools:")
    tool_results = initializer.check_tools(is_python, is_typescript)
    missing_tools = []
    for tool in tool_results:
        marker = "[OK]" if tool["installed"] else "[MISSING]"
        print(f"    {marker:10s} {tool['name']:.<30s} {tool['purpose']}")
        if not tool["installed"]:
            missing_tools.append(tool)

    # Check VSCode extensions
    print()
    print("  VSCode extensions:")
    ext_results = initializer.check_vscode_extensions(is_python, is_typescript)
    missing_extensions = []
    if ext_results:
        for ext in ext_results:
            marker = "[OK]" if ext["installed"] else "[MISSING]"
            print(f"    {marker:10s} {ext['extension_id']}")
            if not ext["installed"]:
                missing_extensions.append(ext)
    else:
        print("    (could not detect VSCode - extension check skipped)")

    # Emit warnings for missing tools
    if missing_tools or missing_extensions:
        print()
        print("  " + "=" * 60)
        print("  WARNING: Missing dependencies detected")
        print("  " + "=" * 60)

        if missing_tools:
            print()
            print("  Install missing CLI tools:")
            for tool in missing_tools:
                print(f"    $ {tool['install']}")

        if missing_extensions:
            print()
            print("  Install missing VSCode extensions:")
            install_ids = " ".join(ext["extension_id"] for ext in missing_extensions)
            print(f"    $ code --install-extension {install_ids}")
            print()
            print("  Or in VSCode: open the Extensions panel (Ctrl+Shift+X),")
            print("  search for each extension, and click Install.")
            print("  (VSCode will also prompt you from .vscode/extensions.json)")

        print()
        print("  " + "=" * 60)
    else:
        print()

    print()
    print("Done. Run 'pre-commit install' to activate git hooks (if applicable).")

    return 0


# ---------------------------------------------------------------------------
# Phase 2 Handlers: Profiles, History, New Code Period
# ---------------------------------------------------------------------------


def run_profiles_command(args: argparse.Namespace, verbose: bool = False) -> int:
    """Handle all 'heimdall profiles' subcommands."""
    profiles_command = getattr(args, "profiles_command", None)
    manager = ProfileManager()

    if profiles_command == "list":
        return _run_profiles_list(args, manager, verbose)
    elif profiles_command == "show":
        return _run_profiles_show(args, manager, verbose)
    elif profiles_command == "assign":
        return _run_profiles_assign(args, manager, verbose)
    elif profiles_command == "create":
        return _run_profiles_create(args, manager, verbose)
    else:
        print("Error: Please specify a profiles subcommand.")
        print("  list     List all available quality profiles")
        print("  show     Show details for a specific profile")
        print("  assign   Assign a profile to a project")
        print("  create   Create a new custom profile")
        return 1


def _run_profiles_list(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    """List all available quality profiles."""
    profiles = manager.list_profiles()
    output_format = getattr(args, "format", "text")

    if output_format == "json":
        data = [
            {
                "name": p.name,
                "language": p.language,
                "description": p.description,
                "parent_profile": p.parent_profile,
                "is_builtin": p.is_builtin,
                "rule_count": len(p.rules),
            }
            for p in profiles
        ]
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print("  HEIMDALL QUALITY PROFILES")
    print("=" * 70)
    print("")

    if not profiles:
        print("  No profiles found.")
    else:
        for profile in profiles:
            builtin_marker = "[builtin]" if profile.is_builtin else "[custom]"
            parent_str = f" (inherits: {profile.parent_profile})" if profile.parent_profile else ""
            print(f"  {builtin_marker:10s} {profile.name}{parent_str}")
            if verbose and profile.description:
                print(f"             {profile.description}")
            print(f"             Language: {profile.language}  |  Rules: {len(profile.rules)}")
            print("")

    print("=" * 70)
    return 0


def _run_profiles_show(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    """Show details for a named profile, with inheritance resolved."""
    name = getattr(args, "name", None)
    if not name:
        print("Error: Profile name is required. Usage: heimdall profiles show <name>")
        return 1

    try:
        effective = manager.get_effective_profile(name)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    output_format = getattr(args, "format", "text")

    if output_format == "json":
        data = {
            "name": effective.name,
            "language": effective.language,
            "description": effective.description,
            "parent_profile": effective.parent_profile,
            "is_builtin": effective.is_builtin,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "enabled": r.enabled,
                    "severity": r.severity,
                    "threshold": r.threshold,
                    "extra_config": r.extra_config,
                }
                for r in effective.rules
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  PROFILE: {effective.name}")
    print("=" * 70)
    print("")
    print(f"  Language:   {effective.language}")
    if effective.parent_profile:
        print(f"  Inherits:   {effective.parent_profile}")
    if effective.description:
        print(f"  Description: {effective.description}")
    print("")
    print("  Rules:")
    print(f"  {'Rule ID':<45} {'Severity':<10} {'Threshold'}")
    print("  " + "-" * 65)
    for rule in effective.rules:
        status = "" if rule.enabled else "[disabled] "
        threshold_str = str(rule.threshold) if rule.threshold is not None else ""
        print(f"  {status}{rule.rule_id:<45} {rule.severity:<10} {threshold_str}")
    print("")
    print("=" * 70)
    return 0


def _run_profiles_assign(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    """Assign a quality profile to a project."""
    project_path = getattr(args, "project_path", None)
    profile_name = getattr(args, "profile_name", None)

    if not project_path or not profile_name:
        print("Error: Both project_path and profile_name are required.")
        print("Usage: heimdall profiles assign <project_path> <profile_name>")
        return 1

    try:
        manager.assign_to_project(project_path, profile_name)
        print(f"Profile '{profile_name}' assigned to project: {Path(project_path).resolve()}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1


def _run_profiles_create(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    """Create a new custom quality profile."""
    name = getattr(args, "name", None)
    parent = getattr(args, "parent", None)
    language = getattr(args, "language", "python")
    from_file = getattr(args, "from_file", None)
    description = getattr(args, "description", "")

    if not name:
        print("Error: Profile name is required. Usage: heimdall profiles create <name>")
        return 1

    if from_file:
        try:
            profile = manager.load_profile_from_file(Path(from_file))
            profile_data = QualityProfile(
                name=name,
                language=profile.language,
                description=description or profile.description,
                parent_profile=parent or profile.parent_profile,
                rules=profile.rules,
            )
            manager.save_profile(profile_data)
            print(f"Profile '{name}' created from '{from_file}'.")
            return 0
        except (OSError, ValueError) as exc:
            print(f"Error loading profile from file: {exc}")
            return 1

    new_profile = QualityProfile(
        name=name,
        language=language,
        description=description,
        parent_profile=parent,
        rules=[],
    )

    try:
        manager.save_profile(new_profile)
        print(f"Profile '{name}' created successfully.")
        if parent:
            print(f"  Inherits from: {parent}")
        print(f"  Stored at: ~/.asgard/profiles/")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1


def run_history_command(args: argparse.Namespace, verbose: bool = False) -> int:
    """Handle all 'heimdall history' subcommands."""
    history_command = getattr(args, "history_command", None)

    if history_command == "show":
        return _run_history_show(args, verbose)
    elif history_command == "trends":
        return _run_history_trends(args, verbose)
    else:
        print("Error: Please specify a history subcommand.")
        print("  show    Show analysis history for a project")
        print("  trends  Show metric trends for a project")
        return 1


def _run_history_show(args: argparse.Namespace, verbose: bool) -> int:
    """Show analysis history snapshots for a project."""
    scan_path = Path(getattr(args, "path", ".")).resolve()
    limit = getattr(args, "limit", 10)
    output_format = getattr(args, "format", "text")

    store = HistoryStore()
    snapshots = store.get_snapshots(str(scan_path), limit=limit)

    if output_format == "json":
        data = [
            {
                "snapshot_id": s.snapshot_id,
                "project_path": s.project_path,
                "scan_timestamp": s.scan_timestamp.isoformat(),
                "git_commit": s.git_commit,
                "git_branch": s.git_branch,
                "quality_gate_status": s.quality_gate_status,
                "ratings": s.ratings,
                "metrics": [{"name": m.metric_name, "value": m.value, "unit": m.unit} for m in s.metrics],
            }
            for s in snapshots
        ]
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  ANALYSIS HISTORY: {scan_path}")
    print("=" * 70)
    print("")

    if not snapshots:
        print("  No history recorded for this project.")
        print("  Run 'heimdall ratings ./src --history' to start recording.")
    else:
        for snap in snapshots:
            ts = snap.scan_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            gate = snap.quality_gate_status or "N/A"
            commit_str = f"  commit: {snap.git_commit[:8]}" if snap.git_commit else ""
            print(f"  {ts}  gate: {gate}{commit_str}")
            if verbose:
                for m in snap.metrics:
                    unit_str = f" {m.unit}" if m.unit else ""
                    print(f"    {m.metric_name}: {m.value:.2f}{unit_str}")
            print("")

    print("=" * 70)
    return 0


def _run_history_trends(args: argparse.Namespace, verbose: bool) -> int:
    """Show metric trends for a project."""
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    store = HistoryStore()
    trend_report = store.get_trend_report(str(scan_path))

    if output_format == "json":
        data = {
            "project_path": trend_report.project_path,
            "analysis_count": trend_report.analysis_count,
            "first_analysis": trend_report.first_analysis.isoformat() if trend_report.first_analysis else None,
            "last_analysis": trend_report.last_analysis.isoformat() if trend_report.last_analysis else None,
            "metric_trends": [
                {
                    "metric_name": t.metric_name,
                    "current_value": t.current_value,
                    "previous_value": t.previous_value,
                    "change": t.change,
                    "change_percentage": t.change_percentage,
                    "direction": str(t.direction),
                }
                for t in trend_report.metric_trends
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  METRIC TRENDS: {scan_path}")
    print("=" * 70)
    print("")
    print(f"  Total analyses recorded: {trend_report.analysis_count}")
    if trend_report.first_analysis:
        print(f"  First analysis: {trend_report.first_analysis.strftime('%Y-%m-%d')}")
    if trend_report.last_analysis:
        print(f"  Last analysis:  {trend_report.last_analysis.strftime('%Y-%m-%d')}")
    print("")

    if not trend_report.metric_trends:
        print("  Not enough history to calculate trends (need at least 2 snapshots).")
    else:
        print(f"  {'Metric':<40} {'Direction':<12} {'Change'}")
        print("  " + "-" * 65)
        for trend in trend_report.metric_trends:
            direction_str = str(trend.direction).upper()
            change_str = f"{trend.change_percentage:+.1f}% ({trend.change:+.2f})"
            print(f"  {trend.metric_name:<40} {direction_str:<12} {change_str}")
    print("")
    print("=" * 70)
    return 0


def run_new_code_detect(args: argparse.Namespace, verbose: bool = False) -> int:
    """Handle the 'heimdall new-code detect' subcommand."""
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    since_date_str = getattr(args, "since_date", None)
    since_branch = getattr(args, "since_branch", None)
    since_version = getattr(args, "since_version", None)

    if since_date_str:
        period_type = NewCodePeriodType.SINCE_DATE
        try:
            ref_date = datetime.strptime(since_date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format '{since_date_str}'. Use YYYY-MM-DD.")
            return 1
        config = NewCodePeriodConfig(
            period_type=period_type,
            reference_date=ref_date,
        )
    elif since_branch:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_BRANCH_POINT,
            reference_branch=since_branch,
        )
    elif since_version:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_VERSION,
            reference_version=since_version,
        )
    else:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_LAST_ANALYSIS,
        )

    detector = NewCodePeriodDetector()
    result = detector.detect(str(scan_path), config)

    if output_format == "json":
        data = {
            "period_type": str(result.period_type),
            "reference_point": result.reference_point,
            "new_files": result.new_files,
            "modified_files": result.modified_files,
            "new_lines_count": result.new_lines_count,
            "total_new_code_files": result.total_new_code_files,
            "detected_at": result.detected_at.isoformat(),
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  NEW CODE PERIOD: {scan_path}")
    print("=" * 70)
    print("")
    print(f"  Reference point: {result.reference_point}")
    print(f"  Total new code files: {result.total_new_code_files}")
    print(f"  New files added: {len(result.new_files)}")
    print(f"  Files modified: {len(result.modified_files)}")
    print("")

    if result.new_files:
        print("  New Files:")
        for f in result.new_files:
            print(f"    + {f}")
        print("")

    if result.modified_files:
        print("  Modified Files:")
        for f in result.modified_files:
            print(f"    M {f}")
        print("")

    print("=" * 70)
    return 0

def run_taint_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Handle the 'heimdall security taint' subcommand."""
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    severity_str = getattr(args, "severity", "low")

    config = TaintConfig(
        scan_path=scan_path,
        min_severity=severity_str,
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
        ],
    )

    try:
        analyzer = TaintAnalyzer(config)
        report = analyzer.scan()

        if output_format == "json":
            data = {
                "scan_info": {
                    "scan_path": report.scan_path,
                    "scanned_at": report.scanned_at.isoformat(),
                    "duration_seconds": report.scan_duration_seconds,
                    "files_analyzed": report.files_analyzed,
                },
                "summary": {
                    "total_flows": report.total_flows,
                    "critical": report.critical_count,
                    "high": report.high_count,
                    "medium": report.medium_count,
                },
                "flows": [
                    {
                        "title": f.title,
                        "severity": f.severity,
                        "source_type": f.source_type,
                        "sink_type": f.sink_type,
                        "cwe_id": f.cwe_id,
                        "owasp_category": f.owasp_category,
                        "description": f.description,
                        "source": {
                            "file_path": f.source_location.file_path,
                            "line_number": f.source_location.line_number,
                            "function_name": f.source_location.function_name,
                            "code_snippet": f.source_location.code_snippet,
                        },
                        "sink": {
                            "file_path": f.sink_location.file_path,
                            "line_number": f.sink_location.line_number,
                            "function_name": f.sink_location.function_name,
                            "code_snippet": f.sink_location.code_snippet,
                        },
                        "sanitizers_present": f.sanitizers_present,
                    }
                    for f in report.flows
                ],
            }
            print(json.dumps(data, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL TAINT FLOW ANALYSIS",
                "=" * 70,
                "",
                f"  Scan Path:      {report.scan_path}",
                f"  Scanned At:     {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:       {report.scan_duration_seconds:.2f}s",
                f"  Files Analyzed: {report.files_analyzed}",
                "",
                f"  Total Flows:    {report.total_flows}",
                f"  [CRITICAL]:     {report.critical_count}",
                f"  [HIGH]:         {report.high_count}",
                f"  [MEDIUM]:       {report.medium_count}",
                "",
            ]
            if report.flows:
                lines.extend(["-" * 70, "  TAINT FLOWS", "-" * 70, ""])
                for f in report.flows:
                    severity_label = str(f.severity).upper()
                    lines.append(f"  [{severity_label}] {f.title}")
                    lines.append(
                        f"  Source: {f.source_location.file_path}:{f.source_location.line_number}"
                        f" ({f.source_type})"
                    )
                    lines.append(
                        f"  Sink:   {f.sink_location.file_path}:{f.sink_location.line_number}"
                        f" ({f.sink_type})"
                    )
                    if f.cwe_id:
                        lines.append(f"  CWE: {f.cwe_id}  OWASP: {f.owasp_category or 'N/A'}")
                    if f.sanitizers_present:
                        lines.append("  Sanitizers detected (manual review recommended)")
                    if verbose:
                        lines.append(f"  Description: {f.description}")
                    lines.append("")
            else:
                lines.extend(["  No taint flows detected.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.critical_count > 0 or report.high_count > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        if verbose:
            _traceback.print_exc()
        return 1



def run_bugs_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Handle the 'heimdall quality bugs' subcommand."""
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    null_only = getattr(args, "null_only", False)
    unreachable_only = getattr(args, "unreachable_only", False)
    exclude_patterns = list(args.exclude) if args.exclude else []

    config = BugDetectionConfig(
        scan_path=scan_path,
        detect_null_dereference=not unreachable_only,
        detect_unreachable_code=not null_only,
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
        ],
    )

    try:
        detector = BugDetector(config)
        if null_only:
            report = detector.scan_null_dereference_only()
        elif unreachable_only:
            report = detector.scan_unreachable_only()
        else:
            report = detector.scan()

        if output_format == "json":
            data = {
                "scan_info": {
                    "scan_path": report.scan_path,
                    "scanned_at": report.scanned_at.isoformat(),
                    "duration_seconds": report.scan_duration_seconds,
                    "files_analyzed": report.files_analyzed,
                },
                "summary": {
                    "total_bugs": report.total_bugs,
                    "critical": report.critical_count,
                    "high": report.high_count,
                    "medium": report.medium_count,
                    "low": report.low_count,
                },
                "findings": [
                    {
                        "file_path": f.file_path,
                        "line_number": f.line_number,
                        "category": f.category,
                        "severity": f.severity,
                        "title": f.title,
                        "description": f.description,
                        "code_snippet": f.code_snippet,
                        "fix_suggestion": f.fix_suggestion,
                    }
                    for f in report.findings
                ],
            }
            print(json.dumps(data, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL BUG DETECTION REPORT",
                "=" * 70,
                "",
                f"  Scan Path:      {report.scan_path}",
                f"  Scanned At:     {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:       {report.scan_duration_seconds:.2f}s",
                f"  Files Analyzed: {report.files_analyzed}",
                "",
                f"  Total Bugs:     {report.total_bugs}",
                f"  [CRITICAL]:     {report.critical_count}",
                f"  [HIGH]:         {report.high_count}",
                f"  [MEDIUM]:       {report.medium_count}",
                f"  [LOW]:          {report.low_count}",
                "",
            ]
            if report.findings:
                lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
                for f in report.findings:
                    severity_label = str(f.severity).upper()
                    lines.append(f"  [{severity_label}] {f.title}")
                    lines.append(f"  File: {f.file_path}:{f.line_number}  Category: {f.category}")
                    if f.code_snippet:
                        lines.append(f"  Code: {f.code_snippet}")
                    if verbose:
                        lines.append(f"  Description: {f.description}")
                        if f.fix_suggestion:
                            lines.append(f"  Fix: {f.fix_suggestion}")
                    lines.append("")
            else:
                lines.extend(["  No bugs detected.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.critical_count > 0 or report.high_count > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        if verbose:
            _traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# JavaScript analysis handler
# ---------------------------------------------------------------------------


def run_js_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute JavaScript static analysis and print findings."""
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        max_file_lines = getattr(args, "max_file_lines", 500)
        max_complexity = getattr(args, "max_complexity", 10)

        config = JSAnalysisConfig(
            scan_path=scan_path,
            language="javascript",
            include_extensions=[".js", ".jsx"],
            exclude_patterns=[
                "node_modules", ".git", "dist", "build", "__pycache__", "*.min.js"
            ] + exclude,
            disabled_rules=disabled,
            max_file_lines=max_file_lines,
            max_complexity=max_complexity,
        )
        analyzer = JSAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  JAVASCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# TypeScript analysis handler
# ---------------------------------------------------------------------------


def run_ts_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute TypeScript static analysis and print findings."""
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        max_file_lines = getattr(args, "max_file_lines", 500)
        max_complexity = getattr(args, "max_complexity", 10)

        config = JSAnalysisConfig(
            scan_path=scan_path,
            language="typescript",
            include_extensions=[".ts", ".tsx"],
            exclude_patterns=[
                "node_modules", ".git", "dist", "build", "__pycache__"
            ] + exclude,
            disabled_rules=disabled,
            max_file_lines=max_file_lines,
            max_complexity=max_complexity,
        )
        analyzer = TSAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  TYPESCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Shell analysis handler
# ---------------------------------------------------------------------------


def run_shell_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute shell script static analysis and print findings."""
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        also_check_shebangs = not getattr(args, "no_shebang_check", False)

        config = ShellAnalysisConfig(
            scan_path=scan_path,
            exclude_patterns=["node_modules", ".git", "__pycache__"] + exclude,
            also_check_shebangs=also_check_shebangs,
            disabled_rules=disabled,
        )
        analyzer = ShellAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  SHELL SCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Issues command handler
# ---------------------------------------------------------------------------


def run_issues_command(args: argparse.Namespace, verbose: bool = False) -> int:
    """Route to the appropriate issues subcommand handler."""
    subcommand = getattr(args, "issues_command", None)

    if subcommand == "list":
        return _run_issues_list(args, verbose)
    if subcommand == "show":
        return _run_issues_show(args, verbose)
    if subcommand == "update":
        return _run_issues_update(args, verbose)
    if subcommand == "assign":
        return _run_issues_assign(args, verbose)
    if subcommand == "summary":
        return _run_issues_summary(args, verbose)

    print("Error: Please specify an issues subcommand (list, show, update, assign, summary).")
    return 1



def _run_issues_list(args: argparse.Namespace, verbose: bool) -> int:
    """List issues for a project with optional filters."""
    try:
        project_path = str(Path(args.path).resolve())
        tracker = IssueTracker()

        status_vals = getattr(args, "status", None)
        severity_vals = getattr(args, "severity", None)
        rule_val = getattr(args, "rule", None)

        issue_filter = None
        if status_vals or severity_vals or rule_val:
            issue_filter = IssueFilter(
                status=[IssueStatus(s) for s in status_vals] if status_vals else None,
                severity=[IssueSeverity(s) for s in severity_vals] if severity_vals else None,
                rule_id=rule_val,
            )

        issues = tracker.get_issues(project_path, issue_filter)
        output_format = getattr(args, "format", "text")

        if output_format == "json":
            print(json.dumps([i.dict() for i in issues], default=str, indent=2))
            return 0

        if not issues:
            print(f"No issues found for project: {project_path}")
            return 0

        print(f"\nIssues for: {project_path}")
        print("=" * 70)
        for issue in issues:
            print(
                f"  [{str(issue.severity).upper()}] {issue.issue_id[:8]}  {issue.title}"
            )
            print(f"    Rule: {issue.rule_id}  Status: {issue.status}  File: {issue.file_path}:{issue.line_number}")
            if verbose:
                print(f"    First seen: {issue.first_detected}  Last seen: {issue.last_seen}")
                if issue.assigned_to:
                    print(f"    Assigned to: {issue.assigned_to}")
            print()
        print(f"Total: {len(issues)} issue(s)")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def _run_issues_show(args: argparse.Namespace, verbose: bool) -> int:
    """Show details for a single issue by UUID."""
    try:
        issue_id = args.issue_id
        tracker = IssueTracker()
        issue = tracker.get_issue(issue_id)

        if not issue:
            print(f"Issue not found: {issue_id}")
            return 1

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(issue.dict(), default=str, indent=2))
            return 0

        print(f"\nIssue: {issue.issue_id}")
        print("=" * 70)
        print(f"  Title:       {issue.title}")
        print(f"  Rule:        {issue.rule_id}")
        print(f"  Type:        {issue.issue_type}")
        print(f"  Severity:    {issue.severity}")
        print(f"  Status:      {issue.status}")
        print(f"  File:        {issue.file_path}:{issue.line_number}")
        print(f"  First seen:  {issue.first_detected}")
        print(f"  Last seen:   {issue.last_seen}")
        print(f"  Scan count:  {issue.scan_count}")
        if issue.assigned_to:
            print(f"  Assigned to: {issue.assigned_to}")
        if issue.git_blame_author:
            print(f"  Author:      {issue.git_blame_author}  ({issue.git_blame_commit})")
        if issue.false_positive_reason:
            print(f"  FP Reason:   {issue.false_positive_reason}")
        print(f"\n  Description: {issue.description}")
        if issue.comments:
            print("\n  Comments:")
            for comment in issue.comments:
                print(f"    - {comment}")
        if issue.tags:
            print(f"\n  Tags: {', '.join(issue.tags)}")
        print()
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def _run_issues_update(args: argparse.Namespace, verbose: bool) -> int:
    """Transition an issue to a new lifecycle status."""
    try:
        issue_id = args.issue_id
        new_status = IssueStatus(args.status)
        reason = getattr(args, "reason", None)

        tracker = IssueTracker()
        updated = tracker.update_status(issue_id, new_status, reason)

        if not updated:
            print(f"Issue not found: {issue_id}")
            return 1

        print(f"Issue {issue_id[:8]} status updated to: {updated.status}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def _run_issues_assign(args: argparse.Namespace, verbose: bool) -> int:
    """Assign an issue to a user."""
    try:
        issue_id = args.issue_id
        assignee = args.assignee

        tracker = IssueTracker()
        updated = tracker.assign_issue(issue_id, assignee)

        if not updated:
            print(f"Issue not found: {issue_id}")
            return 1

        print(f"Issue {issue_id[:8]} assigned to: {updated.assigned_to}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def _run_issues_summary(args: argparse.Namespace, verbose: bool) -> int:
    """Display an aggregated issue summary for a project."""
    try:
        project_path = str(Path(args.path).resolve())
        tracker = IssueTracker()
        summary = tracker.get_summary(project_path)

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(summary.dict(), default=str, indent=2))
            return 0

        print(f"\nIssue Summary for: {project_path}")
        print("=" * 70)
        print(f"  Open:            {summary.total_open}")
        print(f"  Confirmed:       {summary.total_confirmed}")
        print(f"  Resolved:        {summary.total_resolved}")
        print(f"  False Positives: {summary.total_false_positives}")
        print(f"  Wont Fix:        {summary.total_wont_fix}")
        if summary.open_by_severity:
            print("\n  Open by Severity:")
            for sev, count in sorted(summary.open_by_severity.items()):
                print(f"    {sev:12s}: {count}")
        if summary.open_by_type:
            print("\n  Open by Type:")
            for itype, count in sorted(summary.open_by_type.items()):
                print(f"    {itype:20s}: {count}")
        if summary.oldest_open_issue:
            print(f"\n  Oldest open issue: {summary.oldest_open_issue}")
        print()
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def run_sbom_generation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute SBOM generation and output the result."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        fmt_str = getattr(args, "format", "cyclonedx")
        fmt = SBOMFormat.SPDX if fmt_str == "spdx" else SBOMFormat.CYCLONEDX

        config = SBOMConfig(
            scan_path=scan_path,
            output_format=fmt,
            project_name=getattr(args, "project_name", "") or "",
            project_version=getattr(args, "project_version", "") or "",
        )
        generator = SBOMGenerator(config)
        document = generator.generate(str(scan_path))

        if fmt == SBOMFormat.SPDX:
            output_dict = generator.to_spdx_json(document)
        else:
            output_dict = generator.to_cyclonedx_json(document)

        output_json = json.dumps(output_dict, indent=2, default=str)

        output_file = getattr(args, "output", None)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as fh:
                fh.write(output_json)
            print(f"SBOM written to: {output_file}")
            print(f"Format:          {fmt_str.upper()}")
            print(f"Components:      {document.total_components}")
        else:
            print(output_json)

        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def run_codefix_suggestions(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute codefix suggestion generation and display the result."""
    scan_path = Path(args.path).resolve()
    rule_id = getattr(args, "rule_id", None)
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        service = CodeFixService()

        if rule_id:
            fix = service.get_fix(rule_id, code_snippet="")
            if fix is None:
                print(f"No fix template available for rule: {rule_id}")
                return 0

            if output_format == "json":
                print(json.dumps(fix.dict(), indent=2, default=str))
            else:
                print("")
                print("=" * 70)
                print(f"  CODE FIX: {fix.title}")
                print("=" * 70)
                print(f"  Rule:       {fix.rule_id}")
                print(f"  Type:       {fix.fix_type}")
                print(f"  Confidence: {fix.confidence}")
                print("")
                print(f"  Description:")
                print(f"    {fix.description}")
                if fix.explanation:
                    print("")
                    print(f"  Explanation:")
                    print(f"    {fix.explanation}")
                if fix.fixed_code:
                    print("")
                    print(f"  Suggested fix:")
                    for line in fix.fixed_code.splitlines():
                        print(f"    {line}")
                if fix.references:
                    print("")
                    print(f"  References:")
                    for ref in fix.references:
                        print(f"    {ref}")
                print("=" * 70)
                print("")
            return 0

        # No specific rule — show the available rule fix catalogue
        handlers = service._rule_handlers()
        if output_format == "json":
            catalogue = []
            for rid in sorted(handlers.keys()):
                fix = service.get_fix(rid)
                if fix:
                    catalogue.append({
                        "rule_id": rid,
                        "title": fix.title,
                        "fix_type": fix.fix_type,
                        "confidence": fix.confidence,
                    })
            print(json.dumps(catalogue, indent=2, default=str))
        else:
            print("")
            print("=" * 70)
            print("  AVAILABLE CODE FIX TEMPLATES")
            print("=" * 70)
            print(f"  Scan path: {scan_path}")
            print(f"  Use --rule RULE_ID to see fix details for a specific rule.")
            print("")
            for rid in sorted(handlers.keys()):
                fix = service.get_fix(rid)
                if fix:
                    print(f"  {rid}")
                    print(f"    -> {fix.title} [{fix.fix_type} / {fix.confidence}]")
            print("=" * 70)
            print("")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1



def run_mcp_server(args: argparse.Namespace, verbose: bool = False) -> int:
    """Start the Asgard MCP server."""
    host = getattr(args, "host", "localhost")
    port = int(getattr(args, "port", 8765))
    project_path = getattr(args, "project_path", ".")

    config = MCPServerConfig(
        host=host,
        port=port,
        project_path=str(Path(project_path).resolve()),
    )

    try:
        server = AsgardMCPServer(config)
        server.run()
        return 0
    except Exception as exc:
        print(f"Error starting MCP server: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Dashboard command handler
# ---------------------------------------------------------------------------


def run_dashboard(args: argparse.Namespace, verbose: bool = False) -> int:
    """Start the Asgard web dashboard server."""
    config = DashboardConfig(
        host=args.host,
        port=args.port,
        project_path=args.path,
        open_browser=not args.no_open_browser,
    )
    server = DashboardServer(config)
    server.run()
    return 0


# ---------------------------------------------------------------------------
# Scan command handler (runs ALL analyses)
# ---------------------------------------------------------------------------

# Labels shown in tab buttons (short, uppercase acronyms preserved)
_SCAN_TAB_LABELS: dict = {
    "file_length": "File Length",
    "complexity": "Complexity",
    "lazy_imports": "Lazy Imports",
    "env_fallbacks": "Env Fallbacks",
    "type_check": "Type Check",
    "security": "Security",
    "performance": "Performance",
    "oop": "OOP",
    "architecture": "Architecture",
    "dependencies": "Dependencies",
    "test_coverage": "Test Coverage",
}

# Labels shown in the overview table category column (full names)
_SCAN_DISPLAY_NAMES: dict = {
    "file_length": "File Length",
    "complexity": "Complexity",
    "lazy_imports": "Lazy Imports",
    "env_fallbacks": "Env Fallbacks",
    "type_check": "Type Check",
    "security": "Security",
    "performance": "Performance",
    "oop": "Object Oriented Programming",
    "architecture": "Architecture",
    "dependencies": "Dependencies",
    "test_coverage": "Test Coverage",
}

# Short description of what each category checks (shown in overview table)
_SCAN_DESCRIPTIONS: dict = {
    "file_length": "Max lines per file threshold",
    "complexity": "Cyclomatic & cognitive complexity of functions",
    "lazy_imports": "Imports inside functions, methods, or blocks",
    "env_fallbacks": "Environment variables with hardcoded fallback values",
    "type_check": "Static type errors detected by mypy",
    "security": "Security vulnerabilities, secrets & misconfigurations",
    "performance": "Performance anti-patterns & inefficient code",
    "oop": "OOP coupling, cohesion & inheritance metrics",
    "architecture": "SOLID principles, layer & hexagonal design",
    "dependencies": "Circular import cycles between modules",
    "test_coverage": "Test coverage gaps across source methods",
}


def _detail_str(category: str, data: dict) -> str:
    """Build a human-readable detail string for a scan category result."""
    status = data.get("status", "?")
    if status == "ERROR":
        return data.get("error", "")[:80]
    if category == "type_check":
        return f"{data.get('errors', 0)} errors, {data.get('files_with_errors', 0)} files affected"
    if category == "security":
        return f"{data.get('total_findings', 0)} findings ({data.get('critical', 0)} critical)"
    if category == "file_length":
        rate = data.get("compliance_rate")
        base = f"{data.get('violations', 0)} violations"
        return f"{base} ({rate:.1f}% compliant)" if rate is not None else base
    if category == "test_coverage":
        pct = data.get("method_coverage_percent")
        gaps = data.get("total_gaps", 0)
        return f"{pct:.1f}% method coverage, {gaps} gaps" if pct is not None else f"{gaps} gaps"
    if "violations" in data:
        return f"{data['violations']} violations"
    if "total_findings" in data:
        return f"{data['total_findings']} findings"
    if "circular_imports" in data:
        return f"{data['circular_imports']} cycles"
    return ""


def _generate_scan_html_report(
    scan_results: dict,
    step_reports: dict,
    scan_path: str,
    duration: float,
    scanned_at: "datetime",
) -> str:
    """Generate a single tabbed HTML page for the Heimdall full scan."""
    pass_count = sum(1 for d in scan_results.values() if d.get("status") == "PASS")
    fail_count = sum(1 for d in scan_results.values() if d.get("status") == "FAIL")
    err_count = sum(1 for d in scan_results.values() if d.get("status") == "ERROR")
    overall = "PASSING" if fail_count == 0 and err_count == 0 else "FAILING"
    overall_color = "#4ec9b0" if overall == "PASSING" else "#f44747"

    # Overview table rows
    rows_html = ""
    for cat, data in scan_results.items():
        status = data.get("status", "?")
        label = _SCAN_DISPLAY_NAMES.get(cat, cat.replace("_", " ").title())
        detail = _detail_str(cat, data)
        desc = _SCAN_DESCRIPTIONS.get(cat, "")
        cls = "pass" if status == "PASS" else ("fail" if status == "FAIL" else "err")
        rows_html += (
            f"<tr>"
            f"<td>{label}</td>"
            f"<td class='{cls}'>{status}</td>"
            f"<td>{detail}</td>"
            f"<td class='desc'>{desc}</td>"
            f"</tr>\n"
        )

    # Tab buttons and panels
    btn_html = '<button class="tab-btn active" onclick="showTab(this,\'overview\')">Overview</button>\n'
    panel_html = ""
    for key, report_text in step_reports.items():
        label = _SCAN_TAB_LABELS.get(key, key.replace("_", " ").title())
        status = scan_results.get(key, {}).get("status", "?")
        dot_cls = "pass" if status == "PASS" else ("fail" if status == "FAIL" else "err")
        escaped = (
            _strip_ansi(report_text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        tid = f"tab_{key}"
        btn_html += (
            f'<button class="tab-btn" onclick="showTab(this,\'{tid}\')">'
            f'<span class="{dot_cls}-dot"></span>{label}</button>\n'
        )
        panel_html += (
            f'<div id="{tid}" class="tab-panel" style="display:none">'
            f"<pre>{escaped}</pre>"
            f"</div>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Heimdall Scan - {scan_path}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#1e1e1e;color:#d4d4d4;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:13px;line-height:1.6;display:flex;flex-direction:column;height:100vh;overflow:hidden}}
    .hdr{{background:#252526;padding:12px 20px;border-bottom:1px solid #333;flex-shrink:0}}
    .hdr h1{{color:#569cd6;font-size:1em;margin-bottom:2px}}
    .hdr .meta{{color:#777;font-size:.85em}}
    .overall{{color:{overall_color};font-weight:bold;margin-left:8px}}
    .tab-bar{{display:flex;background:#2d2d2d;border-bottom:1px solid #333;padding:8px 16px 0;gap:4px;flex-shrink:0;flex-wrap:wrap}}
    .tab-btn{{background:#333;border:1px solid #444;border-bottom:none;color:#ccc;padding:5px 12px;cursor:pointer;font-family:inherit;font-size:12px;border-radius:4px 4px 0 0}}
    .tab-btn:hover{{background:#3e3e3e}}
    .tab-btn.active{{background:#1e1e1e;color:#fff;border-color:#569cd6;border-bottom-color:#1e1e1e}}
    .pass-dot::before{{content:"● ";color:#4ec9b0}}
    .fail-dot::before{{content:"● ";color:#f44747}}
    .err-dot::before{{content:"● ";color:#ff8c00}}
    .tab-content{{flex:1;overflow:auto;padding:20px 24px}}
    .tab-panel{{display:none}}
    .tab-panel pre{{white-space:pre-wrap;word-wrap:break-word}}
    table{{border-collapse:collapse;width:100%;max-width:920px}}
    th,td{{text-align:left;padding:6px 14px;border-bottom:1px solid #333}}
    th{{color:#777;font-weight:normal;font-size:.9em}}
    .desc{{color:#777;font-size:.9em}}
    .pass{{color:#4ec9b0}}
    .fail{{color:#f44747}}
    .err{{color:#ff8c00}}
    .summary{{margin-top:14px;color:#777;font-size:.9em}}
  </style>
</head>
<body>
  <div class="hdr">
    <h1>Heimdall Full Scan <span class="overall">{overall}</span></h1>
    <div class="meta">
      {scan_path} &nbsp;|&nbsp; {scanned_at.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; {duration:.1f}s &nbsp;|&nbsp;
      <span class="pass">{pass_count} passed</span> &nbsp;
      <span class="fail">{fail_count} failed</span> &nbsp;
      <span class="err">{err_count} errors</span>
    </div>
  </div>
  <div class="tab-bar">
    {btn_html}
  </div>
  <div class="tab-content">
    <div id="overview" class="tab-panel" style="display:block">
      <table>
        <thead><tr><th>Category</th><th>Status</th><th>Details</th><th>What It Checks</th></tr></thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
      <div class="summary">
        <span class="pass">{pass_count} passed</span> &nbsp;
        <span class="fail">{fail_count} failed</span> &nbsp;
        <span class="err">{err_count} errors</span> &nbsp;|&nbsp;
        <span class="overall">{overall}</span>
      </div>
    </div>
    {panel_html}
  </div>
  <script>
    function showTab(btn,id){{
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
      btn.classList.add('active');
      document.getElementById(id).style.display='block';
    }}
  </script>
</body>
</html>"""


def run_full_scan(args: argparse.Namespace, verbose: bool = False) -> int:
    """Execute a full scan running all analysis categories."""
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    output_format = getattr(args, "format", "text")
    exclude_patterns = list(args.exclude) if getattr(args, "exclude", None) else []
    include_tests = getattr(args, "include_tests", False)
    start_time = datetime.now()

    # Default excludes for full scan - large non-code directories
    scan_excludes = [
        "__pycache__", "node_modules", ".git", ".venv", "venv",
        "build", "dist", "assets", "*-venv", "site-packages",
        "android", ".gradle", ".next", "coverage", ".tox",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "*.egg-info", "_*",
    ]
    # Merge user excludes (user patterns take priority / are additive)
    for pattern in exclude_patterns:
        if pattern not in scan_excludes:
            scan_excludes.append(pattern)
    exclude_patterns = scan_excludes

    # Ensure stdout is line-buffered so progress prints appear in real time
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    # Track results from all scans
    scan_results = {}
    overall_exit = 0
    step_reports: dict = {}

    print("=" * 70, flush=True)
    print("  HEIMDALL FULL SCAN", flush=True)
    print("  Running all analysis categories...", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)

    # ---- 1. Quality: File Length ----
    print("[1/11] Quality: File Length Analysis...")
    try:
        config = AnalysisConfig(
            scan_path=scan_path,
            default_threshold=getattr(args, "threshold", 300) or 300,
            exclude_patterns=exclude_patterns,
            output_format=output_format,
            verbose=verbose,
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()
        scan_results["file_length"] = {
            "violations": result.files_exceeding_threshold,
            "files_scanned": result.total_files_scanned,
            "compliance_rate": result.compliance_rate,
            "status": "PASS" if not result.has_violations else "FAIL",
        }
        if result.has_violations:
            overall_exit = 1
        print(f"       {result.files_exceeding_threshold} violations in {result.total_files_scanned} files")
        fl_lines = [
            "",
            "=" * 70,
            "  FILE LENGTH ANALYSIS",
            "=" * 70,
            "",
            f"  Scan Path:              {result.scan_path}",
            f"  Files Scanned:          {result.total_files_scanned}",
            f"  Files Over Threshold:   {result.files_exceeding_threshold}",
            f"  Compliance Rate:        {result.compliance_rate:.1f}%",
            "",
        ]
        if not result.has_violations:
            fl_lines.extend(["  All files are within the threshold.", ""])
        else:
            sorted_viol = sorted(result.violations, key=lambda x: x.line_count, reverse=True)
            fl_lines.extend(["-" * 70, "  VIOLATIONS (longest first)", "  " + "-" * 47, ""])
            for v in sorted_viol:
                fl_lines.append(
                    f"  {v.relative_path}   {v.line_count} lines  (limit: {v.threshold}, over by {v.lines_over})"
                )
            fl_lines.append("")
        fl_lines.extend(["=" * 70, ""])
        step_reports["file_length"] = "\n".join(fl_lines)
    except Exception as e:
        scan_results["file_length"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 2. Quality: Complexity ----
    print("[2/11] Quality: Complexity Analysis...")
    try:
        complexity_config = ComplexityConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        complexity_analyzer = ComplexityAnalyzer(complexity_config)
        complexity_result = complexity_analyzer.analyze()
        violation_count = len(complexity_result.violations) if hasattr(complexity_result, "violations") else 0
        scan_results["complexity"] = {
            "violations": violation_count,
            "status": "PASS" if not complexity_result.has_violations else "FAIL",
        }
        if complexity_result.has_violations:
            overall_exit = 1
        print(f"       {violation_count} violations found")
        try:
            step_reports["complexity"] = complexity_analyzer.generate_report(complexity_result, "text")
        except Exception:
            step_reports["complexity"] = f"Complexity Analysis\n\n{json.dumps(scan_results['complexity'], indent=2)}"
    except Exception as e:
        scan_results["complexity"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 3. Quality: Lazy Imports ----
    print("[3/11] Quality: Lazy Import Detection...")
    try:
        lazy_config = LazyImportConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        lazy_scanner = LazyImportScanner(lazy_config)
        lazy_result = lazy_scanner.analyze(scan_path)
        lazy_count = lazy_result.total_violations
        scan_results["lazy_imports"] = {
            "violations": lazy_count,
            "files_scanned": lazy_result.files_scanned,
            "status": "PASS" if not lazy_result.has_violations else "FAIL",
        }
        if lazy_result.has_violations:
            overall_exit = 1
        print(f"       {lazy_count} violations in {lazy_result.files_scanned} files")
        try:
            step_reports["lazy_imports"] = lazy_scanner.generate_report(lazy_result, "text")
        except Exception:
            step_reports["lazy_imports"] = f"Lazy Import Detection\n\n{json.dumps(scan_results['lazy_imports'], indent=2)}"
    except Exception as e:
        scan_results["lazy_imports"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 4. Quality: Env Fallbacks ----
    print("[4/11] Quality: Environment Variable Fallback Detection...")
    try:
        env_config = EnvFallbackConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        env_scanner = EnvFallbackScanner(env_config)
        env_result = env_scanner.analyze(scan_path)
        env_count = env_result.total_violations
        scan_results["env_fallbacks"] = {
            "violations": env_count,
            "files_scanned": env_result.files_scanned,
            "status": "PASS" if not env_result.has_violations else "FAIL",
        }
        if env_result.has_violations:
            overall_exit = 1
        print(f"       {env_count} violations in {env_result.files_scanned} files")
        try:
            step_reports["env_fallbacks"] = env_scanner.generate_report(env_result, "text")
        except Exception:
            step_reports["env_fallbacks"] = f"Env Fallback Detection\n\n{json.dumps(scan_results['env_fallbacks'], indent=2)}"
    except Exception as e:
        scan_results["env_fallbacks"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 5. Quality: Type Checking (mypy) ----
    print("[5/11] Quality: Static Type Checking (mypy)...")
    try:
        type_config = TypeCheckConfig(
            engine="mypy",
            type_checking_mode=getattr(args, "type_check_mode", "basic"),
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            include_warnings=False,  # Errors only for full scan
            verbose=verbose,
        )
        type_checker = TypeChecker(type_config)
        type_result = type_checker.analyze(scan_path)
        scan_results["type_check"] = {
            "errors": type_result.total_errors,
            "warnings": type_result.total_warnings,
            "files_analyzed": type_result.files_scanned,
            "files_with_errors": type_result.files_with_errors,
            "errors_by_category": type_result.errors_by_category,
            "status": "PASS" if type_result.is_compliant else "FAIL",
        }
        if type_result.has_violations:
            overall_exit = 1
        print(f"       {type_result.total_errors} errors, {type_result.total_warnings} warnings in {type_result.files_scanned} files")
        try:
            step_reports["type_check"] = type_checker.generate_report(type_result, "text")
        except Exception:
            step_reports["type_check"] = f"Static Type Checking\n\n{json.dumps({k: v for k, v in scan_results['type_check'].items() if k != 'errors_by_category'}, indent=2)}"
    except Exception as e:
        scan_results["type_check"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 6. Security ----
    print("[6/11] Security: Vulnerability Scan...")
    try:
        sec_config = SecurityScanConfig(
            scan_path=scan_path,
            min_severity="low",
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        sec_service = StaticSecurityService(sec_config)
        sec_result = sec_service.scan(scan_path)
        sec_total = sec_result.total_findings if hasattr(sec_result, "total_findings") else 0
        sec_critical = sec_result.critical_count if hasattr(sec_result, "critical_count") else 0
        scan_results["security"] = {
            "total_findings": sec_total,
            "critical": sec_critical,
            "status": "PASS" if sec_total == 0 else "FAIL",
        }
        if sec_total > 0:
            overall_exit = 1
        print(f"       {sec_total} findings ({sec_critical} critical)")
        try:
            step_reports["security"] = sec_service.generate_report(sec_result, "text")
        except Exception:
            step_reports["security"] = f"Security Analysis\n\n{json.dumps(scan_results['security'], indent=2)}"
    except Exception as e:
        scan_results["security"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 7. Performance ----
    print("[7/11] Performance: Pattern Analysis...")
    try:
        perf_config = PerformanceScanConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        perf_service = StaticPerformanceService(perf_config)
        perf_result = perf_service.scan(scan_path)
        perf_total = perf_result.total_findings if hasattr(perf_result, "total_findings") else 0
        scan_results["performance"] = {
            "total_findings": perf_total,
            "status": "PASS" if perf_total == 0 else "FAIL",
        }
        if perf_total > 0:
            overall_exit = 1
        print(f"       {perf_total} findings")
        try:
            step_reports["performance"] = perf_service.generate_report(perf_result, "text")
        except Exception:
            step_reports["performance"] = f"Performance Analysis\n\n{json.dumps(scan_results['performance'], indent=2)}"
    except Exception as e:
        scan_results["performance"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 8. OOP Metrics ----
    print("[8/11] OOP: Coupling/Cohesion Metrics...")
    try:
        oop_config = OOPConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        oop_analyzer = OOPAnalyzer(oop_config)
        oop_result = oop_analyzer.analyze(scan_path)
        oop_violations = oop_result.total_violations if hasattr(oop_result, "total_violations") else 0
        scan_results["oop"] = {
            "violations": oop_violations,
            "status": "PASS" if oop_violations == 0 else "FAIL",
        }
        if oop_violations > 0:
            overall_exit = 1
        print(f"       {oop_violations} violations")
        try:
            step_reports["oop"] = oop_analyzer.generate_report(oop_result, "text")
        except Exception:
            step_reports["oop"] = f"OOP Metrics\n\n{json.dumps(scan_results['oop'], indent=2)}"
    except Exception as e:
        scan_results["oop"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 9. Architecture ----
    print("[9/11] Architecture: SOLID/Layer Analysis...")
    try:
        arch_config = ArchitectureConfig(
            scan_path=scan_path,
            exclude_patterns=exclude_patterns,
        )
        arch_analyzer = ArchitectureAnalyzer(arch_config)
        arch_result = arch_analyzer.analyze(scan_path)
        arch_violations = arch_result.total_violations if hasattr(arch_result, "total_violations") else 0
        scan_results["architecture"] = {
            "violations": arch_violations,
            "status": "PASS" if arch_violations == 0 else "FAIL",
        }
        if arch_violations > 0:
            overall_exit = 1
        print(f"       {arch_violations} violations")
        try:
            step_reports["architecture"] = arch_analyzer.generate_report(arch_result, "text")
        except Exception:
            step_reports["architecture"] = f"Architecture Analysis\n\n{json.dumps(scan_results['architecture'], indent=2)}"
    except Exception as e:
        scan_results["architecture"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 10. Dependencies ----
    print("[10/11] Dependencies: Circular Import Detection...")
    try:
        deps_config = DependencyConfig(
            scan_path=scan_path,
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        deps_analyzer = DependencyAnalyzer(deps_config)
        deps_result = deps_analyzer.analyze(scan_path)
        deps_cycles = deps_result.cycle_count if hasattr(deps_result, "cycle_count") else 0
        scan_results["dependencies"] = {
            "circular_imports": deps_cycles,
            "status": "PASS" if deps_cycles == 0 else "FAIL",
        }
        if deps_cycles > 0:
            overall_exit = 1
        print(f"       {deps_cycles} circular dependencies")
        try:
            step_reports["dependencies"] = deps_analyzer.generate_report(deps_result, "text")
        except Exception:
            step_reports["dependencies"] = f"Dependency Analysis\n\n{json.dumps(scan_results['dependencies'], indent=2)}"
    except Exception as e:
        scan_results["dependencies"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- 11. Test Coverage ----
    print("[11/11] Test Coverage: Gap Analysis...")
    try:
        coverage_config = CoverageConfig(
            scan_path=scan_path,
            exclude_patterns=exclude_patterns,
        )
        coverage_analyzer = CoverageAnalyzer(coverage_config)
        coverage_result = coverage_analyzer.analyze(scan_path)
        method_coverage = coverage_result.metrics.method_coverage_percent
        total_gaps = coverage_result.total_gaps
        scan_results["test_coverage"] = {
            "method_coverage_percent": round(method_coverage, 1),
            "total_gaps": total_gaps,
            "status": "PASS" if method_coverage >= coverage_config.min_method_coverage else "FAIL",
        }
        if method_coverage < coverage_config.min_method_coverage:
            overall_exit = 1
        print(f"       {method_coverage:.1f}% method coverage, {total_gaps} gaps")
        try:
            step_reports["test_coverage"] = coverage_analyzer.generate_report(coverage_result, "text")
        except Exception:
            step_reports["test_coverage"] = f"Test Coverage\n\n{json.dumps(scan_results['test_coverage'], indent=2)}"
    except Exception as e:
        scan_results["test_coverage"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    # ---- Summary ----
    duration = (datetime.now() - start_time).total_seconds()

    print()
    print("=" * 70)
    print("  SCAN COMPLETE")
    print("=" * 70)
    print()
    print(f"  Path:     {scan_path}")
    print(f"  Duration: {duration:.1f}s")
    print()

    # Summary table
    print(f"  {'Category':<35} {'Status':<8} {'Details'}")
    print(f"  {'-'*35} {'-'*8} {'-'*30}")

    for category, data in scan_results.items():
        status = data.get("status", "?")
        status_str = f"{'PASS' if status == 'PASS' else 'FAIL' if status == 'FAIL' else 'ERR '}"
        label = _SCAN_DISPLAY_NAMES.get(category, category.replace("_", " ").title())

        detail = _detail_str(category, data)

        print(f"  {label:<35} {status_str:<8} {detail}")

    pass_count = sum(1 for d in scan_results.values() if d.get("status") == "PASS")
    fail_count = sum(1 for d in scan_results.values() if d.get("status") == "FAIL")
    error_count = sum(1 for d in scan_results.values() if d.get("status") == "ERROR")

    print()
    print(f"  Results: {pass_count} passed, {fail_count} failed, {error_count} errors")
    print(f"  Overall: {'PASSING' if overall_exit == 0 else 'FAILING'}")
    print()
    print("=" * 70)

    # JSON output if requested
    if output_format == "json":
        report_data = {
            "scan_path": str(scan_path),
            "scanned_at": start_time.isoformat(),
            "duration_seconds": duration,
            "overall_status": "PASS" if overall_exit == 0 else "FAIL",
            "categories": scan_results,
            "summary": {
                "passed": pass_count,
                "failed": fail_count,
                "errors": error_count,
            },
        }
        print()
        print(json.dumps(report_data, indent=2))

    # Markdown output if requested
    if output_format == "markdown":
        lines = [
            "# Heimdall Full Scan Report",
            "",
            f"**Path:** `{scan_path}`",
            f"**Generated:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {duration:.1f}s",
            f"**Overall:** {'PASS' if overall_exit == 0 else 'FAIL'}",
            "",
            "## Results",
            "",
            "| Category | Status | Details |",
            "|----------|--------|---------|",
        ]
        for category, data in scan_results.items():
            status = data.get("status", "?")
            label = category.replace("_", " ").title()
            if status == "ERROR":
                detail = data.get("error", "")[:60]
            elif category == "type_check":
                detail = f"{data.get('errors', 0)} errors, {data.get('files_with_errors', 0)} files"
            elif category == "security":
                detail = f"{data.get('total_findings', 0)} findings ({data.get('critical', 0)} critical)"
            elif "violations" in data:
                detail = f"{data['violations']} violations"
            elif "total_findings" in data:
                detail = f"{data['total_findings']} findings"
            elif "circular_imports" in data:
                detail = f"{data['circular_imports']} cycles"
            else:
                detail = ""
            lines.append(f"| {label} | **{status}** | {detail} |")

        lines.extend([
            "",
            f"**Summary:** {pass_count} passed, {fail_count} failed, {error_count} errors",
        ])
        print()
        print("\n".join(lines))

    # Generate tabbed HTML report and open in browser
    html_report = _generate_scan_html_report(
        scan_results=scan_results,
        step_reports=step_reports,
        scan_path=str(scan_path),
        duration=duration,
        scanned_at=start_time,
    )
    open_output_in_browser(html_report, "Heimdall Full Scan")

    return overall_exit
