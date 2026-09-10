"""History services and compatibility exports.

Concrete persistence exports are lazy so importing this package does not make
the repository port depend on SQLite as a side effect.
"""

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "HistoryStore": "Asgard.Reporting.History.services.history_store",
    "IHistoryRepository": "Asgard.Reporting.History.ports.history_repository",
    "ReportingAnalyzerService": "Asgard.Reporting.History.services.reporting_analyzer",
    "SQLiteHistoryRepository": (
        "Asgard.Reporting.History.infrastructure.persistence.sqlite_history_repository"
    ),
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value

__all__ = [
    "HistoryStore",
    "IHistoryRepository",
    "ReportingAnalyzerService",
    "SQLiteHistoryRepository",
]
