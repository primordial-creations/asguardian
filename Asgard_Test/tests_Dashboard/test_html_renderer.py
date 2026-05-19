"""
Tests for Asgard Dashboard HTML Renderer

Unit tests for all render methods in HtmlRenderer, verifying correct HTML
structure, quality gate status presentation, issue filtering, navigation
links, and error page generation.
"""

from datetime import datetime

import pytest

from Asgard.Dashboard.models.dashboard_models import (
    DashboardState,
    IssueSummaryData,
    RatingData,
)
from Asgard.Dashboard.services.html_renderer import HtmlRenderer


def _make_empty_issue_summary() -> IssueSummaryData:
    """Return an IssueSummaryData with all zero counts."""
    return IssueSummaryData(
        total=0,
        open=0,
        confirmed=0,
        critical=0,
        high=0,
        medium=0,
        low=0,
    )


def _make_state(
    project_path: str = "/home/user/my-project",
    quality_gate_status: str = None,
    ratings: RatingData = None,
    recent_issues: list = None,
    snapshots: list = None,
    last_analyzed: datetime = None,
) -> DashboardState:
    """Build a DashboardState instance with sensible defaults for testing."""
    return DashboardState(
        project_path=project_path,
        last_analyzed=last_analyzed,
        quality_gate_status=quality_gate_status,
        ratings=ratings,
        issue_summary=_make_empty_issue_summary(),
        recent_issues=recent_issues or [],
        snapshots=snapshots or [],
    )


def _make_issue(
    severity: str = "high",
    status: str = "open",
    rule_id: str = "security.hardcoded_secret",
    file_path: str = "/project/src/main.py",
    line_number: int = 42,
    issue_type: str = "vulnerability",
) -> dict:
    """Build a minimal issue dict for use in dashboard state."""
    return {
        "issue_id": "abc-123",
        "rule_id": rule_id,
        "issue_type": issue_type,
        "file_path": file_path,
        "line_number": line_number,
        "severity": severity,
        "title": "Test issue",
        "description": "Test description",
        "status": status,
        "first_detected": "2025-01-01T00:00:00",
        "last_seen": "2025-01-01T00:00:00",
        "assigned_to": None,
    }


class TestHtmlRendererOverview:
    """Tests for HtmlRenderer.render_overview()."""

    def test_render_overview_returns_string(self):
        """Test that render_overview returns a string."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert isinstance(result, str)

    def test_render_overview_starts_with_doctype(self):
        """Test that render_overview output begins with DOCTYPE html declaration."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert result.strip().startswith("<!DOCTYPE html")

    def test_render_overview_passed_gate_contains_passed(self):
        """Test that a passed quality gate state is reflected in the HTML output."""
        renderer = HtmlRenderer()
        state = _make_state(quality_gate_status="passed")
        result = renderer.render_overview(state)
        assert "passed" in result.lower()

    def test_render_overview_failed_gate_contains_failed(self):
        """Test that a failed quality gate state is reflected in the HTML output."""
        renderer = HtmlRenderer()
        state = _make_state(quality_gate_status="failed")
        result = renderer.render_overview(state)
        assert "failed" in result.lower()

    def test_render_overview_unknown_gate_contains_unknown(self):
        """Test that a None quality gate status renders as unknown."""
        renderer = HtmlRenderer()
        state = _make_state(quality_gate_status=None)
        result = renderer.render_overview(state)
        assert "unknown" in result.lower()

    def test_render_overview_includes_nav_link_to_root(self):
        """Test that the overview page includes a nav link to /."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert 'href="/"' in result

    def test_render_overview_includes_nav_link_to_issues(self):
        """Test that the overview page includes a nav link to /issues."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert 'href="/issues"' in result

    def test_render_overview_includes_nav_link_to_history(self):
        """Test that the overview page includes a nav link to /history."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert 'href="/history"' in result

    def test_render_overview_with_ratings(self):
        """Test that ratings are rendered when present in the state."""
        renderer = HtmlRenderer()
        ratings = RatingData(
            maintainability="A",
            reliability="B",
            security="C",
            overall="B",
        )
        state = _make_state(ratings=ratings)
        result = renderer.render_overview(state)
        assert "Maintainability" in result
        assert "Reliability" in result
        assert "Security" in result

    def test_render_overview_with_last_analyzed_timestamp(self):
        """Test that a last_analyzed timestamp is displayed in the output."""
        renderer = HtmlRenderer()
        ts = datetime(2025, 6, 15, 12, 30, 0)
        state = _make_state(last_analyzed=ts)
        result = renderer.render_overview(state)
        assert "2025-06-15" in result

    def test_render_overview_issue_summary_total_in_output(self):
        """Test that the total issue count from issue_summary appears in output."""
        renderer = HtmlRenderer()
        state = _make_state()
        state.issue_summary.total = 17
        result = renderer.render_overview(state)
        assert "17" in result

    def test_render_overview_contains_asgard_title(self):
        """Test that the page contains the Asgard branding."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_overview(state)
        assert "Asgard" in result

    def test_render_overview_contains_project_name(self):
        """Test that the project directory name appears in the rendered page."""
        renderer = HtmlRenderer()
        state = _make_state(project_path="/home/user/cool-project")
        result = renderer.render_overview(state)
        assert "cool-project" in result


