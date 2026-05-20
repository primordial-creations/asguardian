"""
Tests for Heimdall Issue Tracker Service

Unit tests for persistent issue lifecycle tracking backed by SQLite.
All tests use a temporary file path to avoid polluting ~/.asgard/.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Asgard.Shared.Issues.models.issue_models import (
    IssueFilter,
    IssueSeverity,
    IssueStatus,
    IssueType,
    IssuesSummary,
    TrackedIssue,
)
from Asgard.Shared.Issues.services.issue_tracker import IssueTracker


def _make_tracker(tmp_path: Path) -> IssueTracker:
    """Create an IssueTracker backed by a temp SQLite file."""
    db_file = tmp_path / "test_issues.db"
    return IssueTracker(db_path=db_file)


def _upsert_basic(
    tracker: IssueTracker,
    project_path: str = "/project",
    rule_id: str = "js.no-eval",
    file_path: str = "/project/src/app.js",
    line_number: int = 10,
    issue_type: IssueType = IssueType.VULNERABILITY,
    severity: IssueSeverity = IssueSeverity.HIGH,
    title: str = "Use of eval()",
    description: str = "Direct eval usage detected.",
) -> TrackedIssue:
    """Helper to upsert a basic issue with sensible defaults."""
    return tracker.upsert_issue(
        project_path=project_path,
        rule_id=rule_id,
        file_path=file_path,
        line_number=line_number,
        issue_type=issue_type,
        severity=severity,
        title=title,
        description=description,
    )


class TestIssueTrackerInit:
    """Tests for IssueTracker initialisation."""

    def test_init_creates_database_file(self):
        """Initialising with a db_path should create the database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "issues.db"
            assert not db_file.exists()

            IssueTracker(db_path=db_file)

            assert db_file.exists()

    def test_init_is_idempotent(self):
        """Calling init multiple times with the same path should not raise errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "issues.db"
            IssueTracker(db_path=db_file)
            IssueTracker(db_path=db_file)


class TestIssueTrackerUpsertIssue:
    """Tests for the upsert_issue method."""

    def test_upsert_creates_new_issue(self):
        """upsert_issue should create and return a new TrackedIssue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            assert issue is not None
            assert isinstance(issue, TrackedIssue)
            assert issue.issue_id != ""

    def test_new_issue_has_open_status(self):
        """A newly created issue should have OPEN status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            assert issue.status == IssueStatus.OPEN.value

    def test_new_issue_preserves_rule_id(self):
        """The created issue should retain the provided rule_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker, rule_id="shell.eval-injection")

            assert issue.rule_id == "shell.eval-injection"

    def test_new_issue_preserves_file_path(self):
        """The created issue should retain the provided file_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker, file_path="/project/src/deploy.sh")

            assert issue.file_path == "/project/src/deploy.sh"

    def test_new_issue_preserves_severity(self):
        """The created issue should retain the provided severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker, severity=IssueSeverity.CRITICAL)

            assert issue.severity == IssueSeverity.CRITICAL.value

    def test_new_issue_has_scan_count_of_one(self):
        """A newly created issue should have scan_count = 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            assert issue.scan_count == 1

    def test_new_issue_has_first_detected_set(self):
        """A newly created issue should have first_detected set to a recent datetime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            before = datetime.now()
            issue = _upsert_basic(tracker)
            after = datetime.now()

            assert before <= issue.first_detected <= after

    def test_same_issue_upserted_twice_does_not_duplicate(self):
        """Upserting the same issue twice should update, not create a second row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue1 = _upsert_basic(tracker, line_number=10)
            issue2 = _upsert_basic(tracker, line_number=10)

            assert issue1.issue_id == issue2.issue_id

            all_issues = tracker.get_issues("/project")
            assert len(all_issues) == 1

    def test_upsert_increments_scan_count(self):
        """Upserting the same issue twice should increment scan_count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, line_number=10)
            issue = _upsert_basic(tracker, line_number=10)

            assert issue.scan_count == 2

    def test_upsert_within_proximity_does_not_duplicate(self):
        """Two upserts for the same rule with line numbers within 5 lines should update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, line_number=10)
            issue = _upsert_basic(tracker, line_number=14)

            all_issues = tracker.get_issues("/project")
            assert len(all_issues) == 1
            assert issue.scan_count == 2

    def test_upsert_outside_proximity_creates_new_issue(self):
        """Two upserts for the same rule with line numbers more than 5 apart should create two issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue1 = _upsert_basic(tracker, line_number=10)
            issue2 = _upsert_basic(tracker, line_number=20)

            assert issue1.issue_id != issue2.issue_id

            all_issues = tracker.get_issues("/project")
            assert len(all_issues) == 2

    def test_different_rule_ids_create_separate_issues(self):
        """Two upserts for different rule_ids should create two separate issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue1 = _upsert_basic(tracker, rule_id="js.no-eval", line_number=10)
            issue2 = _upsert_basic(tracker, rule_id="js.no-var", line_number=10)

            assert issue1.issue_id != issue2.issue_id

            all_issues = tracker.get_issues("/project")
            assert len(all_issues) == 2

    def test_different_file_paths_create_separate_issues(self):
        """Two upserts for different file paths should create two separate issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue1 = _upsert_basic(tracker, file_path="/project/a.js", line_number=10)
            issue2 = _upsert_basic(tracker, file_path="/project/b.js", line_number=10)

            assert issue1.issue_id != issue2.issue_id

            all_issues = tracker.get_issues("/project")
            assert len(all_issues) == 2


