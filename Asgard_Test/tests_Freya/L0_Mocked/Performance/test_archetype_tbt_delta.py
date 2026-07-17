"""L0 tests: archetype heuristics, TBT arithmetic, delta snapshots, labeling."""

import pytest

from Asgard.Freya.Performance.models import (
    LAB_DATA_HEADER,
    PageLoadMetrics,
    PerformanceReport,
    RouteArchetype,
)
from Asgard.Freya.Performance.services._archetype_detector import detect_archetype
from Asgard.Freya.Performance.services._page_load_helpers import (
    build_metrics,
    calculate_score,
    compute_tbt,
)
from Asgard.Freya.Performance.models._performance_timing_models import NavigationTiming
from Asgard.Freya.Performance.services.budget_evaluator import evaluate_budget
from Asgard.Freya.Performance.models._budget_models import default_budget_for
from Asgard.Freya.Performance.services.performance_delta import (
    apply_delta_snapshot,
    compute_deltas,
    load_snapshot,
    save_snapshot,
    snapshot_from_report,
)


class TestArchetypeDetector:
    def test_rich_app_spa_markers(self):
        signals = {
            "has_spa_root": True,
            "spa_root_text_nodes": 0,
            "html_bytes": 1000,
            "has_history_routing": True,
        }
        archetype, reason = detect_archetype(signals, js_bytes=10000)
        assert archetype == RouteArchetype.RICH_APP
        assert "heuristic" in reason and "override in budget config" in reason

    def test_document_text_dominant(self):
        signals = {
            "has_spa_root": False,
            "dom_node_count": 100,
            "text_bytes": 5000,
            "form_count": 1,
            "search_form_count": 1,
            "article_count": 2,
            "heading_count": 6,
        }
        archetype, reason = detect_archetype(signals)
        assert archetype == RouteArchetype.DOCUMENT
        assert "heuristic" in reason

    def test_transactional_default(self):
        signals = {
            "has_spa_root": False,
            "dom_node_count": 500,
            "text_bytes": 100,
            "form_count": 3,
            "search_form_count": 0,
        }
        archetype, reason = detect_archetype(signals)
        assert archetype == RouteArchetype.TRANSACTIONAL

    def test_empty_signals_default_transactional(self):
        archetype, _ = detect_archetype({})
        assert archetype == RouteArchetype.TRANSACTIONAL


class TestComputeTbt:
    def test_sums_excess_over_50ms(self):
        tasks = [
            {"start": 100, "duration": 120},  # 70 blocking
            {"start": 300, "duration": 50},   # 0
            {"start": 400, "duration": 51},   # 1
        ]
        assert compute_tbt(tasks) == pytest.approx(71.0)

    def test_tasks_before_fcp_excluded(self):
        tasks = [{"start": 10, "duration": 200}, {"start": 500, "duration": 150}]
        assert compute_tbt(tasks, fcp=100.0) == pytest.approx(100.0)

    def test_tasks_after_window_end_excluded(self):
        tasks = [{"start": 900, "duration": 200}]
        assert compute_tbt(tasks, fcp=0.0, window_end=500.0) == 0.0

    def test_empty(self):
        assert compute_tbt([]) == 0.0

    def test_build_metrics_populates_tbt(self):
        metrics = build_metrics(
            "http://x", NavigationTiming(),
            {"fcp": 100.0, "long_tasks": [{"start": 200, "duration": 150}]},
        )
        assert metrics.total_blocking_time == pytest.approx(100.0)

    def test_build_metrics_no_longtasks_leaves_tbt_none(self):
        metrics = build_metrics("http://x", NavigationTiming(), {"fcp": 100.0})
        assert metrics.total_blocking_time is None


class TestScoreFromHeadroom:
    def test_score_with_evaluations_uses_headroom(self):
        metrics = PageLoadMetrics(url="http://x", largest_contentful_paint=1000.0)
        budget = default_budget_for(RouteArchetype.DOCUMENT)
        evals = evaluate_budget({"lcp_ms": 1000.0}, budget)
        score = calculate_score(metrics, evals)
        assert 0.0 <= score <= 100.0
        assert score == 100.0

    def test_legacy_path_without_evaluations(self):
        metrics = PageLoadMetrics(url="http://x")
        score = calculate_score(metrics)
        assert 0.0 <= score <= 100.0


class TestDeltaSnapshot:
    def _report(self, lcp):
        return PerformanceReport(
            url="http://x",
            page_load_metrics=PageLoadMetrics(
                url="http://x", largest_contentful_paint=lcp,
                time_to_first_byte=100.0, page_load=1000.0,
            ),
        )

    def test_roundtrip_and_delta(self, tmp_path):
        path = str(tmp_path / "performance_baseline.json")
        first = apply_delta_snapshot(self._report(1000.0), path)
        assert first == {}
        second = apply_delta_snapshot(self._report(1300.0), path)
        assert second["lcp_ms"] == pytest.approx(300.0)

    def test_load_missing_returns_none(self, tmp_path):
        assert load_snapshot(str(tmp_path / "nope.json")) is None

    def test_load_corrupt_returns_none(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        assert load_snapshot(str(path)) is None

    def test_compute_deltas_common_keys_only(self):
        assert compute_deltas({"a": 2.0, "b": 1.0}, {"a": 1.0}) == {"a": 1.0}

    def test_snapshot_from_report_and_save(self, tmp_path):
        snapshot = snapshot_from_report(self._report(1500.0))
        assert snapshot["lcp_ms"] == 1500.0
        path = str(tmp_path / "snap.json")
        save_snapshot(path, snapshot, url="http://x")
        assert load_snapshot(path) == snapshot


class TestLabeling:
    def test_report_carries_lab_disclaimer_by_default(self):
        report = PerformanceReport(url="http://x")
        assert report.lab_data_disclaimer == LAB_DATA_HEADER
        assert "Lab Data" in report.lab_data_disclaimer

    def test_report_json_roundtrip_with_and_without_new_fields(self):
        bare = PerformanceReport(url="http://x")
        again = PerformanceReport.model_validate_json(bare.model_dump_json())
        assert again.archetype is None and again.budget_evaluations == []

        full = PerformanceReport(
            url="http://x",
            archetype=RouteArchetype.RICH_APP,
            archetype_reason="explicit",
            metric_deltas={"lcp_ms": -20.0},
        )
        again = PerformanceReport.model_validate_json(full.model_dump_json())
        assert again.archetype == RouteArchetype.RICH_APP
        assert again.metric_deltas["lcp_ms"] == -20.0

    def test_fid_grade_deprecated_none_by_default(self):
        metrics = PageLoadMetrics(url="http://x")
        assert metrics.fid_grade is None
