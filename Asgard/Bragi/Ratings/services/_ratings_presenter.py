"""
Ratings Presenter (Plan 04 Phase C).

Turns a `FileQualityScore`/`ProjectRatings` into developer-trusted text:
fact-vs-inquiry rendering, channel-filtered finding sets, and a mandatory
rationale string (grade + top cap/driver + top ROI actions).

Pure functions, no I/O - consumed by `Heimdall/cli/handlers/ratings.py` and
`MCP/server/_mcp_tools.py`.
"""

from typing import Iterable, List, Optional

from Asgard.Bragi.Ratings.models._scoring_models import FileQualityScore, ROIAction
from Asgard.Bragi.Ratings.models.ratings_models import ChannelProfile, FindingClass

# Channel nesting order (Plan 04 Sec.3.3): ci_gate is the narrowest,
# dashboard the widest. Used for the monotonicity guarantee.
_CHANNEL_ORDER = [
    ChannelProfile.CI_GATE,
    ChannelProfile.PR_REVIEW,
    ChannelProfile.IDE,
    ChannelProfile.DASHBOARD,
]

# Minimum confidence (0-1) for a HEURISTIC finding to appear in pr_review.
PR_REVIEW_MIN_HEURISTIC_CONFIDENCE = 0.5


class RenderedFinding:
    """A finding annotated with its class, confidence, and channel floor."""

    __slots__ = ("rule_id", "message", "finding_class", "confidence", "min_channel")

    def __init__(
        self,
        rule_id: str,
        message: str,
        finding_class: FindingClass,
        confidence: float = 1.0,
        min_channel: ChannelProfile = ChannelProfile.CI_GATE,
    ):
        self.rule_id = rule_id
        self.message = message
        self.finding_class = finding_class
        self.confidence = confidence
        self.min_channel = min_channel

    def render(self) -> str:
        """Fact-vs-inquiry text rendering (DEEPTHINK_02)."""
        if self.finding_class == FindingClass.FACT or self.finding_class == FindingClass.FACT.value:
            return self.message
        pct = int(round(self.confidence * 100))
        return f"Low confidence ({pct}%): {self.message}"

    def visible_in(self, channel: ChannelProfile) -> bool:
        """
        Whether this finding surfaces in a given channel.

        ci_gate: FACT only. pr_review: FACT + HEURISTIC >= threshold. ide
        and dashboard: everything (dashboard additionally carries
        suppressed findings and trend deltas upstream, not modeled here).
        """
        is_fact = self.finding_class in (FindingClass.FACT, FindingClass.FACT.value)
        if channel == ChannelProfile.CI_GATE or channel == ChannelProfile.CI_GATE.value:
            return is_fact
        if channel == ChannelProfile.PR_REVIEW or channel == ChannelProfile.PR_REVIEW.value:
            return is_fact or self.confidence >= PR_REVIEW_MIN_HEURISTIC_CONFIDENCE
        return True  # ide, dashboard: full set


def filter_by_channel(
    findings: Iterable[RenderedFinding], channel: ChannelProfile
) -> List[RenderedFinding]:
    """Filter a finding list down to what a given channel should show."""
    return [f for f in findings if f.visible_in(channel)]


def assert_channel_monotonicity(findings: Iterable[RenderedFinding]) -> bool:
    """
    Property check: ci_gate finding set subset-of pr_review subset-of ide
    subset-of dashboard for the same input. Returns True when satisfied.
    """
    findings = list(findings)
    sets = [set(id(f) for f in filter_by_channel(findings, ch)) for ch in _CHANNEL_ORDER]
    return all(sets[i] <= sets[i + 1] for i in range(len(sets) - 1))


def render_rationale(score: FileQualityScore, top_n_actions: int = 3) -> str:
    """
    Mandatory rationale string (Plan 04 Sec.3.3): grade + top cap/driver +
    top-N ROI actions, e.g.
    "B - held back by duplication (12.4%); best next action: extract
    `parse_config` clone family, +0.03"
    """
    parts = [score.grade]
    if score.cap.applied:
        parts.append(f"held back by {score.cap.reason}")
    elif score.rationale:
        parts.append(score.rationale)

    actions = sorted(score.roi_actions, key=lambda a: a.score_delta, reverse=True)[:top_n_actions]
    if actions:
        top = actions[0]
        parts.append(f"best next action: {top.description}, +{top.score_delta:.2f}")

    return " - ".join(parts)


def render_top_roi_actions(actions: List[ROIAction], top_n: int = 3) -> List[str]:
    """Render the top-N ROI actions as human-readable strings."""
    ranked = sorted(actions, key=lambda a: a.score_delta, reverse=True)[:top_n]
    return [f"{a.description} (+{a.score_delta:.2f})" for a in ranked]
