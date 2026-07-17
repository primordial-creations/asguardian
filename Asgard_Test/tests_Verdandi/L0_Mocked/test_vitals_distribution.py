"""
L0 tests for distribution-based (p75) Core Web Vitals assessment:
tri-band p75 rating, good-fractions, INP-first semantics, masking warning,
and the minimum-sample guard.
"""

import pytest

from Asgard.Verdandi.Web.models.web_models import VitalsRating
from Asgard.Verdandi.Web.services.vitals_calculator import CoreWebVitalsCalculator


@pytest.fixture
def calc():
    return CoreWebVitalsCalculator()


class TestP75BandBoundaries:
    def test_exactly_2500_is_good(self, calc):
        result = calc.assess_distribution([2500.0] * 40, "lcp")
        assert result.p75 == 2500.0
        assert result.rating == VitalsRating.GOOD

    def test_just_over_2500_is_needs_improvement(self, calc):
        result = calc.assess_distribution([2500.01] * 40, "lcp")
        assert result.rating == VitalsRating.NEEDS_IMPROVEMENT

    def test_p75_is_evaluated_not_mean(self, calc):
        """25% catastrophic samples do not break a good p75."""
        samples = [1000.0] * 76 + [10_000.0] * 24
        result = calc.assess_distribution(samples, "lcp")
        assert result.rating == VitalsRating.GOOD
        assert result.poor_fraction == pytest.approx(0.24)

    def test_unknown_metric_raises(self, calc):
        with pytest.raises(ValueError):
            calc.assess_distribution([1.0] * 40, "nope")


class TestMinimumSampleGuard:
    def test_29_samples_is_insufficient_data(self, calc):
        result = calc.assess_distribution([1000.0] * 29, "lcp")
        assert result.rating == VitalsRating.INSUFFICIENT_DATA
        assert result.insufficient_data
        assert result.p75 is None
        assert result.good_fraction is None

    def test_30_samples_is_rated(self, calc):
        result = calc.assess_distribution([1000.0] * 30, "lcp")
        assert result.rating == VitalsRating.GOOD
        assert not result.insufficient_data


class TestGoodFractions:
    def test_fractions_sum_to_one(self, calc):
        samples = [1000.0] * 50 + [3000.0] * 30 + [5000.0] * 20
        result = calc.assess_distribution(samples, "lcp")
        assert result.good_fraction == pytest.approx(0.5)
        assert result.ni_fraction == pytest.approx(0.3)
        assert result.poor_fraction == pytest.approx(0.2)

    def test_merge_invariant(self, calc):
        """The invariant justifying threshold-fractions: the fraction over
        concatenated samples equals the traffic-weighted mean of per-window
        fractions."""
        window_a = [1000.0] * 60 + [5000.0] * 40  # good_fraction 0.6, n=100
        window_b = [1000.0] * 30 + [5000.0] * 270  # good_fraction 0.1, n=300
        frac_a = calc.assess_distribution(window_a, "lcp").good_fraction
        frac_b = calc.assess_distribution(window_b, "lcp").good_fraction
        pooled = calc.assess_distribution(window_a + window_b, "lcp").good_fraction
        weighted = (frac_a * 100 + frac_b * 300) / 400
        assert pooled == pytest.approx(weighted)


