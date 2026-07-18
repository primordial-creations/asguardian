"""
Tests for SAVD (Severity-Adjusted Vulnerability Density) trend metrics.

Covers ``Asgard/Reporting/History/services/savd_metrics.py`` per
``_Docs/Planning/Heimdall/06_Security_Scoring_Severity.md`` §D: "Reporting/
History snapshots add SAVD (findings per KLOC by severity) and store the new
score; trend rendering emphasizes normalized density direction over
absolute counts."
"""
import tempfile
import uuid
from pathlib import Path

from Asgard.Reporting.History.infrastructure.persistence.history_schema import (
    get_lower_is_better_metrics,
)
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot
from Asgard.Reporting.History.services.history_store import HistoryStore
from Asgard.Reporting.History.services.reporting_analyzer import ReportingAnalyzerService
from Asgard.Reporting.History.services.savd_metrics import (
    SAVD_SEVERITIES,
    all_savd_metric_names,
    build_savd_metrics,
    compute_savd,
    savd_metric_name,
    total_savd,
)


class TestComputeSavd:
    def test_basic_density(self):
        densities = compute_savd({"critical": 1, "high": 3}, total_loc=2000)
        # 2000 LOC == 2 KLOC
        assert densities["savd_critical"] == 0.5
        assert densities["savd_high"] == 1.5
        assert densities["savd_medium"] == 0.0
        assert densities["savd_low"] == 0.0

    def test_all_severities_present_even_when_absent_from_input(self):
        densities = compute_savd({}, total_loc=1000)
        assert set(densities.keys()) == set(all_savd_metric_names())
        assert all(v == 0.0 for v in densities.values())

    def test_case_insensitive_severity_keys(self):
        densities = compute_savd({"CRITICAL": 2}, total_loc=1000)
        assert densities["savd_critical"] == 2.0

    def test_unknown_severity_ignored(self):
        densities = compute_savd({"informational": 100}, total_loc=1000)
        assert sum(densities.values()) == 0.0

    def test_zero_loc_never_divides_by_zero(self):
        densities = compute_savd({"critical": 5}, total_loc=0)
        assert densities["savd_critical"] == 0.0

    def test_negative_loc_treated_as_unknown(self):
        densities = compute_savd({"high": 5}, total_loc=-10)
        assert densities["savd_high"] == 0.0

    def test_size_blindness_is_fixed(self):
        # 5 findings in a 10k-LOC repo is a much bigger problem than the
        # same 5 findings in a 500k-LOC repo -- SAVD must distinguish them
        # (the whole point of normalizing, per plan 06 rationale).
        small_repo = compute_savd({"high": 5}, total_loc=10_000)
        large_repo = compute_savd({"high": 5}, total_loc=500_000)
        assert small_repo["savd_high"] > large_repo["savd_high"]


class TestSavdMetricNaming:
    def test_savd_metric_name(self):
        assert savd_metric_name("Critical") == "savd_critical"

    def test_all_savd_metric_names_matches_severities(self):
        assert all_savd_metric_names() == [f"savd_{s}" for s in SAVD_SEVERITIES]

    def test_all_savd_metrics_are_lower_is_better(self):
        # Falling density is always the "improving" direction for a
        # normalized vulnerability count, regardless of severity bucket.
        registered = get_lower_is_better_metrics()
        for name in all_savd_metric_names():
            assert name in registered


class TestBuildSavdMetrics:
    def test_produces_one_metricsnapshot_per_severity(self):
        metrics = build_savd_metrics({"critical": 1}, total_loc=1000)
        assert len(metrics) == len(SAVD_SEVERITIES)
        names = {m.metric_name for m in metrics}
        assert names == set(all_savd_metric_names())

    def test_unit_label_set(self):
        metrics = build_savd_metrics({"low": 2}, total_loc=1000)
        assert all(m.unit == "findings/KLOC" for m in metrics)

    def test_mergeable_into_snapshot_metrics(self):
        snapshot = AnalysisSnapshot(snapshot_id=str(uuid.uuid4()), project_path="/repo")
        snapshot.metrics.extend(build_savd_metrics({"high": 4}, total_loc=4000))
        assert snapshot.get_metric("savd_high") == 1.0


class TestTotalSavd:
    def test_sums_all_buckets(self):
        total = total_savd({"critical": 1, "high": 1, "medium": 1, "low": 1}, total_loc=1000)
        assert total == 4.0

    def test_zero_when_no_findings(self):
        assert total_savd({}, total_loc=1000) == 0.0


class TestSavdTrendIntegration:
    """SAVD metrics flow through the same generic MetricSnapshot pipeline as
    every other tracked metric, so trend direction/density-over-time comes
    for free from ReportingAnalyzerService once persisted."""

    def _make_store(self) -> HistoryStore:
        db_path = Path(tempfile.mkdtemp()) / "history.db"
        return HistoryStore(db_path=db_path)

    def test_savd_trend_direction_improving_when_density_drops(self):
        store = self._make_store()
        project = "/repo/savd-project"

        old_snapshot = AnalysisSnapshot(snapshot_id=str(uuid.uuid4()), project_path=project)
        old_snapshot.metrics.extend(build_savd_metrics({"high": 10}, total_loc=10_000))
        store.save_snapshot(old_snapshot)

        new_snapshot = AnalysisSnapshot(snapshot_id=str(uuid.uuid4()), project_path=project)
        new_snapshot.metrics.extend(build_savd_metrics({"high": 2}, total_loc=10_000))
        store.save_snapshot(new_snapshot)

        analyzer = ReportingAnalyzerService(repository=store._repository)
        report = analyzer.get_trend_report(project, metric_names=["savd_high"])

        trend = next(t for t in report.metric_trends if t.metric_name == "savd_high")
        assert trend.current_value < trend.previous_value
        from Asgard.Reporting.History.models.history_models import TrendDirection
        assert trend.direction == TrendDirection.IMPROVING
