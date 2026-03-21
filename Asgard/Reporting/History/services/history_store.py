"""
Asgard History Store Service

Persists analysis snapshots to a local SQLite database at ~/.asgard/history.db
and provides trend analysis across successive snapshots for a given project.

The store is intentionally lightweight: it uses only the Python stdlib sqlite3
module and avoids external dependencies. All JSON serialisation is handled
in-process before writing to the database.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

from Asgard.Reporting.History.models.history_models import (
    AnalysisSnapshot,
    MetricSnapshot,
    MetricTrend,
    TrendDirection,
    TrendReport,
)
from Asgard.Reporting.History.services._history_db import (
    connect,
    ensure_db,
    get_default_db_path,
    get_lower_is_better_metrics,
    row_to_snapshot,
)


class HistoryStore:
    """
    Persists and retrieves analysis snapshots for trend tracking.

    Uses a SQLite database at ~/.asgard/history.db. The database is created
    automatically on first use.

    Usage:
        store = HistoryStore()

        snapshot = AnalysisSnapshot(
            snapshot_id=str(uuid.uuid4()),
            project_path="/path/to/project",
            metrics=[MetricSnapshot(metric_name="security_score", value=85.0)],
        )
        snapshot_id = store.save_snapshot(snapshot)

        latest = store.get_latest_snapshot("/path/to/project")
        trends = store.get_trend_report("/path/to/project")
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialise the history store.

        Args:
            db_path: Path to the SQLite database file. Defaults to ~/.asgard/history.db.
        """
        self._db_path = db_path or get_default_db_path()
        ensure_db(self._db_path)

    def save_snapshot(self, snapshot: AnalysisSnapshot) -> str:
        """
        Persist an analysis snapshot to the database.

        Args:
            snapshot: The snapshot to store. If snapshot_id is empty a new UUID
                      is assigned automatically.

        Returns:
            The snapshot_id of the stored record.
        """
        if not snapshot.snapshot_id:
            snapshot = snapshot.copy(update={"snapshot_id": str(uuid.uuid4())})

        metrics_data = [
            {"metric_name": m.metric_name, "value": m.value, "unit": m.unit}
            for m in snapshot.metrics
        ]

        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots
                    (id, project_path, scan_timestamp, git_commit, git_branch,
                     quality_gate_status, ratings_json, metrics_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    str(Path(snapshot.project_path).resolve()),
                    snapshot.scan_timestamp.isoformat(),
                    snapshot.git_commit,
                    snapshot.git_branch,
                    snapshot.quality_gate_status,
                    json.dumps(snapshot.ratings),
                    json.dumps(metrics_data),
                ),
            )

        return cast(str, snapshot.snapshot_id)

    def get_snapshots(
        self, project_path: str, limit: int = 50
    ) -> List[AnalysisSnapshot]:
        """
        Return stored snapshots for a project in reverse chronological order.

        Args:
            project_path: Absolute path to the project root.
            limit: Maximum number of snapshots to return.

        Returns:
            List of AnalysisSnapshot objects (newest first).
        """
        resolved = str(Path(project_path).resolve())

        with connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, project_path, scan_timestamp, git_commit, git_branch,
                       quality_gate_status, ratings_json, metrics_json
                FROM snapshots
                WHERE project_path = ?
                ORDER BY scan_timestamp DESC
                LIMIT ?
                """,
                (resolved, limit),
            )
            rows = cursor.fetchall()

        return [row_to_snapshot(row) for row in rows]

    def get_latest_snapshot(self, project_path: str) -> Optional[AnalysisSnapshot]:
        """
        Return the most recent snapshot for a project, or None.

        Args:
            project_path: Absolute path to the project root.

        Returns:
            Most recent AnalysisSnapshot or None if no history exists.
        """
        results = self.get_snapshots(project_path, limit=1)
        return results[0] if results else None

    def get_trend_report(
        self,
        project_path: str,
        metric_names: Optional[List[str]] = None,
    ) -> TrendReport:
        """
        Compute metric trends for a project from all stored snapshots.

        Args:
            project_path: Absolute path to the project root.
            metric_names: Optional list of metric names to include in the report.
                          If None, all metrics present in the snapshots are included.

        Returns:
            TrendReport containing a MetricTrend for each tracked metric.
        """
        snapshots = self.get_snapshots(project_path, limit=100)
        resolved = str(Path(project_path).resolve())

        if not snapshots:
            return TrendReport(
                project_path=resolved,
                metric_trends=[],
                analysis_count=0,
                first_analysis=None,
                last_analysis=None,
                generated_at=datetime.now(),
            )

        chronological = list(reversed(snapshots))
        first_ts = chronological[0].scan_timestamp
        last_ts = chronological[-1].scan_timestamp

        all_metric_names: List[str] = []
        for snap in chronological:
            for m in snap.metrics:
                if m.metric_name not in all_metric_names:
                    all_metric_names.append(m.metric_name)

        if metric_names:
            target_metrics = [n for n in all_metric_names if n in metric_names]
        else:
            target_metrics = all_metric_names

        metric_history: Dict[str, List[Tuple[datetime, float]]] = {
            name: [] for name in target_metrics
        }

        for snap in chronological:
            for name in target_metrics:
                value = snap.get_metric(name)
                if value is not None:
                    metric_history[name].append((snap.scan_timestamp, value))

        trends: List[MetricTrend] = []
        for name in target_metrics:
            history = metric_history[name]
            if len(history) < 2:
                continue

            current_ts, current_value = history[-1]
            prev_ts, previous_value = history[-2]
            change = current_value - previous_value

            if previous_value != 0:
                change_percentage = (change / abs(previous_value)) * 100.0
            else:
                change_percentage = 0.0

            direction = self._compute_direction(name, change_percentage)

            trends.append(MetricTrend(
                metric_name=name,
                current_value=current_value,
                previous_value=previous_value,
                change=change,
                change_percentage=change_percentage,
                direction=direction,
                snapshots=history,
            ))

        return TrendReport(
            project_path=resolved,
            metric_trends=trends,
            analysis_count=len(snapshots),
            first_analysis=first_ts,
            last_analysis=last_ts,
            generated_at=datetime.now(),
        )

    def _compute_direction(
        self, metric_name: str, change_percentage: float
    ) -> TrendDirection:
        """
        Determine the trend direction for a metric.

        For higher-is-better metrics: positive change is IMPROVING, negative is DEGRADING.
        For lower-is-better metrics: the logic is inverted.
        Changes within +/-5% are considered STABLE.

        Args:
            metric_name: Name of the metric.
            change_percentage: Percentage change (current - previous) / previous * 100.

        Returns:
            TrendDirection value.
        """
        threshold = 5.0
        lower_is_better = metric_name in get_lower_is_better_metrics()

        if abs(change_percentage) < threshold:
            return TrendDirection.STABLE

        if lower_is_better:
            if change_percentage <= -threshold:
                return TrendDirection.IMPROVING
            return TrendDirection.DEGRADING
        else:
            if change_percentage >= threshold:
                return TrendDirection.IMPROVING
            return TrendDirection.DEGRADING