class TestPageAssessment:
    def test_all_good_passes_cwv(self, calc):
        assessment = calc.assess_page(
            {"lcp": [1500.0] * 50, "inp": [100.0] * 50, "cls": [0.05] * 50}
        )
        assert assessment.core_passing is True
        assert not assessment.masking_warning

    def test_inp_first_fid_is_legacy_only(self, calc):
        """FID GOOD cannot rescue a POOR INP: core = {LCP, INP, CLS}."""
        assessment = calc.assess_page(
            {
                "lcp": [1500.0] * 50,
                "inp": [800.0] * 50,
                "cls": [0.05] * 50,
                "fid": [50.0] * 50,
            }
        )
        assert assessment.core_passing is False
        assert assessment.legacy_fid_rating == VitalsRating.GOOD
        assert "fid" in assessment.diagnostics
        assert any("deprecated" in r.lower() for r in assessment.recommendations)

    def test_masking_warning_fires_on_bimodal_experience(self, calc):
        """The plan's example: GOOD LCP (1000ms x100) + POOR INP (800ms x100)."""
        assessment = calc.assess_page(
            {"lcp": [1000.0] * 100, "inp": [800.0] * 100, "cls": [0.05] * 100}
        )
        assert assessment.masking_warning
        assert assessment.core_passing is False

    def test_missing_core_metric_is_undecided_not_passing(self, calc):
        assessment = calc.assess_page({"lcp": [1500.0] * 50, "cls": [0.05] * 50})
        assert assessment.core_passing is None

    def test_missing_core_metric_with_definite_failure_is_false(self, calc):
        assessment = calc.assess_page({"lcp": [9000.0] * 50})
        assert assessment.core_passing is False

    def test_insufficient_core_data_is_undecided(self, calc):
        assessment = calc.assess_page(
            {"lcp": [1500.0] * 10, "inp": [100.0] * 10, "cls": [0.05] * 10}
        )
        assert assessment.core_passing is None
        assert assessment.lcp.insufficient_data

    def test_diagnostics_do_not_affect_core_passing(self, calc):
        assessment = calc.assess_page(
            {
                "lcp": [1500.0] * 50,
                "inp": [100.0] * 50,
                "cls": [0.05] * 50,
                "ttfb": [5000.0] * 50,  # POOR, but diagnostic only
            }
        )
        assert assessment.core_passing is True
        assert assessment.diagnostics["ttfb"].rating == VitalsRating.POOR


class TestTailVsSystemicRecommendations:
    def test_tail_problem_recommendation(self, calc):
        samples = [1000.0] * 85 + [10_000.0] * 15
        result = calc.assess_distribution(samples, "lcp")
        assert result.rating == VitalsRating.GOOD
        assert any("tail" in r for r in result.recommendations)

    def test_systemic_problem_recommendation(self, calc):
        result = calc.assess_distribution([3000.0] * 50, "lcp")
        assert any("systemic" in r for r in result.recommendations)


class TestLegacySingleSampleAPIUnchanged:
    def test_calculate_outputs_unchanged(self, calc):
        result = calc.calculate(lcp_ms=2100, fid_ms=50, cls=0.05)
        assert result.lcp_rating == VitalsRating.GOOD
        assert result.fid_rating == VitalsRating.GOOD
        assert result.cls_rating == VitalsRating.GOOD
        assert result.overall_rating == VitalsRating.GOOD
        assert result.score == 100.0

    def test_calculate_score_still_additive(self, calc):
        result = calc.calculate(lcp_ms=5000, inp_ms=100)
        assert result.score == pytest.approx((20 + 100) / 2)


class TestNavigationBatch:
    def test_analyze_batch_phase_percentiles(self):
        from Asgard.Verdandi.Web.models.web_models import NavigationTimingInput
        from Asgard.Verdandi.Web.services.navigation_timing import (
            NavigationTimingCalculator,
        )

        def make(dns_ms):
            return NavigationTimingInput(
                dns_start_ms=0,
                dns_end_ms=dns_ms,
                connect_start_ms=dns_ms,
                connect_end_ms=dns_ms + 20,
                request_start_ms=dns_ms + 20,
                response_start_ms=dns_ms + 120,
                response_end_ms=dns_ms + 150,
                dom_interactive_ms=dns_ms + 200,
                dom_complete_ms=dns_ms + 400,
                load_event_start_ms=dns_ms + 410,
                load_event_end_ms=dns_ms + 420,
            )

        calc = NavigationTimingCalculator()
        batch = calc.analyze_batch([make(float(d)) for d in range(10, 110)])
        assert set(batch) >= {"dns_lookup", "ttfb", "page_load"}
        assert batch["dns_lookup"]["p50"] == pytest.approx(59.5)
        assert batch["ttfb"]["p95"] == pytest.approx(100.0)
        assert batch["dns_lookup"]["count"] == 100

    def test_analyze_batch_empty_returns_empty(self):
        from Asgard.Verdandi.Web.services.navigation_timing import (
            NavigationTimingCalculator,
        )

        assert NavigationTimingCalculator().analyze_batch([]) == {}
