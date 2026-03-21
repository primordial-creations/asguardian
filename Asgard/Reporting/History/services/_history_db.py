"""
Asgard History Store - Database Helpers

SQLite schema, constants, and row-deserialization helpers for HistoryStore.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Reporting.History.models.history_models import AnalysisSnapshot, MetricSnapshot

_DB_PATH = Path.home() / ".asgard" / "history.db"

_LOWER_IS_BETTER_METRICS = {
    "duplication_percentage",
    "cyclomatic_complexity",
    "technical_debt_hours",
    "critical_vulnerabilities",
    "high_vulnerabilities",
    "naming_violations",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    scan_timestamp TEXT NOT NULL,
    git_commit TEXT,
    git_branch TEXT,
    quality_gate_status TEXT,
    ratings_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_project ON snapshots (project_path);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots (project_path, scan_timestamp);
"""


def get_default_db_path() -> Path:
    """Return the default SQLite database path."""
    return _DB_PATH


def get_lower_is_better_metrics() -> set:
    """Return the set of metric names where lower values are better."""
    return _LOWER_IS_BETTER_METRICS


def ensure_db(db_path: Path) -> None:
    """Create the database and schema if they do not already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    with conn:
        conn.executescript(_SCHEMA)


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a database connection with WAL mode for concurrency safety."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def row_to_snapshot(row: tuple) -> AnalysisSnapshot:
    """Convert a database row tuple into an AnalysisSnapshot."""
    (
        snapshot_id,
        project_path,
        scan_timestamp_str,
        git_commit,
        git_branch,
        quality_gate_status,
        ratings_json,
        metrics_json,
    ) = row

    try:
        scan_timestamp = datetime.fromisoformat(scan_timestamp_str)
    except (ValueError, TypeError):
        scan_timestamp = datetime.now()

    try:
        ratings = json.loads(ratings_json)
    except (ValueError, TypeError):
        ratings = {}

    try:
        metrics_data = json.loads(metrics_json)
        metrics = [
            MetricSnapshot(
                metric_name=m["metric_name"],
                value=float(m["value"]),
                unit=m.get("unit", ""),
            )
            for m in metrics_data
        ]
    except (ValueError, TypeError, KeyError):
        metrics = []

    return AnalysisSnapshot(
        snapshot_id=snapshot_id,
        project_path=project_path,
        scan_timestamp=scan_timestamp,
        git_commit=git_commit,
        git_branch=git_branch,
        quality_gate_status=quality_gate_status,
        ratings=ratings,
        metrics=metrics,
    )
