"""
Tests for Plan Bragi-06 remainder: git-diff parsing engine, small-change
wiring, legacy-touched warnings, project state store discipline, hotspot
ranking, root-cause grouping, and the enriched two-tier gate presets.
"""

import subprocess
from pathlib import Path

import pytest

from Asgard.Bragi.QualityGate.baseline_store import BranchBaseline
from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    GateFinding,
    GateStatus,
    MetricType,
)
from Asgard.Bragi.QualityGate.services._differential_engine import (
    DifferentialGateEngine,
)
from Asgard.Bragi.QualityGate.services._git_diff import (
    LineRange,
    git_changed_lines,
    line_in_changes,
    parse_unified_diff,
    total_changed_lines,
)
from Asgard.Bragi.QualityGate.services._hotspot_ranker import (
    HotspotRanker,
    git_churn,
)
from Asgard.Bragi.QualityGate.services._project_state_store import (
    ProjectState,
    ProjectStateStore,
    ReadOnlyStateError,
)
from Asgard.Bragi.QualityGate.services._quality_gate_helpers import (
    build_asgard_main_gate,
    validate_gate_determinism,
)
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import (
    QualityGateEvaluator,
)

DIFF_SAMPLE = """\
diff --git a/pkg/mod.py b/pkg/mod.py
index 111..222 100644
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -10,0 +11,3 @@ def f():
+a = 1
+b = 2
+c = 3
@@ -40 +43 @@ def g():
-old = 1
+new = 1
diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,5 +0,0 @@
-x
diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+hello = 1
+world = 2
"""


def finding(rule="R1", path="pkg/mod.py", line=12, severity="high",
            fingerprint="fp-1"):
    return GateFinding(rule_id=rule, file_path=path, line=line,
                       severity=severity, fingerprint=fingerprint)