class TestIssueTrackerGetIssues:
    """Tests for the get_issues method."""

    def test_get_issues_returns_all_issues_for_project(self):
        """get_issues should return all issues for the given project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, rule_id="js.no-eval")
            _upsert_basic(tracker, rule_id="js.no-var", line_number=20)
            _upsert_basic(tracker, rule_id="js.no-debugger", line_number=30)

            issues = tracker.get_issues("/project")

            assert len(issues) == 3

    def test_get_issues_empty_store_returns_empty_list(self):
        """get_issues on a fresh tracker should return an empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issues = tracker.get_issues("/project")

            assert issues == []

    def test_get_issues_does_not_return_issues_for_other_projects(self):
        """get_issues should only return issues for the specified project_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, project_path="/project_a")
            _upsert_basic(tracker, project_path="/project_b")

            issues_a = tracker.get_issues("/project_a")
            issues_b = tracker.get_issues("/project_b")

            assert len(issues_a) == 1
            assert len(issues_b) == 1

    def test_get_issues_filter_by_open_status(self):
        """Filtering by IssueStatus.OPEN should return only open issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue_open = _upsert_basic(tracker, rule_id="js.no-eval", line_number=10)
            issue_to_resolve = _upsert_basic(tracker, rule_id="js.no-var", line_number=20)

            tracker.update_status(issue_to_resolve.issue_id, IssueStatus.RESOLVED)

            open_filter = IssueFilter(status=[IssueStatus.OPEN])
            open_issues = tracker.get_issues("/project", issue_filter=open_filter)

            assert len(open_issues) == 1
            assert open_issues[0].issue_id == issue_open.issue_id

    def test_get_issues_filter_by_severity(self):
        """Filtering by IssueSeverity should return only issues with that severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, rule_id="js.no-eval", line_number=10, severity=IssueSeverity.HIGH)
            _upsert_basic(tracker, rule_id="js.no-var", line_number=20, severity=IssueSeverity.LOW)

            high_filter = IssueFilter(severity=[IssueSeverity.HIGH])
            high_issues = tracker.get_issues("/project", issue_filter=high_filter)

            assert len(high_issues) == 1
            assert high_issues[0].severity == IssueSeverity.HIGH.value

    def test_get_issues_filter_by_rule_id(self):
        """Filtering by rule_id should return only issues matching that rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, rule_id="js.no-eval", line_number=10)
            _upsert_basic(tracker, rule_id="js.no-var", line_number=20)

            rule_filter = IssueFilter(rule_id="js.no-eval")
            filtered = tracker.get_issues("/project", issue_filter=rule_filter)

            assert len(filtered) == 1
            assert filtered[0].rule_id == "js.no-eval"

    def test_get_issues_filter_by_file_path_contains(self):
        """Filtering by file_path_contains should return only matching issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, file_path="/project/src/utils.js", line_number=10)
            _upsert_basic(tracker, file_path="/project/test/spec.js", line_number=20)

            path_filter = IssueFilter(file_path_contains="src")
            filtered = tracker.get_issues("/project", issue_filter=path_filter)

            assert len(filtered) == 1
            assert "src" in filtered[0].file_path

    def test_get_issues_returns_list_of_tracked_issues(self):
        """get_issues should return a list of TrackedIssue instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            _upsert_basic(tracker)

            issues = tracker.get_issues("/project")

            assert all(isinstance(i, TrackedIssue) for i in issues)


