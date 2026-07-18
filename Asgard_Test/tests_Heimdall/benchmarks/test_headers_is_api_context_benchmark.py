"""Benchmark for the Headers ``is_api`` context modifier (plan 07.9/06).

A pure JSON/API surface has no browser-rendered HTML, so browser-only
findings (CSP, X-Frame-Options, cookie SameSite, Permissions-Policy) are
downgraded -- never suppressed -- while non-browser-only findings (e.g.
CORS wildcard-with-credentials, which matters for any HTTP surface) are
left untouched.
"""
from Asgard.Heimdall.Security.Headers.models.header_models import HeaderFinding
from Asgard.Heimdall.Security.Headers.services._header_context import apply_header_context


def _finding(finding_type: str, severity: str, confidence: float = 0.6) -> HeaderFinding:
    return HeaderFinding(
        file_path="app.py",
        line_number=1,
        finding_type=finding_type,
        severity=severity,
        title="t",
        description="d",
        confidence=confidence,
    )


def test_is_api_downgrades_missing_csp_severity_and_confidence():
    f = _finding("missing_csp", "high", confidence=0.6)
    apply_header_context([f], is_api=True)
    assert f.severity == "medium"
    assert f.confidence < 0.6
    assert f.context_downgraded is True


def test_is_api_never_suppresses_only_downgrades():
    f = _finding("missing_csp", "high", confidence=0.6)
    apply_header_context([f], is_api=True)
    # still present, still reported -- never dropped
    assert f.severity in ("low", "medium", "high")
    assert f.confidence > 0.0


def test_is_api_false_leaves_browser_only_finding_untouched():
    f = _finding("missing_csp", "high", confidence=0.6)
    apply_header_context([f], is_api=False)
    assert f.severity == "high"
    assert f.context_downgraded is False


def test_is_api_does_not_downgrade_non_browser_only_finding():
    f = _finding("cors_credentials_with_wildcard", "critical", confidence=0.9)
    apply_header_context([f], is_api=True)
    assert f.severity == "critical"
    assert f.context_downgraded is False


def test_low_severity_floor_never_goes_below_low():
    f = _finding("missing_x_frame", "low", confidence=0.5)
    apply_header_context([f], is_api=True)
    assert f.severity == "low"


def test_mechanism_id_assigned_for_all_findings():
    f1 = _finding("missing_csp", "high")
    f2 = _finding("cors_wildcard_origin", "medium")
    apply_header_context([f1, f2], is_api=False)
    assert f1.mechanism_id == "headers.missing_csp"
    assert f2.mechanism_id == "headers.cors_wildcard_origin"
