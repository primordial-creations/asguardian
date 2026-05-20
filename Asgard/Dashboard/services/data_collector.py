"""
Asgard Dashboard Data Collector

Collects and aggregates data from issue and history repository interfaces to
populate a DashboardState for rendering by the web dashboard.

This service depends on IIssueRepository and IHistoryRepository abstractions
(Ports) injected at construction time. It has no knowledge of the underlying
storage mechanism (SQLite, in-memory, remote API, etc.), satisfying DIP.
"""

from typing import Optional

from Asgard.Dashboard.models.dashboard_models import (
    DashboardState,
    IssueSummaryData,
    RatingData,
)
from Asgard.Shared.Issues.models.issue_models import IssueSeverity
from Asgard.Shared.Issues.services._issue_repository import IIssueRepository
from Asgard.Reporting.History.services._history_repository import IHistoryRepository


class DataCollector:
    """
    Collects data from issue and history repositories and returns a DashboardState.

    A new instance is constructed per HTTP request so no caching is performed.
    Both repository dependencies are injected via the constructor, decoupling
    this service from any specific storage implementation.
    """

    def __init__(
        self,
        issue_repository: IIssueRepository,
        history_repository: IHistoryRepository,
    ) -> None:
        self._issue_repository = issue_repository
        self._history_repository = history_repository

    def collect(self, project_path: str) -> DashboardState:
        """
        Read from the issue and history repositories and return an aggregated DashboardState.

        Args:
            project_path: Absolute path to the project being inspected.

        Returns:
            DashboardState populated with issue summaries, recent issues, snapshots,
            ratings, and quality gate status.
        """
        summary = self._issue_repository.get_summary(project_path)

        open_by_severity = summary.open_by_severity
        critical_count = open_by_severity.get(IssueSeverity.CRITICAL.value, 0)
        high_count = open_by_severity.get(IssueSeverity.HIGH.value, 0)
        medium_count = open_by_severity.get(IssueSeverity.MEDIUM.value, 0)
        low_count = open_by_severity.get(IssueSeverity.LOW.value, 0)

        total = (
            summary.total_open
            + summary.total_confirmed
            + summary.total_false_positives
            + summary.total_wont_fix
            + summary.total_resolved
        )

        issue_summary = IssueSummaryData(
            total=total,
            open=summary.total_open,
            confirmed=summary.total_confirmed,
            critical=critical_count,
            high=high_count,
            medium=medium_count,
            low=low_count,
        )

        all_issues = self._issue_repository.get_issues(project_path, issue_filter=None)
        recent_issues_raw = all_issues[:100]
        recent_issues = []
        for issue in recent_issues_raw:
            recent_issues.append({
                "issue_id": issue.issue_id,
                "rule_id": issue.rule_id,
                "issue_type": str(issue.issue_type),
                "file_path": issue.file_path,
                "line_number": issue.line_number,
                "severity": str(issue.severity),
                "title": issue.title,
                "description": issue.description,
                "status": str(issue.status),
                "first_detected": issue.first_detected.isoformat() if issue.first_detected else None,
                "last_seen": issue.last_seen.isoformat() if issue.last_seen else None,
                "assigned_to": issue.assigned_to,
            })

        snapshots_raw = self._history_repository.get_snapshots(project_path, limit=20)
        snapshots = []
        for snap in snapshots_raw:
            snapshots.append({
                "snapshot_id": snap.snapshot_id,
                "project_path": snap.project_path,
                "scan_timestamp": snap.scan_timestamp.isoformat() if snap.scan_timestamp else None,
                "git_commit": snap.git_commit,
                "git_branch": snap.git_branch,
                "quality_gate_status": snap.quality_gate_status,
                "ratings": snap.ratings,
                "metrics": [
                    {"metric_name": m.metric_name, "value": m.value, "unit": m.unit}
                    for m in snap.metrics
                ],
            })

        last_analyzed = None
        quality_gate_status = None
        ratings: Optional[RatingData] = None

        if snapshots_raw:
            latest = snapshots_raw[0]
            last_analyzed = latest.scan_timestamp
            quality_gate_status = latest.quality_gate_status or "unknown"

            raw_ratings = latest.ratings or {}
            if raw_ratings:
                ratings = RatingData(
                    maintainability=raw_ratings.get("maintainability", "?"),
                    reliability=raw_ratings.get("reliability", "?"),
                    security=raw_ratings.get("security", "?"),
                    overall=raw_ratings.get("overall", "?"),
                )

        return DashboardState(
            project_path=project_path,
            last_analyzed=last_analyzed,
            quality_gate_status=quality_gate_status,
            ratings=ratings,
            issue_summary=issue_summary,
            recent_issues=recent_issues,
            snapshots=snapshots,
        )
