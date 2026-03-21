import json
from typing import List

from Asgard.Heimdall.Quality.models.syntax_models import (
    LinterType,
    SyntaxResult,
    SyntaxSeverity,
)


def generate_text_report(result: SyntaxResult, linters_used: List[LinterType]) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL SYNTAX CHECK REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:    {result.scan_path}")
    lines.append(f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration:     {result.scan_duration_seconds:.2f}s")
    lines.append(f"  Linters:      {', '.join(l.value for l in linters_used)}")
    lines.append("")

    if result.has_issues:
        lines.append("-" * 70)
        lines.append("  ISSUES FOUND")
        lines.append("-" * 70)
        lines.append("")

        by_severity = result.get_issues_by_severity()

        for severity in [SyntaxSeverity.ERROR, SyntaxSeverity.WARNING, SyntaxSeverity.INFO]:
            issues = by_severity.get(severity.value, [])
            if issues:
                lines.append(f"  [{severity.value.upper()}] ({len(issues)} issues)")
                lines.append("")
                for issue in issues[:20]:
                    lines.append(f"    {issue.location}")
                    lines.append(f"      [{issue.code}] {issue.message}")
                    if issue.fixable:
                        lines.append(f"      (auto-fixable)")
                    lines.append("")
                if len(issues) > 20:
                    lines.append(f"    ... and {len(issues) - 20} more")
                    lines.append("")

    else:
        lines.append("  No syntax issues found!")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Files Scanned:      {result.total_files_scanned}")
    lines.append(f"  Files with Issues:  {result.files_with_issues}")
    lines.append(f"  Total Issues:       {result.total_issues}")
    lines.append(f"    Errors:           {result.total_errors}")
    lines.append(f"    Warnings:         {result.total_warnings}")
    lines.append(f"    Info:             {result.total_info}")
    lines.append(f"    Style:            {result.total_style}")
    lines.append(f"  Compliance Rate:    {result.compliance_rate:.1f}%")

    fixable = result.get_fixable_issues()
    if fixable:
        lines.append(f"  Auto-fixable:       {len(fixable)}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)


def generate_json_report(result: SyntaxResult, linters_used: List[LinterType]) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "linters": [l.value for l in linters_used],
        "summary": {
            "total_files_scanned": result.total_files_scanned,
            "files_with_issues": result.files_with_issues,
            "total_issues": result.total_issues,
            "errors": result.total_errors,
            "warnings": result.total_warnings,
            "info": result.total_info,
            "style": result.total_style,
            "compliance_rate": round(result.compliance_rate, 2),
            "fixable_count": len(result.get_fixable_issues()),
        },
        "files": [
            {
                "path": fa.relative_path,
                "issues": [
                    {
                        "line": i.line_number,
                        "column": i.column,
                        "code": i.code,
                        "message": i.message,
                        "severity": i.severity.value,
                        "linter": i.linter.value,
                        "fixable": i.fixable,
                    }
                    for i in fa.issues
                ],
            }
            for fa in result.file_analyses
            if fa.has_issues
        ],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: SyntaxResult, linters_used: List[LinterType]) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Syntax Check Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append(f"- **Linters:** {', '.join(l.value for l in linters_used)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Files Scanned:** {result.total_files_scanned}")
    lines.append(f"- **Files with Issues:** {result.files_with_issues}")
    lines.append(f"- **Total Issues:** {result.total_issues}")
    lines.append(f"  - Errors: {result.total_errors}")
    lines.append(f"  - Warnings: {result.total_warnings}")
    lines.append(f"  - Info: {result.total_info}")
    lines.append(f"  - Style: {result.total_style}")
    lines.append(f"- **Compliance Rate:** {result.compliance_rate:.1f}%")
    lines.append(f"- **Auto-fixable:** {len(result.get_fixable_issues())}")
    lines.append("")

    if result.has_issues:
        lines.append("## Issues")
        lines.append("")
        lines.append("| File | Line | Code | Severity | Message |")
        lines.append("|------|------|------|----------|---------|")

        for fa in result.file_analyses:
            for issue in fa.issues[:50]:
                lines.append(
                    f"| `{fa.relative_path}` | {issue.line_number} | "
                    f"{issue.code} | {issue.severity.value.upper()} | {issue.message[:50]} |"
                )

        if result.total_issues > 50:
            lines.append("")
            lines.append(f"*... and {result.total_issues - 50} more issues*")

    lines.append("")

    return "\n".join(lines)
