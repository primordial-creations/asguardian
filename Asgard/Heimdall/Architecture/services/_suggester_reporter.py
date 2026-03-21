"""
Heimdall Pattern Suggester Report Generation

Report generation helpers for PatternSuggester.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import PatternSuggestionReport


def generate_text_report(result: PatternSuggestionReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL PATTERN CANDIDATE SUGGESTIONS")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:          {result.scan_path}")
    lines.append(f"  Suggestions Found:  {result.total_suggestions}")
    lines.append(f"  Duration:           {result.scan_duration_seconds:.2f}s")
    lines.append("")

    if not result.suggestions:
        lines.append("  No pattern candidates found.")
        lines.append("  The codebase appears to already apply patterns appropriately,")
        lines.append("  or classes are small enough that patterns are not needed.")
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)

    for pattern_type, suggestions in result.suggestions_by_pattern.items():
        label = pattern_type.value.upper().replace("_", " ")
        lines.append("-" * 70)
        lines.append(f"  {label} PATTERN CANDIDATES  ({len(suggestions)} found)")
        lines.append("-" * 70)
        lines.append("")
        for s in suggestions:
            lines.append(f"  {s.class_name}  (confidence: {s.confidence:.0%})")
            lines.append(f"    File:    {s.file_path}:{s.line_number}")
            lines.append(f"    Why:     {s.rationale}")
            if s.signals:
                lines.append(f"    Signals: {'; '.join(s.signals)}")
            if s.benefit:
                lines.append(f"    Benefit: {s.benefit}")
            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: PatternSuggestionReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "total_suggestions": result.total_suggestions,
        "suggestions": [
            {
                "pattern_type": s.pattern_type.value,
                "class_name": s.class_name,
                "file_path": s.file_path,
                "line_number": s.line_number,
                "confidence": s.confidence,
                "rationale": s.rationale,
                "signals": s.signals,
                "benefit": s.benefit,
            }
            for s in result.suggestions
        ],
    }
    return json.dumps(output, indent=2)


def generate_markdown_report(result: PatternSuggestionReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Pattern Candidate Suggestions")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Total Suggestions:** {result.total_suggestions}")
    lines.append("")

    if not result.suggestions:
        lines.append(
            "_No pattern candidates found. The codebase appears to apply patterns "
            "appropriately, or classes are small enough that patterns are not needed._"
        )
        return "\n".join(lines)

    for pattern_type, suggestions in result.suggestions_by_pattern.items():
        lines.append(f"## {pattern_type.value.replace('_', ' ').title()} Candidates")
        lines.append("")
        for s in suggestions:
            lines.append(f"### `{s.class_name}` — {s.confidence:.0%} confidence")
            lines.append("")
            lines.append(f"**File:** `{s.file_path}:{s.line_number}`")
            lines.append("")
            lines.append(f"**Why:** {s.rationale}")
            lines.append("")
            if s.signals:
                lines.append("**Signals detected:**")
                for sig in s.signals:
                    lines.append(f"- {sig}")
                lines.append("")
            if s.benefit:
                lines.append(f"**Benefit:** {s.benefit}")
                lines.append("")

    return "\n".join(lines)