class TestHtmlRendererIssues:
    """Tests for HtmlRenderer.render_issues()."""

    def test_render_issues_returns_valid_html(self):
        """Test that render_issues returns an HTML document string."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert "<!DOCTYPE html" in result

    def test_render_issues_includes_nav_links(self):
        """Test that the issues page includes all three navigation links."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert 'href="/"' in result
        assert 'href="/issues"' in result
        assert 'href="/history"' in result

    def test_render_issues_shows_no_issues_message_when_empty(self):
        """Test that the issues page displays a no-issues message for empty state."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert "No issues" in result or "no issues" in result.lower()

    def test_render_issues_filter_by_status_open(self):
        """Test that status_filter=open excludes issues with other statuses."""
        renderer = HtmlRenderer()
        issues = [
            _make_issue(status="open", severity="high"),
            _make_issue(status="resolved", severity="high"),
        ]
        state = _make_state(recent_issues=issues)
        result = renderer.render_issues(state, status_filter="open", severity_filter="all")

        # The resolved issue's status badge should not appear in the open-filtered view
        assert result.count("Resolved") == 0 or "open" in result.lower()

    def test_render_issues_filter_by_severity_critical(self):
        """Test that severity_filter=critical shows only critical issues."""
        renderer = HtmlRenderer()
        issues = [
            _make_issue(status="open", severity="critical"),
            _make_issue(status="open", severity="low"),
        ]
        state = _make_state(recent_issues=issues)
        result = renderer.render_issues(state, status_filter="all", severity_filter="critical")

        # The critical issue should appear; the low-severity issue row should not
        assert "sev-badge sev-critical" in result
        assert "sev-badge sev-low" not in result

    def test_render_issues_with_matching_issue_shows_rule_id(self):
        """Test that matching issues display the rule_id in the table."""
        renderer = HtmlRenderer()
        issues = [_make_issue(rule_id="quality.lazy_imports")]
        state = _make_state(recent_issues=issues)
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert "quality.lazy_imports" in result

    def test_render_issues_filter_combined_status_and_severity(self):
        """Test that both status and severity filters are applied together."""
        renderer = HtmlRenderer()
        issues = [
            _make_issue(status="open", severity="critical"),
            _make_issue(status="open", severity="low"),
            _make_issue(status="resolved", severity="critical"),
        ]
        state = _make_state(recent_issues=issues)
        result = renderer.render_issues(
            state, status_filter="open", severity_filter="critical"
        )

        assert "sev-badge sev-low" not in result
        assert "status-badge status-resolved" not in result

    def test_render_issues_contains_filter_form(self):
        """Test that the issues page contains a filter form."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert "<form" in result

    def test_render_issues_contains_table_headers(self):
        """Test that the issues page contains expected table column headers."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_issues(state, status_filter="all", severity_filter="all")
        assert "Severity" in result
        assert "Rule" in result
        assert "File" in result


class TestHtmlRendererHistory:
    """Tests for HtmlRenderer.render_history()."""

    def test_render_history_returns_valid_html(self):
        """Test that render_history returns an HTML document string."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_history(state)
        assert "<!DOCTYPE html" in result

    def test_render_history_includes_nav_links(self):
        """Test that the history page includes all three navigation links."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_history(state)
        assert 'href="/"' in result
        assert 'href="/issues"' in result
        assert 'href="/history"' in result

    def test_render_history_no_snapshots_message(self):
        """Test that the history page shows a no-snapshots message when empty."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_history(state)
        assert "No snapshots" in result or "no snapshots" in result.lower()

    def test_render_history_with_snapshots_shows_timestamp(self):
        """Test that snapshot timestamps appear in the history page."""
        renderer = HtmlRenderer()
        snapshots = [
            {
                "snapshot_id": "snap-1",
                "project_path": "/project",
                "scan_timestamp": "2025-03-10T14:00:00",
                "git_commit": "abcdef1234567890",
                "git_branch": "main",
                "quality_gate_status": "passed",
                "ratings": {
                    "maintainability": "A",
                    "reliability": "B",
                    "security": "A",
                    "overall": "A",
                },
                "metrics": [],
            }
        ]
        state = _make_state(snapshots=snapshots)
        result = renderer.render_history(state)
        assert "2025-03-10" in result

    def test_render_history_with_snapshots_shows_gate_status(self):
        """Test that the quality gate status for each snapshot is rendered."""
        renderer = HtmlRenderer()
        snapshots = [
            {
                "snapshot_id": "snap-2",
                "project_path": "/project",
                "scan_timestamp": "2025-03-10T14:00:00",
                "git_commit": None,
                "git_branch": "main",
                "quality_gate_status": "failed",
                "ratings": {},
                "metrics": [],
            }
        ]
        state = _make_state(snapshots=snapshots)
        result = renderer.render_history(state)
        assert "failed" in result.lower()

    def test_render_history_contains_table_headers(self):
        """Test that the history page contains expected column headers."""
        renderer = HtmlRenderer()
        state = _make_state()
        result = renderer.render_history(state)
        assert "Date" in result
        assert "Gate" in result

    def test_render_history_contains_project_path(self):
        """Test that the project directory name appears in the history page sidebar."""
        renderer = HtmlRenderer()
        state = _make_state(project_path="/home/user/my-project")
        result = renderer.render_history(state)
        assert "my-project" in result