class TestIssueTrackerUpdateStatus:
    """Tests for the update_status method."""

    def test_update_status_to_resolved(self):
        """update_status should correctly transition an issue to RESOLVED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            updated = tracker.update_status(issue.issue_id, IssueStatus.RESOLVED)

            assert updated is not None
            assert updated.status == IssueStatus.RESOLVED.value

    def test_update_status_to_resolved_sets_resolved_at(self):
        """Transitioning to RESOLVED should set the resolved_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            before = datetime.now()
            updated = tracker.update_status(issue.issue_id, IssueStatus.RESOLVED)
            after = datetime.now()

            assert updated.resolved_at is not None
            assert before <= updated.resolved_at <= after

    def test_update_status_to_false_positive(self):
        """update_status should correctly transition an issue to FALSE_POSITIVE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            updated = tracker.update_status(
                issue.issue_id,
                IssueStatus.FALSE_POSITIVE,
                reason="Test environment variable, not production code.",
            )

            assert updated is not None
            assert updated.status == IssueStatus.FALSE_POSITIVE.value

    def test_update_status_to_false_positive_stores_reason(self):
        """Transitioning to FALSE_POSITIVE with a reason should persist the reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            reason = "This is a test fixture, not production code."
            updated = tracker.update_status(
                issue.issue_id,
                IssueStatus.FALSE_POSITIVE,
                reason=reason,
            )

            assert updated.false_positive_reason == reason

    def test_update_status_to_confirmed(self):
        """update_status should correctly transition an issue to CONFIRMED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            updated = tracker.update_status(issue.issue_id, IssueStatus.CONFIRMED)

            assert updated.status == IssueStatus.CONFIRMED.value

    def test_update_status_to_wont_fix(self):
        """update_status should correctly transition an issue to WONT_FIX."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            issue = _upsert_basic(tracker)

            updated = tracker.update_status(issue.issue_id, IssueStatus.WONT_FIX)

            assert updated.status == IssueStatus.WONT_FIX.value

    def test_update_status_nonexistent_issue_returns_none(self):
        """update_status with a non-existent issue_id should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            result = tracker.update_status("nonexistent-uuid", IssueStatus.RESOLVED)

            assert result is None

    def test_resolved_issue_not_returned_in_upsert_proximity_match(self):
        """A resolved issue should not be re-matched by upsert (proximity match only for active issues)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue = _upsert_basic(tracker, line_number=10)
            tracker.update_status(issue.issue_id, IssueStatus.RESOLVED)

            new_issue = _upsert_basic(tracker, line_number=10)

            assert new_issue.issue_id != issue.issue_id
            assert new_issue.status == IssueStatus.OPEN.value


