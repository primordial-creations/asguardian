"""
L6 Industry Benchmark Tests — Freya Accessibility & Security Header Coverage.

Validates that Freya's CSPAnalyzer and MetaTagAnalyzer meet industry-standard
quality thresholds:

  CSP / Security headers
  - Known-bad headers (no default-src, wildcard *) are flagged
  - Known-safe CSP passes with a high security score
  - Throughput: analyze a 5,000-line equivalent HTML blob in < 200 ms

  SEO
  - Missing title / description produces lower score / issues
  - Complete meta tags produce a high score with no critical issues
"""

import time

import pytest

from Asgard.Freya.Security.services.csp_analyzer import CSPAnalyzer
from Asgard.Freya.Security.models.security_header_models import SecurityConfig


# ---------------------------------------------------------------------------
# CSP / Security header benchmarks
# ---------------------------------------------------------------------------

class TestFreyaCSPKnownBad:
    """Known-bad CSP values must be flagged with security issues."""

    def setup_method(self) -> None:
        self.analyzer = CSPAnalyzer()

    def test_empty_csp_reports_issues(self) -> None:
        """An empty CSP string should produce a low security score."""
        report = self.analyzer.analyze("")
        # Empty CSP means no directives; analyzer should give a low security score
        # CSPReport uses critical_issues / warnings / security_score (no top-level issues)
        assert report.security_score < 50 or len(report.critical_issues) > 0 or len(report.warnings) > 0, (
            f"Expected low score or issues for empty CSP, got score={report.security_score}"
        )

    def test_wildcard_default_src_is_flagged(self) -> None:
        """default-src: * allows any source and is a known-bad configuration."""
        report = self.analyzer.analyze("default-src *")
        directive = next((d for d in report.directives if d.name == "default-src"), None)
        assert directive is not None
        assert directive.allows_any, "Expected allows_any=True for wildcard default-src"
        # A wildcard default-src must produce critical issues or a low score
        has_feedback = (
            len(report.critical_issues) > 0
            or len(report.warnings) > 0
            or report.security_score < 70
        )
        assert has_feedback, (
            f"Expected issues or low score for wildcard default-src, "
            f"score={report.security_score}"
        )

    def test_unsafe_inline_script_src_is_flagged(self) -> None:
        """script-src 'unsafe-inline' enables XSS and must be flagged."""
        report = self.analyzer.analyze(
            "default-src 'self'; script-src 'self' 'unsafe-inline'"
        )
        script_directive = next(
            (d for d in report.directives if d.name == "script-src"), None
        )
        assert script_directive is not None
        assert script_directive.has_unsafe_inline, (
            "Expected has_unsafe_inline=True for script-src 'unsafe-inline'"
        )
        # 'unsafe-inline' must generate critical issues or warnings
        has_feedback = len(report.critical_issues) > 0 or len(report.warnings) > 0
        assert has_feedback, (
            f"Expected critical_issues or warnings for 'unsafe-inline', "
            f"critical={report.critical_issues}, warnings={report.warnings}"
        )

    def test_unsafe_eval_is_flagged(self) -> None:
        """script-src 'unsafe-eval' is exploitable and must be flagged."""
        report = self.analyzer.analyze(
            "default-src 'self'; script-src 'self' 'unsafe-eval'"
        )
        script_directive = next(
            (d for d in report.directives if d.name == "script-src"), None
        )
        assert script_directive is not None
        assert script_directive.has_unsafe_eval, (
            "Expected has_unsafe_eval=True for script-src 'unsafe-eval'"
        )


class TestFreyaCSPKnownGood:
    """Known-safe CSP values must pass with a high security score."""

    def setup_method(self) -> None:
        self.analyzer = CSPAnalyzer()

    def test_strict_sample_policy_scores_high(self) -> None:
        """The built-in strict sample policy must achieve a high security score."""
        strict_csp = self.analyzer.get_sample_policy(strict=True)
        report = self.analyzer.analyze(strict_csp)
        assert report.security_score >= 70, (
            f"Strict sample CSP scored {report.security_score:.1f} — expected >= 70"
        )

    def test_nonce_based_csp_detected(self) -> None:
        """A nonce-based CSP is a modern best practice and must be detected."""
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'nonce-abc123xyz'; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        report = self.analyzer.analyze(csp)
        assert report.uses_nonces, "Expected uses_nonces=True for nonce-based CSP"

    def test_restrictive_csp_no_wildcards(self) -> None:
        """A well-formed restrictive CSP must not have wildcard directives."""
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "frame-ancestors 'none'"
        )
        report = self.analyzer.analyze(csp)
        for directive in report.directives:
            assert not directive.allows_any, (
                f"Directive '{directive.name}' unexpectedly allows wildcard"
            )


