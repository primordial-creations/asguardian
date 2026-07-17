"""
Tests for the Bragi remediation model and debt aggregator (Plan 02 A-C).

Covers pessimism-corrected remediation minutes, the DEEPTHINK_05 batching
law (context cost + geometric discount), the rewrite cap, effort intervals,
the standard TDR (30 min/LOC anchor - fixing the ~50x denominator bug), and
the deferred centrality/exposure interface.
"""

from pathlib import Path

import pytest

from Asgard.Bragi.Quality.models.debt_models import (
    DebtItem,
    DebtRecommendation,
    DebtSeverity,
    DebtType,
    EffortInterval,
    RemediationFunction,
)
from Asgard.Bragi.Quality.services._debt_aggregator import (
    CONTEXT_COST_MINUTES,
    DebtAggregator,
)
from Asgard.Bragi.Quality.services._remediation_model import (
    NON_REMEDIATION_FACTORS,
    SEVERITY_MINUTES,
    RemediationModel,
)
from Asgard.Bragi.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer


def _item(debt_type=DebtType.CODE, severity=DebtSeverity.MEDIUM,
          file_path="/proj/a.py", description="issue"):
    return DebtItem(
        debt_type=debt_type, file_path=file_path, line_number=1,
        description=description, severity=severity, effort_hours=1.0,
    )


class TestRemediationModel:
    def test_severity_grid_pessimism_corrected(self):
        assert SEVERITY_MINUTES["tiny"] <= 2.0
        assert SEVERITY_MINUTES["low"] == 10.0
        assert SEVERITY_MINUTES["medium"] == 30.0
        assert SEVERITY_MINUTES["high"] == 60.0
        assert SEVERITY_MINUTES["critical"] == 480.0

    def test_documentation_priced_per_function(self):
        model = RemediationModel()
        item = _item(DebtType.DOCUMENTATION, DebtSeverity.LOW,
                     description="50 undocumented public functions")
        assert model.minutes_for(item) == pytest.approx(100.0)  # 2 min each

    def test_code_debt_has_context_offset(self):
        model = RemediationModel()
        medium = model.minutes_for(_item(severity=DebtSeverity.MEDIUM))
        assert medium == pytest.approx(10.0 + 30.0)  # offset + severity minutes

    def test_sbii_factors(self):
        model = RemediationModel()
        assert model.non_remediation_factor(_item(severity=DebtSeverity.CRITICAL)) == 1000.0
        assert model.non_remediation_factor(_item(severity=DebtSeverity.LOW)) == 10.0
        assert NON_REMEDIATION_FACTORS["medium"] == 15.0

    def test_override_registry(self):
        model = RemediationModel(overrides={
            DebtType.CODE.value: RemediationFunction(
                kind="constant", base_minutes=5.0, batchability=0.1)
        })
        assert model.minutes_for(_item()) == 5.0


class TestBatchingAggregation:
    def test_mechanical_debt_batches_deepthink_worked_example(self):
        """50 missing-docstring items with batchability 0.05 must total about
        context(30) + 2 + tail, i.e. ~32 min - never 50 x 2 + overheads."""
        aggregator = DebtAggregator()
        items = [
            _item(DebtType.DOCUMENTATION, DebtSeverity.LOW, "/p/f.py",
                  description="1 undocumented public functions")
            for _ in range(50)
        ]
        result = aggregator.aggregate(items)
        assert result.total_minutes == pytest.approx(
            CONTEXT_COST_MINUTES + sum(2.0 * 0.05 ** i for i in range(50)), abs=0.1)
        assert result.total_minutes < 35.0

    def test_cognitive_debt_barely_discounts(self):
        aggregator = DebtAggregator()
        items = [_item(severity=DebtSeverity.HIGH) for _ in range(3)]
        result = aggregator.aggregate(items)
        # d=0.8: 70 + 70*0.8 + 70*0.64 = 170.8 (+30 context)
        assert result.total_minutes == pytest.approx(30.0 + 70.0 * (1 + 0.8 + 0.64), rel=1e-3)

    def test_one_context_cost_per_file_not_per_item(self):
        aggregator = DebtAggregator()
        one_file = aggregator.aggregate([_item(), _item()])
        two_files = aggregator.aggregate([
            _item(file_path="/p/a.py"), _item(file_path="/p/b.py")])
        assert two_files.total_minutes - one_file.total_minutes >= CONTEXT_COST_MINUTES - 10.0

    def test_rewrite_cap_small_file_with_huge_debt(self):
        """200-LOC file with ~3000 min of debt gets capped and marked REWRITE."""
        aggregator = DebtAggregator()
        items = [_item(severity=DebtSeverity.CRITICAL) for _ in range(30)]
        result = aggregator.aggregate(items, file_loc={"/proj/a.py": 200})
        assert result.per_file_minutes["/proj/a.py"] == pytest.approx(200 * 0.5)
        assert result.recommendations["/proj/a.py"] == DebtRecommendation.REWRITE.value

    def test_no_rewrite_recommendation_without_loc(self):
        aggregator = DebtAggregator()
        result = aggregator.aggregate([_item(severity=DebtSeverity.CRITICAL)])
        assert result.recommendations["/proj/a.py"] == DebtRecommendation.FIX.value

    def test_deterministic(self):
        aggregator = DebtAggregator()
        items = [_item(severity=s, file_path=f"/p/{i}.py")
                 for i, s in enumerate([DebtSeverity.LOW, DebtSeverity.HIGH] * 5)]
        assert aggregator.aggregate(items).total_minutes == \
            aggregator.aggregate(list(reversed(items))).total_minutes


