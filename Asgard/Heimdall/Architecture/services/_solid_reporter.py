"""
Heimdall SOLID Validator Report Generation

Report generation helpers for SOLIDValidator.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import (
    SOLIDPrinciple,
    SOLIDReport,
)


def generate_text_report(result: SOLIDReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL SOLID PRINCIPLES REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:      {result.scan_path}")
    lines.append(f"  Total Classes:  {result.total_classes}")
    lines.append(f"  Total Violations: {result.total_violations}")
    lines.append("")

    for principle in SOLIDPrinciple:
        violations = result.violations_by_principle[principle]
        if violations:
            lines.append("-" * 70)
            lines.append(f"  {violations[0].principle_name}")
            lines.append("-" * 70)
            lines.append("")

            for v in violations:
                lines.append(f"  [{v.severity.value.upper()}] {v.class_name}")
                lines.append(f"    File: {v.file_path}:{v.line_number}")
                lines.append(f"    {v.message}")
                if v.suggestion:
                    lines.append(f"    Suggestion: {v.suggestion}")
                lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: SOLIDReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "total_classes": result.total_classes,
        "total_violations": result.total_violations,
        "violations": [
            {
                "principle": v.principle.value,
                "class_name": v.class_name,
                "file_path": v.file_path,
                "line_number": v.line_number,
                "message": v.message,
                "severity": v.severity.value,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ],
    }
    return json.dumps(output, indent=2)


def generate_markdown_report(result: SOLIDReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall SOLID Principles Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Total Classes:** {result.total_classes}")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append("")

    for principle in SOLIDPrinciple:
        violations = result.violations_by_principle[principle]
        if violations:
            lines.append(f"## {violations[0].principle_name}")
            lines.append("")
            lines.append("| Class | File | Message | Severity |")
            lines.append("|-------|------|---------|----------|")

            for v in violations:
                lines.append(
                    f"| {v.class_name} | {v.file_path}:{v.line_number} | "
                    f"{v.message} | {v.severity.value.upper()} |"
                )

            lines.append("")

    return "\n".join(lines)
