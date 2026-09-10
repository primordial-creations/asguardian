"""SQLite adapter for the Reporting History repository port."""

import json
import uuid
from pathlib import Path
from typing import List, Optional, cast

from Asgard.Reporting.History.infrastructure.persistence.history_schema import (
    connect,
    ensure_db,
    get_default_db_path,
    row_to_snapshot,
)
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot
from Asgard.Reporting.History.ports.history_repository import IHistoryRepository


class SQLiteHistoryRepository(IHistoryRepository):
    """Persist analysis snapshots in the existing SQLite format."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or get_default_db_path()
        ensure_db(self._db_path)

    def save_snapshot(self, snapshot: AnalysisSnapshot) -> str:
        if not snapshot.snapshot_id:
            snapshot = snapshot.copy(update={"snapshot_id": str(uuid.uuid4())})

        metrics_data = [
            {"metric_name": metric.metric_name, "value": metric.value, "unit": metric.unit}
            for metric in snapshot.metrics
        ]

        with connect(self._db_path) as connection:
            connection.execute(
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
        resolved = str(Path(project_path).resolve())

        with connect(self._db_path) as connection:
            cursor = connection.execute(
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
        results = self.get_snapshots(project_path, limit=1)
        return results[0] if results else None
