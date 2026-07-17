"""
PR hotspot summary with volume guard (plan 08 Part A).

Hotspots are reviewed only on NEW code in PR scans (exception-only
philosophy) — never used to block legacy bulk scans. If more than
``PR_HOTSPOT_CAP`` (5) hotspots would attach to one PR, they collapse to
a single summary comment: >5 inline comments is where bulk "Mark as
Safe" malicious compliance begins (DEEPTHINK_10).

This module is deliberately transport-agnostic (plain strings); wiring
into ``Reporting/PRDecoration`` is owned by the reporting slice.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    PR_HOTSPOT_CAP,
    SecurityHotspot,
)


@dataclass
class HotspotPRComments:
    """Inline comments and/or a single summary comment for a PR."""
    inline: List[str] = field(default_factory=list)
    summary: str = ""
    collapsed: bool = False


def _format_inline(hotspot: SecurityHotspot) -> str:
    priority = getattr(hotspot.review_priority, "value", hotspot.review_priority)
    return (
        f"[{str(priority).upper()}] Security hotspot: {hotspot.title}\n"
        f"{hotspot.file_path}:{hotspot.line_number}\n"
        f"{hotspot.description}\n"
        f"Review guidance: {hotspot.review_guidance}"
    )


def build_pr_hotspot_comments(
    hotspots: Sequence[SecurityHotspot],
    cap: int = PR_HOTSPOT_CAP,
) -> HotspotPRComments:
    """
    Build PR decoration comments with the volume guard applied.

    - suppressed-by-context hotspots never decorate a PR;
    - up to ``cap`` hotspots: one inline comment each, no summary;
    - more than ``cap``: zero inline comments, one summary comment.
    """
    active = [h for h in hotspots if not h.suppressed_by_context]
    if not active:
        return HotspotPRComments()

    if len(active) <= cap:
        return HotspotPRComments(inline=[_format_inline(h) for h in active])

    by_category: Dict[str, int] = {}
    for h in active:
        category = getattr(h.category, "value", h.category)
        by_category[str(category)] = by_category.get(str(category), 0) + 1
    lines = [
        f"Security hotspots: {len(active)} patterns need manual review "
        f"(collapsed — above the {cap}-comment threshold).",
        "",
    ]
    for category, count in sorted(by_category.items()):
        lines.append(f"- {category}: {count}")
    lines += [
        "",
        "Run `asgard heimdall hotspots <path>` for the full list. Each item "
        "requires an individual SAFE_IN_CONTEXT justification or a fix — "
        "bulk-marking is not available by design.",
    ]
    return HotspotPRComments(summary="\n".join(lines), collapsed=True)
