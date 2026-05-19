"""
Freya L8 Performance Benchmarks

Benchmarks for Freya security analysis services that operate on
in-memory string inputs (no browser or network I/O required).
"""

import sys
import pytest

# Import directly from submodules to avoid Asgard.Freya.__init__ which pulls in
# playwright via the Accessibility subpackage (not installed in this environment).
from Asgard.Freya.Security.services.csp_analyzer import CSPAnalyzer  # noqa: E402
from Asgard.Freya.Security.models.security_header_models import SecurityConfig  # noqa: E402


STRICT_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'nonce-abc123'; "
    "style-src 'self' 'nonce-xyz789'; "
    "img-src 'self' data: https://cdn.example.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self' https://api.example.com; "
    "frame-src 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "upgrade-insecure-requests; "
    "report-uri /csp-report"
)

PERMISSIVE_CSP = (
    "default-src *; "
    "script-src * 'unsafe-inline' 'unsafe-eval'; "
    "style-src * 'unsafe-inline'; "
    "img-src *; "
    "font-src *"
)

MEDIUM_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.example.com; "
    "style-src 'self' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'"
)


class TestFreyaPerformance:
    """L8 performance benchmarks for Freya security analysis services."""

    def test_csp_analyze_strict_policy(self, benchmark):
        """Benchmark parsing and analyzing a strict CSP header string."""
        analyzer = CSPAnalyzer()

        result = benchmark(analyzer.analyze, STRICT_CSP)

        assert result is not None
        assert result.is_present
        assert result.security_score >= 0

    def test_csp_analyze_permissive_policy(self, benchmark):
        """Benchmark CSP analysis that detects multiple unsafe directives."""
        analyzer = CSPAnalyzer()

        result = benchmark(analyzer.analyze, PERMISSIVE_CSP)

        assert result is not None
        assert result.is_present
        # Permissive CSP with unsafe-inline/eval should score lower
        assert result.security_score < 80

    def test_csp_analyze_medium_policy(self, benchmark):
        """Benchmark CSP analysis of a typical self-hosted application policy."""
        analyzer = CSPAnalyzer()

        result = benchmark(analyzer.analyze, MEDIUM_CSP)

        assert result is not None
        assert result.is_present
        assert len(result.directives) > 0
