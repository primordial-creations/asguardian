"""
Unit tests for UseAnalyzer (USE method for cloud NICs / DNS quotas, Plan 05 s C).
"""

from Asgard.Verdandi.Network import UseAnalyzer
from Asgard.Verdandi.Network.models.network_models import (
    NetworkOutcome,
    UseCounterSnapshot,
)


class TestUseAnalyzer:
    """Tests for UseAnalyzer."""

    def setup_method(self):
        self.analyzer = UseAnalyzer()

    def test_none_snapshot_insufficient_data(self):
        result = self.analyzer.analyze(None)

        assert result.outcome == NetworkOutcome.INSUFFICIENT_DATA

    def test_linklocal_exceeded_is_critical_even_at_low_utilization(self):
        """L0 USE: linklocal_allowance_exceeded=3 -> CRITICAL + DNS-cache
        remediation even with 5% utilization (errors trump utilization)."""
        snapshot = UseCounterSnapshot(
            linklocal_allowance_exceeded=3,
            dns_qps=51.2,  # 51.2 / 1024 = 5%
        )

        result = self.analyzer.analyze(snapshot)

        assert result.dns_resolver.severity == "critical"
        assert result.overall_severity == "critical"
        assert result.dns_resolver.utilization_percent == 5.0
        assert any("node-local dns cache" in r.lower() for r in result.recommendations)

    def test_no_errors_no_saturation_is_ok(self):
        snapshot = UseCounterSnapshot(
            sent_bytes_ps=1000,
            recv_bytes_ps=1000,
            instance_bw_limit_mbps=1000,
        )

        result = self.analyzer.analyze(snapshot)

        assert result.overall_severity == "ok"
        assert result.nic.errors == []

    def test_pps_allowance_exceeded_is_critical(self):
        snapshot = UseCounterSnapshot(pps_allowance_exceeded=10)

        result = self.analyzer.analyze(snapshot)

        assert result.nic.severity == "critical"
        assert "pps_allowance_exceeded" in result.nic.errors

    def test_listen_overflow_is_saturation_not_error(self):
        snapshot = UseCounterSnapshot(listen_overflows=5)

        result = self.analyzer.analyze(snapshot)

        assert result.nic.saturated is True
        assert result.nic.errors == []
        assert result.nic.severity == "warning"

    def test_retransmits_correlated_with_utilization_flags_saturation(self):
        snapshot = UseCounterSnapshot(tcp_retransmits=50)
        retransmits = [1, 2, 3, 4, 5]
        utilization = [10, 20, 30, 40, 50]

        result = self.analyzer.analyze(
            snapshot, retransmit_series=retransmits, utilization_series=utilization
        )

        assert result.nic.saturated is True
        assert any("saturation" in n.lower() for n in result.nic.saturation_notes)

    def test_retransmits_uncorrelated_suggests_path_loss(self):
        snapshot = UseCounterSnapshot(tcp_retransmits=50)
        retransmits = [5, 1, 4, 2, 5]
        utilization = [10, 50, 15, 45, 12]

        result = self.analyzer.analyze(
            snapshot, retransmit_series=retransmits, utilization_series=utilization
        )

        assert any("path" in n.lower() for n in result.nic.saturation_notes)

    def test_utilization_percent_from_bandwidth_limit(self):
        snapshot = UseCounterSnapshot(
            sent_bytes_ps=62_500_000,  # 500 Mbps
            recv_bytes_ps=0,
            instance_bw_limit_mbps=1000,
        )

        result = self.analyzer.analyze(snapshot)

        assert result.nic.utilization_percent == 50.0
