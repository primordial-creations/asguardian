"""
Unit tests for PhaseAnalyzer (TTFB phase decomposition, Plan 05 s A).
"""

from Asgard.Verdandi.Network import PhaseAnalyzer
from Asgard.Verdandi.Network.models.network_models import (
    HANDSHAKE_OVERHEAD,
    NetworkOutcome,
)


class TestPhaseAnalyzer:
    """Tests for PhaseAnalyzer."""

    def setup_method(self):
        self.analyzer = PhaseAnalyzer()

    def test_empty_samples_insufficient_data(self):
        result = self.analyzer.analyze([])

        assert result.outcome == NetworkOutcome.INSUFFICIENT_DATA
        assert result.sample_count == 0

    def test_tls_1_2_handshake_overhead_flagged(self):
        """L0 phases: TLS1.2 profile, rtt~50ms -> tls_ms~100ms expected;
        300ms observed -> HANDSHAKE_OVERHEAD (per plan testing notes)."""
        samples = [
            {
                "dns_ms": 5,
                "tcp_ms": 50,
                "tls_ms": 300,
                "request_ms": 2,
                "response_ms": 40,
                "tls_version": "1.2",
            }
        ]

        result = self.analyzer.analyze(samples)

        assert result.outcome == NetworkOutcome.OK
        assert HANDSHAKE_OVERHEAD in result.protocol_flags
        assert any("TLS" in rec for rec in result.recommendations)

    def test_tls_1_3_equivalent_passes(self):
        """TLS1.3 equivalent (1-RTT budget) with a normal handshake passes."""
        samples = [
            {
                "dns_ms": 5,
                "tcp_ms": 50,
                "tls_ms": 60,
                "request_ms": 2,
                "response_ms": 40,
                "tls_version": "1.3",
            }
        ]

        result = self.analyzer.analyze(samples)

        assert HANDSHAKE_OVERHEAD not in result.protocol_flags

    def test_resumed_session_never_flagged(self):
        samples = [
            {
                "dns_ms": 5,
                "tcp_ms": 50,
                "tls_ms": 300,
                "request_ms": 2,
                "response_ms": 40,
                "tls_version": "1.2",
                "resumed": True,
            }
        ]

        result = self.analyzer.analyze(samples)

        assert HANDSHAKE_OVERHEAD not in result.protocol_flags

    def test_dominant_phase_attribution(self):
        samples = [
            {"dns_ms": 1, "tcp_ms": 1, "tls_ms": 1, "request_ms": 1, "response_ms": 100},
        ]

        result = self.analyzer.analyze(samples)

        assert result.ttfb_dominant_phase == "response"
        assert result.response.share_of_ttfb_percent > 90

    def test_phase_percentiles_computed(self):
        samples = [
            {"dns_ms": d, "tcp_ms": 10, "tls_ms": 10, "request_ms": 1, "response_ms": 20}
            for d in (5, 10, 15, 20, 25)
        ]

        result = self.analyzer.analyze(samples)

        assert result.sample_count == 5
        assert result.dns.p50_ms == 15
        assert result.dns.mean_ms == 15
