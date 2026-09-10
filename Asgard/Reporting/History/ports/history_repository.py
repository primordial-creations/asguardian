"""Persistence port for analysis-history snapshots.

This module is deliberately dependency-light. Importing the application-facing
contract must not load SQLite schema helpers or create filesystem state.
"""

from typing import List, Optional, Protocol, runtime_checkable

from Asgard.Reporting.History.models.history_models import AnalysisSnapshot


@runtime_checkable
class IHistoryRepository(Protocol):
    """Storage contract used by history application services."""

    def save_snapshot(self, snapshot: AnalysisSnapshot) -> str:
        """Persist an analysis snapshot and return its snapshot ID."""
        ...

    def get_snapshots(
        self, project_path: str, limit: int = 50
    ) -> List[AnalysisSnapshot]:
        """Return snapshots for a project in reverse chronological order."""
        ...

    def get_latest_snapshot(self, project_path: str) -> Optional[AnalysisSnapshot]:
        """Return the most recent project snapshot, or ``None``."""
        ...
