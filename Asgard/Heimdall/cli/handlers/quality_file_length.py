import argparse
import json
from pathlib import Path

from Asgard.Heimdall.cli.common import SEVERITY_MARKERS
from Asgard.Heimdall.cli.handlers._base import _generate_quality_html_report
from Asgard.Heimdall.Quality.models.analysis_models import (
    AnalysisConfig,
    DEFAULT_EXTENSION_THRESHOLDS,
    SeverityLevel,
)
from Asgard.Heimdall.Quality.services.file_length_analyzer import FileAnalyzer
from Asgard.Heimdall.Quality.utilities.file_utils import discover_files


def run_quality_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    if getattr(args, 'dry_run', False):
        files = list(discover_files(scan_path, args.exclude if args.exclude else []))
        print(f"\nDry run: Would analyze {len(files)} files")
        for f in sorted(files)[:20]:
            print(f"  {f}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        return 0

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

    exclude_patterns = list(args.exclude) if args.exclude else []

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
