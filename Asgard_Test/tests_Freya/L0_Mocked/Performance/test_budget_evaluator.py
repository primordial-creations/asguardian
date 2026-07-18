"""L0 tests: performance budget evaluator (Plan 03)."""

import pytest

from Asgard.Freya.Performance.models._budget_models import (
    DEFAULT_BUDGETS,
    BudgetThreshold,
    RouteArchetype,
    RouteBudget,
    default_budget_for,
)
from Asgard.Freya.Performance.models._performance_timing_models import PageLoadMetrics
from Asgard.Freya.Performance.services.budget_evaluator import (
    budget_evaluations_to_issues,
    budget_score,
    collect_metric_values,
    evaluate_budget,
)


def _budget(metric="lcp_ms", soft=1000.0, hard=2500.0, exempt=None):
    return RouteBudget(
        archetype=RouteArchetype.DOCUMENT,
        thresholds=[BudgetThreshold(metric=metric, soft=soft, hard=hard)],
        exemptions=list(exempt or []),
        exemption_reasons={m: "accepted tradeoff" for m in (exempt or [])},
    )


class TestEvaluateBudget:
    @pytest.mark.parametrize("value,expected", [
        (500.0, "pass"),
        (1000.0, "pass"),      # at soft = not above
        (1500.0, "warn"),
        (2500.0, "warn"),      # at hard = not above
        (3000.0, "fail"),
    ])
    def test_status_matrix(self, value, expected):
        evals = evaluate_budget({"lcp_ms": value}, _budget())
        assert len(evals) == 1
        assert evals[0].status == expected

    def test_exempt_wins_over_fail(self):
        evals = evaluate_budget({"lcp_ms": 9999.0}, _budget(exempt=["lcp_ms"]))
        assert evals[0].status == "exempt"
        assert evals[0].note == "accepted tradeoff"

    def test_missing_soft_only_hard(self):
        budget = _budget(soft=None, hard=2500.0)
        assert evaluate_budget({"lcp_ms": 2000.0}, budget)[0].status == "pass"
        assert evaluate_budget({"lcp_ms": 3000.0}, budget)[0].status == "fail"

    def test_missing_hard_only_soft(self):
        budget = _budget(soft=1000.0, hard=None)
        assert evaluate_budget({"lcp_ms": 2000.0}, budget)[0].status == "warn"

    def test_unmeasured_metric_skipped(self):
        assert evaluate_budget({}, _budget()) == []

    def test_default_budgets_cover_all_archetypes(self):
        for archetype in RouteArchetype:
            budget = DEFAULT_BUDGETS[archetype]
            metrics = {t.metric for t in budget.thresholds}
            assert {"lcp_ms", "cls", "tbt_ms", "js_bytes"} <= metrics

    def test_default_budget_for_returns_copy(self):
        budget = default_budget_for(RouteArchetype.DOCUMENT)
        budget.exemptions.append("lcp_ms")
        assert "lcp_ms" not in DEFAULT_BUDGETS[RouteArchetype.DOCUMENT].exemptions


class TestBudgetScore:
    def test_empty_is_zero(self):
        assert budget_score([]) == 0.0

    def test_bounds(self):
        evals = evaluate_budget({"lcp_ms": 100000.0}, _budget())
        assert budget_score(evals) == 0.0
        evals = evaluate_budget({"lcp_ms": 0.0}, _budget())
        assert budget_score(evals) == 100.0

    def test_headroom_midpoint(self):
        evals = evaluate_budget({"lcp_ms": 1750.0}, _budget())  # halfway soft->hard
        assert budget_score(evals) == pytest.approx(50.0)

    def test_exempt_counts_full(self):
        evals = evaluate_budget({"lcp_ms": 9999.0}, _budget(exempt=["lcp_ms"]))
        assert budget_score(evals) == 100.0


class TestIssues:
    def test_fail_maps_to_critical_and_warn_to_serious(self):
        budget = _budget()
        fail_issues = budget_evaluations_to_issues(
            evaluate_budget({"lcp_ms": 3000.0}, budget), "document")
        warn_issues = budget_evaluations_to_issues(
            evaluate_budget({"lcp_ms": 1500.0}, budget), "document")
        assert fail_issues[0].severity == "critical"
        assert fail_issues[0].issue_type == "budget_fail"
        assert warn_issues[0].severity == "serious"
        assert "Lab Data" in warn_issues[0].description
        assert "document" in warn_issues[0].description

    def test_pass_and_exempt_produce_no_issue(self):
        budget = _budget(exempt=["lcp_ms"])
        assert budget_evaluations_to_issues(
            evaluate_budget({"lcp_ms": 9999.0}, budget)) == []


class TestCollectMetricValues:
    def test_from_metrics_and_resources(self):
        metrics = PageLoadMetrics(
            url="http://x",
            largest_contentful_paint=1200.0,
            cumulative_layout_shift=0.05,
            total_blocking_time=80.0,
        )

        class Resources:
            script_size = 500
            image_size = 600
            font_size = 70
            render_blocking_count = 2

        values = collect_metric_values(metrics, Resources())
        assert values["lcp_ms"] == 1200.0
        assert values["cls"] == 0.05
        assert values["tbt_ms"] == 80.0
        assert values["js_bytes"] == 500.0
        assert values["render_blocking_count"] == 2.0

    def test_missing_metrics_absent(self):
        values = collect_metric_values(PageLoadMetrics(url="http://x"))
        assert "lcp_ms" not in values and "tbt_ms" not in values
