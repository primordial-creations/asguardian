"""
Common utilities shared across all CLI modules.

Contains severity markers, shared argument helpers, and utility functions.
"""

import argparse

from Asgard.Heimdall.Quality.models.analysis_models import SeverityLevel
from Asgard.Heimdall.Quality.models.complexity_models import ComplexitySeverity
from Asgard.Heimdall.Quality.models.duplication_models import DuplicationSeverity
from Asgard.Heimdall.Quality.models.smell_models import SmellSeverity
from Asgard.Heimdall.Quality.models.debt_models import DebtSeverity
from Asgard.Heimdall.Quality.models.maintainability_models import MaintainabilityLevel
from Asgard.Heimdall.Quality.models.env_fallback_models import EnvFallbackSeverity
from Asgard.Heimdall.Quality.models.lazy_import_models import LazyImportSeverity
from Asgard.Heimdall.Quality.models.syntax_models import SyntaxSeverity
from Asgard.Heimdall.Quality.models.library_usage_models import ForbiddenImportSeverity
from Asgard.Heimdall.Quality.models.datetime_models import DatetimeSeverity
from Asgard.Heimdall.Quality.models.typing_models import AnnotationSeverity
from Asgard.Heimdall.Quality.models.thread_safety_models import ThreadSafetySeverity
from Asgard.Heimdall.Quality.models.race_condition_models import RaceConditionSeverity
from Asgard.Heimdall.Quality.models.daemon_thread_models import DaemonThreadSeverity
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Performance.models.performance_models import PerformanceSeverity

# Severity display markers for terminal output
SEVERITY_MARKERS = {
    SeverityLevel.CRITICAL.value: "[CRITICAL]",
    SeverityLevel.SEVERE.value: "[SEVERE]",
    SeverityLevel.MODERATE.value: "[MODERATE]",
    SeverityLevel.WARNING.value: "[WARNING]",
}

COMPLEXITY_SEVERITY_MARKERS = {
    ComplexitySeverity.CRITICAL.value: "[CRITICAL]",
    ComplexitySeverity.VERY_HIGH.value: "[VERY HIGH]",
    ComplexitySeverity.HIGH.value: "[HIGH]",
    ComplexitySeverity.MODERATE.value: "[MODERATE]",
    ComplexitySeverity.LOW.value: "[LOW]",
}

DUPLICATION_SEVERITY_MARKERS = {
    DuplicationSeverity.CRITICAL.value: "[CRITICAL]",
    DuplicationSeverity.HIGH.value: "[HIGH]",
    DuplicationSeverity.MODERATE.value: "[MODERATE]",
    DuplicationSeverity.LOW.value: "[LOW]",
}

SMELL_SEVERITY_MARKERS = {
    SmellSeverity.CRITICAL.value: "[CRITICAL]",
    SmellSeverity.HIGH.value: "[HIGH]",
    SmellSeverity.MEDIUM.value: "[MEDIUM]",
    SmellSeverity.LOW.value: "[LOW]",
}

DEBT_SEVERITY_MARKERS = {
    DebtSeverity.CRITICAL.value: "[CRITICAL]",
    DebtSeverity.HIGH.value: "[HIGH]",
    DebtSeverity.MEDIUM.value: "[MEDIUM]",
    DebtSeverity.LOW.value: "[LOW]",
}

MAINTAINABILITY_LEVEL_MARKERS = {
    MaintainabilityLevel.EXCELLENT.value: "[EXCELLENT]",
    MaintainabilityLevel.GOOD.value: "[GOOD]",
    MaintainabilityLevel.MODERATE.value: "[MODERATE]",
    MaintainabilityLevel.POOR.value: "[POOR]",
    MaintainabilityLevel.CRITICAL.value: "[CRITICAL]",
}

ENV_FALLBACK_SEVERITY_MARKERS = {
    EnvFallbackSeverity.HIGH.value: "[HIGH]",
    EnvFallbackSeverity.MEDIUM.value: "[MEDIUM]",
    EnvFallbackSeverity.LOW.value: "[LOW]",
}

LAZY_IMPORT_SEVERITY_MARKERS = {
    LazyImportSeverity.HIGH.value: "[HIGH]",
    LazyImportSeverity.MEDIUM.value: "[MEDIUM]",
    LazyImportSeverity.LOW.value: "[LOW]",
}

