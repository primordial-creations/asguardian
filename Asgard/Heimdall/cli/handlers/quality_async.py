import argparse
from pathlib import Path

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


def run_future_leaks_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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


def run_resource_cleanup_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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
