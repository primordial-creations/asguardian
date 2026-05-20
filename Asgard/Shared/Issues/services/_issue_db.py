"""
Heimdall Issue Tracker - database schema re-exports.

This module re-exports database schema constants and helpers from their
canonical location in infrastructure/persistence/issue_schema.py.

The schema definitions have been moved to the infrastructure layer where
they belong. This shim preserves import compatibility for any code that
still references the old path.
"""

from Asgard.Shared.Issues.infrastructure.persistence.issue_schema import (
    _CREATE_IDX_PROJECT_SQL,
    _CREATE_IDX_STATUS_SQL,
    _CREATE_TABLE_SQL,
    _LINE_PROXIMITY,
    row_to_issue,
)

__all__ = [
    "_CREATE_IDX_PROJECT_SQL",
    "_CREATE_IDX_STATUS_SQL",
    "_CREATE_TABLE_SQL",
    "_LINE_PROXIMITY",
    "row_to_issue",
]
