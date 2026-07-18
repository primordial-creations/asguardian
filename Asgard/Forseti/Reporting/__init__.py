"""
Forseti Reporting - canonical Finding model, audience reporters, sourcemaps.

Analysis is decoupled from presentation: every validator emits `Finding`
objects and all output surfaces (text, explain, json, markdown, SARIF,
GitHub annotations) render from the same finding list.
"""

from Asgard.Forseti.Reporting.models.finding_models import (
    Coordinates,
    Finding,
    Remediation,
    ReportEnvelope,
    ReportSummary,
)
from Asgard.Forseti.Reporting.services.reporter_service import (
    ExplainReporter,
    GithubReporter,
    JsonReporter,
    MarkdownReporter,
    SarifReporter,
    TextReporter,
    select_reporter,
)
from Asgard.Forseti.Reporting.services.finding_adapter_service import (
    legacy_error_to_finding,
    legacy_errors_to_findings,
    result_to_findings,
)
from Asgard.Forseti.Reporting.utilities.sourcemap_loader import (
    annotate_findings,
    build_sourcemap,
    load_with_sourcemap,
    lookup,
)

__all__ = [
    "Coordinates",
    "ExplainReporter",
    "Finding",
    "GithubReporter",
    "JsonReporter",
    "MarkdownReporter",
    "Remediation",
    "ReportEnvelope",
    "ReportSummary",
    "SarifReporter",
    "TextReporter",
    "annotate_findings",
    "build_sourcemap",
    "legacy_error_to_finding",
    "legacy_errors_to_findings",
    "load_with_sourcemap",
    "lookup",
    "result_to_findings",
    "select_reporter",
]
