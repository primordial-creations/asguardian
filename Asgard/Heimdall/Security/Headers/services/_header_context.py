"""
Security-headers context post-processing (plan 07.9/06).

Applies two cross-cutting, finding-list-wide adjustments after all header
sub-analyzers (validator/CSP/CORS) have produced their findings, mirroring
the ``apply_compliance_mapping`` pattern used for Container/IaC:

1. ``mechanism_id`` / ``confidence_bucket`` assignment for every finding
   (normalization engine, plan 06) -- done unconditionally.
2. The ``is_api`` context modifier (plan 07.9): on a pure JSON/API surface
   with no browser-rendered HTML, browser-only findings (CSP, X-Frame,
   cookie SameSite, Permissions-Policy -- see
   ``BROWSER_ONLY_FINDING_TYPES`` in header_models.py) are downgraded, not
   suppressed. Downgrade = one severity step down (never below LOW) plus a
   confidence multiplier, and ``context_downgraded=True`` is set so the
   finding remains fully visible/auditable in the report.

Honest FP/FN note: ``is_api`` is caller-declared (``HeaderConfig.is_api``),
not auto-detected -- there is no reliable static signal that a Python/Node
service never serves any HTML (a "JSON API" can still have a debug/docs
page, an OAuth redirect landing page, etc.), so this scanner does not try
to infer it. If the caller mis-declares is_api=True on an app that does
serve HTML, real browser-exposure findings will be under-severitized here
-- this is a known, accepted risk of a caller-supplied flag, not a scanner
FN.
"""

from typing import List

from Asgard.Heimdall.Security.Headers.models.header_models import (
    BROWSER_ONLY_FINDING_TYPES,
    HeaderFinding,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

_SEVERITY_STEP_DOWN = {
    SecuritySeverity.CRITICAL.value: SecuritySeverity.HIGH.value,
    SecuritySeverity.HIGH.value: SecuritySeverity.MEDIUM.value,
    SecuritySeverity.MEDIUM.value: SecuritySeverity.LOW.value,
    SecuritySeverity.LOW.value: SecuritySeverity.LOW.value,
    SecuritySeverity.INFO.value: SecuritySeverity.INFO.value,
}

_IS_API_CONFIDENCE_MULTIPLIER = 0.6


def apply_header_context(findings: List[HeaderFinding], is_api: bool = False) -> None:
    """Mutate ``findings`` in place: assign mechanism_id/confidence_bucket,
    and if ``is_api`` is True, downgrade browser-only finding types."""
    for finding in findings:
        if not finding.mechanism_id:
            finding.mechanism_id = f"headers.{finding.finding_type}"

        if is_api and finding.finding_type in BROWSER_ONLY_FINDING_TYPES:
            finding.severity = _SEVERITY_STEP_DOWN.get(finding.severity, finding.severity)
            finding.confidence = max(0.1, finding.confidence * _IS_API_CONFIDENCE_MULTIPLIER)
            finding.context_downgraded = True

        finding.confidence_bucket = confidence_bucket(finding.confidence)
