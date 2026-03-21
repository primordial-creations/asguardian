import argparse
import json
from pathlib import Path

from Asgard.Reporting.History.services.history_store import HistoryStore


def run_history_command(args: argparse.Namespace, verbose: bool = False) -> int:
    history_command = getattr(args, "history_command", None)

    if history_command == "show":
        return _run_history_show(args, verbose)
    elif history_command == "trends":
        return _run_history_trends(args, verbose)
    else:
        print("Error: Please specify a history subcommand.")
        print("  show    Show analysis history for a project")
        print("  trends  Show metric trends for a project")
        return 1


def _run_history_show(args: argparse.Namespace, verbose: bool) -> int:
    scan_path = Path(getattr(args, "path", ".")).resolve()
    limit = getattr(args, "limit", 10)
    output_format = getattr(args, "format", "text")

    store = HistoryStore()
    snapshots = store.get_snapshots(str(scan_path), limit=limit)

    if output_format == "json":
        data = [
            {
                "snapshot_id": s.snapshot_id,
                "project_path": s.project_path,
                "scan_timestamp": s.scan_timestamp.isoformat(),
                "git_commit": s.git_commit,
                "git_branch": s.git_branch,
                "quality_gate_status": s.quality_gate_status,
                "ratings": s.ratings,
                "metrics": [{"name": m.metric_name, "value": m.value, "unit": m.unit} for m in s.metrics],
            }
            for s in snapshots
        ]
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  ANALYSIS HISTORY: {scan_path}")
    print("=" * 70)
    print("")

    if not snapshots:
        print("  No history recorded for this project.")
        print("  Run 'heimdall ratings ./src --history' to start recording.")
    else:
        for snap in snapshots:
            ts = snap.scan_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            gate = snap.quality_gate_status or "N/A"
            commit_str = f"  commit: {snap.git_commit[:8]}" if snap.git_commit else ""
            print(f"  {ts}  gate: {gate}{commit_str}")
            if verbose:
                for m in snap.metrics:
                    unit_str = f" {m.unit}" if m.unit else ""
                    print(f"    {m.metric_name}: {m.value:.2f}{unit_str}")
            print("")

    print("=" * 70)
    return 0


def _run_history_trends(args: argparse.Namespace, verbose: bool) -> int:
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    store = HistoryStore()
    trend_report = store.get_trend_report(str(scan_path))

    if output_format == "json":
        data = {
            "project_path": trend_report.project_path,
            "analysis_count": trend_report.analysis_count,
            "first_analysis": trend_report.first_analysis.isoformat() if trend_report.first_analysis else None,
            "last_analysis": trend_report.last_analysis.isoformat() if trend_report.last_analysis else None,
            "metric_trends": [
                {
                    "metric_name": t.metric_name,
                    "current_value": t.current_value,
                    "previous_value": t.previous_value,
                    "change": t.change,
                    "change_percentage": t.change_percentage,
                    "direction": str(t.direction),
                }
                for t in trend_report.metric_trends
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  METRIC TRENDS: {scan_path}")
    print("=" * 70)
    print("")
    print(f"  Total analyses recorded: {trend_report.analysis_count}")
    if trend_report.first_analysis:
        print(f"  First analysis: {trend_report.first_analysis.strftime('%Y-%m-%d')}")
    if trend_report.last_analysis:
        print(f"  Last analysis:  {trend_report.last_analysis.strftime('%Y-%m-%d')}")
    print("")

    if not trend_report.metric_trends:
        print("  Not enough history to calculate trends (need at least 2 snapshots).")
    else:
        print(f"  {'Metric':<40} {'Direction':<12} {'Change'}")
        print("  " + "-" * 65)
        for trend in trend_report.metric_trends:
            direction_str = str(trend.direction).upper()
            change_str = f"{trend.change_percentage:+.1f}% ({trend.change:+.2f})"
            print(f"  {trend.metric_name:<40} {direction_str:<12} {change_str}")
    print("")
    print("=" * 70)
    return 0
