"""
Freya Spatial Focus-Order Tests

L0 tests for the pure spatial focus-order analysis (DEEPTHINK_01).
"""

import pytest

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    KeyboardIssueType,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services._focus_order_spatial import (
    analyze_focus_order_spatial,
    centers_from_focusables,
    count_focus_order_regressions,
)


def _row(y, xs):
    return [{"x": float(x), "y": float(y)} for x in xs]


class TestCountRegressions:
    def test_clean_reading_flow(self):
        centers = _row(10, [10, 100, 200]) + _row(60, [10, 100, 200])
        stats = count_focus_order_regressions(centers, viewport_width=1000)
        assert stats["regressions"] == 0
        assert stats["ratio"] == 0.0

    def test_upward_jump_is_regression(self):
        centers = [{"x": 10, "y": 100}, {"x": 10, "y": 10}]
        stats = count_focus_order_regressions(centers, viewport_width=1000)
        assert stats["regressions"] == 1

    def test_large_leftward_jump_is_regression(self):
        centers = [{"x": 900, "y": 100}, {"x": 100, "y": 100}]
        stats = count_focus_order_regressions(centers, viewport_width=1000)
        assert stats["regressions"] == 1

    def test_small_leftward_jump_ok(self):
        centers = [{"x": 300, "y": 100}, {"x": 200, "y": 100}]
        stats = count_focus_order_regressions(centers, viewport_width=1000)
        assert stats["regressions"] == 0

    def test_new_row_leftward_is_fine(self):
        """Wrapping to the start of the next row is normal reading flow."""
        centers = [{"x": 900, "y": 100}, {"x": 10, "y": 200}]
        stats = count_focus_order_regressions(centers, viewport_width=1000)
        assert stats["regressions"] == 0

    def test_empty_and_single(self):
        assert count_focus_order_regressions([])["steps"] == 0
        assert count_focus_order_regressions([{"x": 1, "y": 1}])["ratio"] == 0.0


class TestAnalyze:
    def test_no_issue_below_threshold(self):
        centers = _row(10, [10, 100, 200, 300, 400])
        assert analyze_focus_order_spatial(centers, 1000) is None

    def test_issue_emitted_for_erratic_order(self):
        # Alternate top/bottom: every step regresses or jumps.
        centers = []
        for i in range(6):
            centers.append({"x": 10.0 + i, "y": 500.0 if i % 2 else 10.0})
        issue = analyze_focus_order_spatial(centers, 1000)
        assert issue is not None
        assert issue.issue_type == KeyboardIssueType.TAB_ORDER_ISSUE
        assert issue.severity == ViolationSeverity.SERIOUS
        assert "High-Risk Disorientation" in issue.description
        assert "1.3.2" in issue.wcag_reference
        assert "not a hard failure" in issue.description

    def test_too_few_elements_never_flagged(self):
        centers = [{"x": 10, "y": 100}, {"x": 10, "y": 10}, {"x": 10, "y": 100}]
        assert analyze_focus_order_spatial(centers, 1000) is None


class TestCentersExtraction:
    def test_extracts_centers(self):
        focusables = [
            {"box": {"x": 0, "y": 0, "width": 100, "height": 50}},
            {"box": None},
            {"tag": "a"},
        ]
        centers = centers_from_focusables(focusables)
        assert centers == [{"x": 50.0, "y": 25.0}]
