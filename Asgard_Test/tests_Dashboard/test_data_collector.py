"""
Tests for Asgard Dashboard Data Collector

Unit tests for DataCollector.collect(). The collector takes injected
IIssueRepository and IHistoryRepository dependencies (DIP), so tests
just pass MagicMock repositories — no patching of storage internals.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from Asgard.Dashboard.models.dashboard_models import (
    DashboardState,
    IssueSummaryData,
    RatingData,
)
from Asgard.Dashboard.services.data_collector import DataCollector
from Asgard.Shared.Issues.models.issue_models import (
    IssueSeverity,
    IssuesSummary,
    IssueStatus,
    IssueType,
    TrackedIssue,
)
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot


PROJECT_PATH = "/project"


def _make_issues_summary(
    total_open: int = 0,
    total_confirmed: int = 0,
    total_false_positives: int = 0,
    total_wont_fix: int = 0,
    total_resolved: int = 0,
    open_by_severity: dict = None,
    project_path: str = PROJECT_PATH,
) -> IssuesSummary:
    return IssuesSummary(
        total_open=total_open,
        total_confirmed=total_confirmed,
        total_false_positives=total_false_positives,
        total_wont_fix=total_wont_fix,
        total_resolved=total_resolved,
        open_by_severity=open_by_severity or {},
        project_path=project_path,
    )


def _make_tracked_issue(
    project_path: str = PROJECT_PATH,
    rule_id: str = "quality.lazy_imports",
    file_path: str = "/project/main.py",
    line_number: int = 10,
    severity: IssueSeverity = IssueSeverity.HIGH,
    status: IssueStatus = IssueStatus.OPEN,
) -> TrackedIssue:
    now = datetime.now()
    return TrackedIssue(
        issue_id="test-uuid-1234",
        rule_id=rule_id,
        issue_type=IssueType.CODE_SMELL,
        file_path=file_path,
        line_number=line_number,
        severity=severity,
        title="Test issue",
        description="A test issue",
        status=status,
        first_detected=now,
        last_seen=now,
    )


def _make_snapshot(
    project_path: str = PROJECT_PATH,
    quality_gate_status: str = "passed",
    ratings: dict = None,
) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        snapshot_id="snap-uuid-1234",
        project_path=project_path,
        scan_timestamp=datetime(2025, 3, 10, 12, 0, 0),
        git_commit="abc1234",
        git_branch="main",
        quality_gate_status=quality_gate_status,
        ratings=(
            ratings
            if ratings is not None
            else {"maintainability": "A", "reliability": "B", "security": "A", "overall": "A"}
        ),
        metrics=[],
    )


def _make_collector(
    summary: IssuesSummary = None,
    issues: list = None,
    snapshots: list = None,
) -> DataCollector:
    """Build a DataCollector with mock repositories."""
    issue_repo = MagicMock()
    issue_repo.get_summary.return_value = summary or _make_issues_summary()
    issue_repo.get_issues.return_value = issues or []

    history_repo = MagicMock()
    history_repo.get_snapshots.return_value = snapshots or []

    return DataCollector(issue_repository=issue_repo, history_repository=history_repo)


class TestDataCollectorCollect:
    """Tests for DataCollector.collect()."""

    def test_collect_returns_dashboard_state(self):
        collector = _make_collector()
        state = collector.collect(PROJECT_PATH)
        assert isinstance(state, DashboardState)

    def test_collect_empty_stores_zero_counts(self):
        collector = _make_collector()
        state = collector.collect(PROJECT_PATH)
        assert state.issue_summary.total == 0
        assert state.issue_summary.open == 0
        assert state.issue_summary.confirmed == 0
        assert state.issue_summary.critical == 0

    def test_collect_returns_correct_project_path(self):
        collector = _make_collector(
            summary=_make_issues_summary(project_path="/my/project")
        )
        state = collector.collect("/my/project")
        assert state.project_path == "/my/project"

    def test_collect_no_history_returns_none_ratings(self):
        collector = _make_collector()
        state = collector.collect(PROJECT_PATH)
        assert state.ratings is None

    def test_collect_no_history_returns_none_last_analyzed(self):
        collector = _make_collector()
        state = collector.collect(PROJECT_PATH)
        assert state.last_analyzed is None

    def test_collect_extracts_ratings_from_most_recent_snapshot(self):
        snapshot = _make_snapshot(
            ratings={
                "maintainability": "A",
                "reliability": "B",
                "security": "C",
                "overall": "B",
            }
        )
        collector = _make_collector(snapshots=[snapshot])
        state = collector.collect(PROJECT_PATH)
        assert state.ratings is not None
        assert state.ratings.maintainability == "A"
        assert state.ratings.reliability == "B"
        assert state.ratings.security == "C"
        assert state.ratings.overall == "B"

    def test_collect_uses_first_snapshot_as_latest(self):
        newest = _make_snapshot(
            quality_gate_status="passed",
            ratings={"maintainability": "A", "reliability": "A", "security": "A", "overall": "A"},
        )
        older = _make_snapshot(
            quality_gate_status="failed",
            ratings={"maintainability": "E", "reliability": "E", "security": "E", "overall": "E"},
        )
        collector = _make_collector(snapshots=[newest, older])
        state = collector.collect(PROJECT_PATH)
        assert state.quality_gate_status == "passed"
        assert state.ratings.overall == "A"

    def test_collect_issue_summary_open_count(self):
        collector = _make_collector(summary=_make_issues_summary(total_open=5))
        state = collector.collect(PROJECT_PATH)
        assert state.issue_summary.open == 5

    def test_collect_issue_summary_total_counts_all_statuses(self):
        collector = _make_collector(
            summary=_make_issues_summary(
                total_open=2,
                total_confirmed=1,
                total_false_positives=1,
                total_wont_fix=1,
                total_resolved=3,
            )
        )
        state = collector.collect(PROJECT_PATH)
        assert state.issue_summary.total == 8

    def test_collect_critical_count_from_open_by_severity(self):
        summary = _make_issues_summary(
            total_open=3,
            open_by_severity={
                IssueSeverity.CRITICAL.value: 2,
                IssueSeverity.HIGH.value: 1,
            },
        )
        collector = _make_collector(summary=summary)
        state = collector.collect(PROJECT_PATH)
        assert state.issue_summary.critical == 2
        assert state.issue_summary.high == 1

    def test_collect_recent_issues_populated_from_get_issues(self):
        tracked_issue = _make_tracked_issue()
        collector = _make_collector(issues=[tracked_issue])
        state = collector.collect(PROJECT_PATH)
        assert len(state.recent_issues) == 1
        assert state.recent_issues[0]["rule_id"] == "quality.lazy_imports"

    def test_collect_snapshots_populated(self):
        snapshot = _make_snapshot()
        collector = _make_collector(snapshots=[snapshot])
        state = collector.collect(PROJECT_PATH)
        assert len(state.snapshots) == 1
        assert state.snapshots[0]["snapshot_id"] == "snap-uuid-1234"

    def test_collect_snapshot_with_no_ratings_uses_unknown(self):
        snapshot = _make_snapshot(ratings={})
        collector = _make_collector(snapshots=[snapshot])
        state = collector.collect(PROJECT_PATH)
        assert state.ratings is None

    def test_collect_last_analyzed_from_most_recent_snapshot(self):
        ts = datetime(2025, 6, 1, 9, 0, 0)
        snapshot = _make_snapshot()
        snapshot.scan_timestamp = ts
        collector = _make_collector(snapshots=[snapshot])
        state = collector.collect(PROJECT_PATH)
        assert state.last_analyzed == ts

    def test_collect_quality_gate_status_from_snapshot(self):
        snapshot = _make_snapshot(quality_gate_status="failed")
        collector = _make_collector(snapshots=[snapshot])
        state = collector.collect(PROJECT_PATH)
        assert state.quality_gate_status == "failed"
