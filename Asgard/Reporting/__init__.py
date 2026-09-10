"""Report generators and optional reporting adapters.

Public names are resolved lazily so importing a narrow port below
``Asgard.Reporting`` does not initialize unrelated HTML, PR, or SQLite
adapters as a parent-package side effect.
"""

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "HTMLReportGenerator": "Asgard.Reporting.html_generator",
    "GitHubActionsFormatter": "Asgard.Reporting.github_formatter",
    "History": "Asgard.Reporting.History",
    "AnalysisSnapshot": "Asgard.Reporting.History",
    "HistoryStore": "Asgard.Reporting.History",
    "MetricSnapshot": "Asgard.Reporting.History",
    "MetricTrend": "Asgard.Reporting.History",
    "TrendDirection": "Asgard.Reporting.History",
    "TrendReport": "Asgard.Reporting.History",
    "PRDecoration": "Asgard.Reporting.PRDecoration",
    "GitHubDecorator": "Asgard.Reporting.PRDecoration",
    "GitLabDecorator": "Asgard.Reporting.PRDecoration",
    "IssueComment": "Asgard.Reporting.PRDecoration",
    "PRDecorationConfig": "Asgard.Reporting.PRDecoration",
    "PRDecorationResult": "Asgard.Reporting.PRDecoration",
    "PRPlatform": "Asgard.Reporting.PRDecoration",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = module if name in {"History", "PRDecoration"} else getattr(module, name)
    globals()[name] = value
    return value

__all__ = [
    "HTMLReportGenerator",
    "GitHubActionsFormatter",
    # History subpackage
    "History",
    "AnalysisSnapshot",
    "HistoryStore",
    "MetricSnapshot",
    "MetricTrend",
    "TrendDirection",
    "TrendReport",
    # PRDecoration subpackage
    "PRDecoration",
    "GitHubDecorator",
    "GitLabDecorator",
    "IssueComment",
    "PRDecorationConfig",
    "PRDecorationResult",
    "PRPlatform",
]
