"""
Heimdall Issues

Issue lifecycle tracking backed by a local SQLite database.
Provides persistent storage, status transitions, assignment, commenting,
and git blame enrichment for analysis findings.

Usage:
    from Heimdall.Issues import IssueTracker, TrackedIssue, IssueStatus

    tracker = IssueTracker()
    issue = tracker.upsert_issue(
        project_path="/path/to/project",
        rule_id="js.no-eval",
        file_path="/path/to/project/src/app.js",
        line_number=42,
        issue_type=IssueType.VULNERABILITY,
        severity=IssueSeverity.HIGH,
        title="Use of eval()",
        description="eval() executes arbitrary code.",
    )
    tracker.update_status(issue.issue_id, IssueStatus.CONFIRMED)
    summary = tracker.get_summary("/path/to/project")
    print(f"Open issues: {summary.total_open}")
"""

from Asgard.Shared.Issues.models.issue_models import (
    IssueFilter,
    IssueStatus,
    IssueSeverity,
    IssuesSummary,
    IssueType,
    TrackedIssue,
)
from Asgard.Shared.Issues.services.issue_tracker import IssueTracker

__all__ = [
    "IssueFilter",
    "IssueStatus",
    "IssueSeverity",
    "IssuesSummary",
    "IssueTracker",
    "IssueType",
    "TrackedIssue",
]
