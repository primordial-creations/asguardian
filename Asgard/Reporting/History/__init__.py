"""
Asgard Reporting History - Metrics History and Trend Tracking

Provides SQLite-backed persistence of analysis snapshots and trend computation
across successive runs. Supports CI/CD integration by recording quality metrics
over time and surfacing whether the codebase is improving, stable, or degrading.

Usage:
    from Asgard.Reporting.History import (
        HistoryStore, ReportingAnalyzerService, AnalysisSnapshot, MetricSnapshot
    )

    store = HistoryStore()
    analyzer = ReportingAnalyzerService(repository=store)

    snapshot = AnalysisSnapshot(
        snapshot_id="<uuid>",
        project_path="./src",
        git_commit="abc1234",
        metrics=[
            MetricSnapshot(metric_name="security_score", value=85.0, unit="score"),
            MetricSnapshot(metric_name="duplication_percentage", value=2.5, unit="%"),
        ],
        quality_gate_status="passed",
        ratings={"security": "A", "reliability": "B"},
    )
    store.save_snapshot(snapshot)

    trends = analyzer.get_trend_report("./src")
    for trend in trends.metric_trends:
        print(f"{trend.metric_name}: {trend.direction} ({trend.change_percentage:+.1f}%)")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "AnalysisSnapshot": "Asgard.Reporting.History.models.history_models",
    "MetricSnapshot": "Asgard.Reporting.History.models.history_models",
    "MetricTrend": "Asgard.Reporting.History.models.history_models",
    "TrendDirection": "Asgard.Reporting.History.models.history_models",
    "TrendReport": "Asgard.Reporting.History.models.history_models",
    "IHistoryRepository": "Asgard.Reporting.History.ports.history_repository",
    "SQLiteHistoryRepository": (
        "Asgard.Reporting.History.infrastructure.persistence.sqlite_history_repository"
    ),
    "HistoryStore": "Asgard.Reporting.History.services.history_store",
    "ReportingAnalyzerService": "Asgard.Reporting.History.services.reporting_analyzer",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value

__all__ = [
    "AnalysisSnapshot",
    "HistoryStore",
    "IHistoryRepository",
    "MetricSnapshot",
    "MetricTrend",
    "ReportingAnalyzerService",
    "SQLiteHistoryRepository",
    "TrendDirection",
    "TrendReport",
]