THREAD_SAFETY_SEVERITY_MARKERS = {
    ThreadSafetySeverity.HIGH.value: "[HIGH]",
    ThreadSafetySeverity.MEDIUM.value: "[MEDIUM]",
}

RACE_CONDITION_SEVERITY_MARKERS = {
    RaceConditionSeverity.HIGH.value: "[HIGH]",
}

DAEMON_THREAD_SEVERITY_MARKERS = {
    DaemonThreadSeverity.MEDIUM.value: "[MEDIUM]",
    DaemonThreadSeverity.LOW.value: "[LOW]",
}

FORBIDDEN_IMPORT_SEVERITY_MARKERS = {
    ForbiddenImportSeverity.HIGH.value: "[HIGH]",
    ForbiddenImportSeverity.MEDIUM.value: "[MEDIUM]",
    ForbiddenImportSeverity.LOW.value: "[LOW]",
}

DATETIME_SEVERITY_MARKERS = {
    DatetimeSeverity.HIGH.value: "[HIGH]",
    DatetimeSeverity.MEDIUM.value: "[MEDIUM]",
    DatetimeSeverity.LOW.value: "[LOW]",
}

TYPING_SEVERITY_MARKERS = {
    AnnotationSeverity.HIGH.value: "[HIGH]",
    AnnotationSeverity.MEDIUM.value: "[MEDIUM]",
    AnnotationSeverity.LOW.value: "[LOW]",
}

SYNTAX_SEVERITY_MARKERS = {
    SyntaxSeverity.ERROR.value: "[ERROR]",
    SyntaxSeverity.WARNING.value: "[WARNING]",
    SyntaxSeverity.INFO.value: "[INFO]",
    SyntaxSeverity.STYLE.value: "[STYLE]",
}

SECURITY_SEVERITY_MARKERS = {
    SecuritySeverity.CRITICAL.value: "[CRITICAL]",
    SecuritySeverity.HIGH.value: "[HIGH]",
    SecuritySeverity.MEDIUM.value: "[MEDIUM]",
    SecuritySeverity.LOW.value: "[LOW]",
    SecuritySeverity.INFO.value: "[INFO]",
}

PERFORMANCE_SEVERITY_MARKERS = {
    PerformanceSeverity.CRITICAL.value: "[CRITICAL]",
    PerformanceSeverity.HIGH.value: "[HIGH]",
    PerformanceSeverity.MEDIUM.value: "[MEDIUM]",
    PerformanceSeverity.LOW.value: "[LOW]",
    PerformanceSeverity.INFO.value: "[INFO]",
}


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add performance-related flags to a parser (parallel, incremental, cache)."""
    parser.add_argument(
        "--parallel",
        "-P",
        action="store_true",
        help="Enable parallel processing for faster analysis",
    )
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--incremental",
        "-I",
        action="store_true",
        help="Enable incremental scanning (skip unchanged files)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching even if incremental mode is enabled",
    )
    parser.add_argument(
        "--baseline",
        "-B",
        type=str,
        default=None,
        help="Path to a baseline file; violations present in the baseline are suppressed from output",
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser (path, format, thresholds, dry-run, exclude)."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "github", "html"],
        default="text",
        help="Output format: text (terminal), json, markdown, github (annotations), html (default: text)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=None,
        help="Maximum allowed lines per file; overrides the per-file-type default",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="List files that would be scanned without running any analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    # Add performance flags to common args
    add_performance_flags(parser)


def add_complexity_args(parser: argparse.ArgumentParser) -> None:
    """Add complexity analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--cyclomatic-threshold",
        "-c",
        type=int,
        default=10,
        help="Cyclomatic complexity threshold (default: 10)",
    )
    parser.add_argument(
        "--cognitive-threshold",
        "-g",
        type=int,
        default=15,
        help="Cognitive complexity threshold (default: 15)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_duplication_args(parser: argparse.ArgumentParser) -> None:
    """Add duplication detection arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--min-lines",
        "-l",
        type=int,
        default=6,
        help="Minimum lines for a duplicate (default: 6)",
    )
    parser.add_argument(
        "--min-tokens",
        "-k",
        type=int,
        default=50,
        help="Minimum tokens for a duplicate (default: 50)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_smell_args(parser: argparse.ArgumentParser) -> None:
    """Add code smell detection arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_debt_args(parser: argparse.ArgumentParser) -> None:
    """Add technical debt analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--horizon",
        "-H",
        choices=["immediate", "short", "medium", "long"],
        default=None,
        help="Filter results to a specific remediation time horizon (default: all horizons)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_maintainability_args(parser: argparse.ArgumentParser) -> None:
    """Add maintainability analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )


