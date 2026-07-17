"""L0 tests: SRI attribute validation and mixed-content classification (Plan 05)."""

import base64

import pytest

from Asgard.Freya.Security.models.security_header_models import (
    MixedContentReport,
    SRIReport,
)
from Asgard.Freya.Security.services.mixed_content_checker import (
    classify_mixed_request,
    scan_static_dom,
)
from Asgard.Freya.Security.services.sri_checker import (
    evaluate_sri_elements,
    is_valid_integrity,
)
from Asgard.Freya.Scoring.services.severity_mapper import security_report_to_findings
from Asgard.Freya.Scoring.models.scoring_models import UniversalSeverity

PAGE = "https://example.com/page"
_VALID_B64 = base64.b64encode(b"x" * 48).decode()
VALID_SHA384 = f"sha384-{_VALID_B64}"


class TestIntegrityFormat:
    @pytest.mark.parametrize("value,expected", [
        (VALID_SHA384, True),
        (f"sha256-{_VALID_B64}", True),
        (f"sha512-{_VALID_B64}", True),
        (f"sha384-{_VALID_B64} sha512-{_VALID_B64}", True),  # multiple tokens
        ("md5-" + _VALID_B64, False),          # bad algorithm
        ("sha384-!!!notbase64!!!", False),     # bad base64
        ("sha384" + _VALID_B64, False),        # missing dash
        ("", False),
        (None, False),
    ])
    def test_matrix(self, value, expected):
        assert is_valid_integrity(value) is expected


class TestEvaluateSRIElements:
    def test_missing_integrity_on_cross_origin_script(self):
        findings, scripts, styles, protected = evaluate_sri_elements(
            [{"element": "script", "url": "https://cdn.other.com/a.js",
              "integrity": None, "crossorigin": None}], PAGE)
        assert scripts == 1 and protected == 0
        assert findings[0].issue_type == "sri_missing"
        assert findings[0].severity == "moderate"
        assert "Missing Mitigation" in findings[0].description

    def test_stylesheet_missing_is_minor(self):
        findings, _, styles, _ = evaluate_sri_elements(
            [{"element": "stylesheet", "url": "https://cdn.other.com/a.css",
              "integrity": None, "crossorigin": None}], PAGE)
        assert styles == 1
        assert findings[0].severity == "minor"

    def test_malformed_hash(self):
        findings, *_ = evaluate_sri_elements(
            [{"element": "script", "url": "https://cdn.other.com/a.js",
              "integrity": "md5-nope", "crossorigin": "anonymous"}], PAGE)
        assert findings[0].issue_type == "sri_malformed"

    def test_valid_integrity_without_crossorigin(self):
        findings, *_ = evaluate_sri_elements(
            [{"element": "script", "url": "https://cdn.other.com/a.js",
              "integrity": VALID_SHA384, "crossorigin": None}], PAGE)
        assert findings[0].issue_type == "sri_missing_crossorigin"

    def test_fully_protected_yields_yes_but_note(self):
        findings, _, _, protected = evaluate_sri_elements(
            [{"element": "script", "url": "https://cdn.other.com/a.js",
              "integrity": VALID_SHA384, "crossorigin": "anonymous"}], PAGE)
        assert protected == 1
        assert findings[0].issue_type == "sri_present_needs_verification"
        assert "pins a version, not its safety" in findings[0].description

    def test_same_origin_and_relative_urls_skipped(self):
        findings, scripts, styles, _ = evaluate_sri_elements([
            {"element": "script", "url": "https://example.com/local.js",
             "integrity": None, "crossorigin": None},
            {"element": "script", "url": "/relative.js",
             "integrity": None, "crossorigin": None},
        ], PAGE)
        assert findings == [] and scripts == 0 and styles == 0


class TestMixedContentClassification:
    def test_active_script(self):
        finding = classify_mixed_request(PAGE, "http://evil.com/a.js", "script")
        assert finding.category == "active"
        assert finding.severity == "serious"
        assert "deterministic" in finding.description

    def test_passive_image(self):
        finding = classify_mixed_request(PAGE, "http://cdn.com/a.png", "image")
        assert finding.category == "passive"
        assert finding.severity == "moderate"

    def test_https_request_not_mixed(self):
        assert classify_mixed_request(PAGE, "https://cdn.com/a.js", "script") is None

    def test_localhost_excluded(self):
        assert classify_mixed_request(PAGE, "http://localhost:3000/a.js", "script") is None
        assert classify_mixed_request(PAGE, "http://127.0.0.1/a.js", "script") is None

    def test_http_page_not_applicable(self):
        assert classify_mixed_request(
            "http://example.com", "http://cdn.com/a.js", "script") is None

    def test_unknown_type_treated_active(self):
        finding = classify_mixed_request(PAGE, "http://x.com/y", "weird")
        assert finding.category == "active"


class TestStaticDomScan:
    def test_finds_http_attributes(self):
        html = ('<img src="http://cdn.com/a.png">'
                '<form action="http://cdn.com/submit"></form>'
                '<a href="https://fine.com">ok</a>')
        findings = scan_static_dom(html, PAGE)
        urls = {f.url for f in findings}
        assert urls == {"http://cdn.com/a.png", "http://cdn.com/submit"}
        assert all(f.category == "static_dom" for f in findings)

    def test_dedupes_and_excludes_localhost(self):
        html = ('<img src="http://cdn.com/a.png"><img src="http://cdn.com/a.png">'
                '<img src="http://localhost/b.png">')
        assert len(scan_static_dom(html, PAGE)) == 1

    def test_http_page_returns_nothing(self):
        assert scan_static_dom('<img src="http://x.com/a.png">', "http://page.com") == []


class TestFindingsAdapter:
    def test_sri_report_maps_to_universal_findings(self):
        findings_raw, *_ = evaluate_sri_elements(
            [{"element": "script", "url": "https://cdn.other.com/a.js",
              "integrity": None, "crossorigin": None}], PAGE)
        report = SRIReport(url=PAGE, issues=findings_raw)
        findings = security_report_to_findings(report)
        assert len(findings) == 1
        assert findings[0].category == "security"
        assert findings[0].severity == UniversalSeverity.MAJOR

    def test_mixed_active_maps_to_critical_not_blocker(self):
        finding = classify_mixed_request(PAGE, "http://evil.com/a.js", "script")
        report = MixedContentReport(url=PAGE, issues=[finding])
        findings = security_report_to_findings(report)
        assert findings[0].severity == UniversalSeverity.CRITICAL
