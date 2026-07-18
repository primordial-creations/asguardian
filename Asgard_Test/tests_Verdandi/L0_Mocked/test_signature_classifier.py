"""
Unit tests for SignatureClassifier (BGP/DNS-hijack anomaly signatures +
clock-skew guard, Plan 05 s D).
"""

from Asgard.Verdandi.Network import SignatureClassifier
from Asgard.Verdandi.Network.models.network_models import NetworkSignatureType
from Asgard.Verdandi.Network.services.signature_classifier import detect_clock_skew


class TestSignatureClassifier:
    """Tests for SignatureClassifier."""

    def setup_method(self):
        self.classifier = SignatureClassifier()

    def test_step_series_sustained_is_route_change(self):
        """L0 signatures: step series 20->45 ms sustained -> ROUTE_CHANGE."""
        series = [20.0] * 20 + [45.0] * 20

        result = self.classifier.classify(rtt_series=series, sample_interval_seconds=60)

        assert result.signature == NetworkSignatureType.ROUTE_CHANGE
        assert result.change_index is not None

    def test_negative_one_way_latency_is_clock_skew_only(self):
        """L0 signatures: negative one-way latency -> CLOCK_SKEW flag only."""
        series = [1.0, 2.0, 3.0, 4.0, 5.0]

        result = self.classifier.classify(
            rtt_series=series, one_way_latencies_ms=[1.0, -2.0, 3.0]
        )

        assert result.signature == NetworkSignatureType.CLOCK_SKEW
        assert result.is_data_quality_issue is True

    def test_detect_clock_skew_standalone_positive_only(self):
        result = detect_clock_skew([1.0, 2.0, 3.0])

        assert result.signature == NetworkSignatureType.NONE

    def test_detect_clock_skew_standalone_negative(self):
        result = detect_clock_skew([1.0, -0.5, 3.0])

        assert result.signature == NetworkSignatureType.CLOCK_SKEW
        assert result.is_data_quality_issue is True

    def test_stable_series_is_none(self):
        series = [20.0 + (i % 3) for i in range(30)]

        result = self.classifier.classify(rtt_series=series, sample_interval_seconds=60)

        assert result.signature == NetworkSignatureType.NONE

    def test_route_change_not_sustained_is_not_flagged(self):
        """A brief step that doesn't hold for >= 15 minutes is not a route change."""
        series = [20.0] * 28 + [45.0] * 2  # only 2 min sustained at 60s interval

        result = self.classifier.classify(rtt_series=series, sample_interval_seconds=60)

        assert result.signature != NetworkSignatureType.ROUTE_CHANGE

    def test_dns_hijack_asn_change_with_tls_failure_spike(self):
        asn_series = ["AS1"] * 5 + ["AS999"] * 5
        tls_failures = [0, 0, 0, 0, 0, 5, 4, 3, 2, 1]

        result = self.classifier.classify_dns_hijack(asn_series, tls_failures)

        assert result.signature == NetworkSignatureType.DNS_HIJACK_SUSPECT

    def test_dns_hijack_asn_change_without_tls_failures_is_none(self):
        asn_series = ["AS1"] * 5 + ["AS999"] * 5
        tls_failures = [0] * 10

        result = self.classifier.classify_dns_hijack(asn_series, tls_failures)

        assert result.signature == NetworkSignatureType.NONE

    def test_insufficient_points_for_route_change(self):
        result = self.classifier.classify_route_change([20.0, 21.0, 22.0])

        assert result.signature == NetworkSignatureType.INSUFFICIENT_DATA

    def test_congestion_variance_growth_no_step(self):
        import random

        random.seed(42)
        first_half = [20.0 + random.uniform(-0.5, 0.5) for _ in range(20)]
        second_half = [20.0 + random.uniform(-5.0, 5.0) for _ in range(20)]

        result = self.classifier.classify_congestion(first_half + second_half)

        assert result.signature == NetworkSignatureType.CONGESTION
