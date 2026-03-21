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
    add_performance_flags(parser)


def add_ratings_history_flag(parser: argparse.ArgumentParser) -> None:
    """Add the --history flag to an existing ratings parser."""
    parser.add_argument(
        "--history",
        action="store_true",
        help="Save the ratings result to the local history store (~/.asgard/history.db)",
    )
