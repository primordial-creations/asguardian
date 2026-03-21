"""
Baseline Manager - Report Formatting

Text and Markdown report formatters for baseline entries.
"""

from pathlib import Path

from Asgard.Baseline.models import BaselineFile, BaselineStats


def format_text_report(
    baseline: BaselineFile,
    stats: BaselineStats,
    baseline_path: Path,
) -> str:
    """Format baseline report as text."""
    lines = [
        "=" * 60,
        "BASELINE REPORT",
        "=" * 60,
        "",
        f"Baseline File: {baseline_path}",
        f"Created: {baseline.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Updated: {baseline.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Entries: {stats.total_entries}",
        f"Active: {stats.active_entries}",
        f"Expired: {stats.expired_entries}",
        "",
    ]

    if stats.entries_by_type:
        lines.extend(["By Type:", "-" * 20])
        for vtype, count in sorted(stats.entries_by_type.items()):
            lines.append(f"  {vtype}: {count}")
        lines.append("")

    if stats.entries_by_file:
        lines.extend(["Top Files:", "-" * 20])
        top_files = sorted(stats.entries_by_file.items(), key=lambda x: x[1], reverse=True)[:10]
        for fpath, count in top_files:
            lines.append(f"  {fpath}: {count}")
        lines.append("")

    if baseline.entries:
        lines.extend(["ENTRIES", "-" * 40])
        for entry in baseline.entries[:30]:
            status = "[EXPIRED]" if entry.is_expired else ""
            lines.append(f"  {entry.file_path}:{entry.line_number} [{entry.violation_type}] {status}")
        if len(baseline.entries) > 30:
            lines.append(f"  ... and {len(baseline.entries) - 30} more")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_markdown_report(
    baseline: BaselineFile,
    stats: BaselineStats,
    baseline_path: Path,
) -> str:
    """Format baseline report as markdown."""
    lines = [
        "# Baseline Report",
        "",
        f"**Baseline File:** `{baseline_path}`",
        f"**Created:** {baseline.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Updated:** {baseline.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Entries | {stats.total_entries} |",
        f"| Active | {stats.active_entries} |",
        f"| Expired | {stats.expired_entries} |",
        "",
    ]

    if stats.entries_by_type:
        lines.extend([
            "## By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for vtype, count in sorted(stats.entries_by_type.items()):
            lines.append(f"| {vtype} | {count} |")
        lines.append("")

    if baseline.entries:
        lines.extend([
            "## Entries",
            "",
            "| File | Line | Type | Status |",
            "|------|------|------|--------|",
        ])
        for entry in baseline.entries[:50]:
            status = "Expired" if entry.is_expired else "Active"
            lines.append(f"| `{entry.file_path}` | {entry.line_number} | {entry.violation_type} | {status} |")

    return "\n".join(lines)
