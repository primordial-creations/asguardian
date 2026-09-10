"""Compatibility import for the History repository port.

The contract moved to ``History.ports`` so importing it never loads a concrete
persistence adapter. The underscored module remains for existing callers.
"""

from importlib import import_module

from Asgard.Reporting.History.ports.history_repository import IHistoryRepository


def __getattr__(name: str):
    """Resolve the former private concrete export without eager infrastructure."""
    if name == "SQLiteHistoryRepository":
        module = import_module(
            "Asgard.Reporting.History.infrastructure.persistence."
            "sqlite_history_repository"
        )
        return module.SQLiteHistoryRepository
    raise AttributeError(name)

__all__ = ["IHistoryRepository", "SQLiteHistoryRepository"]