class TestIssueTrackerGetSummary:
    """Tests for the get_summary method."""

    def test_empty_store_returns_zero_counts(self):
        """get_summary on an empty store should return all zero counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            summary = tracker.get_summary("/project")

            assert summary.total_open == 0
            assert summary.total_confirmed == 0
            assert summary.total_false_positives == 0
            assert summary.total_wont_fix == 0
            assert summary.total_resolved == 0

    def test_get_summary_counts_open_issues(self):
        """get_summary should correctly count issues with OPEN status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, rule_id="js.no-eval", line_number=10)
            _upsert_basic(tracker, rule_id="js.no-var", line_number=20)

            summary = tracker.get_summary("/project")

            assert summary.total_open == 2

    def test_get_summary_counts_resolved_issues(self):
        """get_summary should correctly count issues with RESOLVED status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue = _upsert_basic(tracker)
            tracker.update_status(issue.issue_id, IssueStatus.RESOLVED)

            summary = tracker.get_summary("/project")

            assert summary.total_resolved == 1
            assert summary.total_open == 0

    def test_get_summary_counts_false_positives(self):
        """get_summary should correctly count issues with FALSE_POSITIVE status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue = _upsert_basic(tracker)
            tracker.update_status(issue.issue_id, IssueStatus.FALSE_POSITIVE)

            summary = tracker.get_summary("/project")

            assert summary.total_false_positives == 1
            assert summary.total_open == 0

    def test_get_summary_groups_open_by_severity(self):
        """get_summary should correctly group open issues by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker, rule_id="r1", line_number=10, severity=IssueSeverity.HIGH)
            _upsert_basic(tracker, rule_id="r2", line_number=20, severity=IssueSeverity.HIGH)
            _upsert_basic(tracker, rule_id="r3", line_number=30, severity=IssueSeverity.LOW)

            summary = tracker.get_summary("/project")

            assert summary.open_by_severity.get(IssueSeverity.HIGH.value, 0) == 2
            assert summary.open_by_severity.get(IssueSeverity.LOW.value, 0) == 1

    def test_get_summary_groups_open_by_type(self):
        """get_summary should correctly group open issues by issue type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(
                tracker, rule_id="r1", line_number=10, issue_type=IssueType.VULNERABILITY
            )
            _upsert_basic(
                tracker, rule_id="r2", line_number=20, issue_type=IssueType.CODE_SMELL
            )

            summary = tracker.get_summary("/project")

            assert summary.open_by_type.get(IssueType.VULNERABILITY.value, 0) == 1
            assert summary.open_by_type.get(IssueType.CODE_SMELL.value, 0) == 1

    def test_get_summary_returns_issues_summary_model(self):
        """get_summary should return an IssuesSummary instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            summary = tracker.get_summary("/project")

            assert isinstance(summary, IssuesSummary)
            assert summary.project_path == "/project"

    def test_get_summary_oldest_open_issue_is_set_when_open_issues_exist(self):
        """oldest_open_issue should be set when there are open issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            _upsert_basic(tracker)

            summary = tracker.get_summary("/project")

            assert summary.oldest_open_issue is not None

    def test_get_summary_oldest_open_issue_is_none_when_no_open_issues(self):
        """oldest_open_issue should be None when there are no open issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue = _upsert_basic(tracker)
            tracker.update_status(issue.issue_id, IssueStatus.RESOLVED)

            summary = tracker.get_summary("/project")

            assert summary.oldest_open_issue is None

    def test_get_summary_mixed_statuses(self):
        """get_summary should correctly tally all statuses in a mixed scenario."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            open_issue = _upsert_basic(tracker, rule_id="r1", line_number=10)
            resolved_issue = _upsert_basic(tracker, rule_id="r2", line_number=20)
            fp_issue = _upsert_basic(tracker, rule_id="r3", line_number=30)
            wf_issue = _upsert_basic(tracker, rule_id="r4", line_number=40)

            tracker.update_status(resolved_issue.issue_id, IssueStatus.RESOLVED)
            tracker.update_status(fp_issue.issue_id, IssueStatus.FALSE_POSITIVE)
            tracker.update_status(wf_issue.issue_id, IssueStatus.WONT_FIX)

            summary = tracker.get_summary("/project")

            assert summary.total_open == 1
            assert summary.total_resolved == 1
            assert summary.total_false_positives == 1
            assert summary.total_wont_fix == 1


class TestIssueTrackerGetIssue:
    """Tests for the get_issue method."""

    def test_get_issue_returns_correct_issue(self):
        """get_issue should return the issue with the matching issue_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))
            created = _upsert_basic(tracker)

            fetched = tracker.get_issue(created.issue_id)

            assert fetched is not None
            assert fetched.issue_id == created.issue_id

    def test_get_issue_nonexistent_returns_none(self):
        """get_issue with a non-existent ID should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            result = tracker.get_issue("nonexistent-uuid-1234")

            assert result is None


class TestIssueTrackerMarkResolved:
    """Tests for the mark_resolved method."""

    def test_mark_resolved_transitions_old_issues(self):
        """Issues last seen before the scan start time should be marked resolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            issue = _upsert_basic(tracker)
            scan_start = datetime.now() + timedelta(seconds=1)

            count = tracker.mark_resolved("/project", scan_start)

            assert count >= 1
            updated = tracker.get_issue(issue.issue_id)
            assert updated.status == IssueStatus.RESOLVED.value

    def test_mark_resolved_does_not_affect_recent_issues(self):
        """Issues seen after the scan start time should remain open."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = _make_tracker(Path(tmpdir))

            scan_start = datetime.now() - timedelta(seconds=10)
            issue = _upsert_basic(tracker)

            count = tracker.mark_resolved("/project", scan_start)

            assert count == 0
            updated = tracker.get_issue(issue.issue_id)
            assert updated.status == IssueStatus.OPEN.value
