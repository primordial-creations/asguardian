"""
Versioning Helpers - algorithmic SemVer recommendation, migration-guide
scaffolding, and Keep-a-Changelog-style structured changelogs, all
computed from the unified Compatibility engine's diff output (plan 04,
RESEARCH_03 / DEEPTHINK_07).
"""

import re
from typing import Any, Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import TierVerdict
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Contracts.models.contract_models import (
    Bump,
    VersionRecommendation,
)

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")

# Additive change kinds that never break old clients: MINOR territory.
_ADDITIVE_HINTS = ("ADDED", "EXTENDED")


def parse_semver(version: Optional[str]) -> Optional[tuple[int, int, int]]:
    """Parse 'MAJOR.MINOR.PATCH' (optional leading v); None when invalid."""
    if not version:
        return None
    match = _SEMVER_RE.match(version.strip())
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def classify_bump(changes: list[UnifiedChange]) -> tuple[Bump, list[str]]:
    """
    Map unified changes onto a bump level.

    Any structural FAIL (unwaived, not lifecycle-neutralised) => MAJOR.
    Semantic hazards or additive surface => MINOR. Otherwise PATCH.
    """
    reasons: list[str] = []
    bump = Bump.PATCH
    for change in changes:
        if change.waived or change.base_severity == 0:
            continue
        if change.impact.structural == TierVerdict.FAIL:
            reasons.append(f"{change.rule_id} @ {change.location}")
            bump = Bump.MAJOR
    if bump == Bump.MAJOR:
        return bump, reasons
    for change in changes:
        if change.waived or change.base_severity == 0:
            continue
        additive = any(h in change.rule_id for h in _ADDITIVE_HINTS)
        if change.impact.semantic == TierVerdict.HAZARD or additive:
            reasons.append(f"{change.rule_id} @ {change.location}")
            bump = Bump.MINOR
    return bump, reasons


def recommend_version(
    changes: list[UnifiedChange],
    current_version: Optional[str] = None,
) -> VersionRecommendation:
    """
    Algorithmic SemVer recommendation (RESEARCH_03 §7).

    Pre-1.0 ('0.x') downgrades MAJOR to MINOR: SemVer item 4 declares the
    public API unstable before 1.0.0.
    """
    bump, reasons = classify_bump(changes)
    parsed = parse_semver(current_version)
    pre_stability = bool(parsed and parsed[0] == 0)
    if pre_stability and bump == Bump.MAJOR:
        bump = Bump.MINOR
        reasons.append("0.x pre-stability: MAJOR downgraded to MINOR (SemVer item 4)")
    recommended: Optional[str] = None
    if parsed:
        major, minor, patch = parsed
        if bump == Bump.MAJOR:
            recommended = f"{major + 1}.0.0"
        elif bump == Bump.MINOR:
            recommended = f"{major}.{minor + 1}.0"
        else:
            recommended = f"{major}.{minor}.{patch + 1}"
    return VersionRecommendation(
        current=current_version,
        recommended_bump=bump,
        recommended_version=recommended,
        reasons=reasons,
        pre_stability=pre_stability,
    )


# ---------------------------------------------------------------------------
# Migration guide + structured changelog (DEEPTHINK_07 §1)
# ---------------------------------------------------------------------------

def _sorted_changes(changes: list[UnifiedChange]) -> list[UnifiedChange]:
    """Stable ordering for golden-file friendliness."""
    return sorted(changes, key=lambda c: (c.rule_id, c.location, c.message))


def _change_group(change: UnifiedChange) -> str:
    """Keep-a-Changelog section for a change."""
    if "deprecated" in change.message.lower() and change.base_severity == 0:
        return "Deprecated"
    if change.impact.structural == TierVerdict.FAIL and not change.waived:
        return "Breaking"
    if any(h in change.rule_id for h in _ADDITIVE_HINTS):
        return "Added"
    if change.impact.semantic == TierVerdict.HAZARD:
        return "Changed"
    return "Fixed"


def generate_migration_guide(
    changes: list[UnifiedChange],
    version: str = "next",
    lifecycle: Optional[dict[str, Any]] = None,
) -> str:
    """
    Markdown migration-guide scaffold from the mechanical diff.

    The 'what' is generated; the human 'why' is left as TODO blocks.
    """
    lifecycle = lifecycle or {}
    lines = [f"# Migrating to {version}", ""]
    relevant = [c for c in _sorted_changes(changes)
                if not c.waived and (c.impact.structural == TierVerdict.FAIL
                                     or c.impact.semantic == TierVerdict.HAZARD
                                     or c.base_severity == 0)]
    if not relevant:
        lines.append("No consumer-visible changes require migration.")
        return "\n".join(lines) + "\n"
    for change in relevant:
        title = change.rule_id.replace("-", " ").title().replace("Oas ", "")
        lines.append(f"## {change.rule_id}: `{change.location}`")
        lines.append(f"- **Change**: {change.message}")
        if change.old_value is not None or change.new_value is not None:
            lines.append(
                f"- **Mechanical change**: `{change.old_value!r}` ⇒ "
                f"`{change.new_value!r}`"
            )
        meta = lifecycle.get(change.location)
        replaced_by = getattr(meta, "replaced_by", None) if meta else None
        if replaced_by:
            lines.append(f"- **Replaced by**: `{replaced_by}` (`x-replaced-by`)")
        guide = getattr(meta, "migration_guide", None) if meta else None
        if guide:
            lines.append(f"- **Producer guide**: {guide}")
        if change.mitigation:
            lines.append(f"- **Suggested mitigation**: {change.mitigation}")
        lines.append("- <!-- TODO(author): business context for this change -->")
        lines.append("")
        _ = title
    return "\n".join(lines).rstrip() + "\n"


def generate_structured_changelog(
    changes: list[UnifiedChange],
    version: str = "next",
) -> str:
    """Grouped Keep-a-Changelog Markdown; entries carry rule id + location."""
    lines = [f"## [{version}]", ""]
    groups: dict[str, list[UnifiedChange]] = {}
    for change in _sorted_changes(changes):
        groups.setdefault(_change_group(change), []).append(change)
    if not groups:
        lines.append("No changes detected.")
        return "\n".join(lines) + "\n"
    for section in ("Breaking", "Deprecated", "Added", "Changed", "Fixed"):
        section_changes = groups.get(section)
        if not section_changes:
            continue
        lines.append(f"### {section}")
        for change in section_changes:
            waived = " *(waived)*" if change.waived else ""
            lines.append(
                f"- **`{change.location}`** — {change.message} "
                f"[`{change.rule_id}`]{waived}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
