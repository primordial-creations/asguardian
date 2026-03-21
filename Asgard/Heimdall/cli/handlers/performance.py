import argparse
from pathlib import Path

from Asgard.Heimdall.Performance.models.performance_models import (
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services.static_performance_service import StaticPerformanceService


def run_performance_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
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
