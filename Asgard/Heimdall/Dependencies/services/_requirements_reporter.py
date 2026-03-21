"""
Heimdall Requirements Checker - report generation helpers.

Standalone functions for generating text, JSON, and Markdown reports
from a RequirementsResult.
"""

import json

from Asgard.Heimdall.Dependencies.models.requirements_models import (
    RequirementsResult,
)


def generate_text_report(result: RequirementsResult) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL REQUIREMENTS CHECK REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:           {result.scan_path}")
    lines.append(f"  Scanned At:          {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration:            {result.scan_duration_seconds:.2f}s")
    lines.append(f"  Files Scanned:       {result.files_scanned}")
    lines.append(f"  Requirements Files:  {', '.join(result.requirements_files_found) or 'None found'}")
    lines.append("")

    if result.has_issues:
        lines.append("-" * 70)
        lines.append("  ISSUES FOUND")
        lines.append("-" * 70)
        lines.append("")

        missing = result.missing_packages
        if missing:
            lines.append(f"  [ERROR] Missing Packages ({len(missing)}):")
            lines.append("")
            for issue in missing:
                lines.append(f"    - {issue.package_name}")
                locs = issue.details.get("locations", [])[:3]
                for loc in locs:
                    lines.append(f"        Imported at: {loc}")
                if issue.details.get("total_imports", 0) > 3:
                    lines.append(f"        ... and {issue.details['total_imports'] - 3} more")
            lines.append("")

        unused = result.unused_packages
        if unused:
            lines.append(f"  [WARNING] Unused Packages ({len(unused)}):")
            lines.append("")
            for issue in unused:
                lines.append(f"    - {issue.package_name}")
                if "file" in issue.details:
                    lines.append(f"        In: {issue.details['file']}:{issue.details.get('line', '')}")
            lines.append("")
    else:
        lines.append("  All requirements are in sync!")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Total Requirements:  {result.total_requirements}")
    lines.append(f"  Unique Imports:      {result.total_imports}")
    lines.append(f"  Missing Packages:    {result.missing_count}")
    lines.append(f"  Unused Packages:     {result.unused_count}")
    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)


def generate_json_report(result: RequirementsResult) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "files_scanned": result.files_scanned,
        "requirements_files": result.requirements_files_found,
        "summary": {
            "total_requirements": result.total_requirements,
            "unique_imports": result.total_imports,
            "missing_count": result.missing_count,
            "unused_count": result.unused_count,
            "has_issues": result.has_issues,
        },
        "issues": [
            {
                "type": i.issue_type.value,
                "severity": i.severity.value,
                "package": i.package_name,
                "message": i.message,
                "details": i.details,
            }
            for i in result.issues
        ],
        "suggested_additions": result.get_suggested_additions(),
        "suggested_removals": result.get_suggested_removals(),
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: RequirementsResult) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Requirements Check Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append(f"- **Files Scanned:** {result.files_scanned}")
    lines.append(f"- **Requirements Files:** {', '.join(result.requirements_files_found) or 'None found'}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Requirements:** {result.total_requirements}")
    lines.append(f"- **Unique Imports:** {result.total_imports}")
    lines.append(f"- **Missing Packages:** {result.missing_count}")
    lines.append(f"- **Unused Packages:** {result.unused_count}")
    lines.append("")

    if result.has_issues:
        lines.append("## Issues")
        lines.append("")

        missing = result.missing_packages
        if missing:
            lines.append("### Missing Packages")
            lines.append("")
            lines.append("| Package | Imported At |")
            lines.append("|---------|-------------|")
            for issue in missing:
                locs = ", ".join(issue.details.get("locations", [])[:2])
                lines.append(f"| `{issue.package_name}` | {locs} |")
            lines.append("")

        unused = result.unused_packages
        if unused:
            lines.append("### Unused Packages")
            lines.append("")
            lines.append("| Package | Location |")
            lines.append("|---------|----------|")
            for issue in unused:
                loc = f"{issue.details.get('file', '')}:{issue.details.get('line', '')}"
                lines.append(f"| `{issue.package_name}` | {loc} |")
            lines.append("")

        if missing:
            lines.append("## Suggested Additions")
            lines.append("")
            lines.append("```")
            for pkg in result.get_suggested_additions():
                lines.append(pkg)
            lines.append("```")
            lines.append("")

    lines.append("")

    return "\n".join(lines)
