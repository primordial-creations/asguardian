import json

from Asgard.Heimdall.Quality.models.duplication_models import (
    DuplicationResult,
)


def generate_text_report(result: DuplicationResult) -> str:
    """Generate plain text duplication report."""
    lines = [
        "=" * 70,
        "  HEIMDALL DUPLICATION DETECTION REPORT",
        "=" * 70,
        "",
        f"  Scan Path:    {result.scan_path}",
        f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Duration:     {result.scan_duration_seconds:.2f}s",
        "",
        "-" * 70,
        "  SUMMARY",
        "-" * 70,
        "",
        f"  Files Scanned:        {result.total_files_scanned}",
        f"  Blocks Analyzed:      {result.total_blocks_analyzed}",
        f"  Clone Families:       {result.total_clone_families}",
        f"  Duplicated Lines:     {result.total_duplicated_lines}",
        f"  Duplication:          {result.duplication_percentage:.1f}%",
        f"  Min Block Size:       {result.min_block_size} lines",
        "",
    ]

    if result.has_duplicates:
        lines.extend(["-" * 70, "  CLONE FAMILIES (worst first)", "-" * 70, ""])
        for i, family in enumerate(result.worst_families, 1):
            sev = family.severity if isinstance(family.severity, str) else family.severity.value
            mtype = family.match_type if isinstance(family.match_type, str) else family.match_type.value
            lines.append(f"  Family {i}: [{sev.upper()}] {mtype} ({family.block_count} copies, {family.total_duplicated_lines} lines)")
            for block in family.blocks[:5]:
                lines.append(f"    {block.relative_path}:{block.start_line}-{block.end_line}")
            if len(family.blocks) > 5:
                lines.append(f"    ... and {len(family.blocks) - 5} more")
            lines.append("")

        if result.files_with_duplicates:
            lines.extend(["-" * 70, "  FILES WITH DUPLICATES", "-" * 70, ""])
            for f in result.files_with_duplicates[:20]:
                lines.append(f"  {f}")
            lines.append("")
    else:
        lines.extend(["  No code duplication detected.", ""])

    lines.extend(["=" * 70, ""])
    return "\n".join(lines)


def generate_json_report(result: DuplicationResult) -> str:
    """Generate JSON duplication report."""
    families_data = []
    for family in result.clone_families:
        blocks_data = [
            {
                "file_path": b.file_path,
                "relative_path": b.relative_path,
                "start_line": b.start_line,
                "end_line": b.end_line,
                "line_count": b.line_count,
            }
            for b in family.blocks
        ]
        families_data.append({
            "match_type": family.match_type if isinstance(family.match_type, str) else family.match_type.value,
            "severity": family.severity if isinstance(family.severity, str) else family.severity.value,
            "block_count": family.block_count,
            "total_duplicated_lines": family.total_duplicated_lines,
            "average_similarity": round(family.average_similarity, 3),
            "blocks": blocks_data,
        })

    report_data = {
        "scan_info": {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "duration_seconds": result.scan_duration_seconds,
            "min_block_size": result.min_block_size,
            "similarity_threshold": result.similarity_threshold,
        },
        "summary": {
            "total_files_scanned": result.total_files_scanned,
            "total_blocks_analyzed": result.total_blocks_analyzed,
            "total_clone_families": result.total_clone_families,
            "total_duplicated_lines": result.total_duplicated_lines,
            "duplication_percentage": round(result.duplication_percentage, 2),
            "files_with_duplicates": result.files_with_duplicates,
        },
        "clone_families": families_data,
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(result: DuplicationResult) -> str:
    """Generate Markdown duplication report."""
    lines = [
        "# Heimdall Duplication Detection Report",
        "",
        f"**Scan Path:** `{result.scan_path}`",
        f"**Generated:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {result.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"**Files Scanned:** {result.total_files_scanned}",
        f"**Clone Families:** {result.total_clone_families}",
        f"**Duplicated Lines:** {result.total_duplicated_lines}",
        f"**Duplication Percentage:** {result.duplication_percentage:.1f}%",
        "",
    ]

    if result.has_duplicates:
        lines.extend([
            "## Clone Families",
            "",
            "| # | Type | Severity | Copies | Lines | Similarity |",
            "|---|------|----------|--------|-------|------------|",
        ])
        for i, family in enumerate(result.worst_families, 1):
            sev = family.severity if isinstance(family.severity, str) else family.severity.value
            mtype = family.match_type if isinstance(family.match_type, str) else family.match_type.value
            lines.append(f"| {i} | {mtype} | {sev} | {family.block_count} | {family.total_duplicated_lines} | {family.average_similarity:.0%} |")
        lines.append("")

        if result.files_with_duplicates:
            lines.extend(["## Files With Duplicates", ""])
            for f in result.files_with_duplicates[:20]:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.extend(["No code duplication detected.", ""])

    return "\n".join(lines)
