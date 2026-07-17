"""
Unit tests for LatencyCalculator.analyze_against_profile (Plan 05 s B).
"""

from Asgard.Verdandi.Network import LatencyCalculator
from Asgard.Verdandi.Network.models.network_models import (
    TopologyProfile,
    TopologyRating,
)


class TestTopologyProfiles:
    """Tests for topology-baseline-relative latency rating."""

    def setup_method(self):
        self.calculator = LatencyCalculator()

    def test_empty_samples_insufficient_data(self):
        result = self.calculator.analyze_against_profile([], TopologyProfile.INTER_AZ)

        assert result.rating == TopologyRating.INSUFFICIENT_DATA

    def test_inter_az_1_8ms_is_good(self):
        """L0 profiles: 1.8 ms inter-AZ -> GOOD."""
        samples = [1.7, 1.8, 1.9]

        result = self.calculator.analyze_against_profile(samples, TopologyProfile.INTER_AZ)

        assert result.rating == TopologyRating.GOOD

    def test_inter_az_4ms_is_degraded_with_sync_replication_warning(self):
        """L0 profiles: 4 ms -> DEGRADED with sync-replication warning."""
        samples = [3.9, 4.0, 4.1]

        result = self.calculator.analyze_against_profile(samples, TopologyProfile.INTER_AZ)

        assert result.rating == TopologyRating.DEGRADED
        assert any("sync" in w.lower() or "replication" in w.lower() for w in result.warnings)

    def test_same_series_under_internet_edge_is_good(self):
        """L0 profiles: same series under INTERNET_EDGE -> GOOD."""
        samples = [3.9, 4.0, 4.1]

        result = self.calculator.analyze_against_profile(
            samples, TopologyProfile.INTERNET_EDGE
        )

        assert result.rating == TopologyRating.GOOD

    def test_cross_region_requires_declared_baseline(self):
        result = self.calculator.analyze_against_profile(
            [200, 210, 205], TopologyProfile.CROSS_REGION
        )

        assert result.rating == TopologyRating.INSUFFICIENT_DATA

    def test_cross_region_within_declared_baseline_is_good(self):
        result = self.calculator.analyze_against_profile(
            [200, 210, 205],
            TopologyProfile.CROSS_REGION,
            cross_region_declared_ms=220,
        )

        assert result.rating == TopologyRating.GOOD

    def test_intra_az_poor_above_1ms(self):
        result = self.calculator.analyze_against_profile(
            [1.2, 1.3, 1.4], TopologyProfile.INTRA_AZ
        )

        assert result.rating == TopologyRating.POOR

    def test_packet_loss_downgrades_rating(self):
        result = self.calculator.analyze_against_profile(
            [1.7, 1.8, 1.9],
            TopologyProfile.INTER_AZ,
            packet_loss_percent=1.0,
        )

        assert result.rating != TopologyRating.GOOD
        assert any("packet loss" in w.lower() for w in result.warnings)

    def test_legacy_default_matches_original_bands(self):
        result = self.calculator.analyze_against_profile(
            [10, 15, 20], TopologyProfile.LEGACY_DEFAULT
        )

        assert result.rating == TopologyRating.GOOD