class TestDiffParsing:
    def test_parse_hunks_and_files(self):
        changed = parse_unified_diff(DIFF_SAMPLE)
        assert changed["pkg/mod.py"] == [LineRange(11, 3), LineRange(43, 1)]
        assert changed["new.py"] == [LineRange(1, 2)]
        assert "gone.py" not in changed  # pure deletion

    def test_total_changed_lines(self):
        assert total_changed_lines(parse_unified_diff(DIFF_SAMPLE)) == 6

    def test_line_in_changes(self):
        changed = parse_unified_diff(DIFF_SAMPLE)
        assert line_in_changes(changed, "pkg/mod.py", 12)
        assert line_in_changes(changed, "pkg/mod.py", 43)
        assert not line_in_changes(changed, "pkg/mod.py", 20)
        assert line_in_changes(changed, "new.py", None)  # file-level match

    def test_git_changed_lines_against_real_repo(self, tmp_path):
        def run(*args):
            subprocess.run(["git", "-C", str(tmp_path), *args],
                           check=True, capture_output=True)
        run("init", "-q", "-b", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
        run("add", ".")
        run("commit", "-qm", "base")
        run("checkout", "-qb", "feature")
        (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n")
        run("add", ".")
        run("commit", "-qm", "add z")
        changed = git_changed_lines(tmp_path, base="main", head="feature")
        assert changed == {"a.py": [LineRange(3, 1)]}

    def test_git_failure_raises(self, tmp_path):
        with pytest.raises(RuntimeError):
            git_changed_lines(tmp_path, base="main", head="HEAD")


class TestSmallChangeWiring:
    def test_below_threshold_passes_by_policy(self):
        engine = DifferentialGateEngine()
        baseline = BranchBaseline(branch="main", fingerprints=[])
        result = engine.evaluate(
            [finding(severity="critical")], baseline,
            changed_files={"pkg/mod.py": [LineRange(11, 3)]},
            small_change_threshold_lines=20,
        )
        assert result.status == GateStatus.PASSED
        assert result.skipped_small_change is True
        assert result.changed_lines == 3
        assert "small change" in result.summary

    def test_at_or_above_threshold_evaluates_normally(self):
        engine = DifferentialGateEngine()
        baseline = BranchBaseline(branch="main", fingerprints=[])
        result = engine.evaluate(
            [finding(severity="critical")], baseline,
            changed_files={"pkg/mod.py": [LineRange(11, 25)]},
            small_change_threshold_lines=20,
        )
        assert result.skipped_small_change is False
        assert result.status == GateStatus.FAILED

    def test_evaluator_forwards_threshold(self):
        evaluator = QualityGateEvaluator()
        baseline = BranchBaseline(branch="main", fingerprints=[])
        result = evaluator.evaluate_differential(
            [finding(severity="critical")],
            baseline=baseline,
            changed_files={"pkg/mod.py": [LineRange(11, 3)]},
            small_change_threshold_lines=20,
        )
        assert result.skipped_small_change is True


class TestLegacyTouched:
    def test_preexisting_on_modified_line_warns(self):
        engine = DifferentialGateEngine()
        baseline = BranchBaseline(branch="main", fingerprints=["fp-legacy"])
        legacy = finding(line=12, fingerprint="fp-legacy")
        result = engine.evaluate(
            [legacy], baseline,
            changed_files={"pkg/mod.py": [LineRange(11, 3)]},
        )
        assert result.preexisting_count == 1
        assert result.legacy_touched_findings == [legacy]
        assert result.status == GateStatus.WARNING
        assert "legacy finding(s) on modified lines" in result.summary

    def test_untouched_legacy_stays_invisible(self):
        engine = DifferentialGateEngine()
        baseline = BranchBaseline(branch="main", fingerprints=["fp-legacy"])
        result = engine.evaluate(
            [finding(line=99, fingerprint="fp-legacy")], baseline,
            changed_files={"pkg/mod.py": [LineRange(11, 3)]},
        )
        assert result.legacy_touched_findings == []
        assert result.status == GateStatus.PASSED


class TestProjectStateStore:
    def test_readonly_store_never_writes(self, tmp_path):
        store = ProjectStateStore(tmp_path)  # PR scope: read-only default
        with pytest.raises(ReadOnlyStateError):
            store.save(ProjectState())
        assert not store.store_path.exists()

    def test_main_scan_writes_and_pr_reads(self, tmp_path):
        writer = ProjectStateStore(tmp_path, writable=True)
        writer.save(ProjectState(commit="abc",
                                 violation_fingerprints=["f1", "f2"],
                                 debt_minutes=120.0))
        reader = ProjectStateStore(tmp_path)
        state = reader.load()
        assert state.commit == "abc"
        assert state.fingerprint_set == {"f1", "f2"}
        assert state.debt_minutes == 120.0

    def test_merge_delta_applies_arithmetic(self, tmp_path):
        writer = ProjectStateStore(tmp_path, writable=True)
        writer.save(ProjectState(violation_fingerprints=["f1", "f2"]))
        state = writer.merge_delta(
            commit="def",
            resolved_fingerprints=["f1"],
            new_fingerprints=["f3"],
            debt_minutes=90.0,
            file_scores={"a.py": 0.8},
            interface_hashes={"a.py": "h1"},
        )
        assert state.fingerprint_set == {"f2", "f3"}
        assert state.debt_minutes == 90.0
        assert state.file_scores == {"a.py": 0.8}
        assert state.interface_hashes == {"a.py": "h1"}


class TestHotspotRanker:
    def test_priority_is_severity_times_churn_times_reachability(self):
        ranker = HotspotRanker(
            churn={"hot.py": 20},
            reachability_provider=lambda p: 1.0 if "hot" in p else 0.0,
        )
        hot = finding(path="hot.py", severity="medium", fingerprint="a")
        cold = finding(path="cold.py", severity="medium", fingerprint="b")
        ranked = ranker.rank([cold, hot])
        assert ranked[0].finding.file_path == "hot.py"
        # medium=2.0, churn 1+20/10=3.0, reach 1+1.0=2.0 -> 12.0
        assert ranked[0].priority == pytest.approx(12.0)
        # cold: 2.0 x 1.0 x 1.0
        assert ranked[1].priority == pytest.approx(2.0)

    def test_high_severity_low_churn_can_lose_to_hot_medium(self):
        ranker = HotspotRanker(churn={"hot.py": 50})
        quiet_high = finding(path="cold.py", severity="high")
        hot_medium = finding(path="hot.py", severity="medium")
        ranked = ranker.rank([quiet_high, hot_medium])
        assert ranked[0].finding.file_path == "hot.py"  # 2 x 6 = 12 > 5

    def test_root_cause_grouping(self):
        ranker = HotspotRanker(
            origin_key=lambda f: f.message or f.file_path)
        findings = [
            GateFinding(rule_id="R1", file_path=f"user{i}.py",
                        severity="medium", message="core.auth.validate")
            for i in range(3)
        ] + [GateFinding(rule_id="R2", file_path="other.py",
                         severity="low", message="other.helper")]
        groups = ranker.group_by_root_cause(findings)
        assert groups[0].origin == "core.auth.validate"
        assert groups[0].finding_count == 3
        assert "resolves 3 finding(s)" in groups[0].summary

    def test_git_churn_reads_history(self, tmp_path):
        def run(*args):
            subprocess.run(["git", "-C", str(tmp_path), *args],
                           check=True, capture_output=True)
        run("init", "-q", "-b", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        for i in range(3):
            (tmp_path / "busy.py").write_text(f"x = {i}\n")
            run("add", ".")
            run("commit", "-qm", f"c{i}")
        churn = git_churn(tmp_path)
        assert churn.get("busy.py") == 3

    def test_git_churn_not_a_repo_degrades(self, tmp_path):
        assert git_churn(tmp_path) == {}


class TestTierTwoGate:
    def test_main_gate_has_tier2_conditions(self):
        gate = build_asgard_main_gate()
        metrics = {str(c.metric) for c in gate.conditions}
        assert MetricType.COMPOSITE_SCORE.value in metrics
        assert MetricType.RISK_PROFILE_E_LOC_PCT.value in metrics
        assert MetricType.DEPENDENCY_CYCLES.value in metrics
        assert MetricType.PROHIBITED_LICENSE_COUNT.value in metrics

    def test_tier2_conditions_skip_when_not_supplied(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(build_asgard_main_gate(), {
            MetricType.SECURITY_RATING: "A",
            MetricType.RELIABILITY_RATING: "A",
            MetricType.MAINTAINABILITY_RATING: "A",
            MetricType.DUPLICATION_PERCENTAGE: 1.0,
            MetricType.COMMENT_DENSITY: 20.0,
            MetricType.API_DOCUMENTATION_COVERAGE: 90.0,
            MetricType.CRITICAL_VULNERABILITIES: 0,
        })
        assert result.status == GateStatus.PASSED

    def test_prohibited_license_fails_gate(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(build_asgard_main_gate(), {
            MetricType.SECURITY_RATING: "A",
            MetricType.RELIABILITY_RATING: "A",
            MetricType.MAINTAINABILITY_RATING: "A",
            MetricType.DUPLICATION_PERCENTAGE: 1.0,
            MetricType.COMMENT_DENSITY: 20.0,
            MetricType.API_DOCUMENTATION_COVERAGE: 90.0,
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.PROHIBITED_LICENSE_COUNT: 1,
        })
        assert result.status == GateStatus.FAILED

    def test_no_new_hard_block_on_heuristics(self):
        # The Tier-2 additions must not violate the 99%-precision rule.
        warnings = validate_gate_determinism(build_asgard_main_gate())
        heuristic_new = [w for w in warnings
                         if "composite_score" in w or "risk_profile" in w
                         or "dependency_cycles" in w]
        assert heuristic_new == []
