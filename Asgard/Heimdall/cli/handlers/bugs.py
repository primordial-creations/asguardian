import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import BugDetectionConfig
from Asgard.Heimdall.Quality.BugDetection.services.bug_detector import BugDetector


def run_bugs_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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
