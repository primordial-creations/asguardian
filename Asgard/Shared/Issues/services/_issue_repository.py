"""
Heimdall Issue Tracker - repository abstraction.

Defines the IIssueRepository protocol (abstract interface) and the
SQLiteIssueRepository concrete implementation. IssueTracker depends
on the protocol, not on the SQLite concrete type, satisfying DIP.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol, runtime_checkable

from Asgard.Shared.Issues.models.issue_models import (
    IssueFilter,
    IssuesSummary,
    IssueSeverity,
    IssueStatus,
    IssueType,
    TrackedIssue,
)
from Asgard.Shared.Issues.services._issue_db import (
    _CREATE_IDX_PROJECT_SQL,
    _CREATE_IDX_STATUS_SQL,
    _CREATE_TABLE_SQL,
    _LINE_PROXIMITY,
    row_to_issue,
)
from Asgard.Shared.Issues.services._issue_queries import build_summary, query_issues


@runtime_checkable
class IIssueRepository(Protocol):
    """
    Abstract interface for issue persistence operations.

    Implementations may back this with SQLite, an in-memory store,
    a remote API, or any other provider without changing IssueTracker.
    """

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
        """Insert a new issue or update an existing match."""
        ...

    def mark_resolved(self, project_path: str, scan_start_time: datetime) -> int:
        """Mark as resolved all open/confirmed issues not seen in the latest scan."""
        ...

    def update_status(
        self,
        issue_id: str,
        new_status: IssueStatus,
        reason: Optional[str] = None,
    ) -> Optional[TrackedIssue]:
        """Transition an issue to a new lifecycle status."""
        ...

    def assign_issue(self, issue_id: str, assignee: str) -> Optional[TrackedIssue]:
        """Assign an issue to a user."""
        ...

    def add_comment(self, issue_id: str, comment: str) -> Optional[TrackedIssue]:
        """Append a comment to an issue."""
        ...

    def get_issues(
        self,
        project_path: str,
        issue_filter: Optional[IssueFilter] = None,
    ) -> List[TrackedIssue]:
        """Retrieve issues for a project with optional filtering."""
        ...

    def get_summary(self, project_path: str) -> IssuesSummary:
        """Generate an aggregated summary of issues for a project."""
        ...

    def get_issue(self, issue_id: str) -> Optional[TrackedIssue]:
        """Retrieve a single issue by its UUID."""
        ...


class SQLiteIssueRepository:
    """
    SQLite-backed implementation of IIssueRepository.

    All raw sqlite3 interactions are contained here, keeping the
    IssueTracker service free from direct database driver coupling.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or Path.home() / ".asgard" / "issues.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the issues table and indexes if they do not yet exist."""
        with self._get_connection() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_IDX_PROJECT_SQL)
            conn.execute(_CREATE_IDX_STATUS_SQL)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Open a database connection with WAL mode enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

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
        now_str = datetime.now().isoformat()
        issue_type_val = issue_type if isinstance(issue_type, str) else issue_type.value
        severity_val = severity if isinstance(severity, str) else severity.value

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM issues
                WHERE project_path = ?
                  AND rule_id = ?
                  AND file_path = ?
                  AND status NOT IN ('resolved', 'closed', 'false_positive', 'wont_fix')
                """,
                (project_path, rule_id, file_path),
            ).fetchall()

            existing = None
            for row in rows:
                if abs(row["line_number"] - line_number) <= _LINE_PROXIMITY:
                    existing = row
                    break

            if existing:
                conn.execute(
                    """
                    UPDATE issues
                    SET last_seen = ?, scan_count = scan_count + 1
                    WHERE issue_id = ?
                    """,
                    (now_str, existing["issue_id"]),
                )
                conn.commit()
                updated = conn.execute(
                    "SELECT * FROM issues WHERE issue_id = ?",
                    (existing["issue_id"],),
                ).fetchone()
                return row_to_issue(updated)

            new_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO issues (
                    issue_id, project_path, rule_id, issue_type, file_path,
                    line_number, severity, title, description, status,
                    first_detected, last_seen, resolved_at, false_positive_reason,
                    assigned_to, git_blame_author, git_blame_commit,
                    tags_json, comments_json, scan_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, NULL, NULL, NULL, NULL, NULL, '[]', '[]', 1)
                """,
                (
                    new_id, project_path, rule_id, issue_type_val, file_path,
                    line_number, severity_val, title, description,
                    now_str, now_str,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?",
                (new_id,),
            ).fetchone()
            return row_to_issue(row)

    def mark_resolved(self, project_path: str, scan_start_time: datetime) -> int:
        """Mark as resolved all open/confirmed issues not seen in the latest scan."""
        now_str = datetime.now().isoformat()
        scan_start_str = scan_start_time.isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE issues
                SET status = 'resolved', resolved_at = ?
                WHERE project_path = ?
                  AND status IN ('open', 'confirmed')
                  AND last_seen < ?
                """,
                (now_str, project_path, scan_start_str),
            )
            conn.commit()
            return cursor.rowcount

    def update_status(
        self,
        issue_id: str,
        new_status: IssueStatus,
        reason: Optional[str] = None,
    ) -> Optional[TrackedIssue]:
        """Transition an issue to a new lifecycle status."""
        status_val = new_status if isinstance(new_status, str) else new_status.value
        now_str = datetime.now().isoformat()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            if not row:
                return None

            resolved_at = now_str if status_val in ("resolved", "closed") else row["resolved_at"]
            false_positive_reason = (
                reason
                if status_val == IssueStatus.FALSE_POSITIVE.value
                else row["false_positive_reason"]
            )

            conn.execute(
                """
                UPDATE issues
                SET status = ?, resolved_at = ?, false_positive_reason = ?
                WHERE issue_id = ?
                """,
                (status_val, resolved_at, false_positive_reason, issue_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            return row_to_issue(updated)

    def assign_issue(self, issue_id: str, assignee: str) -> Optional[TrackedIssue]:
        """Assign an issue to a user."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE issues SET assigned_to = ? WHERE issue_id = ?",
                (assignee, issue_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            return row_to_issue(row)

    def add_comment(self, issue_id: str, comment: str) -> Optional[TrackedIssue]:
        """Append a comment to an issue."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            if not row:
                return None
            existing_comments = json.loads(row["comments_json"] or "[]")
            existing_comments.append(comment)
            conn.execute(
                "UPDATE issues SET comments_json = ? WHERE issue_id = ?",
                (json.dumps(existing_comments), issue_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            return row_to_issue(updated)

    def get_issues(
        self,
        project_path: str,
        issue_filter: Optional[IssueFilter] = None,
    ) -> List[TrackedIssue]:
        """Retrieve issues for a project with optional filtering."""
        with self._get_connection() as conn:
            return query_issues(conn, project_path, issue_filter)

    def get_summary(self, project_path: str) -> IssuesSummary:
        """Generate an aggregated summary of issues for a project."""
        with self._get_connection() as conn:
            return build_summary(conn, project_path)

    def get_issue(self, issue_id: str) -> Optional[TrackedIssue]:
        """Retrieve a single issue by its UUID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,),
            ).fetchone()
            if not row:
                return None
            return row_to_issue(row)