def add_env_fallback_args(parser: argparse.ArgumentParser) -> None:
    """Add environment fallback scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_lazy_imports_args(parser: argparse.ArgumentParser) -> None:
    """Add lazy imports scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_security_args(parser: argparse.ArgumentParser) -> None:
    """Add security analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["info", "low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_performance_args(parser: argparse.ArgumentParser) -> None:
    """Add performance analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["info", "low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_oop_args(parser: argparse.ArgumentParser) -> None:
    """Add OOP analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--cbo-threshold",
        type=int,
        default=14,
        help="CBO threshold for high coupling (default: 14)",
    )
    parser.add_argument(
        "--lcom-threshold",
        type=float,
        default=0.8,
        help="LCOM threshold for poor cohesion (default: 0.8)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_deps_args(parser: argparse.ArgumentParser) -> None:
    """Add dependency analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "mermaid", "graphviz"],
        default="text",
        help="Output format: text, json, markdown, mermaid (.mmd), graphviz (.dot) (default: text)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum depth for dependency graph (default: 10)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--direction",
        "-d",
        choices=["LR", "TB", "RL", "BT"],
        default="LR",
        help="Graph direction for mermaid/graphviz output (default: LR)",
    )


def add_deps_export_args(parser: argparse.ArgumentParser) -> None:
    """Add dependency export arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--export-format",
        "-e",
        choices=["dot", "graphviz", "json", "mermaid"],
        default="mermaid",
        help="Export format for the dependency graph: mermaid (.mmd), graphviz/dot (.dot), json (default: mermaid)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: print to stdout)",
    )
    parser.add_argument(
        "--direction",
        "-d",
        choices=["LR", "TB", "RL", "BT"],
        default="LR",
        help="Graph direction for Mermaid/DOT output (default: LR)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_arch_args(parser: argparse.ArgumentParser) -> None:
    """Add architecture analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-solid",
        action="store_true",
        help="Skip SOLID principle validation",
    )
    parser.add_argument(
        "--no-layers",
        action="store_true",
        help="Skip layer analysis",
    )
    parser.add_argument(
        "--no-patterns",
        action="store_true",
        help="Skip design pattern detection",
    )
    parser.add_argument(
        "--hexagonal",
        action="store_true",
        help="Include hexagonal (ports and adapters) architecture analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_coverage_args(parser: argparse.ArgumentParser) -> None:
    """Add coverage analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--test-path",
        type=str,
        default=None,
        help="Path to the test directory to match against source methods (default: auto-detect)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods (prefixed with _) in coverage analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=10,
        help="Maximum number of test case suggestions to generate per run (default: 10)",
    )


def add_syntax_args(parser: argparse.ArgumentParser) -> None:
    """Add syntax checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--linters",
        nargs="+",
        choices=["ruff", "flake8", "pylint", "mypy"],
        default=["ruff"],
        help="Linters to run; multiple values allowed (default: ruff)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["error", "warning", "info", "style"],
        default="warning",
        help="Minimum severity level to report; lower levels are suppressed (default: warning)",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".py"],
        help="File extensions to include in the scan (default: .py)",
    )
    parser.add_argument(
        "--include-style",
        action="store_true",
        help="Include style-level issues in output (e.g. formatting, naming conventions)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_requirements_args(parser: argparse.ArgumentParser) -> None:
    """Add requirements checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--requirements-files",
        nargs="+",
        default=["requirements.txt"],
        help="One or more requirements files to validate (default: requirements.txt)",
    )
    parser.add_argument(
        "--no-check-unused",
        action="store_true",
        help="Do not report packages that are listed in requirements but never imported",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_licenses_args(parser: argparse.ArgumentParser) -> None:
    """Add license checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--allowed",
        nargs="+",
        default=None,
        help="License identifiers that are permitted (e.g. MIT Apache-2.0 BSD-3-Clause)",
    )
    parser.add_argument(
        "--denied",
        nargs="+",
        default=None,
        help="License identifiers that are forbidden; any match is reported as a violation",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_logic_args(parser: argparse.ArgumentParser) -> None:
    """Add logic analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_forbidden_imports_args(parser: argparse.ArgumentParser) -> None:
    """Add forbidden imports scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_datetime_args(parser: argparse.ArgumentParser) -> None:
    """Add datetime scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-check-utcnow",
        action="store_true",
        help="Skip checking for datetime.utcnow()",
    )
    parser.add_argument(
        "--no-check-now",
        action="store_true",
        help="Skip checking for datetime.now() without timezone",
    )
    parser.add_argument(
        "--no-check-today",
        action="store_true",
        help="Skip checking for datetime.today()",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_typing_args(parser: argparse.ArgumentParser) -> None:
    """Add typing coverage scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=80.0,
        help="Minimum typing coverage percentage (default: 80.0)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods (_method) in analysis",
    )
    parser.add_argument(
        "--include-dunder",
        action="store_true",
        help="Include dunder methods (__method__) in analysis",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_type_check_args(parser: argparse.ArgumentParser) -> None:
    """Add static type checking (Pyright/Pylance) arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to type-check (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["off", "basic", "standard", "strict", "all"],
        default="basic",
        help="Type checking strictness (default: basic). "
             "mypy: normal/strict map to basic/strict. "
             "pyright: off/basic/standard/strict/all.",
    )
    parser.add_argument(
        "--python-version",
        type=str,
        default="",
        help="Python version to target (e.g. 3.12). Auto-detected if not set.",
    )
    parser.add_argument(
        "--python-platform",
        type=str,
        default="",
        help="Python platform to target (e.g. Linux). Auto-detected if not set.",
    )
    parser.add_argument(
        "--venv-path",
        type=str,
        default="",
        help="Path to virtual environment for import resolution.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in analysis",
    )
    parser.add_argument(
        "--include-warnings",
        action="store_true",
        default=True,
        help="Include warnings in output (default: True)",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only errors (suppress warnings and info)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["error", "warning", "information"],
        default=None,
        help="Filter output to only this severity level",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[
            "type_mismatch", "missing_import", "undefined_variable",
            "argument_error", "return_type", "attribute_error",
            "assignment_error", "operator_error", "override_error",
            "generic_error", "protocol_error", "typed_dict_error",
            "overload_error", "unreachable_code", "deprecated", "general",
        ],
        default=None,
        help="Filter output to only this diagnostic category",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--npx-path",
        type=str,
        default="npx",
        help="Path to npx binary (default: npx, only used with --engine=pyright)",
    )
    parser.add_argument(
        "--engine",
        choices=["mypy", "pyright"],
        default="mypy",
        help="Type checking engine: mypy (default, pure Python) or pyright (Pylance engine, requires Node.js/npx)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Subprocess timeout in seconds (default: 300)",
    )


def add_thread_safety_args(parser: argparse.ArgumentParser) -> None:
    """Add thread safety scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["medium", "high"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_race_conditions_args(parser: argparse.ArgumentParser) -> None:
    """Add race condition scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_daemon_threads_args(parser: argparse.ArgumentParser) -> None:
    """Add daemon thread scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_future_leaks_args(parser: argparse.ArgumentParser) -> None:
    """Add future/promise leak scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_blocking_async_args(parser: argparse.ArgumentParser) -> None:
    """Add blocking-in-async scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_resource_cleanup_args(parser: argparse.ArgumentParser) -> None:
    """Add resource cleanup scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_error_handling_args(parser: argparse.ArgumentParser) -> None:
    """Add error handling coverage scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_config_secrets_args(parser: argparse.ArgumentParser) -> None:
    """Add config secrets scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high", "critical"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    parser.add_argument(
        "--entropy-threshold",
        type=float,
        default=3.5,
        help="Shannon entropy threshold for high-entropy string detection (default: 3.5)",
    )
    parser.add_argument(
        "--entropy-min-length",
        type=int,
        default=20,
        help="Minimum string length for entropy analysis (default: 20)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_baseline_args(parser: argparse.ArgumentParser) -> None:
    """Add baseline management arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project (default: current directory)",
    )
    parser.add_argument(
        "--baseline-file",
        "-b",
        type=str,
        default=".asgard-baseline.json",
        help="Path to the baseline JSON file (default: .asgard-baseline.json)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--type",
        "-t",
        type=str,
        default=None,
        help="Filter baseline entries by violation type (e.g. env-fallback, lazy-imports)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Filter baseline entries to those whose file path contains this pattern",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Unique violation ID to target; required when using the 'remove' subcommand",
    )


def add_documentation_args(parser: argparse.ArgumentParser) -> None:
    """Add documentation scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--min-comment-density",
        type=float,
        default=10.0,
        help="Minimum acceptable comment density percentage (default: 10.0)",
    )
    parser.add_argument(
        "--min-api-coverage",
        type=float,
        default=70.0,
        help="Minimum acceptable public API documentation coverage percentage (default: 70.0)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_naming_args(parser: argparse.ArgumentParser) -> None:
    """Add naming convention scanner arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-functions",
        action="store_true",
        help="Skip checking function and method names",
    )
    parser.add_argument(
        "--no-classes",
        action="store_true",
        help="Skip checking class names",
    )
    parser.add_argument(
        "--no-variables",
        action="store_true",
        help="Skip checking module-level variable names",
    )
    parser.add_argument(
        "--no-constants",
        action="store_true",
        help="Skip checking module-level constant names",
    )
    parser.add_argument(
        "--allow",
        type=str,
        nargs="+",
        default=[],
        dest="allow_list",
        help="Names to exclude from convention checking (exact matches)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_hotspots_args(parser: argparse.ArgumentParser) -> None:
    """Add security hotspot detection arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--priority",
        "-p",
        choices=["low", "medium", "high"],
        default="low",
        help="Minimum review priority to report (default: low)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_compliance_args(parser: argparse.ArgumentParser) -> None:
    """Add OWASP/CWE compliance reporting arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-owasp",
        action="store_true",
        help="Skip OWASP Top 10 compliance report",
    )
    parser.add_argument(
        "--no-cwe",
        action="store_true",
        help="Skip CWE Top 25 compliance report",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_ratings_args(parser: argparse.ArgumentParser) -> None:
    """Add A-E ratings calculator arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to rate (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Save the ratings result to the local history store (~/.asgard/history.db)",
    )


def add_gate_args(parser: argparse.ArgumentParser) -> None:
    """Add quality gate evaluation arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to evaluate (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--gate",
        type=str,
        default="asgard-way",
        help="Quality gate to use (default: asgard-way)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Save the gate result to the local history store (~/.asgard/history.db)",
    )


def add_ratings_history_flag(parser: argparse.ArgumentParser) -> None:
    """Add the --history flag to an existing ratings parser."""
    parser.add_argument(
        "--history",
        action="store_true",
        help="Save the ratings result to the local history store (~/.asgard/history.db)",
    )


def add_profiles_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the profiles command group."""
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_profile_assign_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles assign' subcommand."""
    parser.add_argument(
        "project_path",
        type=str,
        help="Absolute or relative path to the project root",
    )
    parser.add_argument(
        "profile_name",
        type=str,
        help="Name of the quality profile to assign",
    )


def add_profile_show_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles show' subcommand."""
    parser.add_argument(
        "name",
        type=str,
        help="Name of the quality profile to display",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_profile_create_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles create' subcommand."""
    parser.add_argument(
        "name",
        type=str,
        help="Name for the new quality profile",
    )
    parser.add_argument(
        "--parent",
        type=str,
        default=None,
        help="Name of the parent profile to inherit from",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        help="Target language for this profile (default: python)",
    )
    parser.add_argument(
        "--from-file",
        type=str,
        default=None,
        dest="from_file",
        help="Create the profile from a JSON file instead of prompting interactively",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Human-readable description of the profile",
    )


def add_history_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the history subcommands."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project to show history for (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of snapshots to display (default: 10)",
    )


def add_new_code_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the new-code detect subcommand."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project to analyse (default: current directory)",
    )
    parser.add_argument(
        "--since-date",
        type=str,
        default=None,
        help="Detect code changed since this date (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--since-branch",
        type=str,
        default=None,
        help="Detect code added since diverging from this branch",
    )
    parser.add_argument(
        "--since-version",
        type=str,
        default=None,
        help="Detect code changed since this tagged version",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_taint_args(parser: argparse.ArgumentParser) -> None:
    """Add taint flow analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["critical", "high", "medium", "low"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_bugs_args(parser: argparse.ArgumentParser) -> None:
    """Add bug detection arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--null-only",
        action="store_true",
        help="Run only null dereference detection",
    )
    parser.add_argument(
        "--unreachable-only",
        action="store_true",
        help="Run only unreachable code detection",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_js_args(parser: argparse.ArgumentParser) -> None:
    """Add JavaScript analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Additional patterns to exclude",
    )
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=500,
        help="Maximum file line count threshold (default: 500)",
    )
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=10,
        help="Cyclomatic complexity threshold multiplier (default: 10)",
    )
    parser.add_argument(
        "--disable",
        type=str,
        nargs="+",
        default=[],
        dest="disabled_rules",
        help="Rule IDs to disable",
    )



def add_ts_args(parser: argparse.ArgumentParser) -> None:
    """Add TypeScript analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Additional patterns to exclude",
    )
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=500,
        help="Maximum file line count threshold (default: 500)",
    )
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=10,
        help="Cyclomatic complexity threshold multiplier (default: 10)",
    )
    parser.add_argument(
        "--disable",
        type=str,
        nargs="+",
        default=[],
        dest="disabled_rules",
        help="Rule IDs to disable",
    )



