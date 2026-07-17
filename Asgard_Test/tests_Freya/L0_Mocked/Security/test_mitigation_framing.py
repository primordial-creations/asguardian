"""L0 tests: mitigation vocabulary, framing, disclaimer, scope matrix (Plan 05)."""

import httpx
import pytest

from Asgard.Freya.Security.models.security_header_models import (
    MitigationStatus,
    SecurityHeader,
    SecurityHeaderReport,
    SecurityHeaderStatus,
)
from Asgard.Freya.Security.services._mitigation_framing import (
    DEFENSE_IN_DEPTH_SCORE_LABEL,
    EXECUTIVE_DISCLAIMER,
    MANUAL_VERIFICATION,
    SCOPE_MATRIX,
    THREAT_CONTEXT,
    apply_mitigation_framing,
    classify_mitigation_status,
)
from Asgard.Freya.Security.services._security_header_analyzers import (
    analyze_csp,
    analyze_hsts,
)
from Asgard.Freya.Security.models.security_header_models import SecurityConfig
from Asgard.Freya.cli._formatters_security_console_links import format_security_text


HEADER_NAMES = [
    "Content-Security-Policy", "Strict-Transport-Security",
    "X-Frame-Options", "X-Content-Type-Options", "X-XSS-Protection",
    "Referrer-Policy", "Permissions-Policy",
    "Cross-Origin-Opener-Policy", "Cross-Origin-Embedder-Policy",
    "Cross-Origin-Resource-Policy",
]


class TestVocabulary:
    def test_no_secure_value_in_mitigation_status(self):
        assert "secure" not in [s.value for s in MitigationStatus]

    def test_missing_header_message_uses_missing_mitigation(self):
        header = analyze_csp(httpx.Headers({}), SecurityConfig())
        assert any("Missing Mitigation" in issue for issue in header.issues)

    def test_misconfigured_csp_message(self):
        header = analyze_csp(
            httpx.Headers({"Content-Security-Policy": "script-src 'unsafe-inline'"}),
            SecurityConfig())
        assert any("Misconfigured Mitigation" in i for i in header.issues)

    def test_no_vulnerable_or_secure_wording_in_analyzers(self):
        import inspect
        import Asgard.Freya.Security.services._security_header_analyzers as mod
        import Asgard.Freya.Security.services._csp_analyzer_helpers as helpers
        for module in (mod, helpers):
            source = inspect.getsource(module)
            assert "vulnerable" not in source.lower()


class TestThreatContextCoverage:
    @pytest.mark.parametrize("name", HEADER_NAMES)
    def test_every_header_has_threat_context(self, name):
        assert name in THREAT_CONTEXT
        assert "if" in THREAT_CONTEXT[name].lower()  # assume-breach conditional

    def test_sri_and_mixed_content_covered(self):
        assert "Subresource Integrity" in THREAT_CONTEXT
        assert "Mixed Content" in THREAT_CONTEXT


class TestClassification:
    def _header(self, status, is_secure=True, name="X-Frame-Options"):
        return SecurityHeader(name=name, status=status, is_secure=is_secure)

    def test_missing(self):
        assert classify_mitigation_status(
            self._header(SecurityHeaderStatus.MISSING, False)) == MitigationStatus.MISSING

    def test_misconfigured_invalid(self):
        assert classify_mitigation_status(
            self._header(SecurityHeaderStatus.INVALID, False)) == MitigationStatus.MISCONFIGURED

    def test_misconfigured_present_insecure(self):
        assert classify_mitigation_status(
            self._header(SecurityHeaderStatus.PRESENT, False)) == MitigationStatus.MISCONFIGURED

    def test_present(self):
        assert classify_mitigation_status(
            self._header(SecurityHeaderStatus.PRESENT)) == MitigationStatus.PRESENT

    def test_present_needs_verification_for_csp_and_hsts(self):
        for name in ("Content-Security-Policy", "Strict-Transport-Security"):
            header = self._header(SecurityHeaderStatus.PRESENT, name=name)
            assert classify_mitigation_status(header) == \
                MitigationStatus.PRESENT_NEEDS_VERIFICATION

    def test_none_passthrough(self):
        assert classify_mitigation_status(None) is None


class TestFramingApplication:
    def test_hsts_pass_gets_manual_verification(self):
        header = analyze_hsts(
            httpx.Headers({"Strict-Transport-Security":
                           "max-age=63072000; includeSubDomains"}),
            SecurityConfig())
        apply_mitigation_framing(header)
        assert header.mitigation_status == MitigationStatus.PRESENT_NEEDS_VERIFICATION
        assert "plain-HTTP" in header.manual_verification
        assert header.observable_signal is not None
        assert header.unverifiable_posture is not None

    def test_missing_gets_threat_context(self):
        header = analyze_csp(httpx.Headers({}), SecurityConfig())
        apply_mitigation_framing(header)
        assert header.mitigation_status == MitigationStatus.MISSING
        assert "XSS" in header.threat_context


class TestReportSurfaces:
    def test_scope_matrix_has_four_rows(self):
        controls = {row["control"] for row in SCOPE_MATRIX}
        assert controls == {"Content-Security-Policy", "HSTS",
                            "Subresource Integrity", "Framing protection"}
        for row in SCOPE_MATRIX:
            assert row["tool_validates"] and row["requires_manual"]

    def test_report_defaults_api_compatible(self):
        report = SecurityHeaderReport(url="http://x", security_score=42.0)
        assert report.security_score == 42.0  # field name preserved
        assert report.score_label == DEFENSE_IN_DEPTH_SCORE_LABEL

    def test_formatter_includes_disclaimer_scope_matrix_and_label(self):
        report = SecurityHeaderReport(
            url="http://x",
            disclaimer=EXECUTIVE_DISCLAIMER,
            scope_matrix=list(SCOPE_MATRIX),
        )
        output = format_security_text(report)
        assert "SCOPE OF THIS ASSESSMENT" in output
        assert "Frontend Defense-in-Depth Score" in output
        assert "SCOPE MATRIX" in output
        assert "Resilience Grade" in output
        assert "Secure:" not in output

    def test_manual_verification_texts_are_yes_but(self):
        for text in MANUAL_VERIFICATION.values():
            assert "Manual Verification Required" in text
