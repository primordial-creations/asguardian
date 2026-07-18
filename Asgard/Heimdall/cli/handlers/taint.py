import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintConfig
from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.cli.handlers._security_dispatch import _iter_code_files

#: Non-Python extensions the DispatchEngine's CST taint path supports.
#: `TaintAnalyzer` only walks the Python `ast`, so JS/TS/Java files never
#: reach it -- route those through the DispatchEngine instead and merge
#: the resulting flows into the same report.
_MULTILANG_TAINT_EXTENSIONS = frozenset({
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".java",
})


def _collect_multilang_flows(scan_path: Path, exclude_patterns):
    """Scan non-Python files via the DispatchEngine and return raw TaintFlows."""
    engine = DispatchEngine()
    flows = []
    files_seen = 0
    for path in _iter_code_files(
        scan_path, exclude_patterns, suffixes=_MULTILANG_TAINT_EXTENSIONS
    ):
        files_seen += 1
        result = engine.scan_file(path)
        flows.extend(result.taint_flows)
    return flows, files_seen


def run_taint_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
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

        multilang_flows, multilang_files = _collect_multilang_flows(
            scan_path, exclude_patterns
        )
        min_severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_rank = min_severity_order.get(severity_str, 0)
        for flow in multilang_flows:
            if min_severity_order.get(str(flow.severity).lower(), 0) < min_rank:
                continue
            report.flows.append(flow)
            report.total_flows += 1
            sev = str(flow.severity).lower()
            if sev == "critical":
                report.critical_count += 1
            elif sev == "high":
                report.high_count += 1
            elif sev == "medium":
                report.medium_count += 1
        report.files_analyzed += multilang_files

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