def add_shell_args(parser: argparse.ArgumentParser) -> None:
    """Add shell script analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Additional patterns to exclude",
    )
    parser.add_argument(
        "--no-shebang-check",
        action="store_true",
        help="Do not include files with shell shebangs that lack .sh/.bash extension",
    )
    parser.add_argument(
        "--disable",
        type=str,
        nargs="+",
        default=[],
        dest="disabled_rules",
        help="Rule IDs to disable",
    )



def add_issues_args(parser: argparse.ArgumentParser) -> None:
    """Add common issue tracking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project root path (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--status",
        type=str,
        nargs="+",
        default=None,
        help="Filter by status (open, confirmed, resolved, closed, false_positive, wont_fix)",
    )
    parser.add_argument(
        "--severity",
        type=str,
        nargs="+",
        default=None,
        help="Filter by severity (critical, high, medium, low, info)",
    )
    parser.add_argument(
        "--rule",
        type=str,
        default=None,
        help="Filter by rule ID",
    )



def add_issue_update_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues update subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to update",
    )
    parser.add_argument(
        "--status",
        type=str,
        required=True,
        choices=["open", "confirmed", "resolved", "closed", "false_positive", "wont_fix"],
        help="New status to set",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default=None,
        help="Reason for the status change (required when marking false_positive)",
    )