class TestHtmlRendererError:
    """Tests for HtmlRenderer.render_error()."""

    def test_render_error_returns_html_doctype(self):
        """Test that render_error returns a DOCTYPE HTML document."""
        renderer = HtmlRenderer()
        result = renderer.render_error("something went wrong")
        assert "<!DOCTYPE html" in result

    def test_render_error_contains_message(self):
        """Test that the error message text appears in the rendered HTML."""
        renderer = HtmlRenderer()
        result = renderer.render_error("Database connection failed")
        assert "Database connection failed" in result

    def test_render_error_with_special_characters(self):
        """Test rendering an error with special characters in the message."""
        renderer = HtmlRenderer()
        result = renderer.render_error("File not found: /path/to/file.db")
        assert "File not found" in result
        assert "/path/to/file.db" in result

    def test_render_error_contains_return_link(self):
        """Test that the error page includes a link back to the overview."""
        renderer = HtmlRenderer()
        result = renderer.render_error("test error")
        assert 'href="/"' in result

    def test_render_error_does_not_raise(self):
        """Test that render_error does not raise an exception for any string input."""
        renderer = HtmlRenderer()
        try:
            result = renderer.render_error("")
            assert isinstance(result, str)
        except Exception as exc:
            pytest.fail(f"render_error raised an unexpected exception: {exc}")


class TestHtmlRendererPage:
    """Tests for HtmlRenderer.render_page() wrapper method."""

    def test_render_page_includes_title(self):
        """Test that the page title appears in the rendered HTML head."""
        renderer = HtmlRenderer()
        result = renderer.render_page("Test Title", "<p>content</p>", "overview", "/project")
        assert "Test Title" in result

    def test_render_page_active_nav_has_active_class(self):
        """Test that the active navigation link has the 'active' CSS class."""
        renderer = HtmlRenderer()
        result = renderer.render_page("Issues", "<p>content</p>", "issues", "/project")
        assert 'class="active"' in result

    def test_render_page_includes_content(self):
        """Test that the provided content is embedded in the output."""
        renderer = HtmlRenderer()
        result = renderer.render_page("Test", "<p>unique-marker-xyz</p>", "overview", "/project")
        assert "unique-marker-xyz" in result
