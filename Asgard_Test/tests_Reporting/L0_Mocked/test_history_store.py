"""
Tests for Asgard HistoryStore Service

Unit tests for persisting analysis snapshots and computing metric trends
using a real SQLite database in a temporary directory.
"""

import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Asgard.Reporting.History.models.history_models import (
    AnalysisSnapshot,
    MetricSnapshot,
    TrendDirection,
)
from Asgard.Reporting.History.services.history_store import HistoryStore
from Asgard.Reporting.History.services.reporting_analyzer import (
    ReportingAnalyzerService,
)


def _make_analyzer(store: HistoryStore) -> ReportingAnalyzerService:
    """Build a ReportingAnalyzerService backed by the store's repository.

    get_trend_report() moved from HistoryStore to ReportingAnalyzerService
    as part of an SRP refactor — HistoryStore now only handles persistence.
    """
    return ReportingAnalyzerService(repository=store._repository)


def _make_snapshot(project_path: str, **metric_kwargs) -> AnalysisSnapshot:
    """Helper to create an AnalysisSnapshot with given metric name=value pairs."""
    metrics = [
        MetricSnapshot(metric_name=name, value=float(value))
        for name, value in metric_kwargs.items()
    ]
    return AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        project_path=project_path,
        scan_timestamp=datetime.now(),
        metrics=metrics,
    )


class TestHistoryStoreSaveAndRetrieve:
    """Tests for saving snapshots and retrieving them."""

    def test_save_and_get_snapshot(self):
        """Saving a snapshot and then retrieving it returns the same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            snapshot = _make_snapshot(project_path, security_score=85.0)
            snapshot_id = store.save_snapshot(snapshot)

            snapshots = store.get_snapshots(project_path)
            assert len(snapshots) == 1
            retrieved = snapshots[0]
            assert retrieved.snapshot_id == snapshot_id
            assert retrieved.get_metric("security_score") == 85.0

    def test_get_snapshots_empty_store(self):
        """get_snapshots returns an empty list when no snapshots exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "empty_project")

            result = store.get_snapshots(project_path)
            assert result == []

    def test_get_snapshots_multiple_snapshots(self):
        """Multiple snapshots are stored and retrieved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            for i in range(3):
                snap = _make_snapshot(project_path, security_score=float(70 + i * 5))
                store.save_snapshot(snap)

            snapshots = store.get_snapshots(project_path)
            assert len(snapshots) == 3

    def test_get_snapshots_returns_newest_first(self):
        """get_snapshots returns snapshots in reverse chronological order (newest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i in range(3):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[MetricSnapshot(metric_name="score", value=float(i))],
                )
                store.save_snapshot(snap)

            snapshots = store.get_snapshots(project_path)
            timestamps = [s.scan_timestamp for s in snapshots]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_get_snapshots_isolated_per_project(self):
        """Snapshots for one project are not returned when querying a different project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_a = str(Path(tmpdir) / "project_a")
            project_b = str(Path(tmpdir) / "project_b")

            store.save_snapshot(_make_snapshot(project_a, score=90.0))
            store.save_snapshot(_make_snapshot(project_b, score=80.0))

            a_snapshots = store.get_snapshots(project_a)
            b_snapshots = store.get_snapshots(project_b)
            assert len(a_snapshots) == 1
            assert len(b_snapshots) == 1
            assert a_snapshots[0].get_metric("score") == 90.0
            assert b_snapshots[0].get_metric("score") == 80.0

    def test_get_latest_snapshot_returns_most_recent(self):
        """get_latest_snapshot returns only the most recently stored snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i in range(3):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[MetricSnapshot(metric_name="score", value=float(i * 10))],
                )
                store.save_snapshot(snap)

            latest = store.get_latest_snapshot(project_path)
            assert latest is not None
            assert latest.get_metric("score") == 20.0

    def test_get_latest_snapshot_none_when_empty(self):
        """get_latest_snapshot returns None when no snapshots exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "no_project")
            assert store.get_latest_snapshot(project_path) is None

    def test_save_snapshot_assigns_id_if_empty(self):
        """save_snapshot assigns a UUID if snapshot_id is empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            snap = AnalysisSnapshot(
                snapshot_id="",
                project_path=project_path,
                scan_timestamp=datetime.now(),
                metrics=[],
            )
            returned_id = store.save_snapshot(snap)
            assert returned_id != ""
            snapshots = store.get_snapshots(project_path)
            assert len(snapshots) == 1
            assert snapshots[0].snapshot_id == returned_id


