"""
Unit tests for DnsCalculator.analyze_quota (Plan 05 s E).
"""

from Asgard.Verdandi.Network import DnsCalculator
from Asgard.Verdandi.Network.models.network_models import NetworkOutcome


class TestDnsQuota:
    """Tests for DNS quota/environment-band analysis."""

    def setup_method(self):
        self.calculator = DnsCalculator()

    def test_none_queries_ps_insufficient_data(self):
        result = self.calculator.analyze_quota(None)

        assert result.outcome == NetworkOutcome.INSUFFICIENT_DATA

    def test_under_quota_utilization(self):
        result = self.calculator.analyze_quota(queries_ps=51.2)

        assert result.linklocal_quota_utilization_percent == 5.0
        assert result.quota_exceeded is False
        assert result.status == "ok"

    def test_over_linklocal_quota_is_critical(self):
        result = self.calculator.analyze_quota(queries_ps=2000)

        assert result.quota_exceeded is True
        assert result.status == "critical"
        assert any("node-local" in r.lower() for r in result.recommendations)

    def test_in_vpc_environment_band(self):
        result = self.calculator.analyze_quota(queries_ps=100, environment="in_vpc")

        assert result.expected_band_high_ms == 2.0

    def test_public_environment_band(self):
        result = self.calculator.analyze_quota(queries_ps=100, environment="public")

        assert result.expected_band_high_ms == 100.0

    def test_error_rates_computed(self):
        result = self.calculator.analyze_quota(
            queries_ps=100,
            nxdomain_count=5,
            servfail_count=15,
            timeout_count=2,
            total_queries=1000,
        )

        assert result.nxdomain_rate_percent == 0.5
        assert result.servfail_rate_percent == 1.5
        assert result.timeout_rate_percent == 0.2
        assert result.status == "degraded"
