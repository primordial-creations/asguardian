"""
Heimdall Pattern Detector Report Generation

Report generation helpers for PatternDetector.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import PatternReport


def generate_text_report(result: PatternReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL DESIGN PATTERNS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:       {result.scan_path}")
    lines.append(f"  Patterns Found:  {result.total_patterns}")
    lines.append("")

    for pattern_type, matches in result.patterns_by_type.items():
        if matches:
            lines.append("-" * 70)
            lines.append(f"  {pattern_type.value.upper().replace('_', ' ')}")
            lines.append("-" * 70)
            lines.append("")

            for match in matches:
                lines.append(f"  {match.class_name}")
                lines.append(f"    File: {match.file_path}:{match.line_number}")
                lines.append(f"    Confidence: {match.confidence:.0%}")
                if match.participants:
                    lines.append(f"    Participants: {', '.join(match.participants)}")
                if match.details:
                    lines.append(f"    Details: {match.details}")
                lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: PatternReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "total_patterns": result.total_patterns,
        "patterns": [
            {
                "pattern_type": p.pattern_type.value,
                "class_name": p.class_name,
                "file_path": p.file_path,
                "line_number": p.line_number,
                "confidence": p.confidence,
                "participants": p.participants,
                "details": p.details,
            }
            for p in result.patterns
        ],
    }
    return json.dumps(output, indent=2)


def generate_markdown_report(result: PatternReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Design Patterns Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Patterns Found:** {result.total_patterns}")
    lines.append("")

    for pattern_type, matches in result.patterns_by_type.items():
        if matches:
            lines.append(f"## {pattern_type.value.replace('_', ' ').title()}")
            lines.append("")
            lines.append("| Class | File | Confidence | Details |")
            lines.append("|-------|------|------------|---------|")

            for match in matches:
                lines.append(
                    f"| {match.class_name} | {match.file_path}:{match.line_number} | "
                    f"{match.confidence:.0%} | {match.details} |"
                )

            lines.append("")

    return "\n".join(lines)
