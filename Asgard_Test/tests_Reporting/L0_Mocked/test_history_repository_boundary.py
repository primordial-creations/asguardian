"""Boundary and shared-behavior contracts for Reporting History storage."""

from __future__ import annotations

import ast
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Asgard.Reporting.History.infrastructure.persistence.sqlite_history_repository import (
    SQLiteHistoryRepository,
)
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot
from Asgard.Reporting.History.ports.history_repository import IHistoryRepository
from Asgard.Reporting.History.services.history_store import HistoryStore

REPO_ROOT = Path(__file__).resolve().parents[3]
PORT = (
    REPO_ROOT
    / "Asgard"
    / "Reporting"
    / "History"
    / "ports"
    / "history_repository.py"
)


def _infrastructure_imports(path: Path) -> list[int]:
    """Return executable imports of the History infrastructure package."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        if any(
            name.startswith("Asgard.Reporting.History.infrastructure")
            for name in names
        ):
            lines.append(node.lineno)
    return lines


class InMemoryHistoryRepository:
    """Minimal fake exercising the same port as the SQLite adapter."""

    def __init__(self) -> None:
        self.snapshots: list[AnalysisSnapshot] = []

    def save_snapshot(self, snapshot: AnalysisSnapshot) -> str:
        if not snapshot.snapshot_id:
            snapshot = snapshot.copy(update={"snapshot_id": str(uuid.uuid4())})
        self.snapshots = [
            current
            for current in self.snapshots
            if current.snapshot_id != snapshot.snapshot_id
        ]
        self.snapshots.append(snapshot)
        return snapshot.snapshot_id

    def get_snapshots(
        self, project_path: str, limit: int = 50
    ) -> list[AnalysisSnapshot]:
        resolved = str(Path(project_path).resolve())
        matches = [
            snapshot
            for snapshot in self.snapshots
            if str(Path(snapshot.project_path).resolve()) == resolved
        ]
        return sorted(matches, key=lambda item: item.scan_timestamp, reverse=True)[:limit]

    def get_latest_snapshot(self, project_path: str) -> AnalysisSnapshot | None:
        matches = self.get_snapshots(project_path, limit=1)
        return matches[0] if matches else None


def _assert_repository_contract(repository: IHistoryRepository, project: str) -> None:
    first = AnalysisSnapshot(
        snapshot_id="",
        project_path=project,
        scan_timestamp=datetime(2026, 9, 8, 12, 0),
    )
    second = AnalysisSnapshot(
        snapshot_id="newer",
        project_path=project,
        scan_timestamp=datetime(2026, 9, 8, 12, 0) + timedelta(minutes=1),
    )

    generated_id = repository.save_snapshot(first)
    repository.save_snapshot(second)

    assert generated_id
    assert [item.snapshot_id for item in repository.get_snapshots(project)] == [
        "newer",
        generated_id,
    ]
    assert repository.get_snapshots(project, limit=1)[0].snapshot_id == "newer"
    assert repository.get_latest_snapshot(project).snapshot_id == "newer"  # type: ignore[union-attr]
    assert repository.get_snapshots(project + "-other") == []


def test_history_port_rejects_executable_infrastructure_imports(tmp_path: Path) -> None:
    assert _infrastructure_imports(PORT) == []

    violating = tmp_path / "violating_port.py"
    violating.write_text(
        "from Asgard.Reporting.History.infrastructure.persistence "
        "import SQLiteHistoryRepository\n",
        encoding="utf-8",
    )
    assert _infrastructure_imports(violating) == [1]

    docstring_only = tmp_path / "documentation.py"
    docstring_only.write_text(
        '"""from Asgard.Reporting.History.infrastructure import example"""\n',
        encoding="utf-8",
    )
    assert _infrastructure_imports(docstring_only) == []


def test_importing_history_port_does_not_load_sqlite_adapter() -> None:
    script = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from Asgard.Reporting.History.ports.history_repository import IHistoryRepository
loaded = set(sys.modules)
assert 'Asgard.Reporting.History.infrastructure.persistence.history_schema' not in loaded
assert 'Asgard.Reporting.History.infrastructure.persistence.sqlite_history_repository' not in loaded
assert IHistoryRepository.__name__ == 'IHistoryRepository'
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_private_concrete_import_remains_a_lazy_compatibility_alias() -> None:
    from Asgard.Reporting.History.services._history_repository import (
        SQLiteHistoryRepository as LegacySQLiteHistoryRepository,
    )

    assert LegacySQLiteHistoryRepository is SQLiteHistoryRepository


def test_reporting_public_exports_remain_resolvable() -> None:
    script = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
import Asgard.Reporting as reporting
import Asgard.Reporting.History as history
import Asgard.Reporting.History.services as services
for package in (reporting, history, services):
    for name in package.__all__:
        getattr(package, name)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("adapter", ["fake", "sqlite"])
def test_fake_and_sqlite_satisfy_the_same_contract(
    adapter: str, tmp_path: Path
) -> None:
    repository: IHistoryRepository
    if adapter == "fake":
        repository = InMemoryHistoryRepository()
    else:
        repository = SQLiteHistoryRepository(tmp_path / "history.db")

    assert isinstance(repository, IHistoryRepository)
    _assert_repository_contract(repository, str(tmp_path / "project"))


def test_legacy_history_store_composes_an_injected_port(tmp_path: Path) -> None:
    repository = InMemoryHistoryRepository()
    store = HistoryStore(repository=repository)

    _assert_repository_contract(store, str(tmp_path / "project"))
    assert store._repository is repository
