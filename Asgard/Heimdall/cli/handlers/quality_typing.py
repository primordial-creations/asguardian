import argparse
from pathlib import Path

from Asgard.Heimdall.Quality.models.typing_models import TypingConfig
from Asgard.Heimdall.Quality.services.typing_scanner import TypingScanner
from Asgard.Heimdall.Quality.models.type_check_models import TypeCheckConfig
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


def run_typing_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    user_excludes = list(args.exclude) if args.exclude else []

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
