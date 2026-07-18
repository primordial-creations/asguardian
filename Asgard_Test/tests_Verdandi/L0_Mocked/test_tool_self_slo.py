"""
Unit tests for ToolSelfSLOCalculator: Verdandi's own self-SLOs
(Analytical Yield, Freshness, Incident Recall, Actionability - Plan 09B).
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.SLO import (
    Finding,
    Incident,
    RunRecord,
    ToolSelfSLOCalculator,
)


def _run(submitted, scored, rejections, failed=0, ready_delay_min=5.0):
    now = datetime.now()
    data_closed = now
    report_ready = now + timedelta(minutes=ready_delay_min)
    return RunRecord(
        entities_submitted=submitted,
        entities_scored=scored,
        valid_rejections=rejections,
        entities_failed=failed,
        run_started=now,
        data_closed_at=data_closed,
        report_ready_at=report_ready,
    )


class TestAnalyticalYield:
    def setup_method(self):
        self.calc = ToolSelfSLOCalculator()

    def test_worked_example_80_scored_15_rejected_is_95_percent(self):
        # 80 scored + 15 rejected out of 100 submitted -> 0.95 yield, and
        # since 80+15=95 < 100 this is also the silent-drop example (5
        # submitted entities have no accounted disposition).
        run = _run(submitted=100, scored=80, rejections=15)
        result = self.calc.analytical_yield(run)
        assert result.value == pytest.approx(0.95)
        assert result.integrity_errors != []

    def test_silent_drop_flags_integrity_error(self):
        # submitted > scored + rejected + failed -> 10 entities vanished.
        run = _run(submitted=100, scored=80, rejections=10, failed=0)
        result = self.calc.analytical_yield(run)
        assert result.integrity_errors != []

    def test_full_accounting_meets_target(self):
        run = _run(submitted=1000, scored=996, rejections=4)
        result = self.calc.analytical_yield(run)
        assert result.meets_target is True

    def test_no_submissions_is_insufficient_data(self):
        run = _run(submitted=0, scored=0, rejections=0)
        result = self.calc.analytical_yield(run)
        assert result.insufficient_data is True
        assert result.value is None


class TestFreshness:
    def setup_method(self):
        self.calc = ToolSelfSLOCalculator()

    def test_all_runs_within_threshold(self):
        runs = [_run(10, 10, 0, ready_delay_min=5.0) for _ in range(5)]
        result = self.calc.freshness(runs, threshold_minutes=15.0)
        assert result.value == 1.0
        assert result.meets_target is True

    def test_some_runs_stale(self):
        runs = [_run(10, 10, 0, ready_delay_min=5.0) for _ in range(3)]
        runs += [_run(10, 10, 0, ready_delay_min=30.0) for _ in range(1)]
        result = self.calc.freshness(runs, threshold_minutes=15.0)
        assert result.value == pytest.approx(0.75)

    def test_empty_runs_insufficient_data(self):
        result = self.calc.freshness([])
        assert result.insufficient_data is True


class TestIncidentRecall:
    def setup_method(self):
        self.calc = ToolSelfSLOCalculator()

    def test_recall_governance_is_data_science_freeze(self):
        now = datetime.now()
        incidents = [Incident(id="i1", severity="sev1", started_at=now)]
        findings = [Finding(id="f1", severity="high", acknowledged=True, timestamp=now)]
        result = self.calc.incident_recall(incidents, findings)
        assert result.governance == "data_science_freeze"

    def test_overlapping_finding_counts_as_recalled(self):
        now = datetime.now()
        incidents = [Incident(id="i1", severity="sev1", started_at=now)]
        findings = [Finding(id="f1", severity="high", timestamp=now + timedelta(minutes=10))]
        result = self.calc.incident_recall(incidents, findings, overlap_window=timedelta(hours=1))
        assert result.value == 1.0

    def test_no_overlap_not_recalled(self):
        now = datetime.now()
        incidents = [Incident(id="i1", severity="sev1", started_at=now)]
        findings = [Finding(id="f1", severity="high", timestamp=now + timedelta(days=5))]
        result = self.calc.incident_recall(incidents, findings, overlap_window=timedelta(hours=1))
        assert result.value == 0.0

    def test_no_high_sev_incidents_insufficient_data(self):
        now = datetime.now()
        incidents = [Incident(id="i1", severity="sev3", started_at=now)]
        result = self.calc.incident_recall(incidents, [])
        assert result.insufficient_data is True


class TestActionability:
    def setup_method(self):
        self.calc = ToolSelfSLOCalculator()

    def test_above_30_percent_meets_target(self):
        findings = (
            [Finding(id=f"f{i}", severity="high", acknowledged=True) for i in range(4)]
            + [Finding(id=f"f{i}", severity="high", acknowledged=False) for i in range(6)]
        )
        result = self.calc.actionability(findings)
        assert result.value == pytest.approx(0.4)
        assert result.meets_target is True

    def test_no_high_sev_findings_insufficient_data(self):
        findings = [Finding(id="f1", severity="low", acknowledged=False)]
        result = self.calc.actionability(findings)
        assert result.insufficient_data is True
