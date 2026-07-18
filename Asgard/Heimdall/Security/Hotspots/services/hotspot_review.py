"""
Hotspot review workflow (plan 08 Part A).

Statuses: TO_REVIEW -> SAFE_IN_CONTEXT | FIXED.

SAFE_IN_CONTEXT requires mandatory justification text, persisted to the
Shared/Issues audit log (issue_type ``security_hotspot``). There is
deliberately no "Acknowledged Risk" status: risk acceptance belongs in a
GRC/ticket system; a scanner UI granting it creates discoverable-
negligence liability (DEEPTHINK_10 s4).
"""

import uuid
from datetime import datetime
from typing import Callable, Optional

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    ReviewStatus,
    SecurityHotspot,
)


class HotspotReviewError(ValueError):
    """Raised on an invalid review transition."""


_ALLOWED_TRANSITIONS = {
    ReviewStatus.TO_REVIEW: {ReviewStatus.SAFE_IN_CONTEXT, ReviewStatus.FIXED},
    ReviewStatus.SAFE_IN_CONTEXT: {ReviewStatus.TO_REVIEW, ReviewStatus.FIXED},
    ReviewStatus.FIXED: {ReviewStatus.TO_REVIEW},
}


def review_hotspot(
    hotspot: SecurityHotspot,
    new_status: ReviewStatus,
    justification: str = "",
    reviewer: str = "",
    audit_sink: Optional[Callable[[SecurityHotspot, str, str], None]] = None,
) -> SecurityHotspot:
    """
    Transition a hotspot's review status.

    - ``SAFE_IN_CONTEXT`` REQUIRES non-empty justification text; the
      transition is rejected otherwise.
    - ``audit_sink(hotspot, justification, reviewer)`` is invoked on every
      successful transition; the default sink persists to Shared/Issues
      (see :func:`shared_issues_audit_sink`).
    """
    new_status = ReviewStatus(new_status)
    current = ReviewStatus(hotspot.review_status)

    if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise HotspotReviewError(
            f"Invalid review transition: {current.value} -> {new_status.value}"
        )
    if new_status is ReviewStatus.SAFE_IN_CONTEXT and not justification.strip():
        raise HotspotReviewError(
            "SAFE_IN_CONTEXT requires mandatory justification text explaining "
            "the extrinsic context that makes this code safe."
        )

    hotspot.review_status = new_status
    hotspot.justification = justification.strip()
    if audit_sink is not None:
        audit_sink(hotspot, justification.strip(), reviewer)
    return hotspot


def shared_issues_audit_sink(tracker) -> Callable[[SecurityHotspot, str, str], None]:
    """
    Build an audit sink persisting review transitions to Shared/Issues.

    ``tracker`` is any object with a ``create_issue`` / ``add_issue``-style
    API accepting a TrackedIssue; Heimdall does not import a concrete
    store here so the persistence backend stays pluggable.
    """
    from Asgard.Shared.Issues.models.issue_models import (
        IssueSeverity,
        IssueType,
        TrackedIssue,
    )

    def _sink(hotspot: SecurityHotspot, justification: str, reviewer: str) -> None:
        status = hotspot.review_status
        status_value = status.value if isinstance(status, ReviewStatus) else str(status)
        description = (
            f"Hotspot review transition -> {status_value}."
            + (f" Reviewer: {reviewer}." if reviewer else "")
            + (f" Justification: {justification}" if justification else "")
        )
        now = datetime.now()
        issue = TrackedIssue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.SECURITY_HOTSPOT,
            severity=IssueSeverity.INFO,
            title=f"[hotspot-review] {hotspot.title}",
            description=description,
            file_path=hotspot.file_path,
            line_number=hotspot.line_number,
            rule_id=f"hotspot.{hotspot.category}",
            first_detected=now,
            last_seen=now,
        )
        for method in ("create_issue", "add_issue", "track_issue", "save_issue"):
            fn = getattr(tracker, method, None)
            if callable(fn):
                fn(issue)
                return
        raise HotspotReviewError(
            "Audit tracker exposes no create_issue/add_issue/track_issue/save_issue method"
        )

    return _sink
