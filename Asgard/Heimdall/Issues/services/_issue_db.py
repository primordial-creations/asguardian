"""
Heimdall Issue Tracker - database schema and row conversion helpers.

Contains SQL statements and the _row_to_issue conversion function shared
across issue tracker operations.
"""

import json
import sqlite3
from datetime import datetime

from Asgard.Heimdall.Issues.models.issue_models import TrackedIssue


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    first_detected TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    resolved_at TEXT,
    false_positive_reason TEXT,
    assigned_to TEXT,
    git_blame_author TEXT,
    git_blame_commit TEXT,
    tags_json TEXT DEFAULT '[]',
    comments_json TEXT DEFAULT '[]',
    scan_count INTEGER DEFAULT 1
);
"""

_CREATE_IDX_PROJECT_SQL = "CREATE INDEX IF NOT EXISTS idx_issues_project ON issues(project_path);"
_CREATE_IDX_STATUS_SQL = "CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);"

_LINE_PROXIMITY = 5


def row_to_issue(row: sqlite3.Row) -> TrackedIssue:
    """Convert a database row to a TrackedIssue model."""
    return TrackedIssue(
        issue_id=row["issue_id"],
        rule_id=row["rule_id"],
        issue_type=row["issue_type"],
        file_path=row["file_path"],
        line_number=row["line_number"],
        severity=row["severity"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        first_detected=datetime.fromisoformat(row["first_detected"]),
        last_seen=datetime.fromisoformat(row["last_seen"]),
        resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        false_positive_reason=row["false_positive_reason"],
        assigned_to=row["assigned_to"],
        git_blame_author=row["git_blame_author"],
        git_blame_commit=row["git_blame_commit"],
        tags=json.loads(row["tags_json"] or "[]"),
        comments=json.loads(row["comments_json"] or "[]"),
        scan_count=row["scan_count"],
    )
