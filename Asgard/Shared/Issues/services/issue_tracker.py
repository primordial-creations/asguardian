"""Heimdall Issue Tracker - persists and manages issues in a local SQLite database."""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Shared.Issues.models.issue_models import (
    IssueFilter,
    IssueStatus,
    IssueSeverity,
    IssueType,
    IssuesSummary,
    TrackedIssue,
)
from Asgard.Shared.Issues.services._issue_repository import (
    IIssueRepository,
    SQLiteIssueRepository,
)


class IssueTracker:
    """
    Manages persistent issue lifecycle tracking.

    Depends on IIssueRepository for all storage operations, decoupling
    the service from any specific database driver (DIP). By default a
    SQLiteIssueRepository is created, but any IIssueRepository implementation
    can be injected — enabling in-memory stores, remote APIs, or test doubles.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        repository: Optional[IIssueRepository] = None,
    ) -> None:
        if repository is not None:
            self._repository: IIssueRepository = repository
        else:
            self._repository = SQLiteIssueRepository(db_path=db_path)

    def upsert_issue(
        self,
        project_path: str,
        rule_id: str,
        file_path: str,
        line_number: int,
        issue_type: IssueType,
        severity: IssueSeverity,
        title: str,
        description: str,
    ) -> TrackedIssue:
        """Insert a new issue or update an existing match (by rule, file, line proximity)."""
        return self._repository.upsert_issue(
            project_path=project_path,
            rule_id=rule_id,
            file_path=file_path,
            line_number=line_number,
            issue_type=issue_type,
            severity=severity,
            title=title,
            description=description,
        )

    def mark_resolved(self, project_path: str, scan_start_time: datetime) -> int:
        """Mark as resolved all open/confirmed issues not seen in the latest scan."""
        return self._repository.mark_resolved(project_path, scan_start_time)

    def update_status(
        self, issue_id: str, new_status: IssueStatus, reason: Optional[str] = None,
    ) -> Optional[TrackedIssue]:
        """Transition an issue to a new lifecycle status."""
        return self._repository.update_status(issue_id, new_status, reason)

    def assign_issue(self, issue_id: str, assignee: str) -> Optional[TrackedIssue]:
        """Assign an issue to a user."""
        return self._repository.assign_issue(issue_id, assignee)

    def add_comment(self, issue_id: str, comment: str) -> Optional[TrackedIssue]:
        """Append a comment to an issue."""
        return self._repository.add_comment(issue_id, comment)

    def get_issues(
        self, project_path: str, issue_filter: Optional[IssueFilter] = None,
    ) -> List[TrackedIssue]:
        """Retrieve issues for a project with optional filtering."""
        return self._repository.get_issues(project_path, issue_filter)

    def get_summary(self, project_path: str) -> IssuesSummary:
        """Generate an aggregated summary of issues for a project."""
        return self._repository.get_summary(project_path)

    def get_issue(self, issue_id: str) -> Optional[TrackedIssue]:
        """Retrieve a single issue by its UUID."""
        return self._repository.get_issue(issue_id)

    def get_git_blame(self, file_path: str, line_number: int) -> Optional[Dict[str, str]]:
        """Run git blame on a specific line to identify the author and commit."""
        try:
            result = subprocess.run(
                ["git", "blame", "-L", f"{line_number},{line_number}", "--porcelain", file_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None
            output = result.stdout
            lines = output.splitlines()
            if not lines:
                return None

            commit_hash = lines[0].split()[0] if lines[0].split() else ""
            author = ""
            for line in lines[1:]:
                if line.startswith("author "):
                    author = line[len("author "):]
                    break

            if not commit_hash:
                return None

            return {"author": author, "commit": commit_hash}
        except (subprocess.SubprocessError, OSError, IndexError):
            return None
