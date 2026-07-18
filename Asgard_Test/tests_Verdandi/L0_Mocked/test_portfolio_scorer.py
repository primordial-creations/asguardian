"""
Unit tests for PortfolioScorer: dual-axis CXI/SRI and the sandbagging
detector (Plan 02 section 2.8). Verifies the centrality hook degrades
gracefully to uniform weighting when no APM export is supplied.
"""

import pytest

from Asgard.Verdandi.SLO import PortfolioScorer


class TestCXI:
    def setup_method(self):
        self.scorer = PortfolioScorer()

    def test_uniform_weighting_when_no_business_weights(self):
        result = self.scorer.compute_cxi({"checkout": 0.99, "search": 0.95})
        assert result.cxi == pytest.approx(97.0, abs=0.01)

    def test_business_weighted_average(self):
        result = self.scorer.compute_cxi(
            {"checkout": 0.99, "search": 0.90},
            business_weights={"checkout": 9.0, "search": 1.0},
        )
        # (0.99*9 + 0.90*1) / 10 = 0.981
        assert result.cxi == pytest.approx(98.1, abs=0.01)

    def test_empty_journeys_returns_none(self):
        result = self.scorer.compute_cxi({})
        assert result.cxi is None


class TestSRI:
    def setup_method(self):
        self.scorer = PortfolioScorer()

    def test_default_centrality_is_uniform(self):
        result = self.scorer.compute_sri({"a": 1.0, "b": 20.0})
        assert result.used_default_centrality is True
        # a: 100 (<=1.0), b: 100/20=5 -> avg = 52.5
        assert result.sri == pytest.approx(52.5, abs=0.01)

    def test_pluggable_centrality_reweights_result(self):
        """Weighting the highly-central, badly-burning service more should
        pull the score down, proving the hook is wired end to end."""
        uniform = self.scorer.compute_sri({"a": 1.0, "b": 20.0})
        weighted = self.scorer.compute_sri(
            {"a": 1.0, "b": 20.0}, centrality={"a": 1.0, "b": 9.0}
        )
        assert weighted.used_default_centrality is False
        assert weighted.sri < uniform.sri

    def test_service_at_or_under_sustainable_rate_scores_full(self):
        result = self.scorer.compute_sri({"a": 0.5})
        assert result.sri_service_scores["a"] == pytest.approx(100.0)

    def test_empty_services_returns_none(self):
        result = self.scorer.compute_sri({})
        assert result.sri is None


class TestScorePortfolio:
    def test_combines_both_axes(self):
        scorer = PortfolioScorer()
        result = scorer.score_portfolio(
            journey_success_rates={"checkout": 0.99},
            service_burn_rates={"a": 1.0, "b": 20.0},
        )
        assert result.cxi == pytest.approx(99.0, abs=0.01)
        assert result.sri == pytest.approx(52.5, abs=0.01)


class TestUncalibratedSLODetection:
    def test_flags_sandbagged_slo(self):
        scorer = PortfolioScorer()
        flags = scorer.detect_uncalibrated_slos(
            declared_targets={"svcA": 99.0},
            achieved_pct_90d={"svcA": 99.999},
        )
        assert len(flags) == 1
        assert flags[0].service_name == "svcA"

    def test_does_not_flag_well_calibrated_slo(self):
        scorer = PortfolioScorer()
        flags = scorer.detect_uncalibrated_slos(
            declared_targets={"svcA": 99.9},
            achieved_pct_90d={"svcA": 99.92},
        )
        assert flags == []

    def test_missing_achieved_data_skipped(self):
        scorer = PortfolioScorer()
        flags = scorer.detect_uncalibrated_slos(
            declared_targets={"svcA": 99.9}, achieved_pct_90d={}
        )
        assert flags == []
