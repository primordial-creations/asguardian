"""
Asgard History Store Service

Persists analysis snapshots to a local SQLite database and provides simple
retrieval operations. Trend analysis has been separated into
ReportingAnalyzerService to keep this adapter focused on persistence only.

This class is a thin facade over SQLiteHistoryRepository and is retained
for backward compatibility with existing callers. New code should depend
directly on IHistoryRepository.
"""

from pathlib import Path
from typing import List, Optional

from Asgard.Reporting.History.models.history_models import AnalysisSnapshot
from Asgard.Reporting.History.infrastructure.persistence.sqlite_history_repository import (
    SQLiteHistoryRepository,
)
from Asgard.Reporting.History.ports.history_repository import IHistoryRepository


class HistoryStore:
    """
    Persists and retrieves analysis snapshots for trend tracking.

    Uses a SQLite database at ~/.asgard/history.db by default. The database
    is created automatically on first use.

    This compatibility facade is also a composition boundary: it preserves the
    historical no-argument SQLite default while application services depend on
    the separate ``IHistoryRepository`` port.

    Usage:
        store = HistoryStore()
        snapshot_id = store.save_snapshot(snapshot)
        latest = store.get_latest_snapshot("/path/to/project")

    For trend analysis, use ReportingAnalyzerService with this store as the
    repository dependency.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        repository: Optional[IHistoryRepository] = None,
    ) -> None:
        """
        Initialise the history store.

        Args:
            db_path: Path to the SQLite database file. Defaults to ~/.asgard/history.db.
                     Ignored if repository is provided.
            repository: IHistoryRepository implementation to delegate to. If not
                        provided, a SQLiteHistoryRepository is created using db_path.
        """
        if repository is not None:
            self._repository: IHistoryRepository = repository
        else:
            self._repository = SQLiteHistoryRepository(db_path=db_path)

    def save_snapshot(self, snapshot: AnalysisSnapshot) -> str:
        """
        Persist an analysis snapshot to the database.

        Args:
            snapshot: The snapshot to store. If snapshot_id is empty a new UUID
                      is assigned automatically.

        Returns:
            The snapshot_id of the stored record.
        """
        return self._repository.save_snapshot(snapshot)

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
        return self._repository.get_snapshots(project_path, limit=limit)

    def get_latest_snapshot(self, project_path: str) -> Optional[AnalysisSnapshot]:
        """
        Return the most recent snapshot for a project, or None.

        Args:
            project_path: Absolute path to the project root.

        Returns:
            Most recent AnalysisSnapshot or None if no history exists.
        """
        return self._repository.get_latest_snapshot(project_path)
