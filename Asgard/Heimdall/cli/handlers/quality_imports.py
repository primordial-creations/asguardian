import argparse
from pathlib import Path

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
)
from Asgard.Heimdall.Quality.services.library_usage_scanner import LibraryUsageScanner
from Asgard.Heimdall.Quality.models.datetime_models import DatetimeConfig
from Asgard.Heimdall.Quality.services.datetime_scanner import DatetimeScanner


def run_env_fallback_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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


def run_forbidden_imports_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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