def add_issue_assign_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues assign subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to assign",
    )
    parser.add_argument(
        "assignee",
        type=str,
        help="Username or email to assign the issue to",
    )



def add_issue_show_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues show subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to display",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )



def add_issue_summary_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues summary subcommand."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project root path (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )



def add_sbom_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the SBOM generation command."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project directory to scan for dependencies (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["spdx", "cyclonedx"],
        default="cyclonedx",
        help="SBOM output format (default: cyclonedx)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write SBOM JSON to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="",
        help="Override project name in the SBOM document",
    )
    parser.add_argument(
        "--project-version",
        type=str,
        default="",
        help="Project version to embed in the SBOM document",
    )



def add_codefix_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the codefix suggestion command."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project path to generate fix suggestions for (default: current directory)",
    )
    parser.add_argument(
        "--rule",
        type=str,
        default=None,
        dest="rule_id",
        help="Limit suggestions to a specific rule ID (e.g. quality.lazy_imports)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )



def add_mcp_server_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the MCP server command."""
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address to bind to (default: localhost)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        dest="project_path",
        help="Default project path for analysis tools (default: current directory)",
    )


def add_dashboard_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the dashboard command."""
    parser.add_argument(
        "--path",
        default=".",
        help="Project path to display in dashboard",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to serve dashboard on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not automatically open browser on launch",
    )