class TestEffortIntervals:
    def test_interval_is_a_range_not_a_point(self):
        aggregator = DebtAggregator()
        result = aggregator.aggregate([_item(severity=DebtSeverity.HIGH)])
        interval = result.effort_interval
        assert interval.low_minutes < interval.high_minutes
        assert interval.width_reason != ""

    def test_cognitive_share_widens_and_lowers_confidence(self):
        aggregator = DebtAggregator()
        mechanical = aggregator.aggregate([
            _item(DebtType.DOCUMENTATION, DebtSeverity.LOW,
                  description="10 undocumented public functions")])
        cognitive = aggregator.aggregate([
            _item(DebtType.DESIGN, DebtSeverity.HIGH)])
        assert mechanical.effort_interval.confidence == "high"
        assert cognitive.effort_interval.confidence == "low"

    def test_empty_debt_interval(self):
        result = DebtAggregator().aggregate([])
        assert result.total_minutes == 0.0
        assert result.effort_interval.high_minutes == 0.0

    def test_midpoint_properties(self):
        interval = EffortInterval(low_minutes=60.0, high_minutes=180.0)
        assert interval.midpoint_minutes == 120.0
        assert interval.midpoint_hours == 2.0


class TestExposureInterface:
    """Plan 03 Phase B feeds centrality; the interface must exist and default to x1."""

    def test_no_provider_means_no_multiplier(self):
        base = DebtAggregator().aggregate([_item(DebtType.DESIGN, DebtSeverity.HIGH)])
        provided = DebtAggregator(centrality_provider=lambda p: None).aggregate(
            [_item(DebtType.DESIGN, DebtSeverity.HIGH)])
        assert base.total_minutes == provided.total_minutes

    def test_central_module_multiplied_up_to_3x(self):
        item = _item(DebtType.DESIGN, DebtSeverity.HIGH)
        base = DebtAggregator().aggregate([item])
        hot = DebtAggregator(centrality_provider=lambda p: 1.0).aggregate([item])
        base_work = base.total_minutes - CONTEXT_COST_MINUTES
        hot_work = hot.total_minutes - CONTEXT_COST_MINUTES
        assert hot_work == pytest.approx(base_work * 3.0)

    def test_exposure_only_applies_to_design_debt(self):
        item = _item(DebtType.CODE, DebtSeverity.HIGH)
        base = DebtAggregator().aggregate([item])
        hot = DebtAggregator(centrality_provider=lambda p: 1.0).aggregate([item])
        assert base.total_minutes == hot.total_minutes


class TestStandardTDR:
    def test_golden_research04_worked_example(self):
        """63,987 LOC with 122,563 min debt -> TDR 6.38% -> grade B."""
        tdr = 122563 / (63987 * 30.0) * 100.0
        assert tdr == pytest.approx(6.38, abs=0.01)

    def test_analyzer_populates_tdr_and_intervals(self, tmp_path):
        source = tmp_path / "mod.py"
        source.write_text(
            "def alpha(x):\n    return x\n\n\ndef beta(y):\n    return y\n")
        report = TechnicalDebtAnalyzer().analyze(tmp_path)
        assert report.total_lines_of_code > 0
        assert report.tdr_percent is not None
        expected = (report.aggregated_debt_hours * 60.0) / (report.total_lines_of_code * 30.0) * 100.0
        assert report.tdr_percent == pytest.approx(expected)
        for item in report.debt_items:
            assert item.effort_interval is not None
            assert item.effort_interval.low_minutes < item.effort_interval.high_minutes
        # Legacy surface stays intact.
        assert report.total_debt_hours >= 0.0
        assert report.debt_ratio >= 0.0

    def test_fifty_x_bug_fixed_in_ratings(self):
        """The old Ratings-side LOC/100 denominator was ~50x off the 30 min/LOC
        anchor; when the analyzer supplies tdr_percent, Ratings must use it."""
        from types import SimpleNamespace
        from Asgard.Bragi.Ratings.services.ratings_calculator import RatingsCalculator
        calc = RatingsCalculator()
        # 10h of debt over 10,000 LOC: legacy estimate said 10/(100h) = 10% (C);
        # standard TDR says 600 min / 300,000 min = 0.2% (A).
        report = SimpleNamespace(
            total_debt_hours=10.0, total_lines_of_code=10000,
            total_debt_items=0, debt_items=[], tdr_percent=0.2,
        )
        dim = calc._calculate_maintainability(report)
        assert dim.rating == "A"
        assert dim.score == pytest.approx(0.2)
