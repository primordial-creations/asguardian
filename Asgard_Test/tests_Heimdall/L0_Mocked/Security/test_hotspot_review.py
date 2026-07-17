"""
Tests for the hotspot review workflow (plan 08 Part A).

SAFE_IN_CONTEXT requires mandatory justification; transitions are
audit-logged to Shared/Issues (issue_type security_hotspot); there is no
"Acknowledged Risk" status.
"""

import pytest

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)
from Asgard.Heimdall.Security.Hotspots.services.hotspot_review import (
    HotspotReviewError,
    review_hotspot,
    shared_issues_audit_sink,
)


def _hotspot():
    return SecurityHotspot(
        file_path="/src/crypto.py", line_number=10,
        category=HotspotCategory.WEAK_HASHING,
        review_priority=ReviewPriority.MEDIUM,
        title="Weak hash algorithm: hashlib.md5()",
    )


class TestReviewTransitions:
    def test_safe_in_context_requires_justification(self):
        hotspot = _hotspot()
        with pytest.raises(HotspotReviewError):
            review_hotspot(hotspot, ReviewStatus.SAFE_IN_CONTEXT)
        assert hotspot.review_status == ReviewStatus.TO_REVIEW.value

    def test_whitespace_justification_rejected(self):
        with pytest.raises(HotspotReviewError):
            review_hotspot(_hotspot(), ReviewStatus.SAFE_IN_CONTEXT, justification="   ")

    def test_safe_in_context_with_justification(self):
        hotspot = review_hotspot(
            _hotspot(), ReviewStatus.SAFE_IN_CONTEXT,
            justification="MD5 used for cache-key dedup only; no security role.",
        )
        assert hotspot.review_status == ReviewStatus.SAFE_IN_CONTEXT
        assert "cache-key" in hotspot.justification

    def test_fixed_requires_no_justification(self):
        hotspot = review_hotspot(_hotspot(), ReviewStatus.FIXED)
        assert hotspot.review_status == ReviewStatus.FIXED

    def test_reopen_from_fixed(self):
        hotspot = review_hotspot(_hotspot(), ReviewStatus.FIXED)
        hotspot = review_hotspot(hotspot, ReviewStatus.TO_REVIEW)
        assert hotspot.review_status == ReviewStatus.TO_REVIEW

    def test_invalid_transition_rejected(self):
        hotspot = review_hotspot(_hotspot(), ReviewStatus.FIXED)
        with pytest.raises(HotspotReviewError):
            review_hotspot(hotspot, ReviewStatus.SAFE_IN_CONTEXT, justification="x")


class TestAuditPersistence:
    class _FakeTracker:
        def __init__(self):
            self.issues = []

        def create_issue(self, issue):
            self.issues.append(issue)

    def test_transition_persisted_to_shared_issues(self):
        tracker = self._FakeTracker()
        sink = shared_issues_audit_sink(tracker)
        review_hotspot(
            _hotspot(), ReviewStatus.SAFE_IN_CONTEXT,
            justification="Checksum context only.",
            reviewer="alice",
            audit_sink=sink,
        )
        assert len(tracker.issues) == 1
        issue = tracker.issues[0]
        assert issue.issue_type == "security_hotspot"
        assert "Checksum context only." in issue.description
        assert "alice" in issue.description
        assert issue.file_path == "/src/crypto.py"

    def test_tracker_without_known_method_raises(self):
        sink = shared_issues_audit_sink(object())
        with pytest.raises(HotspotReviewError):
            review_hotspot(
                _hotspot(), ReviewStatus.FIXED, audit_sink=sink,
            )