# ---------------------------------------------------------------------------
# SEO — meta tag quality
# ---------------------------------------------------------------------------

class TestFreyaSEOMetaTags:
    """
    SEO meta tag scoring uses the internal _analyze_* helpers on the
    MetaTagAnalyzer.  We exercise them directly since the public analyze()
    method is async and requires a live browser page.

    MetaTag fields:  is_present (bool), is_valid (bool), issues (List[str]),
                     suggestions (List[str]), length (int), value (Optional[str])
    """

    def setup_method(self) -> None:
        from Asgard.Freya.SEO.services.meta_tag_analyzer import MetaTagAnalyzer
        self.analyzer = MetaTagAnalyzer()

    def test_missing_title_is_not_present(self) -> None:
        """A page without a title tag must be marked as not present."""
        tag = self.analyzer._analyze_title(None)
        assert not tag.is_present, "Expected missing title to be flagged as not present"
        assert len(tag.issues) > 0, "Expected issues list to be non-empty for missing title"

    def test_short_title_is_invalid(self) -> None:
        """A title that is too short violates SEO best-practice and must be marked invalid."""
        tag = self.analyzer._analyze_title("Hi")
        assert not tag.is_valid, "Expected short title to be marked as invalid"
        assert len(tag.issues) > 0, "Expected issues for a too-short title"

    def test_good_title_is_present_and_valid(self) -> None:
        """A well-formed title (30-60 chars) must be present and valid."""
        tag = self.analyzer._analyze_title("Asgard Monitoring Platform – Real-Time SLO")
        assert tag.is_present
        assert tag.is_valid, f"Good title was unexpectedly invalid. Issues: {tag.issues}"

    def test_missing_description_is_not_present(self) -> None:
        """A page without a meta description must be flagged."""
        tag = self.analyzer._analyze_description(None)
        assert not tag.is_present, "Expected missing description to be flagged"
        assert len(tag.issues) > 0, "Expected issues for missing meta description"

    def test_good_description_is_valid(self) -> None:
        """A 120-160 char description matching SEO guidelines must pass."""
        desc = (
            "Asgard is a monorepo of intelligent developer tools covering "
            "security scanning, SLO management, API validation, and more."
        )
        tag = self.analyzer._analyze_description(desc)
        assert tag.is_present
        assert tag.is_valid, f"Good description was unexpectedly invalid. Issues: {tag.issues}"


# ---------------------------------------------------------------------------
# Throughput benchmark — industry baseline: analyze 5,000-line HTML in < 200 ms
# ---------------------------------------------------------------------------

class TestFreyaThroughput:
    """
    CSP parsing must complete in < 200 ms even for complex policies.

    The 200 ms threshold matches the budget for inline HTML security checks
    in browser DevTools audits and Lighthouse-equivalent tools.
    The 5,000-line HTML proxy is a long CSP string with many directives that
    exercises the parser comparably.
    """

    def test_complex_csp_parses_in_under_200ms(self) -> None:
        """Parsing a policy with 50 directives must complete in < 200 ms."""
        analyzer = CSPAnalyzer()

        # Build a CSP with 50 directives to stress-test the parser
        directive_names = [
            "default-src", "script-src", "style-src", "img-src", "font-src",
            "connect-src", "media-src", "object-src", "frame-src", "worker-src",
            "manifest-src", "child-src", "base-uri", "form-action",
            "frame-ancestors",
        ]
        sources = ["'self'", "https://cdn.example.com", "https://api.example.com"]
        parts = []
        # Repeat to get ~50 directives (cycle through names with different sources)
        for i, name in enumerate(directive_names * 4):
            parts.append(f"{name} {' '.join(sources)}")
        complex_csp = "; ".join(parts[:50])

        start = time.perf_counter()
        for _ in range(10):  # 10 iterations simulating repeated page analysis
            analyzer.analyze(complex_csp)
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_call_ms = elapsed_ms / 10
        assert per_call_ms < 200, (
            f"CSP analysis took {per_call_ms:.1f} ms per call "
            f"(industry threshold: 200 ms)"
        )

    def test_bulk_csp_analyses_throughput(self) -> None:
        """100 CSP analyses must complete in < 2 seconds total."""
        analyzer = CSPAnalyzer()
        csp = (
            "default-src 'self'; script-src 'self' 'nonce-abc'; "
            "style-src 'self'; img-src 'self' data: https:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
        )

        start = time.perf_counter()
        for _ in range(100):
            analyzer.analyze(csp)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 2000, (
            f"100 CSP analyses took {elapsed_ms:.1f} ms (expected < 2000 ms)"
        )
