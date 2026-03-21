"""
Heimdall Issue Tracker - query and summary helpers.

Standalone functions for reading issues from the database.
Each function accepts an open sqlite3.Connection so the IssueTracker
can manage connection lifecycle itself.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional

from Asgard.Heimdall.Issues.models.issue_models import (
    IssueFilter,
    IssueStatus,
    IssuesSummary,
    TrackedIssue,
)
from Asgard.Heimdall.Issues.services._issue_db import row_to_issue


def query_issues(
    conn: sqlite3.Connection,
    project_path: str,
    issue_filter: Optional[IssueFilter] = None,
) -> List[TrackedIssue]:
    """
    Retrieve issues for a project with optional filtering.

    Args:
        conn: Open database connection.
        project_path: The project root path to query.
        issue_filter: Optional filter criteria.

    Returns:
        List of matching TrackedIssue objects.
    """
    query = "SELECT * FROM issues WHERE project_path = ?"
    params: List = [project_path]

    if issue_filter:
        if issue_filter.status:
            placeholders = ",".join("?" for _ in issue_filter.status)
            values = [
                s if isinstance(s, str) else s.value
                for s in issue_filter.status
            ]
            query += f" AND status IN ({placeholders})"
            params.extend(values)

        if issue_filter.severity:
            placeholders = ",".join("?" for _ in issue_filter.severity)
            values = [
                s if isinstance(s, str) else s.value
                for s in issue_filter.severity
            ]
            query += f" AND severity IN ({placeholders})"
            params.extend(values)

        if issue_filter.issue_type:
            placeholders = ",".join("?" for _ in issue_filter.issue_type)
            values = [
                t if isinstance(t, str) else t.value
                for t in issue_filter.issue_type
            ]
            query += f" AND issue_type IN ({placeholders})"
            params.extend(values)

        if issue_filter.file_path_contains:
            query += " AND file_path LIKE ?"
            params.append(f"%{issue_filter.file_path_contains}%")

        if issue_filter.assigned_to:
            query += " AND assigned_to = ?"
            params.append(issue_filter.assigned_to)

        if issue_filter.rule_id:
            query += " AND rule_id = ?"
            params.append(issue_filter.rule_id)

    query += " ORDER BY first_detected DESC"

    rows = conn.execute(query, params).fetchall()
    return [row_to_issue(row) for row in rows]


def build_summary(conn: sqlite3.Connection, project_path: str) -> IssuesSummary:
    """
    Generate an aggregated summary of issues for a project.

    Args:
        conn: Open database connection.
        project_path: The project root path.

    Returns:
        IssuesSummary with counts broken down by status, severity, and type.
    """
    rows = conn.execute(
        "SELECT * FROM issues WHERE project_path = ?",
        (project_path,),
    ).fetchall()

    summary = IssuesSummary(project_path=project_path)
    oldest: Optional[datetime] = None

    for row in rows:
        status = row["status"]
        severity = row["severity"]
        issue_type = row["issue_type"]

        if status == IssueStatus.OPEN.value:
            summary.total_open += 1
            summary.open_by_severity[severity] = summary.open_by_severity.get(severity, 0) + 1
            summary.open_by_type[issue_type] = summary.open_by_type.get(issue_type, 0) + 1
            first = datetime.fromisoformat(row["first_detected"])
            if oldest is None or first < oldest:
                oldest = first

        elif status == IssueStatus.CONFIRMED.value:
            summary.total_confirmed += 1
            summary.open_by_severity[severity] = summary.open_by_severity.get(severity, 0) + 1
            summary.open_by_type[issue_type] = summary.open_by_type.get(issue_type, 0) + 1

        elif status == IssueStatus.FALSE_POSITIVE.value:
            summary.total_false_positives += 1

        elif status == IssueStatus.WONT_FIX.value:
            summary.total_wont_fix += 1

        elif status in (IssueStatus.RESOLVED.value, IssueStatus.CLOSED.value):
            summary.total_resolved += 1

    summary.oldest_open_issue = oldest
    return summary
