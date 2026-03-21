import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from Asgard.Heimdall.cli.handlers._base import _save_html_report, _open_in_browser
from Asgard.Heimdall.cli.handlers.scan_html import (
    _detail_str,
    _generate_scan_html_report,
    _SCAN_DISPLAY_NAMES,
)
from Asgard.Heimdall.cli.handlers.scan_steps import (
    _run_scan_steps_1_to_6,
    _run_scan_steps_7_to_11,
)


def run_full_scan(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    output_format = getattr(args, "format", "text")
    exclude_patterns = list(args.exclude) if getattr(args, "exclude", None) else []
    include_tests = getattr(args, "include_tests", False)
    start_time = datetime.now()

    scan_excludes = [
        "__pycache__", "node_modules", ".git", ".venv", "venv",
        "build", "dist", "assets", "*-venv", "site-packages",
        "android", ".gradle", ".next", "coverage", ".tox",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "*.egg-info", "_*",
    ]
    for pattern in exclude_patterns:
        if pattern not in scan_excludes:
            scan_excludes.append(pattern)
    exclude_patterns = scan_excludes

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    scan_results = {}
    overall_exit = 0
    step_reports: dict = {}

    print("=" * 70, flush=True)
    print("  HEIMDALL FULL SCAN", flush=True)
    print("  Running all analysis categories...", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)

    exit_1_to_6 = _run_scan_steps_1_to_6(
        scan_path=scan_path,
        exclude_patterns=exclude_patterns,
        include_tests=include_tests,
        output_format=output_format,
        verbose=verbose,
        scan_results=scan_results,
        step_reports=step_reports,
    )
    if exit_1_to_6:
        overall_exit = 1

    exit_7_to_11 = _run_scan_steps_7_to_11(
        scan_path=scan_path,
        exclude_patterns=exclude_patterns,
        include_tests=include_tests,
        verbose=verbose,
        scan_results=scan_results,
        step_reports=step_reports,
    )
    if exit_7_to_11:
        overall_exit = 1

    duration = (datetime.now() - start_time).total_seconds()

    print()
    print("=" * 70)
    print("  SCAN COMPLETE")
    print("=" * 70)
    print()
    print(f"  Path:     {scan_path}")
    print(f"  Duration: {duration:.1f}s")
    print()

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

    html_report = _generate_scan_html_report(
        scan_results=scan_results,
        step_reports=step_reports,
        scan_path=str(scan_path),
        duration=duration,
        scanned_at=start_time,
    )
    report_path = _save_html_report(html_report, "Heimdall Full Scan")
    print(f"Report saved: {report_path}", file=sys.__stdout__)
    if getattr(args, "open_browser", False):
        _open_in_browser(report_path)

    return overall_exit