class TestHistoryStoreTrendReport:
    """Tests for HistoryStore.get_trend_report()."""

    def test_trend_report_empty_store(self):
        """get_trend_report returns an empty report when no snapshots exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "empty_project")

            report = _make_analyzer(store).get_trend_report(project_path)
            assert report.analysis_count == 0
            assert report.metric_trends == []
            assert report.first_analysis is None
            assert report.last_analysis is None

    def test_trend_report_improving_metric(self):
        """get_trend_report reports IMPROVING when a higher-is-better metric increases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i, value in enumerate([70.0, 85.0]):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[MetricSnapshot(metric_name="security_score", value=value)],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            assert report.analysis_count == 2
            trend = next(
                (t for t in report.metric_trends if t.metric_name == "security_score"),
                None,
            )
            assert trend is not None
            assert trend.direction == TrendDirection.IMPROVING

    def test_trend_report_degrading_metric(self):
        """get_trend_report reports DEGRADING when a higher-is-better metric decreases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i, value in enumerate([85.0, 60.0]):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[MetricSnapshot(metric_name="security_score", value=value)],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            trend = next(
                (t for t in report.metric_trends if t.metric_name == "security_score"),
                None,
            )
            assert trend is not None
            assert trend.direction == TrendDirection.DEGRADING

    def test_trend_report_stable_metric(self):
        """get_trend_report reports STABLE when a metric changes by less than 5%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i, value in enumerate([80.0, 81.0]):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[MetricSnapshot(metric_name="security_score", value=value)],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            trend = next(
                (t for t in report.metric_trends if t.metric_name == "security_score"),
                None,
            )
            assert trend is not None
            assert trend.direction == TrendDirection.STABLE

    def test_trend_report_lower_is_better_improving(self):
        """A lower-is-better metric that decreases is reported as IMPROVING."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i, value in enumerate([30.0, 10.0]):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[
                        MetricSnapshot(metric_name="duplication_percentage", value=value)
                    ],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            trend = next(
                (t for t in report.metric_trends if t.metric_name == "duplication_percentage"),
                None,
            )
            assert trend is not None
            assert trend.direction == TrendDirection.IMPROVING

    def test_trend_report_lower_is_better_degrading(self):
        """A lower-is-better metric that increases is reported as DEGRADING."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i, value in enumerate([5.0, 25.0]):
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=base_time + timedelta(days=i),
                    metrics=[
                        MetricSnapshot(metric_name="duplication_percentage", value=value)
                    ],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            trend = next(
                (t for t in report.metric_trends if t.metric_name == "duplication_percentage"),
                None,
            )
            assert trend is not None
            assert trend.direction == TrendDirection.DEGRADING

    def test_trend_report_timestamps(self):
        """TrendReport first_analysis and last_analysis reflect stored snapshot times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            first_time = datetime(2025, 1, 1, 12, 0, 0)
            last_time = datetime(2025, 3, 1, 12, 0, 0)

            for ts in [first_time, last_time]:
                snap = AnalysisSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    project_path=project_path,
                    scan_timestamp=ts,
                    metrics=[MetricSnapshot(metric_name="score", value=80.0)],
                )
                store.save_snapshot(snap)

            report = _make_analyzer(store).get_trend_report(project_path)
            assert report.first_analysis is not None
            assert report.last_analysis is not None

    def test_trend_report_single_snapshot_no_trends(self):
        """A single snapshot produces no metric trends (need at least two data points)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            store = HistoryStore(db_path=db_path)
            project_path = str(Path(tmpdir) / "my_project")

            store.save_snapshot(_make_snapshot(project_path, security_score=80.0))

            report = _make_analyzer(store).get_trend_report(project_path)
            assert report.analysis_count == 1
            assert report.metric_trends == []
